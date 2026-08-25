# Product-lane acceptance status

This is the working release ledger for the completion branch. It separates
repository regression evidence from external validation evidence and keeps
solver fidelity attached to a provider profile.

## Current lanes

| Lane | Provider/product | Local evidence | External evidence | Claim ceiling |
| --- | --- | --- | --- | --- |
| `planar-moc-primitives-v1` | No provider; standalone `exhaust_plume.models.moc` foundation | 15 scalar round trips plus interior/centerline compatibility and forward-ray residual checks pass | No product comparison; first-cell assembly, convergence, and external measurement mapping remain pending | Numerical planar characteristic diagnostics only; no public VIS/SIG/RAY/FPA claim |
| `shock-cell-basic-v1` | `plume.straight-analytical` and `plume.shock-cell-analytical` -> `plume.visual.sectioned-tube@1` | Both bounded visual providers pass contract, deterministic-serialization, conformance, and declared study-envelope checks | Corpus structure is verified; provider-specific benchmark/operator comparison remains pending | Engineering-approximate straight visual geometry and named features only; no spectral, ray, detector, mixing, or curved-flow claim |
| `shock-cell-reduced-order-v1` | `plume.shock-train-reduced-order` -> `plume.visual.sectioned-tube@1` | Explicit calibration, physical-versus-safety termination, reduced-order geometry labels, visual-only capability, and canonical conformance checks pass | CJ-UEJ archive is verified and used for component context; closure calibration/validation split and train-cell measurement operator are missing | Experimental visual envelope only; downstream cells are scaled reduced-order geometry; no resolved MOC, spectral, ray, detector, or FPA claim |
| `signature-table-mvp-v1` | `signature.table-lookup` -> `plume.signature.spectral-radiant-intensity@1` | Table shape, interpolation, extrapolation, time-axis, partial-result, provenance, and conformance tests | Pending a verified source asset and intrinsic-signature evidence | Versioned table and interpolation behavior only; no geometry, ray field, atmosphere, optics, or detector claim |
| `optical-transfer-v1` | `plume.gray-ray-transfer` -> `plume.optical.spectral-ray-transfer@1` | Exact finite-cylinder intervals, homogeneous slab/chord transfer, layer separation, miss semantics, and analytic/refinement checks | External sensor/path comparisons remain pending; gray analytic evidence is not corpus validation | Homogeneous gray transfer through a straight constant-radius support only; no chemistry, atmosphere, detector, or FPA claim |
| `focal-plane-array-v1` | No provider; validated downstream adapters | Explicit camera/optics identity, ray-to-pixel expected-electron integration, and deterministic ADC expectation pass synthetic contract checks | Requires validated ray transfer plus camera/optics calibration and detector data | No externally validated FPA image, measured detector count, noise realization, or detection claim |

The local optical evidence is recorded in
[`optical_transfer_validation_v1.json`](optical_transfer_validation_v1.json).
It is deliberately limited to the exact straight-cylinder gray-transfer
provider. The curved-support interval refinement is retained as a
nonmonotonic geometry diagnostic and does not expand the provider’s morphology
or claim ceiling.

The cross-product operator evidence is recorded in
[`ray_signature_consistency_v1.json`](ray_signature_consistency_v1.json). It
validates synthetic projected-area summation, ray misses, wavelength-grid
identity, and parent snapshot lineage. It is an adapted, gray-approximate
signature result and remains below the external-validation claim ceiling. The
FPA boundary evidence is recorded in
[`fpa_boundary_validation_v1.json`](fpa_boundary_validation_v1.json); the
downstream lane has no provider ID. Its deterministic
`op.sensor.fpa-pixel-detector` and `op.sensor.fpa-digitization` are validated on
a synthetic ray fixture. They preserve camera/optics identity and invalid
masks, and produce expected ADC counts without sampling noise. They make no
externally validated image, measured detector-count, noise-realization, or
detection claim.

The branch-level quality and release freeze is recorded in
[`release_freeze_v1.json`](release_freeze_v1.json). It is a local completion
candidate, not an external-validation release: `release_ready` remains false.

The basic and signature lanes are deliberately independent. The ray-to-signature
adapter consumes a resolved ray result without changing either upstream
provider. A comparison to a higher-fidelity solver may produce a residual
report, but it must not modify the basic provider's configuration, training
data, or claim ceiling.

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
the exact external operator namespace remains distinct, while provider-specific
comparisons and the separate alignment archive still block external claims.

