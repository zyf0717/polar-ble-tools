# SPEC-009: Remaining platform parity work

**Status:** Implementing; Linux `0.5.0` baseline complete.

Preserve the [public APIs](../../docs/python-api.md),
[lifecycle architecture](../../docs/architecture.md#ble-lifecycle), and
[device-specific setup](../../docs/device-setup.md). Existing observations and
limitations live only in [compatibility](../../docs/compatibility.md); harnesses
are documented in [development](../../docs/development.md#live-workflow-harnesses).
Canonical identifier authorization, uniform 30-second discovery/resolution,
and pinned macOS REC toolchains are implemented; their completed requirements
FR-094/101 do not need a second contract here.

## Open requirements and acceptance

This table owns the remaining implementation gates (FR-092). Open means
insufficient evidence, not proven unsupported behavior. A preliminary single
Loop pass does not close both device families or the entire host.

| IDs | Acceptance | macOS gap | Windows gap |
| --- | --- | --- | --- |
| FR-093 | Native clean install, full SDK-free unit/contracts, packaging, import/CLI smoke; Linux full supported Python matrix and at least one supported version per other host. | Full-suite CI exists; complete packaging/clean-wheel gates. | Expand focused storage/schema CI to full suite and packaging. |
| FR-095 | Bounded readiness and later new-client/new-process reconnect; distinct prepared and separately authorized fresh-state evidence. No OS-shaped public pairing fields. | Complete fresh authentication/persistence proof under CoreBluetooth-owned UI and host-local UUIDs. | Integrate encrypted Bleak pairing at `protection_level=2` into preparation, retaining uncached WinRT discovery; no separate pairing script in completed workflow. |
| FR-096 | Both device families: FTU/read-back, PMD/PFTP reads, ACC start/stop/materialization, exact REC size/hash/manifest verification, eligible cleanup dry-run with zero deletion; passive list/retrieve/decode only where data exists. | Extend preliminary Loop FTU/ACC results to Verity and applicable passive workflows. | Complete guarded workflows for both families. |
| FR-097 | Native atomic stores, manifest locking, schema install/activation, BPB decode, path/alias safety, clean-wheel use. | Finish native filesystem/schema/BPB matrix. | Extend focused locking/schema tests to full matrix. |
| FR-098 | Timeout/cancellation in each phase, partial-connect cleanup, disconnect, later recovery, same-device serialization and bounded two-device concurrency without competing scans. | Complete native failure and concurrency matrix. | Complete native lifecycle/failure/concurrency matrix. |
| FR-099, FR-100 | Pass release gates, hand exact-commit physical evidence to SPEC-005, and publish only approved support with identity/authentication semantics, limits, and recovery guidance. | Certification outstanding. | Certification outstanding. |

Work in table order: native CI and host lifecycle decisions → device workflows
and failure paths → evidence/release. Optional REC decoding remains separate;
Windows unavailability is an accepted non-blocking gap. macOS x86_64 and other
REC categories need their own evidence before claims expand.

## Decision and completion rules

For each host lifecycle outcome, record a reviewed verdict and rationale:
**Bleak-only**, **Bleak plus OS adapter**, **Remove or redesign**, or
**Unsupported**. Judge package outcomes, not matching OS flags. An adapter
requires a demonstrated missing outcome, typed bounded injectable public/native
APIs, independent tests, and a removal condition; no private Bleak state.
Test minimum and newest allowed Bleak minors when selecting dependency ranges.

Stop the affected experiment if cached/external state obscures evidence,
connection ownership can leak, mutation/reset is unauthorized, or private data
would leak. Record Unsupported or a revised reviewed experiment. Never add
implicit bond removal, unsafe retries, or adapter-policy changes.

Implementation completion requires reviewed host verdicts, passing applicable
rows, explicit accepted gaps, and shared [release gates](../README.md#shared-gates).
[SPEC-005](../005-protected-compatibility/README.md) owns protected evidence review
and exact-release certification; its deferral does not block implementation.
Hosted CI, mocks, preliminary observations, and skipped live tests do not
substitute for controlled physical certification.
