/**
 * AOCC AI Assistant chat UI (mock-backed).
 */

import { postChat } from "./api.js";

let sessionId = null;

/**
 * @param {"user"|"assistant"} role
 * @param {string} text
 */
export function appendMessage(role, text) {
  const windowEl = document.getElementById("chat-window");
  if (!windowEl) return;

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;

  const roleEl = document.createElement("p");
  roleEl.className = "chat-role";
  roleEl.textContent = role === "user" ? "Operator" : "AOCC AI";

  const textEl = document.createElement("p");
  textEl.className = "chat-text";
  textEl.textContent = text;

  bubble.appendChild(roleEl);
  bubble.appendChild(textEl);
  windowEl.appendChild(bubble);
  windowEl.scrollTop = windowEl.scrollHeight;
}

/**
 * @param {string} message
 */
export async function sendChatMessage(message) {
  const trimmed = message.trim();
  if (!trimmed) return;

  appendMessage("user", trimmed);

  const submit = document.getElementById("chat-submit");
  const input = document.getElementById("chat-input");
  if (submit) submit.disabled = true;
  if (input) input.disabled = true;

  try {
    const response = await postChat(trimmed, sessionId);
    const data = response.data || {};
    if (data.session_id) sessionId = data.session_id;

    const providerBadge = document.getElementById("chat-provider");
    if (providerBadge && data.provider) {
      providerBadge.textContent = String(data.provider).toUpperCase();
    }

    appendMessage("assistant", data.reply || "No reply received.");
  } catch (error) {
    appendMessage(
      "assistant",
      `Unable to reach the assistant: ${error.message || "unknown error"}`
    );
    console.error("Chat failed:", error);
  } finally {
    if (submit) submit.disabled = false;
    if (input) {
      input.disabled = false;
      input.focus();
    }
  }
}

/**
 * Initialize chat form handlers.
 */
export function initChatbot() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  if (!form || !input) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value;
    input.value = "";
    await sendChatMessage(message);
  });
}
