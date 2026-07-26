# 10. Public Python API

Expose from `polar_ble_tools.rec`:

```python
def decoder_status() -> DecoderStatus:
    ...

def decode_recording(
    source: PathLike[str] | str,
    destination: PathLike[str] | str,
    *,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
) -> DecodeReport:
    ...

def iter_decoded_records(
    decoded_jsonl: PathLike[str] | str,
) -> Iterator[RecRecord]:
    ...
```

Required models:

```python
@dataclass(frozen=True)
class DecoderStatus:
    available: bool
    verified: bool
    sdk_commit: str | None
    protocol_version: int | None
    verification_level: str | None
    reason: str | None

@dataclass(frozen=True)
class DecodeReport:
    source_path: Path
    destination_path: Path
    source_sha256: str
    destination_sha256: str
    sdk_commit: str
    decoder_version: str
    record_count: int
    record_types: Mapping[str, int]
    warnings: tuple[str, ...]

@dataclass(frozen=True)
class RecRecord:
    record_type: str
    timestamp_ns: int | None
    payload: Mapping[str, object]
```

Do not return sidecar process objects, SDK objects, unvalidated dictionaries, or vendor-specific models.

### 10.1 Errors

Define:

```text
RecDecodeError
├── DecoderUnavailableError
├── DecoderManifestError
├── DecoderVerificationError
├── DecoderProtocolError
├── DecoderTimeoutError
└── RecordingDecodeError
```

Errors must include actionable remediation without exposing excessive subprocess output. Truncate captured stderr to a bounded size.

## 11. CLI

Add a top-level `rec` command, separate from `raw`.

```text
polar-ble rec decode INPUT --output OUTPUT
polar-ble rec decode INPUT --output OUTPUT --overwrite
polar-ble rec status
```

Add decoder lifecycle commands beneath `sdk`:

```text
polar-ble sdk decoder build [--commit COMMIT] [--no-activate]
polar-ble sdk decoder verify [--commit COMMIT] [--sample PATH]
polar-ble sdk decoder status [--json]
polar-ble sdk decoder activate --commit COMMIT
polar-ble sdk decoder remove --commit COMMIT
```

Behavior:

- `build` uses the active SDK revision unless `--commit` is supplied;
- `build` never downloads the SDK;
- licence acceptance must already be recorded by the existing explicit SDK installation flow;
- `verify` without `--sample` performs manifest, digest, version, and self-test checks;
- `verify --sample` performs an end-to-end local decode and records `verification_level=sample`;
- `status` succeeds even when unavailable and explains why;
- `decode` requires an active verified decoder;
- `remove` must not affect raw files, schemas, or SDK sources;
- removing the active decoder clears `active-decoder.json` atomically.

Extend `polar-ble doctor` with an optional decoder section. Decoder unavailability must not make core BLE/raw readiness fail.

