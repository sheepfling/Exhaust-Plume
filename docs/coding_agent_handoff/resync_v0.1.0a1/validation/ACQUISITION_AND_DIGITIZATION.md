# Acquisition and Digitization Procedure

## Provenance rules

Store four layers separately:

1. `raw/`: original downloaded files, unchanged;
2. `intermediate/`: page renders, cropped figures, or decoded vendor files;
3. `derived/`: digitized or normalized tables;
4. `metadata/`: source URL, retrieval time, checksum, coordinate convention, units, and extraction notes.

Never overwrite a raw source. Record SHA-256 checksums before extraction.

## Plot digitization

For every curve, save:

- source document and page/figure number;
- image crop checksum;
- axis calibration points and whether axes are linear or logarithmic;
- curve/marker identity;
- raw pixel-to-data picks;
- final SI-unit table;
- estimated digitization uncertainty.

A useful first uncertainty model is half the plotted line thickness plus the axis-calibration residual. Keep that uncertainty separate from instrument uncertainty.

## Coordinate conventions

### Rotor wash

Use a right-handed rotor frame:

- origin at hub center projected onto the rotor axis;
- `+z` upward along rotor axis;
- `r` radial from rotor axis;
- report ground height as `h/R` and rotor height as `z_hub/R`;
- positive radial velocity points outward.

Preserve the original experiment azimuth before creating an azimuthally averaged view.

### Rocket plume

Use a nozzle frame:

- origin at nozzle exit center;
- `+x` downstream along nozzle axis;
- `r` transverse radius for axisymmetric cases;
- preserve observer line-of-sight and aspect-angle convention;
- explicitly distinguish source radiance/intensity from apparent sensor radiance/intensity after atmospheric transmission.

## Data-quality flags

Recommended flags are `verified_table`, `digitized_curve`, `author_reconstructed`, `raw_measurement`, `simulation_only`, `unknown_uncertainty`, and `independent_extrema`.

## Published vector-figure extraction

When a PDF figure contains native vector paths, extract the paths directly before considering raster digitization. Record:

- the source PDF SHA-256;
- zero- and one-indexed page references;
- the figure number;
- the PDF-axis rectangle in points;
- the axis mapping, including logarithmic transforms;
- path-point semantics;
- whether points are true data markers, histogram bins, or adaptive plotting vertices.

A curve that integrates to a published normalization can use that normalization as a transcription check. It must not be promoted to a raw instrument export.

## Modeled-versus-measured separation

Experimental papers often publish modeled chamber/nozzle states beside measured test products. Preserve a `source_kind` field and score the layers separately. In this corpus, EMAP Table 1 rows are modeled RPA states, while Table 2 throat diameters are measured geometry. A model-to-model agreement cannot substitute for agreement with an experimental observable.
