// Minimal observable app state — avoids prop-drilling without a framework.
const state = {};
const subs = new Map();

export function get(key) {
  return state[key];
}

export function set(key, value) {
  state[key] = value;
  const listeners = subs.get(key);
  if (listeners) listeners.forEach((cb) => cb(value));
}

export function subscribe(key, cb) {
  if (!subs.has(key)) subs.set(key, new Set());
  subs.get(key).add(cb);
  return () => subs.get(key).delete(cb);
}
