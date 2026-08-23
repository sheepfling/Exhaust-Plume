# Dependency-Ordered Issue Backlog

## 1. Use

Each item below is intended to become one focused issue and usually one pull
request. Do not combine unrelated physics, architecture, and formatting work.

Priority:

```text
P0 blocking correctness
P1 required model capability
P2 calibration or performance
P3 later fidelity
```

## 2. Phase 0 — Foundation corrections

## FND-001 — Introduce gas and nozzle contracts

**Priority:** P0  
**Depends on:** none

### Scope

Create:

```text
models/gas/contracts.py
models/nozzle/contracts.py
```

Implement frozen, validated contracts for:

```text
GasProperties
NozzleExitState
AmbientState
```

### Done when

- SI units and radians are documented.
- Gas constant and molecular weight consistency is checked.
- Species mass fractions normalize.
- Existing public APIs can construct the new contracts through wrappers.
- Tests cover invalid and valid data.

---

## FND-002 — Correct choked mass-flow and throat-area equations

**Priority:** P0  
**Depends on:** FND-001

### Scope

Correct:

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

Add a forward mass-flow helper and inversion tests.

### Files

```text
models/plume/motor_parameters.py
models/nozzle/area_mach.py
tests/
```

### Done when

- Forward and inverse functions agree.
- The exponent regression test fails on the old implementation and passes on
  the new implementation.
- Public compatibility is preserved.

---

## FND-003 — Remove hidden dry-air assumptions

**Priority:** P0  
**Depends on:** FND-001

### Scope

Route explicit gas properties through all generic nozzle/plume calculations.

### Done when

- No generic plume path imports dry-air molecular weight.
- Density, sound speed, and velocity change consistently with gas molecular
  weight.
- Atmosphere code may still use explicit dry-air properties.

---

## FND-004 — Correct energy and enthalpy properties

**Priority:** P0  
**Depends on:** FND-001, FND-003

### Scope

Add precise properties:

```text
specific_gas_work_Jpkg
specific_static_enthalpy_Jpkg
specific_total_enthalpy_Jpkg
specific_total_energy_Jpkg
```

Deprecate ambiguous behavior.

### Done when

\[
h_0=h+u^2/2=c_pT_0
\]

passes across the test grid.

---

## FND-005 — Replace oblique-shock angle special cases

**Priority:** P0  
**Depends on:** none

### Scope

Implement bounded weak/strong branch roots for the
\(\theta\)-\(\beta\)-\(M\) equation.

### Done when

- Weak zero-turn limit equals Mach angle.
- Strong zero-turn limit equals \(\pi/2\).
- Residual and root bracket are reported.
- Existing closed-form routine may remain only as a checked optimization or
  reference.

---

## FND-006 — Add maximum attached-turn detection

**Priority:** P0  
**Depends on:** FND-005

### Scope

Calculate \(\theta_{\max}(M,\gamma)\) and return
`DETACHED_SHOCK_REQUIRED` when exceeded.

### Done when

- Below-limit case succeeds.
- Above-limit case fails structurally.
- No nominal state is returned after failure.

---

## FND-007 — Add explicit expansion-regime classification

**Priority:** P0  
**Depends on:** FND-001

### Scope

Add:

```text
UNDEREXPANDED
MATCHED
OVEREXPANDED
```

using:

\[
r_p=(p_e-p_a)/p_a.
\]

### Done when

- \(p_e/p_a=1\) returns zero cells.
- Tolerance is configurable.
- `max_cells=0` is valid.
- Tests use target exit-pressure ratios.

---

## FND-008 — Add forward ray-intersection result

**Priority:** P0  
**Depends on:** none

### Scope

Replace point-only pseudoinverse intersections with a diagnostic ray result.

### Done when

- Forward parameters, residual, and condition number are returned.
- Parallel, ill-conditioned, and backward cases fail explicitly.
- Geometry callers migrate to the new API.

---

## FND-009 — Correct overexpanded precursor intersection

**Priority:** P0  
**Depends on:** FND-005, FND-008

### Scope

Use:

\[
\Delta x=R/\tan\beta
\]

with radians and forward-ray validation.

### Done when

