// The only module that knows backend URLs/shapes. If the API changes, edit here.
import { getJSON, postJSON } from "./client.js";

export const listSolutions = () => getJSON("/solutions");
export const listProblems = () => getJSON("/problems");
export const listTemplates = () => getJSON("/templates");
export const getTemplate = (id) => getJSON(`/templates/${encodeURIComponent(id)}`);
export const runTemplate = (id, inputs, inputGroup = null) =>
  postJSON(`/templates/${encodeURIComponent(id)}/run`, { inputs, input_group: inputGroup });
export const getCurrentUser = () =>
  getJSON("/_internal/whoami").catch(() => ({ subject: "guest", is_authenticated: false }));
