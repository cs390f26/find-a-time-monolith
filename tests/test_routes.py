
from src.findatime.app import create_app


def test_homepage():
    app = create_app()
    app.config["TESTING"] = True

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"Find a Time" in response.data


def test_create_event_page():
    app = create_app()
    app.config["TESTING"] = True

    client = app.test_client()
    response = client.get("/events/new")

    assert response.status_code == 200
    assert b"Create an event" in response.data

    
def test_create_valid_event():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    event_data = {
        "title": "CS390 Team Meeting",
        "notes": "Library Room 204",
        "timeSlots": [
            {
                "startTime": "2026-10-15T14:00:00Z",
                "endTime": "2026-10-15T15:00:00Z"
            },
            {
                "startTime": "2026-10-16T16:00:00Z",
                "endTime": "2026-10-16T17:00:00Z"
            }
        ]
    }

    response = client.post("/events", json=event_data)

    assert response.status_code == 201
    assert "id" in response.get_json()


def test_create_event_without_title():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    event_data = {
        "title": "",
        "timeSlots": [
            {
                "startTime": "2026-10-15T14:00:00Z",
                "endTime": "2026-10-15T15:00:00Z"
            },
            {
                "startTime": "2026-10-16T16:00:00Z",
                "endTime": "2026-10-16T17:00:00Z"
            }
        ]
    }

    response = client.post("/events", json=event_data)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"

    
def test_submit_vote_and_results():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    # Create a test event
    event_data = {
        "title": "CS390 Voting Test",
        "timeSlots": [
            {
                "startTime": "2026-10-15T14:00:00Z",
                "endTime": "2026-10-15T15:00:00Z"
            },
            {
                "startTime": "2026-10-16T16:00:00Z",
                "endTime": "2026-10-16T17:00:00Z"
            }
        ]
    }

    create_response = client.post("/events", json=event_data)
    assert create_response.status_code == 201

    event_id = create_response.get_json()["id"]

    # Submit one participant's availability
    vote_response = client.post(
        f"/events/{event_id}/responses",
        json={
            "responderName": "Mohammad",
            "selectedSlotIds": ["slot_1", "slot_2"]
        }
    )

    assert vote_response.status_code == 200

    # Retrieve the results
    results_response = client.get(
        f"/events/{event_id}/results"
    )

    assert results_response.status_code == 200

    results = results_response.get_json()

    assert results["attendeeCount"] == 1
    assert results["timeSlots"][0]["tally"] == 1
    assert results["timeSlots"][1]["tally"] == 1
    assert results["timeSlots"][2]["tally"] == 0
    assert set(results["winningSlotIds"]) == {"slot_1", "slot_2"}

    assert "Mohammad" in results["timeSlots"][0]["attendees"]
    assert "Mohammad" in results["timeSlots"][1]["attendees"]

    
def test_vote_without_name():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    event_data = {
        "title": "Voting Validation Test",
        "timeSlots": [
            {
                "startTime": "2026-10-15T14:00:00Z",
                "endTime": "2026-10-15T15:00:00Z"
            },
            {
                "startTime": "2026-10-16T16:00:00Z",
                "endTime": "2026-10-16T17:00:00Z"
            }
        ]
    }

    response = client.post("/events", json=event_data)
    event_id = response.get_json()["id"]

    vote_response = client.post(
        f"/events/{event_id}/responses",
        json={
            "responderName": "",
            "selectedSlotIds": ["slot_1"]
        }
    )

    assert vote_response.status_code == 400
    assert vote_response.get_json()["error"]["code"] == "BAD_REQUEST"


def test_fallback_cannot_combine_with_other_slots():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    event_data = {
        "title": "Fallback Validation Test",
        "timeSlots": [
            {
                "startTime": "2026-10-15T14:00:00Z",
                "endTime": "2026-10-15T15:00:00Z"
            },
            {
                "startTime": "2026-10-16T16:00:00Z",
                "endTime": "2026-10-16T17:00:00Z"
            }
        ]
    }

    response = client.post("/events", json=event_data)
    event_id = response.get_json()["id"]

    vote_response = client.post(
        f"/events/{event_id}/responses",
        json={
            "responderName": "Mohammad",
            "selectedSlotIds": ["slot_1", "slot_fallback"]
        }
    )

    assert vote_response.status_code == 400
    assert vote_response.get_json()["error"]["code"] == "BAD_REQUEST"

    
def test_unknown_event():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/events/does-not-exist")
    assert response.status_code == 404

    results_response = client.get(
        "/events/does-not-exist/results"
    )
    assert results_response.status_code == 404

    vote_response = client.post(
        "/events/does-not-exist/responses",
        json={
            "responderName": "Mohammad",
            "selectedSlotIds": ["slot_1"]
        }
    )
    assert vote_response.status_code == 404
