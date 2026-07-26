# 15. Documentation

Update:

- `README.md`
  - replace “Structured `.REC` decoding is not currently included” with optional sidecar status;
  - retain the raw-retrieval-first guidance.
- `docs/architecture.md`
  - add the sidecar boundary and data flow.
- `docs/sdk-integration.md`
  - explain that schema and decoder lifecycles are separate.
- `docs/configuration.md`
  - document commands, paths, timeout, and status.
- `docs/troubleshooting.md`
  - cover missing SDK, JDK/Gradle/Android prerequisites, build failure, incompatible protocol, verification failure, and unsupported recording.
- `NOTICE`
  - clarify that decoder binaries are locally built and not distributed.
- `docs/compatibility.md`
  - add a device/recording decoder validation matrix.
- `docs/releasing.md`
  - add artifact scans and a prohibition on decoder release uploads.

Documentation must state that:

- the project is unofficial;
- the user separately obtains and accepts the SDK licence;
- decoding support depends on the locally built decoder and validated SDK revision;
- raw collection remains available without the sidecar.

