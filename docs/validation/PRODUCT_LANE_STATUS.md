# Product-lane acceptance status

This is the working release ledger for the completion branch. It separates
repository regression evidence from external validation evidence and keeps
solver fidelity attached to a provider profile.

## Current lanes

| Lane | Provider/product | Local evidence | External evidence | Claim ceiling |
| --- | --- | --- | --- | --- |
| `planar-moc-primitives-v1` | `plume.visual.planar-moc` -> `plume.visual.sectioned-tube@1` | Research-only lifecycle, retained planar field envelope, and claim-ceiling checks pass alongside the existing MOC diagnostic evidence | CJ-UEJ MOC diagnostic quantifies 10/19 centerline points (RMSE 0.06577) but remains not accepted; coupled reflected-field closure, production shock fitting, disjoint closure evidence, and provider-specific external validation remain pending | Research-only illustrative planar visualization; no production VIS/SIG/RAY/FPA claim |
| `shock-cell-basic-v1` | `plume.straight-analytical` and `plume.shock-cell-analytical` -> `plume.visual.sectioned-tube@1` | Both bounded visual providers pass contract, deterministic-serialization, conformance, finite/positive geometry, straight-axis, arc/extent, channel-shape, and claim-ceiling checks | Corpus structure is verified; provider-specific benchmark/operator comparison remains pending | Engineering-approximate straight visual geometry and named features only; no spectral, ray, detector, mixing, or curved-flow claim |
| `shock-cell-reduced-order-v1` | `plume.shock-train-reduced-order` -> `plume.visual.sectioned-tube@1` | Explicit calibration, physical-versus-safety termination, reduced-order geometry labels, visual-only capability, and canonical conformance checks pass | CJ-UEJ archive is verified; the same-phase pressure-extrema spacing operator is diagnostic-only, and the closure calibration/validation split remains blocked | Experimental visual envelope only; downstream cells are scaled reduced-order geometry; no resolved MOC, spectral, ray, detector, or FPA claim |
| `signature-table-mvp-v1` | `signature.table-lookup` -> `plume.signature.spectral-radiant-intensity@1` | Table shape, interpolation, no-extrapolation, fixed-angle exact-only tables, time-axis, partial-result, reproducible fixture digest, measurement-space mismatch guard, provenance, and conformance tests | Pending a verified source asset and intrinsic-signature evidence | Versioned table and interpolation behavior only; no geometry, ray field, atmosphere, optics, or detector claim |
| `washed-integral-v1` | `plume.visual.curved-integral` -> `plume.visual.sectioned-tube@1` | Canonical lifecycle, snapshot, curved sectioned-tube output, claim ceiling, and conformance tests pass | Provider-specific benchmark/operator comparison and curved-flow validation remain pending | Engineering-approximate curved visual geometry only; no spectral, ray, detector, or FPA claim |
| `optical-transfer-v1` | `plume.gray-ray-transfer` -> `plume.optical.spectral-ray-transfer@1` | Exact finite-cylinder intervals, homogeneous slab/chord transfer, layer separation, miss semantics, and analytic/refinement checks | External sensor/path comparisons remain pending; gray analytic evidence is not corpus validation | Homogeneous gray transfer through a straight constant-radius support only; no chemistry, atmosphere, detector, or FPA claim |
| `curved-optical-transfer-v1` | `plume.curved-gray-ray-transfer` -> `plume.optical.spectral-ray-transfer@1` | Curved sectioned-support path intersections and homogeneous gray segment composition pass local provider checks | Curved path/operator comparison and external validation remain pending | Gray engineering transfer through conservative piecewise capsule supports only; no resolved curved-flow radiation or detector claim |
| `focal-plane-array-v1` | No provider; validated downstream adapters and evaluation gallery | Explicit camera/optics identity, ray-to-pixel expected-electron integration, deterministic ADC expectation, source-bound projections, static gallery, and no-network interactive view pass local checks | Recovered corpus is hash-verified but has no FPA observation members; the separate alignment archive and camera/detector measurement contract remain pending | Deterministic expected-electron and expected-ADC-count views only; no externally validated FPA image, measured detector count, noise realization, or detection claim |

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

