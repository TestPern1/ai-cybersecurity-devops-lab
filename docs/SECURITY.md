# Security & Secret Hygiene

This project is designed to be safe to publish publicly on GitHub. That safety comes from process,
not luck — follow this checklist every time, not just on the first commit.

## Design constraints (why this repo can be public)

- **Air-gapped by design.** Every container in `docker/docker-compose.yml` runs on a Docker network
  with a fixed subnet (`172.28.1.0/24`). Egress is blocked at the host firewall (`firewalld`, see
  `docs/INSTALL.md` step 10) rather than via Docker's own `internal: true` flag — that flag also
  silently disables published ports on the same network (confirmed while building this lab: the
  port binding gets recorded but never actually opens), so it's incompatible with this project's
  requirement to publish Open-WebUI/Loki to `127.0.0.1`. The firewalld rule achieves the same
  "no outbound route" property without that conflict.
- **Loopback-scoped via the VM boundary, not literal 127.0.0.1 binds.** Inside the VM, services bind
  to all interfaces (`0.0.0.0`), not `127.0.0.1` — VirtualBox's NAT port-forwarding delivers
  Windows->VM traffic to the VM's real NIC, so a strict `127.0.0.1` bind inside the guest is
  unreachable even with a correct forward rule (confirmed the hard way: TCP handshake succeeded,
  HTTP request got reset, because nothing was listening on the interface the traffic actually
  arrived on). The "not reachable from your LAN or the internet" property instead comes from the
  VirtualBox network topology itself: NAT only exposes what's explicitly forwarded (to Windows'
  own `127.0.0.1` — see docs/INSTALL.md step 4), and the host-only adapter has no route beyond this
  one physical machine.
- **No real secrets ever needed.** LM Studio's local server doesn't require a real API key (the
  placeholder `lm-studio` value satisfies the OpenAI SDK's "non-empty string" requirement only).
  Nothing in this stack talks to a paid or hosted API.

## Pre-commit checklist (run this before every `git add`, not just the first one)

1. **Diff review, not just `git add -A`.** Run `git status` and `git diff --cached` and actually
   read what's staged before committing. Don't blind-stage a whole directory.
2. **Grep staged files for secret patterns:**
   ```
   git diff --cached | grep -iE "(api[_-]?key|apikey|secret|password|token|sk-[a-zA-Z0-9]|AIza|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)"
   ```
   Any hit needs manual review — is it a real value or an intentional placeholder/fixture?
3. **No real `.env`.** Confirm `.env` never appears in `git status` as a tracked or staged file —
   `.gitignore` excludes it, but a forced `git add -f .env` would bypass that. Only `.env.example`
   with dummy values should ever be committed.
4. **No hardcoded local paths or usernames.** Scan for your actual Windows username, absolute local
   paths (`C:\Users\<name>\...`, `D:\Ai projects\...`), or hostnames leaking into config files,
   comments, or log fixtures. Use relative paths and env vars instead.
5. **No real log/database artifacts.** `docker/loki/data/` and any `*.sqlite`/`*.db` files are
   git-ignored — verify none were force-added. Sample/fixture logs used for the telemetry agent demo
   should be clearly synthetic (fake IPs, fake hostnames), not pulled from a real system.
6. **License headers match permissive OSS.** Any vendored snippet or dependency should be MIT or
   Apache-2.0 licensed — check `LICENSE` files of anything added to `agents/requirements.txt` or
   `web/package.json` before adding it.

## If you find something real

Stop. Do not commit, do not push, and do not just delete the line and continue silently — flag it
so the exposure (if already committed locally) can be handled properly. A secret that was only
ever staged/committed locally and never pushed is easy to fix (amend or drop the commit). A secret
that reached a remote needs to be treated as compromised: rotate it, then clean history.
