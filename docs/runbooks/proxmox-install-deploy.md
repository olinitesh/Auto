# Proxmox Install and Deploy Guide

## Purpose
Install and deploy AutoHaggle on a Proxmox Ubuntu VM for local LAN usage.

## VM Requirements
- Proxmox VM with Ubuntu 24.04 LTS
- 4 vCPU, 8 GB RAM, 80 GB disk (recommended)
- Bridged network and a stable VM IP address
- User with `sudo` access

## System Packages (install first)
Run one line at a time:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git make build-essential python3 python3-venv python3-pip nodejs npm
```

Note:
- `make` is required before running `scripts/deploy/proxmox-deploy.sh`.
- `nodejs` + `npm` are required for `autohaggle-web` service (`make web-prod`).

## Repository Access (fix GitHub 403)
If you see `Write access to repository not granted` or `403`, use valid repo auth.

### Option A: SSH key (recommended)
```bash
ssh-keygen -t ed25519 -C "proxmox-autohaggle"
cat ~/.ssh/id_ed25519.pub
```
Add the public key to GitHub (account key or deploy key), then:
```bash
git remote set-url origin git@github.com:olinitesh/Auto.git
ssh -T git@github.com
```

### Option B: HTTPS with PAT
- Create a GitHub PAT with repo access.
- Authenticate `git clone`/`git pull` using that PAT.

## Clone Repository
```bash
sudo mkdir -p /opt
sudo chown -R "$USER":"$USER" /opt
cd /opt
git clone -b main git@github.com:olinitesh/Auto.git autohaggle
cd /opt/autohaggle
```

## Python Dependencies
Use either workflow:

### Preferred (repo standard)
```bash
make bootstrap
```

### Manual fallback
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Start Infrastructure
```bash
docker compose up -d postgres redis
docker compose ps
```

## Deploy Application (scripted)
```bash
chmod +x scripts/deploy/proxmox-deploy.sh
INSTALL_NGINX=1 ./scripts/deploy/proxmox-deploy.sh
```

First-time deploy with clone inside script:
```bash
REPO_URL=git@github.com:olinitesh/Auto.git REPO_BRANCH=main INSTALL_NGINX=1 ./scripts/deploy/proxmox-deploy.sh
```

## Configure Environment
```bash
cp -n .env.example .env
nano .env
```
Set at minimum:
- `OPENAI_API_KEY`
- `MARKETCHECK_API_KEY`
- `TWILIO_*` (if communication flows enabled)
- `SENDGRID_*` (if notifications enabled)

Restart after env updates:
```bash
sudo systemctl restart autohaggle-api
sudo systemctl restart autohaggle-worker
sudo systemctl restart autohaggle-communication
sudo systemctl restart autohaggle-warroom
sudo systemctl restart autohaggle-web
sudo systemctl restart nginx
```

## Verify Deployment
```bash
sudo systemctl status autohaggle-api autohaggle-web nginx --no-pager
curl -f http://127.0.0.1:8000/health
curl -I http://127.0.0.1:5173
curl -I http://127.0.0.1/
```
Open from LAN browser:
- `http://<vm-ip>/`

## Useful Operations
Tail logs:
```bash
sudo journalctl -u autohaggle-api -f
sudo journalctl -u autohaggle-web -f
sudo journalctl -u nginx -f
```

Redeploy latest code:
```bash
cd /opt/autohaggle
git pull --ff-only
INSTALL_NGINX=1 ./scripts/deploy/proxmox-deploy.sh
```

## Troubleshooting
### `make: command not found`
```bash
sudo apt-get update
sudo apt-get install -y make
```

### `npm: not found` in `autohaggle-web`
```bash
sudo apt-get update
sudo apt-get install -y nodejs npm
sudo systemctl restart autohaggle-web
```

### API DB errors (`psycopg OperationalError`)
```bash
cd /opt/autohaggle
docker compose up -d postgres redis
docker compose logs --tail=120 postgres
sudo systemctl restart autohaggle-api
```

### 502 from Nginx
```bash
sudo systemctl status autohaggle-api autohaggle-web --no-pager
sudo journalctl -u nginx -n 120 --no-pager
```

### Frontend `Failed to fetch`
- Ensure frontend uses proxied endpoints (`/api`, `/ws`) in latest code.
- Hard refresh browser after web restart (`Ctrl+Shift+R`).
