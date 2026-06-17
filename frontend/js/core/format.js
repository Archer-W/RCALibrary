// Tiny, safe text formatting shared by forms and panels.

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Inline: escape, then **bold**.
export function mdInline(s) {
  return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

// Block: inline formatting + newlines become <br>.
export function mdBlock(s) {
  return mdInline(s).replace(/\n/g, "<br>");
}
