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
- explicit caller-bound LTE population closures from frozen-mixture states,
  declared transition data, and caller-supplied partition functions;
- straight and separately labeled curved gray transfer;
- atmospheric layers as caller-owned measurement operators;
- mission-time visual/signature evaluators;
- direct construction of exact, compatible Signature timelines from mission
  samples for downstream angular heatmaps and masked traces;
- direct construction of exact, compatible FPA timelines from mission samples
  with one pixel geometry and detector response, preserving per-sample ray,
  exposure, digitization, and snapshot lineage;
- exact angular heatmaps, direction traces, source trajectories, and typed
  point queries that preserve result IDs, status, masks, and uncertainty.
- deterministic Signature timeline galleries that render those exact sampled
  views as multi-time angular heatmaps, masked direction traces, source
  trajectories, lineage-preserving CSV tables, and a source-bound manifest;
  the gallery is presentation-only and performs no temporal interpolation.

The next promotion boundary requires a source-bound resolved radiation model
and provider-bound measurement evidence. The LTE population closure is now a
source-bound spectral-engineering path, but it still requires caller-supplied
transition cross-sections and partition functions and does not model
reactions, non-LTE populations, atmosphere, or external validation. No table,
gray profile, or explicit line profile may be relabelled as validated
molecular spectroscopy, atmosphere-corrected radiance, or production
Signature evidence.

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
- [x] Provide an exact-time Signature timeline gallery with angular heatmaps,
      masked direction traces, source trajectory, CSV lineage, and guardrails.
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
- [x] Carry an explicit scalar supersonic-to-subsonic normal-shock state
      handoff, audit every thermodynamic field, and expose it to planar
      research visualization without treating it as placed shock geometry.
- [x] Compare the scalar transition requirement with the exact retained global
      frontier; preserve an independently audited typed failure when the
      required upstream state is absent.
- [x] Add an independently audited, spatially sampled shock-interface profile
      handoff for coupled-field inlet faces; consume it without projecting
      interior profiles and expose its geometry/metadata in the standardized
      planar visualization.
- [x] Expose the audited mixed-regime reference overlays in the standardized
      planar visualization: entropy-bearing supersonic patch, entropy handoff,
      control section, scalar perimeter, free boundary, and terminal seam;
      retain residuals and promotion stops as diagnostics.
- [x] Add a caller-bound LTE population closure that derives explicit line
      optical depth from a frozen-mixture state and declared transition data;
      keep reactions, non-LTE inference, database lookup, and production
      claims blocked.
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

### P4.2 source-bound LTE population checkpoint

The Signature radiation seam now accepts an explicit
``LtePopulationClosure``. It binds a validated CHEM-0 frozen-mixture state to
a caller-supplied transition, partition function, integrated lower-state
absorption cross-section, and path length; it records lower/upper populations,
number densities, stimulated-emission factor, and the resulting Voigt line
optical depth. The derived line enters the existing straight ray-transfer and
Signature adapter without changing the provider identity. The claim ceiling
remains spectral engineering only: reactions, non-LTE populations, inferred
spectroscopy, atmosphere, detector, external validation, and production
claims remain blocked. The public frozen closure constructor now recomputes
those derived populations, densities, stimulated-emission factor, and optical
depth from the retained state and rejects inconsistent caller-provided values;
this protects provenance without widening the claim ceiling.

### P4.3 mission/FPA source-state lineage checkpoint

The mission-time FPA adapter now binds an upstream ray-transfer result to all
of the sampled mission state that contributes to its source context.  In
addition to exact mission time and source pose, the adapter independently
recomputes and checks the dynamic-state and ambient-state digests before
applying pixel geometry, detector response, exposure, or digitization.  A ray
field evaluated at the right time and pose but with stale throttle, propellant,
engine-mode, or atmospheric context is therefore rejected rather than being
presented as a valid downstream image.

