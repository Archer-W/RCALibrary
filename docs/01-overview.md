# 01 — Overview

RCALibrary automates **network-issue Root Cause Analysis**. It is organized
around three solution *levels* of increasing autonomy and cost. The UI is
**problem-first**: a user selects the problem they want to solve, then picks a
template available for it (each template is badged with its approach/level).

## The three levels

| Level | Name | Use it when | Status |
|---|---|---|---|
| 1 | **Fixed workflow** | the troubleshooting steps are known and fixed | **implemented** |
| 2 | **Agentic flow (LangGraph)** | the steps are known but the *path* is data-dependent | placeholder |
| 3 | **CLI super-agent** | you can't enumerate the steps; the agent must improvise | placeholder |

The deep-dive on choosing a level is in
[02-decision-framework.md](02-decision-framework.md).

## What Level 1 does (this build)

A **template** is a YAML runbook with five sections — `meta`, `inputs`,
`data_pulls`, `analysis`, `report`. Running a template:

1. validates the user's inputs against the template's declared fields,
2. pulls each dataset from the active data source (sample CSVs now; Snowflake
   later) — source-agnostic, parameterized,
3. runs the declared analysis steps (threshold + statistical anomaly detection,
   or any registered Python analyzer),
4. assembles a **report** of panels (KPI cards, charts with anomaly overlays,
   tables) and returns it to the UI, which renders the charts with Plotly.js.

The result is **deterministic and reproducible**: same inputs → same report.

## Design goals

- **Uniform template representation** so non-developers can author runbooks in
  YAML, with an escape hatch to Python analyzers for non-trivial logic.
- **A reusable visualization-panel library** the backend composes reports from
  declaratively.
- **Clean seams** for the things deferred in this build (Levels 2 & 3, real auth,
  usage logging, Snowflake) so they plug in without refactoring.
