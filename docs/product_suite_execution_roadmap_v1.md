# Exhaust-Plume product suite execution roadmap v1

Status: active long-running goal; checkpointed 2026-11-15. This document is
the concise execution roadmap; [`product_suite_completion_plan_v1.md`](product_suite_completion_plan_v1.md)
holds detailed contracts, research checkpoints, and residual evidence.

## Objective

Finish and release three independently evaluated products:

1. **Visualization** — standard API-based, renderer-neutral inspection of
   plume geometry, regions, fields, slices, paths, time series, and diagnostics.
2. **Signature** — source-bound spectral radiant intensity and resolved ray
   radiance, queryable by wavelength, direction, position, and time.
3. **Focal-plane array (FPA)** — downstream camera, exposure, detector, pixel,
   and digitization composition from an eligible Signature/ray source.

Completion means each product passes its own local contract and held-out
measurement-space validation. Visualization evaluates geometry and fields;
Signature evaluates emitted and transported spectral/angular quantities; FPA
evaluates camera and detector response in pixel space. Each result retains the
source, operators, validity, uncertainty, and fidelity that produced it.

## Guardrails

- Keep the five plume visualization lanes independent: basic shock-cell,
  reduced-order shock train, straight integral, washed/curved integral, and
  planar/reflected MOC. Keep the global mixed-regime solver as its own
  physical-closure lane.
- Preserve fidelity ceilings. The fast basic solver can serve quick
  Visualization and bounded engineering screening; it cannot silently become
  a high-fidelity Signature source or an FPA source. More complex physics gets
  a separate solver/provider and promotion gate.
- Keep flow, chemistry, radiation, atmosphere, ray transfer, and detector
  response as explicit contracts with units, validity, uncertainty, and source
  lineage.
- Label fixtures, planner mocks, gray/table estimates, and research solvers by
  their actual evidence level. Do not turn local tests into external physical
  validation claims.

## Product and model boundaries

The three products consume model outputs through explicit contracts. The five
plume-model lanes remain independently selectable and retain their own
fidelity and promotion ceilings. Improving one lane does not silently change
another lane's behavior or claim level.

| Model lane | Intended use in this plan | Product relationship | Promotion gate |
| --- | --- | --- | --- |
| Basic shock-cell solver | Fast, simple plume geometry and region exploration | Visualization; bounded engineering screening | Reproducible local contract and geometry checks; Signature/FPA use requires separate source-physics qualification. |
| Reduced-order shock train | Fast chain-level estimates and planner exploration | Visualization and planner/mock workflows, with mock status visible | Held-out cell-length/topology evidence before physical chain claims. |
| Straight integral plume | Straight-axis field and diagnostic flow/radiation studies | Visualization; Signature through a declared radiation provider | Qualified flow and spectral comparisons in the declared frame and operating domain. |
| Washed/curved integral plume | More expensive curved/washed-flow studies | Visualization and research Signature experiments | Curved-flow and radiation validation; uncertainty and applicability bounds. |
| Planar/reflected MOC | Higher-fidelity planar/reflected flow research | Visualization and explicitly supported research Signature paths | Independent physical closure, mesh/refinement evidence, and matching observations; planar evidence applies within its declared geometry. |
| Global mixed-regime closure | Shared physical-source research gate, separate from the five gallery lanes | Candidate source for shock-cell fitting and downstream products after acceptance | Reciprocal closure, independent conservation/entropy replay, multi-case and refinement gates. |

## Product-specific completion gates

| Product | Local contract is complete when | Product validation is complete when |
| --- | --- | --- |
| Visualization | Every standard result API has a renderer-neutral adapter and reusable overview, orthogonal/cross-plume slices, stations/channels, regions/cells, paths, masks, time, comparison, provenance, and export views. Units, frames, validity, and fidelity remain visible. | Held-out geometry/feature comparisons use qualified observations with explicit coordinate transforms, measurement operators, and uncertainty. |
| Signature | A replayable mission state supports exact time/position/altitude and operating-state updates; point spectrum and angular/time products preserve wavelength grid, units, masks, uncertainty, and source lineage. Radiation and straight/curved transfer remain explicit operators. | Held-out spectra, angular distributions, time histories, and ray/path quantities pass for each admitted source lane. Spectral radiant intensity and resolved radiance retain their respective contracts. |
| FPA | An eligible Signature/ray source composes with camera pose/projection, exposure, spectral integration, detector response, electron/noise model, pixel integration, optional ADC, masks, and provenance. | Held-out camera/detector observations validate pixel-space images and detector outputs, including calibration and uncertainty. |

## Ordered phases