This closes a lineage gap in the deterministic FPA composition seam only.  It
does not create a camera/detector observation, sample noise, or change the
FPA's expected-electron/expected-ADC claim ceiling.  Focused mission-product
tests cover stale dynamic and ambient contexts; external FPA measurement
evidence remains required for release.

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

The coupled-field result now also performs a strict scalar-to-frontier
compatibility check. It compares the pressure-matching transition's required
upstream Mach/static-pressure state with the exact downstream states retained
on the global Euler shock frontier. The actual case records
``transonic-required-upstream-state-not-retained-on-frontier`` (required Mach
about 3.02 versus retained frontier Mach about 1.49--1.58), with the nearest
frontier point and residuals preserved. A pressure-compatible research case
records ``transonic-frontier-check-not-required``. The independent coupled-field
operator re-derives this comparison and the planar visualization exposes it as
a diagnostic. This prevents the scalar branch from being mistaken for a
placed transition; the next P2.2 slice still has to solve a solver-owned
transonic placement and the surrounding mixed-regime field without fabricating
an absent state or relaxing the fidelity gate.

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

### Solver-owned shock-cell fit measurement checkpoint

The production-fit validation lane now exposes
``measure_moc_production_shock_cell_fit``. It binds the solver-retained shock
path to the candidate field, independently re-runs the raw MOC shock-cell
geometry/topology/pressure measurement, and reports the resulting axial extent
and ``axial_length_m`` through the standardized measurement record. A tampered
fit path is rejected rather than measured against a different field boundary.

This closes the measurement/provenance seam for a research shock-cell fit; it
does not make the length an accepted physical first-cell length. Canonical
reflected/mixed-regime closure, refinement-stable length evidence, disjoint
external comparison, and the final production gates remain open.

### Production-fit visualization checkpoint

The standardized planar-MOC visualization now recognizes a solver-generated
shock-cell fit candidate and adds its retained fitted boundary as a distinct
research-only path. The bundle reports the fit status, requested axial
interval, solver shock-path span, promotion blockers, and an explicit
``production_fit_physical_length_accepted=false`` diagnostic. This keeps the
candidate geometry inspectable in the Visualization product without allowing
the display envelope to imply a production Signature or physical-cell claim.
The adapter also requires the candidate samples to be strictly downstream
ordered before drawing the path or calculating its displayed axial span;
unordered or duplicate-axial samples remain unavailable with an explicit
warning.

### Signature boundary checkpoint

When the standardized bundle represents a solver-generated shock-cell fit,
the Signature assessment retains the existing planar-MOC transport block and
adds the explicit missing-physical-length reason. An optical profile cannot
turn that candidate into a radiance result; a planar field/ray provider and
accepted physical-length evidence are still required before Signature or FPA
consumption.

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

### Coupled-Euler characteristic-inlet checkpoint

The coupled field now has an explicit ``subsonic-characteristic`` inlet mode
beside the retained ``full-state-rusanov`` research mode.  In the
characteristic mode, the control section supplies total pressure, total
temperature, and flow direction while the interior state supplies the
outgoing acoustic invariant; the boundary state is solved from the resulting
subsonic Mach root.  The independent field audit re-derives that boundary
state rather than assuming the full-state inlet flux.

The compatible research fixture converges under this mode and passes the
independent conservative-field audit while remaining research-only.  The
actual low-ambient case has no admissible subsonic root and now returns a
typed ``coupled-euler-inlet-characteristic-failure`` instead of silently
falling back to a lower-fidelity or overconstrained inlet.  This identifies
the next required physics step—a solver-owned transonic/supersonic branch or
shock-placement closure—and does not close the canonical field or authorize
shock-cell, Signature, FPA, or production claims.

### Scalar transonic branch-state checkpoint

