"""Tests for event_types.py: DynamoDB item <-> EventData, and the view types.

These need no database: they only test pure functions.
"""

from decimal import Decimal

from sample_events import DINNER, KICKOFF, STANDUP, STUDY

from findatime.event_types import (
    EventData,
    EventQuestion,
    EventSummary,
    event_data_from_item,
    extract_event_question,
    extract_event_results,
    extract_event_summary,
    item_from_event_data,
)


def test_item_round_trip_keeps_slot_order():
    item = item_from_event_data(STUDY)
    # Stored as a list, so the order is kept (fallback last).
    assert [s["slotId"] for s in item["timeSlots"]] == ["slot_1", "slot_2", "slot_3", "slot_fallback"]
    assert event_data_from_item(item) == STUDY


def test_event_data_from_item_converts_decimal_tally():
    # DynamoDB returns numbers as Decimal; we convert them to int.
    item = item_from_event_data(STANDUP)
    for slot in item["timeSlots"]:
        slot["tally"] = Decimal(slot["tally"])
    event = event_data_from_item(item)
    assert [s["tally"] for s in event.slots] == [2, 1, 0]
    assert all(isinstance(s["tally"], int) for s in event.slots)


def test_extract_summary_counts_each_person_once():
    # STUDY has 10 votes in total, but only 7 different people.
    assert extract_event_summary(STUDY) == EventSummary(
        id=STUDY.event_id,
        title=STUDY.title,
        notes=STUDY.notes,
        created_at=STUDY.created_at,
        attendee_count=7,
    )


def test_extract_summary_with_no_responses():
    assert extract_event_summary(KICKOFF).attendee_count == 0


def test_extract_question_hides_tallies_and_names():
    question = extract_event_question(STUDY)
    assert isinstance(question, EventQuestion)
    assert [s["slotId"] for s in question.time_slots] == ["slot_1", "slot_2", "slot_3", "slot_fallback"]
    for slot in question.time_slots:
        assert set(slot) == {"slotId", "startTime", "endTime", "label"}


def test_extract_results_clear_winner():
    results = extract_event_results(STUDY)
    assert results.winning_slot_ids == ["slot_2"]
    assert results.attendee_count == 7
    assert results.time_slots[1]["tally"] == 5
    assert "Alice Smith" in results.time_slots[1]["attendees"]


def test_extract_results_tie_highlights_all_tied_slots():
    assert extract_event_results(DINNER).winning_slot_ids == ["slot_1", "slot_3"]


def test_extract_results_no_votes_means_no_winner():
    assert extract_event_results(KICKOFF).winning_slot_ids == []


def test_fallback_never_wins_even_with_most_votes():
    event = EventData(
        event_id="ev_x", created_at="2026-10-01T00:00:00Z", title="T", notes="",
        slots=[
            {"slotId": "slot_1", "startTime": "a", "endTime": "b", "label": "One", "tally": 1, "attendees": ["A"]},
            {"slotId": "slot_2", "startTime": "c", "endTime": "d", "label": "Two", "tally": 0, "attendees": []},
            {"slotId": "slot_fallback", "startTime": None, "endTime": None,
             "label": "None of these work for me", "tally": 3, "attendees": ["B", "C", "D"]},
        ],
    )
    assert extract_event_results(event).winning_slot_ids == ["slot_1"]
