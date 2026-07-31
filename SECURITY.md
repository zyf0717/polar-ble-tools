# Security policy

Security reports should be submitted privately through the repository's
security-advisory interface. Do not open a public issue containing credentials,
device identifiers, profiles, captures, participant data, or exploit details.

Only the latest stable release line receives security fixes.

Device cleanup is intentionally guarded: callers must select record types or
all records explicitly, and deletion requires an inactive recording with a
size- and SHA-256-verified local copy. Use `--dry-run` before any cleanup.
