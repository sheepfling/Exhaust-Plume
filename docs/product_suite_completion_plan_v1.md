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
   The exact physical-field continuation handoff now binds a complete
   centerline-to-ambient coupled inlet profile to the retained shock-front
   condition, and the downstream research Euler lane consumes that profile
   without relabelling the interior continuation as a free boundary. This
   closes a boundary-context bookkeeping seam only; coupled residuals,
   refinement, and external validation remain open.
   The coupled Euler result now also retains the conservative inlet-face
   vector actually passed into the field solve. Its independent audit
   rederives the same vector from the front-conditioned physical profile and
   reports a typed inlet-seam failure when the retained faces are tampered
   with. This closes source-to-consumer evidence accounting only; it does not
   change the research-only claim ceiling or close the global field.
   A new global-to-coupled downstream orchestrator now binds a verified
   closure fingerprint to the constant-gamma coupled-Euler request and its
   independent audit. Compatible research cases can therefore be measured as
   locally coupled fields, while the actual ambient case retains its typed
   transonic-frontier failure. The orchestrator deliberately reports
   ``global_coupling_verified=false`` because downstream response is not yet
   iterated back into the upstream shock solve; no promotion gate is relaxed.
   It also accepts the independently audited physical continuation and
   shock-front handoff explicitly, allowing the exact field lineage to reach
   the downstream lane without a scalar fallback.
   The orchestrator now exposes a solver-owned exact-handoff path as well.
   When the coupled request selects the exact physical-field continuation
   mode without caller-supplied profiles, it derives a complete field
   placement, continuation profile, and neighboring shock-front condition
   from the retained global field and independently audits each component
   before consumption.  A handoff failure is typed and the request does not
   fall back to a scalar or lower-fidelity inlet.  This removes a caller-
   assembly seam; it does not establish downstream-to-upstream feedback,
   canonical mixed-regime closure, refinement, or promotion.
   The same orchestrator now exposes the solver-owned transonic-interface
   placement as a separate handoff.  In
   ``SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE`` mode it derives a
   full-span placement from the exact retained global field, requires the
   independently rederived full-field cross-section audit, and preserves that
   placement on the global result and report.  Caller-supplied placements must
   retain the exact field object and pass the same audit; partial-span or
   cross-field inputs return a typed physical-field handoff failure.  The
   coupled field may consume this placement as a local research candidate,
   but global feedback, canonical mixed-regime closure, physical shock-cell
   fitting, and product promotion remain closed.
   The exact physical-field mode now also consumes the retained ambient-
   neighbor path when downstream pressure or geometry profiles are omitted.
   Pressure targets are sampled at cell centers and ordinates at boundary
   nodes, with strict coverage and no extrapolation; the resolved request is
   retained on the coupled result and re-derived independently by the audit.
   A tampered source-owned profile produces a typed neighbor-profile failure.
   This closes solver-owned boundary-profile provenance only; it does not
   close the physical free boundary, global feedback, refinement, validation,
   or product-promotion gates.
   The global coupled candidate now also retains the independently measured
   solver-owned variable-entropy/mixed-regime reference beside the coupled
   Euler result.  Its request and closure object are checked for exact
   identity, and the reference status is serialized in the candidate report.
   The reference is deliberately not consumed as a coupled boundary
   condition; it remains a mapped lower-fidelity research result with
   canonical closure, chain-promotion, production, refinement, and external
   validation gates closed.
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
- explicit homogeneous atmospheric-path transfer through the Signature
  bridge, with per-mission-state layer resolvers and retained layer lineage;
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
- [x] Bind an explicit caller-owned atmospheric path to Signature and
      mission-time product samples without inferring altitude, chemistry,
      scattering, or external atmosphere state.
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
- [x] Add an exact-fingerprint global-frontier reconciliation request and
      solver-owned receipt seam; stop when no consumer is available, verify
      common station coverage across refinement cases, and keep accepted
      targets below global closure and production promotion.
- [x] Bind the accepted fine P2.2c field to the solver-owned first-cell fit
      and exact fresh global-Euler continued-chain handoff; retain explicit
      bridge, stage, and research-only promotion gates.
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

## Feedback-ladder consumption checkpoint

The exact-field downstream feedback ladder now keeps geometry-profile lineage
and geometry-profile consumption as separate aggregate gates (`bb1019d`).  A
profile that is merely aligned with the solver request cannot satisfy the
feedback result: every retained iteration must independently prove that the
geometry profile was consumed, alongside pressure-profile consumption,
response lineage, and the exact initial-state source.  This closes an evidence
accounting defect in the research ladder only; it does not turn the bounded
downstream iteration into upstream/global feedback or change the production
claim ceiling.

### P2.2 global-frontier consumer checkpoint

The downstream feedback proposal now has an explicit
``global-frontier-reconciliation-consumer-v1`` seam.  A reconciliation request
binds the exact global-closure fingerprint, immutable proposal fingerprint,
station frame, relaxed boundary ordinates, tangent targets, and pressure
targets.  A named solver-owned consumer must return a typed receipt that
retains every target exactly; a missing consumer is a typed stop and a changed
receipt is rejected.

An accepted receipt proves only that a solver-owned target was accepted for a
future global re-solve.  It does not mutate the original proposal, claim that
the global equations were consumed, produce a new field, close the physical
downstream boundary, fit a shock cell, or authorize a product claim.  The next
physics slice is the actual solver-owned reflected/mixed-regime consumer and
its independently audited re-solve; the current compression-envelope global
remesh remains unable to satisfy that gate.  The cross-resolution downstream
ladder now also retains a common-station-domain check and shared source-closure
lineage check, so a locally passing proposal cannot be compared across cases
when its target frames are disjoint or sourced from different closures.

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

### P4.4 explicit atmospheric-path Signature checkpoint

The Signature bridge now accepts a sequence of explicit homogeneous
``AtmosphericPathLayer`` values in near-observer-to-far-source order.  The
operator is applied after intrinsic ray integration so provider ray results
retain their canonical miss/validity semantics; the final Signature records
the path operator, layer IDs, layer digest, updated result identity, and a
restricted claim ceiling.  ``MissionSignatureEvaluator`` and
``MissionProductEvaluator`` can resolve those layers independently at every
mission state and retain them on the sampled product.

This is an explicit measurement-space operator, not an atmosphere model.  It
does not infer altitude, composition, scattering, line populations, or
provider-bound path conditions, and it does not create detector or FPA
evidence.  External atmospheric inputs and accepted provider comparisons
remain required for release.

### P4.5 lifecycle ray-to-FPA atmosphere/background checkpoint

The direct lifecycle ray-result-to-FPA adapter now preserves the result's
explicit background-transmittance matrix when a caller supplies background
spectral radiance.  It can also apply the same explicit homogeneous
atmospheric path operator used by Signature, including atmospheric
transmittance of the optional background term.  FPA images retain the path
operator identity, layer IDs, layer digest, source semantics, and downstream
visualization/operator-chain metadata.

This closes an adapter omission only.  Expected electrons and deterministic
ADC counts remain downstream expectations; no noise realization, detection,
camera provider, measured image, or external validation claim is introduced.

The mission-time FPA evaluator now also accepts state-resolved background
spectral radiance and atmospheric-path callbacks.  Each sample retains the
resolved matrices/layers and applies the same explicit operator chain, so
altitude- or time-dependent downstream conditions cannot be silently held
static across a mission timeline.

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

### P2.2 solver-owned pressure-profile compatibility checkpoint

The global-to-coupled pressure feedback path now has its own typed
compatibility record.  It evaluates every solver-owned downstream pressure
target against the isentropic subsonic budget implied by the outer
control-section total pressure, retaining the target extrema, below/within/
above counts, worst-case compatible total pressure, and required additional
loss fraction.  This closes an evidence-accounting gap: the prior ambient
pressure budget could be within bounds while a supplied feedback profile was
below the local sonic-limit budget.

The independent coupled-field audit rederives this profile diagnostic without
calling the model helper and verifies tamper detection.  A below-budget
profile remains valid research input for investigating shock and mixing
physics, but the diagnostic is deliberately non-gating and cannot turn the
global overlap response, physical closure, external validation, or production
claim gates green.  The next closure seam is still a solver-owned physical
transonic/frontier treatment that can account for the required entropy and
match the retained global boundary in measurement space.

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

### Current checkpoint — 2026-09-08

The latest pushed candidate is commit `5dff695` on
`work/washed-integral-visual`.  This slice retains the independently measured
solver-owned variable-entropy/mixed-regime reference on every global coupled
downstream candidate, checks exact request and closure identity, and reports
its research status without feeding the mapped reference into the coupled
Euler boundary condition.  The canonical reflected-field, global-feedback,
physical shock-length, provider-validation, and production gates remain
unchanged and closed.

Verification for this checkpoint is: 149 reflected-domain/MOC tests passed in
the combined targeted run, 3 report-contract tests passed, Ruff and Pyright
passed, and the checkout is clean and pushed.  The release audit is still
`release_ready=false`; the remaining blockers are missing provider-bound
measurement outputs and accepted operators, the absent disjoint reduced-order
calibration/validation split, the unverified alignment archive, open
canonical planar-MOC and physical shock-length closure, and a stale release
freeze that must be regenerated only after the final candidate is settled.

### Candidate evidence checkpoint — 2026-09-05

The earlier `57d23d501f75b96eca90ebb72beac1fa2daa83c6` checkpoint is
historical.  The documented code checkpoint is commit `23261ce`; the
subsequent pushed feedback-lineage slices are `d624784`, `bb1019d`, and
`3e0bdf2`.  The branch remains clean, but the release evidence must be
refreshed again after those later slices so the final candidate is described by
one exact `HEAD`:

- the full test matrix, build/install smoke, static checks, and lane-release
  validator must all be rerun against this exact `HEAD` before the final
  freeze;
- the latest completed full matrix for the active audit slice is
  **1,125 passed**, with the existing 18 warnings;
- the exact-field continuation slice records a solver-owned conservative
  warm-start source and fails closed when a coupled mesh center is outside the
  retained physical field; the downstream feedback ladder now separately
  verifies geometry-profile lineage and actual geometry-profile consumption;
- offline wheel build/install smoke, `scripts.test_lanes --check`, Ruff, and
  the repository scope-marker check all pass; and
- the release manifest remains `release_ready=false` until the external,
  physical, provider, and freeze gates below are satisfied.

The prior freeze and validated-code commits are stale relative to the active
candidate.  CI status is tracked from the pushed run for `HEAD`.  These local
and CI results are release evidence, not external physical validation, and
they do not change the open release blockers below.

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

### Like-for-like downstream shock-state checkpoint

The coupled lane now retains a second, separate compatibility record that
compares the scalar normal-shock branch's downstream Mach/static-pressure/
total-pressure state with the exact downstream states on the retained global
Euler frontier.  This corrects an evidence-accounting ambiguity in the older
pre-shock diagnostic, which intentionally asks whether the scalar required
upstream state is present on the post-shock frontier to expose the missing
incoming branch.  The new record is a like-for-like post-shock comparison and
does not replace or relax that lineage check.

On the actual target, the scalar branch predicts downstream Mach about 0.474
while the retained frontier remains supersonic at about 1.49--1.58.  The new
record therefore reports ``transonic-downstream-shock-state-not-retained-on-
frontier`` with the nearest point and pressure/Mach residuals, and the
independent coupled-field audit rederives the same result.  A compatible
research case reports ``transonic-shock-state-check-not-required``.  Both
records remain diagnostic-only: the missing solver-owned two-dimensional
interface, surrounding mixed-regime field, refinement, physical cell length,
and external validation gates are unchanged.

The standardized planar-MOC Visualization adapter now publishes this
downstream compatibility record alongside the existing scalar transition and
pre-shock frontier diagnostics.  It exposes the status, expected scalar
post-shock state, nearest retained frontier point, and residual channels as
named diagnostics without drawing the unmatched state as a physical interface.

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

### Solver-owned ambient-neighbor boundary-profile checkpoint

In exact physical-field continuation mode, the coupled solver now derives
missing downstream pressure and geometry profiles directly from the retained
shock-front condition's ambient-neighbor path.  Pressure is sampled only at
cell centers; geometry is sampled only at boundary nodes.  The request keeps
the source identifiers, aligned stations, and lower-ordinate frame, and the
global orchestrator retains this resolved request rather than reporting its
pre-resolution input.

The independent audit repeats the path interpolation without calling the
solver helper and detects a tampered pressure or geometry profile with a
typed ``PHYSICAL_FIELD_NEIGHBOR_PROFILE_FAILURE``.  Incomplete coverage,
frame mismatch, and extrapolation remain hard stops.  This is a provenance
and contract checkpoint for the research lane, not acceptance of the free
boundary or a promotion path into shock-cell, Signature, or FPA claims.

The exact-field continuation solve now also initializes coupled cell
states from the retained physical field at every mesh-cell center.  The
result records ``solver-owned-exact-physical-field-samples-v1`` as the
initial-state source, and an uncovered or nonphysical sample returns a
typed continuation failure instead of repeating inlet states.  This removes
an artificial inlet transient from the numerical warm start; it does not
close downstream-to-upstream feedback, canonical closure, refinement,
physical shock-cell length, or any product-promotion gate.

### Exact-field feedback-consumption checkpoint

The downstream feedback runner now distinguishes an exact physical-field
continuation run from the ordinary response-profile path.  When the caller
omits pressure and geometry feedback profiles, the first iteration is accepted
only when the coupled solver materializes both profiles from the retained
ambient-neighbor path, preserves the solver-owned source identifiers and
request object, and passes the independent neighbor-profile audit.  The next
iteration then consumes the explicitly generated profiles at their exact
cell-center and boundary-node stations.

On the compatible exact-field fixture, this closes the local research update
and reports ``CONVERGED_RESEARCH_PRESSURE_UPDATE`` with finite, independently
measured overlap residuals.  It does not set ``global_coupling_verified`` or
the downstream-boundary closure gate, and it cannot authorize continued-chain,
shock-cell, Signature, FPA, or external-validation claims.  The ordinary
response-feedback path remains separately typed and may still fail its local
pressure/tangency gate; it is not silently upgraded by this exact-field seam.

### Exact-field conservative warm-start checkpoint

The solver-owned physical-field continuation mode now samples the retained
closed field at every coupled cell center before the conservative Euler
iterations begin.  It converts the sampled Mach, flow angle, gamma, and total
pressure into conservative states and retains the source identifier in the
coupled result and report.  The inlet-face boundary states remain separately
consumed from the front-conditioned continuation profile; the warm start does
not replace that boundary contract.

Sampling is bounded and strict: a missing, out-of-domain, nonphysical, or
gamma-incompatible sample returns a typed continuation failure, with no
inlet-only fallback.  This reduces an initialization artifact while keeping
the field solver responsible for the final conservative residuals.  It is
not evidence of upstream/global feedback, canonical reflected closure,
refinement, accepted physical shock-cell length, provider validation, or
production Visualization, Signature, or FPA status.

The downstream feedback ladder now carries the same initial-state lineage
through every fresh exact-field iteration.  Selecting the solver-owned exact
continuation mode requires each retained coupled field to report the exact
physical-field sample source; a missing source is a typed fidelity failure,
not an inlet-only fallback.  This closes a multi-iteration provenance gap
while leaving the upstream/global re-solve and canonical closure gates open.

### Global/coupled downstream boundary-response checkpoint

The coupled-field result now retains one static-pressure sample for each
axial cell column adjacent to the retained free boundary.  The
global-to-coupled orchestrator uses those solver-owned adjacent-cell values
to reconstruct the boundary-station pressure comparison against the exact
global ambient-neighbor path over the shared x-domain.  The operator rejects
missing samples, non-monotone stations, and any coupled station outside the
retained global boundary; it does not extrapolate or silently clip the
response.

The response report carries matched points, coordinate and tangent residuals,
pressure residuals, normal-velocity residuals, signed correction offsets,
coverage, and tolerances.  On the compatible research fixture the overlap is
covered but its boundary path residual remains above the research tolerance,
so the result is a typed
``RESIDUAL_FAILURE`` diagnostic.  ``global_coupling_verified`` and the
downstream-boundary closure gate remain false.  This is the measurement seam
needed by the next fixed-point/global-frontier iteration; it is not a
canonical closure, refinement result, physical shock-cell length, or product
validation.

### Global/coupled response refinement checkpoint

The downstream response now has its own fresh mesh-ladder operator.  Each
declared axial/transverse resolution re-solves the coupled field from the same
closure fingerprint, independently remeasures the global/coupled boundary
response, and verifies that the solver-retained response matches the
independent measurement.  The ladder reports coordinate, tangent, pressure,
and normal-velocity residuals separately, so a locally converged field cannot
hide an unresolved global overlap.

The compatible research ladder has ordered mesh growth and complete local
response coverage, but both resolutions remain a typed overlap residual
failure.  This is useful refinement evidence for the next solver-owned
feedback iteration; it does not claim global feedback, canonical downstream
closure, a physical shock-cell length, or a production product comparison.

### Solver-owned boundary-pressure consumer checkpoint

The coupled request now accepts a spatially aligned static-pressure profile
with explicit cell-center coordinates and provenance.  A global-boundary
profile builder samples only the retained global boundary, while a separate
response-feedback builder applies a bounded, signed pressure correction from
the measured overlap response at the next cell-column centers.  The coupled
solver consumes the profile in its material-streamline pressure flux and
shape residual, verifies exact mesh alignment, and reports that consumption
in the field result.

The profile handoff preserves the closure fingerprint and rejects missing
coverage, non-positive pressure, mismatched coordinates, or cross-closure
reuse.  The response-derived path is now a real downstream consumer seam,
but it is not an upstream global re-solve: ``global_coupling_verified``, the
canonical downstream-boundary gate, physical shock-cell fitting, external
provider comparisons, and production claims remain closed.

### Global/coupled pressure-feedback iteration checkpoint

