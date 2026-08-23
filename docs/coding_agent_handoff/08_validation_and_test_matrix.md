# Validation and Test Matrix

## 1. Purpose

Define what must be tested, what constitutes verification versus validation,
and which numerical values serve as branch regression anchors.

A test passing does not imply the model is valid outside the test's assumptions.

## 2. Evidence hierarchy

### Level V0: Input and unit verification

Checks types, units, ranges, and conversions.

### Level V1: Algebraic unit tests

Checks one equation in isolation against analytic values.

### Level V2: Conservation verification

Checks mass, momentum, energy, entropy, and species balances.

### Level V3: Numerical solution verification

Checks convergence, residuals, conditioning, and discretization sensitivity.

### Level V4: Model validation

Compares calculated observables to independent experiment or trusted
higher-fidelity calculation.

### Level V5: Uncertainty characterization

Propagates input, calibration, and numerical uncertainty into final outputs.

No phase may claim V4 validation when it only has V1-V3 tests.

## 3. Common normalized residuals

Pressure:

\[
r_p=\frac{p_{\mathrm{calc}}-p_{\mathrm{ref}}}
{\max(|p_{\mathrm{ref}}|,p_{\mathrm{floor}})}.
\]

Temperature:

\[
r_T=\frac{T_{\mathrm{calc}}-T_{\mathrm{ref}}}
{\max(|T_{\mathrm{ref}}|,T_{\mathrm{floor}})}.
\]

Mass flux across a shock:

\[
r_m
=
\frac{
\rho_1u_{n1}-\rho_2u_{n2}
}{
\max(
|\rho_1u_{n1}|,
|\rho_2u_{n2}|,
m_{\mathrm{floor}}
)
}.
\]

Normal momentum:

\[
r_\Pi
=
\frac{
p_1+\rho_1u_{n1}^2
-
p_2-\rho_2u_{n2}^2
}{
\max(
|p_1+\rho_1u_{n1}^2|,
|p_2+\rho_2u_{n2}^2|
)
}.
\]

Total enthalpy:

\[
r_h
=
\frac{
h_{01}-h_{02}
}{
\max(|h_{01}|,|h_{02}|,h_{\mathrm{floor}})
}.
\]

Geometry intersection:

\[
r_x
=
\frac{
\left\|
\mathbf o_1+s_1\mathbf d_1
-
\mathbf o_2-s_2\mathbf d_2
\right\|
}{
D_e
}.
\]

## 4. Foundation test cases

| ID | Test | Inputs | Expected |
|---|---|---|---|
| GAS-001 | Ideal-gas density | chosen \(p,T,R\) | \(\rho=p/(RT)\) |
| GAS-002 | Mixture molecular weight | binary mixture | both formulas agree |
| GAS-003 | Sound speed | chosen \(T,R,\gamma\) | \(a=\sqrt{\gamma RT}\) |
| ISO-001 | Static/total round trip | grid of \(M,\gamma\) | original state recovered |
| NOZ-001 | Area-Mach inversion | \(A/A^*,\gamma\) | selected branch recovered |
| NOZ-002 | Choked mass-flow inversion | \(A^*,p_0,T_0,R,\gamma\) | forward/inverse agree |
| REG-001 | Overexpanded classifier | \(p_e/p_a=0.90\) | OVEREXPANDED |
| REG-002 | Matched classifier | \(p_e/p_a=1.00\) | MATCHED, zero cells |
| REG-003 | Underexpanded classifier | \(p_e/p_a=1.10\) | UNDEREXPANDED |
| GEO-001 | Perpendicular ray intersection | analytic rays | exact point, positive parameters |
| GEO-002 | Parallel rays | parallel directions | structured failure |
| GEO-003 | Backward intersection | lines cross behind origin | structured failure |

## 5. Normal-shock benchmark

Use:

\[
M_1=2.0,
\qquad
\gamma=1.4.
\]

Expected:

\[
\boxed{
\frac{p_2}{p_1}=4.5
}
\]

\[
\boxed{
\frac{\rho_2}{\rho_1}=2.6666666667
}
\]

\[
\boxed{
\frac{T_2}{T_1}=1.6875
}
\]

\[
\boxed{
M_2=0.5773502692
}
\]

\[
\boxed{
\frac{p_{02}}{p_{01}}\approx0.7208738615.
}
\]

Verify mass, momentum, total enthalpy, and entropy sign.

## 6. Oblique-shock benchmark

Use:

\[
M_1=2.0,
\qquad
\gamma=1.4,
\qquad
\theta=10^\circ.
\]

