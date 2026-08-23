# Integral Downstream Mixing-Plume Plan

## 1. Purpose

Continue the plume after coherent shock cells disappear. This model supplies
the downstream velocity, temperature, radius, density, and species fields
needed for thermal and infrared calculations.

The first implementation is a steady, axisymmetric, pressure-matched,
top-hat integral plume. A Gaussian-profile refinement follows only after the
top-hat conservation equations pass verification.

## 2. Entry condition

Start at:

```text
x0 = shock_train_end_x_m
```

Use an area-averaged state derived from the final coherent-core and shear-layer
state.

Required inputs:

```text
mass_flow_rate_kgps
axial_momentum_flux_N
total_enthalpy_flow_W
species_mass_flow_rates_kgps
ambient_state
initial_radius_m
entrainment_calibration
```

## 3. State vector

Use conserved or balance-friendly variables:

\[
\mathbf q
=
\begin{bmatrix}
\dot m\\
\Pi\\
\dot H_0\\
\dot m_1\\
\vdots\\
\dot m_{N_s}
\end{bmatrix}.
\]

Where:

\[
\dot m=\rho uA,
\]

\[
\Pi=\dot m u+(p-p_a)A,
\]

\[
\dot H_0=\dot m h_0,
\]

\[
\dot m_s=\dot mY_s.
\]

This formulation reduces drift in mass, momentum, enthalpy, and species.

## 4. Baseline assumptions

For the first implementation:

\[
p(x)=p_a.
\]

Therefore:

\[
\Pi=\dot m u.
\]

No body forces:

\[
\frac{d\Pi}{dx}=0.
\]

Frozen, nonreacting chemistry:

\[
\dot\omega_s=0.
\]

No radiative feedback on the flow:

\[
\dot Q'_{\mathrm{rad}}=0.
\]

These assumptions can be relaxed later without changing the state contract.

## 5. Entrainment closure

Let \(R(x)\) be the top-hat plume radius. Use:

\[
\boxed{
\frac{d\dot m}{dx}
=
2\pi R
\rho_a
E
|u-u_a|.
}
\]

\(E\) is a calibrated entrainment coefficient.

For quiescent ambient:

\[
u_a=0.
\]

The entrained stream carries ambient momentum, enthalpy, and species.

## 6. Momentum equation

General pressure-aware form:

\[
\boxed{
\frac{d}{dx}
\left[
\dot m u+(p-p_a)A
\right]
=
F'_x.
}
\]

For the baseline pressure-matched, force-free model:

\[
\boxed{
\frac{d\Pi}{dx}=0.
}
\]

Therefore:

\[
\boxed{
u=\frac{\Pi}{\dot m}.
}
\]

As mass is entrained, velocity decays.

## 7. Total-enthalpy equation

\[
\boxed{
\frac{d\dot H_0}{dx}
=
h_{0a}\frac{d\dot m}{dx}
+
\dot Q'_{\mathrm{chem}}
-
\dot Q'_{\mathrm{rad}}
+
\dot W'_{\mathrm{ext}}.
}
\]

Baseline:

\[
\boxed{
\frac{d\dot H_0}{dx}
=
h_{0a}\frac{d\dot m}{dx}.
}
\]

Recover:

\[
h_0=\frac{\dot H_0}{\dot m}.
\]

Then:

\[
\boxed{
h=h_0-\frac{u^2}{2}.
}
\]

For a calorically perfect mixture:

\[
\boxed{
T=\frac{h}{c_p(\mathbf Y)}.
}
\]

## 8. Species equations

For species \(s\):

\[
\boxed{
\frac{d(\dot mY_s)}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}
+
\dot\omega_sA.
}
\]

Baseline frozen mixing:

\[
\boxed{
\frac{d\dot m_s}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}.
}
\]

Recover:

\[
\boxed{
Y_s=\frac{\dot m_s}{\dot m}.
}
\]

After every step, verify:

\[
Y_s\ge0,
\qquad
\sum_sY_s=1
\]

within tolerance.

## 9. Thermodynamic closure and radius

Calculate mixture molecular weight:

\[
\overline W
=
\left(
\sum_s\frac{Y_s}{W_s}
\right)^{-1},
\]

\[
R=\frac{R_u}{\overline W}.
\]

At \(p=p_a\),

\[
\boxed{
\rho=\frac{p_a}{RT}.
}
\]

The cross-sectional area is:

\[
\boxed{
A=\frac{\dot m}{\rho u}.
}
\]

For a circular plume:

\[
\boxed{
R_{\mathrm{plume}}=\sqrt{\frac{A}{\pi}}.
}
\]

## 10. ODE system

The baseline derivatives are:

\[
\frac{d\dot m}{dx}
=
2\pi R_{\mathrm{plume}}
\rho_a
E
|u-u_a|,
\]

\[
\frac{d\Pi}{dx}=0,
\]

