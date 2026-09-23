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

Set both adapters' **Adapter Type** to **Paravirtualized Network (virtio-net)**, not the default
Intel PRO/1000 emulation — Rocky 9's kernel has virtio drivers built in, and virtio-net has
meaningfully less overhead than emulating real NIC hardware in software. No functional difference
for this lab either way, just better performance.

Attach the Rocky 9 minimal ISO (**Settings → Storage** → add the `.iso` to the optical drive). All
the settings above live under **right-click the VM in VirtualBox Manager → Settings** — easy to miss
if you're used to a different hypervisor's UI. When you boot, use the regular **Start** (normal, not
headless) so you get a console window to watch the installer — pick **"Normal Start"** if you're
asked, or use **"Detachable Start"** if you want the console window to stay open independently of
the VirtualBox Manager window it launched from. Then run through the Rocky installer normally. A
minimal install (no desktop environment) is enough — everything here is command-line only; you'll
view the dashboard from a browser on Windows, not inside the VM. Note: the installer's mouse
pointer will be inaccurate/unusable until Guest Additions are installed (which needs a running OS
first) — navigate the installer with the keyboard (`Tab`/`Space`/`Enter`/arrow keys) instead; this
won't matter again once you're at a text console.

## 4. Set up port forwarding (Windows -> VM)

**Settings → Network → Adapter 1 (NAT) → Advanced → Port Forwarding.** Add these rules so
`127.0.0.1:<port>` on Windows reaches the matching service inside the VM:

| Name | Protocol | Host IP | Host Port | Guest IP | Guest Port |
|---|---|---|---|---|---|
| open-webui | TCP | 127.0.0.1 | 3000 | (leave blank) | 3000 |
| loki | TCP | 127.0.0.1 | 3100 | (leave blank) | 3100 |
| ssh | TCP | 127.0.0.1 | 2222 | (leave blank) | 22 |

The `ssh` rule is optional but convenient for working in the VM from a Windows terminal
(`ssh -p 2222 <user>@127.0.0.1`) instead of the VirtualBox console window.

These forwarding rules are scoped to `127.0.0.1` on the Windows side — nothing here becomes
reachable from your LAN or the internet, consistent with the lab's loopback-only requirement.

**No dashboard (4321) rule** — deliberately. VirtualBox's built-in NAT engine ("slirp") has a
confirmed bug where certain HTTP responses through a NAT port-forward just hang forever (connects,
sends the request, never gets a response back — not a refusal, a silent stall), while the exact same
request works instantly over the host-only adapter instead. Loki/Open-WebUI's responses happened not
to trigger it; the dashboard's did. Rather than fight VirtualBox's NAT engine, access the dashboard
directly via the VM's **host-only IP** (see step 13) — this is no less secure than the NAT path,
since host-only is already a private link reachable only from this one Windows machine, same
reasoning as LM Studio's reachability in step 9.

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

## 6. Inside the VM: install Ansible, Trivy, git, Python, Node.js

```bash
sudo dnf install -y ansible-core git python3 python3-pip

curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | \
  sudo sh -s -- -b /usr/local/bin
# sudo is required here — the install script writes to /usr/local/bin, which your
# unprivileged user can't write to; without it the script fails silently on the copy step.

trivy --version
```

Pre-download Trivy's vulnerability database once, while the VM still has network access via the NAT
adapter, so scans run fully offline afterward:

```bash
trivy image --download-db-only
```

Rocky 9's AppStream `nodejs` package is version 16, which is too old for this project's Vite
version — it fails at `npm run dev` with `TypeError: crypto$2.getRandomValues is not a function`
(Vite expects Node's global Web Crypto API, stable only from Node 20+). Install a current Node LTS
from NodeSource instead. Do this as its own clean step — mixing NodeSource's `nodejs` (which bundles
its own `npm` at the same file paths as the separately-packaged AppStream `npm`) with the AppStream
packages already installed causes a `dnf` file-conflict error that `--allowerasing` does **not**
resolve (confirmed: it's a file-path conflict, not a dependency-resolution conflict, so remove the
old packages outright first, don't try to upgrade in place):

```bash
sudo dnf remove -y nodejs npm nodejs-full-i18n nodejs-docs
sudo dnf clean all

curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs

node --version   # should print v20.x
npm --version
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

Verify it's actually blocking (the container images here don't ship `ping`, so use `curl` with a
short timeout instead):
```bash
docker exec lab_open_webui curl -m 3 -sS http://8.8.8.8   # should time out / fail to connect
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
firewalld rule above. Their published ports bind to all interfaces *inside the VM* (not
`127.0.0.1`) — VirtualBox's NAT delivers Windows->VM forwarded traffic to the VM's real NIC, not its
loopback, so a `127.0.0.1`-only bind inside the guest is unreachable from Windows even with a
correct forward rule (this one cost real debugging time: the TCP handshake succeeded, but the HTTP
request got reset, because nothing was listening on the interface traffic actually arrived on). The
Windows port-forwarding rules from step 4 are still what scope actual exposure — nothing here
reaches your LAN or the internet, only Windows' own `127.0.0.1` via those explicit rules.

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

`agents/common/llm_client.py` loads the repo-root `.env` automatically (via `python-dotenv`), so
running an agent directly picks up the same `LM_STUDIO_BASE_URL` etc. as the Docker stack does — no
manual `export`/`source .env` needed:

```bash
cd agents
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

**Visit the dashboard via the VM's host-only IP, not `127.0.0.1:4321`** — confirmed live: VirtualBox's
NAT port-forward hangs indefinitely on this specific service's HTTP responses (a NAT-engine bug, not
a project bug — see step 4's note), while the same request over the host-only adapter works
instantly. Find the VM's host-only IP if you don't already have it from step 8:

```bash
ip addr show | grep 192.168.56
```

Then from Windows, visit `http://<that-ip>:4321` (e.g. `http://192.168.56.101:4321` — yours may
differ; DHCP-assigned host-only IPs are usually stable across reboots but not guaranteed).

