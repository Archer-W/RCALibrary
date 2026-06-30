# 07 — Building real use cases (for the use-case agent)

This guide is for the **use-case agent**: you build the real RCA problems,
templates, analysis, data connectivity, report composition, and authentication
**on top of the framework, without editing any framework file**.

> Mental model: the framework is a *library you consume*, not code you edit. You
> add your own files (templates, data, a plugin package, optional custom panel
> JS) and point the framework at them with `RCA_*` environment variables. If you
> ever feel you must edit a file under `backend/rcalibrary/` or `frontend/`,
> stop — that's a request to the framework agent (see "Need a framework change?").

See also: [docs/08-collaboration-and-branching.md](08-collaboration-and-branching.md)
for the repo/submodule setup, and [examples/usecase-starter/](../examples/usecase-starter/)
for a copy-paste scaffold.

---

## 0. Setup (once)

Your private repo includes the framework as a git submodule and adds your own
package + dirs. A minimal layout:

```
my-rca-usecases/                 # YOUR private repo
├── framework/                   # git submodule -> RCALibrary (pinned to a tag)
├── usecase/                     # YOUR python package (plugins)
│   ├── __init__.py
│   ├── plugins.py               # the module listed in RCA_PLUGINS
│   ├── analyzers.py
│   ├── datasource_snowflake.py
│   └── auth_provider.py
├── templates/                   # YOUR RCA problems + templates  (RCA_TEMPLATES_DIR)
│   └── ran.throughput-degradation/template.yaml
├── data/samples/                # optional offline sample data    (RCA_SAMPLES_DIR)
├── frontend-ext/                # optional custom panel JS         (RCA_FRONTEND_EXT_DIR)
│   └── custom.js
├── .env
└── run.sh
```

Run the combined app (framework code + your extensions):

```bash
# PYTHONPATH includes the framework's backend AND your package
export PYTHONPATH="framework/backend:."
export RCA_TEMPLATES_DIR="./templates"
export RCA_SAMPLES_DIR="./data/samples"
export RCA_FRONTEND_DIR="./framework/frontend"
export RCA_FRONTEND_EXT_DIR="./frontend-ext"     # optional
export RCA_PLUGINS="usecase.plugins"             # your plugin module(s)
export RCA_DATASOURCE="sample"                    # or "snowflake" once implemented
uvicorn rcalibrary.main:app --reload --port 8000
```

That's the whole integration: **env vars + your files**. Nothing in `framework/`
changes.

---

## 1. Add an RCA problem + a template

Problems are **derived from template metadata** — a problem appears once a
template declares it. Drop a folder in your `RCA_TEMPLATES_DIR`:

`templates/ran.throughput-degradation/template.yaml`
```yaml
meta:
  id: ran.cell-throughput
  name: "Cell throughput triage"
  description: "Pull PM counters for a cell and flag KPI breaches."
  version: "0.1.0"
  solution_level: 1
  tags: [ran, kpi]
  problem:
    id: ran.throughput-degradation        # templates sharing this id group together
    name: "RAN throughput degradation"
    description: "Subscriber-impacting throughput drop on a cell."
    domain: "RAN"

inputs:
  - { name: cell_id, label: "Cell ID", type: string, required: true,
      validation: { pattern: "^[A-Z0-9-]+$" } }
  - { name: lookback_hours, label: "Lookback (hours)", type: int, default: 24,
      validation: { min: 1, max: 168 } }
  - { name: prb_util_threshold, label: "PRB util % threshold", type: float, default: 85 }

data_pulls:
  - id: pm
    query:
      dataset: cell_pm_counters             # logical name your data source resolves
      params: { cell_id: "${input.cell_id}", lookback_hours: "${input.lookback_hours}" }
      filters: [{ column: cell_id, op: eq, value: "${input.cell_id}" }]
    columns: [ts, cell_id, prb_util, dl_thpt_mbps, bler]

analysis:
  - id: prb_breaches
    analyzer: threshold_breach              # a built-in; or your custom analyzer name
    inputs: { dataset: pm }
    params: { column: prb_util, op: gt, threshold: "${input.prb_util_threshold}", severity: high }

report:
  title: "Cell throughput report"
  panels:
    - { id: kpi, type: stat, title: "PRB breaches", analysis_ref: prb_breaches,
        encoding: { value: breach_count } }
    - id: thpt
      type: line
      title: "DL throughput"
      dataset: pm
      encoding: { x: ts, y: dl_thpt_mbps }
      options: { x_title: Time, y_title: "Mbps" }
    - id: prb
      type: line
      title: "PRB utilization"
      dataset: pm
      analysis_ref: prb_breaches            # anomalies + threshold line overlaid here
      encoding: { x: ts, y: prb_util }
      options: { x_title: Time, y_title: "PRB %" }
```

