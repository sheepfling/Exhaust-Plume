# Comprehensive Work Plan

## 1. Purpose

This document is the master execution plan for evolving `sheepfling/Exhaust-Plume`
from the current idealized shock-cell study into a family of swappable plume
providers that serve two primary consumer profiles:

1. **Signature consumers** need intrinsic unresolved spectral radiant intensity
   as a function of time, wavelength, and source-to-observer direction. They do
   not require exposed geometry.
2. **Spatial/physical consumers** need plume support, geometry, local state,
   optical-medium properties, resolved ray transfer, or other spatial products.

The project must support straight, curved, rotor-washed, imported, and future
high-fidelity plumes through the same provider lifecycle. Morphology and
fidelity are metadata and applicability constraints; they are not separate API
families.

This plan consolidates the physics roadmap, provider-interface roadmap,
validation strategy, migration strategy, and coding-agent task packets into one
dependency-ordered program. It is authoritative for execution order. The
specialized documents remain authoritative for their detailed equations,
algorithms, contracts, and test fixtures.

## 2. Target outcome

The target package provides a stable plume-provider framework and several
interchangeable implementations:

```text
PlumeProvider
  -> PlumeSession
      -> PlumeSnapshot
          -> optional, versioned capabilities
```

The initial provider family is:

```text
SignatureTableProvider
    direct unresolved signature; no geometry required

ShockCellAnalyticalProvider
    corrected near-field shock-containing plume

IntegralStraightPlumeProvider
    downstream entraining and mixing continuation

CurvedIntegralPlumeProvider
    curved/crossflow/rotor-washed continuation

ImportedFieldProvider
    CFD/RANS/LES field adapter

GpuTransientPlumeProvider
    future transient general-3D provider
```

The richer physics path is compositional:

```text
corrected nozzle exit state
    -> analytical shock-containing near field
        -> conservative PlumeFluxSection handoff
            -> straight or curved mixing continuation
                -> optical-property adapter
                    -> resolved spectral ray transfer
                        -> far-field directional spectral intensity
```

A signature-only provider may bypass every spatial stage and implement
`directional-spectral-intensity` directly.

## 3. Non-negotiable program rules

1. **Provider-specific inputs, generic capability outputs.** A provider may
   require specialized inputs, but consumer-visible products follow stable,
   versioned capability contracts.
2. **No API split by morphology or fidelity.** Straight, curved, washed,
   analytical, tabulated, and CFD plumes use the same lifecycle.
3. **Geometry is optional.** A provider may use geometry internally while
   exposing only a signature.
4. **One physical plume may contain multiple model segments.** Shock cells and
   the downstream mixed plume are not separate consumer-level plume types.
5. **One plume contains multiple shock cells.** Repeated construction passes
   are not separate plumes.
6. **SI units internally; radians internally.** Degree conversion occurs only
   at CLI, display, or explicitly legacy boundaries.
7. **No hidden dry-air assumptions for rocket exhaust.** Gas properties are
   explicit.
8. **No silent extrapolation, fallback, or fabricated capability.** Domain
   violations and unsupported products are explicit.
9. **Physical termination and safety truncation are distinct.** Every spatial
   result reports a structured termination reason and whether it is physical.
10. **Radiation remains separable from flow.** Flow providers expose neutral
    fields or optical-medium products; radiation adapters derive signatures.
11. **Atmosphere, range, optics, and detector response are not intrinsic plume
    emission.** They are downstream observation layers.
12. **Every correlation and closure has provenance, applicability, calibration
    identity, and uncertainty metadata.**
13. **Every phase is gated.** Later fidelity cannot compensate for an earlier
    failed conservation, geometry, convergence, or contract gate.
14. **Public numerical contracts are immutable and fully typed.** Python 3.12+
    is the target baseline; scopes follow the repository's `####` convention.

## 4. Consumer products and capabilities

### 4.1 Signature profile

The smallest consumer port evaluates intrinsic spectral radiant intensity:

\[
J_\lambda(t,\hat{\mathbf s})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}].
\]

The input direction is a finite unit vector from source to observer in the
plume-local frame. The result excludes range loss, atmosphere, optics, detector
response, and sensor noise.

Required capability:

```text
directional-spectral-intensity v1
```

Optional simplified products may include band-integrated intensity, but the
spectral quantity remains the canonical interchange product.

### 4.2 Spatial/physical profile

A spatial consumer may request any supported subset of:

```text
spatial-support v1
axisymmetric-zone-field v1
centerline-tube-field v1
local-flow-state v1
optical-medium v1
spectral-ray-transfer v1
projected-area v1
scene-radiance-renderer v1
uncertainty v1
```

Capability absence is normal. A table provider is not defective because it has
no geometry, and an early shock-cell provider is not defective because it has
no spectral capability.

### 4.3 Capability derivation lattice

Richer products can often derive simpler products:

```text
local flow / species / particles
    + optical-property model
        -> optical medium
            -> spectral ray transfer
                -> spectral radiance image
                    -> directional spectral radiant intensity
```

The reverse derivations are generally impossible. Therefore the architecture
uses a product lattice, not a fidelity inheritance hierarchy.

## 5. Physical segmentation of plume models

The architecture distinguishes two physical regions while keeping one provider
surface.

### 5.1 Shock-containing near field

This region begins at the nozzle exit and contains expansion fans, compression
waves, shocks, possible shock cells, and a coherent supersonic core. The first
implementation is a corrected planar analytical/MOC study model presented as
an approximate axisymmetric field only where documented.

Primary provider:

```text
ShockCellAnalyticalProvider
```

Initial products:

```text
spatial-support
axisymmetric-zone-field
projected-area
termination and validity diagnostics
```

### 5.2 Entraining downstream plume

This region begins at a conservative cross-section handoff and continues mass,
momentum, total enthalpy, species, radius, and centerline evolution. It may be
straight or curved by ambient flow, rotor wash, buoyancy, or other forcing.

Primary providers:

```text
IntegralStraightPlumeProvider
CurvedIntegralPlumeProvider
```

Primary products:

```text
spatial-support
centerline-tube-field
local-flow-state
termination and validity diagnostics
```

### 5.3 Conservative handoff

Provider composition uses a neutral `PlumeFluxSection`, not legacy internal
zone objects. At a handoff plane with normal \(\mathbf n\):

\[
\dot m = \int_A \rho\,\mathbf u\!\cdot\!\mathbf n\,dA,
\]

\[
\mathbf\Pi = \int_A
\left[\rho\mathbf u(\mathbf u\!\cdot\!\mathbf n)+p\mathbf n\right]dA,
\]

