# Deployment Guide

Find-a-Time is deployed as a **monolith on a single EC2 instance**: the web server
(gunicorn running Flask) and the database (DynamoDB Local) both run on the same machine.

```
browser --HTTP:80--> gunicorn + Flask app --localhost:8000--> DynamoDB Local
                     (findatime.service)                     (dynamodb-local.service)
                     |__________________ one EC2 instance __________________|
```

The whole setup is automated by [`deploy/userdata.sh`](../deploy/userdata.sh), which EC2
runs once when the instance first boots. No SSH is needed to deploy.

## Launch the instance (AWS web console)

1. Open **EC2 → Instances → Launch instances**.
2. **Name:** `find-a-time` (any name works).
3. **Application and OS Images (AMI):** **Amazon Linux 2023** (64-bit x86).
   The script uses `dnf` and Amazon's Java package, so other AMIs will not work.
4. **Instance type:** `t2.micro` or `t3.micro` (free tier). Use `t3.small` if it feels slow;
   DynamoDB Local runs on Java and likes memory.
5. **Key pair:** choose an existing key pair or create one. Only needed if you want to SSH in.
6. **Network settings → Firewall (security group):** create a security group with:
   - **Allow HTTP traffic from the internet** (port 80): so browsers can reach the app
   - **Allow SSH traffic** (port 22): optional, for troubleshooting

   Do **not** open port 8000. The database should only be reachable from inside the instance.
7. **Advanced details → User data:** paste the entire contents of `deploy/userdata.sh`.
8. Click **Launch instance**.

No IAM role, DynamoDB table, or AWS keys need to be created in the console: the database
is DynamoDB Local running on the instance itself.

## Open the app

Setup takes about **3–5 minutes** after the instance shows "Running". Then open:

```
http://<Public IPv4 address>
```

Use `http://` (not https). You should see the four sample events.

**Optional, Elastic IP / domain:** under **EC2 → Elastic IPs**, select an Elastic IP,
then **Actions → Associate Elastic IP address**, and pick the instance. The app is then
reachable at that fixed IP, or at a domain whose DNS A record points to it.

## What `userdata.sh` does

The script runs as root on first boot. Each step is commented in the file.

1. **Installs system packages:** Python 3.11, git, and Java 21 (needed by DynamoDB Local).
2. **Installs the app:** clones this repository into `/home/ec2-user/find-a-time-monolith`,
   creates a virtual environment, and installs `requirements.txt` and the package (`pip install -e .`).
3. **Installs the database:** downloads DynamoDB Local into `/opt/dynamodb-local`.
   Data is stored in `/var/lib/dynamodb-local`.
4. **Starts the database:** copies the systemd unit files from `deploy/` into
   `/etc/systemd/system/` and starts `dynamodb-local`, then waits until it answers on port 8000.
5. **Creates the table and loads sample data:** runs `scripts/create_table.py` and
   `scripts/seed_data.py`.
6. **Starts the web server:** starts `findatime` (gunicorn on port 80).

Both services are **enabled**, so systemd starts them again automatically after a reboot,
and restarts them if they crash.

### The systemd services

| Service | File | Runs |
| --- | --- | --- |
| `dynamodb-local` | `deploy/dynamodb-local.service` | `java -jar DynamoDBLocal.jar -sharedDb -dbPath /var/lib/dynamodb-local -port 8000` |
| `findatime` | `deploy/findatime.service` | `gunicorn -w 2 -b 0.0.0.0:80 "findatime.app:create_app()"` |

- `-w 2`: two gunicorn worker processes handle requests in parallel.
- `"findatime.app:create_app()"`: gunicorn imports `src/findatime/app.py` and calls `create_app()`.
- `AmbientCapabilities=CAP_NET_BIND_SERVICE` lets `ec2-user` use port 80 without running as root.
- `findatime` sets `DYNAMODB_ENDPOINT_URL=http://localhost:8000` and placeholder AWS credentials
  (`local`/`local`): DynamoDB Local ignores them, but boto3 requires some to be set.

## Troubleshooting (SSH)

```bash
ssh -i <your-key>.pem ec2-user@<Public IPv4 address>

# Did userdata.sh finish? The last line should be "Find-a-Time is running on port 80."
sudo tail -50 /var/log/cloud-init-output.log

# Are both services running?
sudo systemctl status dynamodb-local findatime

# Recent log output from the web app
sudo journalctl -u findatime -n 50
```

If SSH warns **"REMOTE HOST IDENTIFICATION HAS CHANGED"** after moving an Elastic IP to a new
instance, remove the old fingerprint with `ssh-keygen -R <ip>` and connect again.

## Updating a running instance

After pushing new code to GitHub:

```bash
cd ~/find-a-time-monolith
git pull
sudo systemctl restart findatime
```

To reset the data to the four sample events:

```bash
cd ~/find-a-time-monolith
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local .venv/bin/python scripts/seed_data.py --reset
```

(Alternatively, terminate the instance and launch a new one: `userdata.sh` rebuilds everything.)
