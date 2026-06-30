# Integration handoff — AI panel builder + gpt-oss LLM routing

**Audience:** the data/LLM agent whose branch has diverged from `HEAD` (it connected
real Snowflake data). This folder describes **everything the structure agent added on
top of the current committed git version (`HEAD`)** so you can port it onto your branch
**without a blind `git merge`** — much of `HEAD` (analyzers, template YAML, data) differs
on your side.

## What was built (3 layers)
1. **Customizable panels** — add optional panels from a per-problem library (computed on
   demand), remove / drag-reorder / snap-resize, and save the report (file cache).
2. **AI panel mode (simulated)** — an "Ask AI" chat that turns a free-text request into a
   predefined panel; ships a **free/offline deterministic** engine (no LLM, no cost).
3. **Real LLM routing (gpt-oss)** — `LLMToolEngine` + an OpenAI-compatible client. Built
   and **verified offline with a fake LLM**; you connect your **local gpt-oss endpoint**
   with a few env vars. **No LangGraph.**

If your branch already has layers 1–2, you only need **layer 3** (`04-integration-steps.md`
marks which files belong to which layer).

## How to use this folder
| file | what it gives you |
|---|---|
| `01-requirements.md` | the feature + the key decisions (and why) |
| `02-architecture.md` | how it fits together (interfaces, the swap seam) |
| `03-changeset.md` | **the per-file delta from `HEAD`**, in three buckets (below) |
| `04-integration-steps.md` | the ordered port checklist + conflict handling |
| `05-connect-gpt-oss.md` | wire your local gpt-oss endpoint (env vars, server flags, test) |
| `06-verification.md` | verify offline + a live smoke against your endpoint |
| `ai-panel-feature.patch` | `git diff HEAD` of the whole delta (CSVs excluded) — reference / `git apply` attempt |

## Legend (used throughout `03`/`04`)
- **✅ new file → drop in.** Copy as-is; it doesn't exist on `HEAD`, so it won't conflict.
- **⚠️ shared file → merge the block.** An additive edit to a file you may also have
  changed; apply the quoted block.
- **✋ likely-diverged file → re-apply the *intent*.** You rewrote this for real data
  (`usecases/netcare_voc.py`, the template YAML); the doc explains the *semantic* change
  so you re-apply it to your version, not the literal lines.
- **🗑 demo-only.** Dummy CSVs / generators — keep your real data; ignore these.

## The one-paragraph summary
The AI engine never generates code: it picks one **predefined library panel** and fills a
few **parameters**, via a stable tool surface (`backend/rcalibrary/ai/tools.py`). Two
engines implement the same `AIPanelEngine` interface — `SimulatedAIEngine` (default,
offline) and `LLMToolEngine` (your gpt-oss). You switch with `RCA_AI_PROVIDER`. The whole
loop is tested offline with a `FakeLLMClient`; the only unrun code is the thin
`OpenAICompatLLMClient` adapter, which you exercise the moment you point it at your endpoint.