Full schema + the YAML `${input.*}` quoting gotcha: [docs/04-authoring-templates.md](04-authoring-templates.md).

---

## 2. Custom analysis (an analyzer plugin)

The built-ins are `threshold_breach`, `zscore_anomaly`, `passthrough`. For
anything else, write a function and register it with `@analyzer`. Put it in your
package and make sure your plugin module imports it.

`usecase/analyzers.py`
```python
from rcalibrary.analyzers import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult

@analyzer("ran_kpi_correlation")
def ran_kpi_correlation(ctx: AnalysisContext) -> AnalysisResult:
    df = ctx.dataset                      # pandas DataFrame for the bound dataset
    p = ctx.params                        # resolved params (${input.*} substituted)
    bad = df[(df["bler"] > p.get("bler_max", 10)) & (df["dl_thpt_mbps"] < p.get("thpt_min", 5))]
    return AnalysisResult(
        summary={"correlated_points": int(len(bad))},
        anomalies=[
            {"index": int(i), "column": "dl_thpt_mbps", "value": float(v),
             "severity": "high", "reason": "high BLER + low throughput"}
            for i, v in bad["dl_thpt_mbps"].items()
        ],
        table=bad.to_dict("records"),
    )
```

`AnalysisResult` fields: `summary` (scalars **and** structured objects →
`stat`/`fields`/`timeseries` panels), `anomalies`
(`index`/`column`/`value`/`severity`/`reason` → markers on charts + the summary
banner), `annotations` (`{"type":"hline","y":...}` → threshold lines), `table`
(rows → `table` panels; a cell may be a `{value, tone}` object to render a colored
badge). Reference it from a template by its registered name.