Weak solution:

\[
\boxed{
\beta_{\mathrm{weak}}
\approx39.313931845^\circ
}
\]

Strong solution:

\[
\boxed{
\beta_{\mathrm{strong}}
\approx83.700080376^\circ.
}
\]

For the weak solution:

\[
M_{n1}\approx1.267138036,
\]

\[
\frac{p_2}{p_1}\approx1.706578604,
\]

\[
\frac{\rho_2}{\rho_1}\approx1.458425613,
\]

\[
\frac{T_2}{T_1}\approx1.170151284,
\]

\[
M_2\approx1.640522229,
\]

\[
\frac{p_{02}}{p_{01}}\approx0.984644023.
\]

Also verify:

\[
\theta\to0
\Rightarrow
\beta_{\mathrm{weak}}\to\sin^{-1}(1/M).
\]

## 7. Current-branch regression anchor

Use:

\[
M_e=4.13,
\qquad
\gamma=1.33,
\qquad
p_0=69\ \mathrm{atm},
\qquad
T_0=2000\ \mathrm K.
\]

Expected isentropic exit values:

\[
1+\frac{\gamma-1}{2}M_e^2
=
3.8143885,
\]

\[
\frac{p_0}{p_e}
=
220.454330636,
\]

\[
p_e
=
0.312989996\ \mathrm{atm},
\]

\[
T_e
=
524.330440\ \mathrm K.
\]

Consequences:

```text
at sea level: overexpanded
at branch 10 km atmosphere (~26436.27 Pa): mildly underexpanded
```

Any test named “underexpanded” at sea level with this total state is mislabeled.

## 8. Prandtl-Meyer tests

| ID | Test | Expected |
|---|---|---|
| PM-001 | \(\nu(M)\) monotonic for \(M>1\) | strictly increasing |
| PM-002 | inverse round trip | \(M\) recovered |
| PM-003 | turn sign | expansion increases \(M\), lowers \(p,T,\rho\) |
| PM-004 | stagnation invariance | \(p_0,T_0\) constant |
| PM-005 | infinite-Mach bound | requested \(\nu\) above limit fails |

## 9. First-cell solution verification

### MOC-001: Matched flow

Expected:

```text
zero cells
NO_PRESSURE_MISMATCH
no shock or expansion segments
```

### MOC-002: Mild underexpansion

Use a target exit-pressure ratio such as:

\[
p_e/p_a=1.10.
\]

Check:

```text
finite characteristic network
boundary pressure equals ambient
centerline theta equals zero
closed positive-area zones
no backward intersections
```

### MOC-003: Mild overexpansion

Use:

\[
p_e/p_a=0.90
\]

and a validated uniform exit state. Check attached weak shock and conservation.

### MOC-004: Detached case

Select \(M,\theta\) above \(\theta_{\max}\). Expected:

```text
DETACHED_SHOCK_REQUIRED
no nominal success geometry
```

### MOC-005: Fan-resolution convergence

Run:

```text
N
2N
4N
```

Track:

```text
cell length
maximum radius
centerline pressure extrema
boundary pressure residual
```

Require decreasing changes.

## 10. First-cell scale correlation

For the branch 10 km illustrative state:

\[
p_a\approx26436.2673\ \mathrm{Pa}.
\]

Expected fully expanded values:

\[
M_j\approx4.257327980,
\]

\[
A_j/A_e\approx1.137766918,
\]

\[
D_j\approx2.133323152\ \mathrm m
\]

for \(D_e=2\ \mathrm m\).

Classical spacing anchor:

\[
L_{s,\mathrm{corr}}
\approx11.52956984\ \mathrm m.
\]

The solver is not required to equal the correlation, but the normalized
difference must be reported and investigated.

## 11. Shock-train tests

| ID | Change | Expected response |
|---|---|---|
| TRN-001 | \(S_i=0\) | no geometric core shrinkage |
| TRN-002 | increase \(S_i\) | shorter core and fewer cells |
| TRN-003 | \(C_d=0\) | no amplitude decay from closure |
| TRN-004 | increase \(C_d\) | fewer coherent cells |
| TRN-005 | increase `max_cells` only | physical result unchanged unless previously truncated |
| TRN-006 | hit `max_cells` | MAX_CELL_LIMIT, truncated |
| TRN-007 | hit axial domain | DOMAIN_LIMIT, truncated |
| TRN-008 | weak amplitude for one cell | no stop unless persistence satisfied |
| TRN-009 | \(p_e/p_a\to1\) | zero or vanishing shock train |

