# RCALibrary

**Automated network-issue Root Cause Analysis (RCA).**

RCALibrary offers three "levels" of RCA solution that a user picks in the UI:

1. **Fixed workflow** — predefined template runbooks. Fill in the inputs; the
   workflow pulls data, runs analysis, highlights anomalies, and renders charts.
   For *deterministic, closed* problems. **(Implemented.)**
2. **Agentic flow (LangGraph)** — AI agents traverse a predefined agent graph
   with heuristic next-step search over vetted MCP tools. For *complex but
   closed* problems. **(Placeholder.)**
3. **CLI super-agent** — a Claude Code-style agent with skills + DB/MCP/API
   access that writes & runs analysis scripts. For *open-ended* problems.
   **(Placeholder.)**

This build implements the **HTML UI + the Level-1 fixed-workflow engine** end to
end. Levels 2 & 3, plus access management and usage logging, are clean
placeholders behind real interfaces so they drop in later without refactoring.

See **[docs/02-decision-framework.md](docs/02-decision-framework.md)** for *which
solution to use in which scenario* — the practical heart of this project.

---

## Quickstart

```bash
pip install -r requirements.txt        # FastAPI, pandas, pydantic, pyyaml, ...
./run.sh                                # uvicorn on http://localhost:8000
```

Open <http://localhost:8000/>. The app is **problem-first**: pick a problem
(**Generic Demo Problem**), then the **template** available for it (**Generic
Demo RCA**, badged *Fixed Workflow*), fill the inputs, and click **Run
analysis**. The report shows two KPI cards, a latency line chart (with anomaly
markers + an SLO threshold line), an error bar chart, and a table of breaching
samples. Interactive API docs live at `/docs`.

> **Charts offline:** Plotly.js is loaded from `frontend/vendor/plotly.min.js`
> (offline-first, matching NetSkills). If that file is absent, chart panels show
> a graceful message; everything else still works. To vendor it:
> `curl -fsSL -o frontend/vendor/plotly.min.js https://cdn.plot.ly/plotly-2.35.2.min.js`

## Repository map

| Path | What it is |
|---|---|
| [`backend/rcalibrary/`](backend/rcalibrary/) | FastAPI app + the Level-1 engine |
| [`backend/rcalibrary/solutions/`](backend/rcalibrary/solutions/) | the shared `Solution` abstraction (L1 concrete; L2/L3 placeholders) |
| [`backend/rcalibrary/workflow/`](backend/rcalibrary/workflow/) | template schema, loader, engine, report builder |
| [`backend/rcalibrary/datasources/`](backend/rcalibrary/datasources/) | data-source layer (sample CSV now, Snowflake stub) |
| [`backend/rcalibrary/analyzers/`](backend/rcalibrary/analyzers/) | analyzer registry + built-ins |
| [`templates/`](templates/) | YAML template runbooks (data, not code) |
| [`data/samples/`](data/samples/) | sample CSVs the demo runs against |
| [`frontend/`](frontend/) | HTML/CSS/vanilla-JS UI + the Plotly panel library |
| [`tests/`](tests/) | unit + API + e2e tests |
| [`docs/`](docs/) | overview, decision framework, architecture, guides |

## For another agent / contributor

This repo is the **generic framework**. Real RCA problems, templates, custom
analysis, real data, and authentication are built in a **separate private
use-case repo** that consumes this one as a git submodule — without editing any
framework file. **Start at [AGENTS.md](AGENTS.md).**

## Docs
- [AGENTS.md](AGENTS.md) — start here: the two-agent ownership/locking model
- [01 — Overview](docs/01-overview.md)
- [02 — Decision framework (which solution when)](docs/02-decision-framework.md)
- [03 — Architecture](docs/03-architecture.md)
- [04 — Authoring templates](docs/04-authoring-templates.md)
- [05 — Data sources](docs/05-data-sources.md)
- [06 — Testing](docs/06-testing.md)
- [07 — Building real use cases](docs/07-building-use-cases.md)
- [08 — Collaboration, repos & branching](docs/08-collaboration-and-branching.md)
- [09 — Structure ↔ data/analysis handoff (co-located skeletons)](docs/09-usecase-handoff.md)
- [examples/usecase-starter/](examples/usecase-starter/) — copy-paste scaffold for a separate use-case repo
- [templates/ana.rca.netcare-voc-trend/](templates/ana.rca.netcare-voc-trend/) — first real problem (skeleton + handoff brief)

## Tests

```bash
pip install -r requirements.txt
pytest                 # pyproject puts backend/ on the path automatically
```

## Roadmap
- L2 LangGraph agentic flow; L3 CLI super-agent (consumes the sibling NetSkills skills)
- Snowflake data source (drop-in behind the existing data-source interface)
- Real access management + usage logging (interfaces already seamed)
- One-click escalation L1 → L2 → L3, carrying context forward