The FPA visualization/readiness record is preserved in
[`fpa_visualization_readiness_v1.json`](fpa_visualization_readiness_v1.json).
It makes the future detector-pixel-count measurement operator and required
camera/detector metadata explicit, while keeping the recovered corpus's lack
of FPA observation data as a blocker. A static or interactive FPA gallery is
therefore an evaluation surface over deterministic operator output, not an
external validation result.

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
[`moc_primitive_validation_v1.json`](moc_primitive_validation_v1.json). Its
reflected characteristic zone now has explicit connected one-perimeter mesh
evidence, the shock candidate records total-pressure loss, and a separate
prescribed-boundary C- continuation reaches the symmetry line. The validation
record also runs a solver-generated marched attached-shock reference with
closed-field and 9/17/33-sample refinement diagnostics, plus a three-cell
solver-generated chain reference and a three-cell prescribed-boundary planner
mock that check terminal-trace consumption and monotonic total-pressure
handoff; the typed normal-shock chain-stop probe also records its planner
handoff before physical termination. The reflected-zone shock probe is
domain-bounded and records the
expected upstream-field failure when the candidate shock exits that lattice;
the source-strip continuation extends that diagnostic domain under an explicit
constant-`K+` simple-wave assumption, but the separate boundary-trace
extension remains diagnostic-only. The report also records a terminal
source-window attempt after the full continuation reaches a characteristic
caustic, plus a bracketed constant-invariant shock closure attempt; the
canonical bracket does not straddle a centerline closure and is not promoted.
The same report also remeasures the solver-owned quasi-one-dimensional
free-boundary reference at declared 5/7/9 resolutions. Its fixed seam,
parameter, perimeter, scalar-root, mass-flow, and outlet-height gates pass,
while the rising embedded 2-D divergence diagnostic keeps the evidence
explicitly research-only and blocks chain promotion.
The latest caustic report additionally executes the solver-owned constant-
invariant simple-wave terminal lane: it verifies the exact event state,
attached-shock prefix, open post-shock zone, typed subsonic terminal, and the
one-step planner's exact incoming handoff. That lane remains explicitly
non-promotable until the physical caustic remesh and mixed-regime perimeter
are solved.
The reflected-zone shock entry point now drives the attached-shock march from
the solved reflected state/pressure callbacks and independently reports the
first outside-domain sample; the canonical attempt is expected to stop there,
so no continued cell is promoted from that result.
The caustic validation also adapts its converged old-family/restarted-family
bridge to the generic bounded upstream-source contract. The adapter preserves
one-sided branch selection and returns no state or pressure across the measured
gap; it is solver-owned research plumbing and does not promote an open caustic
band or expand the planar-MOC claim ceiling. A separate validation probe now
also covers an explicit centerline-conditioned Cauchy remesh and its one-step
shock-chain boundary; it passes the bounded source/topology and typed
upstream-field-stop checks while the canonical outer trace and physical closure
remain pending.
The same research lane now has a multi-cell sequence planner: the first
continued cell consumes the initial bounded remesh, and every later cell must
receive a distinct solver-produced remesh from the exact preceding handoff.
Remesh/source-strip reuse, missing providers, and upstream events become typed
non-physical boundaries; this does not promote the Cauchy lane or alter the
fast visualization/reference providers.
Later remesh requests must now also echo the exact incoming state/total-pressure
handoff; absent or changed provenance is rejected before a source domain can
be reused.
The committed validation report now records a three-cell research-only
sequence audit with two accepted remesh domains and a typed reuse stop; it does
not claim a physical caustic shock chain or provider readiness.
The latest report also exercises the explicit reflected-domain Cauchy remesh:
the prior single ``C-`` front is retained only as a reflection anchor, a new
outer source curve is required, exact handoff provenance is checked for the
fresh-domain sequence, and the bounded result remains research-only.
The same remesh now has an independent ``op.moc.reflected-domain-remesh``
measurement operator. It rechecks the raw incoming trace, polarity, reflection
seam, source rows, scalar pressure lineage, mesh topology, and bounded state
sampling, including the typed single-front reuse rejection. A passing audit is
still non-production: physical closure, canonical mixed-regime continuation,
and external validation remain open.
The same validation report now exercises a bounded scalar ambient-pressure
shoot against the actual post-shock outer perimeter. Its synthetic pressure
coordinate reaches a candidate root but the independent streamline-tangency
gate rejects it, while the reflected-zone adapter stops at the first missing
upstream sample. Neither bounded result is promoted to a physical cell.
The same report now runs the independent MOC shock-cell geometry and chain
operators over the prescribed field, solver-generated reference, and
three-cell planner mock. Those operators verify explicit perimeter topology,
geometry metrics, and supplied shock total-pressure loss, but they do not
create external observations or promote any fixture to a validated physical
cell.
The caustic continuation report also verifies the exact one-sided seed-to-new-
family-band anchor and carries a typed non-physical
``characteristic-caustic`` decision when the old-family bridge and
shock/entropy closure are absent. A family-band assembly failure is surfaced
as a restart failure rather than a successful open-boundary handoff. This is
continued-chain bookkeeping evidence, not physical first-cell closure.
The planner wrapper now records each exact post-shock handoff as a separate
planning step for both the reusable prescribed-boundary mock and the
solver-generated chain reference, and the terminal composite emits a mixed-regime perimeter
request carrying the scalar shock seam without inferring geometry from the
open supersonic zone. The callback-owned closure gate now rejects a missing or
mismatched subsonic field before attachment. Both additions remain
research-lane contracts. The terminal-reflection-patch chain adapter also
records the exact outgoing ``C-`` handoff as it enters the next shock solve and
the canonical validation case ends at the verified normal-shock decision
without appending a synthetic cell. The first-cell composite now joins the
strip and reflection patch into a measurable closed supersonic topology with
explicit shock/ambient/centerline/outgoing-trace edges, while retaining the
non-production closure and promotion gates.
The composite also emits a typed `OPEN_PHYSICAL_CLOSURE` chain decision, so
the planner can stop at that unresolved boundary without treating it as a
physical endpoint or silently dropping the handoff.
The terminal-reflection-patch handoff is also auditable through the generic
planner as a one-step upstream-coupled research run; it records the exact
boundary before invoking the solver and cannot reuse the finite patch domain
for a later cell.
Each planner step also records a deterministic fingerprint of its complete
state/total-pressure handoff, and the generic chain rejects a boundary called a
`centerline-trace` unless its samples satisfy `y=0` and `theta=0`. These are
audit and fidelity-boundary checks; they do not promote the planner mock or
change the canonical MOC closure status.
It remains outside the public product lanes
until the solver-generated shock is coupled to the reflected upstream
state/pressure field, the next-cell shock fit is solved, and disjoint
measurement-space validation is accepted. The shared averaged-characteristic
interface now has zero residual; the separate direct lip-ray diagnostic
differs by 0.1405629941 m and is not promoted into the combined mesh.

