import os, sys, time
from urllib.parse import urlparse
import boto3
from botocore.config import Config

bucket = os.getenv("MINIO_BUCKET", "docs")
endpoint = os.getenv("MINIO_ENDPOINT", "[minio](http://minio:9000)")
access_key = os.getenv("MINIO_ROOT_USER", "admin")
secret_key = os.getenv("MINIO_ROOT_PASSWORD", "adminadmin")
region = os.getenv("MINIO_REGION", "us-east-1")

def client():
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )

if __name__ == "__main__":
    s3 = client()
    for _ in range(30):
        try:
            s3.list_buckets()
            break
        except Exception:
            time.sleep(2)
    resp = s3.list_buckets()
    names = [b["Name"] for b in resp.get("Buckets", [])]
    if bucket not in names:
        s3.create_bucket(Bucket=bucket)
        print(f"Created bucket {bucket}")
    else:
        print(f"Bucket {bucket} already exists")