The standalone planar-MOC foundation is recorded in
[`moc_primitive_validation_v1.json`](moc_primitive_validation_v1.json). It is
kept outside the public product lanes until a first-cell assembler demonstrates
closed topology and grid/refinement convergence.

The provider-comparison preflight is recorded in
[`provider_comparison_preflight_v1.json`](provider_comparison_preflight_v1.json).
It confirms that the two visual providers expose only
`core_radius_fraction` and `opacity_weight`, so the HOTWAKE Mach-disk operator
cannot be applied. The visual feature operator now has a branch-aware,
no-extrapolation comparator, but the 606-point corpus relation supplies no
explicit branch ID and the providers supply no Mach-disk feature or operating
branch channel, so its execution is recorded as blocked. It also keeps BSUV2, EMAP, and ALSI in their declared
sensor-space or band-integrated measurement spaces instead of comparing them
to the synthetic intrinsic signature table. The gray ray-transfer provider now
passes the analytic local gate, while its external sensor-space comparison
remains pending. The spectral probe records explicit no-overlap and
partial-domain outcomes instead of extrapolating the synthetic providers; the
residuals remain diagnostic only. FPA remains an explicit downstream boundary
with no provider ID.

The exact local execution is preserved in
[`product_lane_validation_v1.json`](product_lane_validation_v1.json): VIS and
SIG each pass their independent local contract/operator checks, optical passes
the analytic gray-transfer gate, the ray-to-signature adapter passes its
synthetic lineage checks, and FPA passes its explicit downstream boundary
operators without a provider.

The canonical cold-jet benchmark now has a separate component diagnostic in
[`cj_uej_component_validation_v1.json`](cj_uej_component_validation_v1.json).
It applies the corpus probe-line operator to the bounded shock-cell zones and
reports pressure, scalar-speed proxy, and Mach residuals with coverage and
digitization weighting. The adapter keeps the source's `p0/pa` nozzle pressure
ratio distinct from the derived choked-exit pressure and records its explicit
near-sonic and total-temperature assumptions. This is quantitative supporting
evidence only: the claim remains proposed/not accepted because the current
solver is one construction cell, has no physical shock-train termination, and
does not expose a local-field or validated VIS product.

The reduced-order shock-train component has its own evidence record in
[`shock_train_component_validation_v1.json`](shock_train_component_validation_v1.json).
It records the explicit closure seed, physical/safety termination behavior,
cell-fidelity counts, corpus feature context, and sensitivity sweep. The
calibration/validation split is blocked because the recovered archive contains
one benchmark case; the closure and the visual lane therefore remain
experimental and `not_accepted`.

The recovered corpus changes that sentence for data availability, not for
product acceptance. Its own gate registry reports VIS, SIG, and RAY T1
component evidence as `ready` and their T2 product evidence as
`partial_evidence`; all three T0 contract gates are `outside_corpus`, and the
T3 cross-product gate is `synthetic_only`. Those statuses describe the corpus
alignment layer. The repository now has deterministic spectral-array
sampling, peak-normalization, band integration, atmospheric path transfer,
LOS/FOV integration, and detector-bandpass helpers. These are generic
downstream operators validated on synthetic fixtures; provider-bound observer,
path, detector, source, and threshold assets plus accepted product-specific
measurement mappings are still required before any of the ten comparisons can
be accepted.

## Working branch

The clean completion work is isolated on `work/validation-and-completion`,
created from the integrated local `main`. The original dirty
`feature/post-a1-implementation` worktree remains intentionally untouched.
The bounded provider, solver-boundary, and validation changes recorded here
are already committed on this completion branch; future higher-fidelity work
must branch from an explicitly accepted lane rather than mutate the basic
provider in place. Remote PRs #5, #6, and #7 are merged into remote `main`,
while this completion branch remains local and has not been pushed.

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
interpolation cases, the synthetic ray-to-signature operator checks, and the
negative FPA-advertisement boundary check. Its report intentionally remains
`release_ready: false` until external measurement-operator comparisons and
product-specific gate acceptance are complete.

The missing external archive is a release blocker, not a reason to weaken the
fidelity boundaries or synthesize replacement measurements.
