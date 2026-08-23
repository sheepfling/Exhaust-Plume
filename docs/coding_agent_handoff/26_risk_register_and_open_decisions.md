# Risk Register and Open Decisions

## 1. Purpose

This register prevents unresolved scientific and software choices from being
silently decided inside implementation patches. Each risk has a mitigation and
a phase gate. Each open decision has a current default so work can continue
without repeated clarification.

Risk scale:

```text
likelihood: LOW / MEDIUM / HIGH
impact:     LOW / MEDIUM / HIGH / CRITICAL
```

## 2. Scientific-model risks

| ID | Risk | Likelihood | Impact | Trigger or evidence | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| PHY-001 | Planar MOC is interpreted as axisymmetric physics after revolution | High | High | Results labeled axisymmetric without geometric source terms | Label model planar; keep rendering separate; later axisymmetric validation | Phase 1 |
| PHY-002 | Strong underexpansion is forced into weak attached cells | High | Critical | Requested turn/pressure exceeds attached solution | Maximum-turn and pressure-rise gates; `MACH_DISK_REQUIRED` | Phase 0/1 |
| PHY-003 | Strong overexpansion ignores internal nozzle separation | Medium | Critical | Uniform exit assumed at large adverse pressure ratio | Require validated exit source or return scope status | Phase 1 |
| PHY-004 | Shock-cell termination is tuned to a desired visual count | High | High | `max_cells` controls reported cell count | Physical decay/core criteria; calibration/validation split | Phase 2 |
| PHY-005 | Thermal/IR plume is truncated at shock-train end | High | High | Radiation domain equals last coherent cell | Integral mixing continuation and separate IR criterion | Phase 3/4 |
| PHY-006 | Constant gamma is used outside valid temperature/composition range | High | High | High-temperature or changing mixture cases | Explicit model level and thermally perfect phase | Phase 6 |
| PHY-007 | Molecular-only radiation misses particles/continuum | Medium | High | Sooting or aluminized propellant case | Validity flag; particle phase; propellant-specific model | Phase 6 |
| PHY-008 | LTE radiation is invalid at low density/high altitude | Medium | High | Collisional timescales too long or known non-LTE bands | Applicability gate and future non-LTE design | Phase 5/7 |
| PHY-009 | Ambient coflow materially changes cells but is omitted | High for flight | High | Nonzero flight Mach | Restrict initial calibration to quiescent ambient; explicit ambient velocity | Phase 2/7 |
| PHY-010 | Chemistry-afterburning changes temperature beyond frozen model | Medium | High | Fuel-rich exhaust entrains oxygen | Frozen validity flag; finite-rate continuation | Phase 6 |

## 3. Numerical risks

| ID | Risk | Likelihood | Impact | Trigger | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| NUM-001 | Closed-form oblique-shock formula loses branch continuity | Medium | High | Small turn or near maximum turn | Bracketed residual solve and analytic limits | Phase 0 |
| NUM-002 | Pseudoinverse accepts nonphysical intersections | High | High | Parallel/backward lines produce finite point | Parameterized rays, conditioning, residual checks | Phase 0 |
| NUM-003 | MOC geometry depends strongly on fan resolution | High | High | Cell metrics fail convergence | Predictor-corrector and refinement study | Phase 1 |
| NUM-004 | Reduced train ODE hides discontinuous topology | Medium | High | Mach disk or core collapse inside a cell | Event detection and topology status | Phase 2 |
| NUM-005 | Integral state recovery becomes nonphysical | Medium | High | Negative temperature/radius/species | Conservative variables, bounded recovery, terminate on invalid state | Phase 3 |
| NUM-006 | RTE loses precision for tiny optical depth | High | Medium | `1-exp(-tau)` cancellation | `expm1` exact segment update | Phase 4 |
| NUM-007 | Spectral interpolation creates negative opacity | Medium | High | Sparse tables or extrapolation | Nonnegative interpolation, bounds checks, validation | Phase 5 |
| NUM-008 | Performance optimization changes scientific result | Medium | High | Chunking/GPU path diverges | Reference CPU path and cross-backend tolerances | Phase 5+ |

## 4. Data and calibration risks

| ID | Risk | Likelihood | Impact | Trigger | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| DAT-001 | Calibration and validation reuse the same trace | High | Critical | Random point split within one case | Split by complete operating condition/campaign | Phase 2 |
| DAT-002 | Pressure-ratio definition is ambiguous | High | High | NPR and exit ratio used interchangeably | Manifest field with explicit numerator/denominator | All validation |
| DAT-003 | Remote dataset changes or disappears | Medium | High | Test downloads mutable URL | Content-addressed immutable fixtures | Before CI validation |
| DAT-004 | Measurement uncertainty is omitted | High | High | Residuals treat observations as exact | Record known/unknown uncertainty separately | Calibration |
| DAT-005 | Coefficients are unidentifiable | Medium | High | Correlated Jacobian columns | Sensitivity/SVD, fix or combine parameters | Phase 2/3 |
| DAT-006 | Spectroscopic table provenance is lost | Medium | Critical | Output cannot identify line list/version | Table manifest and hashes in every result | Phase 5 |
| DAT-007 | Propellant-specific chemistry data are unavailable | Medium | High | No mechanism or species set | Keep generic frozen interface; do not fabricate composition | Phase 6 |

## 5. Software and project risks

