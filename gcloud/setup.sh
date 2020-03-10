#!/usr/bin/env bash
sudo apt-get update
sudo apt-get install python3-pip
pip3 install --upgrade google-cloud-spanner google-cloud-pubsub twilio python-dateutil
curl -sSO https://dl.google.com/cloudagents/add-monitoring-agent-repo.sh
sudo bash add-monitoring-agent-repo.sh
sudo apt-get update
sudo apt-get install stackdriver-agent
sudo service stackdriver-agent start
echo "export GOOGLE_APPLICATION_CREDENTIALS=\"/home/philippp/keys/Trapani-9ff766720b9f.json\"" >> ~/.bashrc
# systemd requires a temp directory that's usually set by X, but missing on headless clients.
echo "export XDG_RUNTIME_DIR=/tmp" >> ~/.bashrc
source ~/.bashrc
