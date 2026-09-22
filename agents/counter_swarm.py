"""Counter-Swarm — a local, fully simulated offense/defense loop (Step 3).

Two synthetic actors, no real network or infrastructure involved:

- `simulate_traffic()`   — generates a stream of synthetic request records,
                            some benign, some tagged as scan/brute-force-like
                            patterns. This never sends a real packet; it just
                            produces log-shaped dict records in memory.
- `DefensiveSwarm`        — watches that stream and reacts by writing to a
                            local JSON state file (`counter_swarm_state.json`):
                            "blocking" a source IP, "rotating" a mock token,
                            "rotating" a mock SSH key fingerprint. All of this
                            is bookkeeping in a local file the dashboard can
                            poll — it never touches a real firewall, real
                            tokens, or real keys.

Every "IP", "token", and "key" here is generated locally and clearly marked
synthetic — nothing here is a credential, and nothing here reaches a network
interface. This models the decision loop (detect -> decide -> act -> log),
which is the actual training goal, without the blast radius of touching real
firewall rules or credentials.
"""

from __future__ import annotations

import dataclasses
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).parent / "counter_swarm_state.json"

SCAN_THRESHOLD = 3  # synthetic "requests from same source within window" -> block


@dataclasses.dataclass
class TrafficEvent:
    timestamp: str
    source_ip: str
    path: str
    pattern: str  # "benign" | "scan" | "brute_force"


def simulate_traffic(n: int = 20, seed: int | None = None) -> list[TrafficEvent]:
    rng = random.Random(seed)
    benign_paths = ["/", "/health", "/api/status", "/dashboard"]
    scan_paths = ["/admin", "/.env", "/wp-login.php", "/.git/config", "/api/v1/../../etc/passwd"]

    events: list[TrafficEvent] = []
    for _ in range(n):
        is_malicious = rng.random() < 0.35
        source_ip = f"10.99.{rng.randint(0, 254)}.{rng.randint(1, 254)}"  # synthetic /16, never routed
        if is_malicious:
            events.append(TrafficEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_ip=source_ip,
                path=rng.choice(scan_paths),
                pattern=rng.choice(["scan", "brute_force"]),
            ))
        else:
            events.append(TrafficEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_ip=source_ip,
                path=rng.choice(benign_paths),
                pattern="benign",
            ))
    return events


class DefensiveSwarm:
    """Reacts to simulated traffic by updating local, synthetic defense state."""

    def __init__(self) -> None:
        self.blocked_ips: set[str] = set()
        self.actions: list[dict] = []
        self._offense_counts: dict[str, int] = {}

    def observe(self, event: TrafficEvent) -> None:
        if event.pattern == "benign":
            return

        self._offense_counts[event.source_ip] = self._offense_counts.get(event.source_ip, 0) + 1
        count = self._offense_counts[event.source_ip]

        if event.pattern == "brute_force" and count >= 1:
            self._rotate_mock_credentials(event)

        if count >= SCAN_THRESHOLD and event.source_ip not in self.blocked_ips:
            self._block_ip(event)

    def _block_ip(self, event: TrafficEvent) -> None:
        self.blocked_ips.add(event.source_ip)
        self._log_action(
            f"Blocked {event.source_ip} (simulated firewall rule) after "
            f"{self._offense_counts[event.source_ip]} suspicious requests"
        )

    def _rotate_mock_credentials(self, event: TrafficEvent) -> None:
        mock_token = f"mock-token-{random.randint(100000, 999999)}"
        mock_key_fp = f"SHA256:mock{random.randint(1000, 9999)}fingerprint"
        self._log_action(
            f"Rotated mock API token -> {mock_token} and mock SSH key fingerprint -> "
            f"{mock_key_fp} in response to brute-force pattern from {event.source_ip}"
        )

    def _log_action(self, description: str) -> None:
        self.actions.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "description": description,
        })

    def to_state(self) -> dict:
        return {
            "blocked_ips": sorted(self.blocked_ips),
            "actions": self.actions,
        }


def run_round(n_events: int = 20, seed: int | None = None) -> dict:
    swarm = DefensiveSwarm()
    events = simulate_traffic(n=n_events, seed=seed)
    for event in events:
        swarm.observe(event)

    state = swarm.to_state()
    state["events_seen"] = len(events)
    state["malicious_events"] = sum(1 for e in events if e.pattern != "benign")
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def main() -> None:
    print(f"Writing state to {STATE_FILE}")
    state = run_round()
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
