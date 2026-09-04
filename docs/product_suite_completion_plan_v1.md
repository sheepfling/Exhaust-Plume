# Exhaust-Plume product-suite completion plan v1

Status: active long-running execution plan.

This plan coordinates the three products and the solver lanes that feed them:

- **Visualization** — standardized, renderer-neutral inspection of geometry,
  regions, fields, paths, and diagnostics;
- **Signature** — wavelength-resolved spectral radiant intensity and its
  explicitly composed radiation/atmosphere operators;
- **Focal-plane array (FPA)** — downstream ray, camera, detector, pixel, and
  digitization composition.

The products are related, but they are not interchangeable. A visual envelope
does not become radiation, a Signature table does not become resolved
radiance, and an FPA image is not a plume provider. The release gate must
prove each boundary independently.

## Execution order

The work is organized as gated waves. A later wave may consume an earlier
product only through its declared contract and only at the earlier lane's
claim ceiling.

| Wave | Workstream | Exit evidence | Current position |
| --- | --- | --- | --- |
| 0 | Integration and branch hygiene | Clean dedicated branch, reconciled API/contracts, deterministic local checks | Active integration branch; `main` untouched |
| 1 | Standardized Visualization | Exactly five model bundles, common view schema, slices/views/paths, masks, galleries, and local acceptance artifacts | Local implementation complete; external provider comparisons pending |
| 2 | Mission-time product composition | Immutable state/cursor, explicit flow/optics/ray/FPA resolvers, exact source lineage, time-bound visual/signature/FPA views | Implemented; exact Signature point-query seam is available |
| 3 | Solver-fidelity separation | Independent basic, reduced-order, straight/washed, and planar-MOC lanes with claim ceilings and promotion guards | Basic/straight/washed local lanes exist; reduced-order and planar-MOC remain non-production |
| 4 | Physical Signature and optical chain | Chemistry/radiation/atmosphere inputs, resolved ray-transfer evidence, measurement-space operators, and accepted comparisons | Gray/table paths are local engineering evidence; physical/external gates remain open |
| 5 | FPA downstream product | Explicit camera geometry, detector response, expected electrons, ADC, metadata, and accepted camera/detector comparisons | Deterministic downstream boundary exists; no FPA provider or external image claim |
| 6 | Validation and release | Provider-bound evidence, disjoint calibration/validation, current manifests, CI, package smoke, and `release_ready=true` | Blocked by the release gates listed below |

## Operating protocol

This is a long-running integration goal, so the repository is worked in
small, reviewable vertical slices:

- `main` is the integration reference; feature work stays on a dedicated
  branch. The current integration candidate can continue on its dedicated
  work branch and be published to the integration branch without changing
  `main` until the release gates are green.
- Every slice begins with a contract and fidelity check, then changes the
  smallest necessary implementation surface, adds focused tests, updates the
  applicable plan or validation notes, and records the release evidence it
  produced.
- Commits should represent one coherent slice: contract, implementation,
  tests, and documentation move together. Merge-conflict resolution must
  preserve the stricter claim ceiling when two branches disagree.
- After each slice, run the focused lane tests and static checks. At wave
  boundaries, run the full release-facing matrix and inspect the generated
  manifest; a passing test run does not by itself authorize promotion.
- Do not create a release tag while any physical, provider, data, or package
  gate is open. Research-only outputs may be committed and pushed, but their
  status must remain visible in their contracts and reports.

## Dependency sequence for the remaining work

The remaining work is intentionally ordered by what must be true before the
next product can make a stronger claim:

1. **Validation intake.** Obtain the owner-supplied measurement archives and
   exact provider outputs, verify provenance and digests, assign disjoint
   calibration/validation cases, and register each measurement operator and
   coordinate convention.
2. **Canonical planar-MOC closure.** Replace boundary-conditioned research
   pieces with one solver-owned reflected/mixed-regime solve that closes the
   C- frontier, shock geometry, ambient attachment, centerline reflection,
   entropy transport, and Euler residuals together. Establish stable
   refinement and a terminal criterion before fitting cells. A named
   reflected/mild-attached case-ladder runner now provides separated local
   evidence for this work; it does not satisfy the canonical closure gate.
   The coupled research lane now treats entropy production as allowable shock
   evidence while retaining an independently checked entropy-loss gate; this
   improves physical interpretation but does not close the field.
