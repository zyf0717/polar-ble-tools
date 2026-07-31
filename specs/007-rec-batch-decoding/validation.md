# Validation

- deterministic case-insensitive tree discovery and output-subtree exclusion;
- no symlink traversal or root escape;
- strict JSONL manifest schema, duplicate-key/path, digest, and newline checks;
- complete destination preflight before the first decode;
- no-clobber and constrained-overwrite behavior;
- continued execution after per-file unsupported/failure outcomes;
- deterministic schema-versioned summary ordering and counts;
- atomic output and summary publication;
- stable CLI exit semantics;
- once-per-source redacted provider invocation after SPEC-006.

Private corpus validation remains local and follows SPEC-005.
