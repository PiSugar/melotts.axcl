#!/bin/bash

# set startup service to run the server

echo "Setting up startup service..."

WORKDIR=$(pwd)
SERVICE_FILE="/etc/systemd/system/melotts.service"
echo "[Unit]
Description=Melotts Service
After=network.target
[Service]
Type=simple
WorkingDirectory=$WORKDIR
ExecStart=bash $WORKDIR/serve.sh
Restart=on-failure
LogLevel=info
StandardOutput=append:$WORKDIR/server.log
StandardError=append:$WORKDIR/server-err.log

[Install]
WantedBy=multi-user.target" | sudo tee $SERVICE_FILE


sudo systemctl daemon-reload
sudo systemctl enable melotts.service
sudo systemctl start melotts.service