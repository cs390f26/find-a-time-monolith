"""Tests for app_logic.py (FindATimeApp): the business rules, called directly (no HTTP)."""

import pytest
from sample_events import DINNER, KICKOFF, STANDUP, STUDY, TWO_SLOTS

from findatime.app_logic import (
    FindATimeApp,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from findatime.event_types import extract_event_question, extract_event_results, extract_event_summary


def slot(start, end):
    return {"startTime": start, "endTime": end}


# --- health ---

def test_health_ok(app_logic):
    app_logic.health()


def test_health_raises_when_database_unavailable(missing_table_store):
    with pytest.raises(ServiceUnavailableError):
        FindATimeApp(missing_table_store).health()


# --- create an event ---

def test_create_event_stores_event_with_fallback_slot(app_logic, store):
    event_id = app_logic.create_event("  Team Dinner  ", "  Downtown  ", TWO_SLOTS)

    assert event_id.startswith("ev_")
    stored = store.get_event(event_id)
    assert stored.title == "Team Dinner"        # whitespace trimmed
    assert stored.notes == "Downtown"
    assert [s["slotId"] for s in stored.slots] == ["slot_1", "slot_2", "slot_fallback"]
    assert stored.slots[-1]["label"] == "None of these work for me"
    assert all(s["tally"] == 0 and s["attendees"] == [] for s in stored.slots)


def test_create_event_notes_are_optional(app_logic, store):
    event_id = app_logic.create_event("No notes", None, TWO_SLOTS)
    assert store.get_event(event_id).notes == ""


def test_create_event_uses_given_label(app_logic, store):
    slots = [{**TWO_SLOTS[0], "label": "Thursday 10 AM"}, TWO_SLOTS[1]]
    event_id = app_logic.create_event("Labels", "", slots)
    assert store.get_event(event_id).slots[0]["label"] == "Thursday 10 AM"


@pytest.mark.parametrize(
    "title, time_slots",
    [
        ("", TWO_SLOTS),                                   # missing title
        ("   ", TWO_SLOTS),                                # blank title
        (None, TWO_SLOTS),                                 # no title at all
        ("x" * 141, TWO_SLOTS),                            # title over 140 characters
        ("T", TWO_SLOTS[:1]),                              # fewer than 2 slots
        ("T", [slot(f"2026-10-1{i}T10:00:00Z", f"2026-10-1{i}T11:00:00Z") for i in range(7)]),  # more than 6
        ("T", None),                                       # slots missing
        ("T", [TWO_SLOTS[0], slot("2026-10-16T17:00:00Z", "2026-10-16T16:00:00Z")]),  # end before start
        ("T", [TWO_SLOTS[0], slot("2026-10-16T16:00:00Z", "2026-10-16T16:00:00Z")]),  # end equals start
        ("T", [TWO_SLOTS[0], TWO_SLOTS[0]]),               # duplicate slots
        ("T", [TWO_SLOTS[0], slot("not a date", "2026-10-16T16:00:00Z")]),  # bad time format
    ],
)
def test_create_event_validation(app_logic, store, title, time_slots):
    with pytest.raises(ValidationError):
        app_logic.create_event(title, "", time_slots)
    assert store.list_events() == []  # nothing was stored


def test_create_event_allows_six_slots(app_logic):
    six = [slot(f"2026-10-1{i}T10:00:00Z", f"2026-10-1{i}T11:00:00Z") for i in range(6)]
    assert app_logic.create_event("Six", "", six)


def test_create_event_raises_when_database_unavailable(missing_table_store):
    with pytest.raises(ServiceUnavailableError):
        FindATimeApp(missing_table_store).create_event("T", "", TWO_SLOTS)


# --- browse events ---

def test_list_events_empty(app_logic):
    assert app_logic.list_events() == []


def test_list_events_newest_first(app_logic, store):
    for event in [STANDUP, DINNER, KICKOFF, STUDY]:   # stored in mixed order
        store.add_event(event)
    assert app_logic.list_events() == [
        extract_event_summary(KICKOFF),
        extract_event_summary(STUDY),
        extract_event_summary(DINNER),
        extract_event_summary(STANDUP),
    ]


def test_list_includes_created_event(app_logic):
    event_id = app_logic.create_event("New one", "", TWO_SLOTS)
    summaries = app_logic.list_events()
    assert [s.id for s in summaries] == [event_id]
    assert summaries[0].attendee_count == 0


# --- view an event / results ---

def test_get_event(app_logic, store):
    store.add_event(STUDY)
    assert app_logic.get_event(STUDY.event_id) == extract_event_question(STUDY)


def test_get_event_not_found(app_logic):
    with pytest.raises(NotFoundError):
        app_logic.get_event("does-not-exist")


def test_get_results(app_logic, store):
    store.add_event(DINNER)
    assert app_logic.get_results(DINNER.event_id) == extract_event_results(DINNER)


def test_get_results_not_found(app_logic):
    with pytest.raises(NotFoundError):
        app_logic.get_results("does-not-exist")


# --- submit availability ---

def test_submit_multiple_slots(app_logic, store):
    store.add_event(KICKOFF)
    results = app_logic.submit_response(KICKOFF.event_id, "  Alice  ", ["slot_1", "slot_3"])

    tallies = {s["slotId"]: s["tally"] for s in results.time_slots}
    assert tallies == {"slot_1": 1, "slot_2": 0, "slot_3": 1, "slot_fallback": 0}
    assert results.time_slots[0]["attendees"] == ["Alice"]   # name trimmed
    assert results.attendee_count == 1
    assert results.winning_slot_ids == ["slot_1", "slot_3"]
    # The change was saved.
    assert app_logic.get_results(KICKOFF.event_id) == results


def test_submit_single_slot_adds_to_existing_votes(app_logic, store):
    store.add_event(STUDY)
    results = app_logic.submit_response(STUDY.event_id, "Zoe", ["slot_1"])
    assert results.time_slots[0]["tally"] == 3
    assert results.attendee_count == 8


def test_submit_fallback_only(app_logic, store):
    store.add_event(KICKOFF)
    results = app_logic.submit_response(KICKOFF.event_id, "George", ["slot_fallback"])
    assert results.time_slots[-1]["attendees"] == ["George"]
    assert results.attendee_count == 1
    assert results.winning_slot_ids == []   # fallback never wins


@pytest.mark.parametrize(
    "name, selected",
    [
        ("", ["slot_1"]),                       # missing name
        ("   ", ["slot_1"]),                    # blank name
        (None, ["slot_1"]),                     # no name at all
        ("Alice", []),                          # nothing selected
        ("Alice", None),                        # selection missing
        ("Alice", "slot_1"),                    # not a list
        ("Alice", ["slot_1", "slot_fallback"]), # fallback combined with a slot
        ("Alice", ["slot_9"]),                  # slot not in this event
    ],
)
def test_submit_validation(app_logic, store, name, selected):
    store.add_event(KICKOFF)
    with pytest.raises(ValidationError):
        app_logic.submit_response(KICKOFF.event_id, name, selected)
    assert store.get_event(KICKOFF.event_id) == KICKOFF   # nothing changed


def test_submit_unknown_event(app_logic):
    with pytest.raises(NotFoundError):
        app_logic.submit_response("does-not-exist", "Alice", ["slot_1"])