The downstream pressure handoff now has a typed research-only iteration
operator.  It performs fresh coupled solves, independently remeasures each
retained global/coupled response, derives the next bounded pressure profile,
and checks exact closure/profile lineage before consuming that profile on the
next call.  Profile-station changes are a typed stop; the operator does not
regrid, extrapolate, or silently switch to a lower-fidelity solver.

The compatible fixture demonstrates the complete baseline-to-consumer path and
retains the consumed profile and response evidence.  Its next coupled field
still fails the local field/audit gate, so the iteration is reported as a
solver failure rather than a pressure fixed point.  This is the intended
boundary: ``global_coupling_verified``, canonical downstream closure,
physical shock-cell fitting, provider-bound validation, and Signature/FPA
production claims remain closed until the coupled entrance/frontier physics
and external measurements are accepted.

### Reduced-order shock-train split-audit checkpoint

The reduced-order shock-train lane now has an independent split-audit
operator.  It checks that the available case inventory is unique, every case
has an explicit calibration/validation/unassigned role, and the assigned
calibration and validation identities are disjoint.  The component validation
report records this audit separately from the older role-count contract.

The audit is governance evidence only.  A verified role manifest does not fit
closure coefficients, identify physical shock-cell centers, accept the
pressure-extrema diagnostic, or promote the reduced-order geometry into
Visualization, Signature, ray-transfer, or FPA claims.  The recovered
single-case archive therefore remains a typed missing-split blocker.

### Explicit global/coupled boundary-geometry feedback checkpoint

The downstream feedback lane now carries two separate solver-owned profiles:
the relaxed static-pressure profile at cell centers and the exact retained
free-boundary ordinate profile at boundary nodes.  Each profile keeps the
global closure fingerprint, source identity, ordered stations, and its own
research-only claim ceiling.  The coupled solver rejects station mismatch,
out-of-domain geometry, and inlet-seam mismatch without regridding,
extrapolation, or pressure-only substitution.

The independent coupled-field audit rederives geometry-profile consumption
from the retained boundary nodes.  An exactly aligned profile passes the local
audit.  The initial response fixture correctly failed closed on the
approximately half-metre global/coupled boundary mismatch at the downstream
inlet; the follow-on frame-anchor slice below makes that seam explicit without
translating coordinates.

### Solver-owned geometry-frame anchor checkpoint

The geometry profile now retains the lower ordinate of the source coupled
request, and the downstream solver records that ordinate in the typed request
and independent audit.  When a verified global geometry profile is consumed,
the solver derives a positive inlet height from its first retained boundary
ordinate minus that lower ordinate, then rebuilds the mixed-regime request
with the same solver-owned height.  A lower-ordinate mismatch remains a typed
input failure; no implicit frame translation, regridding, extrapolation, or
pressure-only substitution is allowed.

The compatible fixture now reaches a locally audited coupled field through
the geometry consumer and its coordinate response channel closes to the
declared tolerance.  The full pressure-plus-geometry feedback runner also
proves exact profile lineage, station alignment, coverage, and consumption.
The ordinary response-profile configuration still reports a typed solver
failure when its second fresh field misses the local pressure/tangency gate;
the exact physical-field continuation configuration now recognizes its
solver-owned first-iteration profiles and can reach the local research
pressure-update result.  Both configurations keep global feedback, canonical
downstream closure, physical shock-cell fitting, provider-bound validation,
and Signature/FPA promotion blocked.

### Explicit upstream/global feedback-proposal checkpoint

The downstream response now has a typed, bounded handoff for the next
global-frontier solver seam.  It re-samples the exact retained global boundary
at every measured station, applies one explicit relaxation fraction to the
signed coordinate, tangent, and static-pressure offsets, and retains the
resulting candidate targets together with the closure fingerprint and source
response status.  Out-of-domain stations, shifted frames, non-positive
pressure targets, and incomplete response channels fail closed; no
regridding, endpoint hold, or extrapolation is implicit.

The packet is explicitly ``global_resolve_required=true`` and
``consumed_by_global_solver=false``.  It therefore makes the missing
upstream/global feedback contract executable and auditable without pretending
that the current research global remesh has consumed downstream information.
The bounded downstream feedback runner now retains one such packet per
iteration when the independently measured overlap response passes; its
aggregate readiness is reported separately from local pressure-update
convergence.  A residual-failing response cannot be silently packaged as a
global handoff.
The fresh downstream resolution ladder carries the same packet per mesh and
requires that handoff evidence alongside response coverage and residual
checks.  Its tangent-residual summary is also one value per declared mesh,
so the refinement report cannot hide a dimensional aggregation error.
The canonical C-/C+ frontier solve, global feedback iteration, downstream
boundary closure, physical shock-cell fitting, external validation, and
Visualization/Signature/FPA production gates remain open.

### Solver-owned pressure-profile audit checkpoint

The independent coupled-Euler audit now reconstructs the exact per-column
free-boundary pressure target vector from the request.  When a solver-owned
pressure profile is present, both the independent wall-flux reconstruction
and the pressure/tangency residual gate use that profile; the scalar ambient
pressure remains the target only when no profile was supplied.  This fixes a
measurement-contract mismatch that previously rejected correctly consumed
pressure profiles as though they were ambient-boundary fields.

The combined pressure-and-geometry consumer now reaches a locally audited
field under a full research pressure update, and the bounded feedback runner
can reach a local pressure fixed point when explicitly configured for that
update.  The exact physical-field continuation path also verifies its
solver-owned first-iteration neighbor profiles before entering the same
bounded runner.  These are local research outcomes only: the global/coupled
closure and production claim gates remain blocked, as do physical shock-cell
fitting, provider-bound validation, and Signature/FPA promotion.

### Target-pressure-aware solver-owned placement checkpoint

The solver-owned physical-field placement request now accepts an explicit
downstream static-pressure target and tolerance.  It evaluates every retained
post-shock cross-section using the derived normal-shock profile, selects only
an in-domain candidate whose sampled profile meets the target, and retains the
best candidate when no target is reachable.  The independent placement audit
re-derives candidate ordering, target residual, and the typed
`TARGET_PRESSURE_UNREACHABLE` stop.

This makes the missing transonic/frontier pressure budget executable instead
of treating a fixed post-shock fraction as a solution.  It remains a local
normal-shock placement gate: it does not solve the surrounding C-/C+ field,
ambient/centerline closure, feedback into the global remesh, physical cell
length, Signature/FPA promotion, or external validation.  A target miss is
therefore preserved as evidence for the next mixed-regime solver slice.

### Shock-front conservative-jump audit checkpoint

The independent physical-field shock-front audit now re-derives normalized
mass, normal-momentum, tangential-momentum, and energy fluxes on both sides of
each retained front sample.  It selects the front normal from the retained
ordered geometry, reconstructs primitive quantities from Mach, gamma, and
total-pressure lineage, and records the maximum conservative jump residual.
The exact-field fixture passes this local jump gate at approximately machine
precision; tampered or non-conservative front data remain auditable failures.

This strengthens the local front contract without widening its claim ceiling.
It does not close the global C-/C+ frontier, ambient/centerline feedback,
mixed-regime finite-volume entrance, physical cell length, Signature/FPA
promotion, or external validation.

### Standardized physical shock-front visualization checkpoint

The planar-MOC visualization adapter now carries the retained physical-field
shock-front condition as a distinct named path.  It publishes the condition
status, sample count, finite/ordered geometry availability, solver-side
verification flags, independent conservative-jump audit status, and measured
residuals through the standard diagnostic map.  Malformed geometry or audit
scalars remain unavailable rather than being drawn or coerced into a claim.

The path semantic explicitly labels the overlay as research-only, and the
bundle preserves ``physical_closure_verified=false``, the promotion block,
and the production-claim ceiling from the solver result.  This makes the
local Rankine--Hugoniot evidence inspectable in the Visualization product
without presenting it as a globally closed shock surface, a physical
shock-cell length, Signature/FPA input, or external validation.

### Solver-owned transonic-interface placement checkpoint

The global-to-coupled orchestrator now has a distinct
``SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE`` path.  With no caller
placement it derives a full-span interface from the exact retained global
physical field, runs the independent field-placement audit, and passes the
same placement into the coupled request.  A caller-supplied placement must
retain the exact field object and pass the full-field cross-section audit;
partial-span and cross-field placements stop with a typed handoff failure.
The placement is retained on the global result and report so downstream
Visualization and Signature evidence can distinguish an exact field-bound
handoff from a caller geometry choice.

This closes solver-owned placement provenance only.  The coupled result is
still a local constant-gamma research candidate: global feedback, canonical
mixed-regime/free-boundary closure, refinement, physical shock-cell length,
provider-bound validation, Signature/FPA promotion, and production claims
remain open.

### Long-running execution checkpoint — 2026-09-08

The active integration candidate at this checkpoint is the clean, pushed
branch `work/washed-integral-visual` at `f74baa1`.  `main` remains untouched.
The latest code slice corrected a scope-marker omission in the downstream
solver without changing the fidelity boundary.  The repository retains the
historical Version 8 intake report, but the raw ZIP, the separately named
alignment archive, and provider-bound measurement-space outputs are not
present in the current workspace.  No committed report or embedded overlay is
being treated as a substitute for those inputs.

Local evidence through this checkpoint includes the full test suite
(`1132 passed`), focused frontier/reconciliation and coupled-refinement tests,
Ruff, Pyright, lane partitioning, public-contract checks, Markdown policy,
diff checks, and offline wheel/install smoke.  GitHub CI for this exact
candidate passed all four Python matrix jobs in run `34201987974`.  This is a
green integration checkpoint, not a release freeze: the release manifest
still reports `release_ready=false`, and its freeze/validated-code references
must be refreshed only after the final physics, validation, documentation, and
packaging slices are complete.

The next implementation slice remains `P2.2`, not product promotion.  A
solver-owned placement with no pressure target is a valid local handoff, but
the actual ambient target is currently typed as unreachable by the placement
probe (the normalized target-pressure residual is approximately `0.584`).
The downstream coupled-Euler candidate consequently remains a typed physical
failure.  The next physics work must solve the two-dimensional transonic
placement together with its C-/C+ frontier, entropy-producing shock jump,
ambient/free-boundary and centerline neighbors, conservative residuals, and
an independent audit.  It must preserve the hard stop for unreachable
targets and must not fall back to the basic, reduced-order, or mapped
variable-entropy lanes.

The P2.2 hard-stop is now regression-tested against the actual retained
ambient pressure: the solver-owned placement reports
`TARGET_PRESSURE_UNREACHABLE`, and the coupled consumer returns a typed
physical-field handoff failure before constructing a downstream field.  This
is stronger negative evidence for the missing 2-D physics, not a closure or
promotion result.

The downstream consumer now binds an explicitly supplied ambient pressure into
the solver-owned placement request.  A caller-supplied interior placement that
does not carry the exact ambient target is rejected before the coupled request
is built, and an unreachable automatically derived placement is retained in
the failure result with its best residual and field lineage.  The reflected-
domain contract file passes 103 tests for this packet; this strengthens the
hard-stop/provenance boundary but does not close the two-dimensional physics.

The exit order is unchanged: acquire and verify the missing validation assets
and disjoint splits; close and refine the actual solver-owned reflected field;
fit physical first/continued cells only from that closed field; run each
Visualization, Signature/ray, and FPA comparison in its own measurement
space; then refresh the exact-HEAD freeze and release manifest.  Until all of
those gates are green, the correct deliverable is a reproducible
research-scoped candidate with explicit blockers, not a release tag or a
production claim.

### P2.2 front-aligned conservative reconciliation checkpoint — 2026-09-08

The next solver-owned consumer now re-solves the retained physical-field mesh
with conservative Euler face fluxes.  It consumes the exact fitted shock
front, upstream and post-shock states, ambient-pressure path, centerline path,
and the solver-owned terminal edge.  The edge topology is rebuilt from the
retained cells; no cross-section profile is projected onto a free boundary and
no lower-fidelity lane is selected when a path is unavailable.

The target retained field currently has 53 cells, 88 internal edges, 8 shock
edges, 8 ambient edges, 9 centerline edges, and one terminal outflow edge.
The fixed-front research re-solve converges locally in 140 pseudo-iterations
with a maximum normalized conservative residual of approximately
``4.93e-4`` and a maximum shock jump residual of approximately ``7.93e-5``.
The independent operator
``op.moc.physical-field-euler-reconciliation-audit`` reconstructs the same
residual channels, shock jump, ambient pressure/tangency, centerline, source
geometry, and promotion flags.  Focused success and tampered-residual tests
pass.

This is genuine conservative field consumption, but it is not yet the P2.2
exit condition.  The front geometry is still fixed from the retained MOC
field; there is no solver-owned placement update, cross-case refinement
ladder, or accepted physical comparison.  The result therefore reports
``physical_closure_verified=false``, ``global_coupling_verified=false``, and
the research-only claim ceiling.  The next slice is to bind this consumer to
the global placement/refinement loop and demonstrate stable behavior across
at least two declared resolutions before considering any physical shock-cell
fit or product promotion.

### Standardized reconciliation Visualization checkpoint — 2026-09-08

The standardized planar-MOC adapter now recognizes the front-aligned
conservative reconciliation result as its own research visualization model:
``planar-moc-physical-field-euler-reconciliation``.  It preserves the
solver-owned mesh polygons, shock/ambient/centerline paths, derived primitive
state channels, and five cell-associated normalized residual channels
(``mass``, streamwise/transverse momentum, energy, and maximum Euler
residual).  The bundle also reports the solver status, boundary-edge counts,
pseudo-iteration count, maximum boundary/shock residuals, and independent
audit operator status.

This closes a Visualization-product evidence seam for the new consumer only.
The adapter explicitly retains the research claim ceiling and warns that a
residual heat map is not global placement, refinement convergence, a physical
shock-cell fit, Signature radiance, ray transfer, or FPA evidence.  A focused
renderer-neutral regression test passes, including JSON serialization and the
promotion guard.

### P2.2 source-bound reconciliation refinement checkpoint — 2026-09-08

The front-aligned consumer now has a typed local resolution ladder.  Each
ladder member must carry an independently generated physical-field
shock-front condition, declare the retained shock-front sample count as its
resolution, and freshly execute both the conservative reconciliation and its
independent residual audit.  The aggregate operator fingerprints the retained
boundary paths and cell topology, requires strictly increasing resolutions and
cell counts, and rejects a relabeled copy of one mesh.

The mixed-regime regression exercises distinct five- and nine-sample source
fields: both local reconciliations and audits pass, source fingerprints differ,
and cell counts grow with resolution.  A same-source relabeling case is
rejected.  The ladder remains explicitly local research evidence with
``physical_closure_verified=false``, ``global_coupling_verified=false``, and
the chain/production gates closed.  It does not substitute for a solver-owned
placement update, a canonical reflected/free-boundary closure, accepted
physical shock-cell lengths, or provider validation.

### Global frontier target-guided re-solve checkpoint — 2026-09-08

The downstream feedback packet now has a bounded global consumer seam.  Given
one exact closure fingerprint and one exact relaxed frontier target, the new
operator re-runs the retained global physical closure for every declared
compression-envelope candidate, measures the fresh downstream boundary at the
target stations without extrapolation, and selects the lowest normalized
target-residual candidate.  The regression exercises two fresh global solves,
checks that neither aliases the source closure, and verifies target coverage,
target matching, and proposal lineage.

This is the first fresh upstream/global invocation in the feedback chain, but
it is intentionally not being called full global coupling: the target still
guides selection within an existing candidate family rather than entering the
global equations as a canonical mixed-regime boundary condition.  The result
therefore keeps ``global_coupling_verified=false``,
``downstream_boundary_closure_verified=false``, the chain promotion block, and
the production claim block.  The next physics slice is to replace candidate
selection with a solver-owned pressure/geometry boundary condition and then
re-measure a coupled placement/refinement ladder against independent physical
data.

### P2.2 pressure-target consumer checkpoint — 2026-09-08

The exact global-frontier request now has a real conservative consumer for its
static-pressure channel.  A typed
``MocPhysicalFieldEulerBoundaryPressureTarget`` retains the station frame,
pressure profile, optional target geometry/tangent metadata, and the exact
source closure/proposal fingerprints.  The fixed-front conservative
reconciliation samples that profile at every ambient-face midpoint and uses
it directly in the boundary momentum flux; uncovered stations fail before
the solve and no endpoint extrapolation is allowed.

The independent reconciliation operator rederives the same target pressure
profile, coverage, flux residuals, and target-residual report.  The new
global-frontier target-pressure operator binds the proposal fingerprints,
builds a fresh source-owned front condition, runs the consumer, and retains
the independent audit.  A source-aligned regression passes this local
research path; the actual downstream feedback fixture correctly returns a
typed target-coverage failure because its stations do not cover the retained
ambient path.

The standardized planar-MOC Visualization adapter exposes the consumer as
``planar-moc-global-frontier-target-pressure-reconciliation`` with target
coverage, consumption, station-count, and audit diagnostics.  This remains a
fixed-front research result: shock placement, target geometry consumption,
transonic/mixed-regime closure, upstream feedback, refinement, physical
shock-cell lengths, external validation, and production claims remain open.

### Global coupled frontier feedback runner checkpoint — 2026-09-08

The downstream-response and fresh-global-target operators are now composed
into a bounded outer runner.  Each declared step retains the exact source
closure fingerprint, executes the downstream coupled response ladder, builds
the exact frontier reconciliation request, and fresh-solves the global
candidate family before selecting the next closure.  A selected closure must
be a new object with verified target coverage, target matching, fresh-solve
invocation, and preserved lineage; missing proposals and failed target steps
stop the runner without a fallback or extrapolation.

The runner is deliberately named research feedback rather than global
closure.  It keeps ``global_coupling_verified=false``,
``downstream_boundary_closure_verified=false``, the chain-promotion block,
and the production block even when every bounded step succeeds.  It still
does not impose the response as a canonical mixed-regime/free-boundary
equation, establish refinement convergence, fit physical cell lengths, or
replace provider-bound validation.  The next closure slice is the actual
solver-owned pressure/geometry boundary-condition solve and its cross-case
refinement evidence.

