# AGENTS.md — read this first

This file orients any AI agent (or developer) working on RCALibrary. **Read it
before editing anything.**

## What this repo is

RCALibrary is the **generic framework / platform** for automated network-issue
Root Cause Analysis: the template engine, the HTML UI, the reusable Plotly
visualization library, and the **interfaces** for data sources, analyzers, and
authentication. It ships one demo problem/template so it runs end to end out of
the box.

It is intentionally **use-case-agnostic**. Real RCA problems, real templates,
real data connectivity, custom analysis, and real authentication live in a
**separate use-case repo** that consumes this framework.

## Two agents, two responsibilities

| | **Framework agent** (this repo) | **Use-case agent** (separate private repo) |
|---|---|---|
| Owns | The generic platform | The real, specific use cases |
| Deliverables | Engine, UI, viz library, data-source/analyzer/auth **interfaces**, plugin seams, docs | RCA **problems + templates**, custom **analyzers**, real **data sources** (Snowflake/DB), report **composition**, **authentication** |
| Repo | `RCALibrary` (public) | their private repo, with this repo as a **git submodule** |
| Visibility | Cannot read the use-case repo | Can read/clone this framework repo |

You are the **framework agent**. The use-case agent extends the framework
**without editing any file in this repo** — via plugins + config + their own
template/data dirs. See [docs/08-collaboration-and-branching.md](docs/08-collaboration-and-branching.md).

## Ownership & locking (what each agent may touch)

**Framework-owned — only the framework agent edits these (in this repo):**
- `backend/rcalibrary/**` — all framework code (engine, registries, API, interfaces, plugin loader)
- `frontend/**` — the UI and the Plotly panel library
- `docs/**`, `AGENTS.md`, `CODEOWNERS`, `pyproject.toml`, `requirements.txt`, `run.sh`
- `examples/**` — reference scaffolding for the use-case agent
- `templates/ana.rca.generic-demo/**`, `data/samples/ana.rca.generic-demo/**` — the demo only

**Use-case-owned — created in the SEPARATE use-case repo, never here:**
- their RCA problems + templates (their own `templates/` dir → `RCA_TEMPLATES_DIR`)
- their sample/real data (their `data/` dir → `RCA_SAMPLES_DIR`, or a real data source)
- their plugin package: custom analyzers, data sources, auth provider (→ `RCA_PLUGINS`)
- their custom panel JS, if any (→ `RCA_FRONTEND_EXT_DIR`, served at `/ext`)

The lock is enforced structurally: **framework code never imports use-case code**
— it only discovers it through config + the extension API. So the two repos never
edit each other's files.

## How the use-case agent extends the framework (no framework edits)

| To add… | Mechanism | Doc |
|---|---|---|
| an RCA problem + template | drop a `template.yaml` in their `RCA_TEMPLATES_DIR` (problems are derived from `meta.problem`) | [docs/04](docs/04-authoring-templates.md), [docs/07](docs/07-building-use-cases.md) |
| custom analysis | `@analyzer("name")` in a plugin module listed in `RCA_PLUGINS` | [docs/07](docs/07-building-use-cases.md) |
| real data (Snowflake/DB) | implement `DataSource`, `extensions.register_datasource(...)`, set `RCA_DATASOURCE` | [docs/05](docs/05-data-sources.md), [docs/07](docs/07-building-use-cases.md) |
| charts / reports | reference the built-in panel types from the template; optional custom panel via `window.RCA.registerPanel` + `/ext` | [docs/07](docs/07-building-use-cases.md) |
| authentication | implement `AuthProvider`, `extensions.set_auth_provider(...)` in a plugin | [docs/07](docs/07-building-use-cases.md) |

The public extension API is [`backend/rcalibrary/extensions.py`](backend/rcalibrary/extensions.py).

## Stability contract (framework agent's promise)

These are the stable interfaces the use-case repo depends on; the framework agent
changes them only with a new version tag + a note in the changelog:
- Template YAML schema ([`workflow/models.py`](backend/rcalibrary/workflow/models.py))
- Analyzer contract (`AnalysisContext` / `AnalysisResult`)
- `DataSource` interface ([`datasources/base.py`](backend/rcalibrary/datasources/base.py))
- `AuthProvider` / `Principal` ([`auth/base.py`](backend/rcalibrary/auth/base.py))
- Report/panel payload ([`reporting/contract.py`](backend/rcalibrary/reporting/contract.py)) + the JS panel types
- The extension API ([`extensions.py`](backend/rcalibrary/extensions.py)) + the `RCA_*` env vars

The framework is tagged (e.g. `v0.1.0`); the use-case repo pins the submodule to a
tag. **Need a framework change (new panel type, new built-in analyzer, schema
field)?** That's a request to the framework agent — don't fork-edit the framework.

## Where to start
- Framework internals → [docs/03-architecture.md](docs/03-architecture.md)
- Building real use cases → [docs/07-building-use-cases.md](docs/07-building-use-cases.md)
- Repo/branch model & ownership → [docs/08-collaboration-and-branching.md](docs/08-collaboration-and-branching.md)
- Which RCA solution level for which problem → [docs/02-decision-framework.md](docs/02-decision-framework.md)
- A copy-paste starter for the use-case repo → [examples/usecase-starter/](examples/usecase-starter/)

## Run it
```bash
pip install -r requirements.txt
./run.sh            # http://localhost:8000  (RCA_PORT to change port)
pytest              # 31 tests
```
