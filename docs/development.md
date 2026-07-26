# Development

Python 3.11 through 3.14 is supported. Use the repository virtual environment
and install dependencies there:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,sdk]"
```

## Quality and tests

```bash
ruff check .
ruff format --check .
pytest -q tests/unit tests/contracts
pytest -q tests/live
python scripts/release_audit.py
python -m pytest -q tests/packaging/test_artifacts.py
```

Unit and contract tests are SDK-free unless marked otherwise. `tests/sdk_contract`
requires a separately obtained and licensed SDK. Live tests are disabled by
default and require protected hardware, an ignored `test_devices.yaml`, and
explicit environment flags. A skipped SDK or live test is not a successful
validation result.

The REC decoder corpus contract is also opt-in and requires a built active
decoder plus a local, non-redistributable fixture tree:

```bash
POLAR_BLE_SDK_DECODER_CONTRACT=1 \
POLAR_BLE_REC_FIXTURES=/path/to/rec-fixtures \
pytest -q tests/sdk_decoder_contract
```

It verifies deterministic JSONL output for the documented Loop Gen 2 and
Verity Sense corpus. Do not add fixture paths or recordings to the repository.

## Repository boundaries

Do not commit or package:

- Polar SDK source or archives;
- `.proto` source, `_pb2.py` modules, or descriptor sets generated from SDK
  files;
- SDK checkout or generated-cache directories;
- device inventories, FTU profiles, captures, logs, credentials, or personal
  sensor data.

Raw collection and ordinary imports must work without generated schemas. Keep
network access, BLE access, downloads, generation, and device mutation behind
explicit function or command calls. Use atomic writes for manifests, generated
installations, and caches.

Hardware cleanup tests use dry-run only. Any live mutation must target a device
present in the authorized inventory and must not print or upload identifiers,
profiles, captures, or SDK data.