### Fresh-candidate pressure-consumption checkpoint — 2026-09-08

The target-guided global resolver can now optionally pass its selected fresh
candidate through the exact fixed-front conservative pressure consumer.  The
consumer keeps the proposal-producing closure fingerprint separate from the
fresh candidate fingerprint, reconstructs the candidate-owned shock-front
condition, applies the exact pressure profile in the ambient-face momentum
flux, and independently audits coverage and residual channels.  This removes
an ambiguity in the feedback record: a target match can now be distinguished
from actual pressure consumption by the fresh candidate's conservative field.

The mixed-regime feedback target currently fails the new optional consumer's
coverage gate because its stations do not span the candidate's retained
ambient path.  That typed failure is retained; no interpolation outside the
declared station frame, endpoint hold, or lower-fidelity fallback is allowed.
An exact candidate-bound target passes the consumer regression, with distinct
source/candidate fingerprints and all global, chain, and production gates
closed.  This is still a fixed-front research reconciliation, not the
solver-owned two-dimensional transonic/free-boundary condition required for
canonical global closure.  The next physics work remains target geometry
coverage/placement inside the global solve, followed by cross-case refinement
before any physical shock-cell fit or product promotion.

### Explicit frontier-target overlay checkpoint — 2026-09-08

The fixed-front pressure consumer now has an explicit bounded-overlay
contract for the measured partial-overlap case.  A base target owns the full
retained station frame; a frontier target may replace it only on its declared
interval.  Composition rejects an overlay outside the base frame, performs no
extrapolation or endpoint hold, checks the pressure seam discontinuity, and
retains the base/overlay source IDs plus the measured seam diagnostic in a
distinct ``explicit-overlay`` target model.  The global target-pressure
consumer retains both the exact frontier target and the actually consumed
composite target in its report.

This is intentionally a fixed-front research seam, not a solver-owned shock
geometry update: the direct target path still fails closed when its station
frame does not cover the retained ambient faces, and every global, chain, and
production gate remains closed.  The next implementation slice is to make the
overlay/target contract a boundary condition of the two-dimensional
transonic/free-boundary solve itself, then run the resulting geometry through
the existing cross-case refinement ladder.

### Candidate-bound frontier pressure consumption checkpoint — 2026-09-08

The target-guided resolver now has an explicit opt-in path that derives the
fresh candidate's complete ambient boundary as the base target before asking
the fixed-front pressure consumer to consume a partial downstream frontier
packet.  On the mixed-regime fixture, the default request still returns the
typed target-coverage failure, while the explicit candidate-bound composition
passes target coverage, conservative pressure consumption, and the
independent residual audit.  The result retains separate source/candidate
fingerprints and the composed target lineage.

This is stronger evidence that the measured overlap can be consumed without
extrapolation, but it is still not a two-dimensional placement update: the
candidate shock/mesh remains fixed, global coupling and downstream closure are
false, and chain/production gates remain closed.  The next physics slice is
to put this pressure/geometry condition inside the global free-boundary
equations and then demonstrate cross-case refinement of the resulting
placement rather than only fixed-front consumption.

### Target-bound coupled free-boundary profile checkpoint — 2026-09-08

The coupled downstream lane now accepts a composed typed frontier target at
its actual solver stations.  A target is sampled separately at cell centers
for the pressure condition and at boundary nodes for the free-boundary
geometry condition; the exact candidate closure fingerprint is retained in
both profiles.  Any uncovered station or target whose geometry points do not
retain their declared station frame fails closed without extrapolation.

The regression composes a full solver-owned ambient base with a bounded
frontier overlay, builds both profiles, consumes them in the conservative
coupled-Euler/free-boundary solve, and independently audits the result.  This
is the first target-overlay path that reaches the 2-D downstream equations,
but it remains a fixed candidate boundary condition: shock placement is not
yet re-solved upstream, global coupling and downstream closure remain false,
and cross-case refinement plus physical validation are still required.

### Coupled downstream cross-case refinement checkpoint — 2026-09-08

The coupled downstream validation lane now has a typed cross-case operator.
Each named case owns its exact global-closure fingerprint and its own strict
axial/transverse resolution ladder.  The aggregate audit rejects duplicate
closure identities, mismatched run lineage, reused or reordered ladders, and
failed nested local response audits; it never compares residual magnitudes
between physically distinct cases as if they were mesh refinements.

The regression covers both the duplicate-closure failure path and two fresh
independently generated closure cases.  Both local ladders pass with finite
response channels and retained feedback proposals, while global feedback,
canonical downstream closure, physical shock-cell fitting, external
validation, and production claims remain explicitly closed.  This is the
cross-case evidence boundary required before a physical shock-cell fit; it is
not itself an accepted physical comparison or a canonical global closure.

### Candidate packaging checkpoint — 2026-09-08

The exact candidate at ``eb748e16782f77f2ee047e13d141deccfbd1fc2a`` passes the
repository's offline wheel build and installed-wheel smoke harness
(``python3 scripts/check_build.py --offline``).  The smoke exercised the
current Visualization, Signature, validation, and compatibility entry points
from a fresh system-site-packages environment with no index access.  The
checkout remained clean after the run; the known legacy expansion-fan
warnings and expected unattainable pressure-target diagnostic were retained
as non-fatal diagnostics.

This closes the current packaging checkpoint only.  It does not refresh the
historical release-freeze artifact, and it does not promote any lane: the
canonical globally coupled closure, physical shock-cell fit, provider-bound
comparisons, validation-data provenance, and product-specific external claims
remain open.  The next implementation gate is a solver-owned physical
shock-cell/refinement slice with an accepted disjoint validation boundary,
followed by a final exact-HEAD freeze and release-manifest refresh.

### Target-bound coupled refinement checkpoint — 2026-09-08

The coupled downstream refinement runner now accepts one typed
``MocPhysicalFieldEulerBoundaryPressureTarget`` owned by each refinement case.
For every declared axial/transverse resolution it derives the actual solver
cell-center and free-boundary-node stations, including the solver-owned
post-shock inlet frame used by physical-field continuation, and samples the
target without extrapolation.  Both profiles are passed into the real 2-D
coupled-Euler/free-boundary solve; the case retains target identity, closure
fingerprint, profile sources, and independent consumption flags.

The positive regression passes two target-bound mesh cases and verifies both
pressure and geometry profile consumers.  A truncated target returns a typed
response failure before solving, proving that the runner does not silently
fall back to the unbound baseline.  The new operator remains explicitly
research-only: global coupling, canonical downstream closure, physical
shock-cell fitting, external validation, chain promotion, and production
claims remain closed.  The next physics gate is to use this target-bound
ladder as evidence for solver-owned placement/refinement, then bind it to an
accepted disjoint physical comparison.

### Production shock-cell fit refinement checkpoint — 2026-09-08

The production-fit validation lane now has a typed
``op.moc.reflected-domain.production-shock-cell-fit-refinement`` operator.
It independently remeasures a caller-produced fit at each declared shock
resolution, requires one immutable upstream source band, distinct closure
fingerprints, one common axial interval/cell index, increasing solver-owned
shock sample counts, and finite resolution-to-resolution length deltas.  It
reports the retained axial lengths and their differences without replacing
the solver-generated shock path or treating the result as an observation.

The regression passes a two-resolution ladder and rejects a moved interval.
The operator retains ``physical_length_accepted=false``,
``external_validation_verified=false``, and the chain/production promotion
block even when all local fit and measurement gates pass.  The remaining P3
gate is an accepted, disjoint physical length comparison from the validation
handoff; the missing archive/provider evidence cannot be substituted with
synthetic data.

### Candidate packaging checkpoint — 2026-09-08 (`eb56a66`)

The exact shock-cell-fit refinement candidate ``eb56a66`` passes
``python3 scripts/check_build.py --offline``.  The wheel contains the new
typed refinement operator, and the installed smoke completes with only the
known legacy expansion-fan warnings and expected pressure-target diagnostic.
The checkout remains clean after the build.

This is packaging evidence for the research checkpoint, not release evidence:
the canonical reflected/mixed-regime closure, accepted physical cell-length
comparison, provider-bound VIS/SIG/RAY/FPA comparisons, validation archive,
and final release freeze remain open.

### Fresh production shock-cell runner checkpoint — 2026-09-08 (`1da39ef`)

The exact candidate ``1da39ef`` adds a fresh
``op.moc.reflected-domain.production-shock-cell-fit-refinement-run`` operator.
For each declared resolution it re-executes the existing global Euler shock
boundary refinement runner, retains the solver-owned physical field, fits the
same solver-owned axial interval, and invokes the independent shock-cell
measurement ladder.  The regression passes a two-resolution run, verifies
fresh invocation, local physical closure, source/fidelity isolation, distinct
closure identities, increasing solver-owned shock samples, and the typed
reporting path.  The runner never accepts a caller-provided shock path or
promotes a fitted length.

The candidate also passes the offline wheel build and installed-wheel smoke
(``python3 scripts/check_build.py --offline``); the new runner is present in
the packaged validation surface.  This is still a research-only local fit
checkpoint: ``physical_length_accepted=false``,
``external_validation_verified=false``, chain promotion remains blocked, and
the canonical solver-owned global/free-boundary closure is not established.
The next gate is accepted disjoint physical shock-cell evidence, followed by
the provider-bound VIS/SIG/RAY/FPA comparison matrix and the final release
freeze.

### Continued shock-cell chain checkpoint — 2026-09-08 (`2c60906`)

The production-fit validation surface now exposes the typed
``op.moc.reflected-domain.production-shock-cell-continued-chain-run``
operator.  It fresh-solves the seed global physical field, then invokes the
exact-Euler continued-chain planner so each downstream cell is independently
re-solved from its carried state.  The report retains source/global/planner
measurements, explicit inter-cell bridge measurements, carried-state lineage,
and the fidelity-isolation policy.  A two-cell continuation regression passes
with two fresh downstream solves and two verified bridges.

This remains a research-only evidence slice: canonical global closure,
free-boundary closure, accepted physical cell length, external validation, and
chain promotion are all explicitly false or blocked.  The missing raw
validation archive and separate alignment archive are still unresolved and
must not be replaced by synthetic data.  The next gate is a solver-owned
canonical mixed-regime/free-boundary closure with accepted physical
shock-cell lengths, followed by provider-bound VIS/SIG/RAY/FPA cases and the
final release-manifest acceptance matrix.

### Target-conditioned global frontier refinement checkpoint — 2026-09-08

The global frontier validation surface now exposes the typed
``op.moc.reflected-domain.global-frontier-target-conditioned-refinement``
operator.  It consumes one exact downstream proposal, evaluates a bounded
lower/middle/upper compression-envelope-skew family with fresh global
physical-closure solves, measures each candidate against the target without
extrapolation, and narrows the retained bracket around the best finite
candidate.  Source closure identity, proposal identity, fresh invocation,
target coverage, and fidelity-isolation evidence are retained at every step.

The new research result is also accepted by the standardized planar-MOC
visualization adapter with an explicit target-refinement model ID and
diagnostics.  The focused regression passes with a fresh selected closure and
all promotion gates closed.  This is parameter-conditioned global research
evidence, not a solver-owned physical downstream boundary: global coupling,
canonical free-boundary closure, physical cell-length acceptance, external
validation, chain promotion, and release readiness remain false.  The next
physics gate is to replace the compression-envelope control with a true
solver-owned mixed-regime boundary condition and independently refine that
two-dimensional placement across cases.

### Pressure-conditioned free-boundary checkpoint — 2026-09-08

The coupled Euler lane now exposes a distinct
``solver-owned-physical-field-pressure-free-boundary`` inlet mode.  It requires
the exact retained physical-field continuation and shock-front condition plus
an aligned pressure profile, rejects any caller-supplied geometry profile, and
lets the two-dimensional solver evolve its own free-boundary ordinates through
the existing pressure/tangency update.  The independent audit re-samples the
exact inlet seam and pressure profile, verifies the local conservative field,
and confirms that geometry was not injected as a hidden target.

The global-to-coupled orchestrator can carry this pressure-only candidate with
the closure fingerprint intact.  Focused direct and end-to-end regressions
pass, including the expected research-only stop: global feedback,
canonical/free-boundary closure, accepted shock-cell length, external
provider validation, chain promotion, and release readiness remain false.  The
next physics gate is independent placement/refinement of this pressure-only
boundary across disjoint cases, followed by a true upstream global re-solve.

### Pressure-free-boundary refinement checkpoint — 2026-09-08

The validation surface now exposes a separate
``op.moc.reflected-domain.global-coupled-pressure-free-boundary-refinement``
ladder.  Each mesh resolution fresh-solves the global-to-coupled candidate
from one exact closure and one closure-bound pressure target, samples only
cell-center pressure stations with no extrapolation, independently audits the
coupled field, and verifies that geometry injection stayed blocked while the
solver-generated boundary changed with the mesh/field response.

The two-resolution regression passes with fresh invocation, target/closure
lineage, pressure consumption, solver-owned geometry, finite response
channels, and fidelity isolation.  This remains local research evidence:
cross-case refinement, upstream global feedback, canonical closure, accepted
physical shock-cell length, external provider validation, and release
readiness remain open.

### Disjoint pressure-free-boundary cases checkpoint — 2026-09-08

The pressure-only refinement lane now also has a typed cross-case runner.  It
requires unique case IDs, distinct source closure fingerprints, a separately
bound target for every case, and an independent resolution ladder per case.
The aggregate never compares different closures as adjacent mesh resolutions;
it verifies each nested ladder first, then reports the cross-case evidence.

The two-case regression passes with four fresh coupled solves and retains
``global_coupling_verified=false``, ``downstream_boundary_closure_verified=false``,
the external-validation requirement, and the chain-promotion stop.  This closes
only local disjoint-case evidence.  A solver-owned upstream/global re-solve,
accepted physical shock-cell measurements, provider-bound product cases, and
the missing validation archives remain release blockers.

### Upstream/global consumption audit checkpoint — 2026-09-08

The existing global frontier-feedback composition has been audited at the
solver call boundary.  It does perform fresh
``solve_reflected_domain_global_physical_closure`` calls, but the downstream
frontier packet currently changes only the declared compression-envelope
candidate family; the fresh global results are then measured against the
packet and the best candidate is selected.  That is parameter-conditioned
research evidence, not downstream pressure consumed as a boundary condition
inside the global equations.

The optional pressure consumer in the target-guided resolver is a separate
fixed-front conservative reconciliation on the selected candidate.  It proves
that a pressure profile can be covered and measured on an already retained
front, but it does not move the global shock, solve the ambient/free boundary,
or establish upstream/downstream fixed-point coupling.  The plan therefore
keeps ``global_coupling_verified`` and
``downstream_boundary_closure_verified`` false for every such report.

The next canonical-closure slice must introduce a typed solver-owned global
boundary-condition request (or an equivalent mixed-regime solve) that retains
the source and proposal fingerprints, rejects incomplete pressure coverage,
consumes the pressure response while solving geometry and state together, and
independently audits pressure, tangent, entropy, Euler, and refinement
residuals.  A candidate-selection score or fixed-front overlay cannot satisfy
that gate.  Only after this operator closes across disjoint cases can the
accepted physical shock-cell fit, continued-chain handoff, provider-bound
VIS/SIG/RAY/FPA matrix, and final release manifest advance.

### Solver-owned global pressure-profile consumer checkpoint — 2026-09-08

The next boundary-condition seam is now implemented and independently
regressed through the exact global ambient march.  The typed
``op.moc.reflected-domain.global-frontier-boundary-condition`` runner builds
an explicit pressure-profile target from one lineage-verified frontier
request, fresh-solves the global physical closure, and requires every
solver-produced ambient station to be covered by the target.  The marching
solver re-samples the pressure profile at its own downstream ordinates and
iterates pressure/tangency together; target boundary ordinates are never
read or injected.

The pressure profile and source lineage now survive the ambient boundary,
Euler physical field, global closure, downstream-boundary result, and
independent downstream measurement reports.  The focused boundary-condition
regression, all 126 reflected-domain tests, and the ambient/physical-field
and measurement regression set (95 tests) pass.  Scalar ambient-pressure
behavior remains green.  The result is still explicitly research-only:
global fixed-point coupling, canonical mixed-regime/free-boundary closure,
accepted physical shock-cell lengths, independent refinement across cases,
external provider validation, chain promotion, and release readiness remain
closed.

The immediate next physics slice is to add the independent residual and
refinement evidence around this pressure-conditioned global solve across
disjoint cases, then bind only accepted solver-owned fields to the production
shock-cell fitter.  The missing raw V8 validation archive and separate
alignment archive remain release blockers; synthetic substitutes are not
acceptable.

### Global pressure-consumer refinement and disjoint-case checkpoint — 2026-09-08

The pressure-consumer lane now has a separate research refinement operator and
cross-case aggregate.  Every requested resolution fresh-solves the global
closure from the same lineage-verified source, consumes pressure at the
solver-produced stations, and independently checks target coverage, target
matching, finite response channels, solver-owned geometry, and fidelity
isolation.  The cross-case runner requires unique case IDs and distinct source
closure fingerprints before it combines the per-case ladders; it never treats
different physical closures as adjacent mesh resolutions.

The two-resolution single-case ladder and two-case disjoint ladder pass in the
focused and broad regression set (155 tests total).  The existing solver
alignment invariant also records that sample count 7 is not currently a valid
resolution for this lane; the accepted research ladder uses fresh 9- and
10-sample solves rather than hiding that limitation.  Standardized
visualization now exposes the consumed target as a reference packet, marks
solver-owned geometry and fidelity isolation, and keeps the model explicitly
research-only.

