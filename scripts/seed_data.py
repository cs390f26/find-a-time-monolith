"""Load the sample events (scripts/sample_data.json) into the Events table.

Usage:
    python scripts/seed_data.py           # add/overwrite the sample events
    python scripts/seed_data.py --reset   # delete ALL events first, then load the samples

The sample events are the same ones documented in the specs repo (sample.data.md).
Run scripts/create_table.py first so the table exists.
"""
import argparse
import json
import sys
from pathlib import Path

from findatime.db import DatabaseUnavailableError, EventStorage
from findatime.event_types import EventData
from findatime.settings import ensure_settings

SAMPLE_FILE = Path(__file__).with_name("sample_data.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load sample events into DynamoDB.")
    parser.add_argument("--reset", action="store_true",
                        help="delete every existing event before loading the samples")
    args = parser.parse_args()

    settings = ensure_settings()
    storage = EventStorage(
        table_name=settings["EVENTS_TABLE_NAME"],
        region_name=settings["AWS_DEFAULT_REGION"],
        endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
    )

    try:
        storage.ping()
        if args.reset:
            removed = storage.delete_all_events()
            print(f"Deleted {removed} existing event(s).")

        samples = json.loads(SAMPLE_FILE.read_text())
        for sample in samples:
            storage.add_event(EventData(
                event_id=sample["id"],
                created_at=sample["createdAt"],
                title=sample["title"],
                notes=sample.get("notes", ""),
                slots=sample["timeSlots"],
            ))
            print(f"Loaded {sample['id']}: {sample['title']}")
    except DatabaseUnavailableError as exc:
        print(f"{exc}\nIs DynamoDB Local running, and did you run scripts/create_table.py?",
              file=sys.stderr)
        sys.exit(1)

    print(f"Done: {len(samples)} sample event(s) loaded.")


if __name__ == "__main__":
    main()
