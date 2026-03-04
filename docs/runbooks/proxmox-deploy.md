# Proxmox Deployment Runbook

## Scope
Deploy AutoHaggle on an Ubuntu VM hosted in Proxmox using the deployment script:
`scripts/deploy/proxmox-deploy.sh`.

## Recommended VM Profile
- Ubuntu 24.04 LTS
- 4 vCPU
- 8 GB RAM
- 80 GB SSD
- Bridged network + static IP

## Prerequisites (inside VM)
- `sudo` access
- `git`
- Repository available locally or Git remote URL

## Script Path
`/opt/autohaggle/scripts/deploy/proxmox-deploy.sh` (after clone)

## One-Command Deployment
From repository root:

```bash
chmod +x scripts/deploy/proxmox-deploy.sh
REPO_URL=<your_git_repo_url> \
REPO_BRANCH=main \
INSTALL_NGINX=1 \
./scripts/deploy/proxmox-deploy.sh
```

If `/opt/autohaggle` already exists as a git checkout, `REPO_URL` is optional.

## Configurable Environment Variables
- `APP_NAME` (default: `autohaggle`)
- `APP_USER` (default: current shell user)
- `APP_DIR` (default: `/opt/autohaggle`)
- `REPO_URL` (required only on first clone)
- `REPO_BRANCH` (default: `main`)
- `ENV_FILE` (default: `.env`)
- `INSTALL_NGINX` (`1` to install/configure Nginx)
- `ENABLE_SERVICES` (`1` to enable/start systemd services)

## What the Script Does
1. Installs OS packages (`python3`, `make`, `git`, etc.).
2. Installs Docker if missing.
3. Clones or updates the repository in `APP_DIR`.
4. Creates `.env` from `.env.example` when missing.
5. Runs `make bootstrap`, `make up`, and `make migrate`.
6. Creates and starts systemd services:
   - `${APP_NAME}-api`
   - `${APP_NAME}-worker`
   - `${APP_NAME}-communication`
   - `${APP_NAME}-warroom`
   - `${APP_NAME}-web`
7. Optionally configures Nginx reverse proxy.

## Post-Deploy Required Configuration
Edit `APP_DIR/.env` and provide real keys as needed:
- `OPENAI_API_KEY`
- `MARKETCHECK_API_KEY`
- `TWILIO_*`
- `SENDGRID_*`

Then restart services:

```bash
sudo systemctl restart autohaggle-api autohaggle-worker autohaggle-communication autohaggle-warroom autohaggle-web
```

## Verification
```bash
sudo systemctl status autohaggle-api
sudo journalctl -u autohaggle-api -f
curl -f http://127.0.0.1:8000/health
```

If Nginx is enabled, verify LAN entrypoint:
- `http://<vm-ip>/`