| Phase | Deliverables | Exit criteria | Dependency/status |
| --- | --- | --- | --- |
| 0. Candidate and contract baseline | Review the active branch's uncommitted packet; map each changed contract, test, and solver lane; group separable changes; check the intended base and outstanding PR state; resolve conflicts at contract boundaries. | Reviewed candidate identity, a change-to-contract map, no unresolved conflicts, focused evidence for touched contracts, and accurate lane claims. | Baseline review confirms no open PRs, both local `main` refs are ancestors of `49f39a73`, and no unresolved index conflicts or conflict markers. The 26-path dirty packet separates into Visualization/FPA interactions, global-closure research, validation evidence, and plan/evaluation docs. Focused product/corpus tests pass (`35`), closure handoff regressions pass (`2`), Ruff/JSON/whitespace checks pass, and generated JavaScript parses for all four standard result families. The full suite passes (`1366 passed, 18 warnings`); implementation-level packet/commit boundary review remains open. |
| 1. Complete local product surfaces | **Visualization:** common views for each standard result API and all five plume lanes: 3-D/orthographic overview, XY/XZ/YZ and cross-plume slices, stations/channels, region and shock-cell overlays, named paths, masks, provenance, comparison, export, and time selection. **Signature:** immutable mission state/cursor for time, position/altitude, attitude, ambient state, throttle/burn state, chemistry, and solver selection; exact point lookup; angular heat maps and trajectories over time. **FPA:** camera pose/projection, exposure and spectral integration, detector response, expected electrons/noise variance, pixels, optional ADC, invalid/saturation masks, and provenance views. | Deterministic typed contracts and galleries; source-bound export/replay; explicit units, frames, validity, uncertainty, time/position, and fidelity; no inferred physical quantities from display geometry. | Can proceed alongside Phase 2. The five-lane galleries, Signature time/query seams, and deterministic FPA composition exist; remaining local completeness and provider comparisons are open. |
| 2. Close the canonical physical source | Establish shared solver-owned support and a geometry-bound interface; derive and independently audit the physical interface law; exchange conservative flux and entropy response reciprocally; solve the global and downstream fields together. | Independent replay of geometry/lineage, positivity, mass, both momentum components, energy, entropy, boundary closure, and strict component-wise residual admission over disjoint cases, multiple steps, and increasing resolutions. | Critical path and open research gate. Bounded pressure-profile replay and exact cell-overlap remapping audit pass. State-trace consumption fails conservative residuals. A geometry-locked Euler-flux handoff reaches about `5e-4` conservative residual but fails entropy/pseudo-time gates. Reciprocal closure is not established. |
| 3. Fit the physical shock-cell chain | Fit first and continued cells from an accepted physical field/frontier; retain cell identity, length, uncertainty, termination, and solver lineage. Keep planner mocks and diagnostic fits separate. | Independent solver-length/topology audit and held-out comparisons pass across cases/refinements; continuation stops with typed physical semantics. | Depends on accepted Phase 2 closure and qualified observations. Current fits are diagnostic/research-only. |
| 4. Intake validation evidence | Preserve the recovered Version 8 and alignment archives by digest; review provenance and redistribution rights; map cases, frames, units, operators, and uncertainty; freeze disjoint calibration/validation splits. Acquire separate camera/detector observations for FPA. | Reproducible intake manifest and independent audit; fitting begins only after data mapping and splits are frozen. | Version 8 (`79c2a34d…e9aa`) and alignment (`569aa7f0…4ceb`) archives are verified; all 152 internal checksums pass and the isolated corpus suite passed (`57 passed`). The alignment registry contains 16 operator IDs, a subset of the committed 21; five sensor operators have no exact archive identity yet. Rights review, provider-bound outputs, disjoint splits, and FPA observations remain open. |
| 5. Validate each product in its measurement space | Compare geometry/features for Visualization; spectra, angles, time histories, and ray/path quantities for Signature/ray; pixel-integrated images and detector outputs for FPA. | Held-out comparisons independently replay with source identity, operator, frame, units, masks, uncertainty, and residuals; record accept/research-only decisions per lane. | Requires qualified source models and provider/measurement evidence. Local deterministic checks alone do not pass this phase. |
| 6. Freeze and release | Re-run local tests and static checks, public contracts/docs, package build, installed-package smoke, lane audit, and required external comparisons on one clean exact-HEAD candidate. | Exact-HEAD release manifest reports `release_ready=true`; release handoff occurs only after the separate release decision. | Current-source offline wheel build and installed smoke pass. Release remains blocked by physical closure, provider/measurement evidence, redistribution review, FPA observations, and the dirty/stale exact-HEAD freeze. |

Phases 1 and the preparation work in Phase 4 can advance while Phase 2 is
open. Visualization contract work can use each lane at its declared claim
ceiling. Signature and FPA source admission, physical shock-cell fitting, and
held-out product acceptance require their corresponding qualified source and
measurement evidence. A lane whose evidence is incomplete remains at research
status while independent product work continues.

