#!/usr/bin/env bash
# deploy_cloud.sh — 1-Click Automated 24/7 AANVYA + Hermes Cloud Deployment

set -e

echo "========================================================="
echo "   Deploying AANVYA 24/7 Cloud Assistant with Hermes     "
echo "========================================================="

sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl

APP_DIR="/home/ubuntu/AANVYA-2.0"
VENV_DIR="/home/ubuntu/aanvya_env"

if [ ! -d "$APP_DIR" ]; then
    echo "[+] Cloning AANVYA 2.0 Repository..."
    git clone -b dev https://github.com/rishikhetan00-ops/AANVYA-2.0.git "$APP_DIR"
else
    echo "[+] Updating Repository..."
    cd "$APP_DIR" && git pull origin dev
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[+] Creating Python Virtual Environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "[+] Installing Dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install requests beautifulsoup4 httpx openpyxl

echo "[+] Configuring Systemd 24/7 Daemon Service..."
sudo bash -c "cat << 'EOF' > /etc/systemd/system/aanvya.service
[Unit]
Description=AANVYA 24/7 Cloud Assistant with Hermes Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/AANVYA-2.0
ExecStart=/home/ubuntu/aanvya_env/bin/python cloud_server/aanvya_cloud.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable aanvya.service
sudo systemctl restart aanvya.service

echo ""
echo "========================================================="
echo "   ✅ SUCCESS! AANVYA 24/7 is now LIVE and RUNNING!      "
echo "   Check status anytime with: sudo systemctl status aanvya"
echo "========================================================="
