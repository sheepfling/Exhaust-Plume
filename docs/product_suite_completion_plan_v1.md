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

The recovered Version 8 archive is integrity-checked in the corpus manifests:
its recorded SHA-256 is
`79c2a34dd4c43bd976ceb8773fdccd78a2592d903bf03ca57c2aef82f882e9aa`, with
138 members and 137 internal checksums. That proves corpus integrity, not
provider acceptance. The separately named alignment archive remains an
outstanding input and must not be reconstructed or claimed as present.

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
8. The release manifest reports no promotion violation and
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
- [x] Add a typed provider-bound comparison-evidence envelope requiring exact
      assets, operator identity, uncertainty, applicability, and disjoint cases.
- [x] Make provider-bound evidence ingestible through a strict preflight JSON
      handoff with exact provider-identity matching.
- [ ] Close and independently validate the global planar-MOC physical field.
- [ ] Produce accepted physical shock-cell lengths and continued-chain fits.
- [ ] Bind external VIS/SIG/RAY/FPA cases to accepted measurement operators.
- [ ] Supply the separate alignment archive and disjoint reduced-order cases.
- [ ] Run the final candidate acceptance matrix and create the release tag
      only after the manifest turns green.
