# Development Setup

How to run Find-a-Time on your own computer (macOS or Linux).

The app has three parts, all running locally:

```
browser  -->  Flask app (port 5001)  -->  DynamoDB Local (port 8000)
```

## Prerequisites

- **Python 3.10 or newer**: check with `python3 --version`
- **Java 17 or newer**: DynamoDB Local is a Java program. Check with `java -version`
  (on macOS: `brew install openjdk@21` if missing)
- **git**

## 1. Get the code and install it

```bash
git clone https://github.com/cs390f26/find-a-time-monolith.git
cd find-a-time-monolith

# Create a virtual environment (an isolated set of Python packages for this project)
python3 -m venv .venv
source .venv/bin/activate

# Install the libraries we use (Flask, boto3, gunicorn, pytest, moto)
pip install -r requirements.txt

# Install our own code as a package in "editable" mode (-e), so changes
# to files in src/ take effect without reinstalling
pip install -e .
```

Every new terminal needs `source .venv/bin/activate` before running the commands below.

## 2. Download DynamoDB Local (one time)

DynamoDB Local is a version of Amazon DynamoDB that runs on your computer. It is not
stored in this repo (it is ~65 MB), so download it into the project folder:

```bash
# -L follows redirects; tar -xz unpacks the .tar.gz archive here
curl -L https://d1ni2b6xgvw0s0.cloudfront.net/v2.x/dynamodb_local_latest.tar.gz | tar -xz
```

This creates `DynamoDBLocal.jar` and `DynamoDBLocal_lib/` (both are in `.gitignore`).

## 3. Start the database (terminal 1)

```bash
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb
```

- `-Djava.library.path=./DynamoDBLocal_lib`: where DynamoDB Local finds its native libraries
- `-sharedDb`: keep all data in one file, `shared-local-instance.db`, so it survives restarts

Leave this terminal open; it listens on port 8000. Stop it with **Ctrl+C**.

## 4. Create the table and load sample data (terminal 2)

```bash
source .venv/bin/activate

# boto3 requires credentials even though DynamoDB Local ignores them, so set placeholders
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local

python scripts/create_table.py     # creates the "Events" table (safe to run again)
python scripts/seed_data.py        # loads the 4 sample events from scripts/sample_data.json
```

**Resetting the data** (delete every event and reload the 4 samples):

```bash
python scripts/seed_data.py --reset
```

To start completely from scratch instead, stop DynamoDB Local, delete
`shared-local-instance.db`, start it again, and repeat step 4.

## 5. Run the app

```bash
python src/findatime/app.py
```

Open <http://localhost:5001>. Flask runs in debug mode, so it reloads when you save a file.
(Port 5001 is used because macOS's AirPlay Receiver often occupies port 5000.)

## 6. Run the tests

With DynamoDB Local running:

```bash
pytest
```

> **Warning:** the tests delete every event in the `Events` table before each test
> (see `tests/conftest.py`). Run `python scripts/seed_data.py` afterwards to get the
> sample events back.

## Configuration

The app reads these environment variables (defaults in `src/findatime/settings.py`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `DYNAMODB_ENDPOINT_URL` | `http://localhost:8000` | Where DynamoDB Local is running |
| `AWS_DEFAULT_REGION` | `us-east-1` | Required by boto3; any region works locally |
| `EVENTS_TABLE_NAME` | `Events` | Name of the DynamoDB table |

## Project layout

```
src/findatime/
  app.py          Flask layer: routes, HTML pages, JSON API
  app_logic.py    Business layer: validation and rules (FindATimeApp)
  db.py           Database layer: reads/writes DynamoDB (EventStorage)
  event_types.py  EventData and conversion to/from DynamoDB items
  settings.py     Environment configuration
  templates/      HTML pages
scripts/          create_table.py, seed_data.py, sample_data.json
tests/            pytest tests
deploy/           EC2 user data script and systemd service files
```