\[
\frac{d\dot H_0}{dx}
=
h_{0a}\frac{d\dot m}{dx},
\]

\[
\frac{d\dot m_s}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}.
\]

At every right-hand-side evaluation:

1. Recover \(u=\Pi/\dot m\).
2. Recover \(Y_s=\dot m_s/\dot m\).
3. Calculate \(h_0=\dot H_0/\dot m\).
4. Calculate \(h=h_0-u^2/2\).
5. Invert \(h(T,\mathbf Y)\) for \(T\).
6. Calculate \(R(\mathbf Y)\) and \(\rho=p_a/(RT)\).
7. Calculate \(A=\dot m/(\rho u)\).
8. Calculate plume radius and entrainment.

Use `scipy.integrate.solve_ivp` with event functions and dense output.

## 11. Termination events

### Velocity equilibrium

\[
\boxed{
\frac{|u-u_a|}
{\max(|u_0-u_a|,u_{\mathrm{scale}})}
\le\epsilon_u.
}
\]

### Temperature equilibrium

\[
\boxed{
\frac{|T-T_a|}{T_a}
\le\epsilon_T.
}
\]

### Composition equilibrium

\[
\boxed{
\frac12
\sum_s
|Y_s-Y_{s,a}|
\le\epsilon_Y.
}
\]

### Persistence

Require all selected equilibrium criteria for a minimum axial persistence
length:

\[
\Delta x_{\mathrm{persist}}
\ge
L_{\mathrm{persist}}.
\]

### Domain limit

\[
x\ge x_{\max}
\Rightarrow
\text{DOMAIN_LIMIT}.
\]

## 12. Axisymmetric field reconstruction

The top-hat field is:

\[
\phi(x,r)
=
\begin{cases}
\phi_c(x), & r\le R(x),\\
\phi_a, & r>R(x).
\end{cases}
\]

This is sufficient for the first gray-gas ray tracer but creates a sharp
boundary.

The next refinement uses a Gaussian profile:

\[
\boxed{
\phi(x,r)
=
\phi_a+
[\phi_c(x)-\phi_a]
\exp
\left[
-\left(\frac{r}{b_\phi(x)}\right)^2
\right].
}
\]

Profile widths must be selected so that integrated mass, momentum, enthalpy,
and species match the integral state. Do not choose widths independently of
the conserved fluxes.

## 13. Data contracts

### IntegralPlumeState

```text
x_m
mass_flow_rate_kgps
momentum_flux_N
total_enthalpy_flow_W
species_mass_flow_rates_kgps
velocity_mps
temperature_K
pressure_Pa
density_kgpm3
radius_m
species_mass_fractions
```

### IntegralPlumeResult

```text
states
termination_reason
termination_x_m
conservation_residuals
calibration_id
status
diagnostics
```

### AxisymmetricPlumeField

```text
axial_grid_m
radial_grid_m
temperature_K
pressure_Pa
density_kgpm3
axial_velocity_mps
species_mole_fractions
validity_mask
source_model
```

## 14. Numerical safeguards

Reject or stop when:

```text
mass flow <= 0
velocity <= 0 before expected equilibrium
temperature <= 0
enthalpy inversion fails
radius is nonfinite
species normalization fails
ODE step creates nonphysical state
```

All event and failure states must include the last valid state.

## 15. Verification tests

### Analytic limiting cases

1. \(E=0\):
   - \(\dot m\) constant;
   - \(u\) constant;
   - \(T\) constant;
   - species constant.

2. Ambient identical to plume:
   - no meaningful disturbance;
   - immediate equilibrium status.

3. Frozen entrainment:
   - total species mass-flow derivative equals ambient species in entrained
     mass.

### Conservation

Track:

\[
r_m
=
\dot m(x)
-
\dot m_0
-
\int_{x_0}^x
\frac{d\dot m}{d\xi}d\xi,
\]

\[
r_\Pi=\Pi(x)-\Pi_0,
\]

\[
r_H
=
\dot H_0(x)
-
\dot H_{0,0}
-
\int_{x_0}^x
h_{0a}
\frac{d\dot m}{d\xi}
d\xi.
\]

Require normalized residuals below configured tolerances.

### Monotonic behavior

For hot, fast exhaust in quiescent ambient:

```text
mass flow increases
velocity decreases
temperature approaches ambient
plume radius grows
exhaust-species fractions decrease
ambient-species fractions increase
```

Do not hard-code monotonic temperature when chemistry is later enabled.

## 16. Acceptance gate

Phase 3 is complete when:

- mass, momentum, enthalpy, and species balances close;
- event termination is distinct from domain truncation;
- the top-hat field produces finite ray intersections;
- the field approaches ambient under nonreacting mixing;
- the result preserves model and calibration provenance;
- Gaussian reconstruction, if added, preserves the integral fluxes.
