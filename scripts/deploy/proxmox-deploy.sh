#!/usr/bin/env bash
set -euo pipefail

# Proxmox VM deploy helper for AutoHaggle AI.
# Intended for Ubuntu 22.04/24.04 guests with sudo privileges.

APP_NAME="${APP_NAME:-autohaggle}"
APP_USER="${APP_USER:-$USER}"
APP_DIR="${APP_DIR:-/opt/autohaggle}"
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
ENV_FILE="${ENV_FILE:-.env}"
INSTALL_NGINX="${INSTALL_NGINX:-0}"
ENABLE_SERVICES="${ENABLE_SERVICES:-1}"

SERVICE_NAMES=("api" "worker" "communication" "warroom" "web")

log() {
  printf '[deploy] %s\n' "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

sudo_run() {
  if [[ "$EUID" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

install_os_packages() {
  log "Installing OS dependencies"
  sudo_run apt-get update
  sudo_run apt-get install -y \
    ca-certificates \
    curl \
    git \
    make \
    build-essential \
    python3 \
    python3-venv \
    python3-pip
}

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker already installed"
  else
    log "Installing Docker"
    curl -fsSL https://get.docker.com | sudo_run sh
  fi

  if ! groups "$APP_USER" | grep -q '\bdocker\b'; then
    log "Adding $APP_USER to docker group"
    sudo_run usermod -aG docker "$APP_USER"
    log "Re-login is required for docker group membership to apply"
  fi
}

sync_repo() {
  if [[ -d "$APP_DIR/.git" ]]; then
    log "Repository already exists at $APP_DIR; pulling latest branch $REPO_BRANCH"
    sudo_run git -C "$APP_DIR" fetch --all --prune
    sudo_run git -C "$APP_DIR" checkout "$REPO_BRANCH"
    sudo_run git -C "$APP_DIR" pull --ff-only origin "$REPO_BRANCH"
  else
    if [[ -z "$REPO_URL" ]]; then
      log "REPO_URL is required when $APP_DIR does not exist"
      exit 1
    fi
    log "Cloning repository to $APP_DIR"
    sudo_run mkdir -p "$(dirname "$APP_DIR")"
    sudo_run git clone --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
  fi

  sudo_run chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
}

prepare_env_file() {
  if [[ ! -f "$APP_DIR/$ENV_FILE" ]]; then
    if [[ -f "$APP_DIR/.env.example" ]]; then
      log "Creating $ENV_FILE from .env.example"
      cp "$APP_DIR/.env.example" "$APP_DIR/$ENV_FILE"
    else
      log "No .env.example found. Create $APP_DIR/$ENV_FILE manually."
      exit 1
    fi
  fi
}

run_app_setup() {
  log "Running bootstrap, dependency containers, and migrations"
  (
    cd "$APP_DIR"
    make bootstrap
    make up
    make migrate
  )
}

service_target_for() {
  local name="$1"
  case "$name" in
    api) echo "api" ;;
    worker) echo "worker" ;;
    communication) echo "communication" ;;
    warroom) echo "warroom" ;;
    web) echo "web-prod" ;;
    *) log "Unknown service name: $name"; exit 1 ;;
  esac
}

write_service_unit() {
  local name="$1"
  local target
  target="$(service_target_for "$name")"
  local unit_file="/etc/systemd/system/${APP_NAME}-${name}.service"
  log "Writing systemd unit: $unit_file"

  sudo_run tee "$unit_file" >/dev/null <<EOF
[Unit]
Description=${APP_NAME} ${name}
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/make ${target}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
}

setup_systemd_services() {
  for name in "${SERVICE_NAMES[@]}"; do
    write_service_unit "$name"
  done

  log "Reloading systemd"
  sudo_run systemctl daemon-reload

  if [[ "$ENABLE_SERVICES" == "1" ]]; then
    log "Enabling and starting services"
    for name in "${SERVICE_NAMES[@]}"; do
      sudo_run systemctl enable --now "${APP_NAME}-${name}.service"
    done
  else
    log "Service enable/start skipped (ENABLE_SERVICES=$ENABLE_SERVICES)"
  fi
}

setup_nginx_config() {
  local nginx_file="/etc/nginx/sites-available/${APP_NAME}.conf"
  log "Writing Nginx config: $nginx_file"

  sudo_run tee "$nginx_file" >/dev/null <<'EOF'
server {
  listen 80;
  server_name _;

  location / {
    proxy_pass http://127.0.0.1:5173;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location /comm/ {
    proxy_pass http://127.0.0.1:8010/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location /ws/ {
    proxy_pass http://127.0.0.1:8020/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
EOF

  sudo_run ln -sf "$nginx_file" "/etc/nginx/sites-enabled/${APP_NAME}.conf"
  sudo_run rm -f /etc/nginx/sites-enabled/default
  sudo_run nginx -t
  sudo_run systemctl restart nginx
}

print_summary() {
  cat <<EOF

Deployment complete.

App directory: ${APP_DIR}
Environment file: ${APP_DIR}/${ENV_FILE}

Service status commands:
  sudo systemctl status ${APP_NAME}-api
  sudo systemctl status ${APP_NAME}-worker
  sudo systemctl status ${APP_NAME}-communication
  sudo systemctl status ${APP_NAME}-warroom
  sudo systemctl status ${APP_NAME}-web

Logs:
  sudo journalctl -u ${APP_NAME}-api -f

Important:
  Update ${APP_DIR}/${ENV_FILE} with real keys (OpenAI, MarketCheck, Twilio, SendGrid).
EOF
}

main() {
  require_cmd bash
  require_cmd make
  require_cmd systemctl

  install_os_packages
  install_docker_if_needed
  sync_repo
  prepare_env_file
  run_app_setup
  setup_systemd_services

  if [[ "$INSTALL_NGINX" == "1" ]]; then
    sudo_run apt-get install -y nginx
    setup_nginx_config
  fi

  print_summary
}

main "$@"

