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

## Targeted fetch contract

Accepted device paths have exactly this shape:
`/U/<user-index>/<YYYYMMDD>/R/<HHMMSS>/<record-name>.REC`.
Use absolute POSIX syntax, a non-negative decimal user index, valid calendar
date/time, and one regular filename with case-insensitive `.REC` suffix.
Empty interior segments, `.`/`..`, wildcards, directories, family expansion,
and parent cleanup are rejected. PFTP receives the exact normalized path.

Before connecting, fetch rejects existing output symlinks, source/output aliases,
and unrequested overwrite. It bounds and hashes the bytes, flushes a sibling
temporary regular file, then publishes atomically. Failure or mismatch with a
listed expected size publishes no partial final file. The result records
`device_id`, `device_path`, `output_path`, `fetched_size`, `sha256`, and
`observed_at`.

## Collection

Collection writes each payload atomically and appends a JSONL manifest
containing its device path, local path, size, and SHA-256 digest. Re-running
collection reuses a verified local copy and rejects path escapes or conflicting
content. On Windows, appenders lock a persistent hidden sibling file so readers
can continue consuming the manifest's last complete rows.

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

For BPB files, see [passive retrieval and cleanup](passive-files.md).
