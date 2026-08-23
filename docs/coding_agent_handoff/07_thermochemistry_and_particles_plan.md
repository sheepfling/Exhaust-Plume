# Thermochemistry and Particle-Radiation Plan

## 1. Purpose

Replace the constant-\(\gamma\), dry-air-like approximation with staged
rocket-exhaust composition, thermodynamics, reactions, and particles.

This work begins only after gas dynamics, mixing, and molecular radiative
transfer pass their own verification gates.

## 2. Fidelity stages

### CHEM-0: Explicit frozen mixture

- User-supplied species.
- Explicit molecular weights.
- Constant or tabulated \(c_p(T)\).
- No reactions.

### CHEM-1: CEA boundary-state import

- Chamber/nozzle composition from an external CEA run.
- Frozen or equilibrium nozzle expansion metadata.
- No CEA invocation in the base solver.

### CHEM-2: Thermally perfect frozen flow

- \(h(T,\mathbf Y)\), \(c_p(T,\mathbf Y)\), \(R(\mathbf Y)\).
- Variable \(\gamma(T,\mathbf Y)\).
- Frozen species through shocks and expansions.

### CHEM-3: Equilibrium mixing model

- Equilibrium composition at selected \(p,h,\) and elemental abundance.
- Useful as a limiting model.

### CHEM-4: Finite-rate afterburning

- Reaction kinetics.
- Ambient oxygen entrainment.
- Chemical heat release.
- Species-dependent transport.

### CHEM-5: Soot and condensed particles

- Particle mass and size distributions.
- Particle temperature.
- Absorption, emission, and scattering.

## 3. Composition conversions

For mole fractions \(X_s\), mass fractions \(Y_s\), and molecular weights
\(W_s\):

\[
\boxed{
\overline W
=
\sum_sX_sW_s
=
\left(
\sum_s\frac{Y_s}{W_s}
\right)^{-1}.
}
\]

Convert mole to mass fraction:

\[
\boxed{
Y_s=\frac{X_sW_s}{\overline W}.
}
\]

Convert mass to mole fraction:

\[
\boxed{
X_s=\frac{Y_s/W_s}
{\sum_jY_j/W_j}.
}
\]

Mixture gas constant:

\[
\boxed{
R=\frac{R_u}{\overline W}.
}
\]

All conversions require normalization and nonnegative composition.

## 4. Thermally perfect mixture

For species enthalpy \(h_s(T)\):

\[
\boxed{
h(T,\mathbf Y)=\sum_sY_sh_s(T).
}
\]

Mixture heat capacity:

\[
\boxed{
c_p(T,\mathbf Y)
=
\sum_sY_sc_{p,s}(T).
}
\]

Then:

\[
\boxed{
c_v=c_p-R,
\qquad
\gamma=\frac{c_p}{c_v}.
}
\]

For a variable-\(c_p\) state, temperature is recovered by solving:

\[
h(T,\mathbf Y)-h_{\mathrm{target}}=0.
\]

Use a bounded scalar root solver with a documented valid temperature range.

## 5. Frozen expansions and shocks

Frozen means:

\[
\boxed{
\frac{DY_s}{Dt}=0.
}
\]

The simple constant-\(\gamma\) formulas are no longer exact when \(c_p\) varies
strongly. The thermally perfect extension should conserve:

### Expansion

\[
h_0=h+\frac{u^2}{2}
\]

and entropy for an isentropic expansion:

\[
s_2=s_1.
\]

### Adiabatic shock

Mass:

\[
\boxed{
\rho_1u_{n1}=\rho_2u_{n2}.
}
\]

Normal momentum:

\[
\boxed{
p_1+\rho_1u_{n1}^2
=
p_2+\rho_2u_{n2}^2.
}
\]

Total enthalpy:

\[
\boxed{
h_1+\frac{u_1^2}{2}
=
h_2+\frac{u_2^2}{2}.
}
\]

Tangential velocity is unchanged for an inviscid oblique shock.

Implement the variable-property shock as a nonlinear conservation solve after
the constant-\(\gamma\) model is stable.

## 6. CEA boundary-state adapter

Treat CEA as a boundary-condition generator.

### Input metadata

