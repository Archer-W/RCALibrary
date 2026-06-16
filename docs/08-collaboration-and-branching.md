# 08 — Collaboration, repos & branching

This describes how the **framework agent** and the **use-case agent** work without
stepping on each other, given the required one-way boundary:

> The use-case agent can read/clone the framework. The framework agent **cannot**
> read the use-case repo. Real data, real RCA logic, and credentials must stay
> out of the public framework repo.

## Two repos (not two branches)

Branches in a single repo are mutually readable, so they can't give a one-way
boundary. We therefore use **two repositories**:

```
┌─────────────────────────────┐         git submodule (pinned to a tag)
│  RCALibrary (this repo)      │  ◀──────────────────────────────────────┐
│  PUBLIC · framework agent    │                                          │
│  main + version tags         │                                          │
└─────────────────────────────┘                                          │
                                                                          │
┌─────────────────────────────────────────────────────────────────────┐ │
│  my-rca-usecases (separate)                                           │ │
│  PRIVATE · use-case agent                                            ─┼─┘
│  framework/ = submodule  +  usecase/ + templates/ + data/ + ...      │
└─────────────────────────────────────────────────────────────────────┘
```

- **Framework repo** (`RCALibrary`, public): the framework agent owns `main` and
  cuts version tags. The use-case agent has **read** access only; never pushes here.
- **Use-case repo** (private, the use-case agent's): contains everything specific.
  It embeds the framework as a **git submodule** pinned to a tag. The framework
  agent has **no access** — true one-way isolation.

## Set up the use-case repo (use-case agent)

```bash
mkdir my-rca-usecases && cd my-rca-usecases && git init
git submodule add https://github.com/Archer-W/RCALibrary framework
cd framework && git checkout v0.1.0 && cd ..      # pin to a released tag
git add .gitmodules framework && git commit -m "Add RCALibrary framework v0.1.0 as submodule"
# then copy examples/usecase-starter/ from the framework as your starting point:
cp -r framework/examples/usecase-starter/. .
```

Clone later (submodules need a flag):
```bash
git clone --recurse-submodules <your-private-repo-url>
# or, after a normal clone:  git submodule update --init --recursive
```

## Ownership lock (who may edit what)

| Path / artifact | Owner | The other agent may… |
|---|---|---|
| `RCALibrary/backend/rcalibrary/**` | framework | read only (consume) |
| `RCALibrary/frontend/**` | framework | read only (consume) |
| `RCALibrary/docs/**`, `AGENTS.md`, `examples/**` | framework | read only |
| `RCALibrary` demo template + sample data | framework | read only (copy as reference) |
| use-case repo: `usecase/**` (plugins) | use-case | (framework can't see it) |
| use-case repo: `templates/**`, `data/**` | use-case | (framework can't see it) |
| use-case repo: `frontend-ext/**`, `.env`, `run.sh` | use-case | (framework can't see it) |

Enforcement:
- The framework repo restricts write access to the framework agent; `CODEOWNERS`
  routes any PR that touches framework paths to the framework agent for review.
- The framework **never imports** use-case code — it discovers it only via config
  + the extension API (see [docs/07](07-building-use-cases.md)). So neither side
  edits the other's files.

## Taking framework updates (use-case agent)

The framework is pinned by submodule commit/tag, so updates are deliberate:
```bash
cd framework && git fetch --tags && git checkout v0.2.0 && cd ..
git add framework && git commit -m "Bump framework to v0.2.0"
# re-run your tests against the new version
```
Pinning to a **tag** (not a moving branch) means the framework agent's work in
progress never breaks the use-case build.

## Versioning & the stability contract (framework agent)

- Cut a tag for every release: `git tag -a vX.Y.Z -m "…" && git push origin vX.Y.Z`.
- Treat these as the public API (bump MINOR for additions, MAJOR for breaks):
  template schema, analyzer contract, `DataSource`, `AuthProvider`/`Principal`,
  the report/panel payload + JS panel types, the extension API, the `RCA_*` env vars.
- Record changes in a `CHANGELOG` and call out breaking changes loudly — the
  use-case repo only sees a new tag, not the diff.

## Requesting a framework change (use-case agent → framework agent)

Open an issue on the framework repo describing the need (new panel type, new
built-in analyzer, schema field, backend hook). The framework agent implements it,
tags a release; you bump the submodule. **Do not** edit files under `framework/`
in your repo — those edits would be lost on the next submodule update and break
the lock.