3. **Production shock-cell fitting.** Fit the first and continued cells only
   from the typed, solver-generated frontier and closed field. Compare the
   resulting physical lengths and uncertainties to accepted observations;
   diagnostic pressure-extrema spacing is not sufficient.
4. **Provider-bound product validation.** Run the five Visualization lanes,
   Signature/ray-transfer operators, and FPA camera/detector chain against
   their own supplied measurement-space cases. Preserve each lane's fidelity
   and do not route unresolved MOC results backward into lower-fidelity
   products.
5. **Candidate acceptance and release.** Re-run the exact candidate commit
   through lane partitioning, full tests, static analysis, documentation,
   public-contract checks, wheel build, installed-wheel smoke, and the release
   manifest. Tag only when every gate reports green.

## Product workstreams

### Visualization

The standard surface is `plume.visual.sectioned-tube@1` plus the
renderer-neutral adapters and the five-lane model gallery. The five model
lanes remain separate:

1. `shock-cell-basic-v1` — fast straight engineering visualization;
2. `shock-cell-reduced-order-v1` — calibrated/reduced-order experimental
   envelope;
3. `straight-integral-v1` — straight top-hat reference/integral display;
4. `washed-integral-v1` — curved/washed engineering display;
5. `planar-moc-primitives-v1` — research-only planar field and projected
   comparison envelope.

The local completion bar is a deterministic bundle and gallery for every
lane, with orthographic slices, station inspectors, declared channels,
region/cell polygons, named boundary paths, diagnostics, provenance, and
invalid-value masking. A gallery may expose shock diamonds or regions only
when the source result declares them; it may not infer them from tessellation.

Remaining Visualization work is provider-bound comparison and any richer
uncertainty or observation overlays that can be supported by supplied data.
The planar-MOC adapter also exposes retained solver-owned shock height, wave
angle, flow turn, static/total-pressure ratios, and Rankine--Hugoniot residual
channels whenever the exact curve covers the displayed stations.  Partial
coverage remains explicitly unavailable; the adapter does not extrapolate or
turn missing evidence into zero.

### Signature

The Signature product is
`plume.signature.spectral-radiant-intensity@1` and reports intrinsic
spectral radiant intensity `Jλ [W sr⁻¹ m⁻¹]`. The resolved ray product is a
separate contract and reports source spectral radiance
`Lλ [W m⁻² sr⁻¹ m⁻¹]`.

The current local composition includes:

- deterministic table lookup with explicit wavelength, angular, and time
  policies;
- explicit homogeneous and sectioned gray source/absorption profiles;
- explicit LTE Planck line sources with caller-owned Voigt optical-depth
  primitives;
- straight and separately labeled curved gray transfer;
- atmospheric layers as caller-owned measurement operators;
- mission-time visual/signature evaluators;
- exact angular heatmaps, direction traces, source trajectories, and typed
  point queries that preserve result IDs, status, masks, and uncertainty.

The next promotion boundary requires a source-bound resolved radiation model
and provider-bound measurement evidence. The LTE line profile is a
spectral-engineering source primitive, not a chemistry or non-LTE population
solver; no table, gray profile, or explicit line profile may be relabelled as
validated molecular spectroscopy, atmosphere-corrected radiance, or
production Signature evidence.

### Focal-plane array

The FPA lane is downstream of a resolved ray-transfer result. Its explicit
chain is:

```text
ray transfer -> pixel geometry -> detector response -> expected electrons
             -> optional deterministic ADC expectation -> FPA visualization
```

The local boundary validates camera/optics identity, pixel mapping, spectral
response, exposure, invalid-ray propagation, expected noise variance, and
deterministic digitization. It does not sample noise, create detections, or
advertise an FPA provider.

FPA production evidence requires a supplied camera/detector observation
contract, a source-bound ray scenario, and a measurement-space comparison.
The recovered corpus currently contains no FPA observation members.

## Fidelity and promotion policy

The following rules apply to every wave:

- The basic shock-cell lane stays fast and bounded; higher-fidelity work does
  not mutate its configuration or claim ceiling.
- Reduced-order shock-train cells remain scaled/reduced-order until a
  disjoint calibration/validation split and physical cell-length evidence
  are accepted.
- Washed/curved visual and gray-transfer paths remain explicitly approximate
  until resolved curved-flow physics and validation exist.
- Planar MOC can expose research fields, frontiers, remeshes, and typed stops,
  but cannot promote a first cell or continued chain until the physical
  reflected-field/free-boundary closure, refinement, and independent
  validation gates pass.
