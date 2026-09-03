# Visualization evaluation plan v1

## Purpose

The visualization surface is an evaluation and debugging tool for the public
exhaust-plume contracts. It is not a new physics product and it must not turn
an exploratory display into a validated geometry, radiation, ray, or detector
claim.

The current strict `exhaust_plume.api.ProductResult` union contains four
independent product families:

1. `plume.visual.sectioned-tube@1` — oriented sectioned-tube geometry;
2. `plume.signature.spectral-radiant-intensity@1` — unresolved spectral
   radiant intensity;
3. `plume.optical.spectral-ray-transfer@1` — resolved ray source radiance and
   background transmittance;
4. `plume.engineering.flux-section@1` — engineering flux handoff data.

Focal-plane visualization is a downstream lane. It requires an explicit
camera/optics/detector operator result and must not be synthesized from a
visual tube or a signature table.

## Shared evaluation contract

Every view must retain and display:

- capability ID and schema version;
- provider, model lineage, model fidelity, validation level, and derivation;
- frame ID, time, snapshot/result identity, and content digest;
- applicability, result status, warnings, and validity masks;
- physical units and coordinate conventions;
- the exact view settings used to create the display.

Invalid or unavailable samples remain masked or gapped. They must not be
silently converted to zero. Display scaling, wavelength-unit conversion,
logarithmic axes, colormaps, downsampling, camera settings, and selected
indices are view settings, not changes to the source result.

## Product view matrix

### Sectioned-tube visual geometry

- 3-D overview of the tessellated tube with frame and support labels;
- XY/XZ/YZ orthographic projections;
- axial centerline and semi-axis plots;
- station selector with ellipse, tangent, normals, radii, and feature values;
- one plot per declared feature channel, including component and association;
- mesh quality diagnostics: finite vertices, face indices, ring resolution,
  bounds, orientation, and degenerate-face checks;
- side-by-side overlays for separate fidelity lanes, with provenance kept
  visible for each result.

Shock diamonds, Mach disks, plume regions, and physical plume endpoints are
shown only when explicitly represented by a declared channel or a separate
spatial/region contract. They are never inferred from a display mesh.

### Spectral radiant intensity

- wavelength spectrum for each selected direction;
- wavelength-by-direction heatmap with masked invalid samples;
- direction-unit-sphere view colored by a selected wavelength;
- uncertainty band or uncertainty heatmap when uncertainty is supplied;
- direction table showing the exact 3-D unit vector and status;
- sampled angular-time heatmap for a compatible collection of exact
  request/result pairs, with an explicit display binning policy and no angular
  or temporal interpolation;
- linked exact-direction intensity trace and declared source-pose trajectory
  for compatible time samples, with invalid samples masked;
- wavelength selector and direction selector with linked updates;
- same-axis comparison between independent providers or tables only when
  wavelength and direction domains match.

The contract does not necessarily provide a scalar angular coordinate. The
viewer must use direction index or the exact 3-D direction unless a declared
axis makes a direction cosine meaningful.

### Spectral ray transfer

- 3-D ray-origin/direction bundle view with an explicit display length;
- per-ray source-radiance spectrum;
- separate background-transmittance spectrum;
- ray-by-wavelength heatmaps for each returned field;
- ray table with ID, origin, direction, status, and valid-sample count;
- selected-ray inspector with all source, transmittance, and mask values;
- intersection/path overlays only when the selected contract returns those
  intervals.

The viewer must not infer hit/miss or optical depth from zero radiance or unit
transmittance when those fields are absent from the result.

### Engineering flux section

- section pose and normal glyph;
- momentum-flux vector and scalar magnitude;
- cross-section second-moment ellipse;
- mass-flow, energy-flow, pressure, ambient-pressure, and residual cards;
- species mass-flow bars or stacked bars;
- uncertainty and applicability display;
- ordered section/time plots only when an explicit collection wrapper supplies
  a common axis and shared lineage.

### Downstream focal-plane lane