The transonic pressure reference now optionally carries an explicit
``MocTransonicShockState`` when the caller supplies total temperature.  The
handoff reconstructs upstream supersonic and downstream subsonic static
temperature, density, sound speed, and velocity, while retaining total-pressure
loss and entropy increase.  The independent scalar audit rederives every
state field and rejects an altered handoff.  The coupled-Euler result binds
the handoff to its actual total-temperature input, and the planar
visualization exposes the branch status, Mach/pressure loss, and state values
as diagnostic metadata.

This is the correct state seam for a future solver-owned shock placement or
transonic branch.  It deliberately has no position, orientation, neighboring
characteristic field, mixing model, or free-boundary update; therefore it
remains research-only, cannot seed a continued chain, and does not change the
accepted physical-length or provider-validation gates.

The scalar audit now also recomputes normalized mass-flux, momentum-flux, and
energy-flux jump residuals from that reconstructed state.  The coupled-Euler
validator and planar visualization publish and compare those residuals, so a
state handoff cannot pass by matching pressure and Mach values while violating
the one-dimensional conservative shock seam.  This remains a local
thermodynamic audit; it is not evidence of a placed two-dimensional shock or a
closed global field.

### Transonic placement evidence checkpoint

A bounded numerical probe of the actual coupled-Euler case varied the
research free-boundary pressure relaxation from `0.05` through `0.5` and
extended the shape iterations from the default envelope.  The case remains
below the ambient-pressure gate: the best tested pressure residual was about
`115 kPa` against an ambient pressure of `212.166 kPa`, while the associated
normal-velocity residual fraction was about `0.168`, above the declared `0.05`
tolerance.  More aggressive shape relaxation either increased the residual or
triggered a residual/positivity failure.  The control-section static pressure
is about `564.587 kPa`, and the scalar branch audit independently requires a
supersonic-to-subsonic transition.

This evidence distinguishes a missing internal shock-placement/mixed-regime
boundary condition from a simple shape-iteration tuning problem.  The result
is retained as a research failure with promotion blocked; the next canonical
MOC packet must place and transport the transition in the two-dimensional
field, then re-run the coupled residual and refinement ladders.

### Caller-owned transonic geometry-binding checkpoint

The scalar transonic state now has a typed research seam for binding it to a
caller-owned shock point and normal.  The binding reports normal/tangential
velocity components and independently rechecks normalized mass, momentum, and
energy-flux residuals.  Misaligned geometry and tampered residuals are typed
failures rather than silently accepted state.

This seam is intentionally not a placement solver: it does not choose the
point or normal, connect neighboring characteristics, transport entropy
through the mixed-regime field, or create a continued shock-cell chain.  Its
geometry and audit flags keep physical closure, production claims, and
provider promotion disabled.  The next required implementation remains the
solver-owned two-dimensional shock placement/mixed-regime closure, followed
by disjoint validation and accepted provider comparisons.

### Scalar post-shock downstream-field checkpoint

The coupled constant-gamma research lane now accepts an explicitly audited
caller-bound scalar normal-shock geometry as a ``scalar-normal-shock-branch``
inlet.  It converts the audited downstream state into conservative inlet
states, solves the bounded downstream Euler/free-boundary field, and has an
independent audit that rederives both the branch geometry and the field fluxes.
The actual low-ambient fixture reaches local downstream residual, tangency,
entropy, and audit gates through this mode.

This is a downstream branch experiment, not global plume closure: the
upstream characteristic field and the shock's placement inside that field are
still absent.  The branch is therefore retained as research-only, remains
blocked from chain promotion and production claims, and is visualized only as
a caller-bound marker rather than a fitted global shock boundary.

The next research seam now has a bounded solver-owned field attachment.  It
selects a retained upstream characteristic node whose Mach, flow direction,
gamma, static pressure, and total-pressure lineage match the audited scalar
branch, binds the normal-shock geometry at that node, and independently
remeasures both the selection and geometry.  This is evidence that the scalar
branch can be connected to a valid local field sample; it is not a placed
global shock, a closed mixed-regime field, or a production shock-cell input.
The standardized planar visualization can now consume the attachment result
and exposes the retained upstream field, frontier, branch marker, selected
node marker, and match residuals without promoting any of them to a global
shock boundary.

