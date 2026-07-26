# 12. Build behavior

The builder must:

1. resolve a locally installed SDK revision;
2. validate its recorded provenance and full commit;
3. generate a clean build workspace outside the repository;
4. copy only project-owned adapter/build templates into that workspace;
5. reference the SDK through its local cached path;
6. run the selected toolchain without `shell=True`;
7. capture a bounded build log and structured build report;
8. locate exactly one expected executable artifact;
9. reject unexpected SDK-derived files in the final decoder directory;
10. verify and activate atomically.

Network behavior:

- never download the Polar SDK;
- ordinary Maven/Gradle dependency resolution may occur during an explicit build;
- provide an `--offline` build option if the selected toolchain supports it;
- document all external prerequisites and any network access.

The builder must not edit the cached SDK checkout in place.

## 13. Runtime safety

The Python runtime must:

- resolve the active decoder only from `active-decoder.json`;
- ensure all resolved paths remain under the decoder cache root;
- verify the executable digest before invocation;
- use a temporary destination in the final destination directory;
- reject symlink/path traversal surprises where practical;
- reject missing, non-regular, or unreadable input;
- reject an existing destination unless `overwrite=True`;
- enforce a configurable timeout;
- terminate the child process on timeout;
- bound captured stdout and stderr;
- validate the complete JSONL stream before atomic rename;
- remove temporary output after failure;
- never delete or modify the source `.REC`;
- never invoke device or BLE operations.

