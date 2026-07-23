/**
 * Phase 4 — Active weather alert, history, checklist, and trends.
 */

import { getAlertHistory, getCurrentAlert } from "./api.js";

const SEVERITY_EMOJI = {
  NORMAL: "🟢",
  WATCH: "🟡",
  WARNING: "🟠",
  CRITICAL: "🔴",
};

/**
 * @param {string|Date|null|undefined} value
 */
function formatTime(value) {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

/**
 * @param {string|Date|null|undefined} value
 */
function formatClock(value) {
  if (!value) return "--:--";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toISOString().slice(11, 16);
}

/**
 * @param {object} payload
 */
export function renderCurrentAlert(payload) {
  const current = payload.current || {};
  const severity = current.severity || "NORMAL";
  const color = current.color || "#22c55e";

  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  setText(
    "active-alert-title",
    `${SEVERITY_EMOJI[severity] || "🟢"} ${current.title || "Normal Operations"}`
  );
  setText("active-alert-level", severity);
  setText("active-alert-status", current.status || "ACTIVE");
  setText("active-alert-time", formatTime(current.timestamp));
  setText("active-alert-description", current.description || "—");
  setText(
    "active-alert-ops",
    (current.affected_operations || []).join(" · ") || "None"
  );

  const card = document.getElementById("active-alert-card");
  if (card) {
    card.classList.remove("sev-normal", "sev-watch", "sev-warning", "sev-critical");
    card.classList.add(`sev-${String(severity).toLowerCase()}`);
    card.style.setProperty("--alert-accent", color);
  }

  const badge = document.getElementById("active-alert-badge");
  if (badge) {
    badge.textContent = severity;
    badge.style.background = `${color}22`;
    badge.style.borderColor = color;
    badge.style.color = color;
  }

  const icon = document.getElementById("active-alert-icon");
  if (icon) icon.textContent = SEVERITY_EMOJI[severity] || "🟢";

  renderChecklist(payload.checklist || current.checklist || []);
  renderTrends(payload.trends || {});
}

/**
 * @param {string[]} items
 */
export function renderChecklist(items) {
  const list = document.getElementById("aocc-checklist");
  if (!list) return;
  list.innerHTML = "";
  const rows = items.length ? items : ["Monitor Wind Conditions"];
  rows.forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="check-mark" aria-hidden="true">✔</span><span>${item}</span>`;
    list.appendChild(li);
  });
}

/**
 * @param {object} trends
 */
export function renderTrends(trends) {
  const map = {
    "trend-temp": trends.temperature || "→",
    "trend-wind": trends.wind || "→",
    "trend-visibility": trends.visibility || "Stable",
    "trend-humidity": trends.humidity || "→",
  };
  Object.entries(map).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    el.classList.remove("up", "down", "flat", "warn");
    if (value === "↑" || value === "Improving") el.classList.add("up");
    else if (value === "↓" || value === "Declining") el.classList.add("down");
    else el.classList.add("flat");
  });
  const summary = document.getElementById("trend-summary");
  if (summary) summary.textContent = trends.summary || "—";
}

/**
 * @param {object[]} items
 */
export function renderAlertHistory(items) {
  const tbody = document.getElementById("alert-history-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!items.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="6" class="table-empty">No alerts recorded yet this session.</td>`;
    tbody.appendChild(tr);
    return;
  }
  items.forEach((row) => {
    const tr = document.createElement("tr");
    const sev = row.severity || "NORMAL";
    tr.innerHTML = `
      <td class="mono">${formatClock(row.time)}</td>
      <td>${row.alert || "—"}</td>
      <td><span class="sev-badge sev-${String(sev).toLowerCase()}">${sev}</span></td>
      <td>${row.status || "—"}</td>
      <td>${row.weather_condition || "—"}</td>
      <td>${row.aocc_action || "—"}</td>
    `;
    tbody.appendChild(tr);
  });
}

export async function loadAlerts() {
  const card = document.getElementById("active-alert-card");
  card?.classList.add("is-loading");
  try {
    const [currentRes, historyRes] = await Promise.all([
      getCurrentAlert(),
      getAlertHistory(40),
    ]);
    renderCurrentAlert(currentRes.data || {});
    renderAlertHistory((historyRes.data && historyRes.data.items) || []);
    return currentRes.data;
  } catch (error) {
    const title = document.getElementById("active-alert-title");
    if (title) title.textContent = "Alert engine unavailable";
    console.error("Alert load failed:", error);
    return null;
  } finally {
    card?.classList.remove("is-loading");
  }
}
