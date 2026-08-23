# Equation Traceability Matrix

## 1. Purpose

Every implemented equation shall have a stable project identifier linking:

```text
mathematical statement
classification
assumptions and validity domain
primary source
implementation symbol
verification test
validation evidence
```

Code docstrings, tests, result diagnostics, and calibration artifacts should
refer to these IDs. This prevents an algebraically similar but semantically
different equation from being substituted without review.

Machine-readable entries are in [`equation_registry.yaml`](equation_registry.yaml).

## 2. Classification

```text
GOVERNING   conservation law or thermodynamic relation under stated assumptions
DERIVED     algebraic consequence of governing equations
CORRELATION reduced-order relation with a documented applicability domain
CLOSURE     unresolved-physics relation containing calibrated parameters
NUMERICAL   numerical representation or acceptance criterion
```

A correlation or closure is never relabeled as a governing equation.

## 3. Source identifiers

| ID | Source family |
|---|---|
| SRC-COMP-001 | Anderson, *Modern Compressible Flow*, 3rd edition |
| SRC-NASA-GRC-001 | NASA Glenn compressible-flow and rocket mass-flow equations |
| SRC-SHOCKCELL-001 | Classical Prandtl/Pack circular shock-cell spacing literature |
| SRC-SHOCKCELL-002 | Finite shear-layer and shock-cell decay literature |
| SRC-NASA-JET-001 | NASA underexpanded-jet flow-structure validation data |
| SRC-RTE-001 | Standard non-scattering LTE radiative-transfer equation |
| SRC-HITRAN-001 | HITRAN definitions and units |
| SRC-HITEMP-001 | HITEMP high-temperature line lists |
| SRC-HAPI-001 | HAPI reference absorption/transmittance/radiance calculations |
| SRC-NASA-IR-001 | NASA heated-plume IR field/image validation data |
| SRC-NASA-CEA-001 | NASA Chemical Equilibrium with Applications |
| SRC-CANTERA-001 | Cantera thermodynamics, kinetics, and transport |

The full provenance, access, and fixture-ingestion requirements are in
[`12_reference_sources.md`](12_reference_sources.md).

## 4. Gas and nozzle equations

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| GAS-001 | Mixture molecular weight | DERIVED | `models/gas/mixtures.py::molecular_weight_from_mass_fractions` | `GAS-001-A/B/C` | Ideal-gas mixture; known species molecular weights |
| GAS-002 | Mixture specific gas constant | DERIVED | `models/gas/mixtures.py::specific_gas_constant` | `GAS-002-A/B` | \(R=R_u/\bar W\) |
| GAS-003 | Ideal-gas equation | GOVERNING | `models/gas/calorically_perfect.py::density_from_pressure_temperature` | `GAS-003-A/B` | Thermodynamic ideal gas |
| GAS-004 | Calorically perfect sound speed | DERIVED | `models/gas/calorically_perfect.py::speed_of_sound` | `GAS-004-A/B` | Constant \(\gamma\), equilibrium acoustic mode |
| ISO-001 | Stagnation/static temperature ratio | DERIVED | `models/gas/calorically_perfect.py` | `ISO-001-A/B/C` | Steady adiabatic calorically perfect flow |
| ISO-002 | Stagnation/static pressure ratio | DERIVED | same | `ISO-002-A/B/C` | Isentropic path |
| ISO-003 | Stagnation/static density ratio | DERIVED | same | `ISO-003-A/B/C` | Isentropic path |
| NOZ-001 | Area-Mach relation | DERIVED | `models/nozzle/area_mach.py::area_ratio` | `NOZ-001-A/B/C/D` | Quasi-1D, isentropic, calorically perfect |
| NOZ-002 | Compressible mass-flow function | DERIVED | `models/nozzle/mass_flow.py::mass_flux` | `NOZ-002-A/B/C` | Uniform section, same assumptions as NOZ-001 |
| NOZ-003 | Choked throat area | DERIVED | `models/nozzle/mass_flow.py::choked_area` | `NOZ-003-A/B/C` | Choked \(M=1\) throat |
| REG-001 | Exit pressure residual | NUMERICAL | `models/shock_cells/regime.py::classify_regime` | `REG-001-A/B/C/D` | Positive ambient pressure; explicit tolerance |

### GAS-001

\[
\boxed{
\bar W
=
\left(\sum_s\frac{Y_s}{W_s}\right)^{-1}
}
\]

### GAS-002 and GAS-003

\[
\boxed{R=\frac{R_u}{\bar W}},
\qquad
\boxed{p=\rho RT}.
\]

### NOZ-001

