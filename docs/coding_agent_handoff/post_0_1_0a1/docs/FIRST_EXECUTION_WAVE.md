# First execution wave

## Goal

Stabilize the merged alpha and remove the architectural ambiguity that would otherwise infect every later provider.

## Exact queue

```text
RLS-001
  ↓
RLS-002

RLS-001
  ↓
API-008A
  ↓
API-008B
  ↓
API-008C
  ↓
API-009
  ├─ PRV-001
  ├─ PRV-002
  └─ PRV-003
       ↓
     PRV-004
       ↓
     API-010
```

In parallel after `RLS-001`:

```text
MOC-001 → MOC-002 → MOC-003
```

Do not merge public MOC integration until `API-010`.

## Required review moments

### Release review

Review the exact commit, version, artifacts, warnings, and generated assets.

### API authority review

Review real imports, real schemas, real fixtures, and real provider code. Do not decide based only on the prose ADR.

### Wire compatibility review

Diff every shipped fixture and schema. A semantically harmless Python rename may still be a wire break.

### Provider conformance review

Run prescribed, analytical, and signature providers through the same harness before freezing v1.

## First-wave stop condition

Stop the wave when:

- the baseline has a reproducible tag;
- one lifecycle and wire authority are accepted;
- the three current providers pass canonical conformance;
- old imports have a tested migration path;
- v1 is formally frozen.

Do not begin the washed public provider or alter public MOC semantics before this stop condition.