### Bounded characteristic-transport evidence

The MOC research lane now carries a solver-owned bounded transport result from
the attached scalar branch through the retained characteristic field.  It
records exact samples, pressure lineage, characteristic geometry and
variable-entropy compatibility residuals, forward margins, and the first
unavailable point.  The independent measurement operator re-solves the
request and rechecks those values and the no-extrapolation boundary stop.

The standardized planar visualization consumes the same result without
reconstructing or extrapolating the path: it exposes a named transport trace,
the attachment marker, termination and residual diagnostics, and the first
unavailable point.  This makes the research seam inspectable through the
Visualization product while preserving the distinction between a bounded
transport trace and a globally placed shock.

This is useful evidence for field coverage and for the future placement solve,
but it is not a global shock placement or mixed-regime closure.  The result
therefore remains blocked from continued shock-cell chains, production
Signature/FPA claims, accepted physical length, and provider validation until
neighboring-field coupling, conservative closure, refinement, and disjoint
external validation are complete.

### Solver-owned bounded frontier-placement evidence

The MOC research lane now has a bounded solver-owned placement seam after
characteristic transport.  It searches for one in-domain intersection with a
typed neighboring frontier and accepts only ``RESOLVED_PLANAR_MOC`` geometry.
At that point it interpolates the transported and frontier state/pressure
lineages, checks state and log-total-pressure seam residuals, binds the scalar
shock geometry to the frontier tangent, and independently re-solves and
remeasures the complete local result.

The seam fails closed for reduced-order or prescribed frontiers, ambiguous or
unreached intersections, mismatched lineages, and geometry-audit failures.
Even when the local placement evidence verifies, it remains research-only:
global reflected/mixed-regime closure, physical shock-cell length, continued
chain promotion, external validation, and production Signature/FPA claims are
still blocked.  The standardized Visualization adapter exposes the retained
transport, frontier, intersection marker, fidelity, seam residuals, and
promotion gates without presenting the local seam as a global shock boundary.

## Long-running execution board refresh — 2026-09-05

This board is the working handoff for the continuing integration goal.  It is
deliberately ordered so that missing validation assets or an open physical
closure cannot be hidden by a passing local test suite.

### Current position

The dedicated integration branch remains the active work surface; `main` is
unchanged.  The local candidate has clean, committed evidence for the five
Visualization lanes, mission-time composition, Signature point/timeline
views, gray/line source seams, deterministic ray/FPA operators, and the
research-only planar-MOC progression through bounded frontier placement.
The release manifest still reports `release_ready=false`.  No release tag or
production claim is authorized while any item below remains open.

The known release blockers are:

- the raw Version 8 validation archive, the separately named alignment archive,
  provider-bound outputs, and accepted product-specific measurement operators
  are not present in the workspace;
- the reduced-order shock train has no disjoint calibration/validation split,
  and pressure-extrema spacing remains diagnostic rather than physical cell
  evidence;
- the canonical planar-MOC reflected/mixed-regime field is not closed or
  independently validated;
- no accepted physical solver-length comparison exists for the first or
  continued shock cells; and
- the final release freeze must be regenerated for the final committed
  candidate before acceptance.

### Ordered work packets

