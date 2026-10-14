import sys
from typing import Optional

from flask import Flask, jsonify, render_template, request

from findatime.app_logic import (
    FindATimeApp,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from findatime.db import DatabaseUnavailableError, EventStorage
from findatime.event_types import EventQuestion, EventResults, EventSummary
from findatime.settings import ensure_settings

# This is the API layer: it only handles HTTP. It reads the request, calls the
# application layer (FindATimeApp), and turns the result into JSON.
#
# The HTML pages are static shells. Each page's JavaScript calls the JSON API
# below (fetch) and builds the page from the response.


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _unavailable():
    return jsonify({"status": "unavailable"}), 503


def _summary_json(summary: EventSummary) -> dict:
    return {
        "id": summary.id,
        "title": summary.title,
        "notes": summary.notes,
        "createdAt": summary.created_at,
        "attendeeCount": summary.attendee_count,
    }


def _question_json(event: EventQuestion) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "notes": event.notes,
        "createdAt": event.created_at,
        "attendeeCount": event.attendee_count,
        "timeSlots": event.time_slots,
    }


def _results_json(results: EventResults) -> dict:
    return {
        "id": results.id,
        "title": results.title,
        "notes": results.notes,
        "createdAt": results.created_at,
        "attendeeCount": results.attendee_count,
        "winningSlotIds": results.winning_slot_ids,
        "timeSlots": results.time_slots,
    }


def _storage_from_settings() -> EventStorage:
    settings = ensure_settings()
    return EventStorage(
        table_name=settings["EVENTS_TABLE_NAME"],
        region_name=settings["AWS_DEFAULT_REGION"],
        endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
    )


def create_app(app_logic: Optional[FindATimeApp] = None) -> Flask:
    """Build the Flask app and add routes.

    Tests may pass their own FindATimeApp; otherwise one is built from settings.
    """
    if app_logic is None:
        app_logic = FindATimeApp(_storage_from_settings())

    app = Flask(__name__)
    # Reject request bodies over 64 KB with 413 (a real event is a few hundred bytes).
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    # --- HTML pages (static; JavaScript loads the data from the API) ---

    @app.get("/")
    def index_page():
        return render_template("events.html")

    @app.get("/create")
    def create_page():
        return render_template("create_event.html")

    @app.get("/respond")
    def respond_page():
        return render_template("respond.html")

    @app.get("/results")
    def results_page():
        return render_template("results.html")

    # --- JSON API (see opneapi.yaml in the specs repo) ---

    @app.get("/health")
    def health():
        try:
            app_logic.health()
        except ServiceUnavailableError:
            return _unavailable()
        return jsonify({"status": "ok"}), 200

    @app.get("/events")
    def list_events():
        try:
            summaries = app_logic.list_events()
        except ServiceUnavailableError:
            return _unavailable()
        return jsonify({"events": [_summary_json(s) for s in summaries]}), 200

    @app.post("/events")
    def create_event():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("BAD_REQUEST", "Please provide valid event data.", 400)

        try:
            event_id = app_logic.create_event(
                data.get("title"), data.get("notes", ""), data.get("timeSlots")
            )
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except ServiceUnavailableError:
            return _unavailable()

        # 201 Created: success that made a new resource.
        return jsonify({"id": event_id}), 201

    @app.get("/events/<event_id>")
    def get_event(event_id):
        try:
            event = app_logic.get_event(event_id)
        except NotFoundError:
            return _error("EVENT_NOT_FOUND", "Event not found", 404)
        except ServiceUnavailableError:
            return _unavailable()
        return jsonify(_question_json(event)), 200

    @app.post("/events/<event_id>/responses")
    def submit_response(event_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("BAD_REQUEST", "Invalid response data.", 400)

        try:
            results = app_logic.submit_response(
                event_id, data.get("responderName"), data.get("selectedSlotIds")
            )
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except NotFoundError:
            return _error("EVENT_NOT_FOUND", "Event not found", 404)
        except ServiceUnavailableError:
            return _unavailable()
        return jsonify(_results_json(results)), 200

    @app.get("/events/<event_id>/results")
    def get_results(event_id):
        try:
            results = app_logic.get_results(event_id)
        except NotFoundError:
            return _error("EVENT_NOT_FOUND", "Event not found", 404)
        except ServiceUnavailableError:
            return _unavailable()
        return jsonify(_results_json(results)), 200

    return app


def launch() -> Flask:
    """Build storage + FindATimeApp + Flask app, checking the database first."""
    storage = _storage_from_settings()
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
    app.run(debug=True, port=5001)
