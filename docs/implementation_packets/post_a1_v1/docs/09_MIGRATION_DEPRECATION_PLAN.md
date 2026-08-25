# Migration and Deprecation Plan

## Alpha compatibility goals

The release is still alpha, but changes must remain intentional and testable.

### Preserve

- existing root solver functions;
- current CLI commands;
- a1 provider imports;
- a1 signature and visual asset formats where semantics are unchanged;
- existing numerical kernels until their dedicated packet changes them.

### Consolidate

- public product DTOs under `exhaust_plume.api`;
- capability identity and schema generation;
- provider conformance;
- flux-section transport representation;
- entrainment implementation.

### Deprecate gradually

- overlapping DTOs in `contracts` and `products`;
- ambiguous same-name root exports;
- duplicate `DevelopingShearForcedEntrainment`;
- computational `PlumeFluxSection` name once a replacement internal name exists.

## Required compatibility artifacts

- `docs/migration_0_1_0a1_to_a2.md`;
- import-compatibility tests;
- serialized fixture compatibility tests;
- an alias table with removal target no earlier than the next minor/pre-release line;
- no bulk deletion in the API-freeze PR.