| Packet | Next action | Required input | Exit condition |
| --- | --- | --- | --- |
| `P1` | Intake validation assets and bind measurement spaces | Owner-supplied archives, provider outputs, provenance, units, frames, operators | Digests and member checks pass; calibration and validation cases are disjoint; every comparison has an accepted operator and uncertainty record |
| `P2.2` | Replace the mapped transonic/reference seam with solver-owned reflected/mixed-regime closure | Resolved planar-MOC field, bounded placement result, coupled boundary/entropy law | Shock placement, C-/C+ frontier, ambient/centerline boundaries, entropy transport, conservative residuals, independent audit, and stable refinement all pass on the actual target case |
| `P3` | Fit first and continued physical shock cells | `P2.2` closure plus accepted physical observations | Typed cell fits report solver length, uncertainty, lineage, and an accepted disjoint physical-length comparison |
| `P4` | Run provider-bound VIS, SIG, RAY, and FPA comparisons | `P1` operator records and source-bound scenarios | Each product passes in its own measurement space without inheriting another lane's fidelity or claim ceiling |
| `P5` | Freeze, package, and release | Completed `P1`–`P4` evidence | Exact candidate `HEAD` is clean and frozen; full acceptance matrix, wheel/install smoke, and release manifest are green; only then may a tag be created |

The next implementation slice is `P2.2`.  It may consume the bounded
frontier-placement result only as a typed local handoff.  A placement that
does not reach the actual neighboring field, violates a seam, or encounters
an unreachable pressure target must return a typed stop.  It must never fall
back to the basic shock-cell solver, the reduced-order train, or the mapped
variable-entropy reference.  A successful local solve still remains
research-only until the complete field, independent audit, refinement ladder,
and external comparison gates pass together.

### Slice protocol

Every packet follows the same loop:

1. State the contract, input lineage, fidelity, and claim ceiling before
   editing solver or product code.
2. Implement one vertical slice with typed failure states and independent
   measurement where the result can influence promotion.
3. Add focused tests for success, invalid input, altered lineage, and the
   expected hard stop.  Update the relevant validation note and release
   manifest inputs in the same change.
4. Run the focused lane checks, then the full acceptance matrix at packet
   boundaries.  A passing test is evidence of implementation correctness,
   not evidence of physical or provider validation.
5. Commit one coherent slice, push the dedicated branch, and record the
   resulting status.  Do not tag until `P5` is green.

### Branch and merge rules

- Keep work on the dedicated integration branch until the packet exit
  condition is met.  Start each packet from the current `main` ancestry, but
  do not commit directly to `main`.
- Reconcile `main` or another outstanding branch only from a clean worktree;
  resolve conflicts by retaining the stricter fidelity boundary, explicit
  unavailable/masked values, and the narrower claim ceiling when branches
  disagree.
- Treat validation manifests, public schemas, and product adapters as
  contracts.  A merge conflict in one of those files is not resolved by
  choosing the version with more capabilities; the merged result must keep
  provenance, operator identity, and promotion guards intact.
- After a conflict resolution, rerun the affected lane and contract tests,
  `scripts.test_lanes --check`, static/documentation checks, and the release
  manifest before publishing the branch.

### Completion definition

The goal is complete only when the five Visualization lanes are standardized,
Signature and ray-transfer claims are source- and operator-bound, FPA is
validated in camera/detector measurement space, the canonical planar-MOC
field and physical cell fits have accepted independent evidence, all required
archives and disjoint splits are verified, and the exact frozen candidate
reports `release_ready=true`.  Until then, the correct outcome is a clean,
reproducible integration candidate with visible research and validation
stops—not a production release.

### Solver-owned shock-interface handoff checkpoint

The next P2.2a seam now consumes the verified bounded placement and carries an
explicit upstream/downstream interface record.  It reuses the exact placement
point, scalar shock normal, upstream total-pressure lineage, and resolved
frontier identity, then derives a subsonic downstream sample from the audited
Rankine--Hugoniot state.  Its independent audit rederives the placement,
geometry, both upstream lineages, pressure loss, and downstream state.

The interface deliberately uses a scalar sample type for both sides.  The
upstream MOC ``CharacteristicState`` remains supersonic-only; the downstream
subsonic state is therefore not forced into the compatibility-network type.
This prevents an invalid regime crossing from being hidden as a normal MOC
node.  The standardized planar visualization exposes the interface normal,
upstream/downstream Mach, static/total pressure, gamma, audit, and promotion
flags.  The handoff remains research-only: it does not solve the surrounding
mixed-regime field, ambient/free boundary, refinement ladder, physical cell
length, or external product comparison.

