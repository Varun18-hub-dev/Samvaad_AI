import json
import boto3
import urllib.parse

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

TABLE_NAME = "scholarships"
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):

    for record in event['Records']:

        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        print("Processing:", key)

        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')

        data = json.loads(content)

        scholarship_id = key.split("/")[-1].replace(".json", "")

        item = {
            "scholarship_id": scholarship_id,
            "name": data.get("name"),
            "provider": data.get("provider"),
            "amount": data.get("amount"),
            "eligibility": data.get("eligibility"),
            "deadline": data.get("deadline"),
            "application_link": data.get("application_link"),
            "documents_required": data.get("documents_required"),
            "courses": data.get("courses"),
            "country": data.get("country"),
            "scholarship_type": data.get("scholarship_type")
        }

        table.put_item(Item=item)

        print("Inserted:", scholarship_id)

    return {
        "statusCode": 200,
        "body": "Inserted into DynamoDB"
    }
