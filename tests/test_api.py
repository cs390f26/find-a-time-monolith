"""Tests for app.py: HTTP routes, status codes and JSON shapes (the API in opneapi.yaml)."""

import time

import pytest
from sample_events import DINNER, KICKOFF, STUDY, TWO_SLOTS

from findatime.app import create_app
from findatime.app_logic import FindATimeApp


def create(client, title="Test", slots=TWO_SLOTS, **extra):
    return client.post("/events", json={"title": title, "timeSlots": slots, **extra})


# --- pages (static shells that load data with JavaScript) ---

@pytest.mark.parametrize("path", ["/", "/create", "/respond", "/results"])
def test_pages_are_served(client, path):
    assert client.get(path).status_code == 200


def test_home_page_loads_events_with_javascript(client):
    home = client.get("/").data.decode()
    assert 'fetch("/events")' in home
    assert '"/respond?id="' in home
    assert '"/results?id="' in home


# --- health ---

def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_health_unavailable(missing_table_store):
    client = create_app(FindATimeApp(missing_table_store)).test_client()
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}


def test_database_unavailable_returns_503(missing_table_store):
    client = create_app(FindATimeApp(missing_table_store)).test_client()
    assert client.get("/events").status_code == 503
    assert create(client).status_code == 503


# --- GET /events ---

def test_list_events_empty(client):
    response = client.get("/events")
    assert response.status_code == 200
    assert response.get_json() == {"events": []}


def test_list_events_newest_first(client, store):
    store.add_event(STUDY)
    store.add_event(KICKOFF)
    response = client.get("/events")
    assert response.status_code == 200
    assert response.get_json() == {
        "events": [
            {"id": KICKOFF.event_id, "title": KICKOFF.title, "notes": KICKOFF.notes,
             "createdAt": KICKOFF.created_at, "attendeeCount": 0},
            {"id": STUDY.event_id, "title": STUDY.title, "notes": STUDY.notes,
             "createdAt": STUDY.created_at, "attendeeCount": 7},
        ]
    }


def test_list_events_newest_first_after_creating(client):
    ids = []
    for title in ["First", "Second", "Third"]:
        ids.append(create(client, title).get_json()["id"])
        time.sleep(0.01)  # createdAt has millisecond precision
    listed = [e["id"] for e in client.get("/events").get_json()["events"]]
    assert listed == list(reversed(ids))


# --- POST /events ---

def test_create_event(client):
    response = create(client, "CS390 Team Meeting", notes="Library Room 204")
    assert response.status_code == 201
    event_id = response.get_json()["id"]
    assert client.get(f"/events/{event_id}").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"title": "", "timeSlots": TWO_SLOTS},
        {"title": "One slot", "timeSlots": TWO_SLOTS[:1]},
        {"title": "No slots"},
        {"timeSlots": TWO_SLOTS},
    ],
)
def test_create_event_bad_request(client, body):
    response = client.post("/events", json=body)
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "BAD_REQUEST"
    assert error["message"]


def test_create_event_requires_json_body(client):
    response = client.post("/events", data="not json")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"


# --- GET /events/<id> ---

def test_get_event_hides_tallies_and_names(client, store):
    store.add_event(STUDY)
    response = client.get(f"/events/{STUDY.event_id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == STUDY.title
    assert body["attendeeCount"] == 7
    assert [s["slotId"] for s in body["timeSlots"]] == ["slot_1", "slot_2", "slot_3", "slot_fallback"]
    assert all("tally" not in s and "attendees" not in s for s in body["timeSlots"])


def test_get_event_not_found(client):
    response = client.get("/events/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": {"code": "EVENT_NOT_FOUND", "message": "Event not found"}}


# --- GET /events/<id>/results ---

def test_get_results(client, store):
    store.add_event(DINNER)
    response = client.get(f"/events/{DINNER.event_id}/results")
    assert response.status_code == 200
    body = response.get_json()
    assert body["attendeeCount"] == 8
    assert body["winningSlotIds"] == ["slot_1", "slot_3"]   # tie: both highlighted
    assert body["timeSlots"][0]["tally"] == 6
    assert "Grace Hopper" in body["timeSlots"][0]["attendees"]


def test_get_results_not_found(client):
    response = client.get("/events/does-not-exist/results")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "EVENT_NOT_FOUND"


# --- POST /events/<id>/responses ---

def test_submit_response_and_results(client):
    event_id = create(client).get_json()["id"]

    response = client.post(f"/events/{event_id}/responses",
                           json={"responderName": "Mohammad", "selectedSlotIds": ["slot_1", "slot_2"]})
    assert response.status_code == 200

    results = client.get(f"/events/{event_id}/results").get_json()
    assert results["attendeeCount"] == 1
    assert [s["tally"] for s in results["timeSlots"]] == [1, 1, 0]
    assert set(results["winningSlotIds"]) == {"slot_1", "slot_2"}
    assert "Mohammad" in results["timeSlots"][0]["attendees"]
    assert response.get_json() == results   # POST returns the updated results


def test_attendee_count_counts_each_person_once(client):
    event_id = create(client).get_json()["id"]
    client.post(f"/events/{event_id}/responses",
                json={"responderName": "Alice", "selectedSlotIds": ["slot_1", "slot_2"]})
    client.post(f"/events/{event_id}/responses",
                json={"responderName": "Bob", "selectedSlotIds": ["slot_1"]})

    listed = {e["id"]: e for e in client.get("/events").get_json()["events"]}
    assert listed[event_id]["attendeeCount"] == 2
    assert client.get(f"/events/{event_id}/results").get_json()["attendeeCount"] == 2


@pytest.mark.parametrize(
    "body",
    [
        {"responderName": "", "selectedSlotIds": ["slot_1"]},
        {"responderName": "Alice", "selectedSlotIds": []},
        {"responderName": "Alice", "selectedSlotIds": ["slot_1", "slot_fallback"]},
        {"responderName": "Alice", "selectedSlotIds": ["slot_9"]},
    ],
)
def test_submit_response_bad_request(client, body):
    event_id = create(client).get_json()["id"]
    response = client.post(f"/events/{event_id}/responses", json=body)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"


def test_submit_response_requires_json_body(client):
    event_id = create(client).get_json()["id"]
    response = client.post(f"/events/{event_id}/responses", data="not json")
    assert response.status_code == 400


def test_submit_response_unknown_event(client):
    response = client.post("/events/does-not-exist/responses",
                           json={"responderName": "Alice", "selectedSlotIds": ["slot_1"]})
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "EVENT_NOT_FOUND"