- A missing, failed, or invalid value remains masked or gapped. It is never
  converted into a physical zero.
- Time evolution comes from an explicit state-specific resolver. A timeline
  cursor records and advances prescribed states; it does not infer throttle,
  chemistry, atmosphere, or optical properties.

## Validation intake and acceptance

Validation is accepted only in the measurement space named by the claim.
Each comparison must retain:

- dataset and case identity, provenance, license, and content digest;
- provider/model lane and exact source snapshot;
- measurement operator and coordinate/frame convention;
- calibration versus validation role and a disjoint case split;
- coverage, uncertainty, residual metric, tolerance, and applicability domain;
- limitations and an explicit evidence status.

Repository manifests record a Version 8 archive whose recorded SHA-256 is
`79c2a34dd4c43bd976ceb8773fdccd78a2592d903bf03ca57c2aef82f882e9aa`, with
138 members and 137 internal checksums. Those manifests are provenance
metadata only: the raw ZIP is not currently available in the workspace or
attachment path. A re-supplied archive must be checked against that record;
the digest alone does not prove provider acceptance. The separately named
alignment archive remains an outstanding input and must not be reconstructed
or claimed as present.

The required validation handoff is therefore explicit:

- archive plus member checksums and license/provenance record;
- provider/model snapshot and exact source-output identity;
- measurement operator, units, frame, sampling, and coordinate convention;
- case manifest with disjoint calibration and validation roles;
- uncertainty, coverage, tolerance, and applicability domain; and
- a typed evidence record that binds the comparison claim to all of the
  above.

## Release gates

The suite is releasable only when all of these conditions are true:

1. Every active lane has current local contract and deterministic evidence.
2. Visualization, Signature, ray-transfer, and FPA claims use their own
   provider-bound measurement operators.
3. The reduced-order solver has disjoint calibration and validation cases.
4. The planar-MOC first cell has complete physical closure, stable refinement,
   and an accepted independent comparison before production shock fitting.
5. The first-cell solver-length comparison is accepted; a diagnostic
   correlation is insufficient while closure is open.
6. The missing alignment archive or an equivalent user-supplied, provenance-
   verified replacement is available.
7. Full pytest, lane partitioning, Ruff, Pyright, documentation checks,
   public-contract asset checks, wheel build, and installed-wheel smoke pass
   on the exact candidate commit.
8. The release checkout is clean and the release freeze records that exact
   candidate `HEAD`; a documentation-only refresh may retain an older
   `validated_code_commit`, but it must not silently describe a different
   candidate.
9. The release manifest reports no promotion violation and
   `release_ready=true`.

Until then, the branch may be committed and pushed as an integration
candidate, but no production release tag or externally validated product
claim is authorized.

## Working checklist

- [x] Standardize all five computational visualization lanes.
- [x] Provide renderer-neutral slices, paths, heatmaps, galleries, and FPA
      boundary views.
- [x] Preserve mission time and source pose through visual, Signature, ray,
      and FPA composition seams.
- [x] Provide an exact Signature time/direction/wavelength point query.
- [x] Add exact-fingerprint binding for future high-fidelity promotion evidence
      without changing the current research-only claim ceiling.
- [x] Expose retained higher-fidelity MOC shock geometry, jump, pressure-loss,
      and residual channels through the common visualization bundle.
- [x] Expose retained coupled-Euler/free-boundary mesh cells and physical
      state channels through the same planar-MOC visualization lane.
- [x] Add a typed provider-bound comparison-evidence envelope requiring exact
      assets, operator identity, uncertainty, applicability, and disjoint cases.
- [x] Make provider-bound evidence ingestible through a strict preflight JSON
      handoff with exact provider-identity matching.
- [x] Keep reflected and mild-attached global-Euler resolution ladders as
      separately named, fingerprint-bound research cases.
- [x] Expose the retained downstream continuation law and a hard readiness
      gate for solver-owned reflected/mixed-regime boundary closure.
- [x] Add a fresh global-to-mixed-regime reference resolution ladder with
      independent case audits and explicit research-only promotion stops.
- [x] Add an isolated constant-gamma coupled Euler/free-boundary research
      lane with conservative-state, boundary, entropy, and positivity
      diagnostics; keep it below canonical and production promotion.
- [x] Add an independent re-derivation of the coupled-field flux, mesh,
      thermodynamic, entropy, and free-boundary diagnostics.