\[
\dot H_0 = \int_A \rho h_0(\mathbf u\!\cdot\!\mathbf n)\,dA,
\]

\[
\dot m_s = \int_A \rho Y_s(\mathbf u\!\cdot\!\mathbf n)\,dA.
\]

The handoff also records area, centroid, local frame, average pressure,
applicability, uncertainty, and provenance. Downstream providers reconstruct a
state from these conserved quantities without depending on how the upstream
provider represented geometry.

## 6. Provider capability matrix

| Provider | Direct signature | Spatial support | Neutral field | Ray transfer | Typical morphology | Initial status |
| --- | --- | --- | --- | --- | --- | --- |
| `SignatureTableProvider` | Yes | No | No | No | Metadata only | Early parallel proof |
| `ShockCellAnalyticalProvider` | Via adapter later | Yes | Axisymmetric zones | Via adapter later | Straight | Critical physics path |
| `IntegralStraightPlumeProvider` | Via adapter later | Yes | Centerline tube/local state | Via adapter later | Straight | After conservative handoff |
| `CurvedIntegralPlumeProvider` | Via adapter later | Yes | Centerline tube/local state | Via adapter later | Curved/washed/crossflow | After straight integral model |
| `ImportedFieldProvider` | Optional | Yes | Local field | Optional | General | Later adapter path |
| `GpuTransientPlumeProvider` | Optional | Yes | General 3-D field | Optional | General 3-D | Final execution path |

## 7. Stable provider contracts

The provider-contract foundation must stabilize the following concepts before
physics providers depend on it:

```text
PlumeProvider[DefinitionT, ConfigurationT, OperatingStateT]
PlumeSession[OperatingStateT]
PlumeSnapshot
PlumeProviderDescriptor
ProviderFidelity
ProviderExecutionProfile
ProviderApplicability
PlumeProvenance
TerminationReport
CapabilityId + major version
```

The snapshot is a capability registry. Unsupported requests raise typed
contract errors. Physical out-of-model states normally return structured
validity/termination results rather than arbitrary numerical exceptions.

Execution behavior is explicit. A random-access table provider and a
monotonic-time GPU provider may implement the same capability semantics while
having different snapshot lifetime, batching, concurrency, and checkpointing
constraints.

## 8. Master workstreams

The program is organized into eleven workstreams. Milestones below combine
workstreams into reviewable pull requests.

### W0 — Governance, source baseline, and decisions

Maintain the reviewed branch/blob baseline, architecture decisions, equation
registry, risk register, calibration identity, and release gates. Re-audit a
source file before applying a packet when its blob SHA changes.

### W1 — Provider contracts and consumer semantics

Implement lifecycle contracts, capabilities, descriptors, applicability,
execution behavior, provenance, conformance tests, and package-neutral consumer
ports.

### W2 — Corrected gas, nozzle, shock, and geometry foundation

Correct the choked mass-flow equation, explicit gas-property flow, total-energy
naming, weak/strong shock branches, attached-shock validity, expansion-regime
classification, line/ray intersections, precursor geometry, and result types.

### W3 — Validated shock-cell physics

Implement robust Prandtl–Meyer inversion, planar characteristics, centerline
compatibility, ambient-pressure free boundary, mild underexpanded and attached
overexpanded first cells, topology checks, correlation comparison, and
convergence studies.

### W4 — Finite shock train and physical termination

Add calibrated coherent-core shrinkage, pressure-amplitude decay, local cell
spacing, downstream reduced-order cells, total-pressure loss, physical
termination, safety truncation, diagnostics, sensitivity, and validation.

### W5 — Straight and curved mixing continuations

Implement conservative handoff, straight integral entrainment, state recovery,
field reconstruction, then curved-centerline dynamics and local transported
frames under crossflow/rotor-wash forcing.

### W6 — Radiative transfer and far-field signatures

Implement Planck radiation, axisymmetric ray geometry, gray LTE transfer,
spectral images, angular integration, far-field signature adapters, molecular
cross sections, atmosphere interfaces, and detector-response layers.

### W7 — Direct signature and consumer adapters

Implement a direct table provider and a package-neutral unresolved-source
adapter. This proves that geometry is optional and enables early consumer
integration independently of the full physics path.

### W8 — Thermochemistry and particles

Add frozen/equilibrium mixture contracts, CEA boundary-state import,
thermally-perfect properties, finite-rate afterburning, particle populations,
particle thermal lag, and particle optical effects.

### W9 — Imported and accelerated providers

Add imported CFD/RANS/LES fields, then transient GPU/general-3D execution after
execution-profile conformance is proven.

### W10 — Verification, validation, calibration, uncertainty, and release

Maintain analytic verification, property tests, convergence tests, provider
conformance, external validation, calibration/validation separation,
uncertainty propagation, performance baselines, documentation, wheel smoke,
and release evidence.

## 9. Master dependency graph

The critical physics and product path is:

```text
M0 architecture and baseline
  -> M1 provider contract foundation
      -> M2 corrected foundation and exit-state boundary
          -> M3 analytical provider wrapper
              -> M4 validated first cell
                  -> M5 finite shock train
                      -> M6 conservative handoff
                          -> M7 straight mixing provider
                              -> M8 gray ray transfer
                                  -> M9 far-field signature adapter
                                      -> M11 molecular spectra
                                          -> M13 thermochemistry/particles
```

Parallel lanes are allowed only where semantics are already stable:

```text
M1 -> M10 SignatureTableProvider -> M9-compatible consumer source port
M1 -> imported-field contract design
M6/M7 -> M12 curved-plume design and provider
M8 -> atmosphere/sensor interface design
M1 + execution conformance -> M15 GPU transient provider design
W10 validation/data work runs beside every milestone
```

No parallel lane may redefine a capability already used by another lane.

## 10. Milestone M0 — Architecture and repository baseline

### Objective

Freeze the execution boundary before code changes: two consumer profiles,
capability lattice, provider lifecycle, physical segmentation, neutral handoff,
units, error semantics, compatibility policy, and model-level terminology.

### Required work

- Confirm the reviewed branch and source SHAs.
- Approve capability IDs and major versions.
- Approve the plume-local frame and source-to-observer direction convention.
- Approve geometry visibility states: `INTERNAL_ONLY`,
  `EXPOSED_APPROXIMATE`, and `EXPOSED_VALIDATED`.
- Resolve architecture decisions that block Phase 0, especially public
  configuration/result representation and dependency policy.
