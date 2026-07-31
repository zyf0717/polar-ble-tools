# Raw file retrieval and cleanup

Raw `.REC` listing and retrieval do not require the Polar SDK or generated
schemas.

```bash
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF list
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF \
  fetch --path /U/0/20260727/R/112233/ACC0.REC --output ACC0.REC
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF \
  --root .local/polar-ble-raw collect --type ACC
```

Targeted fetch validates the exact device REC path and publishes one local file
atomically without clobbering an existing destination.

Collection writes each payload atomically and appends a JSONL manifest
containing its device path, local path, size, and SHA-256 digest. Re-running
collection reuses a verified local copy and rejects path escapes or conflicting
content.

Python listing and collection results expose immutable tuple collections.
Outcome fields are project-owned string enums; `to_jsonable()` retains plain
string statuses and JSON lists.

## Cleanup safety

Cleanup requires either one or more `--type` selectors or `--all`. Review a dry
run first:

```bash
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF \
  --root .local/polar-ble-raw cleanup --type ACC --dry-run
```

Without `--dry-run`, a device file is eligible only when:

1. its exact path came from the current device listing;
2. the corresponding recording is inactive;
3. a local manifest entry exists;
4. local file size and SHA-256 match that manifest.

Every decision is written to the deletion log. A BLE transport failure after a
deletion attempt is audited and then propagated. Cleanup never guesses related
paths; empty parent directories are removed only after the selected file is
removed.
