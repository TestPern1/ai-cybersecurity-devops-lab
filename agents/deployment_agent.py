"""Deployment Agent — manages Ansible/Docker deployment actions.

Runs Ansible playbooks against the local lab environment and asks the local
LLM to summarize the outcome in plain language for the dashboard's agent
status panel. Deliberately does not auto-apply anything destructive without
an explicit `--apply` flag; a dry run (`--check`) is the default.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common.llm_client import ask

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = REPO_ROOT / "ansible" / "playbooks" / "deploy.yml"
INVENTORY = REPO_ROOT / "ansible" / "inventory" / "hosts.ini"

SYSTEM_PROMPT = """You are a Deployment Agent summarizing Ansible run output for a security
operations dashboard. Summarize outcome, changed hosts, and any failures in 2-3 sentences.
Do not invent results that are not present in the provided output."""


def run_playbook(apply: bool = False) -> dict:
    cmd = ["ansible-playbook", "-i", str(INVENTORY), str(PLAYBOOK)]
    if not apply:
        cmd.append("--check")

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "mode": "apply" if apply else "dry-run",
    }


def summarize(run_result: dict) -> str:
    return ask(SYSTEM_PROMPT, json.dumps(run_result))


def main() -> None:
    parser = argparse.ArgumentParser(description="Deployment Agent")
    parser.add_argument("--apply", action="store_true", help="Apply changes instead of dry-run")
    parser.add_argument("--no-summarize", action="store_true", help="Skip the LLM summary step")
    args = parser.parse_args()

    result = run_playbook(apply=args.apply)
    print(json.dumps(result, indent=2))

    if not args.no_summarize:
        print("\n--- Agent Summary ---")
        print(summarize(result))

    sys.exit(0 if result["returncode"] == 0 else 1)


if __name__ == "__main__":
    main()