- \(45^\circ\) analytic case passes.
- Current degree/cosine behavior is covered by a regression test.

---

## FND-010 — Separate transitions from closed zones

**Priority:** P0  
**Depends on:** FND-008

### Scope

Introduce:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

### Done when

- Public closed zones contain no `NaN`.
- Unclosed transitions cannot be meshed or ray traced.
- Existing consumers have a documented migration.

---

## FND-011 — Rename repeated plume passes to cells

**Priority:** P1  
**Depends on:** FND-007

### Scope

Migrate:

```text
num_plumes → max_cells
plume_index → cell_index
```

### Done when

- Deprecated aliases work with warnings.
- Supplying both forms fails clearly.
- New serialization uses cell terminology.

---

## FND-012 — Correct and expand branch regression tests

**Priority:** P0  
**Depends on:** FND-002 through FND-011 as applicable

### Scope

Add numeric anchors from `08_validation_and_test_matrix.md`.

### Done when

- The old sea-level “underexpanded” labeling is removed.
- Normal and oblique shock reference values pass.
- Matched/over/under regimes are separately tested.

---

## FND-013 — Establish Python 3.12 quality baseline

**Priority:** P1  
**Depends on:** all Phase 0 code tasks

### Scope

Update project configuration and CI for:

```text
Python 3.12+
pytest
ruff
pyright
build
```

### Done when

All quality commands pass in a clean environment and installed-wheel smoke
tests remain green.

## 3. Phase 1 — Validated first cell

## MOC-001 — Implement robust Prandtl-Meyer inverse

**Priority:** P1  
**Depends on:** Phase 0 gate

### Done when

- Monotonic bracketed inverse passes round-trip tests.
- Infinite-Mach angle limit is checked.
- Root diagnostics are exposed.

---

## MOC-002 — Add characteristic point and segment contracts

**Priority:** P1  
**Depends on:** MOC-001, FND-008

### Done when

- \(C^+\) and \(C^-\) invariants are explicit.
- Radians and SI units are enforced.
- Segments carry intersection diagnostics.

---

## MOC-003 — Implement planar characteristic interior point

**Priority:** P1  
**Depends on:** MOC-002

### Scope

Solve state compatibility and averaged-slope geometry at a \(C^+/C^-\)
intersection.

### Done when

- Invariants are conserved.
- Iteration converges on analytic/synthetic cases.
- Ill-conditioned geometry fails structurally.

---

## MOC-004 — Implement centerline compatibility

**Priority:** P1  
**Depends on:** MOC-003

### Scope

Apply \(\theta=0\) and incoming characteristic invariant.

### Done when

- Centerline angle residual passes.
- State reflection is physical, not only geometric.

---

## MOC-005 — Implement ambient-pressure free boundary

**Priority:** P1  
**Depends on:** MOC-003

### Scope

Solve:

```text
incoming characteristic invariant
p = p_ambient
boundary tangent = flow angle
```

### Done when

- Pressure and tangent residuals pass.
- No fitted parabola is required for the solved boundary.

---

## MOC-006 — Assemble mild underexpanded first cell

**Priority:** P1  
**Depends on:** MOC-004, MOC-005

### Done when

- One closed cell is produced.
- All zones are finite.
- Expansion and shock conservation checks pass.

---

## MOC-007 — Assemble mild attached overexpanded first cell

**Priority:** P1  
**Depends on:** MOC-005, FND-006, FND-009

### Done when

- Certified uniform exit required.
- Attached case succeeds.
- Detached and separation-risk cases fail with explicit status.

---

## MOC-008 — Add closed-zone topology validation

**Priority:** P1  
**Depends on:** MOC-006

### Done when

- Polygon area and orientation checked.
- Self-intersections rejected.
- Shared interfaces match within tolerance.

---

## MOC-009 — Add fan-resolution convergence study

**Priority:** P1  
**Depends on:** MOC-006, MOC-007

### Done when

Results for \(N,2N,4N\) report convergence of cell length, radius, pressure
extrema, and boundary residual.

---

## MOC-010 — Add fully expanded jet and spacing correlation

**Priority:** P1  
**Depends on:** FND-002, MOC-006