| ID | Risk | Likelihood | Impact | Trigger | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| SW-001 | Foundation PR becomes a full rewrite | High | High | MOC/radiation code appears in Phase 0 | File-by-file blueprint and stop rules | Phase 0 |
| SW-002 | Compatibility wrappers contaminate new internals | Medium | High | New modules import `compat` | One-way dependency rule; architecture test | Phase 0 |
| SW-003 | Pydantic/NumPy result serialization is ad hoc | Medium | High | Raw `model_dump` of arrays | Explicit schema adapter and array artifacts | Phase 0/1 |
| SW-004 | Optional dependencies break base import | Medium | High | HAPI/Cantera imported at module top level | Extras, lazy adapters, installed smoke | Every release |
| SW-005 | Pyright target is claimed but not enforced | High | Medium | New files absent from strict include | CI strict include for new modules | Phase 0 |
| SW-006 | Large reference data enter the wheel | Medium | High | Package size increases unexpectedly | Manifest-only large data and wheel audit | Phase 5 |
| SW-007 | Legacy warning noise makes tests unusable | Medium | Medium | Warning emitted at import or every property access | Warn on legacy construction/call, not import | Phase 0 |
| SW-008 | Generated plots become regression truth | Medium | Medium | Image comparison replaces physical metrics | Scalar/conservation tests first; plots diagnostic | All phases |

## 6. Open decisions with working defaults

## DEC-001 — First-cell geometry fidelity

### Question

Should the first implementation remain planar MOC or immediately implement
axisymmetric MOC/finite volume?

### Working default

Implement and validate planar MOC first. Label it accurately and keep a future
axisymmetric solver behind the same result interfaces.

### Decision due

Before Phase 7 design.

## DEC-002 — Overexpanded external-cell scope

### Question

What overexpanded pressure-ratio range may use a supplied uniform exit state?

### Working default

Do not hard-code a universal threshold. Require exit-source metadata and a
validation/calibration applicability record. Return
`NOZZLE_SEPARATION_NOT_MODELED` when the active policy cannot justify the
state.

### Decision due

Before Phase 1 validation cases are finalized.

## DEC-003 — Mach-disk classifier

### Question

Should the reduced solver use an empirical pressure-ratio threshold, attached-
shock feasibility, or both?

### Working default

Use local attached-shock feasibility as a mandatory physics gate. Treat any
empirical Mach-disk criterion as a separately sourced correlation with
applicability metadata.

### Decision due

During Phase 1/2 validation design.

## DEC-004 — Pydantic result envelopes versus dataclass-only API

### Question

Should all public results be Pydantic models?

### Working default

Use Pydantic for boundary/configuration and serialized envelopes; frozen
slotted dataclasses for computational states. Provide explicit conversion.

### Decision due

Phase 0 API review.

## DEC-005 — SciPy as a core dependency

### Question

Should bounded roots and ODE integration rely on SciPy in the base install?

### Working default

Yes, if the project accepts the dependency. Do not maintain duplicate fragile
root/ODE implementations solely to avoid SciPy. If base-size constraints
object, define a separate numerics backend ADR before coding alternatives.

### Decision due

Before Phase 0 dependency commit.

## DEC-006 — Result artifact format

### Question

NPZ, HDF5, or Zarr for large arrays?

### Working default

Use NPZ for small deterministic test fixtures and define a storage interface
before committing to production HDF5/Zarr. JSON/YAML holds metadata only.

### Decision due

Before Phase 4 result persistence.

## DEC-007 — Spectral coordinate

### Question

Should internal spectroscopy use wavelength or wavenumber?

### Working default

Use wavenumber for line-list/cross-section generation and one explicitly tested
conversion layer to wavelength outputs. Never mix density-per-wavelength and
density-per-wavenumber without the Jacobian.

### Decision due

Phase 5 schema freeze.

## DEC-008 — Atmosphere propagation implementation

### Question

Build an internal model, use MODTRAN-like external tooling, or accept user-
supplied transmission/path radiance?

### Working default

Define an interface first and support user-supplied tabulated transmission and
path radiance. Select an external implementation in a later ADR.

### Decision due

Phase 5.

## DEC-009 — Sensor output scope

### Question

Radiometric band signal only, or focal-plane counts/noise as well?

### Working default

Phase 5 ends at spectral/band irradiance and a generic detector response
integral. Detailed focal-plane electronics and detection probability are a
separate consumer layer.

### Decision due

After Phase 5 validation.

## DEC-010 — Chemistry boundary source

### Question

Invoke CEA directly at runtime or import generated boundary states?

### Working default

Start with reproducible offline CEA result ingestion. Runtime coupling is
optional later and must not be required for gas-dynamics unit tests.

### Decision due

Phase 6.

## DEC-011 — Multiple nozzles

### Question

When should plume-plume interaction be modeled?

### Working default

Not before one-nozzle flow and radiation pass validation. Preserve `nozzle_id`
space in future schemas but do not add interaction physics early.

### Decision due

Phase 7 design.

## 7. Escalation rule

The coding agent should stop the current issue and record an ADR proposal when:

- an open decision materially changes public schema;
- a proposed shortcut would weaken a phase gate;
- a new dependency changes base-package installation;
- a validation dataset conflicts with the assumed model topology;
- or a scientific correlation is needed without a source or applicability
  range.

It should not resolve these by silently selecting the easiest implementation.

## 8. Risk review cadence

Review this register:

```text
at the start of each phase
when a validity status is added
when a calibration artifact changes
before any public release
when a downstream result contradicts upstream validation
```

Closed risks remain in the history with the commit, test, or validation artifact
that closed them.
