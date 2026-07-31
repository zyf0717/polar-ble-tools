# Governance and completion

## Execution rules

- Experiments establish package sufficiency; they do not seek parity with
  `bluetoothctl` implementation details.
- Use only supported public Bleak APIs in a Bleak-only verdict.
- Do not use Bleak private backend state to avoid defining a required OS
  adapter.
- Add an OS adapter only for a named, evidenced package outcome and keep it
  below the transport/lifecycle boundary.
- Do not retain subprocess behavior solely for `0.4.x` compatibility.
- Preserve explicit authorization, bounded mutation, deterministic cleanup,
  and private evidence handling.
- Do not broaden device or platform support from mocked tests, hosted CI, or
  successful import.
- Do not change PMD/PFTP protocol, storage, guarded cleanup, or decoder
  boundaries as collateral work.

## Stop conditions

Stop the affected migration row when:

- the required outcome cannot be stated independently of one OS implementation;
- the experiment cannot distinguish success from cached or externally owned
  state;
- failure or cancellation can leave connection ownership ambiguous;
- fresh preparation would require an unauthorized bond reset or other device
  mutation;
- evidence would expose a device identifier, capture, payload, profile, or
  private path;
- the proposed adapter reaches through private Bleak internals;
- a platform claim lacks controlled physical-device evidence.

A stopped row receives an **Unsupported** verdict or a revised, separately
reviewed experiment. It is not silently deferred during implementation.

## Definition of done

SPEC-009 is implemented when:

1. every lifecycle operation has a reviewed verdict and evidence record;
2. Bleak owns every operation for which it passed the sufficiency criteria;
3. every retained OS adapter has a documented missing outcome and removal
   condition;
4. obsolete competing-owner and command-parsing paths are removed;
5. public identity, discovery, preparation, probe, and session contracts are
   platform-neutral and asynchronous;
6. all device-facing workflows use shared connection ownership and cleanup;
7. Loop Gen 2 and Verity Sense FTU dispatch remain device-specific, with
   Verity runtime time and wear location verified independently;
8. Linux automated and two-device-category hardware gates pass;
9. macOS and Windows workflows and certification are explicitly deferred to
   SPEC-005 without a support claim;
10. release audit, packaging, clean-install, and required repository checks
    pass;
11. architecture, API/CLI, compatibility, changelog, and `0.5.0` release notes
    describe the accepted contract and limitations.

macOS and Windows 11 automation and physical certification remain SPEC-005
activities, not SPEC-009 completion gates.