### Done when

- \(M_j,D_j,L_{s,\mathrm{corr}}\) are reported.
- Correlation mismatch is diagnostic, not forced.

## 4. Phase 2 — Finite shock train

## TRN-001 — Add shock-train calibration contract

**Priority:** P1  
**Depends on:** Phase 1 gate

### Done when

Every closure has provenance and applicability ranges.

---

## TRN-002 — Implement coherent-core diameter model

**Priority:** P1  
**Depends on:** TRN-001

### Scope

\[
D_c(x)=\max[D_j-2(\delta_{i,0}+S_ix),0].
\]

### Done when

Sensitivity to \(S_i\) is monotonic and tested.

---

## TRN-003 — Implement pressure-amplitude decay

**Priority:** P1  
**Depends on:** TRN-001, TRN-002

### Scope

\[
dA_p/dx=-C_dA_p/D_c.
\]

### Done when

Zero and positive decay limits pass.

---

## TRN-004 — Implement local cell-spacing continuation

**Priority:** P1  
**Depends on:** TRN-002, TRN-003

### Scope

\[
L_n=C_\lambda D_c\sqrt{M_{j,n}^2-1}\Phi_\delta.
\]

### Done when

Spacing is positive, finite, and carries calibration metadata.

---

## TRN-005 — Implement reduced-order downstream cell geometry

**Priority:** P1  
**Depends on:** TRN-004

### Done when

Scaled cells are labeled `SCALED_REDUCED_ORDER` and are not mislabeled as MOC.

---

## TRN-006 — Implement physical and safety termination

**Priority:** P1  
**Depends on:** TRN-003, TRN-004

### Done when

Core diameter, Mach, oscillation, persistence, topology, domain, and cell limits
are separate reasons.

---

## TRN-007 — Add shock-train result and diagnostics

**Priority:** P1  
**Depends on:** TRN-005, TRN-006

### Done when

Cell count is an output and termination metrics are serialized.

---

## TRN-008 — Add calibration sensitivity and uncertainty

**Priority:** P2  
**Depends on:** TRN-007

### Done when

At least deterministic sweeps of \(S_i,C_d,C_\lambda\) are available.

---

## TRN-009 — Calibrate and validate against separate datasets

**Priority:** P1  
**Depends on:** TRN-007

### Done when

Calibration cases and validation cases are explicitly disjoint.

## 5. Phase 3 — Integral mixing plume

## MIX-001 — Add conserved integral-state contracts

**Priority:** P1  
**Depends on:** Phase 2 gate

### Done when

Mass flow, momentum flux, total-enthalpy flow, and species mass flows are
represented directly.

---

## MIX-002 — Implement top-hat entrainment ODE

**Priority:** P1  
**Depends on:** MIX-001

### Done when

`solve_ivp` integration passes zero-entrainment and conservation tests.

---

## MIX-003 — Implement thermodynamic state recovery

**Priority:** P1  
**Depends on:** MIX-002

### Done when

Temperature, density, area, radius, and composition are recovered at every
valid state.

---

## MIX-004 — Implement mixing termination events

**Priority:** P1  
**Depends on:** MIX-002, MIX-003

### Done when

Velocity, temperature, composition, persistence, and domain termination are
distinct.

---

## MIX-005 — Reconstruct top-hat axisymmetric field

**Priority:** P1  
**Depends on:** MIX-003

### Done when

The field is finite and directly consumable by the gray-gas ray tracer.

---

## MIX-006 — Add flux-preserving Gaussian profiles

**Priority:** P2  
**Depends on:** MIX-005

### Done when

Integrated mass, momentum, enthalpy, and species match the integral state.

## 6. Phase 4 — Gray-gas radiation

## RAD-001 — Implement spectral units and Planck function

**Priority:** P1  
**Depends on:** Phase 3 gate

### Done when

Wavelength/wavenumber conversion preserves integrated radiance.

---

## RAD-002 — Implement axisymmetric ray geometry

**Priority:** P1  
**Depends on:** RAD-001, MIX-005

### Done when

Cylinder/sphere chord tests and rotational symmetry pass.

---

## RAD-003 — Implement exact gray-gas segment transport