`npm install` needs the VM's NAT/internet access; once built, `npm run preview` serves the compiled
static site the same way (also reachable via the host-only IP), with no further network dependency.

If you close the terminal running `npm run dev`, the dashboard stops. To keep it running detached:
```bash
nohup npm run dev > /tmp/vite.log 2>&1 &
disown
```

## Troubleshooting

Failure modes below are listed roughly in the order they're worth checking — several of them look
identical from the browser (page won't load) but have different causes and fixes.

- **VirtualBox: "Could not find Host Interface Networking driver" (E_FAIL 0x80004005) when creating
  the host-only network:** the driver is usually present but *disabled* in Windows, not missing —
  check `Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "*VirtualBox*" }` and
  `Enable-NetAdapter -Name "<name>"` if it shows `Disabled`. If the driver is genuinely missing,
  repair the VirtualBox install (Control Panel → Programs → Oracle VM VirtualBox → Change/Repair).
- **Mouse is inaccurate/unusable in the Rocky installer:** expected — Guest Additions (which fix
  this) can't be installed until there's an OS to install them into. Navigate the installer with the
  keyboard (`Tab`/`Space`/`Enter`/arrows) instead; this won't come up again once you're at a text
  console, since the minimal install has no desktop environment to need a mouse for.
- **SSH (`ssh -p 2222 ...`) fails with `kex_exchange_identification: read: Connection reset`:** the
  TCP connection succeeded but nothing spoke SSH back — check the port-forward rule's guest port is
  `22` (not `2222`), confirm `sudo systemctl status sshd` is active inside the VM, and check
  `sudo firewall-cmd --list-services` includes `ssh`.
- **`docker run --rm hello-world` fails with "permission denied ... docker.sock":** your shell
  session predates the `usermod -aG docker` group change taking effect. Run `newgrp docker` (or log
  out/back in over SSH) rather than re-running `usermod`.
- **`git clone` fails with "Permission denied" creating the work tree dir:** you're likely in a
  root-owned directory (e.g. `/usr/local`). `cd ~` first, then clone — the rest of this guide's `cd`
  steps assume the repo landed in your home directory.
- **An agent (e.g. `deployment_agent.py`) fails with `openai.APIConnectionError` /
  `httpcore.ConnectError: [Errno 111] Connection refused`:** `agents/common/llm_client.py` fell back
  to its hardcoded default (`http://127.0.0.1:1234/v1`), meaning your `.env` never got loaded — check
  that `python-dotenv` installed correctly (`pip install -r requirements.txt` from `agents/`) and
  that `.env` actually exists at the repo root (`ls ../.env` from inside `agents/`). If you see
  `ValueError: Refusing to configure a non-local LM_STUDIO_BASE_URL` instead, your `.env` has a
  public/non-private address in `LM_STUDIO_BASE_URL` — it should be a loopback address or a private
  one like the host-only adapter's `192.168.56.1`, never a public IP.
- **`OPEN_WEBUI_SECRET_KEY`/other `.env` values not taking effect, or `docker compose exec ...`
  fails with "no configuration file provided":** `docker compose` only auto-loads `.env` from the
  directory you run it in, and only finds `docker-compose.yml` if you point `-f` at it. Always run
  compose commands from the repo root with both flags:
  `docker compose -f docker/docker-compose.yml --env-file .env <subcommand>` — not a bare
  `docker compose ...` from the repo root, and not `cd docker && docker compose ...` either.
- **`docker compose ps` output looks garbled/truncated (e.g. `PORTS` column missing):** usually just
  your terminal width wrapping the table oddly, not a real problem — confirm with
  `docker port <container_name>` instead, which prints an unambiguous single-line mapping.
- **A service's port binding doesn't seem to apply even after editing `.env`/`docker-compose.yml`
  and re-running `up -d`:** Compose sometimes decides a container's config hash hasn't changed and
  skips recreating it. Force it explicitly: `docker rm -f <container_name>` then
  `docker compose -f docker/docker-compose.yml --env-file .env up -d --no-deps <service_name>`.
- **Open-WebUI can't reach LM Studio:** confirm LM Studio's server is running with "Serve on Local
  Network" enabled (step 9.4), the Windows Firewall rule allows the host-only subnet (step 9.5), and
  `docker compose -f docker/docker-compose.yml --env-file .env exec open-webui getent hosts host.docker.internal`
  resolves to your host-only IP (e.g. `192.168.56.1`), not `172.17.0.1` (the container's own default
  bridge gateway — means `HOST_LM_STUDIO_IP` wasn't set correctly when the container was created;
  fix `.env` and `--force-recreate open-webui`).
- **VM can't reach the internet during `dnf`/`npm install`:** confirm Adapter 1 is NAT and attached,
  and that the VM actually picked up a NAT-assigned address (`ip addr show` should show an
  interface in the `10.0.2.x` range in addition to the `192.168.56.x` host-only one).
- **`npm run dev` fails with `TypeError: crypto$2.getRandomValues is not a function`:** your Node.js
  is too old (Rocky's AppStream `nodejs` is v16; this project's Vite needs 18+, ideally 20+ — see
  step 6). Check with `node --version`. If you try to fix it with
  `dnf install -y nodejs --allowerasing`, that will *not* work here and fails with a file-conflict
  error (`/usr/lib/node_modules/npm/docs ... conflicts with file from package npm-...`) — this is a
  literal file-path collision between NodeSource's bundled `npm` and the separately-packaged
  AppStream `npm`, which `--allowerasing` doesn't resolve (that flag is for dependency-solver
  conflicts, not file-path collisions). Remove the old packages outright first:
  `sudo dnf remove -y nodejs npm nodejs-full-i18n nodejs-docs`, then install fresh from NodeSource
  (full commands in step 6). After upgrading Node, also do a clean `rm -rf node_modules
  package-lock.json && npm install` — modules built against the old Node version can linger.
