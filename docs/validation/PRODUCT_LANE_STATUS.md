# Product-lane acceptance status

This is the working release ledger for the completion branch. It separates
repository regression evidence from external validation evidence and keeps
solver fidelity attached to a provider profile.

## Current lanes

| Lane | Provider/product | Local evidence | External evidence | Claim ceiling |
| --- | --- | --- | --- | --- |
| `shock-cell-basic-v1` | `plume.straight-analytical` and `plume.shock-cell-analytical` -> `plume.visual.sectioned-tube@1` | Both bounded visual providers pass contract, deterministic-serialization, conformance, and declared study-envelope checks | Corpus structure is verified; provider-specific benchmark/operator comparison remains pending | Engineering-approximate straight visual geometry and named features only; no spectral, ray, detector, mixing, or curved-flow claim |
| `signature-table-mvp-v1` | `signature.table-lookup` -> `plume.signature.spectral-radiant-intensity@1` | Table shape, interpolation, extrapolation, time-axis, partial-result, provenance, and conformance tests | Pending a verified source asset and intrinsic-signature evidence | Versioned table and interpolation behavior only; no geometry, ray field, atmosphere, optics, or detector claim |
| `optical-transfer-v1` | `plume.gray-ray-transfer` -> `plume.optical.spectral-ray-transfer@1` | Exact finite-cylinder intervals, homogeneous slab/chord transfer, layer separation, miss semantics, and analytic/refinement checks | External sensor/path comparisons remain pending; gray analytic evidence is not corpus validation | Homogeneous gray transfer through a straight constant-radius support only; no chemistry, atmosphere, detector, or FPA claim |
| `focal-plane-array-v1` | No provider; downstream adapter | Boundary and dependency checks only | Requires validated ray transfer plus camera/optics/detector data | No FPA image, count, noise, or detection claim |

The local optical evidence is recorded in
[`optical_transfer_validation_v1.json`](optical_transfer_validation_v1.json).
It is deliberately limited to the exact straight-cylinder gray-transfer
provider. The curved-support interval refinement is retained as a
nonmonotonic geometry diagnostic and does not expand the provider’s morphology
or claim ceiling.

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

The recovered archive now satisfies the integrity gate. Repository fixtures
and regression tests remain engineering evidence, not experimental validation;
the unresolved operator crosswalk, provider-specific comparisons, and separate
alignment archive still block external claims.

The provider-comparison preflight is recorded in
[`provider_comparison_preflight_v1.json`](provider_comparison_preflight_v1.json).
It confirms that the two visual providers expose only
`core_radius_fraction` and `opacity_weight`, so the HOTWAKE Mach-disk operator
cannot be applied. It also keeps BSUV2, EMAP, and ALSI in their declared
sensor-space or band-integrated measurement spaces instead of comparing them
to the synthetic intrinsic signature table. The gray ray-transfer provider now
passes the analytic local gate, while its external sensor-space comparison
remains pending. FPA remains an explicit downstream boundary with no provider
ID.

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

python3 scripts/validate_provider_comparisons.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --output provider-comparison-preflight.json
```

This command currently passes the VIS provider/conformance cases, SIG table
interpolation cases, and the negative FPA-advertisement boundary check. Its
report intentionally remains `release_ready: false` until external
measurement-operator comparisons and the operator crosswalk are complete.

The missing external archive is a release blocker, not a reason to weaken the
fidelity boundaries or synthesize replacement measurements.