The downstream boundary is now explicit through
`exhaust_plume.validation.fpa_visualization` and the FPA workflow modules. It
consumes an explicit `FpaPixelImage` plus a source-bound ray identity; it does
not add FPA to the public provider capability union. The evaluation surface
includes:

- pixel-integrated radiance or expected-electron image;
- detector spectral response and bandpass view;
- exposure/time-integration view;
- expected ADC image and deterministic digitization settings;
- invalid-pixel mask, noise policy, and camera/optics identity.

The `FpaVisualizationSpec` and `FpaViewProjection` retain operator lineage,
source digest, masks, selected pixel/wavelength, and the expected-output claim
ceiling. `render_fpa_gallery` writes static PNG/CSV/JSON artifacts and
`write_interactive_fpa_gallery` writes a standalone no-network explorer with
linked layer/pixel controls and view-spec export. Declared camera metadata is
limited to image-plane coordinates; the view does not infer ray directions,
hit masks, optical depth, noise realizations, detections, or measured counts.

The recovered Version 8 corpus is content-verified but has no camera,
detector, pixel-image, or FPA observation member. The separate product-
alignment archive is also still missing. The reproducible readiness result is
[`fpa_visualization_readiness_v1.json`](validation/fpa_visualization_readiness_v1.json);
its future detector-pixel-count measurement operator remains blocked pending
the required observation dataset and metadata.

This lane is downstream composition. It does not create an FPA provider or a
measured-image claim by itself.

### Five computational model lanes

The model-facing visualization seam is now standardized by
`StandardizedModelVisualization` in
`exhaust_plume.products.model_visualization`. It adapts the fast basic
shock-cell, calibrated reduced-order shock-train, straight top-hat integral,
curved/washed integral, and planar-MOC/reflected-domain lanes to the common
sectioned-tube display. It also retains unit-bearing channels, optional region
polygons, named boundary paths, and lane-specific fidelity/promotion metadata.

The planar-MOC result is shown as retained 2-D field cells and boundaries plus
an explicitly illustrative projected envelope. This does not add a public MOC
provider or authorize a production claim. See
[`model_visualization_standard_v1.md`](model_visualization_standard_v1.md) for
the lane matrix and required views.

## Interaction model

The first implementation should support linked, deterministic selections:

- visual station ↔ cross-section, frame triad, channels, and local geometry;
- signature direction ↔ spectrum and uncertainty;
- signature wavelength ↔ direction-sphere map;
- ray ID ↔ 3-D ray, spectrum, transmittance, and status;
- flux section ↔ vector, ellipse, species, and residual panels;
- snapshot/time selection only for a compatible collection of results;
- fidelity/provider comparison as separate results, never a merged product.

Each view can export a reproducible `VisualizationSpec` containing the source
result identity, selected slices, axis scales, display units, masks,
colormaps, camera, mesh resolution, and renderer settings. Exported PNG/SVG,
CSV, JSON, or mesh files must carry the source identity and view spec.

## Implementation layers

1. **Contract adapters** — convert public results to renderer-neutral grids,
   lines, glyphs, paths, and meshes. This is the current
   `exhaust_plume.api.visualization` layer.
2. **View-state primitives** — typed view specifications, selections, axis
   policies, validity policies, metadata panels, and deterministic defaults.
3. **Static renderers** — testable Matplotlib/JSON/mesh outputs for fixtures
   and reports.
4. **Interactive gallery** — linked selectors and inspectors using only the
   view-state and adapter layers.
5. **Comparison and validation** — aligned overlays, residual views, and
   contract/operator checks with explicit lineage.

No renderer should import solver-private zones, flow states, meshes, or
provider configuration objects.

## Implementation status after the static-gallery increment

The current implementation has completed the renderer-neutral and static
evaluation layers for the four strict `ProductResult` families:

- `exhaust_plume.api.visualization` now exposes typed, selection-resolved
  projections for visual stations/channels, signature directions/wavelengths,
  ray IDs/wavelengths, and flux species.
- `exhaust_plume.products.workflow_gallery` provides optional Matplotlib
  galleries for overview/projection/channel/mesh-QA, spectra/heatmap/direction
  sphere, ray bundle/source/transmittance/heatmaps, and flux vectors/scalars/
  second-moment/species views.
