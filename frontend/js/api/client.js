// Thin fetch wrapper with normalized errors.
import { API_BASE } from "../config.js";

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(API_BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    throw { status: 0, message: "Network error: " + e.message };
  }
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const message = (body && (body.detail || body.message)) || res.statusText || "Request failed";
    throw { status: res.status, message, body };
  }
  return body;
}

export const getJSON = (path) => request(path, { method: "GET" });
export const postJSON = (path, data) =>
  request(path, { method: "POST", body: JSON.stringify(data || {}) });
