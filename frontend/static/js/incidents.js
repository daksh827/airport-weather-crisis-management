/**
 * Phase 6A — Incident & Crisis Management panel.
 */

import { getIncidentStats, getIncidents } from "./api.js";

/**
 * @param {unknown} value
 */
function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * @param {string|Date|null|undefined} value
 */
function formatDateTime(value) {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

/**
 * @param {string} status
 */
function statusClass(status) {
  const s = String(status || "").toLowerCase();
  if (s.includes("progress")) return "incident-status-progress";
  if (s.includes("assigned")) return "incident-status-assigned";
  if (s.includes("resolved")) return "incident-status-resolved";
  if (s.includes("closed")) return "incident-status-closed";
  return "incident-status-open";
}

/**
 * @param {string} severity
 */
function severityClass(severity) {
  const s = String(severity || "").toLowerCase();
  if (s === "critical" || s === "high") return "incident-sev-high";
  if (s === "medium") return "incident-sev-medium";
  return "incident-sev-low";
}

/**
 * @param {object} stats
 */
export function renderIncidentStats(stats) {
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? "--";
  };

  setText("incident-stat-open", stats.open_incidents ?? "--");
  setText("incident-stat-assigned", stats.assigned ?? "--");
  setText("incident-stat-progress", stats.in_progress ?? "--");
  setText("incident-stat-resolved", stats.resolved_today ?? "--");
  setText("incident-stat-closed", stats.closed_today ?? "--");
}

/**
 * @param {object} data
 */
export function renderIncidentTable(data) {
  const body = document.getElementById("incident-table-body");
  if (!body) return;

  const items = Array.isArray(data.items) ? data.items : [];
  if (!items.length) {
    body.innerHTML =
      '<tr><td colspan="8" class="table-empty">No incidents recorded.</td></tr>';
    return;
  }

  body.innerHTML = items
    .map((item) => {
      const severity = item.severity || "—";
      const status = item.status || "—";
      return `
        <tr>
          <td class="mono">${escapeHtml(item.incident_id)}</td>
          <td>${escapeHtml(item.incident_type)}</td>
          <td><span class="incident-pill ${severityClass(severity)}">${escapeHtml(severity)}</span></td>
          <td>${escapeHtml(item.airport_area)}</td>
          <td>${escapeHtml(item.assigned_department)}</td>
          <td><span class="incident-pill ${statusClass(status)}">${escapeHtml(status)}</span></td>
          <td class="mono">${escapeHtml(formatDateTime(item.created_time))}</td>
          <td class="mono">${escapeHtml(formatDateTime(item.last_updated))}</td>
        </tr>
      `;
    })
    .join("");
}

export async function loadIncidentStats() {
  try {
    const response = await getIncidentStats();
    renderIncidentStats(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Incident stats load failed:", error);
    renderIncidentStats({});
    return null;
  }
}

export async function loadIncidents() {
  const panel = document.getElementById("incident-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getIncidents();
    renderIncidentTable(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Incident list load failed:", error);
    const body = document.getElementById("incident-table-body");
    if (body) {
      body.innerHTML =
        '<tr><td colspan="8" class="table-empty">Unable to load incidents.</td></tr>';
    }
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}

export async function loadIncidentPanel() {
  await loadIncidentStats();
  await loadIncidents();
}

/**
 * Wire Create Incident button (modal deferred to a later phase).
 */
export function initIncidentControls() {
  const button = document.getElementById("btn-create-incident");
  if (!button) return;

  button.addEventListener("click", () => {
    console.info("[Incidents] Create Incident clicked — modal not implemented yet.");
  });
}
