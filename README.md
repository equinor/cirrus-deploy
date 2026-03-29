Karsk
=====

Karsk (pronounced _kask_) is a Norwegian cocktail from Trøndelag county mixing
coffee with moonshine. It is also a tool for deploying software on our
NFS-backed Linux cluster.

Karsk solves the following problems for us:
1.  **Continuous  upgrades**:  Users  reliably access  the  latest  versions  of
   software without needing to update anything themselves.
2. **User-controlled versioning**: Each deploy persists on disk. Users can select
   any existing version anytime.
3. **Simple rollbacks**: Because releases are symbolic links, rollbacks are
   quick and painless.

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