- Record accepted decisions in the ADR document and machine-readable plan.

### Deliverables

```text
approved ADR set
provider capability registry v1
updated handoff manifest and work plan
source-baseline record
open-decision list with owners and decision gates
```

### Exit gate

- No unresolved decision blocks provider contracts or foundation corrections.
- Consumer semantics are independent of plume morphology and fidelity.
- Existing public APIs have an additive migration strategy.

### Explicit non-goals

No new plume physics and no consumer-specific dependency.

## 11. Milestone M1 — Provider contract foundation (`PR I0`)

### Objective

Introduce the provider/session/snapshot seam without changing existing plume
physics or breaking the legacy solver API.

### Dependencies

`M0` complete.

### Work

Create:

```text
src/exhaust_plume/contracts/
  capability.py
  descriptor.py
  errors.py
  execution.py
  provenance.py
  snapshot.py
  spatial.py
  radiometry.py

src/exhaust_plume/providers/
  __init__.py
```

Implement:

- stable `CapabilityId` and major-version lookup;
- provider/session/snapshot protocols;
- immutable descriptors;
- fidelity, morphology, and execution metadata as separate structures;
- applicability query structures;
- structured termination and provenance;
- typed unsupported/version/domain errors;
- fake-provider fixtures and universal conformance tests.

### Deliverables

```text
core provider contracts v1
capability registry v1
fake direct-signature provider for tests
fake spatial provider for tests
provider conformance test harness
contract API documentation
```

### Acceptance

- Existing `calculatePlumeZones` behavior remains unchanged.
- A fake provider can create a session, produce a snapshot, and serve a typed
  capability.
- Unsupported capabilities and version mismatches produce the specified errors.
- Morphology, fidelity, and execution behavior are not collapsed into one
  ranking or inheritance branch.
- Snapshot lifetime and session closure are tested.
- `pytest`, `ruff`, `pyright`, build, and installed-wheel smoke pass.

### No-go conditions

- Provider contracts import the existing plume solver.
- A capability fabricates unavailable geometry or radiation.
- Provider inputs are forced into one universal nozzle-centric schema.

## 12. Milestone M2 — Corrected foundation and exit-state boundary (`FND-A` through `FND-F`, `PR I1`)

### Objective

Correct the thermodynamic, nozzle, shock, geometry, regime, result, and quality
foundation, then establish an explicit nozzle-exit-state boundary for all
physics providers.

### Dependencies

`M1` may be merged first or developed in a nonconflicting parallel branch. The
foundation gate must pass before `M3` uses the contracts.

### Work packets

#### FND-A — Explicit gas and nozzle contracts

- Add frozen gas/nozzle input models with explicit molecular weight or specific
  gas constant.
- Make units explicit in field names.
- Establish immutable configuration/result conventions.
- Remove hidden assumptions from new core paths while preserving a documented
  legacy wrapper.

#### FND-B — Correct nozzle equations and energy naming

Correct the choked throat relation:

\[
A^*=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

- Verify area–Mach and mass-flow inversion.
- Replace misleading `specific_total_energy_Jpkg` semantics with explicit
  thermodynamic properties such as total enthalpy.
- Use the supplied gas model in density, sound speed, velocity, and mass flux.

#### FND-C — Oblique-shock branches and validity

- Correct the weak zero-turn limit to the Mach angle.
- Keep the strong zero-turn limit at \(90^\circ\).
- Implement maximum attached-turn detection.
- Return structured `DETACHED_SHOCK_REQUIRED` or equivalent validity status.
- Ensure total pressure decreases and total temperature is conserved across an
  adiabatic calorically-perfect shock.

#### FND-D — Geometry primitives and precursor correction

- Replace point-only pseudoinverse intersections with conditioned line/ray
  results containing parameters, residual, and status.
- Require forward ray parameters for physical intersections.
- Correct the overexpanded precursor centerline distance:

\[
\Delta x=\frac{R}{\tan\beta}.
\]

- Eliminate public placeholder `NaN` polygons by separating transitions,
  characteristic segments, shock segments, and closed zones.

#### FND-E — Regime, result separation, and compatibility

Use a pressure residual:

\[
r_p=\frac{p_e-p_a}{p_a}
\]

with explicit underexpanded, overexpanded, and matched ranges.

- Matched flow returns zero shock cells and `NO_PRESSURE_MISMATCH`.
- Rename repeated plume passes to cells or construction passes.
- Add new result/status structures and a legacy adapter.
- Construct regime-controlled tests from target \(p_e/p_a\), not misleading
  total-pressure labels.

#### FND-F — Quality and gate

- Python 3.12 target.
- Fully typed public and critical numerical paths.
- `pytest`, `ruff`, `pyright`, build, and installed-wheel smoke.
- Updated equations, units, migration, and limitation documentation.

### New boundary

```text
legacy calculatePlumeZones(total conditions, ...)
  -> corrected NozzleExitState
      -> calculatePlumeZonesFromExitState(...)
```

The exit-state route becomes the provider entry point. There is one core solve,
not duplicated legacy and provider implementations.

### Deliverables

```text
GasProperties / FrozenGasModel contracts
NozzleExitState contract
corrected nozzle and shock utilities
robust geometry primitives
regime classifier
neutral transition/closed-zone results
legacy compatibility wrapper
Phase 0 evidence report
```

### Acceptance

- Standard mass-flow fixtures pass.
- Molecular weight changes density, sound speed, velocity, and mass flux
  consistently.
- Isentropic round trips close within tolerance.
- Normal/oblique shock conservation residuals pass.
- Weak-branch zero-turn behavior is correct.
- Detached/unattainable shocks are explicit.
- Matched expansion yields no shock-cell construction.
- Every accepted physical intersection lies on the originating forward rays.
- No public closed zone contains nonfinite placeholder geometry.
- Legacy behavior is either preserved or intentionally corrected with a
  documented migration test.

### Explicit non-goals

No new MOC first-cell solver, no shock-train calibration, no radiation, no
chemistry, and no curved plume.

## 13. Milestone M3 — `ShockCellAnalyticalProvider` wrapper (`PR I2`)

### Objective

Expose the corrected analytical solver through neutral provider capabilities
without making legacy `ZoneResult` the permanent interchange format.

### Dependencies

`M1` and `M2` complete.

### Initial capabilities

```text
spatial-support v1
axisymmetric-zone-field v1
projected-area v1
```

### Work

- Add provider-specific definition, configuration, and operating-state models.
- Map corrected solver inputs to a session and snapshot.
- Convert internal transitions/zones to neutral field products.
- Expose structured applicability, termination, approximation, and provenance.
- Declare geometry `EXPOSED_APPROXIMATE` until Phase 1 validation passes.
- Add provider/direct-solver numerical-equivalence tests.

### Deliverables

```text
ShockCellAnalyticalProvider
provider-specific schemas
neutral zone-field capability
legacy adapter sharing the same core implementation
provider conformance tests
```

### Acceptance

- Direct solver and provider snapshot agree for common fixtures.
- Invalid geometry is rejected rather than exported.
- No spectral capability is advertised.
- A signature consumer cannot accidentally depend on shock-cell geometry.
- Provider descriptor states planar analytical origin and validation level.

## 14. Milestone M4 — Validated first shock cell (`MOC-A` through `MOC-F`)

### Objective

Replace heuristic first-cell construction with a verified planar
method-of-characteristics/free-boundary solution for documented mild regimes.

### Dependencies

`M3` complete and Phase 0 gate closed.

### Work packets

#### MOC-A — Characteristic primitives and Prandtl–Meyer inverse

- Harden bracketed inversion of \(\nu(M)\).
- Add characteristic state/segment contracts.
- Verify monotonicity and limiting behavior.

#### MOC-B — Interior and centerline point solvers

For planar isentropic irrotational flow:

\[
K^+=\theta-\nu(M),
\qquad
K^-=\theta+\nu(M),
\]

constant on the appropriate characteristic families, with slopes

\[
\frac{dy}{dx}=\tan(\theta\pm\mu).
\]

At the centerline:

\[
\theta=0.
\]

Implement compatibility and conditioned downstream intersections.

#### MOC-C — Ambient-pressure free boundary

Enforce:

\[
p_b=p_a,
\qquad
\frac{dy_b}{dx}=\tan\theta_b.
\]

Replace the fitted parabola as the authoritative boundary. Preserve the old fit
only as a diagnostic comparison if useful.

#### MOC-D — Mild underexpanded first-cell assembly

- Construct lip expansion, interior characteristics, centerline reflection,
  free-boundary closure, and compression structure.
- Verify closed-zone topology and finite state.

#### MOC-E — Mild attached overexpanded first-cell assembly

- Support only the documented attached external-shock regime.
- Reject cases requiring nozzle separation or detached/Mach-disk topology.

#### MOC-F — Correlation, convergence, and validation gate

Calculate the equivalent fully expanded jet and compare the first cell with the
classical circular-jet scale:

\[
L_{s,0}\approx1.306D_j\sqrt{M_j^2-1}.
\]

Perform fan-resolution, tolerance, and geometry-convergence studies. Compare
against at least one independent experimental or CFD reference family.

### Deliverables

```text
planar characteristic solver
centerline solver
ambient-pressure free-boundary solver
validated mild underexpanded first cell
validated mild attached overexpanded first cell
closed-zone topology validator
convergence and validation report
updated provider fidelity metadata
```

### Acceptance

- Characteristic compatibility residuals satisfy tolerance.
- Centerline flow angle closes to zero.
- Free-boundary pressure satisfies ambient tolerance.
- Every segment intersection is forward and conditioned.
- Polygon/zone topology is closed, finite, and consistently oriented.
- Results converge under characteristic refinement.
- First-cell scale is physically plausible relative to correlation and
  reference data; differences are explained, not tuned away silently.
- Out-of-scope strong regimes return structured validity status.
- `ShockCellAnalyticalProvider` capability semantics do not change when the
  internal first-cell implementation improves.

## 15. Milestone M5 — Finite coherent shock train (`TRN-001` through `TRN-009`)

### Objective

Predict a finite sequence of coherent shock cells with physical termination and
calibrated uncertainty instead of accepting a supposedly physical cell count.

### Dependencies

`M4` complete.

### Work

- Add a versioned shock-train calibration contract.
- Implement inward shear-layer growth and coherent-core diameter:

\[
\delta_i(x)=\delta_{i,0}+S_i x,
\qquad
D_c(x)=\max[D_j-2\delta_i(x),0].
\]

- Implement pressure-oscillation decay:

\[
\frac{dA_p}{dx}=-\frac{C_d}{D_c(x)}A_p.
\]

- Implement local cell-spacing continuation:

\[
L_s(x)=C_\lambda D_c(x)\sqrt{M_c(x)^2-1}.
\]

- Propagate total-pressure loss and reduced-order downstream cell geometry.
- Add physical criteria:

```text
pressure oscillation decayed
mixing layer reached axis
core became subsonic
mean pressure and oscillation near ambient
```

- Add safety criteria:

```text
maximum cells
maximum axial domain
numerical failure
unsupported topology
```

- Report whether termination is physical or imposed.
- Calibrate and validate on separate datasets.
- Propagate parameter sensitivity and uncertainty to cell count and endpoint.

### Deliverables

```text
ShockTrainCalibration
ShockCellMetrics
ShockTrainResult
TerminationPolicy
TerminationReport
calibration artifact and independent validation report
uncertainty summary
```

### Acceptance

- Cell count tends to zero as pressure mismatch tends to zero.
- Greater mixing or decay reduces coherent length in the expected direction.
- Physical termination and truncation are never conflated.
- Calibration and validation datasets are disjoint and provenance-recorded.
- Predicted first-cell properties remain governed by Phase 1, not overridden by
  downstream calibration.
- Shock-train result includes final residuals, last core Mach/diameter, last
  oscillation amplitude, and applicability.

## 16. Milestone M6 — Conservative provider handoff (`PR I3`)

### Objective

Create the neutral seam from a near-field provider to any downstream plume
continuation.

### Dependencies

`M5` complete for the production handoff; contract prototyping may begin after
`M3`.

### Work

- Implement `PlumeFluxSection` and species/particle extensions.
- Integrate conserved fluxes over analytical zones.
- Record local frame, section geometry, covariance/uncertainty, and provenance.
- Implement closure checks comparing upstream integrated fluxes with the
  serialized handoff and downstream reconstructed initial state.
- Define handoff selection by physical endpoint or requested axial section.

### Deliverables

```text
PlumeFluxSection v1
ShockCellToFluxSection adapter
conservation residual report
serialization fixtures
cross-provider composition tests
```

### Acceptance

- Mass, axial/vector momentum, total enthalpy, and species fluxes close within
  documented tolerance.
- The handoff does not expose legacy analytical-zone types.
- A fake downstream provider can initialize solely from the neutral section.
- Uncertainty and calibration provenance survive the handoff.

## 17. Milestone M7 — Straight integral mixing provider (`MIX-001` through `MIX-006`)

### Objective

Continue the plume beyond coherent shock cells using an entraining integral
model and reconstruct a neutral spatial field.

### Dependencies

`M6` complete.

### Governing structure

Mass entrainment closure:

\[
\frac{d\dot m}{dx}
=2\pi R\rho_a E|u-u_a|.
\]

Momentum, total enthalpy, and species balances:

\[
\frac{d}{dx}\left[\dot m u+(p-p_a)A\right]=0,
\]

\[
\frac{d}{dx}(\dot m h_0)
=h_{0a}\frac{d\dot m}{dx}
+\dot Q'_{\mathrm{chem}}-\dot Q'_{\mathrm{rad}},
\]

\[
\frac{d}{dx}(\dot mY_s)
=Y_{s,a}\frac{d\dot m}{dx}+\dot\omega_sA.
\]

The first implementation is frozen and nonreacting:

\[
\dot\omega_s=0,
\qquad
\dot Q'_{\mathrm{chem}}=0.
\]

### Work

- Add conserved integral-state contracts.
- Implement top-hat ODE integration and thermodynamic state recovery.
- Add ambient-equilibrium/domain events.
- Reconstruct a top-hat axisymmetric field.
- Add a flux-preserving Gaussian profile option.
- Expose `spatial-support`, `centerline-tube-field`, and `local-flow-state`.
- Implement as `IntegralStraightPlumeProvider` or a composable continuation
  session.

### Deliverables

```text
IntegralStraightPlumeProvider
integral state ODE
state recovery
termination events
axisymmetric top-hat and Gaussian field reconstructions
cross-provider handoff tests
```

### Acceptance

- Integrated mass increase equals ambient entrainment.
- Momentum and total-enthalpy residuals satisfy tolerance.
- Frozen species and elemental totals are conserved.
- Reconstructed profiles preserve the intended integral fluxes.
- Field approaches ambient conditions in a physically consistent direction.
- Termination is structured and distinct from the shock-train endpoint.

## 18. Milestone M8 — Gray radiative transfer (`RAD-001` through `RAD-006`, `PR I4`)

### Objective

Create a verified resolved ray-transfer path over neutral plume fields before
adding molecular spectroscopy.

### Dependencies

`M7` for the complete downstream field. Infrastructure may be unit-developed
against analytic synthetic fields earlier.

### Work

- Implement spectral coordinate/unit contracts and Planck radiance.
- Implement axisymmetric ray geometry in the plume-local frame.
- Intersect and order ray segments through zone and tube fields.
- Implement exact LTE, no-scattering segment transfer:

\[
I_{\lambda,i+1}
=I_{\lambda,i}e^{-\Delta\tau_{\lambda,i}}
+B_\lambda(T_i)\left(1-e^{-\Delta\tau_{\lambda,i}}\right).
\]

- Use numerically stable `expm1` formulations for small optical depth.
- Produce spectral radiance images and area integration.
- Sweep observer direction.
- Add a separate IR-domain termination criterion based on incremental band
  contribution.
- Expose `spectral-ray-transfer v1` through adapters.

### Deliverables

```text
Planck and spectral-unit utilities
axisymmetric ray marcher
GrayOpticalPropertyModel
gray spectral-ray-transfer adapter
radiance image result
angular sweep result
IR-domain termination report
analytic verification report
```

### Acceptance

- Homogeneous slab matches the analytic solution.
- Zero opacity returns background radiance.
- Optically thin radiance is linear in concentration/path length.
- Optically thick radiance approaches Planck radiance.
- Hot/cold layer order produces the correct self-absorption difference.
- Cylinder/tube chord lengths match analytic geometry.
- Complete-image optically thin integrated emission is nearly orientation
  invariant where expected.
- Ray, pixel, and axial-domain refinement converge.

## 19. Milestone M9 — Far-field signature and consumer integration (`PR I5`, `PR I7`)

### Objective

Derive the canonical signature product from resolved rays and provide a
package-neutral adapter for unresolved consumers.

### Dependencies

`M8` for the physics-backed path. The consumer port may be specified and tested
with a fake provider after `M1`.

### Work

Integrate radiance over the orthographic image plane:

\[
J_\lambda(\hat{\mathbf s})
=\int_{A_\perp}I_\lambda(u,v;\hat{\mathbf s})\,du\,dv.
\]

- Implement `FarFieldFromRays` adapter.
- Implement direction and wavelength batching.
- Add unresolved-distance applicability checks using source support and
  requested observer range where the consumer layer needs them.
- Implement a package-neutral `DirectionalSpectralSource` adapter.
- Keep atmosphere and sensor response outside the intrinsic source result.
- Add rich-to-simple equivalence tests.

### Deliverables

```text
FarFieldFromRays adapter
directional-spectral-intensity capability
consumer-facing source port adapter
batch evaluation support
resolved-to-unresolved equivalence report
```

### Acceptance

- Direction vectors are validated and normalized according to contract.
- Spectral units and wavelength-grid identity are preserved.
- Orthographic integration converges under image refinement.
- The adapter result matches direct integration fixtures.
- The consumer adapter depends only on the small signature port, not provider
  internals or geometry.

## 20. Milestone M10 — Direct `SignatureTableProvider` (`PR I6`)

### Objective

Prove the signature-only use case independently of the spatial physics path and
support fast lookup/surrogate products.

### Dependencies

`M1` complete. This milestone can proceed in parallel with `M2` through `M8`.

### Work

- Define table asset schema for time/operating state, direction, wavelength,
  values, units, frame, provenance, calibration, uncertainty, and validity.
- Implement explicit interpolation and no-silent-extrapolation behavior.
- Support direction batching and random-access snapshots.
- Expose only `directional-spectral-intensity` unless an asset genuinely
  includes another standard capability.
- Add asset digest and reproducibility metadata.

### Deliverables

```text
SignatureTableProvider
versioned table asset schema
table ingestion and validation
interpolation/extrapolation policy
signature-provider conformance tests
```

### Acceptance

- Table nodes reproduce exactly.
- Interpolation behavior is deterministic and documented.
- Out-of-domain time, angle, wavelength, or operating state is explicit.
- The provider exposes no fake geometry.
- A signature consumer can swap between the table provider and
  `FarFieldFromRays` without changing query semantics.

## 21. Milestone M11 — Molecular spectral radiation (`SPC-001` through `SPC-007`)

### Objective

Replace gray opacity with validated high-temperature molecular absorption and
emission while preserving the same ray-transfer and signature capabilities.

### Dependencies

`M8` and `M9` complete. Frozen composition must be available from provider
fields or prescribed inputs.

### Work

- Build an offline reproducible HITEMP/HITRAN/HAPI cross-section generator.
- Store per-species cross sections on a versioned \((T,p,\tilde\nu)\) grid.
- Record database/version/source digests and line-shape assumptions.
- Implement bounded interpolation with no silent extrapolation.
- Form mixture absorption:

\[
\alpha_{\tilde\nu}=\sum_s n_s\sigma_s(\tilde\nu,T,p).
\]

- Integrate molecular optical properties into images and directional
  signatures.
- Add atmosphere propagation interface and detector-response model as separate
  downstream layers.
- Validate against standalone spectral fixtures and heated-plume image/spectral
  data.

### Deliverables

```text
cross-section generator
versioned spectral assets
molecular optical-property model
molecular images and signatures
atmosphere interface
detector response interface
spectral validation report
```

### Acceptance

- Cross sections reproduce generator reference cases.
- Number-density, cross-section, optical-depth, and radiance units are closed.
- Interpolation and spectral-grid refinement converge.
- Gray limit or prescribed-opacity compatibility is retained.
- Atmosphere and detector layers cannot be confused with intrinsic plume
  emission.
- External validation residuals and known discrepancies are documented.

## 22. Milestone M12 — Curved/washed integral provider

### Objective

Add a curved downstream plume that serves the same spatial and radiometric
capabilities as the straight provider.

### Dependencies

`M6` and `M7` complete. The dedicated curved-plume physics design must be
approved before implementation.

### Design gate

Approve equations and contracts for:

- ambient flow-field sampling;
- centerline arc-length parameterization;
- vector momentum evolution;
- crossflow/rotor-wash entrainment closure;
- buoyancy or body-force terms where applicable;
- parallel-transport local frame;
- radius and cross-sectional profile evolution;
- source/near-field handoff and validity regime;
- self-intersection and excessive-curvature handling.

### Geometric representation

\[
\mathbf c(s),
\qquad
\mathbf t(s)=\frac{d\mathbf c}{ds},
\qquad
R(s),
\]

with a transported normal/binormal frame and local cross-sectional fields.
A representative vector balance is

\[
\frac{d}{ds}(\dot m\mathbf u)
=\mathbf f_{\mathrm{entrainment}}
+\mathbf f_{\mathrm{crossflow}}
+\mathbf f_{\mathrm{buoyancy}}
+\cdots.
\]

### Work

- Implement ambient-flow service contract.
- Generalize integral state from scalar axial momentum to vector momentum.
- Implement centerline integration and parallel-transport frame.
- Reconstruct `centerline-tube-field` and `local-flow-state` in 3-D.
- Reuse optical-medium and ray-transfer adapters where applicable.
- Add straight-limit equivalence, rigid-transform invariance, and curvature
  conformance tests.

### Deliverables

```text
approved curved-plume physics specification
CurvedIntegralPlumeProvider
ambient-flow service contract
centerline and transported-frame solver
curved tube-field capability
curved ray-intersection support
validation/applicability report
```

### Acceptance

- Zero crossflow/forcing converges to the straight provider within tolerance.
- Global rigid transforms do not change intrinsic plume results.
- Centerline arc length and frame remain continuous without Frenet-frame flips.
- Conserved fluxes close along the curved path according to modeled forces and
  entrainment.
- Spatial and signature consumers require no API changes.
- Applicability under rotor wash/crossflow is explicit and calibration-backed.

## 23. Milestone M13 — Thermochemistry and particles (`CHEM-001` through `CHEM-008`)

### Objective

Increase thermodynamic and radiative fidelity without changing consumer
capability semantics.

### Dependencies

`M7` and `M11` complete. Frozen molecular radiation is validated first.

### Work

- Add species/mixture contracts and elemental inventories.
- Add CEA boundary-state adapter with frozen/equilibrium provenance.
- Add thermally-perfect \(h(T,\mathbf Y)\), \(c_p(T,\mathbf Y)\),
  \(R(\mathbf Y)\), and \(\gamma(T,\mathbf Y)\).
- Add frozen variable-property expansion/shock reference paths.
- Add equilibrium reference calculations.
- Add finite-rate integral afterburning:

\[
\frac{d}{dx}(\dot mY_s)
=Y_{s,a}\frac{d\dot m}{dx}+\dot\omega_sA,
\]

with chemical enthalpy coupling.
- Add particle population, particle temperature lag, absorption/emission, and
  later scattering.

### Deliverables

```text
mixture/species contracts
CEA boundary adapter
thermally-perfect property model
finite-rate chemistry adapter
particle population and thermal model
particle optical-property model
chemistry/particle validation report
```

### Acceptance

- Species fractions sum to one and elemental abundances close.
- Frozen/equilibrium reference limits reproduce source calculations.
- Reaction enthalpy and total-energy accounting close.
- Disabling reaction rates recovers frozen behavior.
- Particle-free and zero-loading limits recover the molecular model.
- Provider capability versions remain unchanged unless semantics, not fidelity,
  break.

## 24. Milestone M14 — Imported field provider (`PR I8`)

### Objective

Allow CFD/RANS/LES or other field assets to participate in the same provider
and radiation ecosystem.

### Dependencies

`M1` and stable spatial contracts. Molecular/optical adapters may be attached
when field content permits.

### Work

- Define imported-field asset schema, coordinates, units, time identity,
  interpolation, topology, species, particles, and provenance.
- Implement local-flow and spatial-support capabilities.
- Add optical-medium/ray adapters when sufficient state is present.
- Add conservative section extraction for provider chaining.
- Add transformation and interpolation conformance tests.

### Acceptance

- No hidden unit or coordinate conversion.
- Asset digest and source solver metadata are retained.
- Interpolation is deterministic and domain-bounded.
- Equivalent neutral fields produce equivalent downstream radiometric products
  within tolerance.

## 25. Milestone M15 — GPU transient/general-3D provider (`PR I9`)

### Objective

Add high-throughput or transient providers only after execution-profile
semantics are proven.

### Dependencies

`M1`, conformance harness, and at least one stable semantic implementation of
each capability being accelerated.

### Work

- Declare monotonic/random time access, snapshot lifetime, concurrency,
  batching, checkpointability, preferred device, and host/device result rules.
- Implement direction/ray batching.
- Enforce snapshot invalidation behavior.
- Compare semantic host results against CPU/reference capability fixtures.
- Add resource failure and checkpoint recovery tests.

### Acceptance

- Execution differences do not alter physical quantity semantics.
- Snapshot lifetime violations are detected.
- Batched and scalar evaluations agree.
- Determinism/reproducibility status is explicit.
- GPU-specific assets do not leak into consumer contracts.

## 26. Cross-cutting validation program

Every milestone includes five evidence classes.

### 26.1 Analytic verification

Examples:

- isentropic round trips;
- choked mass flow;
- area–Mach inversion;
- normal/oblique shock conservation;
- Mach-angle and zero-turn limits;
- characteristic compatibility;
- homogeneous radiative slab;
- analytic cylinder/tube chords;
- optically thin and thick limits.

### 26.2 Property and metamorphic tests

Examples:

- SI scaling and unit identity;
- rigid-transform invariance;
- direction normalization;
- straight-limit equivalence for curved providers;
- richer-product to simpler-product equivalence;
- scalar versus batched evaluation;
- zero-loading/zero-reaction limit recovery;
- monotonic response to calibrated mixing/decay coefficients where physically
  expected.

### 26.3 Numerical convergence

Each discretized solver records the sequence of resolutions/tolerances and the
observed convergence of load-bearing quantities:

```text
MOC: cell length, boundary residual, zone extrema
ODE: endpoint, conserved fluxes, state profiles
ray tracer: pixel/ray/segment refinement
spectral model: wavelength and T-p table refinement
curved plume: arc-length and frame integration refinement
```

A single-resolution match is not sufficient evidence.

### 26.4 Provider conformance

Universal tests cover:

- lifecycle and closure;
- capability lookup and versioning;
- applicability and no-silent-extrapolation;
- provenance and termination retention;
- units and frames;
- batching semantics;
- cross-provider swap tests for signature and spatial consumers.

### 26.5 External validation

Calibration and validation datasets are separate. Every fixture records:

```text
source and citation
raw-data digest
transformation script/version
operating-condition identity
measurement uncertainty
calibration/validation role
model applicability
```

Validation reports distinguish governing-equation defects, closure error,
measurement uncertainty, and model discrepancy.

## 27. Scientific data, calibration, and uncertainty

### 27.1 Correlation and closure governance

Every non-governing relation is registered with:

```text
equation/closure ID
parameter names and units
bounds and transformations
source provenance
calibration dataset
validation dataset
applicability region
parameter covariance or uncertainty
model-discrepancy statement
```

No “default” coefficient may appear without a calibration identity.

### 27.2 Calibration objective

Use uncertainty-scaled residuals:

\[
r_i(\boldsymbol\theta)
=\frac{m_i(\boldsymbol\theta)-y_i}{\sigma_i},
\]

with robust objectives where justified. Record optimizer, bounds, priors if
used, Jacobian/SVD identifiability, covariance approximation, and held-out
validation performance.

### 27.3 Uncertainty propagation

At minimum propagate uncertain gas/nozzle inputs and calibrated closure
parameters to:

```text
first-cell length
cell count
shock-train endpoint
mixing endpoint
selected field values
spectral/angular intensity
band-integrated intensity
```

Provider results expose uncertainty only when supported by the registered
`uncertainty` capability; otherwise they state that uncertainty is unavailable.

## 28. Compatibility and migration

### 28.1 Additive migration

The initial provider framework and corrected solver are additive. Existing
public functions remain available as wrappers while new contracts stabilize.

### 28.2 Single implementation path

Legacy and provider APIs call the same corrected core. Duplicated physics paths
are prohibited.

### 28.3 Deprecation sequence

1. Introduce new exit-state and provider APIs.
2. Add compatibility tests and migration documentation.
3. Emit deprecation warnings only after an equivalent replacement is stable.
4. Retain serialized schema versioning and conversion tools.
5. Remove legacy APIs only in a planned breaking release.

### 28.4 Schema policy

- Stable enums serialize as strings.
- Arrays use documented artifact storage rather than enormous inline JSON.
- Every result contains schema version, provider identity, calibration identity,
  validity, termination, and provenance.
- Capability major versions change only when consumer-visible semantics break.

## 29. Coding-agent execution protocol

Each coding-agent assignment is one reviewable packet or PR.

### Before implementation

The agent must:

1. Read this master plan and the packet-specific documents.
2. Re-audit target source files when SHAs differ from the handoff baseline.
3. State the packet, files, equations, compatibility behavior, and non-goals.
4. Add or update failing tests before or with implementation.
5. Avoid unrelated formatting or refactoring.

### During implementation

- Preserve TODOs unless the task explicitly resolves them.
- Use Python 3.12+, full type annotations, NumPy typing, Pydantic v2 where
  configured, SciPy bracketed solvers where approved, pytest, ruff, and pyright.
- End scopes according to the repository `####` convention.
- Raise typed programmer/configuration errors; return structured physical domain
  results where specified.
- Record residuals and convergence diagnostics rather than logging and
  continuing with a questionable state.
- Do not add network-dependent tests.

### Completion report

Every PR report includes:

```text
packet and issue IDs
files changed
equations implemented or corrected
public API/schema changes
compatibility behavior
tests and commands run
numerical fixtures and residuals
convergence evidence where applicable
known limitations and out-of-scope regimes
updated documentation/registry entries
```

## 30. Release gates

### Gate R0 — Contract preview

Requires `M0` and `M1`:

- provider lifecycle and conformance stable;
- no physics behavior change;
- fake signature and spatial providers pass.

### Gate R1 — Corrected analytical foundation

Requires `M2` and `M3`:

- foundation equations/conservation pass;
- explicit gas/exit state;
- provider/direct equivalence;
- approximate geometry clearly labeled.

### Gate R2 — Validated analytical near field

Requires `M4` and `M5`:

- first-cell convergence/validation;
- finite shock train;
- physical termination and calibrated uncertainty.

### Gate R3 — Complete reduced-order spatial plume

Requires `M6` and `M7`:

- conservative handoff;
- straight entrainment/mixing field;
- mass, momentum, enthalpy, and species closure.

### Gate R4 — Gray resolved and unresolved radiometry

Requires `M8` and `M9`:

- analytic ray-transfer verification;
- directional spectral source from spatial fields;
- consumer swap tests.

### Gate R5 — Direct signature ecosystem

Requires `M10`:

- table provider;
- signature-only consumer proven without geometry.

### Gate R6 — Molecular signature beta

Requires `M11`:

- reproducible spectral assets;
- molecular images/signatures;
- independent spectral/plume validation;
- atmosphere/sensor layers separated.

### Gate R7 — Curved plume beta

Requires `M12`:

- approved curved physics;
- straight-limit and rigid-transform conformance;
- curved spatial and radiometric products through unchanged capabilities.

### Gate R8 — Advanced thermochemistry/particles research release

Requires `M13`:

- elemental and energy closure;
- frozen/equilibrium/finite-rate validation;
- molecular and particle limit recovery.

### Gate R9 — High-fidelity provider ecosystem

Requires `M14` and optionally `M15`:

- imported/general field conformance;
- execution-profile conformance for accelerated providers.

## 31. Critical risks and controls

| Risk | Consequence | Control and decision gate |
| --- | --- | --- |
| Provider abstraction overfits shock cells | Curved/CFD providers become awkward | Keep provider-specific inputs and capability-based outputs; fake-provider conformance at M1 |
| Planar geometry presented as axisymmetric physics | Misleading spatial validity | Explicit geometry/flow metadata; Phase 1 convergence and validation before `EXPOSED_VALIDATED` |
| Strong underexpansion or Mach disk forced through attached shocks | Invalid topology | Attached-shock/Mach-disk classifier and structured out-of-scope status |
| Overexpanded nozzle separation ignored | Invalid exit state | Require validated exit state or return separation-not-modeled validity |
| Cell count tuned without mixing physics | Nonphysical endpoint | Physical termination closures, separate calibration/validation, uncertainty |
| Curved provider merely bends a straight field | Broken momentum and transport | Dedicated vector integral equations and straight-limit validation |
| Radiation multiplied by projected area | Incorrect gas-plume signature | Volumetric RTE with analytic limiting tests |
| Spectral database/runtime coupling is unreproducible | Unrepeatable signatures | Offline versioned cross-section assets with digests |
| Atmosphere/sensor folded into source signature | Consumer lock-in and wrong units | Separate intrinsic source, propagation, and detector layers |
| Legacy and provider paths diverge | Contradictory results | One corrected core and regression equivalence tests |
| GPU execution leaks into semantics | Consumer-specific behavior | Explicit execution profile and semantic reference tests |
| Too many simultaneous coding-agent changes | Unreviewable failures | One packet/PR at a time and phase gates |

## 32. Parallel execution lanes

After `M1`, the work can be organized into four controlled lanes.

### Lane A — Critical physical model

```text
M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8 -> M9 -> M11 -> M13
```

### Lane B — Direct signature product

```text
M1 -> M10 -> consumer integration tests
```

This lane proves the minimal signature profile early.

### Lane C — Curved and imported providers

```text
M6/M7 -> M12
M1 + spatial contracts -> M14
```

Shared field and handoff contracts must be stable before implementation.

### Lane D — Validation, data, and governance

Runs throughout:

```text
reference data ingestion
analytic fixture maintenance
calibration/validation split
uncertainty work
provider conformance
performance baselines
release evidence
```

Lane D is never deferred to the end.

## 33. Immediate execution queue

The next coding-agent queue is:

```text
1. M0 architecture review and open-decision closure
2. M1 / PR I0 provider contract foundation
3. M2 / FND-A explicit gas and nozzle contracts
4. M2 / FND-B corrected nozzle equations and energy naming
5. M2 / FND-C shock branches and validity
6. M2 / FND-D geometry primitives and precursor correction
7. M2 / FND-E regime/results/compatibility
8. M2 / FND-F quality gate
9. M3 / PR I2 ShockCellAnalyticalProvider wrapper
10. M4 / MOC-A through MOC-F
```

`M10 SignatureTableProvider` may begin after `M1` in a separate branch because
it does not depend on corrected shock-cell physics.

## 34. Definition of program completion

The comprehensive program is complete when:

- signature and spatial consumers can swap providers without API changes;
- direct table, analytical straight, straight mixing, curved mixing, and
  imported-field providers pass shared conformance;
- the analytical near field is corrected, convergent, and validated within an
  explicit applicability domain;
- shock-cell and mixed-plume endpoints are physically distinguished;
- provider chaining preserves conserved fluxes and provenance;
- gray and molecular radiative transfer pass analytic and external validation;
- intrinsic source, atmospheric propagation, and detector response remain
  separate;
- thermochemistry and particles preserve elemental and energy closure where
  enabled;
- physical fidelity, morphology, radiation fidelity, validation, execution,
  and uncertainty are separately declared;
- no provider silently fabricates unsupported products or extrapolates outside
  its applicability;
- every release gate has reproducible evidence and installed-artifact tests.

## 35. Document ownership map

This master plan controls sequence and scope. Use the following documents for
implementation detail:

| Subject | Authoritative document |
| --- | --- |
| Unified provider/consumer architecture | `00_unified_plume_architecture.md` |
| Model assumptions and equations | `01_model_contract_and_architecture.md` |
| Foundation corrections | `02_foundation_corrections_plan.md` |
| First-cell MOC | `03_validated_first_cell_plan.md` |
| Shock train and termination | `04_shock_train_and_termination_plan.md` |
| Integral mixing | `05_integral_mixing_plume_plan.md` |
| Radiation | `06_spectral_ir_plan.md` |
| Chemistry and particles | `07_thermochemistry_and_particles_plan.md` |
| Verification and validation | `08_validation_and_test_matrix.md` |
| Issue definitions | `09_issue_backlog.md` |
| Agent behavior | `10_coding_agent_execution_protocol.md` |
| Source provenance | `12_reference_sources.md` |
| Settled decisions | `13_architecture_decision_records.md` |
| API and serialization | `14_api_contracts_and_serialization.md` |
| Provider interface | `15_plume_provider_interface.md` and `30_provider_contracts_v1.md` |
| Equation ownership | `16_equation_traceability_matrix.md` and `equation_registry.yaml` |
| Algorithms | `17_numerical_algorithms_and_pseudocode.md` |
| Calibration/data | `18_scientific_data_and_calibration_plan.md` |
| Uncertainty | `19_uncertainty_and_sensitivity_methods.md` |
| Phase 0/1 packets | `20_phase_0_patch_blueprint.md`, `21_phase_0_foundation_task_packets.md`, `22_phase_1_first_cell_task_packets.md` |
| Agent prompts/gates | `23_agent_prompts_and_gate_checklists.md`, `27_release_gates_and_definition_of_done.md` |
| Consumer queries and provider taxonomy | `28_consumer_profiles_and_query_contracts.md`, `29_provider_taxonomy_and_composition.md` |
| Cross-provider testing | `31_unified_conformance_and_testing.md` |
| Machine-readable master plan | `work_plan.yaml` |
