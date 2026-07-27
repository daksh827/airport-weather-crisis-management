/**
 * Shared Fetch API client for AOCC endpoints.
 * All responses are expected in the envelope:
 * { success: boolean, message: string, data: object }
 */

const DEFAULT_HEADERS = {
  Accept: "application/json",
};

/**
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<{success: boolean, message: string, data: any}>}
 */
export async function apiRequest(path, options = {}) {
  const config = {
    ...options,
    headers: {
      ...DEFAULT_HEADERS,
      ...(options.headers || {}),
    },
  };

  let response;
  try {
    response = await fetch(path, config);
  } catch (networkError) {
    const error = new Error("Network error — unable to reach AOCC API");
    error.cause = networkError;
    error.success = false;
    throw error;
  }

  let payload;
  try {
    payload = await response.json();
  } catch {
    const error = new Error(`Invalid JSON response from ${path}`);
    error.status = response.status;
    throw error;
  }

  if (!response.ok || payload.success === false) {
    const error = new Error(payload.message || `Request failed (${response.status})`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export async function getHealth() {
  return apiRequest("/health");
}

export async function getWeather(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/weather${query}`);
}

export async function getSeverity(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/severity${query}`);
}

export async function getCurrentAlert(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/alerts/current${query}`);
}

export async function getAlertHistory(limit = 50) {
  return apiRequest(`/api/alerts/history?limit=${encodeURIComponent(limit)}`);
}

export async function getOperationsImpact(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/operations/impact${query}`);
}

export async function getNotifications(limit = 30) {
  return apiRequest(`/api/notifications?limit=${encodeURIComponent(limit)}`);
}

export async function getFlightOperations(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/operations/flights${query}`);
}

export async function getRunwayOperations(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/operations/runway${query}`);
}

export async function getTerminalOperations(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/operations/terminal${query}`);
}

export async function getGroundOperations(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/operations/ground${query}`);
}

export async function getAirportKpis(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/operations/kpi${query}`);
}

export async function getRecommendations(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/recommendations${query}`);
}

export async function getIncidents(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/incidents${query}`);
}

export async function getIncidentStats(icao) {
  const query = icao ? `?icao=${encodeURIComponent(icao)}` : "";
  return apiRequest(`/api/incidents/stats${query}`);
}

/**
 * @param {{incident_type: string, description: string, severity: string, airport_area: string, icao_code?: string}} payload
 */
export async function createIncident(payload) {
  return apiRequest("/api/incidents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * @param {string} incidentId
 * @param {{status?: string, description?: string, airport_area?: string}} payload
 */
export async function updateIncident(incidentId, payload) {
  return apiRequest(`/api/incidents/${encodeURIComponent(incidentId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * @param {string} incidentId
 */
export async function deleteIncident(incidentId) {
  return apiRequest(`/api/incidents/${encodeURIComponent(incidentId)}`, {
    method: "DELETE",
  });
}

/**
 * @param {string} message
 * @param {string|null} [sessionId]
 */
export async function postChat(message, sessionId = null) {
  return apiRequest("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });
}

/**
 * @param {File} file
 */
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest("/api/upload", {
    method: "POST",
    body: formData,
  });
}