The next P2.2b slice is to consume this handoff in the coupled reflected
field solve and close the actual pressure/tangency seam.  A failed or
unreachable interface must remain a typed stop; it must not fall back to the
basic, reduced-order, or mapped variable-entropy lanes.

### Coupled-field interface-inlet checkpoint

The coupled constant-gamma research field now exposes an explicit
``audited-shock-interface`` inlet mode.  It consumes the audited downstream
sample, reconstructs the conservative inlet state from the retained total
pressure, Mach number, flow angle, gamma, total temperature, and gas
constant, and independently remeasures the interface before iteration.

The mode accepts only an interface whose placement point is on the coupled
field inlet section.  An interior placement is returned as the typed
``INLET_SHOCK_INTERFACE_FAILURE`` stop; it is not projected to the inlet and
does not fall back to ``scalar-normal-shock-branch`` or any lower-fidelity
lane.  The standardized planar visualization now shows the consumed normal,
interface samples, audit state, and explicit promotion flags.

This closes a solver-to-field handoff contract, not the physical product
claim.  The coupled field still needs an interior placed interface, actual
pressure/tangency closure at that interface, independent refinement, physical
shock-cell length comparison, and external validation before any promotion.

### Spatial shock-interface profile checkpoint

The coupled field now also accepts a typed, independently audited profile of
paired upstream/downstream samples when the profile is a spatial cross-section
on the field inlet.  The solver interpolates the downstream profile onto its
inlet faces and retains the exact profile contract in the result.  An interior
profile, endpoint mismatch, normal mismatch, or failed profile audit returns a
typed stop in that ordinary inlet mode; the profile is never projected or
silently replaced by the scalar handoff.  A distinct
``audited-interior-shock-interface-profile`` research mode now starts a new
downstream conservative field at the exact retained profile cross-section.
The upstream control-section field remains a separate domain, and the new
mode preserves the full profile identity and independent audit rather than
pretending that the profile is a global shock surface.

The standardized planar visualization exposes the consumed profile as a named
inlet path and reports its sample count, cross-section, ordinate bounds,
normal, profile identity, and consumed state.  This advances the interior
handoff and downstream-field contract only.  It does not establish a full
surrounding shock surface, canonical mixed-regime closure, physical
shock-cell length, or a production claim.

### Mixed-regime reference overlay checkpoint

The standardized planar-MOC adapter now follows a global-to-mixed-regime
research result through its exact retained closure and draws the downstream
reference as named overlays: the entropy-bearing supersonic patch, the
shock-interface entropy handoff, the control section, the scalar perimeter,
the variable-entropy/free-boundary path, and a terminal seam marker.  The
bundle also records the reference model identity, station counts, iteration
count, residual channels, sample counts, and promotion flags.

These overlays make the current higher-fidelity reference inspectable beside
the upstream field without treating its mapped continuity/entropy model as a
canonical two-dimensional Euler closure.  They remain research diagnostics;
the P2 physical-closure gate, P3 physical-length gate, and all provider-bound
release gates are unchanged.

### Global transonic-frontier preflight checkpoint

The coupled constant-gamma field now performs a solver-owned preflight for
the ordinary full-state and subsonic-characteristic inlet modes.  When the
control-section/ambient seam requires a scalar transonic transition, the
preflight compares the required upstream Mach, static pressure, and total
pressure against the exact retained global-Euler shock frontier.  If that
state is absent, the request returns the typed
``TRANSONIC_FRONTIER_FAILURE`` stop before any downstream field iteration.
The result retains the transition, independent transition audit, control
section compatibility, pressure budget, and frontier comparison for
diagnosis; it does not synthesize a state, project a shock, or select a
lower-fidelity branch.

