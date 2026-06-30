// The "Ask AI to build a panel" chat modal (multi-turn). The AI engine parses a
// free-text request, picks a predefined library panel, fills params, and builds it
// — or asks a clarifying question / says it can't. This modal owns the thread + the
// session id and stays open for refinement; built panels are inserted into the
// report via opts.onPanel. The engine is server-side (simulated by default,
// swappable to a real LLM) — see docs/11-ai-panel-builder.md.
//
// opts = {
//   send(message, sessionId) -> Promise<AIPanelResponse>,  // one chat turn
//   onPanel(panelPayload),                                  // insert a built panel
// }
// Node-12 safe: no optional chaining / nullish coalescing.
import { el } from "../core/dom.js";
import { mdBlock } from "../core/format.js";

export function aiChatModal(opts) {
  let sessionId = null;
  let busy = false;

  const onKey = (e) => { if (e.key === "Escape") close(); };
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };

  const thread = el("div", { class: "ai-chat-thread" });

  function bubble(role, node) {
    const b = el("div", { class: "ai-msg ai-msg-" + role }, node);
    thread.appendChild(b);
    thread.scrollTop = thread.scrollHeight;
    return b;
  }
  // Replies may contain **bold**; mdBlock escapes then formats (safe).
  function rich(role, text) {
    return bubble(role, el("div", { class: "ai-msg-body", html: mdBlock(text || "") }));
  }

  const input = el("textarea", {
    class: "ai-chat-input", rows: "2",
    placeholder: 'Describe a panel, e.g. "call volume from 2026-05-01 to 2026-05-20, hourly"',
    onKeydown: (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } },
  });
  const sendBtn = el("button", { class: "btn btn-primary", type: "button", onClick: () => send() }, "Send");

  async function send() {
    const text = (input.value || "").trim();
    if (!text || busy) return;
    rich("user", text);
    input.value = "";
    busy = true; sendBtn.disabled = true;
    const thinking = bubble("ai", el("div", { class: "ai-msg-body ai-thinking" }, "Thinking…"));
    try {
      const resp = await opts.send(text, sessionId);
      sessionId = resp.session_id || sessionId;
      thinking.remove();
      rich("ai", resp.reply || "");
      if (resp.status === "panel" && resp.panel) {
        try { opts.onPanel(resp.panel); } catch (err) { /* insertion is best-effort */ }
        bubble("ai", el("div", { class: "ai-msg-note" }, "✓ Added to the report"));
      }
    } catch (e) {
      thinking.remove();
      bubble("ai", el("div", { class: "ai-msg-body ai-msg-error" },
        "Something went wrong: " + (e && e.message ? e.message : e)));
    } finally {
      busy = false; sendBtn.disabled = false; input.focus();
    }
  }

  const overlay = el("div",
    { class: "modal-overlay", onClick: (e) => { if (e.target === overlay) close(); } },
    el("div", { class: "modal ai-chat", role: "dialog" },
      el("div", { class: "ai-chat-head" },
        el("div", { class: "ai-chat-title" }, "✨ Ask AI to build a panel"),
        el("button", { class: "btn btn-link ai-chat-close", type: "button", onClick: () => close() }, "Done")),
      el("div", { class: "ai-chat-hint" },
        "I build panels from this report's predefined templates & data. I'll ask if I need a detail, and say so if I can't."),
      thread,
      el("div", { class: "ai-chat-compose" }, input, sendBtn)));
  document.body.appendChild(overlay);
  document.addEventListener("keydown", onKey);

  rich("ai", "What would you like to see? For example: **call volume from 2026-05-01 "
    + "to 2026-05-20 at hourly granularity**, or **summarize the symptom types from "
    + "the call transcripts**.");
  setTimeout(() => input.focus(), 0);
}
