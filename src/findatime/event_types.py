from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class EventData:
    """Core data structure for a Find-a-Time event."""
    event_id: str
    created_at: str
    title: str
    notes: str
    slots: list[dict]
    # Each slot structure:
    # {"slotId": str, "startTime": str, "endTime": str, "label": str, "attendees": list[str], "tally": int}


def item_from_event_data(event: EventData) -> dict:
    """Convert an EventData Python object into a raw dictionary format that DynamoDB expects.

    timeSlots is stored as a DynamoDB List (L) of Maps, not a Map keyed by slotId.
    DynamoDB does not preserve the order of keys inside a Map, but it does preserve
    the order of a List, so a List keeps the slots in display order with the
    fallback slot last.
    """
    slots_list = []
    for slot in event.slots:
        slots_list.append({
            "slotId": slot["slotId"],
            "startTime": slot.get("startTime"),
            "endTime": slot.get("endTime"),
            "label": slot["label"],
            "attendees": slot.get("attendees", []),
            "tally": slot.get("tally", 0)
        })

    return {
        "eventId": event.event_id,
        "createdAt": event.created_at,
        "title": event.title,
        "notes": event.notes,
        "timeSlots": slots_list,
    }


def event_data_from_item(item: dict) -> EventData:
    """Convert a raw dictionary returned by DynamoDB back into a clean EventData Python object."""
    slots = []
    raw_slots = item.get("timeSlots", [])

    for slot_data in raw_slots:
        # DynamoDB returns numbers as Decimal; convert so Flask can turn it into JSON.
        tally = slot_data.get("tally", 0)
        if isinstance(tally, Decimal):
            tally = int(tally)

        slots.append({
            "slotId": slot_data["slotId"],
            "startTime": slot_data.get("startTime"),
            "endTime": slot_data.get("endTime"),
            "label": slot_data["label"],
            "attendees": list(slot_data.get("attendees", [])),
            "tally": tally
        })

    return EventData(
        event_id=item["eventId"],
        created_at=item["createdAt"],
        title=item["title"],
        notes=item.get("notes", ""),
        slots=slots,
    )

# --- View types: the shape of data each screen / API response needs ---
# The DB layer returns the full EventData. The application layer turns it into
# one of these views, and the API layer turns the view into JSON.


@dataclass(frozen=True)
class EventSummary:
    """One row in the events list (no slots)."""
    id: str
    title: str
    notes: str
    created_at: str
    attendee_count: int


@dataclass(frozen=True)
class EventQuestion:
    """Event as shown on the Respond page: slots without tallies or names."""
    id: str
    title: str
    notes: str
    created_at: str
    attendee_count: int
    time_slots: list[dict]
    # each slot: {"slotId", "startTime", "endTime", "label"}


@dataclass(frozen=True)
class EventResults:
    """Event as shown on the Results page: tallies, names and the best time(s)."""
    id: str
    title: str
    notes: str
    created_at: str
    attendee_count: int
    winning_slot_ids: list[str]
    time_slots: list[dict]
    # each slot: {"slotId", "startTime", "endTime", "label", "tally", "attendees"}


FALLBACK_SLOT_ID = "slot_fallback"


def _attendee_count(event: EventData) -> int:
    """Number of different people who responded (a name counts once, even if it picked several slots)."""
    return len({name for slot in event.slots for name in slot.get("attendees", [])})


def _winning_slot_ids(event: EventData) -> list[str]:
    """Slot(s) with the highest tally. The fallback slot never wins; no votes means no winner."""
    candidates = [s for s in event.slots if s["slotId"] != FALLBACK_SLOT_ID]
    highest = max((s["tally"] for s in candidates), default=0)
    if highest == 0:
        return []
    return [s["slotId"] for s in candidates if s["tally"] == highest]


def extract_event_summary(event: EventData) -> EventSummary:
    return EventSummary(
        id=event.event_id,
        title=event.title,
        notes=event.notes,
        created_at=event.created_at,
        attendee_count=_attendee_count(event),
    )


def extract_event_question(event: EventData) -> EventQuestion:
    slots = [
        {"slotId": s["slotId"], "startTime": s.get("startTime"),
         "endTime": s.get("endTime"), "label": s["label"]}
        for s in event.slots
    ]
    return EventQuestion(
        id=event.event_id,
        title=event.title,
        notes=event.notes,
        created_at=event.created_at,
        attendee_count=_attendee_count(event),
        time_slots=slots,
    )


def extract_event_results(event: EventData) -> EventResults:
    slots = [
        {"slotId": s["slotId"], "startTime": s.get("startTime"),
         "endTime": s.get("endTime"), "label": s["label"],
         "tally": s["tally"], "attendees": list(s.get("attendees", []))}
        for s in event.slots
    ]
    return EventResults(
        id=event.event_id,
        title=event.title,
        notes=event.notes,
        created_at=event.created_at,
        attendee_count=_attendee_count(event),
        winning_slot_ids=_winning_slot_ids(event),
        time_slots=slots,
    )