The independent coupled-field audit recognizes this stop and rechecks the
frontier comparison without attempting to audit a field that was never
solved.  The actual global target now fails at the missing transonic state
seam with promotion blocked, while compatible research fixtures and explicit
caller-bound scalar/profile handoffs remain available as separate research
lanes.  This is a stricter closure boundary, not completion of P2.2: the
solver still needs a two-dimensional placed interface, pressure/tangency
closure, refinement evidence, physical shock-cell length, and external
validation.

### Solver-owned normal-shock profile-builder checkpoint

The next handoff slice adds a typed profile builder for the case where a
caller already has an ordered supersonic upstream cross-section.  The builder
requires one retained interface normal and rejects missing samples, unordered
ordinates, mixed gamma, non-supersonic input, thermodynamic inconsistency, or
flow/normal misalignment.  It derives each downstream sample through the
existing normal-shock primitive, preserves the exact cross-section identity,
and runs an independent rederivation of the Rankine--Hugoniot mapping before
reporting a converged profile.

The profile is now a reusable coupled-field input with explicit build status,
sample-level residuals, independent audit, and promotion flags.  Its
acceptance still means only a local cross-section handoff: it does not place
the profile in the global Euler field, solve the surrounding pressure/
tangency or free-boundary closure, establish physical shock-cell length, or
authorize production Visualization, Signature, or FPA claims.  The next
solver-owned slice remains an actual placed interface and coupled-field seam
on the target case, followed by refinement and provider-bound validation.

### Global physical-field-bound interface checkpoint

The target global physical field now has a typed bridge into the transonic
interface contract.  Given caller-selected points on one retained field
cross-section, the bridge reads the field's exact state and total-pressure
sampler at every point, rejects points outside the closed sampled domain, and
derives the downstream normal-shock profile without projecting or fabricating
an upstream state.  A second audit re-samples the same physical field and
rederives the profile before the result is accepted.

The target-case test consumes this field-bound profile through the distinct
``audited-interior-shock-interface-profile`` coupled-field mode.  The coupled
solver now reaches its downstream free-boundary iteration with the profile
marked consumed and conservative states retained; the actual pressure/
tangency/free-boundary solve still fails closed at its later residual gate.
This is evidence of a real field-to-solver handoff, not completion of P2.2.
The next slice must choose and validate an interior interface from a
solver-owned placement rule, then close the downstream pressure/tangency seam
and its refinement ladder before any shock-cell or product promotion.

### Interior-profile mesh initialization checkpoint

The coupled research solver now preserves the exact retained profile height
when an ``audited-interior-shock-interface-profile`` starts a downstream
field.  Previously, the first downstream free-boundary column reused the
upstream mixed-regime reference's outlet height, which could be unrelated to
the profile cross-section and collapse the initial mesh before iteration.  The
first downstream mesh column is now initialized from the profile's retained
ordinate span, with a regression assertion on the target handoff.

This is a numerical-boundary correction: the target case still fails its
pressure/tangency residual gate, so local field closure, canonical reflected
closure, physical shock-cell fitting, and production promotion remain open.

### Solver-owned physical-field placement checkpoint

The field-to-interface bridge now has a solver-owned placement rule.  It
starts after the retained shock endpoint, enumerates the closed field's
retained cell-strip midpoints, selects the midpoint nearest the declared
post-shock fraction, and accepts only a contiguous vertical interval whose
sampled states remain in the field, supersonic, and aligned with the declared
interface normal.  The selected samples are then passed through the existing
audited normal-shock profile builder.

The actual global field selects a cross-section near ``x=5.4957 m`` with ten
exact field samples; an independent operator reproduces the candidate order,
cross-section, sample points, regime checks, and profile audit.  Tampering with
the selected cross-section is rejected.  This removes caller-selected
geometry from the next handoff, but it remains a research interface profile:
the coupled pressure/tangency solve, refinement, physical shock-cell length,
and provider-bound validation are still open.

### Coupled-lane solver-owned handoff checkpoint

