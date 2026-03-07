# Proxmox Install and Deploy Guide

## Purpose
Install and deploy AutoHaggle on a Proxmox Ubuntu VM for local LAN usage.

## VM Requirements
- Proxmox VM with Ubuntu 24.04 LTS
- 4 vCPU, 8 GB RAM, 80 GB disk (recommended)
- Bridged network and a stable VM IP address
- User with `sudo` access

## Prerequisites in VM
```bash
sudo apt-get update
sudo apt-get install -y git curl
```

## Repository Access (Fix 403 Errors)
If you see:
`remote: Write access to repository not granted` or `fatal: ... 403`
then your VM auth is not authorized for that GitHub repo.

Use one of these methods:

1. SSH key (recommended)
```bash
ssh-keygen -t ed25519 -C "proxmox-autohaggle"
cat ~/.ssh/id_ed25519.pub
```
Add the public key to GitHub (user key or deploy key), then:
```bash
git remote set-url origin git@github.com:olinitesh/Auto.git
ssh -T git@github.com
```

2. HTTPS + PAT
- Create a GitHub Personal Access Token with repo access.
- Use a credential helper and authenticate when prompted.

## Clone Repository
```bash
sudo mkdir -p /opt
authorized_user="$USER"
sudo chown -R "$authorized_user":"$authorized_user" /opt
cd /opt
git clone -b main git@github.com:olinitesh/Auto.git autohaggle
cd /opt/autohaggle
```

## Deploy
```bash
chmod +x scripts/deploy/proxmox-deploy.sh
INSTALL_NGINX=1 ./scripts/deploy/proxmox-deploy.sh
```

First-time clone using script directly:
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

Restart services after updates:
```bash
sudo systemctl restart autohaggle-api autohaggle-worker autohaggle-communication autohaggle-warroom autohaggle-web
```

## Verify Deployment
```bash
sudo systemctl status autohaggle-api autohaggle-web --no-pager
curl -f http://127.0.0.1:8000/health
```
Open from LAN browser:
- `http://<vm-ip>/`

## Useful Operations
View logs:
```bash
sudo journalctl -u autohaggle-api -f
sudo journalctl -u autohaggle-web -f
```

Redeploy latest code:
```bash
cd /opt/autohaggle
git pull --ff-only
INSTALL_NGINX=1 ./scripts/deploy/proxmox-deploy.sh
```

## Troubleshooting
- Port 80 unreachable: verify VM firewall and Proxmox network bridge.
- 403 on git pull/clone: fix GitHub auth (SSH key or PAT).
- Service boot loop: inspect `journalctl` for the failing unit.
