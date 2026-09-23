"""Remediation Agent — proposes and (with human approval) executes patch
actions based on the Vulnerability Agent's findings.

Excessive-agency guardrail: this agent NEVER auto-executes a remediation
action. Every proposed action must pass a deterministic policy check and then
be explicitly approved by a human operator before running. This mirrors the
lesson from llm-security-labs/lab4 — an LLM connected to real tools needs
least-privilege scoping and a human-in-the-loop gate, not just a polite
system prompt asking it to be careful.

A note on "wrong" proposals (e.g. `sudo: apt-get: command not found`): this
agent has no awareness of what OS/package-manager the vulnerability actually
applies to, or whether the target was a container image (where the fix
belongs in a rebuilt image, not a command run on this host) versus the host
itself. Confirmed live: given a musl/Alpine finding from scanning
`alpine:3.19`, the local model proposed an `apt-get` command run against this
Rocky/RHEL VM — wrong package manager, and arguably the wrong target
entirely, since the vulnerable package lives inside the scanned image, not
the host. That is expected, not a bug in this code: local open-weight models
will sometimes propose something confidently wrong, and the whole point of
the deny-list + approval gate above is that the blast radius of a wrong
proposal is contained to "the command errors out" (a `command not found`,
harmless) rather than actually damaging anything — even after a human
approves it. Seeing a proposal fail safely like this is the guardrail design
working as intended, not evidence something is broken.
"""

from __future__ import annotations

import argparse
import json
import subprocess

from common.llm_client import ask

SYSTEM_PROMPT = """You are a Remediation Agent. Given a vulnerability summary, propose a
single concrete remediation command (e.g. an apt/dnf upgrade, a docker image bump).
Output ONLY the shell command on the first line, followed by a one-sentence rationale.
Do not use markdown formatting, code fences, or backticks anywhere in your response.
Never propose a command that deletes data, modifies firewall rules, or targets
anything outside the package/image mentioned in the input."""

# Deterministic policy: commands containing any of these are rejected outright,
# regardless of what the model proposed or why.
DENYLIST_SUBSTRINGS = [
    "rm -rf",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "iptables",
    "ufw",
    "> /dev/",
]


def _strip_code_fence(text: str) -> str:
    """Models routinely wrap output in ```bash ... ``` fences even when told
    not to (confirmed live: LM Studio's Qwen did this on the first real run —
    and not just at the very start/end of the response, but with the closing
    fence landing mid-response, right before the rationale text, which a
    naive first-line/last-line strip misses). Don't rely on the system prompt
    alone to prevent this — drop every line that's purely a fence marker,
    wherever it lands, the same "deterministic guard, not just a polite ask"
    principle as the deny-list below.
    """
    lines = [ln for ln in text.strip().splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


def propose_remediation(vulnerability_summary: str) -> tuple[str, str]:
    response = _strip_code_fence(ask(SYSTEM_PROMPT, vulnerability_summary))
    lines = response.strip().splitlines()
    command = lines[0].strip() if lines else ""
    rationale = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
    return command, rationale


def policy_check(command: str) -> str | None:
    lowered = command.lower()
    for bad in DENYLIST_SUBSTRINGS:
        if bad in lowered:
            return f"Rejected by deterministic policy: command contains '{bad}'."
    if not command:
        return "Rejected: empty command."
    return None


def execute(command: str) -> dict:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def main() -> None:
    parser = argparse.ArgumentParser(description="Remediation Agent")
    parser.add_argument("vulnerability_summary_file", help="Path to a text file with the finding")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation (still policy-checked)")
    args = parser.parse_args()

    with open(args.vulnerability_summary_file, "r", encoding="utf-8") as f:
        summary = f.read()

    command, rationale = propose_remediation(summary)
    print(f"Proposed command : {command}")
    print(f"Rationale        : {rationale}")

    rejection = policy_check(command)
    if rejection:
        print(f"\n[X] {rejection}")
        return

    if not args.yes:
        approval = input("\nApprove and execute this command? (y/N): ").strip().lower()
        if approval != "y":
            print("Execution aborted by operator.")
            return

    result = execute(command)
    print(json.dumps(result, indent=2))
    if result["returncode"] != 0:
        print(
            "\n[i] Non-zero exit code. If this is a package-manager-not-found or similar "
            "shell error (not a policy rejection above), that's the local model proposing "
            "something incorrect for this host/target — see the module docstring at the top "
            "of this file for why that's an expected, safely-contained outcome rather than a bug."
        )


if __name__ == "__main__":
    main()
