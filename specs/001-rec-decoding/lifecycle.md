# 7. Local lifecycle and cache

Extend `SdkCache` without changing existing SDK/schema paths.

```text
<user-data-root>/
├── sdk/polar/<sdk-commit>/                 existing
├── generated/polar/<sdk-commit>/           existing
├── decoder-build/polar/<sdk-commit>/       generated build workspace
├── decoder/polar/<sdk-commit>/
│   ├── bin/ or decoder.jar
│   ├── manifest.json
│   ├── build-report.json
│   └── verify-report.json
├── active-sdk.json                         existing
└── active-decoder.json                     new
```

Required `SdkCache` additions:

```python
decoder_build_root
decoder_root
active_decoder_manifest_path
decoder_build_path(commit)
decoder_path(commit)
```

### 7.1 Independence from schema generation

The schema and decoder lifecycles are related by SDK provenance but remain independent:

- schema generation may succeed while decoder build is unavailable;
- decoder build may succeed without regenerating schemas;
- activating an SDK revision must not activate a decoder;
- activating a decoder must not change the active schema revision;
- deleting generated schemas must not delete a decoder;
- decoder removal must be explicit.

### 7.2 Decoder manifest

`manifest.json` must contain at least:

```json
{
  "manifest_version": 1,
  "decoder_protocol_version": 1,
  "sdk_commit": "<full commit>",
  "polar_ble_tools_version": "<version>",
  "build_mode": "jvm|android-jvm",
  "build_timestamp_utc": "<RFC3339>",
  "platform": "<normalized platform>",
  "architecture": "<normalized architecture>",
  "java_version": "<version>",
  "gradle_version": "<version>",
  "adapter_source_sha256": "<digest>",
  "executable_relative_path": "<path>",
  "executable_sha256": "<digest>",
  "verification_level": "handshake|sample",
  "verified": true
}
```

Never store licence text, SDK source, personal paths, device identifiers, or recording data in the manifest.

### 7.3 Activation

Build into a staging directory. Activate only after verification succeeds.

Activation must be atomic:

1. complete build;
2. compute digests;
3. run structural verification;
4. write final manifest;
5. move staged output to the revision directory;
6. atomically replace `active-decoder.json`.

A failed build or verification must leave the previous active decoder unchanged.