**Priority:** P1  
**Depends on:** RAD-002

### Done when

Homogeneous slab and optical-depth limits pass.

---

## RAD-004 — Implement spectral image and area integration

**Priority:** P1  
**Depends on:** RAD-003

### Done when

Radiance images and radiant intensity have explicit units.

---

## RAD-005 — Implement angular signature sweep

**Priority:** P1  
**Depends on:** RAD-004

### Done when

Optically thin integrated orientation invariance passes.

---

## RAD-006 — Implement IR-domain termination

**Priority:** P1  
**Depends on:** RAD-004

### Done when

Incremental band contribution controls the radiation-domain end independently
of shock-cell termination.

## 7. Phase 5 — Molecular spectra, atmosphere, and sensor

## SPC-001 — Build reproducible cross-section generator

**Priority:** P1  
**Depends on:** RAD-003

### Done when

HITEMP/HAPI inputs and all metadata are versioned.

---

## SPC-002 — Implement cross-section table storage and interpolation

**Priority:** P1  
**Depends on:** SPC-001

### Done when

Grid-node and withheld-point errors pass.

---

## SPC-003 — Implement mixture absorption

**Priority:** P1  
**Depends on:** SPC-002

### Done when

\[
\alpha=\sum_sn_s\sigma_s
\]

passes mixture and column-density tests.

---

## SPC-004 — Integrate molecular transport into images

**Priority:** P1  
**Depends on:** SPC-003, RAD-004

### Done when

Narrow-window line-by-line benchmark agrees with reference.

---

## SPC-005 — Add atmospheric path model interface

**Priority:** P1  
**Depends on:** SPC-004

### Done when

Source radiance, path transmission, and path radiance remain separable.

---

## SPC-006 — Add detector response model

**Priority:** P1  
**Depends on:** SPC-005

### Done when

Output units identify power, photon rate, counts, or normalized response.

---

## SPC-007 — Validate against heated-plume IR data

**Priority:** P1  
**Depends on:** SPC-004

### Done when

Image and band metrics are compared with independent measurements.

## 8. Phase 6 — Thermochemistry and particles

## CHEM-001 — Add species and mixture contracts

**Priority:** P1  
**Depends on:** Phase 0 gas contracts

### Done when

Mass/mole conversion and elemental composition tests pass.

---

## CHEM-002 — Add CEA boundary-state adapter

**Priority:** P1  
**Depends on:** CHEM-001

### Done when

Raw provenance, units, composition, and elemental closure are preserved.

---

## CHEM-003 — Add thermally perfect mixture properties

**Priority:** P1  
**Depends on:** CHEM-001

### Done when

\(h(T)\), \(c_p(T)\), \(\gamma(T)\), and enthalpy inversion pass.

---

## CHEM-004 — Add frozen variable-property expansion/shock solve

**Priority:** P2  
**Depends on:** CHEM-003, Phase 1

### Done when

Mass, momentum, total enthalpy, entropy, and frozen composition checks pass.

---

## CHEM-005 — Add equilibrium reference path

**Priority:** P2  
**Depends on:** CHEM-003

### Done when

Trusted CEA/Cantera cases are reproduced.

---

## CHEM-006 — Add finite-rate integral afterburning

**Priority:** P2  
**Depends on:** MIX-002, CHEM-003

### Done when

Elemental and energy balances pass and disabling rates recovers frozen mixing.

---

## CHEM-007 — Add particle population and thermal model

**Priority:** P3  
**Depends on:** CHEM-006

### Done when

Particle/gas temperatures and drag/energy relaxation are explicit.

---

## CHEM-008 — Add particle absorption and scattering

**Priority:** P3  
**Depends on:** CHEM-007, SPC-004

### Done when

Zero-particle limit recovers molecular radiation and optical-property metadata
is versioned.

## 9. Phase 7 — Higher-fidelity flow

Create separate planning issues before implementation for:

```text
axisymmetric Euler/RANS continuation
Mach-disk topology
internal nozzle separation
flight coflow
vehicle/base flow
multiple engines
crossflow and curved plumes
non-LTE radiation
rarefied flow
```

These are not hidden extensions of the reduced-order solver.
