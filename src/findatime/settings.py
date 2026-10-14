import os
from typing import Dict, Any


def ensure_settings() -> Dict[str, Any]:
    """Load and validate environment configuration settings."""
    return {
        "EVENTS_TABLE_NAME": os.environ.get("EVENTS_TABLE_NAME", "Events"),
        "DYNAMODB_ENDPOINT_URL": os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8000"),
        "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    }