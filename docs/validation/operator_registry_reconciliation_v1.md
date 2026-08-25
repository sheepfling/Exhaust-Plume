# Validation operator-registry reconciliation

The recovered Version 8 corpus is content-valid. Its embedded alignment
overlay uses a distinct external `operator.*` namespace, so it is not wire-
compatible with the committed registry. A complete scoped semantic
crosswalk is now recorded, while exact namespace identity remains false. This
is a contract distinction, not a data-integrity failure.

## Observed inventories

| Source | Product IDs | Alignment mappings | Operator IDs | Gate-eligible mappings |
| --- | ---: | ---: | ---: | ---: |
| Recovered `plume_validation_data_v8.zip` | 3 primary products | 78 | 35 `operator.*` IDs | 10 |
| Committed alignment directory | 8 catalog products | N/A | 20 `op.*` IDs | N/A |

The three primary product IDs agree exactly:

- `plume.visual.sectioned-tube@1`
- `plume.signature.spectral-radiant-intensity@1`
- `plume.optical.spectral-ray-transfer@1`

The operator namespaces do not agree. Examples include
`operator.extract.sectioned_tube_mach_disk_position` in the recovered corpus
and `op.visual.feature-extractor` in the committed registry. Similar-looking
names are not aliases until their input product, observable, metadata,
uncertainty, and benchmark scope are proven equivalent.

One narrow cross-product mapping has now been reviewed explicitly. The
embedded rule `MVP-X-001` names `adapter.far_field_from_rays@1`; its invariant
and required context match the committed `op.ray.projected-area-signature`
operator, and the implementation is exposed as the internal adapter
`plume.adapter.far-field-from-rays`. This mapping is accepted for the
synthetic cross-product consistency gate only. It is separate from the
external sensor/feature operator crosswalk used by the VIS, SIG, and RAY
measurement comparisons.

A second narrow mapping is recorded for the cold component diagnostic only:
`operator.sample.canonical_jet_probe_lines` maps to the committed
`op.field.profile-probe` semantics for disclosed `x/D`, `y/D`, probe/source
uncertainty, and profile sampling. The mapping is explicitly scoped to
`CJ-UEJ-001` supporting-component evidence; it does not reconcile the
external `operator.*` namespace by exact alias or authorize a primary VIS
product claim.

The complete semantic review is recorded in
[`operator_semantic_crosswalk_v1.json`](operator_semantic_crosswalk_v1.json).
It covers all 35 external IDs, including the seven unique operators used by
the ten primary-product gate mappings and the CJ-UEJ supporting-component
review. The review records one-to-one matches, ordered operator pipelines,
partial matches, and explicit no-safe-equivalent cases. It is a typed
governance artifact, not an automatic alias table: the semantic crosswalk is
`complete-scoped`, exact namespace identity remains pending, provider
execution remains separately gated, and every entry retains
`claim_status: not_accepted`.

In particular, the crosswalk makes these boundaries explicit:

- the Mach-disk feature operator is semantically scoped to
  `op.visual.feature-extractor`, but the current visual provider still lacks
  the feature channel;
- the two spectral-shape operators are pipelines over sampling,
  normalization, and (for RAY) LOS/FOV transfer, not intrinsic `J_lambda`
  claims;
- the Gardon and ALSI mappings are partial because surface response,
  detector calibration, formulation sweeps, or image-area lineage are not
  present in the current providers;
- `operator.image.integrate_alsi_band_and_area` has no safe committed
  equivalent and is deliberately not substituted with the source-only
  projected-area operator.

Three deterministic spectral-array helpers are now implemented and unit-tested
under the committed namespace: `op.sensor.spectral-sampling`,
`op.sensor.peak-normalize-spectrum`, and `op.sensor.band-integral`. They cover
interpolation, peak normalization, and numeric band reduction while preserving
validity masks. They deliberately do not implement line-of-sight geometry,
atmospheric transfer, detector response, source calibration, or formulation
sweeps. Their presence reduces an implementation gap but does not reconcile an
external `operator.*` ID by exact namespace or close a product gate.

The provider-comparison preflight also runs a bounded spectral-shape diagnostic
against the recovered BSUV2 and EMAP curves. It records no-overlap and
partial-overlap outcomes without extrapolation; the partial FTIR residuals are
measurement-space diagnostics from synthetic provider probes, not accepted
external validation. Non-spectral visual, Gardon time-history, and ALSI
band-integrated mappings are explicitly recorded as not executed by that
diagnostic.

The downstream `op.sensor.fpa-pixel-detector` adapter is also implemented and
unit-tested. It applies explicit ray-to-pixel collection weights, detector
spectral response, exposure, dark-current, read-noise variance, and invalid-ray
propagation to produce expected electrons. It is a deterministic measurement
adapter only: it does not advertise an FPA provider, draw random noise, or make
a detection decision.

## Release treatment

The typed `ValidationRegistry` loads only the committed registry and therefore
does not accept the recovered overlay as if it were already reconciled. The
corpus may be used for source-corpus integrity and alignment analysis, but no
external product claim is promoted to accepted status merely because a
semantic crosswalk entry exists; every reviewed entry remains explicitly
`not_accepted` until its provider-bound comparison closes.

The separate `plume_mvp_validation_alignment_v1.zip` named by the handoff is
still required. When recovered, compare its operator registry and crosswalk to
both inventories. If it does not provide an authoritative crosswalk, add one
explicitly with semantic review and tests; do not use string similarity or
prefix replacement as an automatic mapping rule.

## Consequence for product gates

- VIS can use the corpus's shock-feature mappings only after the feature
  operator is mapped to the canonical visual provider output and its metric
  domain is declared.
- The CJ-UEJ component record may use the reviewed profile-probe mapping for
  quantitative diagnostics, while its claim remains proposed and unaccepted.
- SIG can use the implemented spectral-array reductions for internal fixtures,
  but sensor-space and relative-shape mappings still require explicit
  line-of-sight, path, detector, and source-calibration operators; they do not
  become intrinsic `J_lambda` claims.
- RAY/FPA mappings remain downstream and require a ray-transfer provider,
  pixel/detector operator, and cross-product lineage checks.

This keeps the recovered data useful immediately while preventing a merge
conflict in governance metadata from becoming a false validation result.
