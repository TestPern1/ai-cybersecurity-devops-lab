# Installation Guide (VirtualBox + Rocky Linux 9)

This guide runs the entire Docker/agent stack **inside a VirtualBox VM** running Rocky Linux 9,
with LM Studio staying on the Windows host (to use the host's GPU directly). This setup was chosen
because WSL2 requires a healthy Windows servicing stack (`wcp.dll`/CBS), and on some machines that
stack is corrupted deeply enough that neither Windows Update, DISM, nor an in-place repair install
can fix it — a VirtualBox VM sidesteps that layer entirely since it's a standard application
install, not a Windows feature.

If your machine doesn't have that problem, WSL2 also works fine as a host for this stack; this
guide only covers the VirtualBox path.

## Why Rocky Linux 9

Free, no registration, RHEL-compatible — the same `dnf`-based commands below apply directly, and
Rocky is what this guide (and the rest of the lab's docs) targets first, with Debian/Ubuntu
substitutions noted where they differ.

## 1. Install VirtualBox on the Windows host

1. Download VirtualBox from the official site (virtualbox.org) and install it normally.
2. Also install the matching **VirtualBox Extension Pack** if you want USB passthrough or better
   RDP support — not required for this lab.

## 2. Create the host-only network (VM <-> Windows host, no internet route)

This is what lets the VM reach LM Studio on Windows without exposing anything to your LAN or the
internet — it's a private, virtual point-to-point network between the VM and this one host machine.

1. Open VirtualBox → **File → Tools → Network Manager** (or **Host Network Manager** on older
   versions).
2. Create a new **Host-only Network** if one doesn't already exist (default name `vboxnet0`).
3. Note its IPv4 address — default is `192.168.56.1`. This is the Windows host's address as seen
   from the VM. If yours differs, use that value everywhere `192.168.56.1` appears below and in
   `.env`.
4. Leave its DHCP server enabled (default) so the VM gets an IP automatically.

## 3. Create the Rocky 9 VM

Sizing for a Ryzen 7 3700X (8c/16t) / 64GB host — this lab's workload (Docker, a handful of Python
agents, Trivy scans) is modest, so it doesn't need much:

- **Type/Version:** Linux / Red Hat (64-bit)
- **RAM:** 8192 MB (8 GB) — plenty of headroom left for LM Studio on the host
- **CPU:** 4 cores
- **Disk:** 40 GB, dynamically allocated (VDI)

Network adapters (**Settings → Network**):
- **Adapter 1:** NAT — gives the VM internet access for package installs (`dnf`, `docker pull`,
  `npm install`, the one-time Trivy DB download). This is the only adapter with any outbound route.
- **Adapter 2:** Host-only Adapter → select `vboxnet0` — this is how the VM reaches LM Studio on
  Windows, and how Windows reaches the VM's services.

Attach the Rocky 9 minimal ISO (**Settings → Storage** → add the `.iso` to the optical drive), boot
the VM, and run through the Rocky installer. A minimal install (no desktop environment) is enough —
everything here is command-line only; you'll view the dashboard from a browser on Windows, not
inside the VM.

## 4. Set up port forwarding (Windows -> VM)

**Settings → Network → Adapter 1 (NAT) → Advanced → Port Forwarding.** Add these rules so
`127.0.0.1:<port>` on Windows reaches the matching service inside the VM:

| Name | Protocol | Host IP | Host Port | Guest IP | Guest Port |
|---|---|---|---|---|---|
| dashboard | TCP | 127.0.0.1 | 4321 | (leave blank) | 4321 |
| open-webui | TCP | 127.0.0.1 | 3000 | (leave blank) | 3000 |
| loki | TCP | 127.0.0.1 | 3100 | (leave blank) | 3100 |
| ssh | TCP | 127.0.0.1 | 2222 | (leave blank) | 22 |

The `ssh` rule is optional but convenient for working in the VM from a Windows terminal
(`ssh -p 2222 <user>@127.0.0.1`) instead of the VirtualBox console window.

These forwarding rules are scoped to `127.0.0.1` on the Windows side — nothing here becomes
reachable from your LAN or the internet, consistent with the lab's loopback-only requirement.

## 5. Inside the VM: install Docker Engine

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

Verify:
```bash
docker --version
docker compose version
newgrp docker
docker run --rm hello-world
```

## 6. Inside the VM: install Ansible, Trivy, git, Python

```bash
sudo dnf install -y ansible-core git python3 python3-pip

curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | \
  sh -s -- -b /usr/local/bin

trivy --version
```

Pre-download Trivy's vulnerability database once, while the VM still has network access via the NAT
adapter, so scans run fully offline afterward:

```bash
trivy image --download-db-only
```

## 7. Get the project into the VM

Easiest path is `git clone` your repo (once you've pushed it) directly inside the VM:

```bash
git clone <your-repo-url>
cd ai-cybersecurity-devops-lab
```

If you haven't pushed yet, use `scp` from Windows over the `ssh` port-forward instead:
```powershell
scp -P 2222 -r "D:\Ai projects\Projects\ai-cybersecurity-devops-lab" <user>@127.0.0.1:~/
```

## 8. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and confirm `LM_STUDIO_BASE_URL` and `HOST_LM_STUDIO_IP` match your host-only adapter's
IP from step 2 (default `192.168.56.1`). Check the VM's own IP on that adapter with:

```bash
ip addr show | grep 192.168.56
```

## 9. Install LM Studio on the Windows host (not inside the VM)

LM Studio stays on Windows to use the RTX 3070 directly — it is a desktop app, not something that
runs in this VM.

1. Download and install LM Studio normally on Windows.
2. Download an open-weight model such as `Qwen2.5-7B-Instruct` (adjust `LM_STUDIO_MODEL` in `.env`
   to match whatever model ID LM Studio reports).
3. Go to LM Studio's **Developer** tab and start the local server.
4. By default LM Studio binds to `127.0.0.1`, which the VM cannot reach (loopback is
   machine-local, not shared across a VM boundary). Enable LM Studio's **"Serve on Local Network"**
   option so it binds to `0.0.0.0:1234` instead.
5. **Immediately lock this down in Windows Firewall** so it's reachable only from the VM's
   host-only subnet, not your whole LAN:
   ```powershell
   New-NetFirewallRule -DisplayName "LM Studio - VM only" -Direction Inbound -Protocol TCP `
     -LocalPort 1234 -RemoteAddress 192.168.56.0/24 -Action Allow
   New-NetFirewallRule -DisplayName "LM Studio - block other inbound" -Direction Inbound -Protocol TCP `
     -LocalPort 1234 -RemoteAddress Any -Action Block
   ```
   (Run as Administrator. Adjust `192.168.56.0/24` if your host-only network uses a different range.)

This keeps the "local only" security intent intact — LM Studio's server is reachable only from this
VM, not the internet or your LAN, even though it's no longer bound to literal `127.0.0.1`.

## 10. Block internet egress for the Docker network (firewalld, inside the VM)

The lab's Docker network (`lab_internal`, fixed subnet `172.28.1.0/24`) is **not** created with
Docker's `internal: true` flag, because that flag also silently breaks published ports (see the
comment in `docker/docker-compose.yml` if you want the full story — short version: `internal: true`
disables the same iptables chain that host-port publishing needs, so `ports:` stops working with no
error). Instead, "these containers can't reach the internet" is enforced one layer down, at the
host firewall, against that fixed subnet:

```bash
sudo firewall-cmd --permanent --direct --add-rule ipv4 filter FORWARD 0 \
  -s 172.28.1.0/24 ! -d 192.168.56.0/24 -j REJECT
sudo firewall-cmd --reload
```

This blocks the Docker network from reaching anywhere except your host-only subnet (where LM Studio
lives) — no internet, no LAN, while leaving host->container published ports (which don't go through
this `FORWARD` path) untouched. Adjust `192.168.56.0/24` if your host-only network differs.

Verify it's actually blocking:
```bash
docker exec lab_open_webui ping -c1 -W2 8.8.8.8   # should fail/time out
```

## 11. Bring up the Docker stack (inside the VM)

`docker compose` only auto-loads a `.env` file from the directory you run it in — since `.env`
lives at the repo root and `docker-compose.yml` lives in `docker/`, run this from the repo root
with an explicit `--env-file`, not `cd docker && docker compose up -d` (that silently falls back to
blank/default values for everything in `.env`, including `HOST_LM_STUDIO_IP`):

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d
docker compose -f docker/docker-compose.yml --env-file .env ps
```

Loki, Promtail, and Open-WebUI come up on the `lab_internal` network, egress-blocked by the
firewalld rule above, all published only to the VM's own `127.0.0.1`. The Windows port-forwarding
rules from step 4 are what expose them to your Windows browser.

Confirm Open-WebUI can reach LM Studio (same `-f`/`--env-file` flags as above are required here too
— a bare `docker compose exec ...` from the repo root will fail with "no configuration file
provided" since `docker-compose.yml` isn't in this directory):
```bash
docker compose -f docker/docker-compose.yml --env-file .env exec open-webui getent hosts host.docker.internal
```
This should print your host-only adapter's IP (e.g. `192.168.56.1`), not `172.17.0.1` (the
container's own default bridge gateway) — if you see `172.17.0.1`, the container was created before
`HOST_LM_STUDIO_IP` was set correctly in `.env`; fix `.env` and re-run with `--force-recreate`:
```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --force-recreate open-webui
```
This should resolve to your host-only adapter IP (`192.168.56.1` by default). Then from Windows,
visit `http://127.0.0.1:3000` and confirm it can see your local Qwen model.

## 12. Run the agents (inside the VM)

```bash
cd ../agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python deployment_agent.py                    # dry-run by default
python telemetry_agent.py --minutes 15
python telemetry_agent.py --sandbox-inspect    # Step 1: sandboxed log inspection
python vulnerability_agent.py alpine:3.19
python remediation_agent.py <path-to-a-summary-file>
python counter_swarm.py                        # Step 3: simulated counter-swarm round
```

`sandbox.py` runs its own disposable Docker containers — this works fine from inside the VM, since
Docker-in-a-VM is standard, no nesting concerns here (unlike Docker-in-Docker).

## 13. Run the dashboard (inside the VM, viewed from Windows)

```bash
cd ../web
npm install
npm run dev
```

Visit `http://127.0.0.1:4321` **from Windows** (the port-forward from step 4 routes it into the VM).
`npm install` needs the VM's NAT/internet access; once built, `npm run preview` serves the compiled
static site with no further network dependency.

## Troubleshooting

- **Open-WebUI can't reach LM Studio:** confirm LM Studio's server is running with "Serve on Local
  Network" enabled (step 9.4), the Windows Firewall rule allows the host-only subnet (step 9.5), and
  `docker compose exec open-webui getent hosts host.docker.internal` resolves to the right IP.
- **VM can't reach the internet during `dnf`/`npm install`:** confirm Adapter 1 is NAT and attached,
  and that the VM actually picked up a NAT-assigned address (`ip addr show` should show an
  interface in the `10.0.2.x` range in addition to the `192.168.56.x` host-only one).
- **Windows browser can't reach `127.0.0.1:4321`/`:3000`/`:3100`:** re-check the port-forwarding
  table in step 4 — a typo in host/guest port is the most common cause. Also confirm the service is
  actually running inside the VM (`docker compose ps`, or the `npm run dev` terminal).
- **`docker compose up` fails to pull images:** the *first* pull of each image needs the VM's NAT
  internet access — once pulled, `internal: true` only affects the running containers, not the
  initial `docker pull`.
- **Host-only adapter IP isn't `192.168.56.1`:** check **File → Tools → Network Manager** in
  VirtualBox for the actual IPv4 address of your host-only network, and use that value everywhere
  `192.168.56.1` appears in this guide, `.env`, and `docker-compose.yml`'s `HOST_LM_STUDIO_IP`
  default.
