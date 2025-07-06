import json
import os
import boto3
from datetime import datetime

# Initialize AWS clients
s3 = boto3.client("s3")
ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Environment variables
RAW_BUCKET = os.environ['RAW_BUCKET']
ENRICHED_BUCKET = os.environ['ENRICHED_BUCKET']
LOOKUP_BUCKET = os.environ['LOOKUP_BUCKET']
LOOKUP_REGION = os.environ['LOOKUP_REGION']

# If your lookup bucket is in a different region, configure a separate client
# lookup_s3 = boto3.client('s3', region_name=LOOKUP_REGION)

def lambda_handler(event, context):
    for record in event.get('Records', []):
        # Parse the SQS message
        body = json.loads(record['body'])
        s3_key = body.get('s3_key')

        # 1. Fetch raw event JSON from S3
        raw_obj = s3.get_object(Bucket=RAW_BUCKET, Key=s3_key)
        lead_data = json.loads(raw_obj['Body'].read())
        lead_id = lead_data.get('lead_id', 'unknown')

        # 2. Fetch lookup JSON from the lookup bucket
        lookup_key = f"{lead_id}.json"
        lookup_obj = s3.get_object(Bucket=LOOKUP_BUCKET, Key=lookup_key)
        owner_data = json.loads(lookup_obj['Body'].read())

        # 3. Merge raw data and lookup data
        enriched = {**lead_data, **owner_data}

        # 4. Write enriched JSON back to S3
        timestamp = int(datetime.utcnow().timestamp())
        enriched_key = f"enriched/crm_enriched_{lead_id}_{timestamp}.json"
        s3.put_object(
            Bucket=ENRICHED_BUCKET,
            Key=enriched_key,
            Body=json.dumps(enriched)
        )

        # 5. Send notification email via SES
        from_addr = os.environ['SES_FROM_ADDRESS']
        to_addrs = os.environ['SES_TO_ADDRESS'].split(',')
        subject = f"New Enriched Lead: {lead_id}"
        body_text = (
            f"Lead ID: {lead_id}\n"
            f"Name: {lead_data.get('display_name')}\n"
            f"Owner: {owner_data.get('lead_owner')}\n"
            f"Status: {owner_data.get('status_label')}\n"
            f"Created: {owner_data.get('date_created')}\n"
            f"S3 Key: {enriched_key}"
        )
        ses.send_email(
            Source=from_addr,
            Destination={"ToAddresses": to_addrs},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body_text}}
            }
        )

    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'enriched'})
    }