- Each gallery writes `visualization_spec.json` and `gallery_manifest.json`
  with source identity, fidelity, validation, applicability, provenance,
  warnings, masks/policies, selections, and artifact paths.
- `exhaust_plume.products.workflow_interactive` writes an optional standalone,
  no-network HTML gallery with linked selectors for station/channel,
  direction/wavelength, ray/wavelength, or species. The page can export the
  current selection as a source-bound view-spec JSON file.
- `exhaust_plume.products.workflow_comparison` provides same-axis, same-frame
  diagnostics for all four standard product families, retaining both source
  lineages and validity counts. Mismatched domains are reported as blocked;
  the output is explicitly not validation evidence. Its optional static
  renderer emits an aligned overlay PNG beside the JSON report.
- The strict ray contract still has no hit mask, optical depth, or intersection
  interval. The gallery records that limitation and does not infer it from
  zero radiance or unit transmittance. The strict visual contract likewise does
  not acquire shock-diamond or plume-region claims from tessellation.
- `exhaust_plume.products.signature_timeline` now joins compatible exact
  signature request/result pairs into renderer-neutral sampled angular maps,
  direction traces, and source-pose trajectories. It retains the request axes,
  forbids changing grids and temporal interpolation, and represents missing or
  invalid bins as masked values rather than zeros.

The FPA boundary, renderer-neutral projections, static gallery, interactive
explorer, and validation-readiness checker are implemented. Remaining FPA work
is measurement-data intake and comparison once a camera/optics/detector
observation contract is supplied, plus richer declared uncertainty rendering
for all products. Validation datasets must still enter through their declared
measurement-space/operator contracts; a gallery cannot promote a diagnostic
overlay into validation evidence.

## Milestones and exit gates

### M0 — Shared foundation

- persist `VisualizationSpec` and common metadata/validity types;
- define stable selection and display-unit policies;
- round-trip view specs deterministically;
- reject incompatible result/frame/capability selections.

### M1 — Visual geometry gallery

- implement overview, projections, station inspector, channel panels, and
  mesh QA;
- verify ring geometry, frame orientation, bounds, finite values, and channel
  alignment;
- render the prescribed, basic shock-cell, and reduced-order fixtures with
  explicit fidelity labels.

### M2 — Signature gallery

- implement spectra, heatmaps, direction-sphere view, uncertainty, masks, and
  exact-axis comparison;
- verify wavelength ordering, direction identity, validity propagation, and
  no accidental angular-coordinate assumptions.

### M3 — Ray-transfer gallery

- implement ray bundle, per-ray spectra, separate transmittance, heatmaps, and
  status tables;
- verify source/transmittance separation, invalid-ray behavior, frame identity,
  and no inferred path claims.

### M4 — Flux/support gallery

- implement section glyphs, vectors, second-moment ellipses, species bars, and
  residual cards;
- add collection wrappers only after a public multi-section/time contract is
  available;
- add support/projected-area views when their public result contracts exist.

### M5 — Comparison and downstream composition

- add lineage-aware overlays and residual plots;
- add ray-to-signature consistency views only through the declared operator;
- add the explicit downstream FPA result contract, deterministic views, and
  no-inference guardrails;
- add provider-bound FPA comparison only after camera/detector measurement
  data and the external measurement operator are available.

### M6 — Release evidence

- golden fixture renders and deterministic view-spec snapshots;
- invalid/masked-data interaction tests;
- frame/unit/axis labeling checks;
- product-specific and cross-product validation reports;
- documented performance ceilings for the fast visual lane;
- explicit statement of unsupported views and fidelity limits.

## Non-negotiable guardrails

- A visual tube is not a spectral source, ray field, or detector image.
- A signature table is not geometry or atmosphere-corrected radiance.
- A ray-transfer result is not an FPA result without camera and detector
  operators.
- Higher-fidelity comparisons never mutate or retrain the basic lane.
- A display can expose a claim; it cannot create a claim absent from the
  result contract and validation evidence.
