/**
 * Phase 6A/6B — Incident & Crisis Management panel with create / edit / delete workflow.
 */

import {
  createIncident,
  deleteIncident,
  getIncidentStats,
  getIncidents,
  updateIncident,
} from "./api.js";

const STATUS_OPTIONS = [
  "Open",
  "Assigned",
  "In Progress",
  "Resolved",
  "Closed",
];

/** @type {Map<string, object>} */
const incidentCache = new Map();

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
  if (
    s === "critical" ||
    s === "high" ||
    s === "level 3" ||
    s.includes("level 3")
  ) {
    return "incident-sev-high";
  }
  if (s === "medium" || s === "level 2" || s.includes("level 2")) {
    return "incident-sev-medium";
  }
  return "incident-sev-low";
}

/**
 * @param {string} current
 */
function statusSelectHtml(current) {
  const selected = String(current || "Open");
  const options = STATUS_OPTIONS.map(
    (status) =>
      `<option value="${escapeHtml(status)}"${
        status === selected ? " selected" : ""
      }>${escapeHtml(status)}</option>`
  ).join("");
  return `<select class="incident-status-select" data-action="status" aria-label="Change status">${options}</select>`;
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
  incidentCache.clear();
  items.forEach((item) => {
    if (item?.incident_id) incidentCache.set(item.incident_id, item);
  });

  if (!items.length) {
    body.innerHTML =
      '<tr><td colspan="9" class="table-empty">No incidents recorded.</td></tr>';
    return;
  }

  body.innerHTML = items
    .map((item) => {
      const severity = item.severity || "—";
      const status = item.status || "—";
      const id = item.incident_id || "";
      return `
        <tr data-incident-id="${escapeHtml(id)}">
          <td class="mono">${escapeHtml(id)}</td>
          <td>${escapeHtml(item.incident_type)}</td>
          <td><span class="incident-pill ${severityClass(severity)}">${escapeHtml(severity)}</span></td>
          <td>${escapeHtml(item.airport_area)}</td>
          <td>${escapeHtml(item.assigned_department)}</td>
          <td><span class="incident-pill ${statusClass(status)}">${escapeHtml(status)}</span></td>
          <td class="mono">${escapeHtml(formatDateTime(item.created_time))}</td>
          <td class="mono">${escapeHtml(formatDateTime(item.last_updated))}</td>
          <td>
            <div class="incident-actions">
              ${statusSelectHtml(status)}
              <button type="button" class="btn btn-ghost incident-action-btn" data-action="edit">Edit</button>
              <button type="button" class="btn btn-ghost incident-action-btn is-danger" data-action="delete">Delete</button>
            </div>
          </td>
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
        '<tr><td colspan="9" class="table-empty">Unable to load incidents.</td></tr>';
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

function getModalEls() {
  return {
    modal: document.getElementById("incident-modal"),
    form: document.getElementById("incident-form"),
    mode: document.getElementById("incident-form-mode"),
    editId: document.getElementById("incident-edit-id"),
    title: document.getElementById("incident-modal-title"),
    submit: document.getElementById("incident-form-submit"),
    type: document.getElementById("incident-type"),
    severity: document.getElementById("incident-severity"),
    area: document.getElementById("incident-area"),
    description: document.getElementById("incident-description"),
    status: document.getElementById("incident-status"),
    statusField: document.getElementById("field-incident-status"),
    idDisplay: document.getElementById("incident-id-display"),
    createdDisplay: document.getElementById("incident-created-display"),
  };
}

/**
 * @param {string} fieldKey
 * @param {string} message
 */
function setFieldError(fieldKey, message) {
  const input = document.getElementById(`incident-${fieldKey}`);
  const error = document.getElementById(`error-incident-${fieldKey}`);
  const field = input?.closest(".incident-field");
  if (field) field.classList.toggle("is-invalid", Boolean(message));
  if (error) {
    if (message) {
      error.hidden = false;
      error.textContent = message;
    } else {
      error.hidden = true;
      error.textContent = "";
    }
  }
}

function clearValidation() {
  ["type", "severity", "area", "description"].forEach((key) =>
    setFieldError(key, "")
  );
}

/**
 * @returns {boolean}
 */
function validateCreateForm() {
  const { type, severity, area, description, mode } = getModalEls();
  clearValidation();
  let ok = true;

  if (mode?.value === "create") {
    if (!type?.value.trim()) {
      setFieldError("type", "Incident Type is required.");
      ok = false;
    }
    if (!severity?.value.trim()) {
      setFieldError("severity", "Severity is required.");
      ok = false;
    }
  }

  if (!area?.value.trim()) {
    setFieldError("area", "Airport Area is required.");
    ok = false;
  }
  if (!description?.value.trim()) {
    setFieldError("description", "Description is required.");
    ok = false;
  }

  return ok;
}

/**
 * Ensure a select can show an existing value (for legacy mock areas/types).
 * @param {HTMLSelectElement|null} select
 * @param {string} value
 */
function ensureSelectValue(select, value) {
  if (!select || !value) return;
  const exists = Array.from(select.options).some((opt) => opt.value === value);
  if (!exists) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  select.value = value;
}

function openModal(mode = "create", incident = null) {
  const els = getModalEls();
  if (!els.modal || !els.form) return;

  clearValidation();
  els.mode.value = mode;

  if (mode === "edit" && incident) {
    els.title.textContent = "Update Incident";
    els.submit.textContent = "Save Changes";
    els.editId.value = incident.incident_id || "";
    els.idDisplay.value = incident.incident_id || "";
    els.createdDisplay.value = formatDateTime(incident.created_time);
    els.statusField.hidden = false;
    els.type.disabled = true;
    els.severity.disabled = true;
    ensureSelectValue(els.type, incident.incident_type || "");
    ensureSelectValue(els.severity, incident.severity || "");
    ensureSelectValue(els.area, incident.airport_area || "");
    els.description.value = incident.description || "";
    els.status.value = incident.status || "Open";
  } else {
    els.title.textContent = "Create Incident";
    els.submit.textContent = "Create Incident";
    els.editId.value = "";
    els.idDisplay.value = "Auto-generated";
    els.createdDisplay.value = "Auto-filled on create";
    els.statusField.hidden = true;
    els.type.disabled = false;
    els.severity.disabled = false;
    els.form.reset();
    els.mode.value = "create";
    els.idDisplay.value = "Auto-generated";
    els.createdDisplay.value = "Auto-filled on create";
  }

  els.modal.hidden = false;
  document.body.classList.add("incident-modal-open");
  const focusEl = mode === "edit" ? els.area : els.type;
  focusEl?.focus();
}

function closeModal() {
  const { modal, form, type, severity } = getModalEls();
  if (!modal) return;
  modal.hidden = true;
  document.body.classList.remove("incident-modal-open");
  clearValidation();
  if (type) type.disabled = false;
  if (severity) severity.disabled = false;
  form?.reset();
}

async function refreshIncidentsLive() {
  await Promise.all([loadIncidentStats(), loadIncidents()]);
}

async function handleFormSubmit(event) {
  event.preventDefault();
  const els = getModalEls();
  if (!validateCreateForm()) return;

  const submit = els.submit;
  const previousLabel = submit?.textContent;
  if (submit) {
    submit.disabled = true;
    submit.textContent = els.mode.value === "edit" ? "Saving…" : "Creating…";
  }

  try {
    if (els.mode.value === "edit") {
      await updateIncident(els.editId.value, {
        status: els.status.value,
        description: els.description.value.trim(),
        airport_area: els.area.value.trim(),
      });
    } else {
      await createIncident({
        incident_type: els.type.value.trim(),
        description: els.description.value.trim(),
        severity: els.severity.value.trim(),
        airport_area: els.area.value.trim(),
      });
    }
    closeModal();
    await refreshIncidentsLive();
  } catch (error) {
    console.error("Incident save failed:", error);
    setFieldError(
      "description",
      error?.message || "Unable to save incident. Please try again."
    );
  } finally {
    if (submit) {
      submit.disabled = false;
      submit.textContent = previousLabel || "Create Incident";
    }
  }
}

/**
 * @param {string} incidentId
 * @param {string} nextStatus
 */
async function handleStatusChange(incidentId, nextStatus) {
  try {
    await updateIncident(incidentId, { status: nextStatus });
    await refreshIncidentsLive();
  } catch (error) {
    console.error("Status update failed:", error);
    await refreshIncidentsLive();
    window.alert(error?.message || "Unable to update status.");
  }
}

/**
 * @param {string} incidentId
 */
async function handleDelete(incidentId) {
  const confirmed = window.confirm(
    `Delete incident ${incidentId}? This cannot be undone.`
  );
  if (!confirmed) return;

  try {
    await deleteIncident(incidentId);
    await refreshIncidentsLive();
  } catch (error) {
    console.error("Delete failed:", error);
    window.alert(error?.message || "Unable to delete incident.");
  }
}

/**
 * Wire Create Incident modal, table actions, and form validation.
 */
export function initIncidentControls() {
  const createBtn = document.getElementById("btn-create-incident");
  const els = getModalEls();
  const table = document.getElementById("incident-table");

  createBtn?.addEventListener("click", () => openModal("create"));

  els.modal
    ?.querySelectorAll("[data-incident-modal-close]")
    .forEach((node) => node.addEventListener("click", closeModal));

  els.form?.addEventListener("submit", handleFormSubmit);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && els.modal && !els.modal.hidden) {
      closeModal();
    }
  });

  ["type", "severity", "area", "description"].forEach((key) => {
    const input = document.getElementById(`incident-${key}`);
    input?.addEventListener("input", () => setFieldError(key, ""));
    input?.addEventListener("change", () => setFieldError(key, ""));
  });

  table?.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    if (target.dataset.action !== "status") return;
    const row = target.closest("tr[data-incident-id]");
    const incidentId = row?.getAttribute("data-incident-id");
    if (!incidentId) return;
    handleStatusChange(incidentId, target.value);
  });

  table?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const button = target.closest("button[data-action]");
    if (!button) return;
    const row = button.closest("tr[data-incident-id]");
    const incidentId = row?.getAttribute("data-incident-id");
    if (!incidentId) return;

    const action = button.getAttribute("data-action");
    if (action === "edit") {
      const incident = incidentCache.get(incidentId);
      if (incident) openModal("edit", incident);
      return;
    }
    if (action === "delete") {
      handleDelete(incidentId);
    }
  });
}
