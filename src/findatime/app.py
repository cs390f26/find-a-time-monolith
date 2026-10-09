
from flask import Flask, render_template


def create_app():
    app = Flask(__name__)

    # Temporary data for frontend development.
    # We will replace this with database calls later.
    sample_events = [
        {
            "id": "ev_101a9b2c",
            "title": "CS 320 Group Project Kickoff",
            "attendeeCount": 0,
        },
        {
            "id": "ev_202c4d5e",
            "title": "Weekend Midterm Study Group",
            "attendeeCount": 6,
        },
        {
            "id": "ev_303e6f7a",
            "title": "End of Semester Dinner",
            "attendeeCount": 8,
        },
    ]

    @app.get("/")
    def home():
        return render_template("events.html", events=sample_events)

    @app.get("/events")
    def list_events():
        return {
            "events": [
                {
                    "id": event["id"],
                    "title": event["title"],
                    "notes": event.get("notes", ""),
                    "attendeeCount": event.get("attendeeCount", 0)
                }
                for event in sample_events
            ]
        }, 200

    @app.get("/events/new")
    def new_event():
        return render_template("create_event.html")

    @app.post("/events")
    def create_event():
        from flask import request, jsonify
        from datetime import datetime
        from uuid import uuid4

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Please provide valid event data."
                }
            }), 400

        title = data.get("title")
        notes = data.get("notes", "")
        slots = data.get("timeSlots")

        if (not isinstance(title, str)
                or not title.strip()
                or len(title) > 140
                or not isinstance(notes, str)
                or len(notes) > 500
                or not isinstance(slots, list)
                or not 2 <= len(slots) <= 6):
            return jsonify({
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Enter a title and 2 to 6 valid time slots."
                }
            }), 400

        validated_slots = []
        seen = set()

        for slot in slots:
            if not isinstance(slot, dict):
                return jsonify({"error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid time slot."
                }}), 400

            try:
                start = datetime.fromisoformat(slot["startTime"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(slot["endTime"].replace("Z", "+00:00"))
            except (KeyError, AttributeError, TypeError, ValueError):
                return jsonify({"error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid date or time."
                }}), 400

            if (start.tzinfo is None or end.tzinfo is None
                    or end <= start or (start, end) in seen):
                return jsonify({"error": {
                    "code": "BAD_REQUEST",
                    "message": "Time slots must be unique and end after they start."
                }}), 400

            seen.add((start, end))
            validated_slots.append({
                "slotId": f"slot_{len(validated_slots) + 1}",
                "startTime": slot["startTime"],
                "endTime": slot["endTime"],
                "label": slot.get("label") or start.strftime("%b %d, %I:%M %p")
            })

        event_id = "ev_" + uuid4().hex[:8]

        validated_slots.append({
            "slotId": "slot_fallback",
            "startTime": None,
            "endTime": None,
            "label": "None of these work for me"
        })

        sample_events.insert(0, {
            "id": event_id,
            "title": title.strip(),
            "notes": notes,
            "attendeeCount": 0,
            "timeSlots": validated_slots
        })

        return jsonify({"id": event_id}), 201

    @app.get("/events/<event_id>")
    def view_event(event_id):
        event = next(
            (item for item in sample_events if item["id"] == event_id),
            None
        )

        if event is None:
            return "Event not found", 404

        return render_template("respond.html", event=event)

    @app.post("/events/<event_id>/responses")
    def submit_response(event_id):
        from flask import request, jsonify

        event = next(
            (item for item in sample_events if item["id"] == event_id),
            None
        )

        if event is None:
            return jsonify({"error": {
                "code": "EVENT_NOT_FOUND",
                "message": "Event not found"
            }}), 404

        
        if not event.get("timeSlots"):
            return jsonify({"error": {
                "code": "BAD_REQUEST",
                "message": "This event has no available time slots."
            }}), 400


        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({"error": {
                "code": "BAD_REQUEST",
                "message": "Invalid response data."
            }}), 400

        name = data.get("responderName")
        selected = data.get("selectedSlotIds")

        if (not isinstance(name, str)
                or not name.strip()
                or len(name) > 50
                or not isinstance(selected, list)
                or not selected
                or any(not isinstance(s, str) for s in selected)
                or len(selected) != len(set(selected))
                or ("slot_fallback" in selected and len(selected) > 1)):
            return jsonify({"error": {
                "code": "BAD_REQUEST",
                "message": "Enter a name and select valid time slots."
            }}), 400

        valid_ids = {
            slot["slotId"] for slot in event["timeSlots"]
        }

        if not set(selected).issubset(valid_ids):
            return jsonify({"error": {
                "code": "BAD_REQUEST",
                "message": "Unknown time slot selected."
            }}), 400

        for slot in event["timeSlots"]:
            slot.setdefault("attendees", [])
            slot.setdefault("tally", 0)

            if slot["slotId"] in selected:
                slot["attendees"].append(name.strip())
                slot["tally"] += 1

        event["attendeeCount"] += 1

        candidate_slots = [
            slot for slot in event["timeSlots"]
            if slot["slotId"] != "slot_fallback"
        ]

        highest = max(
            (slot["tally"] for slot in candidate_slots),
            default=0
        )

        winning_ids = [
            slot["slotId"] for slot in candidate_slots
            if highest > 0 and slot["tally"] == highest
        ]

        return jsonify({
            "id": event["id"],
            "title": event["title"],
            "notes": event.get("notes", ""),
            "attendeeCount": event["attendeeCount"],
            "winningSlotIds": winning_ids,
            "timeSlots": event["timeSlots"]
        }), 200

    @app.get("/events/<event_id>/results")
    def event_results(event_id):
        from flask import jsonify

        event = next(
            (item for item in sample_events if item["id"] == event_id),
            None
        )

        if event is None:
            return jsonify({
                "error": {
                    "code": "EVENT_NOT_FOUND",
                    "message": "Event not found"
                }
            }), 404

        slots = event.get("timeSlots", [])

        result_slots = []
        for slot in slots:
            result_slots.append({
                **slot,
                "tally": slot.get("tally", 0),
                "attendees": slot.get("attendees", [])
            })

        candidate_slots = [
            slot for slot in result_slots
            if slot["slotId"] != "slot_fallback"
        ]

        highest = max(
            (slot["tally"] for slot in candidate_slots),
            default=0
        )

        winning_ids = [
            slot["slotId"] for slot in candidate_slots
            if highest > 0 and slot["tally"] == highest
        ]

        return jsonify({
            "id": event["id"],
            "title": event["title"],
            "notes": event.get("notes", ""),
            "attendeeCount": event["attendeeCount"],
            "winningSlotIds": winning_ids,
            "timeSlots": result_slots
        }), 200

    @app.get("/events/<event_id>/results/view")
    def results_page(event_id):
        from flask import abort

        event = next(
            (item for item in sample_events if item["id"] == event_id),
            None
        )

        if event is None:
            abort(404)

        slots = [
            {
                **slot,
                "tally": slot.get("tally", 0),
                "attendees": slot.get("attendees", [])
            }
            for slot in event.get("timeSlots", [])
        ]

        candidate_slots = [
            slot for slot in slots
            if slot["slotId"] != "slot_fallback"
        ]

        highest = max(
            (slot["tally"] for slot in candidate_slots),
            default=0
        )

        winning_ids = [
            slot["slotId"] for slot in candidate_slots
            if highest > 0 and slot["tally"] == highest
        ]

        return render_template(
            "results.html",
            event=event,
            slots=slots,
            winning_ids=winning_ids
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
