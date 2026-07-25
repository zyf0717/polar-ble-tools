# Contributing

Contributions should preserve the separation between BLE transport, PMD/PFTP
clients, device operations, collection, decoding, storage, and SDK tooling.
Imports and property access must not download data, generate schemas, connect to
devices, or mutate device state.

## Setup

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,sdk]"
```

Run focused tests for changed behavior, then the full SDK-free suite and quality
checks:

```bash
ruff check .
ruff format --check .
pytest -q tests/unit tests/contracts
python scripts/release_audit.py
```

Hardware tests are opt-in and require an authorized device inventory. SDK
contract tests require a separately obtained SDK and accepted upstream licence.
See [development](docs/development.md) for the complete test boundaries.

Do not commit SDK checkouts, `.proto` files, generated protobuf modules,
descriptor sets, generated caches, device inventories, personal profiles,
captures, credentials, or hardware logs. Update `pyproject.toml` with any
dependency change.