This does not close canonical/global fixed-point coupling, physical shock-cell
length acceptance, continued-chain fitting, provider-bound VIS/SIG/RAY/FPA
cases, or release readiness.  The raw V8 validation archive and separate
alignment archive are still absent, and the next gate remains an independently
validated solver-owned field bound to production fitting only after the final
acceptance matrix turns green.

### Partial global-target hard-stop checkpoint — 2026-09-08

The boundary-conditioned global consumer now classifies an incomplete frontier
packet before attempting a fresh solve.  A downstream response whose station
interval does not cover the solver-owned shock interval returns the typed
``TARGET_COVERAGE_FAILURE`` stop, retaining the exact proposal lineage and
without extrapolation, endpoint hold, or a lower-fidelity fallback.  The
ambient-march failure record was also hardened so a failed target station
cannot be hidden by a secondary evidence-shape exception; retained samples,
point results, and invariant residuals remain aligned on every typed stop.

The direct solver-owned full-boundary regression remains green, and the
partial-target regression now proves that the correct next operation is a
joint geometry/state boundary solve.  This is a contract-hardening slice, not
canonical closure: the current consumer still accepts pressure only, ignores
target ordinates/tangents for geometry evolution, and leaves
``global_coupling_verified``, downstream mixed-regime closure, physical cell
length acceptance, external validation, and release readiness false.  The
next P2.2 slice must replace this pressure-only handoff with a solver-owned
mixed-regime/free-boundary iteration that solves the interface geometry,
pressure, tangent, entropy, and conservative residuals together.

### Ambient-pressure free-boundary checkpoint — 2026-09-08

The coupled constant-gamma research lane now has a separate
``solver-owned-physical-field-ambient-pressure-free-boundary`` mode. It
consumes the exact global physical-field continuation and shock-front handoff,
uses only the mixed-regime request's uniform ambient static pressure as the
free-boundary target, and evolves the boundary ordinates from the local
pressure/tangency iteration. It rejects caller-supplied axial pressure and
geometry profiles, so a downstream packet cannot masquerade as a joint
closure. The result records explicit ambient-target consumption and remains
independently auditable.

The focused solver/audit regressions pass for this new contract, including the
typed rejection of profile injection. This advances the downstream boundary
law but does not yet feed the evolved interface geometry or state back into
the upstream global shock solve; the result therefore remains research-only
with canonical/global coupling, accepted shock-cell length, external
validation, product-provider comparisons, chain promotion, and release gates
closed. The next P2.2 slice is a bounded joint global/downstream iteration
that consumes this solver-owned boundary response on a fresh upstream solve,
with explicit interval coverage and independent pressure/tangent/entropy/
conservative residuals plus disjoint-case refinement.

### Bounded global pressure-frame composition checkpoint — 2026-09-08

The global pressure consumer now accepts an optional lineage-bound base target
when a downstream response is only a bounded overlay.  The base frame must
carry the exact source-closure and frontier-proposal fingerprints; the
downstream packet is composed only over its declared interval, with seam
pressure checks and no endpoint extrapolation.  The direct overlay remains
available for measurement, while the composed target is the only pressure
profile passed to the fresh ambient march.  Target ordinates and tangents from
both packets remain diagnostics; the global solver still owns geometry.

The focused boundary-condition suite passes all five cases, including the
full-target solve, the original partial-target hard stop, lineage-mismatched
base rejection, the fresh-resolution ladder, and disjoint-case refinement.
The composed path advances past the initial shock-interval coverage check but
currently returns a typed ``TARGET_COVERAGE_FAILURE`` when the fresh
solver-owned ambient boundary moves to a later station outside the composed
frame.  The result retains the source/base/overlay identities and records
that no extrapolation was attempted.  This is evidence for the next joint
geometry/state solve, not canonical global coupling, accepted physical
shock-cell length, chain promotion, external validation, or release readiness.

The next P2.2 slice is therefore a bounded mixed-regime/free-boundary
iteration that can negotiate the moving station frame while independently
checking pressure, tangent, entropy, and conservative residuals.  The
provider-bound VIS/SIG/RAY/FPA matrix, raw V8 validation archive, alignment
archive, and final release gates remain unchanged blockers.

### Joint downstream/global boundary-feedback checkpoint — 2026-09-08

The validation surface now exposes
``op.moc.reflected-domain.global-coupled-boundary-condition-feedback``.  It
executes the bounded outer sequence of coupled downstream response, exact
frontier request, solver-owned ambient base frame, explicit pressure overlay,
and fresh global ambient re-solve.  The base and overlay identities retain
the source closure and proposal fingerprints; target geometry remains
diagnostic, and the global solver owns the new boundary ordinates.

The iteration result separates response, lineage, composition, fresh-solve,
coverage, pressure, tangent, entropy, conservative-Euler, and fidelity gates.
The current target case reaches the fresh global attempt and returns the
typed moving-frame ``TARGET_COVERAGE_FAILURE`` without extrapolation or a
lower-fidelity fallback.  The standardized planar visualization exposes the
new feedback model ID and all of those diagnostics while keeping canonical
coupling, chain promotion, and production claims false.  This is a concrete
outer-iteration handoff, not accepted mixed-regime closure.

The next physics slice must negotiate the moving station frame inside a
solver-owned mixed-regime/free-boundary iteration, then repeat this operator
over disjoint cases and refinement levels.  Physical shock-cell acceptance,
provider-bound VIS/SIG/RAY/FPA comparisons, the raw V8 and alignment archives,
and the final release gates remain open.

### Active execution board — 2026-09-08

The long-running goal remains active on the dedicated integration branch.  The
  current candidate is a local research checkpoint; it is not a release
  candidate.  The current pushed checkpoint is `768b964` on
`work/washed-integral-visual`; `main` remains untouched.  Work proceeds in the
following order,
with each item stopping closed when its evidence is absent:

1. **P2.2a — negotiate the moving solver frame.** Add a typed request and
   result for a bounded mixed-regime/free-boundary frame negotiation.  It must
   retain the source-closure and downstream-proposal fingerprints, define an
   explicit extension budget, and distinguish covered, under-covered, and
   non-physical frame requests.  It may request new solver-owned stations only
   through the physical boundary law; it may not hold an endpoint, extrapolate
   pressure, inject downstream geometry, or fall back to a lower-fidelity
   model.
2. **P2.2b — close the joint boundary.** Consume the negotiated frame in a
   fresh global solve and audit pressure, tangent, entropy transport, Euler
   residuals, and conservative boundary fluxes from retained states.  Keep the
   current research-only claim ceiling until the actual target case converges
   and the independent audit agrees.
3. **P2.2c — prove stability.** Run the joint operator across disjoint source
   closures and strictly increasing mesh/frame resolutions.  Require fresh
   solver invocations, exact lineage, finite residuals, stable response, and
   no geometry/profile injection before the closure can feed P3.
4. **P3 — fit physical cells.** Bind first and continued shock-cell fits only
   to an accepted P2.2 field.  Measure solver-owned axial length and uncertainty
   independently, then compare against disjoint physical observations; the
   current diagnostic spacing and research candidates remain ineligible.
5. **P1/P4 — acquire and execute external validation in parallel.** The raw V8
   archive, separately named alignment archive, provider outputs, camera/
   detector observations, and product-specific measurement operators must be
   supplied and provenance-verified.  Until then, VIS/SIG/RAY/FPA outputs stay
   local engineering or research evidence.
6. **P5 — freeze and release.** Refresh the exact-candidate freeze, rerun the
   complete lane/test/static/documentation/package matrix, verify the manifest
   reports `release_ready=true`, and only then create a release tag.

The immediate implementation target is item 4.  P2.2a and P2.2b are complete
for the current research target, and the fine P2.2c ladder now passes the
declared local stability, conservative-flux, and terminal final-closure audit
gates; the coarse ladder remains an explicit stability failure.  P3 now has a first-cell fit and an exact
highest-resolution carried-field continuation handoff, both research-only.
The continued-chain adapter now retains and independently fits the downstream
research fields from one accepted chain.  The continued-chain refinement
ladder now also passes its declared local geometry and downstream-length
sensitivity gates; this is numerical research evidence only.  The remaining
physics slice is comparison against disjoint physical observations and
canonical/global closure.
The absence of the validation archives is a parallel release blocker, not a
reason to synthesize observations or promote the physical model early.

### Solver-owned moving-frame negotiation checkpoint — 2026-09-08

The next P2.2a seam is now typed as
``op.moc.reflected-domain.global-boundary-frame-negotiation``.  It binds the
available pressure frame to the exact source-closure and downstream-proposal
fingerprints, measures the stations actually attempted by the fresh global
solver, and reports the lower/upper frame extension required by that attempt.
The ambient march retains a failed solver point separately from the aligned
accepted-sample arrays, so a coverage failure cannot be misreported as a
covered prefix.

On the current target case, the outer feedback operator now returns
``FRAME_NEGOTIATION_REQUIRED`` and retains an upper extension of approximately
``3.4e-4 m``.  The result explicitly blocks pressure extrapolation, endpoint
holding, downstream geometry injection, chain promotion, and production
claims.  This is a real solver-observed frame request, not a fabricated
station or a completed mixed-regime closure.  The next P2.2b slice must make a
solver-owned mixed-regime/free-boundary law generate and audit that extension
before the global iteration can continue.

### P2.2b solver-owned ambient frame extension checkpoint — 2026-09-08

The joint boundary-feedback operator now consumes the moving-frame request
through the separately named
``op.moc.reflected-domain.global-boundary-frame-extension`` operator.  The
extension request is accepted only when the exact source/proposal lineage is
preserved, the requested stations are an upper-frame extension within budget,
and the retained terminal target pressure independently matches the
solver-owned source ambient pressure.  It then adds only the newly requested
stations with that declared ambient-pressure law; target geometry and tangent
metadata are omitted so the fresh exact global solver must generate the
boundary geometry and states itself.

On the current mixed-regime target, the previously observed upper extension of
approximately ``3.386e-4 m`` is generated as one new ambient-law station.  A
fresh exact global solve consumes it, regenerates the ambient boundary, and
passes the local pressure, tangent, entropy-lineage, conservative cell-Euler,
target-consumption, and frame-coverage gates.  The outer operator now passes
two consecutive research iterations with the extension path.  A zero
extension budget still returns a typed frame-negotiation failure and retains
the original coverage stop, proving that the new path is bounded rather than
an implicit fallback.

This closes a solver-owned moving-frame handoff for the current research
case; it does not close the canonical reflected 2-D mixed-regime/free-boundary
law, independent refinement, physical shock-cell length, external validation,
or any production claim.  P2.2c must now repeat the joint operator across
disjoint source closures and increasing frame/mesh resolutions, with explicit
stability and conservative boundary-flux evidence before P3 can consume it.

### P2.2c disjoint refinement checkpoint — 2026-09-08

The next refinement seam is now typed as
``op.moc.reflected-domain.global-coupled-boundary-condition-feedback-cross-case-refinement``.
It binds each fresh feedback run to a distinct source-closure fingerprint and
an explicitly increasing ``(axial stations, axial cells, transverse cells)``
resolution.  Caller-supplied geometry, pressure, continuation, shock-front,
and mesh overrides are rejected; the operator installs the exact
solver-owned physical-field handoff and verifies the global geometry policy,
fresh solve, target lineage, frame coverage, finite response channels, and
fidelity isolation for every case.

The first disjoint pair (source samples ``5 -> 9`` and downstream resolution
``(7, 8, 4) -> (9, 10, 5)``) passes those local gates.  The response channel
ladder is within the declared ``0.75`` research stability fraction, but the
solver-observed initial frame-extension demand changes by approximately
``0.794`` relative and therefore returns typed ``STABILITY_FAILURE``.  A new
independent retained-state boundary-face audit replays all centerline, inlet,
free-boundary, and outlet fluxes, verifies internal-face antisymmetry, and
passes for both cases; ``conservative_boundary_fluxes_verified`` is now true
without being inferred from cell-Euler residuals.

This is a useful refinement result, not a promotion: P2.2c remains open until
the moving-frame demand is stable across the declared ladder.  P3 physical
shock-cell fitting, provider-bound VIS/SIG/RAY/FPA validation, the raw V8 and
alignment archives, and P5 release gates remain blocked.

### P2.2c accepted fine-ladder checkpoint — 2026-09-08

The same operator now passes a declared fine disjoint ladder with source
samples ``9 -> 11 -> 13`` and downstream resolutions
``(9, 10, 5) -> (11, 12, 6) -> (13, 14, 7)``.  The maximum adjacent response
change is approximately ``0.329`` and the maximum frame-demand change is
approximately ``0.320``, both below the ``0.75`` research stability fraction.
Every case retains a fresh solver invocation, exact source/target lineage,
solver-owned geometry, finite residuals, frame coverage, fidelity isolation,
and an independently replayed conservative boundary-face ledger.

This closes the local P2.2c refinement gate for the declared fine-ladder
research envelope.  The ``5 -> 9`` coarse ladder remains an explicit
``STABILITY_FAILURE`` and is not promoted into the high-fidelity envelope.
The result still does not establish canonical reflected 2-D mixed-regime
closure, external validation, or production validity.  The next implementation
slice is P3: bind physical shock-cell fitting to the accepted fine-ladder
field, retain first/continued fit uncertainty, and keep the fit research-only
until disjoint physical observations are available.

### P3 coupled-field first-cell fitting checkpoint — 2026-09-08

The new
``op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-fit``
adapter consumes only a converged fine P2.2c refinement run. For every
resolution it follows the final retained coupled-Euler result, verifies that
the result consumed the exact source shock-front condition and exact physical
initial-state handoff, and binds the existing solver-owned first-cell fitter
to that same physical field. The independent geometry measurement is retained
per case rather than inferred from a display path or diagnostic spacing.

The report now carries solver-owned axial lengths, adjacent resolution deltas,
and a resolution-derived uncertainty (the maximum adjacent length change).
This is numerical refinement evidence only: it is not a physical uncertainty,
accepted cell length, external comparison, canonical mixed-regime closure, or
production claim. Continued shock-cell fitting is still a separate carried
field/chain gate and is reported as not attempted; the raw V8 and alignment
archives remain unavailable.

The focused regression passes for the 9 -> 11 -> 13 fine ladder. The next P3
slice is to build the continued-chain handoff on the same accepted field
contract, then execute the disjoint physical-observation comparison when the
validation data is available.

### P3 accepted-field continued-chain handoff checkpoint — 2026-09-08

The new
``op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-chain``
adapter consumes the converged P3 first-cell run and selects only its highest
resolution case. It verifies object-identity lineage from the P2.2c source
closure through the retained global-Euler field, the first-cell fit, and the
coupled solver-owned shock-front condition before invoking the fresh exact
global-Euler continuation planner. The continuation retains fresh source-band,
global-remesh, exact-Euler, state-carry, and explicit intercell-bridge audits;
the planner receives one extra typed terminal callback slot so configured cell
exhaustion is not confused with a physical endpoint.

The focused 9 -> 11 -> 13 regression now passes with one exact retained seed
and one independently remeasured downstream research field. The chain report
exposes the downstream axial fit and its retained-field lineage, while keeping
continued-length refinement uncertainty explicitly pending until the ladder
comparison completes.

### P3 continued-chain refinement ladder checkpoint — 2026-09-08

The new
``op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-chain-refinement``
runner executes the same fresh exact-Euler continuation once for each accepted
P2.2c/P3 resolution, preserves exact case identity, independently remeasures
each retained field, and compares chain extent, shock spacing, mesh area, typed
termination, and downstream axial lengths. The 9 -> 11 -> 13 ladder passes
with declared local tolerances; the measured result remains research-only and
does not accept a physical length.

Physical acceptance, canonical/global closure, provider-bound VIS/SIG/RAY/FPA
validation, and production promotion remain blocked pending disjoint physical
observations and the remaining closure gates.

### P2.2 solver-owned profiled outer-pressure handoff checkpoint — 2026-09-08

The alternating reflected-domain source solver now accepts the typed
``MocPhysicalFieldEulerBoundaryPressureTarget`` as an optional, solver-owned
outer pressure condition.  It interpolates only between declared axial
stations, iterates the characteristic endpoint against the pressure sampled at
the solver-produced station, and retains the exact target object and source
identifier in the result and ambient-boundary report.  Boundary points and
tangent metadata carried by the target are deliberately ignored; the fresh
MOC march owns geometry and tangent acceptance.

The target must cover the retained seed and every generated outer station.  A
missing station is a typed boundary failure with no endpoint extrapolation or
endpoint holding.  The scalar ambient path remains unchanged and the target
path is covered by focused tests for scalar regression, profile retention,
ignored target geometry metadata, and incomplete-target rejection.

This is a bounded global-coupling handoff, not canonical closure: shock
entropy, mixed-regime downstream closure, disjoint physical observations,
provider-bound VIS/SIG/RAY/FPA acceptance, and release promotion remain open.

### P2.2 fresh source-band consumption checkpoint — 2026-09-08

The global physical-closure consumer now composes a separate source-band
pressure target from the exact source seed/ambient frame and the lineage-bound
downstream overlay.  A fresh alternating ``C-``/``C+`` source band consumes
that composed pressure profile before global shock remesh and exact-Euler
closure.  The downstream/global target retains its own station frame, so
source-frame coverage cannot hide a global ambient-frame extension request.

The source result retains the composed target and reports its source ID,
consumption, and geometry-injection guard.  Geometry and tangent metadata are
not consumed as boundary conditions.  If the overlay cannot be contained by
the source frame, or any solver-produced station leaves the declared frame,
the closure returns a typed remesh failure without extrapolation or endpoint
holding.

The two-step feedback regression, zero-extension-budget stop, and all five
global coupled-boundary-feedback tests pass.  Solver-owned continuation and
shock-front handoffs are also refreshed by object identity after each fresh
upstream closure, preventing a downstream iteration from using stale field
lineage.  This advances global coupling evidence but does not close the
canonical mixed-regime downstream boundary, physical shock-cell acceptance,
external validation, or production release gates.

### P3 indexed external-review handoff checkpoint — 2026-09-08

