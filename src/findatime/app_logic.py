import secrets
from datetime import datetime, timezone
from findatime.db import EventStorage, DatabaseUnavailableError
from findatime.event_types import (
    EventData,
    EventQuestion,
    EventResults,
    EventSummary,
    extract_event_question,
    extract_event_results,
    extract_event_summary,
)


class ValidationError(Exception):
    """Raised when input fails application validation rules."""


class NotFoundError(Exception):
    """Raised when an event ID does not exist."""


class ServiceUnavailableError(Exception):
    """Raised when the database cannot be reached."""


class FindATimeApp:
    """Handles core business logic and rules for the Find-a-Time application."""

    def __init__(self, storage: EventStorage):
        self._store = storage

    def health(self) -> None:
        """Verify the database is reachable."""
        try:
            self._store.ping()
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Service unavailable: database unreachable") from exc

    def create_event(self, title: str, notes: str, time_slots: list[dict]) -> str:
        """Validate input, format slots including the fallback, and store a new event."""
        # Requests can come from anywhere (e.g. curl), not just our page, so check types too.
        if title is not None and not isinstance(title, str):
            raise ValidationError("Event title must be text.")
        if notes is not None and not isinstance(notes, str):
            raise ValidationError("Notes must be text.")
        title = title.strip() if title else ""
        notes = notes.strip() if notes else ""

        if not title:
            raise ValidationError("Event title must not be blank.")
        if len(title) > 140:
            raise ValidationError("Event title must be at most 140 characters.")
        if len(notes) > 500:
            raise ValidationError("Notes must be at most 500 characters.")
        if not isinstance(time_slots, list) or not (2 <= len(time_slots) <= 6):
            raise ValidationError("Events must have between 2 and 6 time slots.")

        formatted_slots = []
        seen_times = set()

        for i, slot in enumerate(time_slots, start=1):
            if not isinstance(slot, dict):
                raise ValidationError("Each time slot must have a startTime and endTime.")
            start_str = slot.get("startTime")
            end_str = slot.get("endTime")
            
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except (AttributeError, TypeError, ValueError):
                raise ValidationError("Invalid start or end time format.")

            # Require a timezone (e.g. "Z") so all times can be compared.
            if start.tzinfo is None or end.tzinfo is None:
                raise ValidationError("Times must include a timezone, e.g. 2026-10-15T14:00:00Z.")
            label = slot.get("label")
            if label is not None and (not isinstance(label, str) or len(label) > 100):
                raise ValidationError("Slot label must be text of at most 100 characters.")

            if end <= start:
                raise ValidationError("Time slot end time must be after start time.")
            
            time_key = (start_str, end_str)
            if time_key in seen_times:
                raise ValidationError("Duplicate time slots are not allowed.")
            seen_times.add(time_key)

            formatted_slots.append({
                "slotId": f"slot_{i}",
                "startTime": start_str,
                "endTime": end_str,
                "label": slot.get("label") or start.strftime("%b %d, %I:%M %p"),
                "attendees": [],
                "tally": 0
            })

        # Automatically append the required fallback slot
        formatted_slots.append({
            "slotId": "slot_fallback",
            "startTime": None,
            "endTime": None,
            "label": "None of these work for me",
            "attendees": [],
            "tally": 0
        })

        event_id = "ev_" + secrets.token_hex(4)
        created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

        event = EventData(
            event_id=event_id,
            created_at=created_at,
            title=title,
            notes=notes,
            slots=formatted_slots
        )

        try:
            self._store.add_event(event)
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Service unavailable: database unreachable") from exc

        return event_id

    def get_event(self, event_id: str) -> EventQuestion:
        """Return an event for the Respond page (no tallies), or raise NotFoundError."""
        return extract_event_question(self._load_event(event_id))

    def get_results(self, event_id: str) -> EventResults:
        """Return tallies, names and best time(s) for an event, or raise NotFoundError."""
        return extract_event_results(self._load_event(event_id))

    def submit_response(self, event_id: str, responder_name: str, selected_slot_ids: list[str]) -> EventResults:
        """Record a participant's vote response and update tallies."""
        event = self._load_event(event_id)
        if responder_name is not None and not isinstance(responder_name, str):
            raise ValidationError("Responder name must be text.")
        responder_name = responder_name.strip() if responder_name else ""

        if not responder_name:
            raise ValidationError("Responder name must not be blank.")
        if len(responder_name) > 50:
            raise ValidationError("Responder name must be at most 50 characters.")
        if not isinstance(selected_slot_ids, list) or not selected_slot_ids:
            raise ValidationError("Must select at least one time slot.")
        if not all(isinstance(slot_id, str) for slot_id in selected_slot_ids):
            raise ValidationError("Selected time slots must be slot ids.")
        if "slot_fallback" in selected_slot_ids and len(selected_slot_ids) > 1:
            raise ValidationError("'None of these work for me' cannot be combined with other slots.")

        valid_slot_ids = {slot["slotId"] for slot in event.slots}
        if not set(selected_slot_ids).issubset(valid_slot_ids):
            raise ValidationError("Selected time slot does not exist for this event.")

        updated_slots = []
        for slot in event.slots:
            slot_copy = dict(slot)
            attendees = list(slot_copy.get("attendees", []))
            tally = slot_copy.get("tally", 0)

            if slot_copy["slotId"] in selected_slot_ids:
                attendees.append(responder_name)
                tally += 1

            slot_copy["attendees"] = attendees
            slot_copy["tally"] = tally
            updated_slots.append(slot_copy)

        updated_event = EventData(
            event_id=event.event_id,
            created_at=event.created_at,
            title=event.title,
            notes=event.notes,
            slots=updated_slots
        )

        try:
            self._store.update_event(updated_event)
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Service unavailable: database unreachable") from exc

        return extract_event_results(updated_event)

    def list_events(self) -> list[EventSummary]:
        """Return a summary of every event, newest first.

        DynamoDB Scan returns items in no particular order, so we sort here by
        createdAt. createdAt is an ISO 8601 UTC string, and those sort correctly
        as plain strings.
        """
        try:
            events = self._store.list_events()
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Service unavailable: database unreachable") from exc
        events = sorted(events, key=lambda ev: ev.created_at, reverse=True)
        return [extract_event_summary(ev) for ev in events]

    def _load_event(self, event_id: str) -> EventData:
        try:
            event = self._store.get_event(event_id)
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Service unavailable: database unreachable") from exc
        if event is None:
            raise NotFoundError(f"Event {event_id!r} not found.")
        return event