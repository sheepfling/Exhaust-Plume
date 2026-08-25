# MVP Product and Validation-Corpus Alignment

## Decision

Keep the Version 7 validation corpus **source- and experiment-centric**. Add this product-alignment overlay rather than reshaping every source table into a public product DTO.

The public architecture remains:

```text
PlumeProvider -> PlumeSession -> immutable PlumeSnapshot
                          |
          +---------------+----------------+
          |               |                |
          v               v                v
plume.visual.sectioned-tube@1     plume.signature.spectral-radiant-intensity@1     plume.optical.spectral-ray-transfer@1
          |               ^                |
          +------- supporting products ----+
            support / fields / particles /
            optical medium / engineering
```

This preserves the central MVP rule: geometry, unresolved signature, and resolved ray transfer are independent products. A provider may advertise one, two, or all three; evidence for one product does not automatically validate the others.

## Why a measurement-operator layer is mandatory

The experiments typically report:

- pressure or velocity at probes;
- PIV planes and vortex features;
- apparent spectral radiance through a line of sight and field of view;
- relative spectra or band-integrated radiance;
- surface heat flux, pressure, force, or temperature response;
- particle-size or particle-velocity distributions.

Those are not interchangeable with the native MVP outputs. Validation must therefore follow:

```text
canonical source data
      -> BenchmarkDefinition
      -> provider product at a PlumeSnapshot
      -> explicit MeasurementOperator
      -> predicted experiment/sensor observable
      -> metric + uncertainty
      -> scoped ValidationClaim
```

A `ValidationClaim` must never be a free-floating pass/fail flag. It must identify the benchmark, product, operator, metric, applicability domain, evidence level, uncertainty, provenance, calibration/validation role, and limitations.

## Evidence-level interpretation

| Level | Meaning | Permitted wording |
|---:|---|---|
| 0 | No evidence or source not acquired | No validation claim |
| 1 | Upstream context, boundary state, or component evidence | Informed by / consistent with |
| 2 | Indirect feature, relative shape, band result, or envelope | Baselined for the named feature only |
| 3 | Quantitative comparison after an explicit measurement operator | Quantitatively validated for the named observable/operator/domain |
| 4 | Direct native product observable with matching semantics/units | Directly validated for the named product quantity/domain |

The current corpus contains strong Level-4 evidence for selected **supporting** particle and field observables. It does not yet contain Level-4 evidence for intrinsic `plume.signature.spectral-radiant-intensity@1` or for the complete `plume.visual.sectioned-tube@1` geometry contract.

## Product-lane alignment

### 1. Visual geometry — `plume.visual.sectioned-tube@1`

Best current evidence:

- `RP-HOTWAKE-001`: Level 3 for Mach-disk position and named unsteady feature channels.
- `CJ-UEJ-001`: Level 2 for shock-cell phase/spacing and coherent-feature proxies; it is a cold gasdynamic precursor.
- `RW-IGE-001`: Level 2 for washed-plume/outwash position and vertical-structure proxies, with Level 3 direct field evidence underneath.
- `FW-DWOW-001`: Level 2 full-scale plausibility envelope only.
- `RP-RETALT-001`: Level 2 until schlieren/IR geometry is digitized.

The visual MVP can therefore be called **externally baselined for selected feature channels**, not yet directly validated as a complete sectioned-tube geometry. The most valuable next acquisitions are Black Brant plume-length curves, RETALT image geometry, and HART II measured PIV.

### 2. Unresolved signature — `plume.signature.spectral-radiant-intensity@1`

Best current evidence:

- `RP-BSUV2-001`: measured high-altitude UV **spectral radiance** in sensor space.
- `RP-EMAP-RAD-001`: relative UV/visible and FTIR spectral shapes.
- `RP-ALSI-001`: band radiance and total-power trends versus composition.
- `RP-IR-001`: promising flight IR case, but quantitative curves remain pending.

These datasets are valuable, but none directly measures intrinsic

$$J_\lambda(t,\hat{s})\;[\mathrm{W\,sr^{-1}\,m^{-1}}].$$

