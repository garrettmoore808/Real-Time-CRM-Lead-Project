import json
import os
import boto3
from datetime import datetime

s3 = boto3.client("s3")
sqs = boto3.client("sqs")

# Environment variables set in SAM template
BUCKET = os.environ["RAW_BUCKET"]
QUEUE_URL = os.environ["DELAY_QUEUE_URL"]

def lambda_handler(event, context):
    # 1. Parse the incoming CRM payload
    body = json.loads(event.get("body", "{}"))
    lead_id = body.get("lead_id", "unknown")

    # 2. Write raw JSON to S3 with a timestamped key
    timestamp = int(datetime.utcnow().timestamp())
    key = f"raw/crm_event_{lead_id}_{timestamp}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(body)
    )

    # 3. Enqueue an SQS message to trigger enrichment after a 10-min delay
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"s3_key": key}),
        DelaySeconds=600
    )

    # 4. Return a simple 200 response
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Received", "s3_key": key})
    }
