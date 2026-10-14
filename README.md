# Find-a-Time (Monolith)

A scheduling poll app for finding a meeting time that works for a group.

One person creates an event with 2–6 candidate time slots ("None of these work for me" is
added automatically). Others enter their name and check every slot that works for them.
The results page shows how many people picked each slot, who they are, and highlights the
best time.

## Screens

1. **Events list** (`/`): all events, newest first, with response counts
2. **Create event** (`/events/new`)
3. **Respond** (`/events/<id>`): enter your name and pick time slots
4. **Results** (`/events/<id>/results/view`): tallies, names, and the best time

## Architecture

```
browser → Flask (app.py) → business logic (app_logic.py) → storage (db.py) → DynamoDB Local
```

- **Flask layer** (`app.py`): HTML pages and the JSON API
- **Business layer** (`app_logic.py`): validation and rules
- **Database layer** (`db.py`, `event_types.py`): reads and writes DynamoDB

In production, gunicorn and DynamoDB Local run on a single EC2 instance under systemd.

## Tech stack

Python 3.11 · Flask · boto3 · DynamoDB Local · gunicorn · systemd · pytest · GitHub Actions

## Docs

- [Development setup](docs/development.md): run it on your own computer
- [Deployment](docs/deploy.md): launch it on EC2 with `deploy/userdata.sh`
- [Team process](docs/process.md)

## Repos

- `find-a-time-specs`: use cases, mockups, API spec, schema, sample data
- `find-a-time-monolith` (this repo): the implementation