The accepted local P3 continued-chain refinement now has a typed external-data
review adapter.  It selects only the exact highest-resolution chain measurement
retained by the refinement ladder, verifies the scalar source-resolution
lineage against the coupled case resolution tuple, and preserves the
research-only fidelity boundary before delegating to the existing exact-index
external comparison operator.

The adapter requires caller-provided calibration and validation datasets,
explicit provenance and coordinate metadata, exact indexed coverage, and an
owner-declared residual/uncertainty policy.  It performs no calibration,
interpolation, origin fitting, feature synthesis, or product promotion.  Even
when an external review passes, canonical reflected closure, physical-length
acceptance, and VIS/SIG/RAY/FPA product claims remain separate gates.

The end-to-end coupled-chain regression passes with two disjoint test-only
fixture roles and confirms that external evidence can be recorded while
``physical_length_accepted``, chain promotion, and product claims remain
false.  The owner validation archives and provider-bound observations are
still absent, so this checkpoint does not change the release freeze.

### Terminal final-response audit checkpoint — 2026-09-08 (`0b109e0`)

The bounded outer feedback lane now exposes
``op.moc.reflected-domain.global-coupled-boundary-condition-feedback-terminal-fixed-point``.
It re-measures ``final_closure`` against a fresh downstream feedback field
instead of treating the last upstream solve as self-validating.  The replay
uses the exact retained downstream configuration and refreshes solver-owned
physical-field continuation/shock-front handoffs by final-field identity.  A
caller may also provide a separately retained terminal run; its final-closure
fingerprint, temperature/iteration configuration, response lineage, and
unconsumed proposal are checked before acceptance.

The terminal audit requires covered finite coordinate, tangent, pressure, and
normal-velocity response channels and compares their signed offsets against
explicit research tolerances.  The current target passes this terminal local
response check in both supplied-run and replayed-run paths.  The audit still
reports ``global_coupling_verified=false``,
``downstream_boundary_closure_verified=false``,
``chain_promotion_blocked=true``, and ``production_claim_allowed=false``.
This closes a missing end-of-loop evidence seam only; it does not establish
canonical reflected/mixed-regime closure, physical shock-cell acceptance,
provider-bound product validation, or release readiness.

### P2.2c per-case terminal closure gate — 2026-09-08 (`2661343`)

The cross-case refinement runner now independently applies the terminal
fixed-point audit to every retained resolution case.  Each case stores the
typed audit and reports its final-closure fingerprint, refreshed solver-owned
handoff lineage, covered response channels, explicit offset tolerances, and
fidelity-isolation result.  The aggregate measurement now requires every case
to pass this terminal audit before it can be locally research-verified or
reported as a stable refinement; a failed audit has its own typed
``TERMINAL_FIXED_POINT_FAILURE`` status rather than being hidden behind a
generic stability result.

The focused cross-case regression passes for both the coarse stability-stop
and the fine research-converged ladder (``2 passed``); Ruff, Pyright,
documentation lint, and diff checks are green.  This strengthens the local
P2.2c evidence boundary but does not change the claim ceiling:
``global_coupling_verified=false``, canonical closure remains open, physical
shock-cell observations remain absent, and production claims stay blocked.
The exact pushed candidate also passes the full repository regression:
``1179 passed, 18 warnings``.  The warnings are pre-existing legacy-API and
projected-area numerical warnings; they do not alter the release blockers.

### Trace-referenced global remesh research-lane checkpoint — 2026-09-08 (`f4e0e76`)

The reflected-trace compression profile now uses the retained outgoing trace
as a piecewise-linear flow-angle baseline in ordinate.  It no longer silently
replaces the measured interior angles with an affine first-angle surrogate;
the positive ``4*s*(1-s)`` envelope remains an explicit research boundary
condition with zero-strength endpoints.

The solver-owned first-cell and global shock-remesh APIs now expose an opt-in
``use_trace_referenced_profile`` lane.  That lane is deliberately restricted
to the exact retained outer seed and first generated centerline state
(``outer_source_index=0``, ``target_centerline_index=0``), records the mode in
typed results and reports, and is independently remeasured for source,
profile, attempt, endpoint, and fidelity lineage.  It does not reinterpret a
trace-seeded front as an ordinary outer-row remesh and cannot promote a chain
cell.

The new local evidence passes the 48-test physical-cell suite and 19 targeted
reflected-domain/global-closure tests, plus Ruff, Pyright, compilation, and
diff checks.  The trace-seeded candidate remains a no-endpoint-root research
result; the high-level global closure returns a typed Euler/source-frontier
failure when the positively compressed endpoint remains outside the first
retained centerline edge.  This is useful failure evidence, not canonical
closure.  The full repository regression was refreshed after this checkpoint
by ``f167d69``; the compatibility result is recorded below.

This checkpoint therefore leaves the claim ceiling unchanged:
``canonical_free_boundary_verified=false``,
``canonical_euler_verified=false``,
``external_validation_verified=false``, physical shock-cell observations are
still absent, and ``production_claim_allowed=false``.

### Trace-baseline compatibility checkpoint — 2026-09-08 (`f167d69`)

The retained-trace baseline is now explicitly opt-in.  Existing terminal
reflection and geometry-owned research chains retain the established affine
endpoint law by default, while the new global trace-seeded research lane
passes ``use_interpolated_trace_baseline=true`` and records the
piecewise-linear retained-trace baseline in its profile report.  This keeps
the two fidelity lanes segregated instead of silently changing an established
research result while adding the new experiment.

The focused compatibility regressions pass, including the deterministic
geometry-owned chain and validation-report tests that previously detected the
behavioral drift.  The exact pushed candidate also passes the complete
repository regression: ``1181 passed, 18 warnings`` in ``1213.24s``
(``20:13``).  The warnings are the existing legacy-API deprecations and
projected-area numerical warnings; no new failure or promotion violation was
introduced.  The branch is pushed and remains clean at this checkpoint.

This is release evidence for regression stability only.  It does not close
canonical reflected/free-boundary physics, physical shock-cell acceptance,
provider-bound VIS/SIG/RAY/FPA validation, missing validation archives, or the
release freeze; the current claim ceiling remains research-only.

### Current-candidate packaging and lane-audit checkpoint — 2026-09-08 (`8e23dc1`)

The current committed candidate passes the local packaging and lane-audit
surfaces: ``python3 scripts/check_build.py --offline`` built a fresh wheel,
installed it into a clean temporary environment, and completed the installed
smoke; ``python3 scripts/validate_product_lanes.py`` returned
``local_status=passed``; and ``python3 scripts/validate_lane_releases.py``
reported no low-fidelity promotion violation.  The complete repository
regression remains ``1181 passed, 18 warnings``.

The lane audit still reports ``release_ready=false`` for the correct reasons:
the current release-freeze artifact is historical rather than bound to this
candidate, provider comparisons are not externally accepted, the reduced-
order lane has no accepted disjoint physical calibration/validation split,
and the planar-MOC/physical-length gates remain open.  The wheel smoke and
local lane checks therefore establish package integrity and scoped local
release evidence only; they do not authorize a product claim or release tag.

### Full product-suite release map — 2026-09-08

This is the go-forward definition of completion for the long-running goal.  A
green local test run is necessary evidence, but it does not close a product
lane unless the lane's own measurement space, fidelity, and external evidence
are also accepted.

| Gate | Must be true | Current state | Unlocks |
| --- | --- | --- | --- |
| Branch and contracts | Dedicated branch is clean, pushed, and every merged slice preserves the stricter contract and claim ceiling | `work/washed-integral-visual` is clean and pushed; latest tested code candidate is `e81d4e9`; no release tag | Safe integration and review |
| Visualization | All five model lanes emit the common bundle, views, slices, paths, regions, masks, diagnostics, and provenance; supplied provider overlays use the declared operator | Local standardized gallery is complete; provider comparison is pending | Visualization product claim |
| Mission-time composition | State/cursor advancement preserves source, pose, atmosphere, chemistry, optics, ray, Signature, and FPA lineage without inferred time evolution | Local timeline and exact Signature/FPA point/timeline seams are present | Time-resolved product demonstrations |
| Solver fidelity | Basic, reduced-order, straight/washed, and planar-MOC lanes remain independently configured and promotion-guarded | Local separation passes; planar-MOC is still research-only | Controlled use of each fidelity |
| Canonical physical field | A solver-owned reflected/mixed-regime free boundary closes geometry, Euler residuals, entropy, ambient attachment, centerline reflection, conservative boundary flux, and refinement; an independent audit agrees | P2.2 moving-frame and fine-ladder evidence pass locally, but canonical closure remains open | Physical shock-cell fitting |
| Physical shock cells | First and continued cells come only from the accepted physical field, have solver-owned lengths and uncertainty, and pass disjoint physical observations | Research fits and indexed-review plumbing exist; physical observations are absent | Chain promotion and physical plume claims |
| Signature and ray | Source-bound chemistry/radiation and ray-transfer outputs are compared in the declared spectral/radiometric measurement space with provider cases | Local table/gray/LTE/timeline paths pass engineering checks; provider-bound evidence is pending | Signature product claim |
| FPA | Camera, optics, detector, pixel, exposure, digitization, and invalid-ray behavior are compared against supplied FPA observations in pixel/ADC space | Deterministic downstream boundary is implemented; no FPA observation corpus is available | FPA product claim |
| Validation intake | V8 and separately named alignment archives match their recorded digests, retain provenance/member checksums, and provide disjoint calibration/validation cases plus provider outputs | Both owner archives are missing from the checkout/attachment paths | External validation gates |
| Release freeze | Exact-HEAD lane manifest, full tests, static checks, docs, public contracts, wheel build, installed-wheel smoke, and package metadata are green; no blocker remains | Historical freeze remains `release_ready=false` and must not be reused as current evidence | Release tag and production claims |

The remaining work is therefore executed in five waves:

1. **Intake and measurement binding (parallel).** Obtain the recorded V8
   archive and the separate alignment archive; verify digests, member
   checksums, provenance, license, coordinate conventions, and disjoint
   calibration/validation roles.  Obtain the provider-bound Visualization,
   Signature/ray, and FPA measurement outputs and register each operator.
2. **Canonical solver closure.** Replace the current research boundary
   envelope with the solver-owned mixed-regime/free-boundary law.  Preserve
   the current moving-frame and conservative-flux audits, add the missing
   physical closure equations and independent re-derivation, and repeat the
   result across disjoint cases and strictly increasing resolutions.  A
   pressure/geometry profile, endpoint hold, extrapolation, or lower-fidelity
   fallback cannot close this wave.
3. **Physical cell acceptance.** Bind the first-cell and continued-chain
   fitters only to the accepted canonical field.  Compare solver-owned
   lengths, spacing, branch identity, and uncertainty against the disjoint
   physical observations.  Keep the current indexed external-review adapter
   as an evidence handoff only; it must not promote a research fit by itself.
4. **Product acceptance.** Run the five Visualization lanes, Signature/ray
   operators, and FPA chain against their own provider-bound cases.  Confirm
   that missing coverage remains masked, time/pose/source lineage is exact,
   and no planar-MOC result is routed backward into a lower-fidelity product.
5. **Exact-candidate release.** Refresh the freeze and lane manifest from the
   actual candidate `HEAD`; run the complete test, static, documentation,
   public-contract, wheel, and installed-wheel matrix; inspect every blocker;
   and create a tag only after `release_ready=true`.

The working rule for this goal is to keep the current dedicated branch as the
integration candidate, commit vertical slices, and merge toward `main` only
after their contracts and focused evidence are reviewable.  Missing archives
or provider outputs are external blockers to record and request, not inputs to
replace with synthetic observations.  Approximate lanes remain useful for
Visualization and engineering exploration, but they never inherit the
canonical solver's unresolved claims.

### Active execution decision checkpoint — 2026-09-08 (`e81d4e9`)

The current branch is the clean, pushed integration candidate.  The local
acceptance matrix is green on the preceding code candidate (`1188 passed, 18
warnings`; Ruff, Pyright, documentation, lane partition, public-contract
assets, offline wheel build, and installed-wheel smoke all passed), and the
latest commit records that evidence without changing runtime behavior.

The next implementation slice is the solver-owned canonical reflected /
mixed-regime closure, not product promotion.  It must produce a fresh field
that closes the physical boundary, Euler residuals, entropy transport,
centerline reflection, ambient attachment, conservative boundary flux, and
strict refinement on the target case, with an independent re-derivation.  The
existing moving-frame, profiled-pressure, exact-handoff, and fine-ladder
results are prerequisites and research evidence only; none may be relabelled
as canonical closure or used to fit production shock cells.

In parallel, validation intake remains an owner-supplied dependency.  When the
Version 8 and alignment archives plus provider-bound VIS/SIG/RAY/FPA outputs
arrive, ingest them through the strict digest and measurement-operator
handoff, assign disjoint calibration/validation cases, and run those product
comparisons without changing solver claim ceilings.  Until then, keep the
provider and physical gates explicitly pending, continue focused local
regressions after each vertical slice, and do not create a release tag.

### Five-lane executable Visualization checkpoint — 2026-09-08

The product-lane validator now exercises the complete standardized
Visualization adapter, not only the basic straight provider.  Its local
contract fixture produces one common bundle for
`shock-cell-basic-v1`, `shock-cell-reduced-order-v1`, `straight-integral-v1`,
`washed-integral-v1`, and `planar-moc-primitives-v1`, checks the common section
shape and deterministic serialization, and verifies that only the basic lane
retains its existing local production flag.  Reduced-order, integral, and
planar-MOC bundles remain explicitly non-production.

The focused validation passes (`8 passed`), and the complete product-lane
validator returns `local_status=passed` while retaining
`release_ready=false`.  These fixtures establish local adapter coverage only;
provider-bound visual observations, canonical planar-MOC closure, and the
remaining Signature/ray/FPA external gates are unchanged.

### Mission-time executable product-composition checkpoint — 2026-09-08

The product-lane validator now exercises the prescribed mission-time seam
across all three products.  A repository-local three-state schedule at 0, 5,
and 10 seconds is advanced without inferred temporal evolution and is checked
for exact source snapshot, pose, and lineage preservation.  The Visualization
lane emits one snapshot per mission state; the Signature lane produces an
exact angular timeline, heat map, and point query; and the FPA lane produces
an exact exposure timeline, deterministic detector/ADC outputs, and a selected
pixel projection.

The focused mission-time and adjacent product regression slice passes
(`54 passed`), and the complete product-lane validator reports
`local_status=passed`.  The report keeps the mission-time claim ceiling at
prescribed composition with exact source lineage: it does not claim a solved
transient, trajectory, chemistry, detector-noise process, or external product
comparison.  Provider-bound observer, atmospheric, detector, and trajectory
measurements remain release gates.

### Full regression refresh after mission-time release binding — 2026-09-08 (`4bcc9ff`)

The exact pushed candidate passes the complete repository regression:
`1183 passed, 18 warnings` in 20:12.  The warnings are the existing legacy
compatibility and projected-area numerical warnings; no test failed.  This
refresh validates the release-manifest and current-evidence changes across the
full repository, but it does not close the external provider, alignment, or
canonical physical-closure blockers recorded above.

### Current local evidence and release-manifest binding checkpoint — 2026-09-08

The committed local product report and lane-release manifest were refreshed
from the current checkout.  The report now includes the prescribed mission-
time composition record, and the manifest checks that Visualization,
Signature, and FPA all pass at the exact 0, 5, and 10 second schedule.  It
also records when a matrix lane is evidenced by the standardized five-lane
Visualization bundle rather than by a separate provider report; the washed
integral lane is currently resolved through that explicit source.

The refresh was run without `--corpus` because the Version 8 archive is not
present in the current checkout.  The report therefore records
`external_corpus.status=not-provided`, while preserving the external claim
ceiling and keeping `release_ready=false`.  This is a current local evidence
refresh, not a replacement for the missing archive or provider-bound
measurements.

### Coupled-Euler boundary-trace contract checkpoint — 2026-09-09

The global-to-coupled downstream candidate now retains an explicit full-state
boundary trace reconstructed from its audited coupled-Euler top row.  Each
trace sample carries conservative state, density, velocity, static and total
pressure, temperature, Mach, entropy proxy, flow angle, and exact boundary
coordinates; pressure, normal-velocity, and geometric-tangent residuals are
retained on their aligned node/segment grids.  The trace is a separate
contract from the supersonic MOC frontier because the coupled field may be
subsonic, so it cannot be silently cast into `CharacteristicState` samples.

The trace is locally independently checkable and is useful input for the
future global feedback operator, Visualization, and Signature sampling.  It
still reports canonical free-boundary and downstream closure as false and
blocks chain/production promotion.  Global feedback consumption, strict
cross-case refinement, disjoint physical observations, and the missing V8 /
alignment/provider archives remain release blockers.

### Coupled-Euler trace consumption in feedback ladder — 2026-09-09

The downstream pressure/geometry feedback ladder now consumes the full-state
boundary trace as an iteration gate.  Every fresh solve must retain the exact
closure fingerprint, a locally verified trace, and the trace's explicit
research-only promotion ceiling before the ladder can report a converged
research update.  Missing or mismatched trace lineage now fails the feedback
step rather than allowing the older overlap response alone to stand in for a
full-state boundary contract.

This strengthens global reconciliation evidence without claiming upstream
global re-solve, canonical mixed-regime closure, physical shock-cell
promotion, or production validity.

### Coupled-Euler trace consumption in refinement ladders — 2026-09-09

The resolution and cross-case refinement operators now retain the same
full-state coupled-Euler boundary trace as the feedback ladder.  A refinement
case must carry exact closure lineage, a locally verified trace, and the
trace's research-only promotion ceiling before its response ladder can report
convergence.  The cross-case aggregate also exposes and gates on that trace
evidence for every named closure, so a locally converged overlap response
cannot hide a missing full-state boundary contract.

