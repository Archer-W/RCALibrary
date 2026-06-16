// Hash-based router + view manager. Problem-first navigation.
//   #/problems            -> problem catalog (default)
//   #/problem/<id>        -> templates available for a problem
//   #/run/<templateId>    -> the template runner (form + report)
//   #/approaches          -> about the approach types + decision framework
//   #/admin               -> admin / usage placeholder
import { clear } from "./dom.js";
import { renderShell } from "../views/shell.js";
import * as problemsView from "../views/view-problems.js";
import * as runnerView from "../views/view-runner.js";
import * as approachesView from "../views/view-approaches.js";
import { renderAdmin } from "../views/view-admin.js";

let mainEl = null;
let cleanup = null;

function parse() {
  const hash = location.hash || "#/problems";
  const parts = hash.replace(/^#\//, "").split("/");
  return { section: parts[0] || "problems", param: parts[1] ? decodeURIComponent(parts[1]) : null };
}

async function route() {
  if (cleanup) {
    try { cleanup(); } catch { /* ignore */ }
    cleanup = null;
  }
  clear(mainEl);
  const { section, param } = parse();
  let result;
  switch (section) {
    case "problem": result = await problemsView.render(mainEl, { problemId: param }); break;
    case "run": result = runnerView.render(mainEl, { templateId: param }); break;
    case "approaches": result = approachesView.render(mainEl); break;
    case "admin": result = renderAdmin(mainEl); break;
    case "problems":
    default: result = await problemsView.render(mainEl, {});
  }
  cleanup = result && result.destroy ? result.destroy : null;
}

export function startRouter(root) {
  mainEl = renderShell(root);
  window.addEventListener("hashchange", route);
  route();
}
