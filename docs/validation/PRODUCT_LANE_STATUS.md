# Product-lane acceptance status

This is the working release ledger for the completion branch. It separates
repository regression evidence from external validation evidence and keeps
solver fidelity attached to a provider profile.

## Current lanes

| Lane | Provider/product | Local evidence | External evidence | Claim ceiling |
| --- | --- | --- | --- | --- |
| `shock-cell-basic-v1` | `plume.straight-analytical` -> `plume.visual.sectioned-tube@1` | Contract, deterministic-provider, first-cell regression, conformance, and declared study-envelope tests | Pending the recovered Version 8 corpus and benchmark/operator intake | Engineering-approximate straight visual geometry and named features only; no spectral, ray, detector, mixing, or curved-flow claim |
| `signature-table-mvp-v1` | `signature.table-lookup` -> `plume.signature.spectral-radiant-intensity@1` | Table shape, interpolation, extrapolation, time-axis, partial-result, provenance, and conformance tests | Pending a verified source asset and intrinsic-signature evidence | Versioned table and interpolation behavior only; no geometry, ray field, atmosphere, optics, or detector claim |
| `optical-transfer-v1` | No provider | Canonical ray-transfer contract and miss/failed-ray semantics only | No provider-specific transfer validation yet | No optical-transfer claim |
| `focal-plane-array-v1` | No provider; downstream adapter | Boundary and dependency checks only | Requires validated ray transfer plus camera/optics/detector data | No FPA image, count, noise, or detection claim |

The basic and signature lanes are deliberately independent. A comparison to a
higher-fidelity solver may produce a residual report, but it must not modify
the basic provider's configuration, training data, or claim ceiling.

## Release gates

The completion branch cannot call a lane externally validated until all of the
following are true:

1. The referenced archive is present, its SHA-256 digest matches
   `corpus_intake_manifest_v1.json`, its license and retrieval provenance are
   recorded, and the archive passes the safe ZIP intake check.
2. Each claim names a benchmark, product, measurement operator, metric,
   applicability domain, uncertainty treatment, provenance, limitation, and
   evidence role.
3. VIS and SIG run their own provider-specific acceptance suites. Shared API
   conformance is necessary but is not product evidence by itself.
4. A ray/FPA claim additionally passes the cross-product operator checks for
   ray misses, support containment, spectral/band consistency, and snapshot
   lineage. The shock-cell provider cannot satisfy these gates by supplying
   geometry alone.

Until the archive is recovered, the repository's fixtures and regression
tests remain useful engineering evidence but are not reported as experimental
validation.

The recovered corpus changes that sentence for data availability, not for
product acceptance. Its own gate registry reports VIS, SIG, and RAY T1
component evidence as `ready` and their T2 product evidence as
`partial_evidence`; all three T0 contract gates are `outside_corpus`, and the
T3 cross-product gate is `synthetic_only`. Those statuses describe the corpus
alignment layer. The repository still needs provider-specific operators,
thresholds, and the unresolved operator crosswalk before it can accept a
product claim.

## Working branch

The clean completion work is isolated on `work/validation-and-completion`,
created from the integrated local `main`. The original dirty feature worktree
is intentionally left untouched; its changes will be audited and ported in
bounded commits after this branch's gates identify which changes belong to an
active lane.

The branch checks are:

```bash
python3 -m pytest -q
python3 -m ruff check .
python3 scripts/check_pyright.py
```

The fidelity-specific local report is generated with:

```bash
python3 scripts/validate_product_lanes.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --output product-lane-report.json
```

This command currently passes the VIS provider/conformance cases, SIG table
interpolation cases, and the negative FPA-advertisement boundary check. Its
report intentionally remains `release_ready: false` until external
measurement-operator comparisons and the operator crosswalk are complete.

The missing external archive is a release blocker, not a reason to weaken the
fidelity boundaries or synthesize replacement measurements.
