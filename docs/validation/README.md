# Validation corpus intake

The merged validation handoff describes two external, content-addressed
archives. The Version 8 corpus archive has now been recovered from a
user-provided attachment and verified against its expected digest. The
separately named product-alignment archive is still missing; the recovered
corpus contains an embedded alignment overlay, but that is not silently treated
as the separately hashed archive.

The intake gate is:

```bash
python scripts/verify_validation_corpus.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --alignment /path/to/plume_mvp_validation_alignment_v1.zip \
  --output validation-intake-report.json
```

The command succeeds only when both files exist, match their recorded SHA-256
digests, are valid ZIP archives, and contain no path-traversal or duplicate
members. It never extracts or modifies the supplied archives.

After the corpus archive passes intake, run the alignment preflight against the
same file:

```bash
python scripts/validate_external_corpus_alignment.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --output external-alignment-preflight.json
```

The preflight verifies the 17 benchmark definitions, 19 source records, 60
indexed products, 78 mappings, 20-row summary, seven cross-product rules, 11
gates, and all 137 internal checksums. It reports the exact external-versus-
internal operator namespace difference, scoped semantic-crosswalk coverage,
and provider-comparison gates rather than treating a structurally valid corpus
as product validation.

The recovered corpus intake evidence is recorded in
[`corpus_intake_report_v1.json`](corpus_intake_report_v1.json). It matched the
handoff SHA-256, passed safe-ZIP inspection, verified all 137 internal checksum
entries, and its bundled test suite was executed from an isolated extraction:
57 tests passed. Do not create synthetic
replacements for the still-missing alignment archive. Keep raw observations
separate from derived tables, digitized curves, modeled states, and
product-alignment records.

The recovered archive contains 17 benchmark definitions, 19 source records, 60
indexed products, 78 alignment mappings, 11 validation gates, and 57 source-
corpus tests. These counts establish corpus integrity; they do not by
themselves establish provider-specific product validation.

After the archive preflight, record provider-specific comparability with:

```bash
python scripts/validate_provider_comparisons.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --output provider-comparison-preflight.json
```

The committed [`provider_comparison_preflight_v1.json`](provider_comparison_preflight_v1.json)
is the result for the recovered attachment. It records all ten gate-eligible
VIS/SIG/RAY comparison mappings and the actual provider channels and corpus
observation shapes, while leaving every comparison explicitly blocked. A blocked comparison is not a
failed physics result: it means that the current provider does not produce the
observable or operator required for a valid comparison. No external claim is
accepted from this report. The report also executes the spectral-shape probe
where possible: BSUV2 and EMAP UVVIS have no model-domain overlap, while EMAP
FTIR produces only a partial-overlap diagnostic because the synthetic provider
ends at 3 micrometres and the observation continues beyond 5 micrometres.
Those residuals are diagnostics, not validation claims.
For the non-spectral VIS gate, the preflight also records the explicit
branch-aware/no-extrapolation feature operator. The recovered HOTWAKE relation
has 606 points but no declared branch ID, and the current providers do not
emit the required Mach-disk feature channel; this remains a blocked diagnostic,
not an inferred comparison.

The reviewed, gate-specific operator semantics for all 35 external operator
IDs are recorded in
[`operator_semantic_crosswalk_v1.json`](operator_semantic_crosswalk_v1.json).
This artifact is a complete scoped review: it documents matches, partial
pipelines, and explicit non-equivalences without treating the external
`operator.*` namespace as an exact alias of the internal `op.*` namespace.
Every entry remains `claim_status: not_accepted` until its provider-bound
measurement comparison is accepted.

The repository also implements the generic downstream composition primitives
`op.atmosphere.path-transfer`, `op.sensor.los-fov-spectrum`, and
`op.sensor.bandpass-detector`. Their synthetic probes verify explicit source
versus path-radiance semantics, FOV selection and solid-angle weighting,
response-domain coverage, band integration, and invalid-sample propagation.
They do not supply a provider-bound flight, hot-fire, atmosphere, or detector
asset, so they do not by themselves accept an external comparison.

The reproducible local lane run is preserved in
[`product_lane_validation_v1.json`](product_lane_validation_v1.json). It shows
independent VIS and SIG contract/operator acceptance, the analytic optical
boundary, the synthetic ray-to-signature check, and the downstream FPA adapter
status. Its `release_ready` flag remains false.

The first quantitative benchmark component record is
[`cj_uej_component_validation_v1.json`](cj_uej_component_validation_v1.json).
It is intentionally separate from the product preflight: `CJ-UEJ-001` is a
cold gasdynamic precursor, and the current visual product emits display
channels rather than a local flow field. The record quantifies the bounded
shock-cell component where the declared probe-line operator can be applied,
reports uncovered and ambiguous points, and keeps the claim proposed rather
than treating partial residuals as VIS validation.

The bounded gray optical lane has its own reproducible local evidence in
[`optical_transfer_validation_v1.json`](optical_transfer_validation_v1.json).
Its straight-cylinder analytic gate passes; the curved-support refinement is
recorded as nonmonotonic geometry-only evidence and is not promoted into the
provider claim.

The ray-to-signature operator is recorded separately in
[`ray_signature_consistency_v1.json`](ray_signature_consistency_v1.json). It
passes synthetic projected-area, miss, wavelength-grid, and snapshot-lineage
checks, but does not convert the gray ray provider into an externally validated
signature provider. The focal-plane-array boundary is recorded in
[`fpa_boundary_validation_v1.json`](fpa_boundary_validation_v1.json); it has no
provider. Its deterministic pixel/detector adapter is boundary evidence only
and makes no externally validated image, detector, noise-realization, or
detection claim.

The branch-level freeze is recorded in
[`release_freeze_v1.json`](release_freeze_v1.json). It captures the current
357-test, Ruff, Pyright, deterministic-asset, and installed-wheel checks while keeping
`release_ready` false until the external gates close.

The intake gate is a prerequisite for external validation claims. Corpus
integrity tests are not product validation: repository contract tests and
physics regressions must still be run through the named VIS, SIG, and future
RAY/FPA measurement operators before a product claim is accepted.

## Typed claim registry

`exhaust_plume.validation.claims` loads the committed product catalog,
measurement-operator registry, and evidence-level taxonomy without importing
or rewriting experimental observations. It provides typed
`BenchmarkDefinition`, `MeasurementOperatorSpec`, and `ValidationClaim`
records. Quantitative claims require an explicit operator, uncertainty, and
provenance; an unacquired evidence level cannot be marked accepted.