## 12. Integral-plume tests

### MIX-001: Zero entrainment

Set \(E=0\). Expected constant:

```text
mass flow
velocity
temperature
radius
species
```

### MIX-002: Frozen entrainment

Verify:

\[
\frac{d(\dot mY_s)}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}.
\]

### MIX-003: Momentum conservation

For pressure-matched, force-free flow:

\[
\Pi(x)=\Pi_0.
\]

### MIX-004: Enthalpy balance

\[
\dot H_0(x)
=
\dot H_{0,0}
+
\int h_{0a}\,d\dot m.
\]

### MIX-005: Equilibrium event

Verify velocity, temperature, and composition tolerances plus persistence.

## 13. Radiation analytic tests

### RAD-001: Homogeneous slab

\[
I_{\mathrm{out}}
=
I_0e^{-\alpha L}
+
B(T)(1-e^{-\alpha L}).
\]

Require direct agreement.

### RAD-002: Zero opacity

\[
\alpha=0
\Rightarrow
I_{\mathrm{out}}=I_0.
\]

### RAD-003: Optically thin

For \(\tau\ll1\):

\[
I_{\mathrm{out}}-I_0
\approx
[B(T)-I_0]\tau.
\]

### RAD-004: Optically thick

\[
\tau\gg1
\Rightarrow
I_{\mathrm{out}}\to B(T).
\]

### RAD-005: Layer ordering

Hot-behind-cold differs from cold-behind-hot.

### RAD-006: Cylinder chord

For cylinder radius \(R\) and impact parameter \(b\):

\[
L=2\sqrt{R^2-b^2}.
\]

### RAD-007: Optically thin angular invariance

Integrated radiant intensity of a fully visible axisymmetric test volume is
nearly independent of angle.

### RAD-008: Spectral-coordinate conversion

Integrated radiance is preserved between wavelength and wavenumber
representations.

## 14. Spectroscopy tests

| ID | Test | Expected |
|---|---|---|
| SPC-001 | cross-section table at grid node | matches generator |
| SPC-002 | withheld \(T,p\) interpolation | bounded error |
| SPC-003 | mixture opacity | species sum |
| SPC-004 | column-density scaling | linear optical depth |
| SPC-005 | table metadata | version and line-shape reproducible |
| SPC-006 | narrow-window line-by-line case | agrees with HAPI reference |

## 15. Chemistry tests

| ID | Test | Expected |
|---|---|---|
| CHM-001 | \(X\leftrightarrow Y\) round trip | original composition |
| CHM-002 | elemental closure | conserved |
| CHM-003 | enthalpy inversion | original \(T\) |
| CHM-004 | frozen shock | unchanged species |
| CHM-005 | equilibrium reference | matches CEA/Cantera |
| CHM-006 | disabled kinetics | frozen behavior |
| CHM-007 | finite-rate element sources | sum to zero |
| CHM-008 | no particles | molecular radiation recovered |

## 16. External validation families

Use independent cases with archived raw inputs and processed comparison data.

### Flow structure

- Underexpanded supersonic round-jet schlieren or PLIF cases.
- Cases reporting exit Mach, pressure ratio, geometry, and centerline pressure.
- Separate calibration and validation subsets.

### First-cell and Mach-disk geometry

- Datasets reporting cell wavelength, maximum jet diameter, Mach-disk
  location, and Mach-disk diameter.
- Mach-disk data may initially validate an out-of-scope classifier rather than
  the attached-cell solver.

### Infrared plume

- Axisymmetric heated-plume cases with measured temperature/pressure fields and
  infrared images.
- Use these before a reacting rocket plume.

### Thermochemistry

- Published CEA example problems.
- Cantera equilibrium and homogeneous-reactor references.
- Propellant-specific data only after generic verification.

## 17. Regression artifact policy

Store regression values with:

```text
case_id
input schema version
solver version
model level
calibration id
expected values
tolerances
source provenance
```

Do not update expected values merely because an implementation changed.
Document the physical or mathematical reason.

## 18. Quality commands

```bash
python -m pytest
python -m pytest --maxfail=1 -q
python -m ruff check .
python -m pyright
python -m build
```

Recommended later additions:

```text
coverage report
property-based tests
benchmark timing
wheel-installed smoke tests
```

## 19. Phase-exit rule

A phase exits only when:

1. Its analytic verification cases pass.
2. Its conservation residuals pass.
3. Its discretization sensitivity is documented.
4. Its validity range is encoded.
5. Its failure states are tested.
6. Its calibration and validation data are distinct where empirical closures
   exist.