- [x] Add a fresh coupled-field case/resolution ladder that records finite
      independent audits and preserves the actual global-seam failure.
- [x] Add an isolated CHEM-0 frozen-mixture property/state contract with
      constant/tabulated heat capacity and composition conversion tests;
      keep it source-bound and production claims blocked.
- [x] Give CHEM-0 its own focused `thermochemistry-chem0-v1` test lane so
      its evidence cannot be conflated with shared gas contracts or
      downstream Signature claims.
- [x] Validate retained CHEM-0 states for normalized composition and ideal-gas
      identities before they can provide Signature source provenance.
- [x] Bind the coupled pressure-budget seam to an independently audited
      scalar transonic/normal-shock pressure reference; keep 2-D placement,
      mixed-regime closure, and chain promotion blocked.
- [x] Retain the scalar transition and its audit in every coupled-field result
      so the actual global pressure seam is part of the verified lineage.
- [ ] Close and independently validate the global planar-MOC physical field.
- [ ] Produce accepted physical shock-cell lengths and continued-chain fits.
- [ ] Bind external VIS/SIG/RAY/FPA cases to accepted measurement operators.
- [ ] Supply the separate alignment archive and disjoint reduced-order cases.
- [ ] Run the final candidate acceptance matrix and create the release tag
      only after the manifest turns green.

## Downstream-boundary readiness checkpoint

The global physical-closure result now reports the exact downstream turn law
retained by its selected remesh and exposes a separate
``downstream_boundary_closure_verified`` promotion gate.  The current result
is intentionally false for that gate because it uses the bounded research
compression-envelope law.  A future canonical reflected/mixed-regime solver
must provide a typed solver-owned downstream boundary result; renaming or
reusing the envelope cannot satisfy the gate.  The result also reports
concrete promotion blockers so production shock-cell fitting and release
reviews can distinguish a local exact-Euler field from a completed physical
closure.

The named reflected/mild-attached resolution runner now carries that same
downstream-boundary evidence at every case/resolution point: selected law,
readiness gate, blockers, and promotion-gate map.  This makes cross-case
review auditable without flattening distinct source bands or treating the
current compression-envelope law as a physical downstream closure.

The frontier-only production shock-cell fitter now carries the same downstream
readiness gate in its own promotion map.  A locally fitted candidate therefore
cannot become a production chain cell merely because later canonical,
refinement, or external evidence is attached while the downstream boundary is
still the research envelope.

## Typed downstream-boundary evidence checkpoint

The closure now retains a typed downstream-boundary evidence object.  It
preserves the solver-carried boundary points, state and pressure samples,
point/segment residuals, selected continuation-law identity, and separate
solver-owned, boundary-condition, and mixed-regime-field flags.  The existing
compression-envelope output is classified as research-only inside that object;
even relabeling its status cannot satisfy the closure gate.  This gives the
next canonical reflected/mixed-regime solver a concrete handoff contract while
keeping the current research field and production fitter below the release
boundary.

The downstream-boundary contract now also has an independent measurement
operator.  It rederives the point geometry, static pressure from total pressure
and local Mach/gamma, ambient-pressure residuals, and streamline-tangent
residuals from the retained samples.  A passing audit is recorded as
research-boundary evidence only: it does not solve the missing mixed-regime
field, authorize continued physical shock cells, or change the release gate.

## Active execution ledger — 2026-09-04

This section is the handoff for the active long-running goal. Work proceeds
in the order below; a later packet may consume an earlier packet only through
its typed contract and recorded claim ceiling.

| Packet | Scope | Depends on | Exit evidence | Status |
| --- | --- | --- | --- | --- |
| `P0` | Keep the integration candidate isolated, clean, and reproducible | — | Dedicated branch, committed changes, focused checks, full CI, current release provenance | In progress; branch `work/washed-integral-visual` is clean, `main` is untouched |
| `P1` | Intake and bind validation assets | Owner-supplied Version 8 archive, separate alignment archive, provider outputs | Verified archive/member digests, provenance/license, disjoint case manifest, typed measurement-operator records | Partially complete; the Version 8 digest/provenance record exists but its raw archive is absent here, and the alignment archive/provider-bound outputs are missing |
| `P2` | Close the canonical reflected planar-MOC/mixed-regime field | Solver-owned C-/C+ frontier, shock remesh, ambient attachment, centerline reflection, entropy transport | Coupled residual report, physical downstream boundary, independent re-derivation, stable case/resolution ladder | Active physics gate; current exact-Euler and variable-entropy results remain research references |
| `P3` | Fit the first and continued physical shock cells | `P2` closed field plus accepted physical observations | Solver-length/uncertainty comparison, disjoint validation, typed continued-chain cells | Blocked by `P2` and physical measurement evidence |
| `P4` | Bind the three products to their own measurement spaces | `P1`, stable lane contracts, source-bound scenarios | VIS feature/geometry comparison, SIG spectral/radiance comparison, RAY path comparison, FPA camera/detector comparison | Local boundaries pass; external product claims are pending |
| `P5` | Candidate acceptance and release | `P0`–`P4` | Full matrix on exact candidate `HEAD`, clean checkout, current freeze, wheel/install smoke, manifest `release_ready=true` | Blocked; no tag is authorized |

