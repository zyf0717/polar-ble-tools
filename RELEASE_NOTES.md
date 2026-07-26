# polar-ble-tools 0.2.0

`0.2.0` adds an optional, local-only REC decoder sidecar and expands the Python
API for operational use. The package continues to support Linux/BlueZ BLE
discovery, pairing, PMD/PFTP operations, raw REC and passive BPB retrieval,
FTU setup, guarded cleanup, and locally generated-schema BPB decoding.

## Highlights

- Build, verify, activate, inspect, and remove a locally compiled REC decoder
  through `polar-ble sdk decoder`; decode with `polar-ble rec` or
  `polar_ble_tools.rec`.
- Validate decoder runtime files, JDK provenance, sidecar handshakes, JSONL
  protocol output, source digests, and race-safe output publication.
- Use direct `doctor()` and async FTU workflow APIs; passive collection is now
  available from the top-level package.
- Consult dedicated [CLI](docs/cli-reference.md) and
  [Python API](docs/python-api.md) references.

## Compatibility and boundaries

REC decoding is experimental and local-only. Encrypted recordings and record
categories without private fixture-contract evidence are unsupported. The
Verity Sense PPI timestamp remains intentionally suppressed until its SDK
semantics are validated. See [compatibility](docs/compatibility.md).

The distribution does not include the Polar BLE SDK, SDK schema source,
generated SDK artifacts, real recordings, or a compiled decoder binary. Users
obtain and license the SDK separately.

## Validation

Release validation completed with Ruff, the complete test suite, fresh wheel
and sdist build, strict Twine validation, packaging tests, artifact/history
audit, and CLI smoke checks. Hardware and private-fixture contract validation
remain local opt-in gates.
