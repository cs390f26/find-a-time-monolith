import sys
import boto3
from botocore.exceptions import ClientError
from findatime.settings import ensure_settings


def main() -> None:
    """Provision the DynamoDB table for Find-a-Time events."""
    try:
        settings = ensure_settings()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    table_name = settings.get("EVENTS_TABLE_NAME", "Events")
    endpoint_url = settings.get("DYNAMODB_ENDPOINT_URL")
    region_name = settings["AWS_DEFAULT_REGION"]

    print(f"Connecting to DynamoDB at {endpoint_url or 'AWS Cloud'} (Region: {region_name})...")
    
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=region_name,
        endpoint_url=endpoint_url,
    )

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "eventId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "eventId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Waiting for table {table_name!r} to become active...")
        table.wait_until_exists()
        print(f"Table {table_name!r} created and active successfully.")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code == "ResourceInUseException":
            print(f"Table {table_name!r} already exists.", file=sys.stderr)
        else:
            print(f"Error creating table: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()