The direct `SignatureTableProvider` remains an excellent MVP path because it can ship independently after the common contract gate. Its external evidence must be described honestly as **sensor-space, relative-shape, or band-integrated forward-model validation** until range, atmosphere, projected source integration, instrument response, and absolute calibration close the measurement equation.

### 3. Resolved ray transfer — `plume.optical.spectral-ray-transfer@1`

Best current evidence:

- `RP-BSUV2-001`: Level 3 LOS/FOV UV spectral-radiance comparison.
- `RP-EMAP-RAD-001`: Level 3 relative spectral-shape and Gardon heat-flux comparisons.
- `RP-ALSI-001`: Level 3 band-radiance and total-power comparison.
- `RP-FASTRAC-001`: Level 2 extinction/radiance envelope, with Level 3 optical-medium scale evidence.

This is sufficient for a credible external ray-transfer baseline when combined with analytic slab, chord, layer-ordering, optically thin/thick, and grid-refinement tests. It is not yet a single end-to-end calibrated per-ray truth dataset.

## Supporting products are first-class evidence paths

The accumulated corpus strongly supports products beneath the three MVP lanes:

- `plume.field.local-state@1`: direct cold-jet profiles plus hot-plume pressure and surface-linked observations.
- `plume.particles.population@1`: direct EMAP particle-size and visible-window velocity distributions.
- `plume.optical.medium@1`: Fastrac extinction scale plus particle/composition constraints.
- `plume.engineering.surface-response@1`: surface pressure, heat flux, temperature response, and full-scale hazard envelopes.
- `plume.spatial.support@1`: conservative support constrained indirectly by velocity, vortex, and hazard envelopes.

These products should feed the provider implementations and validation claims. They should not be forced into one universal public result object.

## Required cross-product checks

The principal identity is:

$$J_\lambda(\hat{s})=\int_{A_\perp} L_{\lambda,\mathrm{source}}\,dA_\perp.$$

For a provider advertising both signature and ray products, native and ray-derived results must agree within declared quadrature and truncation tolerance. The background transmittance term remains separate and must not be folded into intrinsic source intensity.

Additional gates:

1. Every nonzero ray/source segment lies inside the same snapshot's conservative support.
2. A miss ray returns zero source radiance and declared background-transmittance behavior.
3. Band integration uses identical wavelength and detector-response conventions across SIG and RAY.
4. Co-reported products share a snapshot ID or explicit derivation chain.
5. Visual feature channels are generated from the same state or marked illustrative.
6. Signature-only data/providers cannot be used to infer geometry or local fields.
7. Calibration and validation cohorts remain disjoint.

## Recommended implementation order

```text
API-008 contract freeze
      |
      +-> ALIGN-001 claim overlay
      +-> ALIGN-002 measurement-operator registry
             |
             +-> VIS-VAL-001 CJ-UEJ shock-feature suite
             +-> VIS-VAL-002 RP-HOTWAKE Mach-disk suite
             +-> SIG-VAL-001 honest signature-table MVP
             +-> RAY-VAL-001 external sensor/flux/extinction suite
             +-> CROSS-VAL-001/002 product-consistency gates
```

The acquisition lane runs in parallel: Black Brant curves/cubes, full Fastrac report, NASA CR-150348 appendix, HART II archives, and RETALT image geometry.

## Repository boundary recommendation

```text
plume/
  contracts/                    # public product DTOs and capability IDs
  providers/                    # analytical, table, imported, curved, GPU
  validation/
    benchmarks/                 # source-centric canonical data references
    operators/                  # experiment/sensor measurement operators
    claims/                     # scoped ValidationClaim records
    suites/                     # VIS, SIG, RAY, supporting, cross-product gates
    metrics/                    # quantity-appropriate metrics
  assets/                       # versioned spectral/opacity/table assets
```

## Immediate release position

- **VIS:** contract-ready and externally constrained at feature level; not yet fully geometry-validated.
- **SIG:** contract/table-provider-ready; external evidence is currently proxy/sensor-space evidence, not direct intrinsic `J_lambda` truth.
- **RAY:** ready for an analytic plus multi-cohort external baseline, with explicit limitations per observable.
- **Supporting FIELD/PARTICLE/ENGINEERING products:** several quantitative and direct benchmark lanes are already mature enough to drive provider development.
