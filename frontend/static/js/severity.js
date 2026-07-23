/**
 * Severity / alert-level and AOCC recommendations renderer.
 */

import { getSeverity } from "./api.js";

const LEVEL_PILLS = {
  1: "NORMAL",
  2: "CAUTION",
  3: "CRISIS",
};

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
function setSeverityLoading(isLoading) {
  const loader = document.getElementById("severity-loader");
  if (loader) loader.hidden = !isLoading;
  if (isLoading) {
    setStatusChip("severity-status-chip", "loading", "Assessing");
  }
}

/**
 * @param {string|null} message
 */
function setSeverityError(message) {
  const errorEl = document.getElementById("severity-error");
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
export function renderSeverity(data) {
  const level = Number(data.level) || 0;
  const banner = document.getElementById("severity-banner");
  const levelEl = document.getElementById("severity-level");
  const titleEl = document.getElementById("severity-title");
  const descEl = document.getElementById("severity-description");
  const guidanceEl = document.getElementById("severity-guidance");
  const actionEl = document.getElementById("severity-action");
  const factorsEl = document.getElementById("severity-factors");
  const badge = document.getElementById("severity-level-badge");
  const pill = document.getElementById("severity-pill");
  const recoBadge = document.getElementById("reco-level-badge");

  if (levelEl) levelEl.textContent = level ? String(level) : "—";
  if (titleEl) titleEl.textContent = data.title || "Assessment unavailable";
  if (descEl) {
    descEl.textContent = data.description || "—";
    descEl.classList.remove("error-text");
  }
  if (guidanceEl) {
    guidanceEl.textContent =
      data.operational_guidance || "No operational guidance available.";
  }
  if (actionEl) {
    actionEl.textContent =
      data.recommended_action || "No recommended action available.";
  }

  if (banner) {
    banner.classList.remove("level-1", "level-2", "level-3");
    if (level >= 1 && level <= 3) {
      banner.classList.add(`level-${level}`);
    }
  }

  if (badge && data.color) {
    badge.style.borderColor = data.color;
    if (levelEl) levelEl.style.color = data.color;
  }

  if (pill) {
    pill.textContent = LEVEL_PILLS[level] || "STANDBY";
  }

  if (recoBadge) {
    recoBadge.textContent = level ? `LEVEL ${level}` : "LEVEL —";
    if (data.color) {
      recoBadge.style.color = data.color;
      recoBadge.style.borderColor = data.color;
    }
  }

  if (factorsEl) {
    factorsEl.innerHTML = "";
    const factors = Array.isArray(data.contributing_factors)
      ? data.contributing_factors
      : [];
    if (factors.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No contributing factors reported";
      factorsEl.appendChild(li);
    } else {
      factors.forEach((factor) => {
        const li = document.createElement("li");
        li.textContent = factor;
        factorsEl.appendChild(li);
      });
    }
  }
}

/**
 * @param {string} [icao]
 * @returns {Promise<object|null>}
 */
export async function loadSeverity(icao) {
  setSeverityLoading(true);
  setSeverityError(null);

  try {
    const response = await getSeverity(icao);
    renderSeverity(response.data || {});
    setStatusChip("severity-status-chip", "ready", "Assessed");
    return response.data;
  } catch (error) {
    const message =
      error.message ||
      "Unable to assess airport alert level. Please retry shortly.";
    setSeverityError(`Severity assessment unavailable: ${message}`);
    setStatusChip("severity-status-chip", "error", "Error");

    const title = document.getElementById("severity-title");
    const desc = document.getElementById("severity-description");
    const guidance = document.getElementById("severity-guidance");
    const action = document.getElementById("severity-action");
    if (title) title.textContent = "Severity assessment failed";
    if (desc) {
      desc.textContent = "Live operational impact could not be calculated.";
      desc.classList.add("error-text");
    }
    if (guidance) {
      guidance.textContent =
        "Guidance unavailable while severity service is unreachable.";
    }
    if (action) {
      action.textContent =
        "Maintain standard monitoring and retry severity assessment.";
    }
    console.error("Severity load failed:", error);
    return null;
  } finally {
    setSeverityLoading(false);
  }
}

/**
 * @param {() => void} [onLoaded]
 */
export function initSeverityControls(onLoaded) {
  const button = document.getElementById("btn-refresh-severity");
  if (!button) return;

  button.addEventListener("click", async () => {
    button.disabled = true;
    await loadSeverity();
    if (typeof onLoaded === "function") onLoaded();
    button.disabled = false;
  });
}