\[
\boxed{
\frac{A}{A^*}
=
\frac1M
\left[
\frac{2}{\gamma+1}
\left(1+\frac{\gamma-1}{2}M^2\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}
}
\]

### NOZ-003

\[
\boxed{
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{\frac{\gamma+1}{2(\gamma-1)}}
}
\]

Primary sources: `SRC-COMP-001`, `SRC-NASA-GRC-001`.

## 5. Expansion, characteristics, and shocks

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| PM-001 | Mach angle | DERIVED | `shock_cells/prandtl_meyer.py::mach_angle` | `PM-001-A/B` | \(M\ge1\) |
| PM-002 | Prandtl-Meyer function | DERIVED | `shock_cells/prandtl_meyer.py::prandtl_meyer` | `PM-002-A/B/C` | 2D/axisymmetric local simple wave, calorically perfect |
| PM-003 | Expansion turn | DERIVED | `shock_cells/prandtl_meyer.py::expansion_turn` | `PM-003-A/B` | Isentropic supersonic expansion |
| MOC-001 | Characteristic slopes | GOVERNING/DERIVED | `shock_cells/planar_characteristics.py` | `MOC-001-A/B/C` | Steady planar supersonic irrotational flow |
| MOC-002 | Planar compatibility invariants | GOVERNING/DERIVED | same | `MOC-002-A/B/C` | Same as MOC-001 |
| MOC-003 | Centerline symmetry | BOUNDARY | `shock_cells/first_cell.py` | `MOC-003-A/B` | Symmetric planar jet |
| MOC-004 | Free-boundary pressure | BOUNDARY | `shock_cells/free_boundary.py` | `MOC-004-A/B/C` | Quiescent constant-pressure ambient first model |
| MOC-005 | Free-boundary streamline slope | BOUNDARY | same | `MOC-005-A/B` | Inviscid material boundary |
| SHK-001 | Theta-beta-M relation | DERIVED | `shock_cells/oblique_shock.py::turn_from_wave_angle` | `SHK-001-A/B/C` | Attached planar oblique shock |
| SHK-002 | Upstream normal Mach | DERIVED | same | `SHK-002-A` | Oblique shock |
| SHK-003 | Static pressure ratio | DERIVED | `shock_cells/normal_shock.py` | `SHK-003-A/B` | Calorically perfect normal component |
| SHK-004 | Static density ratio | DERIVED | same | `SHK-004-A/B` | Same |
| SHK-005 | Downstream Mach | DERIVED | `shock_cells/oblique_shock.py` | `SHK-005-A/B` | Attached shock with \(\beta>\theta\) |
| SHK-006 | Stagnation pressure loss | DERIVED | `shock_cells/normal_shock.py::total_pressure_ratio` | `SHK-006-A/B/C` | Adiabatic calorically perfect shock |
| SHK-007 | Maximum attached turn | NUMERICAL | `shock_cells/oblique_shock.py::maximum_attached_turn` | `SHK-007-A/B/C` | \(M>1\), chosen \(\gamma\) |

### PM-002

\[
\boxed{
\nu(M)
=
\sqrt{\frac{\gamma+1}{\gamma-1}}
\tan^{-1}\sqrt{\frac{\gamma-1}{\gamma+1}(M^2-1)}
-
\tan^{-1}\sqrt{M^2-1}
}
\]

### MOC-001 and MOC-002

\[
\boxed{\frac{dy}{dx}=\tan(\theta\pm\mu)},
\]

\[
\boxed{\theta-\nu=\mathrm{const}\text{ on }C^+},
\qquad
\boxed{\theta+\nu=\mathrm{const}\text{ on }C^-}.
\]

The sign convention must be tested against the chosen coordinate orientation;
code shall not rely on a copied sign without a geometric test.

### SHK-001

\[
\boxed{
\tan\theta
=
2\cot\beta
\frac{M_1^2\sin^2\beta-1}
{M_1^2(\gamma+\cos2\beta)+2}
}
\]

Primary source: `SRC-COMP-001`.

## 6. Geometry and topology

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| GEO-001 | Forward ray intersection | NUMERICAL | `shock_cells/geometry.py::intersect_rays_2d` | `GEO-001-A..F` | Nondegenerate 2D rays |
| GEO-002 | Polygon signed area | NUMERICAL | `shock_cells/geometry.py::signed_polygon_area` | `GEO-002-A/B/C` | Ordered finite polygon |
| GEO-003 | Polygon self-intersection | NUMERICAL | `shock_cells/geometry.py::validate_simple_polygon` | `GEO-003-A/B/C` | Closed 2D polygon |
| GEO-004 | Precursor centerline intersection | DERIVED | `shock_cells/first_cell.py` | `GEO-004-A/B` | Straight shock line; \(0<\beta<\pi/2\) |

### GEO-001

\[
\mathbf o_1+s_1\mathbf d_1
=
\mathbf o_2+s_2\mathbf d_2,
\qquad
s_1,s_2\ge0.
\]

Acceptance requires bounded residual and condition number.

### GEO-004

\[
\boxed{\Delta x=\frac{R}{\tan\beta}}.
\]

## 7. Shock-cell scale and termination

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| CELL-001 | Fully expanded jet Mach | DERIVED | `shock_cells/correlations.py::fully_expanded_mach` | `CELL-001-A/B` | Isentropic equivalent state at \(p_a\) |
| CELL-002 | Fully expanded diameter | DERIVED | same | `CELL-002-A/B` | Equal mass flow and total state, circular sections |
| CELL-003 | Classical first-cell spacing | CORRELATION | `shock_cells/correlations.py::prandtl_cell_spacing` | `CELL-003-A/B/C` | Nearly adapted uniform circular jet |
| TRN-001 | Inward mixing-layer growth | CLOSURE | `shock_cells/train.py` | `TRN-001-A/B/C` | Calibrated reduced-order train |
| TRN-002 | Coherent-core diameter | DERIVED/CLOSURE | same | `TRN-002-A/B` | Top-hat core and two-sided inward layer |
| TRN-003 | Pressure-amplitude decay | CLOSURE | same | `TRN-003-A/B/C` | Calibrated positive decay coefficient |
| TRN-004 | Local cell spacing | CORRELATION/CLOSURE | same | `TRN-004-A/B/C` | Within calibration applicability |
| TRN-005 | Persistent termination | NUMERICAL | `shock_cells/termination.py` | `TRN-005-A..E` | Ordered completed-cell metrics |

### CELL-003

\[
\boxed{
L_{s,0}=1.306D_j\sqrt{M_j^2-1}
}
\]

Source: `SRC-SHOCKCELL-001`. Correlation mismatch is diagnostic; it is not
forced into MOC geometry.

### TRN-001 through TRN-003

\[
\delta_i(x)=\delta_{i,0}+S_ix,
\]

\[
D_c(x)=\max[D_j-2\delta_i(x),0],
\]

\[
\boxed{
\frac{dA_p}{dx}=-\frac{C_d}{D_c(x)}A_p
}.
\]

Parameters \(S_i\) and \(C_d\) require a calibration artifact.

## 8. Integral mixing plume

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| MIX-001 | Entrainment mass rate | CLOSURE | `mixing/entrainment.py` | `MIX-001-A/B/C` | Axisymmetric top-hat integral plume |
| MIX-002 | Axial momentum flux | GOVERNING | `mixing/integral_plume.py` | `MIX-002-A/B/C` | Steady integral control volume |
| MIX-003 | Total enthalpy-flow balance | GOVERNING | same | `MIX-003-A/B/C` | Defined source/sink terms |
| MIX-004 | Species mass-flow balance | GOVERNING | same | `MIX-004-A/B/C` | Frozen or explicit reaction source |
| MIX-005 | Cross-section area recovery | DERIVED | same | `MIX-005-A/B` | Positive \(\rho,u,\dot m\) |

### MIX-001

\[
\boxed{
\frac{d\dot m}{dx}
=
2\pi R\rho_aE|u-u_a|
}
\]

The entrainment coefficient \(E\) is a closure with provenance.

### MIX-002 through MIX-004

\[
\frac{d}{dx}\left[\dot m u+(p-p_a)A\right]=0,
\]

\[
\frac{d}{dx}(\dot m h_0)
=
h_{0a}\frac{d\dot m}{dx}
+\dot Q'_{\mathrm{chem}}-\dot Q'_{\mathrm{rad}},
\]

\[
\frac{d}{dx}(\dot mY_s)
=
Y_{s,a}\frac{d\dot m}{dx}+\dot\omega_sA.
\]

## 9. Radiation

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| RAD-001 | Planck radiance in wavenumber | GOVERNING/DERIVED | `radiation/planck.py` | `RAD-001-A/B/C/D` | Thermal equilibrium radiation |
| RAD-002 | Non-scattering LTE RTE | GOVERNING | `radiation/radiative_transfer.py` | `RAD-002-A/B` | LTE, absorption/emission, no scattering |
| RAD-003 | Exact uniform-segment transport | DERIVED | same | `RAD-003-A..E` | Constant properties over segment |
| RAD-004 | Mixture absorption coefficient | DERIVED | `radiation/spectroscopy.py` | `RAD-004-A/B/C` | Independent species line absorption |
| RAD-005 | Species number density | DERIVED | same | `RAD-005-A/B` | Ideal gas |
| RAD-006 | Image-to-radiant-intensity integral | DEFINITION | `radiation/radiative_transfer.py` | `RAD-006-A/B/C` | Complete projected source image |
| RAD-007 | Vacuum inverse-square irradiance | DEFINITION/DERIVED | `radiation/sensor.py` | `RAD-007-A/B` | Far field, unresolved source |
| RAD-008 | Spectral-density Jacobian | DERIVED | `radiation/contracts.py` | `RAD-008-A/B/C` | Monotonic wavelength/wavenumber transform |
| RAD-009 | IR-domain contribution cutoff | NUMERICAL | `radiation/radiative_transfer.py` | `RAD-009-A/B/C` | Ordered axial contribution slices |

### RAD-001

For \(\tilde\nu=1/\lambda\) in \(\mathrm{m^{-1}}\),

\[
\boxed{
B_{\tilde\nu}(T)
=
\frac{2hc^2\tilde\nu^3}
{\exp(hc\tilde\nu/k_BT)-1}
}
\]

with spectral density per \(\mathrm{m^{-1}}\).

### RAD-002 and RAD-003

\[
\boxed{
\frac{dI_{\tilde\nu}}{ds}
=-\alpha_{\tilde\nu}I_{\tilde\nu}
+\alpha_{\tilde\nu}B_{\tilde\nu}(T)
}
\]

\[
\boxed{
I_{i+1}
=I_i e^{-\Delta\tau_i}
+B_i(1-e^{-\Delta\tau_i}),
\qquad
\Delta\tau_i=\alpha_i\Delta s_i
}
\]

### RAD-004 and RAD-005

\[
\alpha_{\tilde\nu}
=
\sum_s n_s\sigma_s(\tilde\nu,T,p),
\qquad
n_s=X_s\frac{p}{k_BT}.
\]

Sources: `SRC-HITRAN-001`, `SRC-HITEMP-001`, `SRC-HAPI-001`.

## 10. Thermochemistry and particles

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| CHEM-001 | Mass/mole fraction conversion | DERIVED | `chemistry/contracts.py` | `CHEM-001-A/B/C` | Defined species molecular weights |
| CHEM-002 | Gibbs minimization equilibrium | GOVERNING/DEFINITION | external CEA/validated adapter | `CHEM-002-A/B/C` | Equilibrium at selected constraints |
| CHEM-003 | Finite-rate species source | GOVERNING/MODEL | `chemistry/finite_rate.py` | `CHEM-003-A/B/C` | Selected mechanism and rate laws |
| CHEM-004 | Chemical energy source | DERIVED | same | `CHEM-004-A/B` | Consistent species enthalpies |
| PART-001 | Particle energy balance | GOVERNING/CLOSURE | `chemistry/particles.py` | `PART-001-A/B/C` | Lumped particle temperature |
| PART-002 | Particle spectral extinction | MODEL | `radiation/particles.py` | `PART-002-A/B/C` | Chosen optical model and size distribution |

### CHEM-002

\[
\min_{n_s\ge0}\sum_s n_s\mu_s
\quad\text{subject to}\quad
\sum_s a_{ks}n_s=b_k.
\]

### CHEM-003

\[
\dot\omega_s
=W_s\sum_r(\nu''_{sr}-\nu'_{sr})q_r.
\]

Sources: `SRC-NASA-CEA-001`, `SRC-CANTERA-001`.

## 11. Traceability rules for code

Every implementation function for a registered equation shall include:

```text
Equation IDs
assumptions
input/output units
branch or root selection
failure modes
primary source ID
```

Example docstring fragment:

```python
def calc_choked_area(...) -> float:
  """Calculate sonic throat area.

  Equations:
    NOZ-002, NOZ-003.
  Assumptions:
    Quasi-one-dimensional, isentropic, calorically perfect ideal gas.
  Units:
    SI.
  Sources:
    SRC-COMP-001, SRC-NASA-GRC-001.
  """
  ...
####
```

Tests shall include the equation ID in the test docstring or parameter-case ID.

## 12. Change-control rule

Changing a registered equation requires all of:

1. Update the equation registry.
2. Add or supersede an ADR when semantics change.
3. Update source provenance.
4. Update analytic verification cases.
5. Re-run dependent conservation and validation cases.
6. Record expected regression changes.
7. Increment the affected model or calibration version.

A numerical refactor that preserves the equation may retain the same equation
ID but must demonstrate equivalence within tolerance.
