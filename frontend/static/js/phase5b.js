/**
 * Phase 5B — Terminal Operations, Ground Operations, Airport KPIs.
 */

import {
  getAirportKpis,
  getGroundOperations,
  getTerminalOperations,
} from "./api.js";

/**
 * @param {string} value
 * @param {"load"|"queue"} kind
 */
function toneClass(value, kind) {
  const v = String(value || "").toUpperCase();
  if (kind === "load") {
    if (v === "CRITICAL") return "bad";
    if (v === "BUSY") return "warn";
    return "ok";
  }
  if (v === "HIGH") return "bad";
  if (v === "MEDIUM") return "warn";
  return "ok";
}

/**
 * @param {object} data
 */
export function renderTerminalOperations(data) {
  ["1", "2", "3"].forEach((n) => {
    const block = data[`terminal${n}`] || {};
    const set = (suffix, value) => {
      const el = document.getElementById(`t${n}-${suffix}`);
      if (el) el.textContent = value ?? "—";
    };
    set("occupied", block.occupied_gates);
    set("available", block.available_gates);
    set("boarding", block.boarding_gates);

    const loadEl = document.getElementById(`t${n}-load`);
    if (loadEl) {
      loadEl.textContent = block.passenger_load || "—";
      loadEl.classList.remove("ok", "warn", "bad");
      loadEl.classList.add(toneClass(block.passenger_load, "load"));
    }
    const queueEl = document.getElementById(`t${n}-queue`);
    if (queueEl) {
      queueEl.textContent = block.security_queue || "—";
      queueEl.classList.remove("ok", "warn", "bad");
      queueEl.classList.add(toneClass(block.security_queue, "queue"));
    }
  });
}

const GROUND_LABELS = [
  ["fuel_trucks", "fuel"],
  ["baggage_vehicles", "baggage"],
  ["pushback_vehicles", "pushback"],
  ["catering_vehicles", "catering"],
  ["maintenance_vehicles", "maintenance"],
  ["follow_me_vehicles", "followme"],
];

/**
 * @param {object} data
 */
export function renderGroundOperations(data) {
  GROUND_LABELS.forEach(([key, id]) => {
    const block = data[key] || {};
    const set = (part, value) => {
      const el = document.getElementById(`ground-${id}-${part}`);
      if (el) el.textContent = value ?? "--";
    };
    set("available", block.available);
    set("inuse", block.in_use);
    set("maint", block.maintenance);
  });

  const status = document.getElementById("ground-status");
  if (status) {
    status.textContent = data.ground_status || "—";
    status.classList.remove("ok", "warn", "bad");
    const g = String(data.ground_status || "").toUpperCase();
    if (g === "RESTRICTED") status.classList.add("bad");
    else if (g === "CONSTRAINED") status.classList.add("warn");
    else status.classList.add("ok");
  }
}

/**
 * @param {string} id
 * @param {number} pct
 */
function setProgress(id, pct) {
  const value = Math.max(0, Math.min(100, Number(pct) || 0));
  const fill = document.getElementById(id);
  const label = document.getElementById(`${id}-label`);
  if (fill) fill.style.width = `${value}%`;
  if (label) label.textContent = `${value}%`;
}

/**
 * @param {object} data
 */
export function renderAirportKpis(data) {
  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  setText("kpi-flights-today", data.flights_today ?? "--");
  setText("kpi-passengers-today", data.passengers_today ?? "--");
  setText("kpi-delayed", data.delayed_flights ?? "--");
  setText("kpi-cancelled", data.cancelled_flights ?? "--");
  setText("kpi-avg-delay", data.average_delay != null ? `${data.average_delay} min` : "—");

  setProgress("kpi-runway-bar", data.runway_availability);
  setProgress("kpi-terminal-bar", data.terminal_utilization);
  setProgress("kpi-ground-bar", data.ground_vehicle_availability);
  setProgress("kpi-efficiency-bar", data.operational_efficiency);

  const statusEl = document.getElementById("kpi-airport-status");
  if (statusEl) {
    statusEl.textContent = data.airport_status || "—";
    statusEl.style.color = data.airport_status_color || "";
    statusEl.style.borderColor = data.airport_status_color || "";
    statusEl.classList.remove(
      "status-operational",
      "status-watch",
      "status-limited",
      "status-disrupted",
      "status-closed"
    );
    const key = String(data.airport_status || "")
      .toLowerCase()
      .replace(/\s+/g, "-");
    if (key) statusEl.classList.add(`status-${key}`);
  }
}

export async function loadTerminalOperations() {
  const panel = document.getElementById("terminal-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getTerminalOperations();
    renderTerminalOperations(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Terminal operations load failed:", error);
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}

export async function loadGroundOperations() {
  const panel = document.getElementById("ground-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getGroundOperations();
    renderGroundOperations(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Ground operations load failed:", error);
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}

export async function loadAirportKpis() {
  const panel = document.getElementById("kpi-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getAirportKpis();
    renderAirportKpis(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Airport KPI load failed:", error);
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}