### Product completion bars

- **Visualization:** local completion is met for all five lanes. The next
  evidence is provider-bound geometry/feature comparison and, where supplied,
  uncertainty/observation overlays. The planar-MOC lane remains a research
  visualization and cannot backfill another lane.
- **Signature:** local table, Planck-continuum/gray, sectioned transfer, time,
  angular, and point-query paths are available with explicit units and masks.
  Completion requires a source-bound resolved radiance/chemistry path and a
  provider-bound spectral measurement comparison; a table or gray profile is
  not sufficient.
- **Focal-plane array:** the deterministic ray-to-pixel, detector, expected
  electron, ADC, and visualization boundary is available. Completion requires
  a camera/detector observation contract and a source-bound image comparison;
  deterministic expected counts are not measured-image evidence.

### P4.1 curved-optical evidence checkpoint

The curved gray-transfer lane is now recorded independently in the product
validation report and release manifest (`4f5a317`). Its provider identity,
snapshot serialization, hit/validity masks, and transfer outputs pass local
diagnostic checks. The piecewise-capsule path refinement remains explicitly
``nonmonotonic-observed-not-promoted``; the lane is therefore
``diagnostic-only`` and ``not-released-validation-pending``. Promotion still
requires a convergent curved-path/operator treatment and a provider-bound
observer/path/scenario comparison. This checkpoint does not change the
straight optical lane or add a curved-flow, chemistry, detector, or FPA claim.

### P2.1 evidence checkpoint

The first P2.1 evidence-plumbing slice is complete on the candidate branch at
`f219ae5`.  The terminal-patch planner now retains the independent
variable-entropy measurement as a typed field beside the exact solver
reference, validates reference identity, and exposes the full measurement
record in its report.  Focused MOC tests, Ruff, Pyright, and the scope-marker
check pass for this slice.  This closes the audit-retention subtask only; it
does not close the canonical reflected/mixed-regime field or authorize any
production claim.

The follow-on P2.1 evidence slice adds a conservative Euler residual audit to
that reference.  The solver and independent measurement now retain and
reproduce normalized mass, streamwise-momentum, transverse-momentum, energy,
and combined Euler residual maxima over the triangular field, with an explicit
"measured" flag.  The audit is intentionally diagnostic: nonzero residuals
identify the unresolved coupled closure, while the reference remains
non-canonical, chain promotion remains blocked, and production claims remain
false.  A tampered reported residual is rejected by the independent operator.

The next P2.1 evidence slice adds an independently measured resolution ladder
for the same reference.  The refinement operator requires a coarse-to-fine
sequence (the current regression case is 5/7/9 axial stations), one exact
request/handoff/control-section seam, fixed physical solver parameters, actual
mesh growth, independently reproduced conservative-Euler evidence, and stable
post-entrance free-boundary geometry at normalized axial locations.  The two
seeded entrance stations remain covered by the single-case audit but are not
silently labeled converged geometry.  The current ladder passes its local
research checks: node/cell counts grow from 21/27 to 37/51, outlet-height
deltas are zero, and post-entrance shape deltas are below `5e-10 m`.  The
conservative-Euler maxima (about 1.52, 2.60, and 3.14 across the cases) are
retained as diagnostic evidence and are deliberately not treated as a
monotone convergence claim.  This closes only numerical-sensitivity evidence
for the mapped reference; `physical_closure_verified`, canonical free-boundary
acceptance, chain promotion, and production claims remain false.

### P2.1 global-to-mixed-regime boundary-reference checkpoint

