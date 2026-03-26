import boto3

textract = boto3.client('textract')

SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:510728438979:textract-topic"
TEXTRACT_ROLE_ARN = "arn:aws:iam::510728438979:role/textract"

def lambda_handler(event, context):

    print("EVENT:", event)

    for record in event['Records']:

        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        print("Processing:", key)

        if not key.endswith(".pdf"):
            print("Skipping non-pdf")
            continue

        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            },
            NotificationChannel={
                'SNSTopicArn': SNS_TOPIC_ARN,
                'RoleArn': TEXTRACT_ROLE_ARN
            }
        )

        print("✅ Job started:", response['JobId'])

    return {
        "statusCode": 200,
        "body": "Textract job started"
    }
