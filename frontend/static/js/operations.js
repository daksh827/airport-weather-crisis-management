/**
 * Phase 4 — Operational impact panel and notification feed.
 */

import { getNotifications, getOperationsImpact } from "./api.js";

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
 * @param {string} value
 */
function statusClass(value) {
  const v = String(value || "").toUpperCase();
  if (/(SEVERE|CRITICAL|POOR|RESTRICTED|DISRUPTED|TEMPORARILY)/.test(v)) return "bad";
  if (/(REDUCED|LIMITED|CAUTION|DELAYED|MONITOR|DEGRADED|WATCH)/.test(v)) return "warn";
  return "ok";
}

/**
 * @param {object} data
 */
export function renderOperationsImpact(data) {
  const fields = [
    ["impact-arrival", data.arrival_operations],
    ["impact-departure", data.departure_operations],
    ["impact-runway-ops", data.runway_operations],
    ["impact-taxiway", data.taxiway_visibility],
    ["impact-ground", data.ground_handling],
    ["impact-passenger", data.passenger_processing],
    ["impact-arrival-rate", data.arrival_rate],
    ["impact-runway-status", data.runway_status],
  ];

  fields.forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value || "—";
    el.classList.remove("ok", "warn", "bad");
    el.classList.add(statusClass(value));
  });

  const overall = document.getElementById("impact-overall");
  if (overall) {
    overall.textContent = data.overall_status || "—";
    overall.classList.remove("ok", "warn", "bad");
    overall.classList.add(statusClass(data.overall_status));
  }
}

/**
 * @param {object[]} items
 */
export function renderNotifications(items) {
  const feed = document.getElementById("notification-feed");
  if (!feed) return;
  feed.innerHTML = "";
  if (!items.length) {
    feed.innerHTML = `<li class="feed-empty">No notifications yet this session.</li>`;
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "feed-item";
    const sev = (item.severity || "").toLowerCase();
    if (sev) li.classList.add(`feed-${sev}`);
    li.innerHTML = `
      <span class="feed-time mono">${formatClock(item.time)}</span>
      <span class="feed-message">${item.message || "—"}</span>
    `;
    feed.appendChild(li);
  });
}

export async function loadOperationsImpact() {
  const panel = document.getElementById("operations-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getOperationsImpact();
    renderOperationsImpact(response.data || {});
    return response.data;
  } catch (error) {
    const overall = document.getElementById("impact-overall");
    if (overall) {
      overall.textContent = "Impact unavailable";
      overall.classList.add("bad");
    }
    console.error("Impact load failed:", error);
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}

export async function loadNotifications() {
  try {
    const response = await getNotifications(30);
    renderNotifications((response.data && response.data.items) || []);
    return response.data;
  } catch (error) {
    console.error("Notification load failed:", error);
    return null;
  }
}
