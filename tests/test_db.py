"""Tests for db.py (EventStorage): saving and loading events in DynamoDB."""

import pytest
from sample_events import ALL_SAMPLE_EVENTS, KICKOFF, STUDY

from findatime.db import DatabaseUnavailableError, EventStorage
from findatime.event_types import EventData


def test_init_requires_table_name():
    with pytest.raises(ValueError, match="table_name"):
        EventStorage(table_name="", region_name="us-east-1")


def test_init_requires_region_name():
    with pytest.raises(ValueError, match="region_name"):
        EventStorage(table_name="Events", region_name="")


def test_ping_succeeds_when_table_exists(store):
    store.ping()  # no exception means the database is usable


def test_ping_raises_when_table_missing(missing_table_store):
    with pytest.raises(DatabaseUnavailableError):
        missing_table_store.ping()


def test_add_and_get_event(store):
    store.add_event(STUDY)
    assert store.get_event(STUDY.event_id) == STUDY


def test_get_event_keeps_slot_order(store):
    # Regression test: slots used to come back in random order.
    store.add_event(STUDY)
    loaded = store.get_event(STUDY.event_id)
    assert [s["slotId"] for s in loaded.slots] == ["slot_1", "slot_2", "slot_3", "slot_fallback"]


def test_get_event_returns_none_when_missing(store):
    assert store.get_event("does-not-exist") is None


def test_list_events_empty(store):
    assert store.list_events() == []


def test_list_events_returns_every_sample(store):
    for event in ALL_SAMPLE_EVENTS:
        store.add_event(event)
    events = store.list_events()
    # list_events does not sort; compare membership, not order.
    assert len(events) == len(ALL_SAMPLE_EVENTS)
    for event in ALL_SAMPLE_EVENTS:
        assert event in events


def test_update_event_replaces_stored_event(store):
    store.add_event(KICKOFF)
    slots = [dict(s) for s in KICKOFF.slots]
    slots[0] = {**slots[0], "tally": 1, "attendees": ["Alice"]}
    updated = EventData(KICKOFF.event_id, KICKOFF.created_at, KICKOFF.title, KICKOFF.notes, slots)

    store.update_event(updated)

    assert store.get_event(KICKOFF.event_id) == updated


def test_delete_all_events(store):
    for event in ALL_SAMPLE_EVENTS:
        store.add_event(event)
    assert store.delete_all_events() == len(ALL_SAMPLE_EVENTS)
    assert store.list_events() == []


def test_operations_raise_when_table_missing(missing_table_store):
    with pytest.raises(DatabaseUnavailableError):
        missing_table_store.add_event(STUDY)
    with pytest.raises(DatabaseUnavailableError):
        missing_table_store.get_event(STUDY.event_id)
    with pytest.raises(DatabaseUnavailableError):
        missing_table_store.list_events()
