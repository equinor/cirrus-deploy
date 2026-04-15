Karsk
=====

<!-- --8<-- [start:intro] -->
Karsk (pronounced _kashk_) is a Norwegian cocktail from Trøndelag county mixing
coffee with moonshine. It is also a tool for deploying software on our
NFS-backed Linux cluster.

Karsk solves the following problems for us:

1.  **Continuous  upgrades**:  Users  reliably access  the  latest  versions  of
   software without needing to update anything themselves.

2. **User-controlled versioning**: Each deploy persists on disk. Users can select
   any existing version anytime.

3. **Simple rollbacks**: Because releases are symbolic links, rollbacks are
   quick and painless.

# How it works

Karsk has three stages: **build**, **install**, and **sync**. Each stage writes
to a different location, and the destination is strictly append-only — nothing
is ever overwritten.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          karsk build                                    │
│                                                                         │
│  Builds packages in containers, then assembles an environment           │
│  (symlink tree + manifest) in the staging directory.                    │
│                                                                         │
│  staging/                                                               │
│  ├── .store/                                                            │
│  │   └── a1b2c3-myapp-1.0.0/       ← built package artifacts            │
│  ├── 1.0.0-1/                       ← environment (symlinks into store) │
│  │   ├── bin/myapp -> ../../.store/a1b2c3-myapp-1.0.0/bin/myapp         │
│  │   └── manifest                                                       │
│  ├── latest -> 1.0.0-1                                                  │
│  ├── stable -> latest                                                   │
│  └── bin/run                        ← wrapper script                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          karsk install                                  │
│                                                                         │
│  Copies store packages from staging to destination and builds the       │
│  environment there. Destination is append-only: the build ID is         │
│  allocated against what already exists in destination.                  │
│                                                                         │
│  destination/  (/opt/karsk/myapp)                                       │
│  ├── .store/                                                            │
│  │   ├── a1b2c3-myapp-1.0.0/       ← first build                        │
│  │   └── d4e5f6-myapp-1.0.0/       ← second build (new hash)            │
│  ├── 1.0.0-1/                       ← first build env                   │
│  ├── 1.0.0-2/                       ← second build env                  │
│  ├── latest -> 1.0.0-2                                                  │
│  ├── stable -> latest                                                   │
│  └── bin/run                                                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          karsk sync                                     │
│                                                                         │
│  Replicates the destination to remote hosts via rsync + SSH.            │
│  Build IDs are identical across all sync locations.                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Build IDs

Each environment directory is named `<version>-<build_id>`, e.g. `1.0.0-1`.
The build ID is a monotonically increasing counter scoped to its target
directory. Because staging is typically cleared between builds while destination
is not, the **same build may get different IDs** in staging vs destination:

```
staging:      1.0.0-1  (staging was cleared, starts from 1)
destination:  1.0.0-3  (two previous builds already exist)
```

This is by design. The key invariant is:

- **Destination is append-only** — existing builds are never overwritten or
  removed.
- **Sync locations are identical** — `karsk sync` replicates the destination
  layout exactly, so build IDs match across all remote hosts.
- **Same manifest = same build** — if a build with an identical manifest
  already exists at the target, it is skipped.

<!-- --8<-- [end:intro] -->

# Installing

Karsk is written in Python and requires
[uv](https://docs.astral.sh/uv/getting-started/installation/) and some container
engine. Currently, only [Podman](https://podman.io/) is supported, but
[Docker](https://www.docker.com/) may work as well.

To get started, clone this repository and run `uv sync` to get the `karsk`
executable.

# Using 

See [examples](./examples) directory for examples. Use `karsk --help` to view
documentation.

# Testing

This project uses [pytest](https://pytest.org) for tests,
[mypy](https://www.mypy-lang.org/) for type-checking and
[ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```sh
# Run tests
uv run pytest tests

# Typecheck (note: we don't typecheck test code)
uv run mypy --strict src

# Lint and format
uv run ruff format
uv run ruff check --fix
```