The candidate branch now binds a solver-owned downstream reference through
``build_reflected_domain_mixed_regime_boundary_request`` and
``solve_reflected_domain_mixed_regime_boundary``.  The builder derives the
open, strictly lossy supersonic patch from the retained global exact-Euler
shock curve, applies an explicit normal-shock terminal at its centerline
endpoint, builds the pressure-aware entropy handoff, and carries an explicit
axis-aligned control section.  The request includes the global-closure
fingerprint and exact incoming frontier; altered, missing, or reused frontier
data are rejected by the typed contract.

``measure_reflected_domain_mixed_regime_boundary`` independently checks the
closure identity, shock-curve binding, terminal normal-shock scalars,
pressure/entropy lineage, control-section identity, geometry, ambient
condition, and tangency.  It exposes independently reproduced mass,
streamwise-momentum, transverse-momentum, energy, and combined-Euler maxima
with per-channel coverage and validity masks, and detects a tampered reported
residual.  The resulting candidate is explicitly distinct from the existing
compression-envelope law.

This packet is deliberately a boundary reference, not the missing canonical
physics.  With the global closure's actual ambient pressure, the current
reference returns a typed strict-subsonic pressure-unreachable stop; a
separately declared reference ambient pressure can exercise the full mapped
variable-entropy audit.  In both cases ``mixed_regime_field_verified`` and
``physical_closure_verified`` remain false, chain promotion remains blocked,
and production claims remain false.  The next physics task is to replace this
mapped reference with a coupled reflected 2-D Euler/free-boundary solve and
then repeat the case/resolution ladder.

The follow-on reference-evidence slice now provides
``run_reflected_domain_mixed_regime_boundary_refinement`` and
``measure_reflected_domain_mixed_regime_boundary_refinement``.  A fresh 5/7/9
global shock-resolution run reuses one fingerprinted source band, derives a
new terminal and entropy handoff at each resolution, and applies the same
explicit 0.98 terminal-total-pressure reference fraction.  Independent audits
verify the closure/request seams, mesh growth, conservative-Euler channel
coverage, and post-entrance geometry/output sensitivity.  The regression run
passes with shock and downstream axial counts 5/7/9, node/cell counts 21/27,
29/39, and 37/51; the largest post-entrance shape and outlet-height delta is
about ``1.10e-6 m``.  Residual maxima increase across this mapped reference
ladder and remain diagnostic rather than a convergence or production claim.
The new evidence explicitly keeps canonical free-boundary/Euler, external,
physical-closure, chain-promotion, and production flags false.

The first coupled-field slice now lives in the separate
``coupled_euler_free_boundary`` module.  It carries an explicit total
temperature and gas constant, rejects nonuniform-gamma input, advances a
curvilinear finite-volume conservative Euler field, imposes a specified-
pressure material-streamline flux on the moving outer boundary, and updates
that boundary from the computed flow slope and pressure mismatch.  The
boundary flux has zero normal mass and energy transport; the ambient pressure
enters through the normal momentum flux.  It retains normalized
mass, momentum, energy, positivity, entropy-proxy, pressure, and normal-flow
diagnostics.  A pressure-compatible research fixture reaches local closure,
but the actual global case remains a typed ``FREE_BOUNDARY_FAILURE``: the
inherited control section enters with static pressure well above ambient and
cannot yet satisfy the coupled pressure/tangency seam.  This is useful physics
evidence and an explicit blocker, not a canonical closure or a production
shock-cell input.  An independent re-derivation now reconstructs the
curvilinear mesh, conservative face fluxes, thermodynamic state, entropy
bounds, and boundary reports from the retained field, and detects tampered
residual channels.  The follow-on ladder reruns fresh solver instances at
strictly growing ``(axial, transverse)`` meshes and audits every case.  The
actual global request remains ``CASE_FAILURE`` at the tested meshes because
the inherited control-section pressure/tangency seam is still open; the
pressure-compatible fixture reaches ``CONVERGED_RESEARCH_LADDER`` only as a
local research result.  Both paths retain finite diagnostic records and keep
physical closure, canonical Euler/free-boundary acceptance, external
validation, chain promotion, and production claims false.  The next physics
slice is to close and independently validate the actual global planar-MOC
field, not to reinterpret this ladder as a production shock-cell input.