The coupled-Euler request now has a distinct
``solver-owned-interior-shock-interface-profile`` mode that consumes the
audited field-placement result itself.  The request retains the placement
identity and derived profile; the solver rechecks the placement/profile audit,
starts the downstream mesh at the retained cross-section, and reports both
placement and profile consumption.  Invalid or tampered placement results
return a typed inlet-placement failure, with no caller-selected profile or
lower-fidelity fallback.

The actual target reaches the coupled conservative field and remains blocked
only at its later pressure/tangency/free-boundary residual gate.  This closes
the direct contract handoff, not the P2 physical-closure gate; refinement,
physical shock-cell lengths, and external product validation remain open.
The consumer also re-runs the placement audit at the coupled boundary, so a
tampered cached result is rejected before any field iteration.

### Coupled-lane physical entrance-seam diagnostic

The first target-case pressure/tangency probe after the solver-owned handoff
shows that the remaining failure is a boundary-design seam, not a missing
iteration budget.  A full-span field profile with 60 shape iterations drives
the conservative residual below the declared local tolerance and reduces the
downstream top-boundary pressure residuals to roughly ``11 kPa``, but the
profile entrance still carries an approximately ``232 kPa`` pressure jump and
the maximum normal-velocity fraction remains about ``0.079`` against the
declared ``0.05`` gate.  Extending the downstream window improves the relaxed
tail but does not remove the entrance discontinuity.

The reason is physical and contractual: the retained cross-section profile is
an internal shock/interface handoff, while the current finite-volume lane
treats its upper edge as an ambient-pressure material streamline from the
first station.  An interior profile must therefore not be reinterpreted as a
closed free boundary.  The next P2.2 implementation slice must carry an
explicit placed shock/front and its neighboring mixed-regime/free-boundary
conditions, then re-run independent residual and refinement audits.  Increasing
shape iterations, changing relaxation, or accepting only the downstream tail
would weaken the closure gate and is not an acceptable promotion path.

### Solver-owned full-span boundary guard

The solver-owned placement audit now distinguishes an auditable interior
cross-section from a profile that spans the complete retained physical-field
interval.  The coupled solver-owned inlet consumes only the latter, so the
default margin-sampled placement is rejected with a typed placement failure
instead of being treated as an ambient free-boundary span.  A zero-margin
placement passes the new independent full-span check and reaches the existing
pressure/tangency residual gate, where the target remains correctly blocked
by the unresolved internal-shock entrance seam.  The ordinary explicit
research-profile mode remains separate; this guard narrows the solver-owned
handoff without promoting the research lane.

The coupled request now also exposes an optional explicit downstream study
window.  Omitting it preserves the mixed-regime reference length; supplying
one records the override and effective length in the request lineage without
changing the upstream closure fingerprint.  This enables longer-tail
pressure/tangency studies to be compared honestly against the same entrance
seam.  It is a numerical-study control only: a longer window cannot waive the
entrance residual, physical closure, refinement, or promotion gates.

The next handoff now also has a distinct exact-field continuation contract.
The retained global physical field can remain supersonic downstream of an
oblique shock, so its sampled cross-section must not be sent through the
normal-shock profile builder a second time.  The new continuation profile
preserves the field state, flow angle, static pressure, total pressure, and
section geometry, then independently re-samples the source field.  The coupled
research solver now consumes it through a distinct inlet mode and the coupled
audit independently verifies that handoff.  It remains research-only until the
solver also closes the explicit shock/front and neighboring free-boundary
conditions; this handoff does not promote the downstream field by itself.

The continuation lane now also requires an explicit shock-front condition.
That condition binds the exact retained front, ambient/free-boundary path, and
centerline reflection path to the same source field and continuation profile,
then remeasures all four paths independently.  The coupled solver records and
audits that condition before it starts the downstream finite-volume field.
This closes the provenance and boundary-context seam; it does not claim that
the finite-volume entrance residual, transverse closure, refinement ladder,
physical shock-cell length, or external validation has passed.
