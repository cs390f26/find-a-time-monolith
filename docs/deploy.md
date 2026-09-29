# Deployment Guide

The application runs as a monolith service on a single AWS EC2 instance (Amazon Linux 2023) and connects directly to AWS DynamoDB.

## System Requirements
- Python 3.11+
- SystemD
- AWS IAM Role / Credentials with access to the DynamoDB table

## Setup on EC2
1. Clone the repository onto the instance.
2. Create and activate a virtual environment:
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e .
3. Copy the SystemD service unit file to /etc/systemd/system/findatime.service.
4. Reload systemd and start the service:
   sudo systemctl daemon-reload
   sudo systemctl enable --now findatime
5. Verify service status:
   sudo systemctl status findatime
