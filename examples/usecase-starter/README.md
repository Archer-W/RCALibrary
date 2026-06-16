# Use-case starter

A copy-paste scaffold for the **use-case agent's private repo**. It extends the
RCALibrary framework **without editing any framework file** — via a plugin
package, your own templates/data dirs, optional custom panel JS, and `RCA_*` env
vars.

> This folder lives inside the framework repo as **reference only**. Copy it into
> your own private repo (which embeds the framework as a submodule). See
> [../../docs/08-collaboration-and-branching.md](../../docs/08-collaboration-and-branching.md).

## Bootstrap your repo

```bash
mkdir my-rca-usecases && cd my-rca-usecases && git init
git submodule add https://github.com/Archer-W/RCALibrary framework
cd framework && git checkout v0.1.0 && cd ..        # pin to a released tag
cp -r framework/examples/usecase-starter/. .         # this scaffold
pip install -r framework/requirements.txt
git add -A && git commit -m "Init use-case repo on RCALibrary v0.1.0"
```

## Run (offline against the bundled sample data)

```bash
./run.sh            # http://localhost:8000  -> open the "RAN throughput degradation" problem
```

`run.sh` sets `PYTHONPATH="framework/backend:."`, points `RCA_TEMPLATES_DIR`,
`RCA_SAMPLES_DIR`, `RCA_FRONTEND_DIR`, `RCA_FRONTEND_EXT_DIR` at this repo, and
loads `RCA_PLUGINS=usecase.plugins`.

## What's inside

| Path | What to do with it |
|---|---|
| `usecase/plugins.py` | the module in `RCA_PLUGINS`; wires analyzers + data source + auth |
| `usecase/analyzers.py` | example custom analyzer (`ran_kpi_correlation`) |
| `usecase/datasource_snowflake.py` | flesh out `fetch()` for real data, then `RCA_DATASOURCE=snowflake` |
| `usecase/auth_provider.py` | replace with your real auth |
| `templates/…/template.yaml` | your RCA problems + templates |
| `data/samples/…` | offline sample data (delete once on real data) |
| `frontend-ext/custom.js` | optional custom panel registrations |
| `tests/test_usecase.py` | example test against the framework's TestClient |

Full guide: [../../docs/07-building-use-cases.md](../../docs/07-building-use-cases.md).
