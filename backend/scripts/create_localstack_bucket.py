#!/usr/bin/env python3
"""
Create the LocalStack S3 bucket for local development.
Run once after `docker compose up`:
    python scripts/create_localstack_bucket.py
"""
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Allow importing app config when run from backend/ directory
sys.path.insert(0, ".")

from app.config import get_settings

settings = get_settings()


def create_bucket() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        config=Config(retries={"max_attempts": 3}),
    )

    bucket = settings.S3_BUCKET_NAME
    print(f"Creating bucket: {bucket} at {settings.S3_ENDPOINT_URL}")

    # Wait for LocalStack to be ready
    for attempt in range(10):
        try:
            s3.list_buckets()
            break
        except Exception:
            print(f"  Waiting for LocalStack... attempt {attempt + 1}/10")
            time.sleep(2)

    try:
        if settings.S3_REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": settings.S3_REGION},
            )
        print(f"✅ Bucket '{bucket}' created successfully.")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"ℹ️  Bucket '{bucket}' already exists.")
        else:
            print(f"❌ Failed to create bucket: {e}")
            sys.exit(1)

    # Set bucket CORS policy for future browser uploads
    s3.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
                    "AllowedOrigins": ["*"],
                    "MaxAgeSeconds": 3000,
                }
            ]
        },
    )
    print("✅ Bucket CORS policy set.")


if __name__ == "__main__":
    create_bucket()
