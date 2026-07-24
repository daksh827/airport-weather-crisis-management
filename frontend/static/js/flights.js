/**
 * Phase 5A — Flight Operations and Runway Operations panels.
 */

import { getFlightOperations, getRunwayOperations } from "./api.js";

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
 * @param {object} data
 */
export function renderFlightOperations(data) {
  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  setText("flights-arrivals", data.arrivals ?? "--");
  setText("flights-departures", data.departures ?? "--");
  setText("flights-delayed", data.delayed ?? "--");
  setText("flights-cancelled", data.cancelled ?? "--");
  setText("flights-diverted", data.diverted ?? "--");
  setText("flights-last-updated", formatDateTime(data.last_updated));
}

/**
 * @param {object} data
 */
export function renderRunwayOperations(data) {
  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  const status = data.status || "—";
  setText("runway-number", data.runway_number || "—");
  setText("runway-status", status);
  setText("runway-surface", data.surface || "—");
  setText("runway-inspection", data.inspection || "—");
  setText("runway-lighting", data.lighting || "—");
  setText("runway-last-updated", formatDateTime(data.last_updated));

  const statusEl = document.getElementById("runway-status");
  const card = document.getElementById("runway-ops-card");
  if (statusEl) {
    statusEl.classList.remove("ok", "warn", "bad");
    if (status === "OPEN") statusEl.classList.add("ok");
    else if (status === "LIMITED") statusEl.classList.add("warn");
    else if (status === "CLOSED") statusEl.classList.add("bad");
  }
  if (card) {
    card.classList.remove("runway-open", "runway-limited", "runway-closed");
    if (status === "OPEN") card.classList.add("runway-open");
    else if (status === "LIMITED") card.classList.add("runway-limited");
    else if (status === "CLOSED") card.classList.add("runway-closed");
  }
}

export async function loadFlightOperations() {
  const panel = document.getElementById("flights-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getFlightOperations();
    renderFlightOperations(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Flight operations load failed:", error);
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}

export async function loadRunwayOperations() {
  const panel = document.getElementById("runway-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getRunwayOperations();
    renderRunwayOperations(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Runway operations load failed:", error);
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}
