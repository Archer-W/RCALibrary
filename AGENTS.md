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

The durable split is **by what you touch, not by repo**: the *structure /
framework agent* owns the generic platform and the **structure** of templates;
the *data / analysis agent* owns the **real data + analysis** and authentication.

| | **Structure / framework agent** (you) | **Data / analysis agent** |
|---|---|---|
| Owns | the generic platform + template **structure** | the real **data + analysis** |
| Deliverables | engine, UI, viz library, data-source/analyzer/auth **interfaces** + plugin seams, docs; **problem definitions + template structure** (`meta`, `inputs`, `report` layout) | real **data sources** (Snowflake/DB), real **analyzers**, the `data_pulls` + `analysis` blocks of templates, **authentication** |

**Where use-case artifacts live — two patterns:**
1. **Co-located skeleton (in this repo).** The structure agent scaffolds a
   problem/template skeleton here; the data agent fills the `data_pulls` +
   `analysis` blocks (and ships analyzers/data-source/auth as plugins). Locking is
   **in-file** — ownership-banner comments in the YAML — plus a per-template
   `IMPLEMENTATION.md` handoff brief. Used by
   [`templates/ana.rca.netcare-voc-trend/`](templates/ana.rca.netcare-voc-trend/).
   See [docs/09-usecase-handoff.md](docs/09-usecase-handoff.md). (Trade-off: both
   agents edit one repo, so there is no hard one-way visibility — the lock is by
   convention + review, not by repo isolation.)
2. **Separate private repo (submodule).** For fully-private use cases, the data
   agent works in their own repo with this framework as a **git submodule** and
   never edits this repo (true one-way isolation). See
   [docs/08-collaboration-and-branching.md](docs/08-collaboration-and-branching.md).

Either way, **framework code never imports use-case code** — analyzers, data
sources, and auth are discovered via the extension API + config, so a deployment
missing a plugin simply **skips** templates that need it (it never crashes).

## Ownership & locking (what each agent may touch)

**Structure / framework agent — owns (in this repo):**
- `backend/rcalibrary/**`, `frontend/**` — all framework code, the UI, the viz library
- `docs/**`, `AGENTS.md`, `CODEOWNERS`, `pyproject.toml`, `requirements.txt`, `run.sh`, `examples/**`
- each template's **structure** blocks — `meta` (incl. the `problem` definition), `inputs`, `report` (panel layout)

**Data / analysis agent — owns:**
- each template's `data_pulls` and `analysis` blocks (marked with `# ===== … =====` banners in the YAML)
- analyzer functions, real data-source providers, the auth provider — as **plugins** (`RCA_PLUGINS`), co-located here or in a separate private repo
- credentials/queries live in env or the plugin, **never hard-coded** in templates

Changing the *other* agent's block — e.g. a `data_pull` id or column the `report`
depends on — requires coordination (the YAML banners + `IMPLEMENTATION.md` spell
out the contract).

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
- **Structure↔data/analysis handoff (co-located skeletons)** → [docs/09-usecase-handoff.md](docs/09-usecase-handoff.md)
- Repo/branch model & ownership → [docs/08-collaboration-and-branching.md](docs/08-collaboration-and-branching.md)
- Which RCA solution level for which problem → [docs/02-decision-framework.md](docs/02-decision-framework.md)
- A copy-paste starter for a separate use-case repo → [examples/usecase-starter/](examples/usecase-starter/)
- First real problem (worked skeleton + handoff) → [templates/ana.rca.netcare-voc-trend/](templates/ana.rca.netcare-voc-trend/)

## Run it
```bash
pip install -r requirements.txt
./run.sh            # http://localhost:8000  (RCA_PORT to change port)
pytest              # test suite
```
