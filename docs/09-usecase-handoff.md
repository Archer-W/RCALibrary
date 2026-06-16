# 09 — Structure ↔ data/analysis handoff (co-located skeletons)

This describes the collaboration pattern used when a real use case is **kept in
this repo** (rather than a separate private repo — that's [docs/08](08-collaboration-and-branching.md)).
The work is split **within the same template** along the data boundary.

## The split

| Block in `template.yaml` | Owner | What it is |
|---|---|---|
| `meta` (incl. `problem`) | structure agent | id, name, the problem definition |
| `inputs` | structure agent | the form fields |
| `report` | structure agent | the panel layout (which charts/tables, their encodings) |
| `data_pulls` | **data agent** | the real data requests (Snowflake datasets / SQL / params / filters) |
| `analysis` | **data agent** | which analyzers run + their params (analyzers themselves are plugins) |

Plus: the **data agent** ships analyzer functions, the real data-source provider,
and (optionally) the auth provider as **plugins** (`RCA_PLUGINS`) — see
[docs/07](07-building-use-cases.md).

## How the boundary is marked (in-file locking)

Each co-located skeleton's YAML carries banner comments so ownership is obvious in
the file itself:

```yaml
# --- STRUCTURE (framework/structure agent owns this block) ---
inputs: [...]
# --- DATA  (data agent owns this block) — TODO ---
data_pulls: [...]
# --- ANALYSIS  (data agent owns this block) — TODO ---
analysis: [...]
```

A sibling **`IMPLEMENTATION.md`** in the template folder is the handoff brief: it
states the **contract** (the `data_pull` ids + expected columns, and the analysis
ids + what each must return) so either agent can change their block without
breaking the other. Changing the *other* agent's block — e.g. a `data_pull` id or
a column the `report` depends on — requires coordination.

> Trade-off vs the separate-repo model: co-location is simpler but both agents
> edit one repo, so there's **no hard one-way visibility**. The lock is by
> convention (banners + `IMPLEMENTATION.md`) and review (CODEOWNERS), not by repo
> isolation. Use [docs/08](08-collaboration-and-branching.md) when the use case
> must stay private from the framework agent.

## Skeleton lifecycle

1. **Structure agent** scaffolds the skeleton: full `meta`/`inputs`/`report`, and
   **placeholder** `data_pulls` (`source: snowflake`, placeholder datasets) +
   `analysis` (the built-in `passthrough` so it's valid and visible now). Writes
   `IMPLEMENTATION.md`.
2. The template **loads and appears in the UI immediately**; **running it errors**
   (no real data/analysis yet) — expected.
3. **Data agent** implements the data source + analyzers (plugins), fills the
   `data_pulls` + `analysis` blocks, and (coordinating) updates any `report`
   `encoding` key that depends on a real summary field.

## Resilience: placeholders never crash the app

Template discovery is **resilient** ([`workflow/registry.py`](../backend/rcalibrary/workflow/registry.py)):
a template that can't load — e.g. it references an analyzer whose plugin isn't on
`RCA_PLUGINS` in this deployment — is **skipped with a logged warning** and
recorded in `registry.errors()`, instead of aborting startup. So:
- a skeleton using `passthrough` loads everywhere;
- once it references a plugin analyzer, deployments **with** that plugin show the
  template and deployments **without** it simply omit it — neither crashes.

Keep the plugin loaded in every deployment that ships the template.

## Worked example

[`templates/ana.rca.netcare-voc-trend/`](../templates/ana.rca.netcare-voc-trend/)
— "NetCare VoC Trend Triage": structure is done; `data_pulls` + `analysis` are
placeholders; [`IMPLEMENTATION.md`](../templates/ana.rca.netcare-voc-trend/IMPLEMENTATION.md)
is the data agent's brief.
