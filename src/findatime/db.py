import boto3
from botocore.exceptions import BotoCoreError, ClientError
from findatime.event_types import EventData, item_from_event_data, event_data_from_item


class DatabaseUnavailableError(Exception):
    """Raised when the database or table cannot be reached."""


class EventStorage:
    """Stores and loads Find-a-Time events in DynamoDB using boto3."""

    def __init__(self, table_name: str, region_name: str, endpoint_url: str | None = None):
        if not table_name:
            raise ValueError("table_name is required")
        if not region_name:
            raise ValueError("region_name is required")

        if endpoint_url is not None:
            resource = boto3.resource("dynamodb", region_name=region_name, endpoint_url=endpoint_url)
        else:
            resource = boto3.resource("dynamodb", region_name=region_name)
        self._table = resource.Table(table_name)

    def ping(self) -> None:
        """Check that the table exists and is ACTIVE."""
        try:
            self._table.load()
        except (BotoCoreError, ClientError) as exc:
            raise DatabaseUnavailableError(f"Database unavailable: {exc}") from exc

        if self._table.table_status != "ACTIVE":
            raise DatabaseUnavailableError(f"Table {self._table.name!r} is not ACTIVE")

    def add_event(self, event: EventData) -> None:
        """Store a new event item in DynamoDB."""
        try:
            self._table.put_item(Item=item_from_event_data(event))
        except (BotoCoreError, ClientError) as exc:
            raise DatabaseUnavailableError(f"Database unavailable: {exc}") from exc

    def get_event(self, event_id: str) -> EventData | None:
        """Retrieve a single event by its eventId, or None if not found."""
        try:
            response = self._table.get_item(Key={"eventId": event_id})
        except (BotoCoreError, ClientError) as exc:
            raise DatabaseUnavailableError(f"Database unavailable: {exc}") from exc

        item = response.get("Item")
        if item is None:
            return None
        return event_data_from_item(item)

    def list_events(self) -> list[EventData]:
        """Scan and return all events from the table."""
        try:
            items = []
            response = self._table.scan()
            items.extend(response.get("Items", []))
            while "LastEvaluatedKey" in response:
                response = self._table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                items.extend(response.get("Items", []))
            return [event_data_from_item(item) for item in items]
        except (BotoCoreError, ClientError) as exc:
            raise DatabaseUnavailableError(f"Database unavailable: {exc}") from exc

    def update_event(self, event: EventData) -> None:
        """Update an existing event in the DynamoDB table."""
        try:
            self._table.put_item(Item=item_from_event_data(event))
        except (BotoCoreError, ClientError) as exc:
         raise DatabaseUnavailableError(f"Database unavailable: {exc}") from exc

    def delete_all_events(self) -> int:
        """Delete every event in the table (used to reset sample data). Returns how many were deleted."""
        try:
            events = self.list_events()
            with self._table.batch_writer() as batch:
                for event in events:
                    batch.delete_item(Key={"eventId": event.event_id})
            return len(events)
        except (BotoCoreError, ClientError) as exc:
            raise DatabaseUnavailableError(f"Database unavailable: {exc}") from exc