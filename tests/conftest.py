import pytest
import boto3
from findatime.settings import ensure_settings

@pytest.fixture(autouse=True)
def clear_dynamodb_table():
    """Clear the Events table before every test to ensure complete test isolation."""
    settings = ensure_settings()
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings["AWS_DEFAULT_REGION"],
        endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
    )
    table = dynamodb.Table(settings["EVENTS_TABLE_NAME"])
    
    # Dynamically find the primary key name from the table schema
    try:
        key_schema = table.key_schema
        pk_name = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "HASH"), "id")
        
        response = table.scan()
        for item in response.get("Items", []):
            table.delete_item(Key={pk_name: item[pk_name]})
    except Exception:
        pass
    
    yield