**Chaining & multiple sources** (for multi-step workflows): besides `ctx.dataset`
(this step's primary frame) and `ctx.params`, an analyzer gets:
- `ctx.inputs` — validated inputs (incl. `_input_group` for grouped templates).
- `ctx.results` — `{step_id: AnalysisResult}` of **earlier** steps, so a later
  step can build on a confirmed entity (e.g. `ctx.results["lookup"].summary["anchor"]`).
- `ctx.datasets` — `{pull_id: DataFrame}` for **every** data pull, so one analyzer
  can join more than one source.

Steps in `analysis:` run in order, and a panel can `visible_when:` gate on any
step's summary key (e.g. only render later panels when an earlier step `found`
something). See [docs/04 — Panel reference](04-authoring-templates.md#panel-reference).

**AI synthesis skills (optional).** When the data is free text needing AI to digest
it (e.g. call transcripts), register a `@skill("name")`
([`rcalibrary.ai.skills`](../backend/rcalibrary/ai/skills/)) and call it from an
analyzer. Skills are the only place an LLM runs in production; the shipped ones are
free/offline deterministic stand-ins (the LLM agent swaps in a real impl under the
same name). The AI add-panel chat reaches skills through the MCP tool server. See
**[11-ai-panel-builder.md](11-ai-panel-builder.md)**.

---

## 3. Real data (a data-source plugin)

Templates reference **logical datasets** and never carry connection details, so
swapping the data source requires no template change. Implement the `DataSource`
interface, register it, and select it with `RCA_DATASOURCE`.

`usecase/datasource_snowflake.py`
```python
import pandas as pd
from rcalibrary.datasources.base import DataPullRequest, DataSource, FetchResult

class SnowflakeProvider(DataSource):
    name = "snowflake"                    # RCA_DATASOURCE=snowflake selects this

    def __init__(self, account, user, password, warehouse, database, schema, role=None):
        self._cfg = dict(account=account, user=user, password=password,
                         warehouse=warehouse, database=database, schema=schema, role=role)

    def fetch(self, request: DataPullRequest) -> FetchResult:
        import snowflake.connector                       # add to your requirements
        conn = snowflake.connector.connect(**self._cfg)
        try:
            cur = conn.cursor()
            sql, binds = self._compile(request)          # map dataset/filters -> parameterized SQL
            cur.execute(sql, binds)                       # named binds — never string-concat
            frame = cur.fetch_pandas_all()
        finally:
            conn.close()
        return FetchResult(frame=frame)

    def health(self) -> dict:
        return {"name": self.name, "ready": True}

    def _compile(self, request: DataPullRequest):
        # dataset -> fully-qualified view; filters -> parameterized WHERE; request.params -> binds
        ...
```

Tips:
- The framework ships a **stub** at `framework/backend/rcalibrary/datasources/snowflake.py`
  documenting the intended mapping — copy it as your starting point (don't edit it
  in place; it's framework-owned).
- Read credentials from env in your `plugins.py` (below), not from code.
- The sample provider's `${input.lookback_hours}` + `ts` window convention is just
  a sample-data nicety; your real provider implements its own filtering.

---

## 4. Compose reports with the visualization library

You drive the framework's panels **declaratively from the template's `report`
section** — no JS needed. Built-in panel types and how each is driven:

| `type` | Purpose | `encoding` keys | Notes |
|---|---|---|---|
| `line` | time-series | `x`, `y`, `series?` | anomalies → red markers; `annotations` hline → dashed threshold |
| `bar` | categorical / time bars | `x`, `y`, `series?` | grouped via `series` |
| `scatter` | point cloud | `x`, `y`, `series?` | |
| `stat` | single KPI card | `value`, `state`, `badge`, `detail`, `sub`, `alert` (summary keys) | `options.unit`; `state` colors it; `badge` = highlighted pill; `detail` = prominent line; `alert` = red badge |
| `stat_group` | several stat cards in one panel | — (`options.stats[]` mini-specs) | each item reads its own `analysis_ref` + keys; per-item `visible_when` |
| `table` | data grid | `columns` | rows from the analysis `table`, else the dataset; a cell `{value, tone}` → colored badge |
| `fields` | grid of labeled boxes | `value` (→ `{items, notice}`) | one box per value; per-box `state` tint |
| `timeseries` | interactive multi-series | `value` (→ `TimeseriesData`) | client-side USID/granularity toggles; `overlay_ref` adds toggleable bands |
| `map` | interactive site map | `value` (→ `MapData`) | lat/lon markers color-coded by status, clickable ticket tags, side detail, layer toggles, auto-fit; muted street basemap or offline blank-canvas scatter, switchable at runtime / via `RCA_MAP_TILES` |
| `heatmap` | 2-D intensity | `x`, `y`, `value` | pivots the dataset |
| `pie` | distribution pie/donut | `labels`, `values` | from analysis `table` (else dataset); `options.hole` |
| `flow` | workflow / process diagram | — (static `options.stages`) | left→right stages `{title, steps:[...]}`; multi-step stage = parallel; optional `options.caption` |
| `markdown` | static / analysis text | `value?` | `summary[value]` else `options.text` |

Anomaly overlays + the summary banner come **for free** when a panel sets
`analysis_ref` to an analysis that returns `anomalies`/`annotations`. Panel width
is auto (`stat`→third; `line`/`table`/`fields`/`timeseries`→full; `bar`→half) or
set `width: full|half|third`; panels in one row are equal height.

**Color, gating & overlays** (full reference in
[docs/04](04-authoring-templates.md#panel-reference)): `stat`/`fields` use
`state` ∈ `good|warn|bad|neutral`; `table` badges use `tone` ∈
`red|amber|green|blue|grey|purple`. `visible_when: {ref, key}` renders a panel
only when an analysis summary key is truthy; `overlay_ref` lets a `timeseries`
panel show another step's toggleable overlay.

### Optional: a custom panel type (advanced)
Prefer composing from the built-ins. If you genuinely need a new visual, you can
register one client-side **without editing framework JS**:

`frontend-ext/custom.js` (served at `/ext` when `RCA_FRONTEND_EXT_DIR` is set)
```js
// window.RCA = { registerPanel, el, plotly: { draw, baseLayout, baseConfig } }
window.RCA.registerPanel("sankey", (panel, bodyEl) => {
  window.RCA.plotly.draw(bodyEl, panel.traces, window.RCA.plotly.baseLayout(panel.layout));
});
```
Your backend then emits panels with `type: "sankey"` (the framework's
`report_builder` only special-cases the built-in types, so a custom type needs
its `traces`/`layout` supplied by a custom analyzer or a small report post-step —
ask the framework agent if you need a backend hook). **If a panel is broadly
useful, request it as a built-in** so every use case benefits.

---

## 5. Authentication

The framework ships an anonymous provider and the seam to replace it. Implement
`AuthProvider` and install it from your plugin — no route changes needed (every
protected route already depends on `get_principal`).

`usecase/auth_provider.py`
```python
from rcalibrary.auth.base import Principal

class ApiKeyAuthProvider:
    def __init__(self, valid_keys: dict[str, list[str]]):
        self._keys = valid_keys           # api_key -> roles

    def authenticate(self, request=None) -> Principal:
        # NOTE: wire request access via your own FastAPI dependency if you need
        # headers; the framework calls authenticate() per request.
        # Minimal example returns an authenticated principal:
        return Principal(subject="svc", roles=["operator"], is_authenticated=True)
```

For header/token-based auth you will typically also add a FastAPI dependency in
your plugin and (if needed) request a small framework hook to pass the request
into `authenticate()`. The `Principal` (subject/roles/is_authenticated) flows into
the audit log and is available to `require_roles`-style checks later.

---

## 6. The plugin module (wires it all together)

`usecase/plugins.py` — this is the module you list in `RCA_PLUGINS`. Importing it
registers everything:
```python
import os
from rcalibrary import extensions

# 1) analyzers self-register on import
from . import analyzers  # noqa: F401

# 2) data source
from .datasource_snowflake import SnowflakeProvider
if os.getenv("SNOWFLAKE_ACCOUNT"):
    extensions.register_datasource(SnowflakeProvider(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"], warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"], schema=os.environ["SNOWFLAKE_SCHEMA"],
    ))

# 3) auth
from .auth_provider import ApiKeyAuthProvider
extensions.set_auth_provider(ApiKeyAuthProvider(valid_keys={}))
```

---

## 7. Configuration reference (`RCA_*`)

| Env var | Default | Meaning |
|---|---|---|
| `RCA_DATASOURCE` | `sample` | active data source name |
| `RCA_TEMPLATES_DIR` | framework `templates/` | where templates are discovered |
| `RCA_SAMPLES_DIR` | framework `data/samples/` | sample-CSV root |
| `RCA_FRONTEND_DIR` | framework `frontend/` | static UI served at `/` |
| `RCA_FRONTEND_EXT_DIR` | (unset) | extra static dir served at `/ext` (custom panel JS) |
| `RCA_PLUGINS` | (empty) | comma-separated import paths of your plugin modules |
| `RCA_AUDIT_MODE` | `noop` | `noop` or `file` |
| `RCA_MAP_TILES` | `false` | map panels use online OpenStreetMap tiles (needs internet) vs the offline blank-canvas default |
| `RCA_HOST` / `RCA_PORT` | `0.0.0.0` / `8000` | server bind |

---

## 8. Test your use case

Use the framework's `TestClient` against your env. Example:
```python
import os
os.environ["RCA_TEMPLATES_DIR"] = "./templates"
os.environ["RCA_PLUGINS"] = "usecase.plugins"
from fastapi.testclient import TestClient
from rcalibrary.main import app

def test_my_template_runs():
    c = TestClient(app)
    problems = c.get("/api/problems").json()
    assert any(p["id"] == "ran.throughput-degradation" for p in problems)
    r = c.post("/api/templates/ran.cell-throughput/run",
               json={"inputs": {"cell_id": "C-001", "lookback_hours": 24, "prb_util_threshold": 85}})
    assert r.status_code == 200
```
Validate templates early — invalid YAML / unknown analyzers / bad references fail
at **startup** with a clear message.

---

## 9. Need a framework change?

If you need a new built-in panel type, a new built-in analyzer, a template-schema
field, or a backend hook (e.g. request-aware auth), **request it from the
framework agent** rather than editing `framework/`. The framework agent ships it
in a new tagged version; you bump the submodule. See
[docs/08-collaboration-and-branching.md](08-collaboration-and-branching.md).