An audit-driven boundary correction now gives the moving outer edge an explicit
``specified-pressure-material-streamline-v1`` flux: normal mass and energy
transport are zero and the ambient pressure enters only through the normal
momentum flux.  The independent audit re-derives that flux rather than calling
the solver helper.  The refined 6/3, 8/4, and 10/5 coupled cases now retain
finite residual audits under the explicit pseudo-time budget, while the actual
global case remains a typed free-boundary failure and the compatible case
remains local research evidence.  This corrects the boundary discretization;
it does not close the canonical mixed-regime field or alter any promotion gate.

The coupled-field request now also accepts an explicit optional downstream
static-pressure condition for a subsonic truncated outlet.  When supplied,
the finite-volume residual uses a solver-owned pressure ghost state; when it
is omitted, the prior extrapolated-outflow research behavior is retained for
backward compatibility.  The moving outer boundary is a separate
specified-pressure material streamline, not the outlet ghost condition.
Exercising the actual global case with the
ambient-pressure outlet leaves the result correctly typed as
``FREE_BOUNDARY_FAILURE``: the added terminal condition does not repair the
upstream pressure budget or authorize a canonical closure.  This is a
boundary-condition experiment recorded for the next 2-D solver slice, not a
relaxation of the promotion gates.

The coupled-field result now also retains a typed, independently recomputed
subsonic pressure-budget diagnostic.  It compares the ambient target against
the isentropic static-pressure bounds implied by the outer control-section
total pressure and reports the minimum additional total-pressure loss needed
to reach a target below the sonic-limit bound.  The actual global case is
explicitly ``below-isentropic-subsonic-pressure-bounds`` (about 47.5% minimum
additional total-pressure reduction for the current fixture), while the
compatible research fixture is within the bounds.  This is a one-dimensional
reachability diagnostic only: a future 2-D continued shock/mixing solve may
change the budget through entropy production, so the diagnostic explains the
next physics seam without becoming a closure or promotion gate.

The coupled request now binds that pressure budget to a separate scalar
`research-normal-shock-after-transonic-pressure-reference-v1`. When the
actual target is below the subsonic sonic bound, the reference solves the
upstream supersonic Mach number whose normal-shock downstream static pressure
matches the target and retains the resulting total-pressure loss and entropy
increase. An independent measurement rederives those scalar invariants. This
identifies an admissible entropy-producing mechanism for the next 2-D solver;
it does not place a shock in the retained mesh, close the mixed-regime field,
or authorize a continued physical cell.

The coupled result now also retains an explicit control-section/free-boundary
inlet-seam compatibility record.  It reports the signed and normalized
pressure jump, the outer control-section Mach and total pressure, and whether
the scalar transition would require a supersonic upstream state.  The actual
global case is therefore classified as ``TARGET_BELOW_CONTROL_SECTION`` with
an open inlet pressure seam, while the compatible research fixture is
``PRESSURE_MATCHED``.  The independent field audit re-derives this record and
the planar visualization exposes it as a diagnostic.  This makes the current
failure actionable without treating the scalar transition or a downstream
shape relaxation as a placed shock or a canonical closure.

### Explicit LTE line-source Signature checkpoint

The Signature bridge now accepts an explicit `LineRadiationProfile` alongside
the existing gray profiles. It derives an LTE Planck source and a summed
normalized Voigt absorption spectrum from caller-owned line-integrated optical
depths; Doppler widths may be derived from explicitly supplied temperature and
molecular mass. The line path is exposed through the existing ray-transfer
and far-field operators with a distinct adapter schema and
`radiation=spectral_engineering` metadata.

The bridge also accepts a `SectionedLineRadiationProfile`. It carries one
explicit LTE line profile per straight-support section, so source temperature,
line optical depth, and CHEM-0 source-state provenance can vary with position
without interpolation or chemistry inference. The existing piecewise transfer
operator consumes those section arrays, and the adapter records a distinct
sectioned-line schema and section count. This is still spectral-engineering
evidence: population closure, pressure broadening, non-LTE behavior, atmosphere,
and provider-bound validation remain outside the claim.

This advances the physical source contract without inventing chemistry: line
populations, composition, pressure-broadening inputs, non-LTE effects,
atmosphere, and external validation remain open. The new source path is
therefore locally tested but non-production, and the provider-bound Signature,
ray, FPA, and release gates remain unchanged.

### CHEM-0 frozen-mixture source-property checkpoint

