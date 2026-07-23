/**
 * Weather panel renderer for the AOCC dashboard.
 */

import { getWeather } from "./api.js";

const ICONS = {
  clear: `<svg class="wx-icon" viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="12" fill="currentColor"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M32 8v6M32 50v6M8 32h6M50 32h6M14 14l4 4M46 46l4 4M50 14l-4 4M18 46l-4 4"/></g></svg>`,
  cloudy: `<svg class="wx-icon" viewBox="0 0 64 64" fill="currentColor"><path d="M44 46H18a12 12 0 0 1-1-24 14 14 0 0 1 27-5 10 10 0 0 1 0 29z" opacity="0.9"/></svg>`,
  rain: `<svg class="wx-icon" viewBox="0 0 64 64"><path d="M44 34H18a12 12 0 0 1-1-24 14 14 0 0 1 27-5 10 10 0 0 1 0 29z" fill="currentColor"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M22 42v8M32 44v8M42 42v8"/></g></svg>`,
  thunder: `<svg class="wx-icon" viewBox="0 0 64 64"><path d="M44 30H18a12 12 0 0 1-1-24 14 14 0 0 1 27-5 10 10 0 0 1 0 29z" fill="currentColor"/><path d="M30 34l-4 12h8l-6 14 14-18h-8l6-8z" fill="#fbbf24"/></svg>`,
  fog: `<svg class="wx-icon" viewBox="0 0 64 64" stroke="currentColor" stroke-width="3" stroke-linecap="round" fill="none"><path d="M12 24h40M16 32h32M14 40h36M20 48h24"/></svg>`,
  snow: `<svg class="wx-icon" viewBox="0 0 64 64"><path d="M44 30H18a12 12 0 0 1-1-24 14 14 0 0 1 27-5 10 10 0 0 1 0 29z" fill="currentColor"/><g fill="currentColor"><circle cx="22" cy="44" r="2"/><circle cx="32" cy="48" r="2"/><circle cx="42" cy="44" r="2"/></g></svg>`,
  wind: `<svg class="wx-icon" viewBox="0 0 64 64" stroke="currentColor" stroke-width="3" stroke-linecap="round" fill="none"><path d="M10 24h30a8 8 0 1 0-8-8M10 34h38a8 8 0 1 1-8 8M10 44h24a8 8 0 1 1-8 8"/></svg>`,
  default: `<svg class="wx-icon" viewBox="0 0 64 64" fill="currentColor"><circle cx="32" cy="32" r="14" opacity="0.85"/></svg>`,
};

/**
 * @param {string|Date|null|undefined} value
 * @returns {string}
 */
