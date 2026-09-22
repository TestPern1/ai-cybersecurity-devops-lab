# AI Cybersecurity DevOps Lab

A fully local, air-gapped, 100% open-source (MIT/Apache-2.0) DevOps + AI cybersecurity training
lab: a multi-agent Python backend coordinating Ansible, Docker, Loki/Promtail, and Trivy, fronted
by a local dashboard website — everything running against `127.0.0.1` only, on a local Qwen model
served by LM Studio.

## Mission

Build hands-on fluency in AI-assisted DevOps security workflows — deployment automation, log
telemetry, vulnerability scanning, and gated auto-remediation — using only local, open-weight
models and permissively-licensed tooling. No cloud API, no telemetry, no data ever leaves this
machine.

## Why this is safe to publish

- **Air-gapped by design:** all containers run on a Docker network created with `internal: true`
  (no outbound/inbound internet route).
- **Loopback-only:** every service (Open-WebUI, Loki, the dashboard) binds strictly to
  `127.0.0.1`.
- **No real secrets required:** the local LM Studio server needs no real API key; `.env.example`
  ships placeholder values only, `.env` is git-ignored.
- **Pre-commit security checklist:** see [docs/SECURITY.md](docs/SECURITY.md) — followed before
  every commit, not just the first one.

## Architecture

```
Docker Compose → Promtail/Loki → Trivy → Ansible → Local Qwen Agents → Dashboard
```

Full diagram and trust-boundary breakdown: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository structure

```
/
├── agents/          # Python multi-agent backend (deployment, telemetry, vulnerability, remediation)
├── ansible/          # Playbooks + inventory for the Deployment Agent
├── docker/           # docker-compose.yml + Loki/Promtail config (air-gapped network)
├── web/              # Vite + Tailwind dashboard: architecture diagram, live agent status, CVE alerts
├── docs/             # INSTALL.md, ARCHITECTURE.md, SECURITY.md
├── .env.example      # Placeholder config values — copy to .env, never commit .env
└── .gitignore        # Excludes .env, logs, local DBs, caches, IDE dirs
```

## Getting started

Full step-by-step setup (installing Docker/Ansible/Trivy from scratch, configuring LM Studio,
bringing up the stack): [docs/INSTALL.md](docs/INSTALL.md).

Quick version, once everything is installed:

```bash
cp .env.example .env
cd docker && docker compose up -d
cd ../agents && pip install -r requirements.txt
python telemetry_agent.py --sandbox-inspect   # Step 1: sandboxed log inspection
python counter_swarm.py                       # Step 3: simulated counter-swarm round
cd ../web && npm install && npm run dev   # http://127.0.0.1:4321
```

## Agents

| Agent | Role | Guardrail |
|---|---|---|
| Deployment | Runs Ansible against the local stack, summarizes results | Dry-run (`--check`) by default |
| Telemetry | Queries Loki, flags anomalies in recent logs | Untrusted log content wrapped in `<log_data>` containment tags; optional `--sandbox-inspect` runs raw-line inspection in the isolated sandbox |
| Vulnerability | Runs Trivy (offline DB) against images/filesystem, triages via LLM | Summary grounded strictly in scan JSON |
| Remediation | Proposes a fix command based on findings | Deterministic deny-list check + mandatory human approval before execution |
| Sandbox (`agents/sandbox.py`) | Isolated, disposable Docker boundary for running commands derived from untrusted log/scan data | `--network none`, read-only root, capabilities dropped, non-root user, bounded memory/pids/timeout |
| Counter-Swarm (`agents/counter_swarm.py`) | Simulated attacker traffic vs. a defensive swarm that "blocks" IPs and "rotates" mock tokens/keys | Fully synthetic — writes only to a local, git-ignored JSON state file, never touches a real firewall or credential |

These guardrails aren't decorative — they're the same lessons red-teamed and validated in the
companion [`Cybersecurity_AI_Learning`](https://github.com/TestPern1/Cybersecurity_AI_Learning)
repo: schema/output validation isn't correctness validation, untrusted data needs structural
containment, and an LLM with tool access needs least-privilege scoping plus a human gate.

## Disclaimer

Educational lab running entirely on local infrastructure. No production systems, third-party
services, or real credentials are involved anywhere in this repository.
