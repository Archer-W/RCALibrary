// The only module that knows backend URLs/shapes. If the API changes, edit here.
import { getJSON, postJSON } from "./client.js";

export const getMeta = () => getJSON("/meta").catch(() => ({ map_tiles: false }));
export const listSolutions = () => getJSON("/solutions");
export const listProblems = () => getJSON("/problems");
export const listTemplates = () => getJSON("/templates");
export const getTemplate = (id) => getJSON(`/templates/${encodeURIComponent(id)}`);
export const runTemplate = (id, inputs, inputGroup = null, refresh = false) =>
  postJSON(`/templates/${encodeURIComponent(id)}/run`, { inputs, input_group: inputGroup, refresh });
// Compute one optional library panel on demand.
export const addPanel = (id, panelId, inputs, inputGroup = null) =>
  postJSON(`/templates/${encodeURIComponent(id)}/panel`, {
    panel_id: panelId, inputs, input_group: inputGroup,
  });
// One turn of the AI "build a panel" chat. body: {message, session_id, inputs, input_group}.
export const aiPanelChat = (id, body) =>
  postJSON(`/templates/${encodeURIComponent(id)}/panel/ai`, body);
// Persist the customized report under the search key (re-search loads it).
export const saveReport = (id, inputs, inputGroup, report) =>
  postJSON(`/templates/${encodeURIComponent(id)}/save`, {
    inputs, input_group: inputGroup, report,
  });
export const getCurrentUser = () =>
  getJSON("/_internal/whoami").catch(() => ({ subject: "guest", is_authenticated: false }));
