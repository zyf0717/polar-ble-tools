# Raw file retrieval and cleanup

Raw `.REC` listing and retrieval do not require the Polar SDK or generated
schemas.

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF list
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF \
  --root .local/polar-ble-raw collect --type ACC
```

Collection writes each payload atomically and appends a JSONL manifest
containing its device path, local path, size, and SHA-256 digest. Re-running
collection reuses a verified local copy and rejects path escapes or conflicting
content.

## Cleanup safety

Cleanup requires either one or more `--type` selectors or `--all`. Review a dry
run first:

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF \
  --root .local/polar-ble-raw cleanup --type ACC --dry-run
```

Without `--dry-run`, a device file is eligible only when:

1. its exact path came from the current device listing;
2. the corresponding recording is inactive;
3. a local manifest entry exists;
4. local file size and SHA-256 match that manifest.

Every decision is written to the deletion log. Cleanup never guesses related
paths; empty parent directories are removed only after the selected file is
removed.