The focused refinement/feedback slice passes (`4 passed`), with Ruff,
Pyright, and compilation checks passing.  This is still local research
evidence: canonical global closure, physical shock-cell acceptance,
provider-bound observations, and release tagging remain separate gates.

### Separate alignment-archive preflight checkpoint — 2026-09-08

Provider-comparison preflight now accepts the separately named
`plume_mvp_validation_alignment_v1.zip` through `--alignment` and verifies it
against the content-addressed intake manifest.  Its report distinguishes
`verified`, `missing`, and `not-provided` states and retains the release blocker
until the archive is actually present and verified.  The embedded alignment
overlay remains a scoped repository reference only; it cannot satisfy this
gate or promote a VIS, Signature, ray, or FPA comparison.

### Current alignment-preflight candidate checkpoint — 2026-09-08 (`768b964`)

The provider-comparison preflight now binds the separately named alignment
archive to the validation intake manifest.  Commit `9550f46` added the
content-addressed archive check and the explicit `not-provided`/`missing`
states; `768b964` refreshed the lane-release manifest against that candidate.
The focused validation slice passes (`20 passed`), with Ruff, Pyright, and
documentation checks also passing.  The earlier complete regression remains
the recorded baseline (`1183 passed, 18 warnings` at `6588209`); it has not
been re-run after this narrow preflight change.

The manifest correctly remains `release_ready=false`: the raw V8 and
alignment archives, provider-bound VIS/SIG/RAY/FPA observations, canonical
mixed-regime closure, accepted physical shock-cell lengths, and exact current
release freeze are still open.  No synthetic archive or embedded overlay is
being promoted as external evidence.

### Provider-bound asset digest verification checkpoint — 2026-09-08

The provider-comparison preflight now has a strict
`exhaust-plume.provider-bound-asset-manifest@1` handoff.  When a provider
submits accepted evidence, the preflight requires a separate asset root and
manifest, matches every source asset, provider output, and operator-manifest
digest to the typed evidence envelope, rejects path traversal, and fails closed
on missing or tampered files.  Diagnostic and blocked handoffs remain usable
for review without those files, but cannot promote a comparison.  This closes
an evidence-integrity seam; it does not create the missing V8/alignment data or
change the external-validation and release blockers.

### P2.2 joint-boundary consumption checkpoint — 2026-09-08

The reflected alternating source now has an explicit, opt-in joint boundary
consumer.  When a downstream target includes pressure, coordinates, and flow
tangents, the solver intersects the declared curve with the incoming C+
characteristic, checks the outgoing boundary characteristic, and records the
coordinate, pressure, and tangent residuals.  An unreachable target returns
`GEOMETRY_TARGET_FAILURE`; it is not projected onto the existing pressure-only
march.  The global physical-closure entry point exposes the same opt-in seam
and carries whether the geometry was actually consumed into its lineage report.

The pressure-only path remains unchanged for existing research callers.  The
new joint path is still research-only: it does not replace the compression
envelope with a canonical mixed-regime law, does not authorize chain-cell
fitting, and does not set any production flag.  Focused validation passes
(`15` alternating-source tests, including exact-consumption and hard-stop
cases); the canonical reflected/free-boundary equations, independent
refinement, external comparisons, and release gates remain open.

### Candidate release-manifest rebinding checkpoint — 2026-09-08 (`3ba857f`)

The committed lane-release manifest has been rebound to the current integrity
candidate.  Its local lane records and mission-time composition remain
deterministic, while the umbrella release remains blocked by the missing
provider-bound assets, canonical physical-field closure, accepted physical
shock-cell observations, and exact release freeze.  Rebinding provenance does
not turn a local manifest into external validation evidence.

### Fresh candidate quality checkpoint — 2026-09-08 (`63ab69c`)

The exact pushed candidate completed the fresh local quality matrix: `1188
passed, 18 warnings` in `20:07`; Ruff, Pyright, documentation checks, the
12-lane partition (`138` test modules), and deterministic public-contract
asset checks all passed.  The offline wheel build and installed smoke also
passed, retaining the known expansion-fan diagnostic warnings and no test
failure.  This refresh strengthens the local package evidence only.  The
provider-bound comparison, missing V8/alignment assets, canonical physical
closure, accepted physical shock-cell observations, and release-freeze
provenance gates remain open, so `release_ready` stays false.

### Global frontier geometry-consumption checkpoint — 2026-09-09

The global frontier boundary-condition resolver now exposes an explicit
research-only `consume_target_geometry` mode.  The default pressure-only
consumer retains the prior solver-owned geometry contract.  The opt-in path
passes the declared coordinates and flow tangents into the fresh global
source march, verifies that the exact source closure retained that geometry
consumption, and fails closed if the target cannot satisfy the characteristic
and pressure seams.  The downstream ambient boundary remains solver-owned;
this is not a canonical two-dimensional free-boundary solve.

The result and standardized Visualization adapter now distinguish
`solver_owned_geometry_verified`, `target_geometry_consumed`, and the shared
`geometry_conditioning_verified` gate.  The focused frontier boundary/
refinement/cross-case regression passes (`6 passed`), with Pyright, Ruff, and
compilation checks passing.  This strengthens the target geometry seam while
leaving global coupling, canonical closure, physical shock-cell acceptance,
provider-bound validation, release-freeze provenance, and `release_ready`
blocked.

### Geometry-conditioned global feedback checkpoint — 2026-09-09

The explicit-overlay target composer now retains complete base geometry and
tangent metadata when the downstream overlay is intentionally pressure-only;
partial metadata is not synthesized.  This allows the joint research mode
to carry the solver-owned base frame into the fresh global source march
without treating a pressure response as a geometry profile.

The downstream/global feedback runner now exposes and reports
target_geometry_consumed and geometry_conditioning_verified as first-class
iteration and run gates.  On the retained mixed-regime target, the
geometry-conditioned feedback run completes its bounded research step and
retains the moving-frame extension evidence.  The composition test and six
feedback regressions pass; canonical global closure, physical shock-cell
acceptance, provider-bound validation, and production promotion remain
blocked.

### Current candidate evidence refresh checkpoint — 2026-09-09

The tracked lane-release manifest has been regenerated from the current clean
candidate `e5b2483` after the geometry-conditioned feedback slice.  The local
product report remains passing for the standardized Visualization bundle,
mission-time composition, Signature engineering paths, and deterministic FPA
boundary; the manifest now records the actual candidate HEAD instead of the
previous checkpoint.  `release_ready` remains false because the canonical
mixed-regime field, accepted physical shock-cell observations, provider-bound
VIS/SIG/RAY/FPA evidence, alignment archive, and release freeze are still
open.  This is provenance repair, not a promotion or release decision.

### Canonical transonic-closure seam audit checkpoint — 2026-09-09

The current physics implementation was re-audited at the seam that still
blocks canonical planar-MOC closure.  The repository now has four useful,
typed research components: scalar shock-state compatibility, bounded
characteristic transport, resolved-frontier intersection, and field-bound
normal-shock interface profiles.  Each component preserves state/pressure
lineage and independently reports its local residuals.  These components are
valid prerequisites for the next solver, but they do not solve the missing
global operation.

The missing operation is a fresh solver-owned mixed-regime solve that chooses
the interior transonic interface while simultaneously satisfying the upstream
field, downstream conservative state, free-boundary geometry/tangency,
centerline reflection, ambient attachment, entropy inequality, and Euler
residuals.  The existing coupled-Euler lane can consume a cross-section
profile or a solver-owned field placement, but those are inlet handoffs and
remain research-only; the scalar compatibility diagnostics intentionally
return a typed failure when the retained global frontier does not contain the
required upstream state.  No low-fidelity fallback or synthetic placement is
permitted.

The next physics work package is therefore **P2.2d — solver-owned interior
transonic/free-boundary closure**:

1. Define one request/result carrying the exact source-closure and frontier
   fingerprints, an interior interface candidate, and a bounded station/frame
   policy.
2. Solve the upstream/downstream fields and interface geometry together;
   consume only retained states, never an endpoint hold, extrapolated
   pressure, or caller-injected geometry.
3. Independently rederive interface Rankine--Hugoniot state, free-boundary
   pressure/tangency, centerline and ambient fluxes, entropy, and cell-Euler
   residuals from the returned field.
4. Run the new operator on the existing fine disjoint ladder and require
   stable interface location, residuals, and solver-owned axial length before
   allowing P3 physical-cell fitting to consume it.

Until that package passes, the current attachment/profile/feedback evidence
continues to support Visualization and engineering diagnostics only. It may
not authorize physical shock-cell promotion, Signature/FPA validation claims,
or a release tag.

### P2.2d interface-consumption audit checkpoint — 2026-09-09

The first P2.2d vertical slice is now implemented as
``op.moc.reflected-domain.global-transonic-interface-audit``.  It audits the
existing solver-owned interior-interface candidate without changing its claim
ceiling.  The audit requires exact global-closure and placement lineage,
full-span placement evidence, the exact coupled-Euler request/placement
identity, downstream mesh anchoring at the retained interface cross-section,
and exact profile consumption.  It independently reconstructs every
downstream inlet conservative state from the retained subsonic interface
profile and reports the maximum component-wise seam residual.

The compatible research fixture passes the new audit and a tampered inlet
state is rejected with a typed inlet-seam failure.  The adjacent transonic /
global-coupled regression passes (`21 passed`), the attachment suite passes
(`13 passed`), and configured Pyright, Ruff, compilation, and diff checks pass.
The audit intentionally reports local interface handoff only; it does not
claim canonical mixed-regime closure, global feedback, refinement, physical
shock-cell acceptance, or production validity.  The next P2.2d slice is to
consume this seam in a joint interface/field iteration and independently
rederive the interface jump plus centerline/ambient boundary residuals.

### P2.2d feedback-gate checkpoint — 2026-09-09

The seam audit is now consumed by the existing downstream/global feedback
ladder whenever the explicit
`SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE` lane is selected.  Each fresh
coupled result retains its typed interface audit; the feedback run reports a
dedicated transonic-interface failure when placement, field lineage, mesh
anchoring, or independently reconstructed inlet states do not pass.  The
outer boundary-condition feedback path requires the aggregate audit before it
accepts a downstream proposal, while the default full-state and physical-field
continuation lanes remain unchanged.

The combined focused explicit-interface/global-downstream/boundary-feedback
selection passes (`11 passed`) and now exercises the typed ambient-boundary
residual stop.  The audit remains research-only and promotion-blocked;
canonical mixed-regime closure, global upstream feedback, centerline/ambient
residual closure, refinement, physical shock-cell acceptance, provider
evidence, and release freeze remain open.  The next P2.2d slice is to replace
the one-way handoff with a joint interface/field iteration and independently
rederive the interface jump plus centerline/ambient residuals at each iterate.

### P2.2d independent boundary-residual checkpoint — 2026-09-09

The global transonic-interface audit now independently rederives the retained
normal-shock profile build and the downstream coupled field's outer-edge
pressure/tangency residuals.  It also distinguishes the solver-owned
placement profile from the request's mutually exclusive explicit-profile
field, so the coupled-Euler audit no longer reports a false interface-profile
geometry failure on this handoff.

On the actual target fixture, the interface seam and Rankine--Hugoniot
rederivation pass, but the returned field still misses the ambient boundary:
the maximum pressure residual is approximately ``371.3 kPa`` (about ``1.75``
of the ambient pressure) and the normal-velocity residual fraction is about
``0.748``, against declared tolerances of ``0.10`` and ``0.05``.  The result
therefore returns the typed
``global-transonic-interface-ambient-boundary-residual-failure`` status, and
the explicit feedback runner fails closed on that evidence.  Centerline
reflection remains unclosed as well; no canonical field, physical shock-cell
fit, Signature/FPA validation claim, or release promotion is implied.

The next P2.2d implementation slice is a joint solver-owned
interface/field/free-boundary iteration that consumes the interface candidate
inside the equations, closes ambient and centerline neighbors, and repeats the
independent jump, boundary-flux, entropy, Euler, and refinement audits.  The
default full-state and physical-field continuation lanes remain separate and
unchanged.

### P2.2d compression-budget hard-stop checkpoint — 2026-09-09

The next P2.2d vertical slice is now an explicit typed operator,
``op.moc.reflected-domain.global-transonic-interface-closure``.  Its request
binds one exact global physical-closure fingerprint and one exact retained
frontier fingerprint to a fixed solver-owned station/frame policy.  Its result
retains the selected interface candidate, an independently rederived
Rankine--Hugoniot pressure budget, any coupled-field attempt, and the existing
interface/boundary audit without changing the fidelity lanes.

On the retained mixed-regime target, the operator records the actual pressure
infeasibility before starting the downstream field: the minimum retained
upstream static pressure is approximately ``239.5 kPa``, the minimum derived
normal-compression downstream pressure is approximately ``509.6 kPa``, and the
requested ambient target is approximately ``212.2 kPa``.  Because an attached
compression shock cannot lower static pressure, the operator returns the typed
``global-transonic-closure-compression-target-unreachable`` stop with the best
in-domain placement and ``downstream_field_attempted=false``.  No endpoint
hold, extrapolation, oblique-shock fiction, or lower-fidelity fallback is
introduced.

The focused regression, Ruff, Pyright, compilation, scope-marker, and diff
checks pass.  This is a correct physical hard stop, not closure evidence.  The
next physics slice is an expansion/mixed-regime solver-owned interface solve
that can lower pressure while simultaneously closing the centerline and
ambient neighbors; the operator must retain this pressure-budget gate when
that higher-fidelity law is added.  Canonical closure, physical shock-cell
acceptance, provider-bound Signature/FPA validation, and release promotion
remain blocked.

### P2.2d exact-source mixed-regime continuation checkpoint — 2026-09-09

The transonic gate now carries a separate solver-owned expansion/mixed-regime
attempt on the exact retained global Euler field.  The attempt consumes the
field by identity, builds the terminal characteristic wedge, solves the local
entropy-carry trial, and independently verifies the bounded
entropy-characteristic band before trying continuation.  It never imports the
variable-entropy scalar reference or a caller-provided endpoint into the
global lane.

On the retained target, the local band passes, but the continuation remesh
reaches the existing compression-only free-boundary path at a negative-turn
sample.  The result therefore returns the typed
``global-transonic-expansion-required`` stop with the exact source and frontier
fingerprints, rather than converting the failed continuation into a pressure
or geometry value.  ``mixed_regime_closure_verified`` remains false and chain
promotion remains blocked.  The next physics slice is a true shock/expansion
mixed-wave interface law with the same independent centerline, ambient,
entropy, Euler, and refinement audits; this checkpoint is evidence-plumbing
and a bounded research continuation, not canonical closure.

### Long-running execution board — 2026-09-09

This is the active order of work for completing the suite.  The dedicated
branch remains the integration candidate; ``main`` is not the working branch.
The latest committed candidate is clean and published, including this
execution board.  Each item below is a
separate vertical slice with its contract, focused tests, evidence note, and
static checks.  A later item may consume an earlier item only through its
declared contract and claim ceiling.

1. **P2.2d — close the canonical mixed-regime physics seam.** Consume the
   solver-owned signed shock/expansion interface law inside a joint iteration
   of the interface, upstream/downstream fields, centerline reflection, and ambient
   boundary together.  Independently rederive Rankine--Hugoniot, entropy,
   conservative/Euler, geometry/tangency, and pressure/velocity residuals at
   every accepted iterate.  Run the fine disjoint refinement ladder and stop
   on instability or missing physics; do not use endpoint holds, extrapolation,
   scalar fallback, or a lower-fidelity substitute.
   The current entropy-profile consumer is still research-only: it applies a
   fixed-velocity/fixed-temperature relaxation source and must not be treated
   as the canonical mixed-wave closure.
2. **P3 — fit physical shock cells.** Consume only a passing canonical field;
   fit first and continued cells from solver-owned frontier/field geometry,
   report uncertainty and lineage, and compare physical lengths against a
   disjoint accepted validation set.  Diagnostic pressure-extrema spacing is
   not sufficient for promotion.
3. **P1/P4 — bind validation and measurement spaces.** Intake the owner-
   supplied V8/alignment archives and provider outputs, verify provenance and
   digests, define units/frames/operators, and assign disjoint calibration and
   validation cases.  Run each Visualization, Signature/ray, and FPA
   comparison in its own measurement space; missing data stays blocked or
   masked.
4. **Signature — complete the source-bound optical product.** Preserve the
   exact mission-time state/cursor and source lineage, then validate chemistry,
   spectral source, atmosphere, ray transfer, angular heatmaps, and time
   series against accepted operators.  Tables, gray paths, LTE line sources,
   or unresolved MOC fields remain engineering/research outputs until their
   provider gates pass.
5. **FPA — complete the downstream detector product.** Consume a validated
   ray result through camera geometry, spectral response, exposure, detector
   response, expected electrons, ADC, metadata, and invalid-ray semantics;
   then compare in camera/detector measurement space.  Do not infer an FPA
   provider from a deterministic image alone.
6. **Visualization — finish the evidence surface.** Keep all five model
   bundles standardized and separate; expose slices, stations, paths,
   shock/expansion regions, physical channels, masks, uncertainty, provenance,
   and mission-time views without inventing missing values.  Add provider and
   observation overlays only when their source/operator records exist.
7. **Release — freeze and publish.** Reconcile contracts and merge conflicts
   in the dedicated integration branch, run the full test/static/public-API
   matrix, rebuild the package and installed-wheel smoke, refresh manifests
   and documentation, and require ``release_ready=true``.  Only then merge
   toward ``main`` and create a release tag.

Current gate summary: local Visualization, mission-time, Signature
engineering, and deterministic FPA boundary checks pass.  Canonical
mixed-regime closure, physical shock-cell fitting, owner-supplied validation
assets, provider-bound comparisons, and release freeze remain open.  The
active next slice is the joint P2.2d interface/field iteration; no product
claim or release tag is promoted by this board.

### P2.2d signed mixed-wave law checkpoint — 2026-09-09

