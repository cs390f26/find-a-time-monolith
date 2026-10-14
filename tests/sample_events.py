"""Named sample events for tests, loaded from scripts/sample_data.json.

The same events are documented in the specs repo (sample.data.md) and loaded by
scripts/seed_data.py.

  KICKOFF   - brand-new event, zero responses, newest createdAt, 3 slots
  STUDY     - clear winner (slot_2), one fallback response, 7 people
  DINNER    - tie for best time (slot_1 and slot_3), 8 people
  STANDUP   - minimum of 2 slots, 2 people, oldest createdAt
"""

import json
from pathlib import Path

from findatime.event_types import EventData

_SAMPLE_FILE = Path(__file__).resolve().parent.parent / "scripts" / "sample_data.json"


def _load() -> dict[str, EventData]:
    events = {}
    for item in json.loads(_SAMPLE_FILE.read_text()):
        events[item["id"]] = EventData(
            event_id=item["id"],
            created_at=item["createdAt"],
            title=item["title"],
            notes=item.get("notes", ""),
            slots=item["timeSlots"],
        )
    return events


_events = _load()

KICKOFF = _events["ev_101a9b2c"]
STUDY = _events["ev_202c4d5e"]
DINNER = _events["ev_303e6f7a"]
STANDUP = _events["ev_404g8h9i"]

ALL_SAMPLE_EVENTS = [KICKOFF, STUDY, DINNER, STANDUP]

# Two valid candidate slots, reused by tests that create events.
TWO_SLOTS = [
    {"startTime": "2026-10-15T14:00:00Z", "endTime": "2026-10-15T15:00:00Z"},
    {"startTime": "2026-10-16T16:00:00Z", "endTime": "2026-10-16T17:00:00Z"},
]
