/**
 * Simulated telemetry, agent status, and CVE data for the dashboard demo.
 * All values here are synthetic fixtures — no real hostnames, IPs, or
 * findings from any actual system. Swap this module for real API calls
 * (to the Telemetry/Vulnerability agents) once the backend is wired up.
 */

export function getAgentStatuses() {
  return [
    { name: "Deployment Agent", status: "idle", lastRun: "2 min ago", detail: "Stack healthy, 5/5 containers up" },
    { name: "Telemetry Agent", status: "running", lastRun: "just now", detail: "Scanning last 15 min of logs" },
    { name: "Vulnerability Agent", status: "idle", lastRun: "14 min ago", detail: "Last scan: 2 HIGH, 0 CRITICAL" },
    { name: "Remediation Agent", status: "awaiting-approval", lastRun: "1 min ago", detail: "1 proposed action pending human review" },
  ];
}

export function getCveAlerts() {
  return [
    { id: "CVE-2026-10321", severity: "HIGH", package: "libexample1.2", summary: "Simulated: out-of-bounds read in parser" },
    { id: "CVE-2026-10455", severity: "HIGH", package: "sample-weblib", summary: "Simulated: improper input validation" },
    { id: "CVE-2026-09981", severity: "MEDIUM", package: "demo-toolkit", summary: "Simulated: denial of service under load" },
  ];
}

export function getRemediationLog() {
  return [
    { time: "10:41:02", action: "Proposed: upgrade sample-weblib to 2.3.1", outcome: "pending human approval" },
    { time: "10:22:17", action: "Approved: rebuild demo-toolkit image", outcome: "applied successfully" },
    { time: "09:58:40", action: "Rejected: command matched deny-list policy", outcome: "blocked automatically" },
  ];
}

export function getCounterSwarmLog() {
  return [
    { time: "10:44:11", action: "Blocked 10.99.42.7 (simulated firewall rule) after 3 suspicious requests" },
    { time: "10:43:02", action: "Rotated mock API token -> mock-token-582103 in response to brute-force pattern from 10.99.19.201" },
    { time: "10:40:55", action: "Blocked 10.99.201.4 (simulated firewall rule) after 3 suspicious requests" },
  ];
}

export function getSandboxStatus() {
  return { active: false, lastRun: "6 min ago", lastVerdict: "1 line inspected, 0 IOCs beyond source IP, no escape attempted" };
}

export const architectureDiagram = `
graph LR
  A[Docker Compose] --> B[Promtail]
  B --> C[Loki]
  A --> D[Trivy Scans]
  C --> E[Telemetry Agent]
  D --> F[Vulnerability Agent]
  E -->|untrusted lines| S[Sandbox: isolated Docker exec]
  S --> E
  E --> G[Local Qwen via LM Studio]
  F --> G
  G --> H[Remediation Agent]
  H -->|human approval gate| I[Ansible Apply]
  A -.->|status| J[Deployment Agent]
  J --> G
  K[Counter-Swarm: simulated traffic] --> L[Defensive Swarm]
  L -->|local state only| M[counter_swarm_state.json]
`;
