# Evidence contract

The detailed private matrix and redacted public schema are deferred pending
maintainer or organizational approval.

Current prose observations in `docs/compatibility.md` are historical,
capability-scoped inputs. They are not formal rows under this deferred schema
and do not satisfy exact-commit certification by themselves.

## Public evidence

Public compatibility evidence is limited to:

```text
observed date
package commit and version
device family
host architecture
operation or capability
pass/fail/unsupported/unvalidated
approved limitation
```

It excludes MAC addresses, serial numbers, participant identifiers, profile
content, raw/decoded payloads, secrets, exact private paths, and unredacted
logs.

## Evidence semantics

- `pass` requires a controlled exercise on the identified commit.
- `unsupported` means the protocol/device rejected or did not expose the
  capability under the controlled contract.
- `unvalidated` means no sufficient controlled evidence exists.
- `skipped` is never interpreted as pass.
- Passive time coverage does not prove raw waveform or continuous-signal
  coverage.
- Unit/contract tests prove software behavior, not physical-device support.

## Private records

Private validation records bind the public row to approved fixture/hardware
evidence, test procedure, expected outcome, retention deadline, and reviewer.
They remain outside the repository and public automation.
