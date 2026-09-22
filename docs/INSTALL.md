# Installation Guide

Written for a Linux / RHEL-compatible host (also applies to Debian/Ubuntu with the package-manager
substitutions noted). Assumes Docker and the auxiliary tools are **not yet installed**.

## 1. Install Docker Engine from scratch

### RHEL / Fedora / CentOS Stream

```bash
sudo dnf remove -y docker docker-client docker-client-latest docker-common \
  docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null

sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# Log out and back in (or `newgrp docker`) for the group change to take effect.
```

### Debian / Ubuntu

```bash
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

### Verify

```bash
docker --version
docker compose version
docker run --rm hello-world
```

## 2. Install Ansible and Trivy

```bash
# RHEL/Fedora
sudo dnf install -y ansible-core

# Debian/Ubuntu
sudo apt-get install -y ansible

# Trivy (both families) — installs from the official binary release, no package
# manager repo needed:
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | \
  sh -s -- -b /usr/local/bin

trivy --version
```

Pre-download Trivy's vulnerability database once, while you still have network access, so scans
run fully offline afterward:

```bash
trivy image --download-db-only
```

## 3. Install Python dependencies for the agents

```bash
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Configure environment

```bash
cd ..
cp .env.example .env
# Edit .env if you want a different port or model name. Never commit this file.
```

## 5. Install LM Studio and load a local model

1. Download LM Studio from the official site and install it normally (this is a desktop app, not
   a container — it runs directly on your RTX 3070/64GB host).
2. In LM Studio, download an open-weight model such as `Qwen2.5-7B-Instruct` (adjust
   `LM_STUDIO_MODEL` in `.env` to match whatever model ID LM Studio reports).
3. Go to LM Studio's **Developer** tab and start the local server. Confirm it's bound to
   `127.0.0.1:1234` (LM Studio's default) — do not expose it on `0.0.0.0`.

## 6. Bring up the air-gapped Docker stack

```bash
cd docker
docker compose up -d
docker compose ps
```

This starts Loki, Promtail, and Open-WebUI, all on the `lab_internal` network
(`internal: true` — no outbound route) and all published only to `127.0.0.1`.

Open-WebUI reaches LM Studio on the host via `host.docker.internal` (mapped through
`host-gateway`, not through any external network) — visit `http://127.0.0.1:3000` to confirm it can
see your local Qwen model.

## 7. Run the agents

```bash
cd ../agents
source .venv/bin/activate

python deployment_agent.py            # dry-run by default
python telemetry_agent.py --minutes 15
python vulnerability_agent.py alpine:3.19
python remediation_agent.py <path-to-a-summary-file>
```

## 8. Run the dashboard website

```bash
cd ../web
npm install
npm run dev
```

Visit `http://127.0.0.1:4321`. `npm install` is the only step in this whole stack that needs
network access (to fetch build tooling) — once built, `npm run preview` serves the compiled static
site with no further network dependency.

## Troubleshooting

- **Open-WebUI can't reach LM Studio:** confirm LM Studio's server is actually running and bound
  to `127.0.0.1:1234`, and that Docker's `host-gateway` extra_hosts entry resolved — run
  `docker compose exec open-webui getent hosts host.docker.internal` to check.
- **`docker compose up` fails to pull images:** the *first* pull of each image needs network
  access (this is a normal Docker Hub/GHCR pull, separate from the lab's own runtime network) —
  once pulled, `internal: true` only affects the running containers, not the initial `docker pull`.
