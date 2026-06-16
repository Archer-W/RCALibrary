# 03 — Architecture

## Layers

```
frontend/ (HTML + vanilla JS + Plotly)         <-- renders forms & report panels
        │  JSON over /api
backend/rcalibrary/
  api/            FastAPI routers (meta, templates, l2, l3)
  solutions/      Solution ABC + registry (L1 concrete; L2/L3 placeholders)
  workflow/       template models, loader, registry, engine, report_builder
  analyzers/      analyzer registry + built-ins (threshold, zscore, passthrough)
  datasources/    DataSource interface + sample provider + Snowflake stub
  reporting/      the ReportPayload/Panel contract returned to the UI
  auth/ audit/    placeholders behind interfaces (deferred features)
templates/        YAML runbooks (data)        data/samples/  sample CSVs (data)
```

Each of `datasources`, `analyzers`, `reporting`, `auth`, `audit` is a
self-contained package fronted by a `base.py` interface. The engine depends only
on interfaces, never concrete providers.

## The shared `Solution` abstraction

`solutions/base.py` defines one interface implemented by all three levels:

- `info() -> SolutionInfo` — metadata + availability for the UI.
- `list_problems() -> list[ProblemDescriptor]` — for L1, the templates; for L2/L3, `[]`.
- `run(RunRequest, principal) -> SolutionResult` — the single entry point.

`SolutionRegistry` maps level → instance. The API **never branches on level**: it
looks the solution up and calls the interface. `FixedWorkflowSolution` is
concrete; `LangGraphSolution` / `CliAgentSolution` return a well-formed
`SolutionResult` with `status="not_implemented"` (never an unhandled error). When
L2/L3 are built, only those two files change.

## Request flow (problem-first; one Level-1 run)

```
UI  GET /api/problems             -> problems, each with the templates available
                                     for it (annotated with approach/level/status)
UI  (user picks a problem, then a template under it)
UI  GET /api/templates/{id}       -> input schema  (UI renders the form)
UI  POST /api/templates/{id}/run  -> { inputs }
        route -> get_principal -> SolutionRegistry.get(1).run(...)
        engine: validate inputs -> data pulls -> analysis -> report_builder
        -> ReportPayload (panels + anomaly overlays) -> audit.emit (no-op)
UI  renders panels: chart panels via Plotly.newPlot(traces, layout);
    stat/table panels as DOM; anomaly summary banner from report.summary
```

`GET /api/problems` groups templates by `template.meta.problem.id` and tags each
with its approach (derived from `solution_level` via the SolutionRegistry). The
3 approach types remain visible as badges + an "About approaches" info page;
`GET /api/solutions` still backs that page.

## Dependency injection (`deps.py`)

Singletons are `lru_cache`-d factories: the datasource registry, analyzer
registry, audit logger, template registry, engine, and solution registry.
`get_principal` returns a guest principal today. Swapping a provider later (real
auth, Snowflake, a DB audit sink) means editing only the relevant factory — route
signatures are untouched.

## Frontend module map

- `core/` — `dom` (element helpers), `store` (pub/sub state), `router` (hash routing).
- `api/` — `client` (fetch + error normalization), `endpoints` (the only file
  that knows backend URLs).
- `forms/` — schema-driven form rendering + validation.
- `panels/` — `registry.renderPanel()` dispatches by `panel.type`; `plotly-base`
  holds the theme; `panel-charts/-kpi/-table/-misc` are the renderers. Adding a
  panel type = one file + one import.
- `report/` — `report-view` lays panels into a 12-column grid; `anomaly-summary`
  builds the banner.
- `views/` — `shell` (header + sidebar: Problems / About approaches / Admin),
  `view-problems` (problem catalog + problem detail listing templates with
  approach badges), `view-runner` (form → report), `view-approaches` (the 3
  approach types + decision-framework summary), `view-admin` (placeholder).
