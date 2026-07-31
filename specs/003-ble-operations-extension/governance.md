# Governance and completion

## Execution rules

- Preserve protocol, workflow, storage, and command ownership.
- Keep device mutations verified, bounded, and audited.
- Never infer support from unit tests or service presence alone.
- Keep device payloads, identifiers, profiles, and inventories out of Git and
  public artifacts.
- Do not make core BLE retrieval depend on SDK material or a REC decoder.
- Update contracts, tests, and release documentation with public behavior.
- Stop destructive work when exact eligibility or auditability cannot be
  established.

## Definition of done

SPEC-003 is complete when:

1. recording control and targeted retrieval are documented CLI and Python APIs;
2. raw collection/cleanup and passive list/collect/cleanup are implemented;
3. every destructive operation is locally verified, dry-runnable where
   applicable, and audited;
4. same-device operations serialize through the shared workflow runner;
5. public results use immutable collections and constrained status models;
6. shared storage mechanics are centralized without merging domain policy;
7. transport failures retain their typed category and abort workflows;
8. unit, contract, packaging, metadata, audit, and clean-install gates pass;
9. release documentation describes only evidence-backed support;
10. version and release notes identify the `0.3.0` contract.

SPEC-004 through SPEC-007 are independent follow-on programs and are not
SPEC-003 completion gates.
