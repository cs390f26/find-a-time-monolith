import sys
from typing import Optional
from flask import Flask, jsonify, render_template, request, abort

from findatime.db import DatabaseUnavailableError, EventStorage
from findatime.app_logic import (
    FindATimeApp,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from findatime.settings import ensure_settings


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status

def _unique_attendee_count(slots) -> int:
    return len({name for s in slots for name in s.get("attendees", [])})

def create_app(app_logic: Optional[FindATimeApp] = None) -> Flask:
    """Build the Flask app and bind routes to the FindATimeApp logic layer."""
    if app_logic is None:
        settings = ensure_settings()
        storage = EventStorage(
            table_name=settings.get("EVENTS_TABLE_NAME", "Events"),
            region_name=settings["AWS_DEFAULT_REGION"],
            endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
        )
        app_logic = FindATimeApp(storage)

    app = Flask(__name__)

    @app.get("/")
    def home():
        try:
            events = app_logic.list_events()
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503
        
        # Map event dataclasses back to dict format for the template
        event_list = [
            {
                "id": ev.event_id,
                "title": ev.title,
                "notes": ev.notes,
                "attendeeCount": _unique_attendee_count(ev.slots)
            }
            for ev in events
        ]
        return render_template("events.html", events=event_list)

    @app.get("/events")
    def list_events():
        try:
            events = app_logic.list_events()
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503
        
        return {
            "events": [
                {
                    "id": ev.event_id,
                    "title": ev.title,
                    "notes": ev.notes,
                    "createdAt": ev.created_at,
                    "attendeeCount": _unique_attendee_count(ev.slots)
                }
                for ev in events
            ]
        }, 200

    @app.get("/events/new")
    def new_event():
        return render_template("create_event.html")

    @app.post("/events")
    def create_event():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("BAD_REQUEST", "Please provide valid event data.", 400)

        title = data.get("title")
        notes = data.get("notes", "")
        time_slots = data.get("timeSlots")

        try:
            event_id = app_logic.create_event(title, notes, time_slots)
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({"id": event_id}), 201

    @app.get("/events/<event_id>")
    def view_event(event_id):
        try:
            ev = app_logic.get_event(event_id)
        except NotFoundError:
            return "Event not found", 404
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        event_dict = {
            "id": ev.event_id,
            "title": ev.title,
            "notes": ev.notes,
            "timeSlots": ev.slots
        }
        return render_template("respond.html", event=event_dict)

    @app.post("/events/<event_id>/responses")
    def submit_response(event_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("BAD_REQUEST", "Invalid response data.", 400)

        responder_name = data.get("responderName")
        selected_slot_ids = data.get("selectedSlotIds")

        try:
            updated_event = app_logic.submit_response(event_id, responder_name, selected_slot_ids)
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except NotFoundError:
            return _error("EVENT_NOT_FOUND", "Event not found", 404)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        candidate_slots = [s for s in updated_event.slots if s["slotId"] != "slot_fallback"]
        highest = max((s["tally"] for s in candidate_slots), default=0)
        winning_ids = [s["slotId"] for s in candidate_slots if highest > 0 and s["tally"] == highest]

        total_attendees = _unique_attendee_count(updated_event.slots)

        return jsonify({
            "id": updated_event.event_id,
            "title": updated_event.title,
            "notes": updated_event.notes,
            "attendeeCount": total_attendees,
            "winningSlotIds": winning_ids,
            "timeSlots": updated_event.slots
        }), 200

    @app.get("/events/<event_id>/results")
    def event_results(event_id):
        try:
            ev = app_logic.get_event(event_id)
        except NotFoundError:
            return _error("EVENT_NOT_FOUND", "Event not found", 404)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        candidate_slots = [s for s in ev.slots if s["slotId"] != "slot_fallback"]
        highest = max((s["tally"] for s in candidate_slots), default=0)
        winning_ids = [s["slotId"] for s in candidate_slots if highest > 0 and s["tally"] == highest]
        total_attendees = _unique_attendee_count(ev.slots)
        return jsonify({
            "id": ev.event_id,
            "title": ev.title,
            "notes": ev.notes,
            "attendeeCount": total_attendees,
            "winningSlotIds": winning_ids,
            "timeSlots": ev.slots
        }), 200

    @app.get("/events/<event_id>/results/view")
    def results_page(event_id):
        try:
            ev = app_logic.get_event(event_id)
        except NotFoundError:
            abort(404)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        candidate_slots = [s for s in ev.slots if s["slotId"] != "slot_fallback"]
        highest = max((s["tally"] for s in candidate_slots), default=0)
        winning_ids = [s["slotId"] for s in candidate_slots if highest > 0 and s["tally"] == highest]
        total_attendees = _unique_attendee_count(ev.slots)

        event_dict = {
            "id": ev.event_id,
            "title": ev.title,
            "notes": ev.notes,
            "attendeeCount": total_attendees
        }

        return render_template(
            "results.html",
            event=event_dict,
            slots=ev.slots,
            winning_ids=winning_ids
        )

    @app.get("/health")
    def health():
        try:
            app_logic.health()
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"status": "ok"}), 200

    return app


def launch() -> Flask:
    """Initialize storage, application logic, and Flask app from environment settings."""
    settings = ensure_settings()
    storage = EventStorage(
        table_name=settings.get("EVENTS_TABLE_NAME", "Events"),
        region_name=settings["AWS_DEFAULT_REGION"],
        endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
    )
    try:
        storage.ping()
    except DatabaseUnavailableError as exc:
        raise RuntimeError(
            "Database not reachable. Is DynamoDB Local running? "
            "Is the Events table created (python scripts/create_table.py)? "
            f"Details: {exc}"
        ) from exc

    return create_app(FindATimeApp(storage))


if __name__ == "__main__":
    try:
        app = launch()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    app.run(debug=True, port=5000)