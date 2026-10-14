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