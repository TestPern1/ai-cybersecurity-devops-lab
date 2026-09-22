import mermaid from "mermaid";
import "./styles/main.css";
import {
  architectureDiagram,
  getAgentStatuses,
  getCveAlerts,
  getRemediationLog,
  getCounterSwarmLog,
} from "./lib/mockData.js";

mermaid.initialize({ startOnLoad: false, theme: "dark" });

const severityColor = {
  CRITICAL: "text-red-400",
  HIGH: "text-orange-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-gray-400",
};

const statusColor = {
  idle: "bg-gray-600",
  running: "bg-accent",
  "awaiting-approval": "bg-yellow-500",
  error: "bg-red-500",
};

async function renderDiagram() {
  const el = document.getElementById("architecture-diagram");
  const { svg } = await mermaid.render("architecture-svg", architectureDiagram);
  el.innerHTML = svg;
}

function renderAgentStatus() {
  const el = document.getElementById("agent-status");
  el.innerHTML = getAgentStatuses()
    .map(
      (agent) => `
      <div class="bg-surface rounded-lg p-4">
        <div class="flex items-center justify-between mb-1">
          <span class="font-medium">${agent.name}</span>
          <span class="flex items-center gap-2 text-xs text-gray-400">
            <span class="w-2 h-2 rounded-full ${statusColor[agent.status] ?? "bg-gray-600"}"></span>
            ${agent.status}
          </span>
        </div>
        <p class="text-sm text-gray-400">${agent.detail}</p>
        <p class="text-xs text-gray-500 mt-1">Last run: ${agent.lastRun}</p>
      </div>`
    )
    .join("");
}

function renderCveAlerts() {
  const el = document.getElementById("cve-alerts");
  el.innerHTML = getCveAlerts()
    .map(
      (cve) => `
      <div class="p-4 flex items-center justify-between">
        <div>
          <span class="font-mono text-sm">${cve.id}</span>
          <span class="text-sm text-gray-400 ml-2">${cve.package}</span>
          <p class="text-sm text-gray-500">${cve.summary}</p>
        </div>
        <span class="text-xs font-semibold ${severityColor[cve.severity] ?? "text-gray-400"}">${cve.severity}</span>
      </div>`
    )
    .join("");
}

function renderRemediationLog() {
  const el = document.getElementById("remediation-log");
  el.innerHTML = getRemediationLog()
    .map(
      (entry) => `
      <div class="p-4">
        <div class="flex items-center justify-between">
          <span class="text-sm">${entry.action}</span>
          <span class="text-xs text-gray-500">${entry.time}</span>
        </div>
        <p class="text-xs text-gray-500 mt-1">${entry.outcome}</p>
      </div>`
    )
    .join("");
}

function renderCounterSwarmLog() {
  const el = document.getElementById("counter-swarm-log");
  el.innerHTML = getCounterSwarmLog()
    .map(
      (entry) => `
      <div class="p-4">
        <div class="flex items-center justify-between">
          <span class="text-sm">${entry.action}</span>
          <span class="text-xs text-gray-500">${entry.time}</span>
        </div>
      </div>`
    )
    .join("");
}

async function refreshAll() {
  await renderDiagram();
  renderAgentStatus();
  renderCveAlerts();
  renderRemediationLog();
  renderCounterSwarmLog();
}

refreshAll();
// Simulated on-demand refresh, matching the "refreshable views" requirement
// without an actual backend poll loop.
setInterval(() => {
  renderAgentStatus();
  renderCveAlerts();
  renderRemediationLog();
  renderCounterSwarmLog();
}, 15000);
