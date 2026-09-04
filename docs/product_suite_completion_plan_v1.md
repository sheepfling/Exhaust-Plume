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
- straight and separately labeled curved gray transfer;
- atmospheric layers as caller-owned measurement operators;
- mission-time visual/signature evaluators;
- exact angular heatmaps, direction traces, source trajectories, and typed
  point queries that preserve result IDs, status, masks, and uncertainty.

The next promotion boundary requires a physically resolved source model and
provider-bound measurement evidence. No static table or gray profile may be
relabelled as chemistry, molecular spectroscopy, atmosphere-corrected
radiance, or production Signature evidence.

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
- [x] Add a typed provider-bound comparison-evidence envelope requiring exact
      assets, operator identity, uncertainty, applicability, and disjoint cases.
- [x] Make provider-bound evidence ingestible through a strict preflight JSON
      handoff with exact provider-identity matching.
- [x] Keep reflected and mild-attached global-Euler resolution ladders as
      separately named, fingerprint-bound research cases.
- [x] Expose the retained downstream continuation law and a hard readiness
      gate for solver-owned reflected/mixed-regime boundary closure.
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