export function formatDateTime(value) {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

/**
 * @param {number|string|null|undefined} value
 * @param {number} [digits]
 */
function formatNumber(value, digits = 1) {
  const num = Number(value);
  if (Number.isNaN(num)) return "--";
  return num.toFixed(digits);
}

/**
 * @param {string} description
 * @returns {keyof typeof ICONS}
 */
function resolveWeatherIcon(description) {
  const text = (description || "").toLowerCase();
  if (!text) return "default";
  if (/(thunder|storm|lightning)/.test(text)) return "thunder";
  if (/(snow|flurr|sleet|ice)/.test(text)) return "snow";
  if (/(fog|mist|haze)/.test(text)) return "fog";
  if (/(rain|drizzle|shower|precip)/.test(text)) return "rain";
  if (/(wind|gale|breeze)/.test(text)) return "wind";
  if (/(cloud|overcast)/.test(text)) return "cloudy";
  if (/(clear|sunny|fair)/.test(text)) return "clear";
  return "default";
}

/**
 * @param {string} chipId
 * @param {"idle"|"loading"|"ready"|"error"} state
 * @param {string} [label]
 */
function setStatusChip(chipId, state, label) {
  const chip = document.getElementById(chipId);
  if (!chip) return;
  chip.classList.remove("loading", "ready", "error");
  if (state !== "idle") chip.classList.add(state);
  chip.textContent = label || state;
}

/**
 * @param {boolean} isLoading
 */
function setWeatherLoading(isLoading) {
  const loader = document.getElementById("weather-loader");
  const panel = document.querySelector(".weather-panel");
  if (loader) loader.hidden = !isLoading;
  panel?.classList.toggle("is-loading", isLoading);
  if (isLoading) {
    setStatusChip("weather-status-chip", "loading", "Loading");
  }
}

/**
 * @param {string|null} message
 */
function setWeatherError(message) {
  const errorEl = document.getElementById("weather-error");
  if (!errorEl) return;
  if (!message) {
    errorEl.hidden = true;
    errorEl.textContent = "";
    return;
  }
  errorEl.hidden = false;
  errorEl.textContent = message;
}

/**
 * @param {object} data
 */
export function renderWeather(data) {
  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  const description = data.weather_description || "—";
  const source = (data.source || "mock").toUpperCase();
  const lastUpdated = formatDateTime(data.last_updated || data.timestamp);

  setText("weather-icao", data.icao_code || "VIDP");
  setText("weather-description", description);
  setText("weather-description-card", description);
  setText("weather-temperature", formatNumber(data.temperature, 1));
  setText("weather-temperature-card", formatNumber(data.temperature, 1));
  setText("weather-humidity", formatNumber(data.humidity, 1));
  setText("weather-pressure", formatNumber(data.pressure, 1));
  setText("weather-visibility", formatNumber(data.visibility, 0));
  setText("weather-wind-speed", formatNumber(data.wind_speed, 1));
  setText("weather-wind-direction", data.wind_direction || "--");
  setText("weather-rainfall", formatNumber(data.rainfall, 1));
  setText("weather-observation-time", formatDateTime(data.observation_time));
  setText("weather-last-updated", lastUpdated);

  const iconWrap = document.getElementById("weather-icon");
  if (iconWrap) {
    iconWrap.innerHTML = ICONS[resolveWeatherIcon(description)] || ICONS.default;
  }

  const sourceBadge = document.getElementById("weather-source");
  if (sourceBadge) sourceBadge.textContent = source;

  // Airport Information panel
  setText("info-name", data.airport_name || "—");
  setText("info-icao", data.icao_code || "—");
  setText("info-location", data.location || "—");
  setText("info-last-updated", lastUpdated);
  const infoSource = document.getElementById("info-source");
  if (infoSource) infoSource.textContent = source;

  if (data.airport_name || data.icao_code) {
    const headerAirport = document.getElementById("header-airport");
    if (headerAirport && data.airport_name) {
      headerAirport.textContent = `${data.icao_code} · ${data.airport_name}`;
    }
  }

  if (data.location) {
    const headerLocation = document.getElementById("header-location");
    if (headerLocation) headerLocation.textContent = data.location;
  }

  const desc = document.getElementById("weather-description");
  desc?.classList.remove("error-text");
}

/**
 * @param {string} [icao]
 * @returns {Promise<object|null>}
 */
export async function loadWeather(icao) {
  setWeatherLoading(true);
  setWeatherError(null);

  try {
    const response = await getWeather(icao);
    renderWeather(response.data || {});
    setStatusChip("weather-status-chip", "ready", "Live");
    return response.data;
  } catch (error) {
    const message =
      error.message ||
      "Unable to retrieve live weather. Check AOCC connectivity and try again.";
    setWeatherError(`Weather feed unavailable: ${message}`);
    setStatusChip("weather-status-chip", "error", "Error");
    const desc = document.getElementById("weather-description");
    if (desc) {
      desc.textContent = "Weather data unavailable";
      desc.classList.add("error-text");
    }
    console.error("Weather load failed:", error);
    return null;
  } finally {
    setWeatherLoading(false);
  }
}

/**
 * @param {() => void} [onLoaded]
 */
export function initWeatherControls(onLoaded) {
  const button = document.getElementById("btn-refresh-weather");
  if (!button) return;

  button.addEventListener("click", async () => {
    button.disabled = true;
    await loadWeather();
    if (typeof onLoaded === "function") onLoaded();
    button.disabled = false;
  });
}
