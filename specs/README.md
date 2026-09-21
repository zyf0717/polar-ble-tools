# Open specifications

Specs describe unresolved work only. Start with the relevant row; do not load
predecessors or deferred designs unless the task changes that boundary.

| Spec | State | Remaining scope |
| --- | --- | --- |
| [009](009-bleak-platform-migration/README.md) | Implementing | macOS/Windows workflow parity and evidence handoff |
| [004](004-rec-decoder-extension/README.md) | Implementing | REC architecture certification and explicit payload adapters |
| [005](005-protected-compatibility/README.md) | Deferred | Approved evidence policy and physical release certification |
| [006](006-protected-rec-decoding/README.md) | Deferred | Protected decode protocol and SDK/fixture proof |
| [007](007-rec-batch-decoding/README.md) | Deferred | Batch decoding after adapter certification and priority approval |

## Graduated contracts

SPEC-003 core operations and SPEC-008 BPB decoding are complete. Their contracts
now live in [architecture](../docs/architecture.md#detailed-contracts),
[recording](../docs/offline-recording.md), [raw retrieval](../docs/raw-file-retrieval.md),
[passive files](../docs/passive-files.md), and [BPB decoding](../docs/bpb-decoding.md).
Implemented portions of SPEC-004 and SPEC-009 live in
[REC decoding](../docs/rec-decoding.md), [SDK integration](../docs/sdk-integration.md),
and [public APIs](../docs/python-api.md). Evidence lives in
[compatibility](../docs/compatibility.md); historical plans and closed FRs stay
in Git history. Do not recreate completed-spec archives.

## Shared gates

Use [development](../docs/development.md) and [release](../docs/releasing.md)
gates. Specs add only work-specific acceptance. Public docs own current behavior;
specs must not silently broaden support. On completion, merge missing contracts
into their topic docs, delete duplicates, and remove the completed spec.

Keep one status/acceptance owner per workstream. A separate file is justified
only for a detailed pending protocol. Keep existing spec/FR IDs for open work;
never renumber or reuse retired IDs (next spec: 010; 000 reserved, 001/002 unused).
Deferred work requires its stated prerequisite, not speculative implementation.
Specs stay on `dev` and are removed from release trees.
