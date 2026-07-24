/**
 * AOCC dashboard bootstrap — wires modules and 30-minute polling.
 */

import { getHealth } from "./api.js";
import { loadAlerts } from "./alerts.js";
import { initChatbot } from "./chatbot.js";
import { loadFlightOperations, loadRunwayOperations } from "./flights.js";
import { loadNotifications, loadOperationsImpact } from "./operations.js";
import {
  loadAirportKpis,
  loadGroundOperations,
  loadTerminalOperations,
} from "./phase5b.js";
import { initSeverityControls, loadSeverity } from "./severity.js";
import { initWeatherControls, loadWeather } from "./weather.js";

async function loadPhase5bPanels() {
  await loadTerminalOperations();
  await loadGroundOperations();
  await loadAirportKpis();
}

const WEATHER_REFRESH_INTERVAL = 30 * 60 * 1000;

let refreshDeadline = Date.now() + WEATHER_REFRESH_INTERVAL;

/**
 * Update UTC system clock and next-refresh countdown.
 */
function startClock() {
  const clockEl = document.getElementById("system-clock");
  const nextEl = document.getElementById("next-refresh");

  const tick = () => {
    const now = new Date();
    if (clockEl) {
      clockEl.textContent = now.toISOString().slice(11, 19) + "Z";
    }
    if (nextEl) {
      const remaining = Math.max(0, refreshDeadline - Date.now());
      const totalSeconds = Math.ceil(remaining / 1000);
      const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
      const seconds = String(totalSeconds % 60).padStart(2, "0");
      nextEl.textContent = `${minutes}:${seconds}`;
    }
  };

  tick();
  setInterval(tick, 1000);
}

/**
 * @param {boolean} online
 * @param {string} label
 */
function setConnectionStatus(online, label) {
  const dot = document.getElementById("connection-dot");
  const status = document.getElementById("connection-status");
  const footer = document.getElementById("footer-health");

  if (dot) {
    dot.classList.toggle("online", online);
    dot.classList.toggle("offline", !online);
  }
  if (status) status.textContent = label;
  if (footer) footer.textContent = `Health: ${label}`;
}

/**
 * @param {string|null} message
 */
function setGlobalAlert(message) {
  const alertEl = document.getElementById("global-alert");
  if (!alertEl) return;
  if (!message) {
    alertEl.hidden = true;
    alertEl.textContent = "";
    return;
  }
  alertEl.hidden = false;
  alertEl.textContent = message;
}

async function refreshHealth() {
  try {
    const response = await getHealth();
    const data = response.data || {};
    setConnectionStatus(
      true,
      data.status === "healthy" ? "Online" : data.status || "Online"
    );
    return data;
  } catch (error) {
    setConnectionStatus(false, "Offline");
    console.error("Health check failed:", error);
    return null;
  }
}

/**
 * Refresh weather, severity, and Phase 4 operational modules.
 */
async function refreshOperationalPanels() {
  const weather = await loadWeather();
  const severity = await loadSeverity();
  await loadAlerts();
  await loadOperationsImpact();
  await loadFlightOperations();
  await loadRunwayOperations();
  await loadPhase5bPanels();
  await loadNotifications();

  if (!weather && !severity) {
    setGlobalAlert(
      "AOCC data feeds are currently unavailable. Displayed values may be stale. Retrying on the next refresh cycle."
    );
  } else if (!weather) {
    setGlobalAlert(
      "Live weather feed failed. Severity may use cached observations until the feed recovers."
    );
  } else if (!severity) {
    setGlobalAlert(
      "Severity assessment failed. Weather is live; retry Reassess or wait for auto-refresh."
    );
  } else {
    setGlobalAlert(null);
  }

  refreshDeadline = Date.now() + WEATHER_REFRESH_INTERVAL;
}

async function bootstrap() {
  startClock();
  initChatbot();
  initWeatherControls(async () => {
    await loadSeverity();
    await loadAlerts();
    await loadOperationsImpact();
    await loadFlightOperations();
    await loadRunwayOperations();
    await loadPhase5bPanels();
    await loadNotifications();
    refreshDeadline = Date.now() + WEATHER_REFRESH_INTERVAL;
  });
  initSeverityControls(async () => {
    await loadAlerts();
    await loadOperationsImpact();
    await loadFlightOperations();
    await loadRunwayOperations();
    await loadPhase5bPanels();
    await loadNotifications();
    refreshDeadline = Date.now() + WEATHER_REFRESH_INTERVAL;
  });

  await refreshHealth();
  await refreshOperationalPanels();

  setInterval(async () => {
    await refreshHealth();
    await refreshOperationalPanels();
  }, WEATHER_REFRESH_INTERVAL);
}

document.addEventListener("DOMContentLoaded", () => {
  bootstrap().catch((error) => {
    console.error("Dashboard bootstrap failed:", error);
    setConnectionStatus(false, "Bootstrap error");
    setGlobalAlert(
      "Dashboard failed to initialize. Refresh the page or check that the AOCC API is running."
    );
  });
});