The research MOC lane now has a typed signed local wave law.  Positive turns
use the existing attached Rankine--Hugoniot compression primitive and require
static-pressure increase plus total-pressure loss.  Negative turns use the
finite Prandtl--Meyer inversion with the ``C-`` invariant
``theta + nu`` and constant total pressure, requiring static-pressure decrease.
Zero-strength samples remain explicit Mach-wave limits.  A path wrapper accepts
only explicit, downstream-ordered source states, pressures, and target angles,
retains per-sample regime/residual/pressure evidence, and stops at the first
failure without mutating the source into a marching solution.

The exact-source transonic expansion attempt now retains a separate
solver-owned pressure-target mixed-wave path built from the verified entropy
frontier.  Each source state derives its target Mach/angle from the retained
total pressure and the requested ambient pressure, selecting an attached shock
when the target is above a local source and an isentropic expansion when it is
below.  The path independently checks the resulting static-pressure residual.
On the retained target, all three local source states are below ambient, so
the local path converges with attached-compression samples even though the
upstream global compression budget still requires an expansion-capable global
solve.  The hard-stop regression passes with that path converged, while the
existing continuation still returns ``global-transonic-expansion-required``.
The new law and probe remain research-only: they do not close the global
free-boundary, centerline/ambient neighbors, conservative Euler residuals,
refinement ladder, physical shock-cell fit, provider validation, or production
promotion.  The next slice is to consume the signed law in the joint
interface/field iteration and independently audit every boundary at each
iterate.

### P2.2d solver-owned mixed-wave interface checkpoint — 2026-09-09

The exact entropy-characteristic frontier now feeds a separate
op.moc.reflected-domain.global-transonic-mixed-wave-interface operator.
It consumes the source field by identity, pressure-matches the signed local
wave path, derives an explicit solver-owned outer turn, marches a generated
shock to the symmetry line, refits the retained preterminal shock geometry,
and independently marches the ambient-pressure boundary.  The terminal is
retained as a typed subsonic normal-shock seam; no caller-supplied shock points
or endpoint values are accepted.

The retained target passes the local interface gates: frontier lineage,
pressure target, angle-law endpoints, shock fit, ambient pressure/tangency,
and typed subsonic terminal.  This evidence is deliberately narrower than a
physical closure: the centerline perimeter and global upstream/downstream
feedback remain false, chain promotion is blocked, and production claims are
disallowed.  When the optional scalar strict-subsonic reference is run, it
returns the typed pressure-unreachable result because the terminal total
pressure is too high to reach the ambient target on that branch; this is kept
as evidence rather than hidden by a fallback.

The focused transonic regression and static checks pass.  The next physics
slice is to consume this interface inside the joint field iteration and
independently rederive shock, entropy, Euler, geometry, centerline, ambient,
and refinement residuals at every accepted iterate.  Canonical closure,
physical shock-cell fitting, provider-bound validation, and release promotion
remain blocked.

### P2.2d transonic-placement consumption checkpoint — 2026-09-09

The mixed-wave downstream operator now binds the retained solver-owned,
full-span transonic interface placement before invoking the coupled field.
Placement is derived from the exact retained global physical field, independently
audited, and passed through the dedicated
``SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE`` mode.  The downstream result
retains placement identity and separately reports whether both the placement
and its profile were consumed; the mixed-wave perimeter and entropy handoff
remain distinct exact contracts.

On the current fixture, this advances the field past the previous typed
``coupled-euler-transonic-frontier-failure`` stop.  The field consumes the
placement and profile, then returns the typed
``coupled-euler-free-boundary-failure`` because the ambient pressure/tangency
residual tolerance is not reached.  No field result is promoted: centerline
closure, joint interface feedback, refinement, external validation, physical
shock-cell fitting, Signature/FPA acceptance, and release gates remain open.

The next physics slice is to make the placement and mixed-wave terminal part
of one joint interface/free-boundary iteration, reducing the retained ambient
and tangency residuals while independently rederiving jump, entropy,
conservative/Euler, centerline, geometry, and refinement evidence at every
accepted iterate.  The field must continue to fail closed when those gates do
not pass.

### P2.2d exact mixed-wave downstream-consumption checkpoint — 2026-09-09

The solver-owned mixed-wave terminal now has an explicit opt-in request seam,
``build_reflected_domain_mixed_regime_boundary_request_from_perimeter``.  The
legacy mixed-regime builder remains bound to the global-Euler terminal seam;
the new builder requires the exact perimeter source, an exact entropy
handoff, an anchored control section, and the retained global-closure
fingerprint before a coupled field can consume the request.

The new
``op.moc.reflected-domain.global-transonic-mixed-wave-downstream-field``
operator consumes that request in the coupled constant-γ Euler/free-boundary
solver and retains the field result, mesh contract, entropy handoff, and
control-section provenance.  On the current target fixture, the field reaches
the existing typed ``coupled-euler-transonic-frontier-failure`` stop because
the retained global frontier does not contain the scalar upstream state needed
to place the transonic interface.  No field iteration or lower-fidelity
fallback is attempted.  This is a useful source-to-consumer stop, not closure
evidence: centerline closure, global feedback, refinement, external
validation, physical shock-cell fitting, Signature/FPA acceptance, and release
promotion remain blocked.

### P2.2d open shock/ambient characteristic-net checkpoint — 2026-09-09

The mixed-wave interface now consumes the existing shock/ambient
characteristic-strip assembler in an explicit open-endpoint mode.  The
default strip contract still requires a centerline shock endpoint; the new
mode is used only because this mixed-regime handoff retains a separate scalar
subsonic normal-shock terminal just downstream of the supersonic net.  The
assembler verifies the shock-sourced ``C+`` and ambient-sourced ``C-``
characteristics, connected topology, strict geometry, pressure/tangency
conditions, and terminal trace without coercing the subsonic state into the
supersonic MOC state type.

The current target consumes a connected 45-node/44-cell open strip.  It is
stronger local interface evidence, but ``physical_closure_verified`` remains
false because the terminal trace, subsonic field, centerline closure, and
global feedback are still unresolved.  The ambient-strip lane (17 tests),
transonic regressions, Ruff, and bytecode checks pass.  The next physics slice
is a solver-owned subsonic/terminal patch that closes this net into the
downstream field while retaining the same entropy, Euler, geometry, and
refinement gates.

The next P2.2d slice is therefore to place the solver-owned transonic
interface inside this downstream field (or to implement a joint interface/
field iteration that solves for it), then independently rederive the jump,
entropy, conservative/Euler, ambient, centerline, geometry, and refinement
residuals at each accepted iterate.  The full-suite order remains: canonical
planar-MOC closure, physical shock-cell fitting, owner-supplied validation
archives and provider comparisons for Visualization/Signature/ray/FPA,
release-manifest refresh, package smoke, and only then merge toward ``main``
and tag.

### P2.2d additional-entropy requirement checkpoint — 2026-09-09

The mixed-wave downstream result now distinguishes a typed
``mixed-wave-downstream-additional-entropy-required`` stop from an ordinary
coupled-field failure.  When the exact perimeter, entropy handoff, and
solver-owned full-span transonic placement are consumed but the field returns
an ambient free-boundary failure below the isentropic subsonic pressure
bounds, the result retains the exact pressure-budget object and exposes the
minimum additional total-pressure loss fraction.  The result remains
research-only, promotion-blocked, and production-disallowed; no loss,
geometry, endpoint, or lower-fidelity substitute is invented.

On the retained target, increasing the field budget to 1,500 pseudo-time
iterations and 60 shape iterations leaves approximately 233 kPa of maximum
ambient pressure residual and a 0.074 normal-velocity residual fraction.  The
independent budget still requires approximately 47.5% additional total-
pressure loss.  This confirms that the open seam is physical closure physics,
not an iteration-limit classification.  The focused regression passes.  The
next P2.2d slice must add and audit the actual joint mixed-wave/interface,
entropy-producing, centerline, and ambient closure mechanism before any
canonical field or shock-cell fit can consume it.

### P2.2d interface-coverage checkpoint — 2026-09-09

The downstream handoff now retains a typed geometry audit between the exact
mixed-wave interface and the solver-owned transonic field placement.  The
audit consumes the retained open shock/ambient characteristic strip and the
exact terminal coordinate.  It requires both boundaries to span the selected
cross-section; it does not extend either trace or infer a missing connecting
surface.

On the current target, the field placement is downstream of the shorter exact
shock/ambient trace by more than 0.2 m.  The coupled field is still run as a
bounded research diagnostic so its pressure and velocity residuals remain
available, but any future local field convergence will be classified as
``interface-coverage-required`` until this geometric seam is actually solved.
The baseline full 1,207-test lane passed before this audit; the post-change
focused regression, static checks, and bytecode checks pass.  A complete
post-change lane rerun remains a release-freeze task.  Canonical mixed-regime
closure, physical shock-cell fitting, provider-bound validation, and release
promotion remain blocked.

### P2.2d explicit entropy-profile contract checkpoint — 2026-09-09

The mixed-wave downstream pressure-budget stop now has a typed
``op.moc.reflected-domain.global-transonic-mixed-wave-entropy-closure``
contract.  A candidate mechanism must provide every downstream station, a
non-increasing total-pressure-loss profile, the static-pressure target at each
station, the exact global-closure/perimeter lineage, and at least the measured
additional-loss budget.  The builder does not invent a spatial loss law from a
single scalar budget, regrid stations, or turn a pressure target into a field
solution.

The retained target accepts an explicitly declared profile at the exact
coupled-field cell centers and reports
``mixed-wave-entropy-profile-ready-for-joint-interface-field-solver``.  The
audit also records that a profile-only audit is not a field solve,
``physical_closure_verified`` remains false, and chain/production promotion
remain blocked.  A tampered perimeter lineage is rejected.

### P2.2d research entropy-consumer checkpoint — 2026-09-09

The next seam is now executable in the research lane.  The coupled Euler
solver consumes the exact profile through an explicit fixed-velocity,
fixed-temperature relaxation source, while retaining the ambient static
pressure profile as a separate free-boundary target.  The field result reports
per-cell total-pressure residuals and the independent coupled-field validator
reconstructs the same source contribution before comparing conservative
residuals.  The consumer test proves that the profile is actually carried by
the fresh request and retained in the field result.

This is intentionally not a physical mixing closure: ``physical_closure_verified``
and production claims remain false, centerline/global coupling is still open,
and the consumer cannot promote a shock-cell chain.  The next work must replace
the relaxation with a physically justified mechanism, run refinement and
cross-case evidence, bind validation data, and only then revisit canonical
Signature/FPA promotion.

### P2.2d centerline boundary-evidence checkpoint — 2026-09-09

The coupled Euler/free-boundary research contract now exposes the centerline
normal-velocity residual separately from the outer free-boundary tangency
residual.  The solver records one residual magnitude per axial column (the
signed face-normal value remains in the solver-side measurement), applies a
request-scoped tolerance, and requires that condition for local research
convergence.  The independent validator recomputes the wall-face normals and
centerline residuals from the retained conservative field, verifies the
reported arrays and maxima, and fails closed on a tampered centerline report.

This closes an evidence seam in the current wall-flux implementation; it does
not close the canonical mixed-wave physics.  The centerline result remains
research-only, canonical closure and promotion flags remain false, and the next
P2.2d slice is still a jointly coupled signed interface/field solve with
independent centerline, ambient, entropy, Euler, and refinement evidence.

### P2.2d downstream trace centerline-retention checkpoint — 2026-09-09

The global-to-downstream full-state boundary trace now retains the coupled
field's audited centerline normal-velocity residuals alongside pressure,
outer-boundary normal velocity, and tangent residuals.  Trace construction
requires the centerline array to align with every retained cell column and
requires both the candidate field and its independent audit to verify the
centerline condition.  A downstream feedback consumer therefore cannot
silently drop the centerline gate while carrying the outer boundary trace.

This is contract/evidence propagation only.  It does not create global
feedback, close the mixed-wave interface, or authorize canonical Signature,
FPA, or production claims.

### Candidate functional/package-gate checkpoint — 2026-09-09

The exact clean candidate at ``70357e8`` passed the full release-facing
functional and package checks: ``1,207`` tests passed, the twelve-lane test
partition passed, Ruff, scope-marker, documentation, Pyright, and public
contract-asset checks passed, and the isolated wheel build plus installed-wheel
smoke exited successfully.  The resulting wheel digest was
``c6a9109dccb92fa7755d07d03fd7bb07dc82642de0eb8abb59c66a09c0228bf1``.

The current release manifest confirms a clean checkout and no low-fidelity
promotion, but ``release_ready`` remains false.  Its open blockers are still
canonical mixed-regime closure, accepted physical first/continued shock-cell
fits, provider-bound VIS/SIG/RAY/FPA measurement evidence, the separate
alignment archive, and a release freeze refreshed to the final candidate
commit.  The wheel/build evidence therefore closes a package gate only; it
does not authorize a merge toward ``main`` or a release tag.

### P2.2d conservative ambient-entrainment source checkpoint — 2026-09-09

The mixed-wave research consumer now has a separately identified
``solver-owned-conservative-ambient-entrainment-v1`` mechanism.  Its profile
requires explicit ambient temperature and velocity plus one station-aligned
entrainment fraction per downstream cell column.  The coupled solver forms a
conservative convex mixture of the current cell state and that explicit
ambient state, so density, momentum, and total energy are exchanged together;
the independent coupled-Euler audit reconstructs the same source before
rechecking the residual channels.

The former fixed-velocity/fixed-temperature relaxation remains available as a
named research baseline and is not silently replaced for existing callers.
The new source is still research-only: its total-pressure profile is an
explicit acceptance target rather than a source derivation, no upstream/global
feedback is solved, and canonical closure, refinement, physical shock-cell
fitting, external validation, Signature/FPA acceptance, and release promotion
remain blocked.  The focused mixed-wave regression and the broader coupled-
Euler/MOC subset pass (1 and 14 tests respectively); Pyright, Ruff, bytecode,
documentation, and diff checks pass.

The subsequent full repository regression at ``90c4bc6`` also passes: ``1,207``
tests passed with 18 existing warnings.  The lane partition, public-contract
assets, and offline wheel/install smoke pass at the same source state.  The
release manifest still records ``release_ready=false`` and the candidate is
not frozen for release; these checks establish compatibility and source-term
auditability only.

### P2.2d station-resolved ambient source checkpoint — 2026-09-09

The conservative ambient-entrainment profile now accepts either one explicit
ambient temperature/velocity pair or station-aligned temperature and velocity
profiles.  The coupled solver and independent audit normalize both forms to
the same axial source frame; no altitude, atmospheric composition, or missing
station value is inferred.  This makes spatially varying ambient conditions
available to the research closure while preserving exact source provenance.

The scalar compatibility path and the station-resolved preflight path pass in
the mixed-wave regression; the focused coupled-Euler/MOC subset passes (14
tests), with Pyright, public-contract assets, Ruff, bytecode, and documentation
checks green.  The source remains research-only: no global feedback, canonical
free-boundary closure, physical cell fit, external validation, or product
promotion is implied.

### P2.2d joint interface/free-boundary iteration checkpoint — 2026-09-09

The mixed-wave entropy-closure lane now exposes a bounded joint research
operator, ``op.moc.reflected-domain.global-transonic-mixed-wave-joint-interface-field``.
It consumes the exact solver-owned transonic placement and station-resolved
conservative ambient state, runs the coupled Euler/free-boundary field, and
updates only the explicit station-wise entrainment fractions from signed
boundary and column total-pressure residuals.  Every iterate retains its
profile, field, source lineage, and independent coupled-Euler audit.  The
declared total-pressure loss profile is not rewritten, ambient conditions are
not inferred, and the transonic placement is not extended across a missing
interface span.

The target mixed-wave fixture executes two field iterations with one explicit
source update between them and independently remeasures both fields; the
complete reflected-domain regression passes with 151 tests.  The current
result remains blocked at the known interface-coverage
gap and is not canonical physical closure, global feedback, physical shock-
cell evidence, external validation, Signature/FPA acceptance, or a production
claim.  The next physics gate is to replace the bounded source controller with
an accepted solver-owned interface/entropy mechanism and close the missing
characteristic-to-field coverage without extrapolation.

### P2.2d control-section-anchored placement checkpoint — 2026-09-09

The downstream handoff now passes the exact solver-owned control-section
abscissa into the retained global physical field placement rule.  Placement
selection remains mesh-bound and independently audited, but it discards
retained sections upstream of that anchor and chooses the nearest available
section downstream.  It therefore no longer targets an arbitrary 25% field
fraction when the mixed-regime solver has already declared a downstream
control section.

On the target fixture this moves the selected section from approximately
``x=5.49573 m`` to ``x=5.28131 m`` (downstream of the ``x=5.27135 m`` control
section).  The exact shock/ambient strip still ends earlier, leaving a typed
coverage gap of approximately ``0.03025 m``; no boundary extension,
extrapolation, or promotion was introduced.  The coupled field remains
``additional-entropy-required`` and research-only.  Focused placement and
mixed-wave regressions, Ruff, Pyright, bytecode, and diff checks pass; the
full reflected-domain lane remains the next verification step for this slice.

### P2.2e bounded terminal-reflection probe checkpoint — 2026-09-09

The open global mixed-wave interface now has a separate
``op.moc.reflected-domain.global-transonic-mixed-wave-terminal-probe``
operator.  It consumes only a locally verified shock/ambient strip, reflects
its retained terminal ``C+`` trace to the centerline, and passes the outgoing
``C-`` trace to the existing in-domain next-shock solver.  The operator keeps
the trace tolerance explicit (the target fixture currently requires
``1e-5 m`` at its retained mesh resolution), carries the exact reflection and
shock-probe reports, and exposes a typed subsonic normal-shock reference at
approximately ``x=5.25541 m`` with downstream Mach approximately ``0.73365``.

