# Template: `ana.rca.netcare-voc-trend`

**Problem:** NetCare VoC Trend Triage (`netcare.voc-trend`, domain *Customer Care / VoC*).

Triage a NetCare Voice-of-Customer (VoC) trend with automated RCA. A VoC trend is
a rise in customer-reported service issues — complaints surfaced through
customer-care calls and troubleshooting requests — and this workflow helps
pinpoint what is driving the increase.

## Status

| Part | Owner | State |
|---|---|---|
| Problem + template **structure** (meta, inputs, report layout) | structure agent | **done** |
| **Snowflake data pulls** (real datasets / SQL) | data agent | **TODO** |
| **Analysis logic** (real analyzers) | data agent | **TODO** |

The skeleton loads and appears in the UI now (using the built-in `passthrough`
analyzer as a stand-in). **Running it errors until the data agent wires Snowflake
+ analyzers** — that's expected.

➡ **Data agent: start with [IMPLEMENTATION.md](IMPLEMENTATION.md).**