- **`web/package.json`'s `dev`/`preview` scripts hardcode `--host 127.0.0.1`:** don't reintroduce
  this — CLI flags override `vite.config.js`, so a hardcoded `--host 127.0.0.1` silently undoes the
  `0.0.0.0` bind `vite.config.js` sets (confirmed live: this exact regression happened once already).
  The scripts should just be `"dev": "vite"` / `"preview": "vite preview"`, letting
  `vite.config.js` be the single source of truth for host/port.
- **Dashboard (`:4321`) hangs indefinitely from Windows via `127.0.0.1`, even though `curl` from
  inside the VM (both `127.0.0.1` and the host-only IP) returns instantly:** this is a confirmed
  VirtualBox NAT engine ("slirp") bug, not a project bug — some HTTP responses through the NAT
  port-forward path just stall forever (TCP connects, request is sent, nothing ever comes back,
  no error). Loki/Open-WebUI didn't trigger it; the dashboard's response did. Don't chase this
  further — access the dashboard via the VM's host-only IP instead (`http://192.168.56.101:4321` or
  whatever `ip addr show | grep 192.168.56` reports), per step 13. If Open-WebUI or Loki ever exhibit
  the same symptom, the same host-only-IP workaround applies to them too
  (`http://<host-only-ip>:3000` / `:3100`).
- **From Windows: `Test-NetConnection` to a forwarded port succeeds, but the browser shows
  `ERR_CONNECTION_RESET` (or `curl.exe` shows "Recv failure: Connection was reset"):** this means
  the TCP handshake works but the actual HTTP exchange doesn't — almost always because the service
  inside the VM is bound to `127.0.0.1` instead of `0.0.0.0`. VirtualBox's NAT delivers forwarded
  traffic to the VM's real NIC, not its loopback, so a strict-loopback bind inside the guest can
  never receive it. Check the service's bind address (`docker-compose.yml`'s `ports:` host-IP
  prefix, or `web/vite.config.js`'s `host` setting) — both should already be `0.0.0.0`-equivalent in
  this repo (no `127.0.0.1:` prefix); if you've customized either file, this is the first thing to
  check.
- **Windows browser can't reach `127.0.0.1:4321`/`:3000`/`:3100` at all (times out, not reset):**
  re-check the port-forwarding table in step 4 — a typo in host/guest port is the most common cause.
  Also confirm the service is actually running inside the VM
  (`docker compose -f docker/docker-compose.yml --env-file .env ps`, or the `npm run dev` terminal),
  and that the port-forward rule was added under **Adapter 1 (NAT)**, not Adapter 2 (host-only,
  which has no port-forwarding UI since it's directly routable already).
- **`docker compose up` fails to pull images:** the *first* pull of each image needs the VM's NAT
  internet access — once pulled, the firewalld egress rule from step 10 only affects the running
  containers' outbound traffic, not `docker pull` itself (which the daemon performs, not the
  containers).
- **Host-only adapter IP isn't `192.168.56.1`:** check **File → Tools → Network Manager** in
  VirtualBox for the actual IPv4 address of your host-only network, and use that value everywhere
  `192.168.56.1` appears in this guide, `.env`, and `docker-compose.yml`'s `HOST_LM_STUDIO_IP`
  default.
