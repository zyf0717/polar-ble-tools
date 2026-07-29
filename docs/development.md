# Development

Python 3.11 through 3.14 is supported. Use the repository virtual environment
and install dependencies there:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,sdk]"
```

## Quality and tests

```bash
ruff check .
ruff format --check .
pytest -q tests/unit tests/contracts
pytest -q tests/live
python scripts/release_audit.py
python -m pytest -q tests/packaging/test_artifacts.py
```

Unit and contract tests are SDK-free unless marked otherwise. `tests/sdk_contract`
requires a separately obtained and licensed SDK. Live tests are disabled by
default and require protected hardware, an ignored `test_devices.yaml`, and
explicit environment flags. A skipped SDK or live test is not a successful
validation result.

Record live evidence at the capability level actually exercised:

- an advertised PMD type is not start/stop evidence;
- a retrieved and hash-verified BPB file is not decoding evidence;
- `selected > 0`, `dry_run = 0`, and blocked-only cleanup results validate the
  safety guard, not an eligible cleanup dry-run; and
- a bounded retry that passes should retain the preceding failure phase and
  timeout location in the private test record.

An eligible cleanup dry-run requires at least one selected recording with a
verified local copy in the configured raw root and a resulting `dry_run` status.
Do not publish the inventory, device path, manifest, payload, or hardware log
used to establish that evidence.

The REC decoder corpus contract is also opt-in and requires a built active
decoder plus a local, non-redistributable fixture tree:

```bash
POLAR_BLE_SDK_DECODER_CONTRACT=1 \
POLAR_BLE_REC_FIXTURE_MANIFEST=/private/path/fixtures.json \
pytest -q tests/sdk_decoder_contract
```

The private manifest contains fixture-relative paths, source/output SHA-256,
record type, and count. It verifies deterministic JSONL output. Do not add the
manifest, fixture paths, or recordings to the repository. Public tests use a
fake sidecar and never download the SDK, JDK, Gradle, or Maven artifacts.

## Repository boundaries

Do not commit or package:

- Polar SDK source or archives;
- `.proto` source, `_pb2.py` modules, or descriptor sets generated from SDK
  files;
- SDK checkout or generated-cache directories;
- device inventories, FTU profiles, captures, logs, credentials, or personal
  sensor data.

Raw collection and ordinary imports must work without generated schemas. Keep
network access, BLE access, downloads, generation, and device mutation behind
explicit function or command calls. Use atomic writes for manifests, generated
installations, and caches.

Hardware cleanup tests use dry-run only. Any live mutation must target a device
present in the authorized inventory and must not print or upload identifiers,
profiles, captures, or SDK data.

## Branch and release workflow

Use `dev` as the integration branch and keep `main` linear through pull
requests:

1. Develop and integrate changes on `dev`.
2. Make `dev` release-ready: finalize the version, dated changelog, release
   notes, product documentation, and required evidence; commit and push them.
3. Create the release branch from the verified `origin/dev` tip.
4. Delete only `AGENTS.md` and `specs/` on the release branch.
5. Merge the release pull request into `main` using rebase or squash.
6. Merge the updated `origin/main` back into `dev`, then restore the
   development-only controls from the pre-merge `dev` tip.
7. Rebuild and force-update `dev` only when accumulated duplicate history
   warrants compaction.

Do not use a release branch to curate or finish product changes. If `dev`
contains work that is not ready, revert or finish it on `dev` before branching.
Prepare the release tree as follows:

```bash
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c release/<version> origin/dev
git rm -r -- AGENTS.md specs
git commit -m "chore: prepare <version> release tree"
git diff --name-status origin/dev...HEAD
```

The final command must show only deletion of `AGENTS.md` and `specs/` relative
to `origin/dev`. Run the required checks and inspect the complete
`origin/main...HEAD` product diff before opening the pull request. Product,
documentation, workflow, version, changelog, and release-note edits on the
release branch indicate that `dev` was not release-ready and must be corrected
there instead.

After the pull request is merged, synchronize its rebase or squash result back
into `dev`. Preserve the pre-merge `dev` tip so its development-only controls
can be restored after accepting the released product tree from `main`:

```bash
git fetch origin
git switch dev
git pull --ff-only origin dev
dev_tip="$(git rev-parse HEAD)"
git merge --no-ff origin/main
git restore --source="$dev_tip" -- AGENTS.md specs
git add AGENTS.md specs
git commit -m "chore: restore development controls after <version>"
git push origin dev
```

Resolve conflicts by preserving the released state from `main` together with
work that remains outstanding on `dev`.

### Exceptional `dev` compaction

Rebuilding `dev` discards its old topology and disrupts dependent branches.
Use it only after coordinating with contributors and preserving an archive:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git branch -m dev dev-archive-<date>
git switch -c dev main
```

Replay only genuinely outstanding changes from the archive. Do not blindly
restore the archived endpoint: that can revert release-only changes already on
`main`. Prefer selective cherry-picks or a reviewed patch, then verify the
result before replacing the remote:

```bash
git diff --cached --check
git fetch origin dev
git push --force-with-lease -u origin dev
git branch --unset-upstream dev-archive-<date>
```

Keep the archive until dependent worktrees and open branches have been
reconciled.
