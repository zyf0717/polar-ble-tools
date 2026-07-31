# Models and errors

`RecordingIdentity` contains only the minimum redacted source identity required
by a provider. `RecordingSecret` is immutable and byte-oriented; its string and
debug representations never expose secret bytes.

Required errors extend the SPEC-004 hierarchy:

```text
RecDecodeError
└── RecordingSecurityError
```

Stable security outcomes expose project-owned codes without SDK class names,
secret material, private paths, or provider internals.
