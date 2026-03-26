import json
import boto3
import re
import urllib.parse

# AWS Clients
s3 = boto3.client('s3')
textract = boto3.client('textract')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')


# ======================================================
# Helper Functions
# ======================================================

def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_education(values):

    mapping = {
        "ug": "Undergraduate",
        "pg": "Postgraduate",
        "polytechnic": "Diploma",
        "diploma": "Diploma",
        "engineering": "Engineering",
        "class": "School",
        "iti": "ITI"
    }

    normalized = []

    for v in values:

        v_lower = v.lower()

        for key in mapping:
            if key in v_lower:
                normalized.append(mapping[key])
                break
        else:
            normalized.append(v)

    return list(set(normalized))


def clean_deadline(deadline):

    if not deadline:
        return None

    if "invalid" in str(deadline).lower():
        return None

    return deadline


def normalize_docs(docs):

    cleaned = []

    for d in docs:

        d = d.lower()

        if "income" in d:
            cleaned.append("Income Certificate")

        elif "mark" in d:
            cleaned.append("Previous Marksheet")

        elif "bank" in d:
            cleaned.append("Bank Passbook")

        elif "aadhaar" in d or "id" in d:
            cleaned.append("ID Proof")

        else:
            cleaned.append(d.title())

    return list(set(cleaned))


def extract_amount_range(amount):

    if not amount:
        return None, None

    nums = re.findall(r'\d+', str(amount))

    if len(nums) == 2:
        return int(nums[0]), int(nums[1])

    if len(nums) == 1:
        return int(nums[0]), int(nums[0])

    return None, None


def extract_income_limit(text):

    nums = re.findall(r'(\d[\d,]{3,})', text)

    if nums:
        value = nums[0].replace(",", "")
        return int(value)

    return None


# ======================================================
# Lambda Handler
# ======================================================

def lambda_handler(event, context):

    print("EVENT:", json.dumps(event))

    try:

        extracted_text = ""

        # ======================================================
        # CASE 1: TXT Upload
        # ======================================================

        if 'Records' in event and 's3' in event['Records'][0]:

            bucket = event['Records'][0]['s3']['bucket']['name']
            key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])

            print("TXT Trigger:", key)

            response = s3.get_object(Bucket=bucket, Key=key)

            extracted_text = response['Body'].read().decode('utf-8')

        # ======================================================
        # CASE 2: Textract Result
        # ======================================================

        else:

            message = json.loads(event['Records'][0]['Sns']['Message'])

            job_id = message['JobId']
            bucket = message['DocumentLocation']['S3Bucket']
            key = urllib.parse.unquote_plus(message['DocumentLocation']['S3ObjectName'])

            print("Textract JobId:", job_id)

            next_token = None

            while True:

                if next_token:
                    response = textract.get_document_text_detection(
                        JobId=job_id,
                        NextToken=next_token
                    )
                else:
                    response = textract.get_document_text_detection(
                        JobId=job_id
                    )

                for block in response['Blocks']:

                    if block['BlockType'] == 'LINE':
                        extracted_text += block['Text'] + "\n"

                next_token = response.get('NextToken')

                if not next_token:
                    break

        print("Original Length:", len(extracted_text))

        extracted_text = extracted_text[:6000]

        print("Trimmed Length:", len(extracted_text))

        # ======================================================
        # File Name
        # ======================================================

        base_filename = key.split("/")[-1]
        base_filename = base_filename.replace(".pdf", "").replace(".txt", "")

        processed_bucket = "gov-schemes-processed"

        # ======================================================
        # Save Extracted Text
        # ======================================================

        s3.put_object(
            Bucket=processed_bucket,
            Key=f"extracted-text/{base_filename}.txt",
            Body=extracted_text
        )

        print("Saved extracted text")

        # ======================================================
        # Bedrock Prompt
        # ======================================================

        prompt = f"""
You are an information extraction system.

Extract scholarship information and return ONLY valid JSON.

Fields required:

name
provider
education (list)
category (list)
income_limit (number)
gender (list)
state (list)
amount
deadline
documents_required (list)
application_link

Rules:

education examples:
["10th","12th","Diploma","Engineering","Postgraduate"]

category examples:
["SC","ST","OBC","General","EWS","All"]

gender examples:
["Male","Female","All"]

state examples:
["All India"] or ["Karnataka","Tamil Nadu"]

income_limit must be number only (remove ₹ and commas)

documents_required must be a list

Return ONLY JSON.

TEXT:
{extracted_text}
"""

        # ======================================================
        # Call Bedrock
        # ======================================================

        body = json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": 900,
                "temperature": 0.1
            }
        })

        response = bedrock.invoke_model(
            modelId="amazon.nova-lite-v1:0",
            body=body,
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response['body'].read())

        raw_output = result['output']['message']['content'][0]['text']

        print("Raw Output:", raw_output)

        # ======================================================
        # Extract JSON
        # ======================================================

        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)

        if json_match:
            output_text = json_match.group(0)
        else:
            output_text = raw_output

        try:
            json_data = json.loads(output_text)
        except:
            json_data = {"raw_output": output_text}

        # ======================================================
        # Normalize Fields
        # ======================================================

        json_data["education"] = normalize_education(
            ensure_list(json_data.get("education"))
        )

        json_data["category"] = ensure_list(json_data.get("category"))
        json_data["gender"] = ensure_list(json_data.get("gender"))
        json_data["state"] = ensure_list(json_data.get("state"))

        json_data["documents_required"] = normalize_docs(
            ensure_list(json_data.get("documents_required"))
        )

        json_data["deadline"] = clean_deadline(
            json_data.get("deadline")
        )

        # ======================================================
        # Amount Parsing
        # ======================================================

        amount_min, amount_max = extract_amount_range(
            json_data.get("amount")
        )

        json_data["amount_min"] = amount_min
        json_data["amount_max"] = amount_max

        # ======================================================
        # Income Detection Fallback
        # ======================================================

        if not json_data.get("income_limit"):

            json_data["income_limit"] = extract_income_limit(
                extracted_text
            )

        # ======================================================
        # Save Structured JSON
        # ======================================================

        s3.put_object(
            Bucket=processed_bucket,
            Key=f"structured-json/{base_filename}.json",
            Body=json.dumps(json_data, ensure_ascii=False),
            ContentType="application/json"
        )

        print("Saved structured JSON")

        return {
            "statusCode": 200,
            "body": "Success"
        }

    except Exception as e:

        print("ERROR:", str(e))

        return {
            "statusCode": 500,
            "body": str(e)
        }
