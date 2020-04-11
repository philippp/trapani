#!/usr/bin/env bash
curl -sSO https://dl.google.com/cloudagents/add-monitoring-agent-repo.sh
sudo bash add-monitoring-agent-repo.sh
sudo rm add-monitoring-agent-repo.sh
sudo apt-get update
sudo apt-get install -y python3-pip stackdriver-agent iptables-persistent mysql-client nginx
sudo service stackdriver-agent start

sudo pip3 install --upgrade google-cloud-spanner google-cloud-pubsub twilio python-dateutil cryptography flask uwsgi mysql-connector-python pytz

echo "export GOOGLE_APPLICATION_CREDENTIALS=\"/home/philippp/keys/Trapani-9ff766720b9f.json\"" >> ~/.bashrc
# systemd requires a temp directory that's usually set by X, but missing on headless clients.
echo "export XDG_RUNTIME_DIR=/tmp" >> ~/.bashrc
source ~/.bashrc

wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O gcloud/cloud_sql_proxy
chmod +x gcloud/cloud_sql_proxy
