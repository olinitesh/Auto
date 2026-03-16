#!/usr/bin/env bash
set -euo pipefail

# ---------- EDIT THESE ----------
REPO_URL="https://github.com/olinitesh/Auto.git"
APP_DIR="/opt/Auto"
DOMAIN_OR_IP="192.168.1.60"   # your VM LAN IP or local DNS name
INSTALL_NGINX="1"             # 1=yes, 0=no
# -------------------------------

echo "[1/8] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
  git curl wget ca-certificates gnupg lsb-release \
  build-essential make jq unzip \
  python3 python3-pip python3-venv \
  docker.io

echo "[2/8] Enabling Docker..."
sudo systemctl enable --now docker

echo "[2.1/8] Ensuring Docker Compose v2 is available..."
if ! docker compose version >/dev/null 2>&1; then
  sudo apt-get install -y docker-compose-v2 || true
fi
if ! docker compose version >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi

echo "[3/8] Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "[4/8] Verifying toolchain..."
python3 --version
node -v
npm -v
docker --version
docker compose version

echo "[5/8] Cloning repo..."
if [ ! -d "$APP_DIR/.git" ]; then
  sudo mkdir -p "$(dirname "$APP_DIR")"
  sudo git clone "$REPO_URL" "$APP_DIR"
fi
sudo chown -R "$USER:$USER" "$APP_DIR"
cd "$APP_DIR"

echo "[6/8] Creating .env from template (if missing)..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Edit it now with your local values before production use."
fi

echo "[7/8] Running Proxmox deploy script..."
sudo INSTALL_NGINX="$INSTALL_NGINX" DOMAIN="$DOMAIN_OR_IP" bash scripts/deploy/proxmox-deploy.sh

echo "[8/8] Enabling/starting services..."
sudo systemctl daemon-reload
sudo systemctl enable --now \
  autohaggle-api \
  autohaggle-worker \
  autohaggle-communication \
  autohaggle-warroom \
  autohaggle-web

echo
echo "Deployment complete."
echo "If nginx enabled: http://$DOMAIN_OR_IP"
echo "Direct web:       http://$DOMAIN_OR_IP:5173"
echo "Direct API:       http://$DOMAIN_OR_IP:8000/health"
echo
echo "Service status:"
sudo systemctl --no-pager --full status autohaggle-web autohaggle-api | sed -n '1,80p'