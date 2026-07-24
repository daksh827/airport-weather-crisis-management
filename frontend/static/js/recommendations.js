/**
 * Phase 5C — AI Operations Decision Support recommendations panel.
 */

import { getRecommendations } from "./api.js";

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
 * @param {string} priority
 */
function priorityClass(priority) {
  const p = String(priority || "").toLowerCase();
  if (p === "high") return "priority-high";
  if (p === "medium") return "priority-medium";
  return "priority-low";
}

/**
 * @param {string} decision
 */
function decisionClass(decision) {
  const d = String(decision || "").toLowerCase();
  if (d.includes("emergency")) return "decision-emergency";
  if (d.includes("critical")) return "decision-critical";
  if (d.includes("severe")) return "decision-severe";
  if (d.includes("restrictions")) return "decision-restricted";
  return "decision-normal";
}

/**
 * @param {object} data
 */
export function renderRecommendations(data) {
  const decisionEl = document.getElementById("overall-airport-decision");
  const listEl = document.getElementById("recommendation-cards");
  if (!decisionEl || !listEl) return;

  const decision = data.overall_decision || "Airport Operating Normally";
  decisionEl.textContent = decision;
  decisionEl.classList.remove(
    "decision-normal",
    "decision-restricted",
    "decision-severe",
    "decision-critical",
    "decision-emergency"
  );
  decisionEl.classList.add(decisionClass(decision));

  const items = Array.isArray(data.recommendations) ? data.recommendations : [];
  if (!items.length) {
    listEl.innerHTML =
      '<p class="decision-empty">No operational recommendations at this time.</p>';
    return;
  }

  listEl.innerHTML = items
    .map((item) => {
      const priority = escapeHtml(item.priority || "Low");
      const status = escapeHtml(item.status || "Recommended");
      const department = escapeHtml(item.department || "AOCC");
      const title = escapeHtml(item.title || "Operational Action");
      const description = escapeHtml(item.description || "");
      const pClass = priorityClass(item.priority);
      return `
        <article class="decision-card">
          <div class="decision-card-head">
            <span class="priority-badge ${pClass}">${priority}</span>
            <span class="decision-dept">${department}</span>
          </div>
          <h3 class="decision-card-title">${title}</h3>
          <p class="decision-card-desc">${description}</p>
          <div class="decision-card-foot">
            <span class="decision-status">${status}</span>
          </div>
        </article>
      `;
    })
    .join("");
}

export async function loadRecommendations() {
  const panel = document.getElementById("decision-support-panel");
  panel?.classList.add("is-loading");
  try {
    const response = await getRecommendations();
    renderRecommendations(response.data || {});
    return response.data;
  } catch (error) {
    console.error("Recommendations load failed:", error);
    const decisionEl = document.getElementById("overall-airport-decision");
    const listEl = document.getElementById("recommendation-cards");
    if (decisionEl) {
      decisionEl.textContent = "Decision support unavailable";
      decisionEl.classList.remove(
        "decision-normal",
        "decision-restricted",
        "decision-severe",
        "decision-critical",
        "decision-emergency"
      );
    }
    if (listEl) {
      listEl.innerHTML =
        '<p class="decision-empty">Unable to load operational recommendations.</p>';
    }
    return null;
  } finally {
    panel?.classList.remove("is-loading");
  }
}
