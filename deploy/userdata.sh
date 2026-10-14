#!/bin/bash
# EC2 user data script for Find-a-Time (Amazon Linux 2023).
#
# Paste this whole file into "Advanced details -> User data" when launching the instance.
# It runs once, as root, on first boot, and sets up the complete monolith:
#   1. installs Python 3.11, Java (for DynamoDB Local) and git
#   2. downloads our code from GitHub and installs it in a virtual environment
#   3. downloads DynamoDB Local and runs it as a systemd service (the database)
#   4. creates the Events table and loads the sample events
#   5. runs the Flask app with gunicorn as a systemd service on port 80
#
# Progress/errors are logged to /var/log/cloud-init-output.log on the instance.

# -e: stop on the first error   -u: error on unset variables
# -x: print each command (shows up in the log)   -o pipefail: a failing pipe counts as an error
set -euxo pipefail

REPO_URL="https://github.com/cs390f26/find-a-time-monolith.git"
APP_DIR="/home/ec2-user/find-a-time-monolith"
DDB_DIR="/opt/dynamodb-local"
DDB_DATA_DIR="/var/lib/dynamodb-local"
DDB_URL="https://d1ni2b6xgvw0s0.cloudfront.net/v2.x/dynamodb_local_latest.tar.gz"

# --- 1. System packages ------------------------------------------------------
dnf install -y python3.11 git java-21-amazon-corretto-headless tar

# --- 2. Application code and Python environment ------------------------------
# Run as ec2-user so the files belong to the user the services run as.
sudo -u ec2-user git clone "$REPO_URL" "$APP_DIR"
sudo -u ec2-user python3.11 -m venv "$APP_DIR/.venv"
sudo -u ec2-user "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u ec2-user "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo -u ec2-user "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

# --- 3. Database: DynamoDB Local ---------------------------------------------
mkdir -p "$DDB_DIR" "$DDB_DATA_DIR"
curl -fsSL "$DDB_URL" | tar -xz -C "$DDB_DIR"
chown -R ec2-user:ec2-user "$DDB_DIR" "$DDB_DATA_DIR"

cp "$APP_DIR/deploy/dynamodb-local.service" /etc/systemd/system/
cp "$APP_DIR/deploy/findatime.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dynamodb-local

# Wait (up to 60s) until DynamoDB Local answers on port 8000.
for i in $(seq 1 60); do
  if curl -s -o /dev/null http://localhost:8000; then break; fi
  sleep 1
done

# --- 4. Create the table and load sample data ---------------------------------
# Same settings the web service uses (see deploy/findatime.service).
export DYNAMODB_ENDPOINT_URL="http://localhost:8000" AWS_DEFAULT_REGION="us-east-1" \
       EVENTS_TABLE_NAME="Events" AWS_ACCESS_KEY_ID="local" AWS_SECRET_ACCESS_KEY="local"
cd "$APP_DIR"
sudo -E -u ec2-user "$APP_DIR/.venv/bin/python" scripts/create_table.py
sudo -E -u ec2-user "$APP_DIR/.venv/bin/python" scripts/seed_data.py

# --- 5. Web server ------------------------------------------------------------
systemctl enable --now findatime

echo "Find-a-Time is running on port 80."
