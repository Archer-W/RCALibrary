# 02 — Decision Framework: which RCA solution for which scenario

This is the practical heart of RCALibrary. Use it to decide whether a given
network-RCA problem belongs to **Level 1 (fixed workflow)**, **Level 2 (LangGraph
agentic flow)**, or **Level 3 (CLI super-agent)**.

## One-line rule per level

- **L1 — Fixed workflow:** use when you can *write the exact steps in advance*
  and they don't change run to run. The template **is** the runbook.
- **L2 — LangGraph flow:** use when the *steps are known but the path isn't* — a
  bounded set of tools/checks, but which to run next depends on the data.
- **L3 — CLI super-agent:** use when you *can't enumerate the steps at all* —
  novel, cross-domain, or exploratory problems where the agent must write new
  analysis on the fly.

## Comparison matrix

| Dimension | L1 Fixed workflow | L2 LangGraph flow | L3 CLI super-agent |
|---|---|---|---|
| **Problem shape** | deterministic, closed | complex but **closed** | open-ended, novel |
| **Path through steps** | fixed (template-defined) | dynamic over a fixed graph | fully emergent |
| **Data variability** | low (known schemas/queries) | medium (known sources) | high (arbitrary joins) |
| **Reproducibility / audit** | highest (byte-stable) | medium (path logged, stochastic) | lowest (needs transcript capture) |
| **Latency** | seconds | tens of seconds | minutes |
| **Cost** | negligible | moderate (LLM per node) | high (long sessions) |
| **Trust / safety** | high (no arbitrary exec) | medium (vetted MCP tools) | needs guardrails (arbitrary exec) |
| **Maintenance** | low/template, but N templates | graph + tools + heuristics | skills + access governance |
| **Who authors** | NOC/SME writes YAML | ML/platform eng designs graph | platform eng curates skills |
| **Primary failure mode** | silent miss; staleness | wrong branch; premature stop | hallucinated cause; runaway cost |

## Network-RCA examples per level

**Level 1 — fixed workflow** (named entity + time window in, known queries, fixed
thresholds):
- Single-cell / gNB **throughput-degradation triage** (PRB utilization, RRC
  users, DL/UL throughput, BLER vs. thresholds).
- **Interface / link error-rate check** (CRC/input errors, discards, utilization).
- **PON ONT optical-budget check** (Rx/Tx power vs. the budget table).
- **Post-maintenance health snapshot** (fixed KPI list, before/after delta).
- **Top-N alarms / KPIs for a site** (rank + table + bar chart).
- **N4/PFCP association sanity check** (association state, session counts,
  heartbeat misses).

**Level 2 — LangGraph flow** (all checks pre-built, but no single fixed sequence
fits every instance):
- **Multi-domain degradation correlation** (RAN → transport → core branching by
  what each check shows).
- **Intermittent latency spikes across a region** (iterate candidates, prune
  clean branches, deepen on suspicious ones).
- **Handover-failure root cause** (select which cause to test next from counter
  signatures).
- **Capacity-vs-fault disambiguation** (sequence growth-trend, fault-log,
  config-change checks by the data).

**Level 3 — CLI super-agent** (must author queries/analysis on the fly):
- "This region is weird and **no runbook explains it**."
- **Novel post-upgrade / new-feature failures** with no existing template.
- **Cross-layer + cross-vendor incidents** needing a join nobody pre-modeled.
- Exploratory "**what changed?**" investigations — which may *produce* a new L1
  template or L2 tool as a byproduct.

## Decision checklist (stop at the first "yes")

1. **Can I write the exact steps as a fixed sequence that won't change between
   runs?** → **Level 1.**
2. **Are all needed checks/tools already built, and is the only uncertainty
   *which to run next*?** → **Level 2.**
3. **Does solving this require writing new analysis / joining sources nobody
   pre-modeled?** → **Level 3.**

**Cross-cutting overrides:**
- Need byte-stable, auditable, customer-facing reports → prefer **L1**; treat
  L2/L3 output as advisory until a human confirms.
- Tight latency/cost budget, run thousands of times/day → push toward **L1**.
- One-off or rare investigation → **L3** is fine even if expensive.

## Decision tree

```
New RCA problem
   │
   ├─ Steps fully known & fixed? ───────────────── yes ─▶ LEVEL 1 (fixed workflow)
   │                                   no
   │                                    │
   ├─ Tools known, only the PATH is data-dependent? ─ yes ─▶ LEVEL 2 (LangGraph)
   │                                   no
   │                                    │
   └─ Must author new analysis / open exploration? ─ yes ─▶ LEVEL 3 (CLI super-agent)
```

## Escalation and hybrids (opinionated)

- **Default to escalation, not selection.** Start at L1. If the fixed workflow
  returns "no anomaly found" or "inconclusive," offer **escalate to L2**; if L2's
  search doesn't converge, offer **escalate to L3**. This keeps the common case
  cheap and fast and reserves expensive reasoning for genuinely hard problems.
- **Escalation carries context forward.** Pass the prior level's inputs, the data
  already pulled, and the findings into the next level as seed context (the shared
  `Solution` interface's `RunRequest.context` is built for this).
- **The escalation loop feeds the library.** An L3 investigation that converges
  on a repeatable procedure should be **distilled into a new L1 template** (or an
  L2 tool). Over time work shifts leftward — cheaper, faster, more auditable.
- **Hybrids:** L1 templates are reusable *atoms*. An L2 node can invoke an L1
  template as one tool; an L3 session can call an L1 template or an L2 flow as a
  sub-tool. Build L1 templates to be callable both from the UI and programmatically.