This is a bounded continuation reference, not a missing-field fill: it does
not extrapolate outside the reflection patch, derive a global feedback law,
solve the downstream subsonic field, or authorize a first/continued physical
shock-cell fit.  ``physical_closure_verified`` remains false,
``chain_promotion_blocked`` remains true, and production claims remain false.
The focused reflected-domain regression passes with this evidence attached;
the next gate is an independently audited subsonic field and refinement
comparison that can consume the terminal reference without reusing the
reduced-order reference as canonical physics.

The same checkpoint now has an independent retained-output audit,
``op.moc.reflected-domain.global-transonic-mixed-wave-terminal-probe-audit``.
It remeasures the open-strip trace identity, reflected ``C-`` geometry,
in-domain shock sampling, state/pressure lineage, subsonic terminal position,
and the hard non-promotion flags.  The audit also rejects a tampered retained
trace in regression coverage.  This strengthens evidence for the next physics
step without changing the release decision: the downstream subsonic field,
global coupling, physical cell fit, external data, and provider comparisons
remain open.

### P2.2e scalar terminal thermodynamic handoff checkpoint — 2026-09-09

The audited terminal reference now has an explicit scalar handoff operator,
``op.moc.reflected-domain.global-transonic-mixed-wave-terminal-transonic-handoff``.
It supplies only the caller-owned total temperature and gas constant, uses the
retained upstream Mach number for a direct Rankine--Hugoniot reconstruction,
and binds the resulting ``MocTransonicShockState`` to the exact retained
terminal point.  The shock normal is derived from the retained upstream flow
direction; the retained terminal's perpendicular shock-surface angle is not
silently reused as a normal vector.

The handoff has an independent retained-state and geometry audit,
``op.moc.reflected-domain.global-transonic-mixed-wave-terminal-transonic-handoff-audit``.
It passes on the target fixture and rejects a tampered terminal point.  The
existing pressure-target transition solver remains correctly separate: the
terminal post-shock static pressure lies within the isentropic subsonic
interval, so it must not be forced through the pressure-target shock branch.

Passing the handoff into the scalar coupled-Euler branch still returns the
typed inlet-location failure: the retained terminal is approximately
``x=5.25541 m`` while the current coupled control-section inlet begins at
approximately ``x=5.26625 m``.  The solver therefore does not shift,
extrapolate, or hold the terminal state.  This closes the missing scalar
thermodynamic seam only; an interior subsonic field or solver-owned moving
interface is still required before canonical closure, shock-cell fitting, or
production promotion.

### P2.2e open-terminal cross-section coverage checkpoint — 2026-09-09

The next seam is now explicit as
``op.moc.reflected-domain.global-transonic-mixed-wave-terminal-field-coverage``.
Given a caller-declared cross-section, the operator independently re-audits
the scalar terminal handoff and samples only the retained terminal reflection
patch.  It records each covered state/total-pressure/static-pressure sample
and the first missing ordinate; it never holds the terminal scalar state over
the section, extends the patch, or converts a supersonic patch sample into a
subsonic field.

The target fixture correctly returns the typed
``global-transonic-mixed-wave-subsonic-field-cross-section-required`` outcome:
the terminal point is bound to the requested section, but the retained patch
does not cover the requested 0.05 m span.  The independent coverage audit
reproduces the missing-sample lineage and preserves
``subsonic_field_required=true``, ``physical_closure_verified=false``, and
the non-promotion flags.  This is evidence accounting and a solver input
contract, not a downstream field solve.  The next implementation slice must
solve a moving mixed-regime interface/subsonic field from conservative
boundary data and repeat the jump, boundary, entropy, Euler, and refinement
audits before any physical shock-cell or Signature/FPA claim can consume it.

### P2.2e terminal-to-field seam decision checkpoint — 2026-09-09

The next implementation boundary has been audited against the actual coupled
Euler request and solver, rather than inferred from the scalar handoff.  The
retained terminal normal shock is approximately at ``x=5.25541 m``; the
reflected patch carries a short supersonic outgoing trace and does not cover a
complete downstream cross-section.  The coupled-Euler consumer, by design,
requires a complete inlet-bound profile or a full-span solver-owned placement.
It therefore correctly rejects the scalar terminal when the existing control
section begins downstream, and a zero-offset section would be invalid because
it would relabel the uncovered supersonic patch as subsonic data.

The existing variable-entropy and quasi-one-dimensional references remain
useful diagnostic lanes but are not eligible to close this seam.  They may not
be wrapped, renamed, or used as an inlet-profile fallback.  The next P2.2e
implementation must introduce a separately named solver-owned moving
mixed-regime interface/subsonic-field request and result that consumes
conservative boundary data and retains the interface geometry explicitly.  Its
minimum independent evidence is:

- exact terminal Rankine--Hugoniot jump and interface lineage;
- no extrapolation beyond the retained supersonic patch, with explicit
  unavailable/masked coverage where the interface is not solved;
- centerline and ambient/free-boundary residuals in the same field solve;
- entropy transport/production and conservative mass, momentum, and energy
  residuals rederived by an independent audit; and
- a strictly increasing mesh/iteration refinement ladder with a stable
  interface and field, still blocked from chain promotion until external
  physical comparison is accepted.

Until that operator exists and passes those gates, the correct status remains
``subsonic_field_required`` and ``release_ready=false``.  No scalar endpoint
hold, profile extension, pressure/geometry profile substitution, or mapped
variable-entropy result may be counted as canonical closure.

### Integration ancestry checkpoint — 2026-09-09

The dedicated candidate branch ``work/washed-integral-visual`` is based on the
reconciled local mainline and already contains the checked-in integration
slices from ``main``, ``integration/full-suite``,
``feature/post-a1-implementation``, and ``work/validation-and-completion``.
The fetched remote PR refs ``github/pr/5-head``, ``github/pr/6-head``, and
``github/pr/7-head`` are also ancestors of the candidate.  No additional
merge or conflict resolution is required for those refs at this boundary;
the candidate is clean and pushed.

This is an ancestry/provenance result, not a release decision.  The branch
still must remain separate from ``main`` while the canonical mixed-regime
field, physical shock-cell observations, provider-bound VIS/SIG/RAY/FPA
comparisons, owner validation archives, and exact release freeze remain open.
Future work should continue as reviewable vertical slices on this branch and
must preserve the current claim ceiling.

### P2.2e conservative moving-interface boundary seam — 2026-09-09

The next solver-owned contract is now present in
``models/moc/moving_mixed_regime_interface.py``.  It accepts an explicitly
audited scalar terminal geometry, an explicit downstream-moving interface
polyline, and typed conservative boundary states on a declared cross-section.
It rederives the scalar geometry audit, checks the terminal downstream
Rankine--Hugoniot conservative state, requires the declared ordinate grid, and
retains missing sample indices instead of interpolating or extending the
open supersonic patch.  Its result and independent audit force
``subsonic_field_required=true``, ``moving_interface_solve_attempted=false``,
``physical_closure_verified=false``, and ``production_claim_allowed=false``.

Focused seam tests pass (3 tests), as do the three existing terminal
mixed-wave tests (3 tests).  A full reflected-domain file run reached 145
passing tests before being stopped in a pre-existing, very expensive
``as_report``/physical-cell sampling case; that interrupted run is not release
evidence.  The next implementation slice is to feed this contract from the
verified terminal handoff and implement the actual moving-interface/subsonic
field iteration.  No existing variable-entropy, quasi-1D, planar-potential,
or endpoint-profile result may be substituted for that solver.

The verified terminal handoff now has an explicit bridge into this request:
it retains the exact scalar geometry and one conservative downstream sample,
then returns ``interface_geometry_required`` because no moving trace has been
solved.  This bridge is intentionally a typed stop, not a fallback inlet
profile and not a field-completion claim.

The owner validation archives were rechecked in the current temporary
attachment/workspace paths and are still absent; no archive or synthetic
provider observation was added.  The external-validation and release-freeze
blockers therefore remain unchanged.

### P2.2e conservative subsonic-boundary admission checkpoint — 2026-09-09

The moving-interface seam now independently checks the supplied conservative
cross-section states before admitting complete coverage.  Each retained state
must reconstruct a strictly subsonic Mach number, and its total pressure may
not exceed the audited terminal downstream total pressure within the declared
state tolerance.  The result retains the maximum boundary Mach and maximum
total-pressure gain fraction; a supplied supersonic or total-pressure-gaining
profile returns a typed ``subsonic_boundary_required``/boundary failure rather
than being passed to a downstream field solver.

The focused moving-interface suite passes 4 tests, including the independent
audit of a tampered supersonic sample.  This closes only the conservative
boundary-admission gate.  It does not solve the moving interface, fill missing
ordinates, close the subsonic field, or change the canonical physical and
production claim ceilings.

### Coupled-Euler consumer prerequisite checkpoint — 2026-09-09

The existing coupled-Euler interior-profile consumer was inspected against the
new seam.  It requires an independently audited vertical profile with aligned
upstream and downstream samples, a complete inlet span, a separate
mixed-regime control request, and an explicit interior cross-section.  The
current terminal bridge supplies only the exact scalar downstream
Rankine--Hugoniot state and a singleton interface seed, so it cannot be
converted into that profile without inventing the missing upstream field or
interpolating the open patch.

The next physical implementation must therefore either solve the moving
interface and both-side conservative field directly, or produce a complete
solver-owned two-sided profile from that solve.  Routing the current seam into
``SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE`` would violate the fidelity
boundary and is explicitly disallowed.  This checkpoint leaves the
canonical-field and release gates open.

### Release-path sampling performance checkpoint — 2026-09-09

The repeated physical-cell report path was profiled after the reflected-domain
regression exposed an expensive nested ``as_report``/state-sampling loop.
``MocPhysicalPostShockFieldResult`` now caches the default-tolerance cell
resolution and uses an exact-coordinate source index before falling back to
the original tolerance scan.  The source index preserves the historical
first-matching-source precedence, including duplicate boundary/node
coordinates; custom tolerances still use the uncached resolver.

The physical-cell module passes 48 tests, and the targeted reflected-domain
feedback regression passes in approximately 70 seconds.  The complete
repository regression then passed with ``1214 passed, 18 warnings`` in
approximately 12m40s; after the conservative-boundary slice the committed
candidate passes ``1215 passed, 18 warnings`` in approximately 12m48s.  Ruff,
the full repository Pyright check, and the
documentation check are clean.  This is a bounded performance improvement
only: it changes neither the solver fidelity boundary nor the promotion
gates, and the release audit remains required before release claims.

### Package/build gate checkpoint — 2026-09-09

The committed candidate also passes the offline package/build gate via
``python3 scripts/check_build.py --offline`` (exit code 0).  The check builds
the wheel and runs the installed smoke path; the emitted expansion-fan and
legacy-name messages are the repository's existing warning/deprecation output,
not build failures.  This closes the local packaging checkpoint only.  It does
not supply the missing owner validation archives, provider-bound
VIS/SIG/RAY/FPA comparisons, canonical coupled mixed-regime field, or exact
release freeze, so no release tag or production-readiness claim is authorized.

### Candidate release-manifest refresh — 2026-09-09

The release manifest was regenerated from candidate ``c48df13``.  The
worktree is clean; all active lanes have local evidence; the low-fidelity
promotion guard, mission-time composition, and deterministic FPA downstream
guard pass.  The manifest correctly remains ``release_ready=false`` because
provider comparison preflight is not externally accepted, the canonical
mixed-regime field and physical shock-cell fit are open, the alignment archive
is not verified, and the committed release-freeze record still names an older
candidate.  This is current release-provenance evidence, not a release
freeze or tag authorization.

### P2.2e exact moving-interface coupled-field consumer checkpoint — 2026-09-09

The coupled Euler research lane now has a dedicated
``solver-owned-moving-mixed-regime-subsonic-field`` inlet mode.  It consumes
only a ``MocMovingMixedRegimeInterfaceResult`` that passes its independent
seam audit, retains the exact declared section frame, and maps conservative
samples to coupled inlet faces by declared index.  The request rejects
profile, entropy, scalar-shock, continuation, and spatial regridding
substitutes in this mode; missing coverage returns the typed
``inlet-moving-mixed-regime-field-failure`` stop before field iteration.

The independent coupled-field audit now remeasures the moving-interface seam
and reconciles the retained inlet conservative states.  Scalar transonic
frontier compatibility remains a diagnostic in this mode rather than a hidden
replacement for the explicit conservative inlet.  The result still carries
``chain_promotion_blocked=true`` and ``production_claim_allowed=false``;
this is an exact inlet-consumption tranche, not a canonical moving-interface
solution, a completed subsonic closure, or an external-validation result.

The focused complete/incomplete consumer tests pass (2 tests), the existing
moving-interface suite passes (4 tests), the reflected-domain regression
passes (154 tests), and Ruff plus Python compilation are clean.  The next
physical tranche remains the solver-owned moving-interface/two-sided field
solve, followed by mesh/refinement evidence and provider-bound VIS/SIG/RAY/FPA
validation.  Owner archives, external comparisons, canonical field closure,
and the exact release freeze remain open.

### P2.2e mixed-wave downstream moving-seam routing checkpoint — 2026-09-09

The mixed-wave downstream operator now accepts an optional
``MocMovingMixedRegimeInterfaceResult`` through a distinct solver-owned inlet
path.  It independently remeasures the conservative seam, requires complete
coverage with a transverse sample count that matches the coupled field, and
requires the retained section to begin strictly downstream of the
solver-owned control section.  The legacy transonic-placement/profile path
remains separate; its interface-coverage evidence is not reused for the
moving seam.

The downstream result now retains separate moving-interface verification and
consumption flags, and the field handoff is preserved in reports.  Complete
and incomplete moving-seam routing tests pass, including the typed pre-field
stop for missing coverage.  This is a routing and exact-consumption slice:
the coupled solver still does not iterate the moving interface geometry or
close the two-sided mixed-regime field, so local canonical closure, refinement,
shock-cell promotion, provider-bound VIS/SIG/RAY/FPA validation, owner
archives, and release freeze remain blocked.

### P2.2e optional two-sided Euler shock-boundary audit checkpoint — 2026-09-09

The moving-interface request now accepts an optional retained
``MocEulerShockBoundaryCurveResult``.  When present, the seam requires the
curve to pass its local Rankine--Hugoniot gate, retain the audited terminal
point as its exact endpoint, use the same gamma, and survive an independent
geometry-conditioned rederivation of its downstream states and mass,
momentum, energy, and tangent residuals.  The result and audit retain the
two-sided boundary object, its maximum jump residual, and separate
``two_sided_shock_boundary_verified``/``two_sided_shock_boundary_rederived``
flags.  Missing two-sided evidence remains valid for the existing boundary
seam, preserving backward compatibility; supplied but tampered evidence
returns the typed ``moving-mixed-regime-two-sided-shock-boundary-failure``
stop.

The focused moving-interface suite passes 6 tests, including positive
independent remeasurement and a tampered downstream-state case.  The full
reflected-domain regression passes 158 tests.  This checkpoint proves only
local two-sided shock-jump lineage at the terminal boundary.  It does not
iterate the moving interface geometry, solve the coupled subsonic field,
close centerline/ambient/free-boundary feedback, establish refinement, fit a
physical shock cell, or authorize Signature/FPA/release claims.  The next
physics slice remains the solver-owned moving-interface/two-sided field
iteration that consumes this evidence and rederives the full field residual
set.

### P2.2e two-sided moving-field consumer admission checkpoint — 2026-09-09

The coupled-Euler research lane now exposes a distinct
``solver-owned-moving-mixed-regime-two-sided-field`` inlet mode.  It accepts
the conservative moving-interface seam only when the optional two-sided Euler
shock-boundary handoff is present and independently audited.  The downstream
operator routes a verified handoff into this mode; a one-sided seam is rejected
at request construction, and a tampered or unconsumed handoff has a typed
``coupled-euler-audit-moving-mixed-regime-two-sided-boundary-failure`` stop.
The result and independent audit retain separate two-sided-consumption and
verification flags, while preserving the existing one-sided moving-field
mode for backward-compatible research cases.

The focused two-sided consumer regression passes 3 tests, the complete
reflected-domain model regression passes 160 tests, Ruff is clean, and the
full Pyright check reports zero errors, warnings, or informations.  This is an
admission/lineage checkpoint only: the coupled field currently consumes the
verified two-sided handoff as a solver-owned prerequisite but does not yet
iterate the shock curve, use it in a converged two-sided update, close the
centerline/ambient/free-boundary feedback, or authorize canonical, Signature,
FPA, provider-validation, or release claims.  The next physics slice remains
the actual moving-interface/two-sided field iteration with mesh/refinement
evidence and independent residual closure.

### P2.2e open two-sided companion-field handoff checkpoint — 2026-09-09

The moving-interface seam now optionally accepts an exact caller-supplied
``MocChainBoundarySample`` companion boundary alongside the independently
audited two-sided Euler shock curve.  When the pressure/state lineage and
mixed-characteristic orientation are valid, the seam independently assembles
and retains a typed one-layer open Euler characteristic strip.  The request,
result, and audit preserve the exact companion samples, the open-field
result, and a separate ``two_sided_companion_field_verified`` /
``two_sided_companion_field_rederived`` evidence pair.  A malformed or
pressure-tampered companion boundary stops with the typed
``moving-mixed-regime-two-sided-companion-field-failure`` outcome; the failed
diagnostic is not promoted as a usable field handoff.

The focused moving-interface suite passes 9 tests, including positive open
strip assembly, independent remeasurement, tamper rejection, and the missing
shock-boundary guard.  The complete reflected-domain regression passes 160
tests; Ruff and Python compilation are clean.  This is stronger two-sided
open-field evidence, not a closed subsonic/free-boundary solution: the strip
still has no moving shock/interface iteration, centerline/ambient/entropy
feedback, downstream closure, mesh/refinement evidence, physical shock-cell
fit, Signature/FPA promotion, provider comparison, owner archive, or release
freeze.  The next physics tranche remains solver-owned two-sided field
iteration followed by residual/refinement closure and the product-lane
validation gates.