```text
propellant names
oxidizer/fuel ratio
chamber pressure
chamber temperature or enthalpy assumptions
nozzle area ratio
equilibrium/frozen expansion option
CEA version
thermodynamic database version
```

### Imported outputs

```text
exit pressure
exit temperature
exit Mach
exit velocity
mass flow or characteristic velocity data
species mole fractions
species mass fractions
molecular weight
cp
gamma
enthalpy
entropy
```

### Adapter requirements

- Parse versioned machine-readable output.
- Preserve all original CEA metadata.
- Validate mass-fraction and elemental closure.
- Convert units explicitly.
- Store the raw CEA result as provenance.
- Do not silently collapse trace species required by the selected spectral
  windows.

## 7. Chemical equilibrium

At fixed temperature and pressure, equilibrium minimizes Gibbs free energy:

\[
\boxed{
\min_{\{n_s\ge0\}}
G
=
\sum_sn_s\mu_s.
}
\]

Subject to elemental conservation:

\[
\boxed{
\sum_sa_{ks}n_s=b_k
\quad
\text{for each element }k.
}
\]

For ideal-gas species:

\[
\boxed{
\mu_s
=
\mu_s^\circ(T)
+
R_uT
\ln
\left(
\frac{X_sp}{p^\circ}
\right).
}
\]

In an adiabatic mixing problem, temperature must also satisfy the total
enthalpy constraint.

The project should initially use a trusted equilibrium library rather than
implementing a new Gibbs minimizer.

## 8. Finite-rate chemistry

Species equation:

\[
\boxed{
\frac{\partial(\rho Y_s)}{\partial t}
+
\nabla\cdot(\rho\mathbf uY_s)
=
\nabla\cdot(\rho D_s\nabla Y_s)
+
\dot\omega_s.
}
\]

For reaction \(r\):

\[
\sum_s\nu'_{sr}\mathcal S_s
\rightleftharpoons
\sum_s\nu''_{sr}\mathcal S_s.
\]

Forward Arrhenius rate:

\[
\boxed{
k_{f,r}
=
A_rT^{b_r}
\exp
\left(
-\frac{E_{a,r}}{R_uT}
\right).
}
\]

Progress rate:

\[
\boxed{
q_r
=
k_{f,r}
\prod_jC_j^{\nu'_{jr}}
-
k_{r,r}
\prod_jC_j^{\nu''_{jr}}.
}
\]

Species source:

\[
\boxed{
\dot\omega_s
=
W_s
\sum_r
(\nu''_{sr}-\nu'_{sr})q_r.
}
\]

Chemical heat release:

\[
\boxed{
\dot q_{\mathrm{chem}}
=
-\sum_sh_s(T)\dot\omega_s.
}
\]

Use Cantera or an equivalent validated kinetics library. Do not hand-code a
reaction mechanism inside the plume solver.

## 9. Frozen/equilibrium/finite-rate classifier

Define flow time:

\[
\boxed{
\tau_{\mathrm{flow}}=\frac{L}{u}.
}
\]

Define a selected chemical time \(\tau_{\mathrm{chem}}\). Then:

\[
\boxed{
Da=\frac{\tau_{\mathrm{flow}}}{\tau_{\mathrm{chem}}}.
}
\]

Interpretation:

```text
Da << 1  approximately frozen
Da >> 1  approximately equilibrium-limited
Da ~ 1   finite-rate model needed
```

This is a diagnostic, not an automatic guarantee.

## 10. Coupling finite-rate chemistry to the integral plume

Extend the species equation:

\[
\boxed{
\frac{d(\dot mY_s)}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}
+
\dot\omega_sA.
}
\]

Here \(\dot\omega_s\) is the standard volumetric species mass-production rate
with units \(\mathrm{kg\,m^{-3}\,s^{-1}}\). Multiplication by cross-sectional
area gives the required source per unit axial length. Do not divide by velocity
unless the chemistry interface instead supplies a material derivative such as
\(dY_s/dt\); that alternative convention must have a different typed contract.

Extend total enthalpy consistently. If species sensible and formation
enthalpies are included in \(h(T,\mathbf Y)\), chemical energy should not be
double-counted as an additional arbitrary heat source. Choose one consistent
energy formulation and document it.

## 11. Particle state

For particle class \(k\):

```text
material
diameter_m
number_density_per_m3
mass_fraction
temperature_K
velocity_mps
complex_refractive_index_model
```

### Particle momentum

A reduced model may use drag relaxation:

\[
m_p\frac{du_p}{dt}
=
\frac12
C_D\rho_gA_p
|u_g-u_p|(u_g-u_p).
\]

### Particle energy

\[
\boxed{
m_pc_{p,p}\frac{dT_p}{dt}
=
h_cA_p(T_g-T_p)
-
\epsilon_p\sigma A_p
(T_p^4-T_{\mathrm{rad}}^4)
+
\dot q_{p,\mathrm{chem}}.
}
\]

Particle temperature need not equal gas temperature.

## 12. Particle optical properties

For particle size distribution \(N(d_p)\):

\[
\boxed{
\alpha_{\lambda,\mathrm{part}}
=
\int
N(d_p)
C_{\mathrm{abs}}(\lambda,d_p,m_\lambda)
\,dd_p.
}
\]

Scattering coefficient:

\[
\boxed{
\sigma_{\lambda,\mathrm{sca}}
=
\int
N(d_p)
C_{\mathrm{sca}}(\lambda,d_p,m_\lambda)
\,dd_p.
}
\]

Extinction:

\[
\boxed{
\beta_{\lambda,\mathrm{ext}}
=
\alpha_{\lambda,\mathrm{part}}
+
\sigma_{\lambda,\mathrm{sca}}.
}
\]

The no-scattering molecular RTE is no longer sufficient once particle
scattering matters. Add the scattering source only in a separate solver level.

## 13. Data contracts

### SpeciesDefinition

```text
name
molecular_weight_kgpmol
elemental_composition
thermo_model_id
spectroscopy_id | None
```

### MixtureState

```text
temperature_K
pressure_Pa
density_kgpm3
species_mass_fractions
species_mole_fractions
molecular_weight_kgpmol
specific_gas_constant_JpkgK
cp_JpkgK
gamma
specific_enthalpy_Jpkg
specific_entropy_JpkgK
```

### ChemistryModelMetadata

```text
kind
mechanism_name
mechanism_version
thermo_database_version
transport_model
valid_temperature_range_K
valid_pressure_range_Pa
```

### ParticlePopulation

```text
classes
total_mass_fraction
total_number_density
optical_model_id
```

## 14. Verification tests

### Composition

- \(X\to Y\to X\) round trip.
- \(Y\to X\to Y\) round trip.
- mixture molecular weight agrees by both forms.
- mass and mole fractions normalize.

### Thermodynamics

- \(dh/dT=c_p\) numerically.
- enthalpy inversion returns the original temperature.
- \(c_p-c_v=R\).
- \(\gamma=c_p/c_v\).

### Frozen shock/expansion

- species unchanged.
- mass, momentum, and total enthalpy conserved.
- entropy increases across shocks.
- entropy remains constant through isentropic expansion.

### Equilibrium

- elemental abundances conserved.
- Gibbs energy does not increase from the initial feasible composition.
- reference CEA/Cantera equilibrium cases are reproduced.

### Finite rate

- elemental source sums are zero:
  \[
  \sum_s\frac{a_{ks}}{W_s}\dot\omega_s=0.
  \]
- species remain nonnegative.
- total mass source sums to zero.
- disabling rates recovers frozen behavior.

### Particles

- zero particle concentration recovers molecular radiation.
- optically thin extinction is linear in number density.
- particle energy converges to gas temperature when convection dominates.
- radiation-dominated cooling follows the expected sign.

## 15. Validation strategy

Use a hierarchy:

```text
library reference thermodynamics
CEA nozzle cases
Cantera homogeneous reactor cases
nonreacting heated plume
reacting laboratory jet
propellant-specific plume
particle-bearing plume
```

Do not calibrate particle emissivity to compensate for an incorrect gas
temperature or composition field.

## 16. Acceptance gate

Thermochemistry is accepted only when:

- all composition and elemental balances close;
- CEA provenance is preserved;
- frozen and equilibrium limits reproduce references;
- finite-rate energy is not double-counted;
- radiation uses species number density from the same mixture state;
- particle and gas temperatures remain separate where required;
- every mechanism and optical model has a version and validity range.
