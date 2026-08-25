# Provider-bound validation acquisition matrix

This matrix is the handoff for the remaining external-validation work. It is
deliberately separate from the local lane contracts and from the recovered
corpus-intake result. The machine-readable comparison status remains the source
of truth in [`provider_comparison_preflight_v1.json`](provider_comparison_preflight_v1.json);
this document makes each missing provider-bound input and its acceptance
condition explicit.

## Global prerequisites

The user-provided Version 8 archive is integrity-valid:

- SHA-256: `79c2a34dd4c43bd976ceb8773fdccd78a2592d903bf03ca57c2aef82f882e9aa`
- 138 members, 137 internal checksum entries, and 57 isolated corpus tests
- embedded MVP alignment overlay present and verified
- separately named `plume_mvp_validation_alignment_v1.zip` still missing

The missing alignment archive must be acquired or explicitly removed from the
release requirement by its owner. It must not be reconstructed from the
embedded overlay or from digitized source figures.

The repository already has generic LOS/FOV, path-transfer, spectral sampling,
peak-normalization, bandpass, ray-to-signature, and FPA boundary operators.
Those operators are local/synthetic evidence until they receive the
provider-bound fields, observer, detector, and scenario inputs below.

## Gate matrix

| Product gate | Provider/corpus evidence already present | Required provider-bound output or input | Why the current lane cannot close it | Acceptance condition for a future lane |
| --- | --- | --- | --- | --- |
| VIS `VIS-MVP-A-061` | `RP-HOTWAKE-001`: 606 digitized chamber-pressure/Mach-disk-position points, pressure trace, and source uncertainty; the relation is explicitly hysteretic and unordered | Physical `mach_disk_position_m`; operating-point identity plus explicit branch/time/plateau semantics | The basic visual providers emit display channels only. Their bounded construction endpoint is not a physical Mach-disk endpoint. The corpus has no temporal branch ID | A dedicated visual provider emits a physical Mach-disk observable in metres with operating-point/branch semantics. Compare with a branch-aware, no-extrapolation operator using declared digitization uncertainty. Keep the outer-envelope claim separate; a frequency match cannot close this gate |
| SIG `SIG-MVP-A-043` | `RP-BSUV2-001`: 13 digitized markers over 0.2–0.4 micrometres, 4° line of sight, 2° FOV, altitude/time/flight state | Sensor-space radiance after the same LOS/FOV, source/path, and detector mapping | `signature.table-lookup` is an intrinsic synthetic table and has no BSUV2 source field, observer, path, or detector calibration. Direct comparison would mix measurement spaces | Bind an independent signature/source case to the BSUV2 observer and detector operator, then score sensor-space log residuals with digitization uncertainty. Do not label the result intrinsic `J_lambda` validation |
| SIG `SIG-MVP-A-064` | `RP-EMAP-RAD-001` UV-visible relative curve, approximately 500–850 nm, arbitrary/peak-normalized intensity | Sensor-sampled, peak-normalized spectral shape plus source case and applicable wavelength domain | The corpus is relative raster evidence; it does not supply an absolute source/calibration case. Normalization cannot validate absolute radiance | Bind a provider source/operating point and apply the declared spectral sampling/normalization operator only over the calibrated domain. Accept shape/features separately from absolute magnitude |
| SIG `SIG-MVP-A-066` | `RP-EMAP-RAD-001` FTIR relative raster envelope, approximately 2.5–5.5 micrometres | Sensor-sampled relative shape with measurement volume and calibration provenance | The FTIR product is an envelope from a published raster, not raw bins or independent source radiance/transmittance | Bind a provider field and FTIR measurement-volume/calibration model; score relative shape only and preserve the envelope uncertainty. No intrinsic absolute-radiance claim |
| SIG `SIG-MVP-A-073` | `RP-ALSI-001`: five averaged thermal-image runs, 2.5–5.5 and 3.5–5.0 micrometre bands, formulation labels, power/radiance/temperature rows | Band-integrated radiance plus formulation-sweep input and detector response | The signature contract is wavelength-resolved; the current table has no ALSI detector/image operator or formulation-bound provider input | Apply the actual bandpass/response and projected-area/image reduction to a formulation-bound provider. Score band power and composition sensitivity separately; retain the emissivity and Mach-disk caveats |
| RAY `RAY-MVP-A-044` | Same BSUV2 sensor-space markers and geometry metadata | Source spectral radiance, background transmittance/optical depth, plume field, observer, and detector binding | The gray provider only transfers through a homogeneous support; it has no BSUV2 plume field or calibrated detector scenario | Run the provider through the declared BSUV2 LOS/FOV/path/detector operator and compare the integrated sensor-space radiance. Source/path separation is not claimed unless independently observed |
| RAY `RAY-MVP-A-065` / `RAY-MVP-A-067` | EMAP UV/FTIR relative source-plus-path traces | Provider field, extinction/path model, measurement volume, and relative-calibration mapping | Generic ray helpers cannot infer a missing EMAP field or decompose a normalized source-plus-path trace into source and transmittance | Validate normalized line-of-sight shape after a provider-bound path operator. Keep source radiance and transmittance non-identifiable where the experiment does not separate them |
| RAY `RAY-MVP-A-068` | EMAP Gardon heat-flux trace digitized from a published display | Time-dependent source state, surface pose, detector response, conjugate thermal model, and flux operator | The current ray lane has no time-dependent source or surface/detector model; the corpus trace is not per-ray source-radiance truth | Bind a surface-flux provider and Gardon response, then score the detector-space time history. Do not infer radiation from total heat transfer |
| RAY `RAY-MVP-A-074` | ALSI band-integrated thermal/radiance table and measurement area | ALSI detector response, projected-area/image integration, source spectrum, path, and formulation case | Band integration alone cannot create the missing image geometry or source spectrum | Validate the declared band/image observable with a provider-bound detector response and projected-area operator |
| FPA boundary | Synthetic camera/optics identity, expected-electron integration, and deterministic ADC adapter | Validated upstream ray transfer, camera/optics calibration, detector response, measured counts/images, and an explicit noise/detection policy | V8 has no simultaneous visual/signature/ray/FPA truth set and the current FPA lane has no provider ID | Keep FPA downstream-only until an upstream ray provider and detector dataset close their own gates. Accept expected counts/ADC deterministically first; claim measured images/noise/detection only with external detector evidence |

## Lane policy

1. The basic shock-cell visual lane remains frozen at its engineering-approximate
   straight-geometry ceiling. A new Mach-disk or curved-flow model gets a new
   provider/lane and its own calibration and validation split.
2. The signature table remains an independent intrinsic-table provider. It is
   not backfilled from the visual lane or used to erase sensor-space and
   relative-calibration mismatches.
3. Optical transfer and FPA remain downstream composition lanes. Generic
   operators may be tested synthetically, but they do not create provider data.
4. A comparison is accepted only when its product, measurement space, operator,
   metric, uncertainty, provenance, applicability domain, and limitation are
   all recorded. A blocked comparison is an evidence gap, not a physics
   residual and not permission to relax the fidelity boundary.