## Current next work packet

1. **Finish candidate packet review.** Complete the file-level change map for
   the four identified groups, check their contract/fidelity boundaries, and
   define reviewable change boundaries. The PR/base and merge-conflict checks
   are clear; the packet remains uncommitted. The full suite passes, and the
   next review should choose coherent commit boundaries without combining
   product surfaces with physical promotion claims.
2. **Advance the Phase 2 physical closure gate.** Retain the bounded ambient
   profile and its independent source replay as established local evidence.
   Review the exact conservative cell-overlap remap and its independent audit:
   geometry, full coverage, and conservative remap are verified, while the
   measured source/downstream state and entropy mismatches remain open. A
   state-trace solve fails conservative residuals; a geometry-locked Euler
   normal-flux handoff brings conservative residuals near `5e-4` but still
   fails entropy and pseudo-time gates. Derive and independently audit a
   geometry-bound, entropy-consistent common interface law, then make
   downstream conservative and entropy response affect the upstream equations
   in a jointly solved update. Require strict component-wise descent of the
   full residual vector across multiple steps, disjoint cases, and increasing
   resolutions. If the interface law or common support cannot be established,
   fail closed and retain research status.
3. **Finish product-local contracts in parallel.** Audit standard API
   adapters against every result family and all five gallery lanes; close
   missing slices/views, Signature exact-state queries and angular/time-series
   products, and FPA validity/provenance views. Exercise planner mocks as
   visibly mock outputs. Preserve source identity, units, frames, validity,
   uncertainty, and replayable provenance in every product.
4. **Close evidence intake and comparisons.** Preserve the verified archive
   digests and internal manifests; finish provenance and redistribution
   review; resolve operator identity and semantics without guessed aliases;
   freeze disjoint calibration/validation sets; and bind provider outputs to
   each product's operator and scenario. Acquire separate camera/detector
   observations for FPA. Keep absent or unbound evidence explicitly pending.
5. **Gate shock-cell fitting and release.** After Phase 2 source acceptance,
   fit first and continued shock cells and pass held-out topology/length
   comparisons. Then freeze one exact-HEAD candidate and regenerate local,
   public-contract, package, installed-package, lane, and external-evidence
   results. The release manifest must report `release_ready=true` before a
   release handoff.

The Codex long-running goal for this suite is already active. Work through
these packets in dependency order, recording each implementation, independent
audit, and evidence result in the detailed ledger. Product-local work and
validation preparation can advance alongside Phase 2; physical shock-cell
acceptance, production Signature/FPA claims, and release remain gated on
qualified sources and observations.

## Work sequence and checkpoint rules

1. Finish Phase 0 by auditing the current dirty packet against the contract
   and model matrices above. Record which changes belong together and what
   focused evidence each group needs.
2. Pick the next implementation packet from either (a) a contract gap exposed
   by that review or (b) one falsifiable Phase 2 interface-law experiment.
   Do not combine unrelated work just to produce a larger checkpoint.
3. Advance validation intake in parallel: rights/provenance review, exact
   operator mapping, and held-out split design. Record requests for absent
   provider or FPA observations as external data dependencies.
4. Admit source models only after their own physical and measurement gates;
   then validate Signature and FPA outputs in their respective measurement
   spaces. Fit physical first/continued shock cells after accepted flow
   closure and qualified observations.
5. Run the exact-HEAD release matrix only after all required product and
   evidence gates are closed. The release candidate must have a clean tree and
   a generated manifest with `release_ready=true`.

Every checkpoint records: touched contracts and files, solver/product lane,
claim ceiling, preconditions, focused verification, independent replay or
audit, measured result, and remaining gate. A passing local regression proves
the checked behavior only; it does not close an external validation or
physical-admission gate.

## Product completion checklist

- [ ] Visualization adapters and gallery/evaluation utilities cover all
  standard API result families and each of the five plume lanes.
- [ ] Visualization offers multiple slices, station/channel views, region and
  shock-cell overlays, paths, masks, time views, comparison, and reproducible
  export with source lineage.
- [ ] Signature can advance a replayable time/position state and query the
  spectrum or angular response at that exact state; angular heat maps preserve
  masks, units, uncertainty, and source identity.
- [ ] Radiation and ray-transfer paths declare source physics, atmosphere,
  path model, and separate straight/curved evidence.
- [ ] FPA consumes only a declared source/ray contract and preserves camera,
  exposure, detector, pixel, digitization, validity, and uncertainty metadata.
- [ ] Global physical closure and first/continued shock-cell fitting pass
  independent residual, topology, refinement, and held-out evidence gates.
- [ ] Validation archives and provider observations are digested, mapped,
  rights-checked, split, and compared with product-specific operators.
- [ ] Exact-HEAD release matrix is green and explicitly reports
  `release_ready=true`.