An isolated `chem-0-explicit-frozen-mixture-v1` property contract now provides
explicit species definitions, molecular weights, normalized mass/mole-basis
conversion, and either constant or bounded tabulated `c_p(T)`. It derives
`R(Y)`, `c_v(T,Y)`, `gamma(T,Y)`, density, sound speed, mixture enthalpy, and a
bounded enthalpy-to-temperature inversion while retaining the exact frozen
composition in each derived state. The report identifies reactions as
disabled and keeps `production_claim_allowed=false`.

This is a cross-cutting CHEM-0 source primitive, not a chemistry or Signature
provider. The explicit LTE line bridge may bind its derived state for source
temperature and composition provenance, but no general flow/radiation
provider consumes the mixture yet. Formation/species entropy data, pressure
broadening, non-LTE populations, reacting/afterburning behavior, particle
loading, and provider-bound validation remain open. The property tests close
only the composition and thermodynamic identities for this declared local
lane.

After that gate, the order is fixed: close the coupled field (`P2`), run the
case/resolution ladder, fit cells (`P3`), acquire and execute provider-bound
VIS/SIG/RAY/FPA comparisons (`P4`), then refresh the exact-candidate freeze
and run the release matrix (`P5`). Missing data is an explicit blocker; it
must not be replaced with synthetic observations or a lower-fidelity solver.

### Current stop conditions

The goal must stop at the current claim ceiling when any of the following is
true: the downstream result is only a compression envelope; the independent
audit does not cover the retained field; the physical cell length has no
accepted comparison; a validation case is not disjoint from calibration; a
provider output is not in the claim's measurement space; an FPA result has no
camera/detector observation; or the release freeze does not identify the
candidate commit. In each case the result remains usable as scoped local or
research evidence, but it is not promoted.

### Cell-wise regime-evidence visualization checkpoint

The coupled-Euler visualization now exposes the solver-retained
``entropy_production_fraction_by_cell`` channel in the common planar field,
alongside explicit subsonic, near-sonic, and supersonic display masks.  The
near-sonic band is fixed at ``|M-1| <= 0.05`` and is recorded in the bundle
diagnostics so a renderer can show regime regions without guessing a
threshold.  The entropy map is independently rederived and audited per cell.

These channels make compression/transition evidence inspectable in the
visualization product, but they are not shock identification, radiance, or
production closure.  Missing channels remain unavailable; the coupled lane
still requires a solver-owned mixed-regime field, stable refinement, and
provider-bound validation before any promotion.

### Refinement-level entropy-map checkpoint

The coupled-Euler refinement measurement now requires every resolution case to
carry an independently verified per-cell entropy-production map.  It retains
the maximum production fraction per resolution and reports a dedicated
``entropy_production_maps_verified`` gate.  This prevents an aggregate
entropy scalar from masking a missing or altered cell-level field in a
research ladder.

The gate strengthens reproducibility evidence only.  It does not turn the
coupled ladder into a shock-resolved solution or close the canonical
mixed-regime/free-boundary, physical-length, or external-validation gates.

### Coupled-Euler lineage-builder checkpoint

The coupled-Euler lane now exposes an explicit builder and one-call solver
seam from a retained mixed-regime boundary reference.  The request carries
the exact upstream global-closure fingerprint as a first-class report field,
so a downstream field run cannot silently substitute a different control
section or closure snapshot.  The convenience solver returns the same typed
invalid-input and research-only results as the direct request path; it does
not fall back to a lower-fidelity solver.

This is contract and provenance plumbing for the next physics iteration, not
canonical closure.  The actual-ambient case remains below the coupled
pressure/tangency gate, the scalar transonic reference remains a diagnostic,
and chain promotion, external validation, and production claims remain
blocked.

### Coupled-Euler pressure-continuation checkpoint

The coupled-Euler research lane now exposes a separate pressure-target
continuation operator.  It runs a fresh, independently audited field solve for
each strictly decreasing ambient-pressure target, while retaining one exact
upstream global-closure fingerprint and all numerical controls.  The report
keeps the free-boundary residuals, outlet heights, scalar pressure-budget loss
fractions, solver statuses, and audit statuses aligned by target.  A compatible
control-section case can therefore be followed toward the actual ambient
target without reusing a prior field or silently changing the optional outlet
condition.

The current ladder passes independent diagnostic coverage and the expected
pressure-loss trend, but its actual-ambient endpoint remains a typed
free-boundary case failure.  The ladder's research evidence is useful for
locating the pressure/entropy closure seam; it does not satisfy canonical
mixed-regime closure, accepted physical cell length, external validation,
chain promotion, or production claims.