The provider-comparison preflight is recorded in
[`provider_comparison_preflight_v1.json`](provider_comparison_preflight_v1.json).
It confirms that the two visual providers expose only
`core_radius_fraction` and `opacity_weight`, so the HOTWAKE Mach-disk operator
cannot be applied. The visual feature operator now has a branch-aware,
no-extrapolation comparator, but the 606-point corpus relation supplies no
explicit branch ID and the providers supply no Mach-disk feature or operating
branch channel, so its execution is recorded as blocked. It also keeps BSUV2, EMAP, and ALSI in their declared
sensor-space or band-integrated measurement spaces instead of comparing them
to the synthetic intrinsic signature table. The typed spectral comparison
boundary now blocks cross-space pairs before residual calculation, and the
signature lane records the local content digest for its synthetic table
fixture without presenting that digest as experimental source provenance. The gray
ray-transfer provider now passes the analytic local gate, while its same-unit
BSUV2 probe remains a no-overlap diagnostic pending provider-bound LOS/FOV and
source/path scenario binding. FPA remains an explicit downstream boundary with
no provider ID.

The exact next-input and acceptance requirements for the ten blocked
provider-bound comparisons are tracked in
[`provider_validation_acquisition_matrix_v1.md`](provider_validation_acquisition_matrix_v1.md).

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
one benchmark case, which the machine-checked split contract keeps explicitly
unassigned rather than reusing as both calibration and validation. The solver
now exposes an explicit covariance-parameter order and a finite-difference
output-uncertainty diagnostic, but the engineering seed contains no calibrated
covariance artifact, so the uncertainty result is
`not-available-no-calibration-covariance`. The closure and the visual lane
therefore remain experimental and `not_accepted`. The report also runs the
internal `op.reduce.pressure-extrema-spacing` operator separately for minimum
and maximum phases. It pairs the overlapping prefix of observed same-phase
spacing with reduced-order cell lengths and carries axial digitization
uncertainty, but performs no origin fit or cell-center assignment; its result
is diagnostic-only and does not identify physical train cells.

The higher-fidelity CJ-UEJ MOC comparison is intentionally a separate record in
[`moc_cj_uej_component_validation_v1.json`](moc_cj_uej_component_validation_v1.json).
It does not reuse the reduced-order solver's zones or promote its residuals into
the visual lane.

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
