# Actuator-Disk Wake Field for Curved Exhaust Plumes

## Status

This note documents the first helicopter-specific ambient-flow closure used by the curved-plume solver. It is a steady engineering model for hover or approximately axial flow. It is not a blade-resolved, free-vortex, dynamic-inflow, ground-effect, vortex-ring-state, or forward-flight wake model.

The plume conservation kernel remains rotor-agnostic. The rotor contributes only a velocity field that can be added to freestream, wind, tail-rotor flow, or an imported CFD field.

## 1. Velocity-field composition

Thermodynamic ambient state and velocity perturbations are kept separate:

```text
AmbientStateField
    pressure, temperature, density, cp, gas constant, background velocity

AmbientVelocityField
    velocity contribution only
```

`VelocityAugmentedAmbientField` evaluates

\[
\boxed{
\mathbf U_a(\mathbf x)
=
\mathbf U_{\mathrm{background}}(\mathbf x)
+
\mathbf U_{\mathrm{velocity\ field}}(\mathbf x)
}
\tag{1}
\]

without modifying ambient pressure, temperature, density, or caloric properties. `CompositeVelocityField` forms the vector sum of any number of velocity contributions.

This permits a later helicopter case to use

\[
\mathbf U_a
=
\mathbf U_\infty
+
\mathbf U_{\mathrm{main\ rotor}}
+
\mathbf U_{\mathrm{tail\ rotor}}
+
\mathbf U_{\mathrm{wind}}
+
\mathbf U_{\mathrm{airframe}}.
\]

## 2. Coordinate convention

The rotor is defined by

- center \(\mathbf x_R\);
- radius \(R_R\);
- unit wake axis \(\mathbf n_R\), pointing downstream into the wake;
- positive thrust magnitude \(T_R\);
- signed torque \(Q_R\).

For a query point \(\mathbf x\), define downstream distance

\[
\boxed{
\zeta=(\mathbf x-\mathbf x_R)\cdot\mathbf n_R
}
\tag{2}
\]

and radial vector

\[
\boxed{
\mathbf r_\perp
=
\mathbf x-\mathbf x_R-\zeta\mathbf n_R,
\qquad
r=\|\mathbf r_\perp\|.
}
\tag{3}
\]

Version 0 returns zero rotor-induced velocity for \(\zeta<0\). Upstream induction is intentionally omitted.

## 3. Hover momentum-theory scale

The rotor-disk area is

\[
A_R=\pi R_R^2.
\]

For ideal hover momentum theory, induced velocity at the disk is

\[
\boxed{
v_i
=
\sqrt{\frac{T_R}{2\rho_aA_R}}.
}
\tag{4}
\]

The ideal far-wake velocity increment is

\[
\boxed{
w_\infty=2v_i.
}
\tag{5}
\]

These relations establish the velocity scale only. They do not resolve blade loading, tip vortices, wake skew, or unsteadiness.

## 4. Wake development and contraction

A smooth downstream development closure is used:

\[
\boxed{
\bar w(\zeta)
=
v_i\left[2-\exp\left(-\frac{\zeta}{L_w}\right)\right],
\qquad \zeta\ge0.
}
\tag{6}
\]

Here \(L_w\) is a calibration length; the default is one rotor radius. Equation (6) satisfies

\[
\bar w(0)=v_i,
\qquad
\bar w(\infty)=2v_i.
\]

Conservation of the prescribed disk-average volume flux gives

\[
\pi R_w^2\bar w
=
\pi R_R^2v_i,
\]

so

\[
\boxed{
R_w(\zeta)
=
R_R\sqrt{\frac{v_i}{\bar w(\zeta)}}.
}
\tag{7}
\]

Consequently,

\[
R_w(0)=R_R,
\qquad
R_w(\infty)=\frac{R_R}{\sqrt2}.
\]

The exponential development law is an engineering closure, not a consequence of ideal momentum theory. It must be calibrated or replaced when wake measurements are available.

## 5. Normalized radial loading

Let

\[
\xi=\frac{r}{R_w}.
\]

For \(0\le\xi<1\), the compact axial profile is

\[
\boxed{
\phi_n(\xi)
=
(n+1)(1-\xi^2)^n,
\qquad n\ge0.
}
\tag{8}
\]

It is zero outside the wake. The normalization follows from

\[
2\int_0^1\phi_n(\xi)\xi\,d\xi=1.
\]

Thus

\[
\boxed{
u_z(r,\zeta)
=
\bar w(\zeta)\phi_n(r/R_w)
}
\tag{9}
\]

has area-average velocity \(\bar w\), independent of \(n\). This prevents a radial-profile choice from silently changing rotor mass flux.

The special case \(n=0\) is a uniform top-hat wake. Positive \(n\) produces a compact profile that decreases continuously toward the wake boundary.

## 6. Torque-normalized swirl

Define the azimuthal direction by the right-hand rule about the wake axis:

\[
\mathbf e_\theta
=
\mathbf n_R\times\mathbf e_r.
\]

The first swirl closure is a tapered solid-body profile,

\[
\boxed{
u_\theta(r,\zeta)
=
\Omega_w(\zeta)r(1-\xi^2)^m,
\qquad m\ge0.
}
\tag{10}
\]

Rotor torque is equated to axial angular-momentum flux:

\[
Q_R
=
\int_A
\rho_a u_z(r)
\left[r u_\theta(r)\right]dA.
\tag{11}
\]

Substituting Equations (8)--(10) yields

\[
Q_R
=
\pi\rho_a\bar w\Omega_wR_w^4
\frac{n+1}{(n+m+1)(n+m+2)}.
\]

Therefore

\[
\boxed{
\Omega_w
=
\frac{Q_R(n+m+1)(n+m+2)}
{\pi\rho_a\bar wR_w^4(n+1)}.
}
\tag{12}
\]

Signed \(Q_R\) determines swirl direction. Reversing torque must mirror the lateral plume displacement in an otherwise axisymmetric case.

The complete induced field is

\[
\boxed{
\mathbf U_R
=
u_z\mathbf n_R+u_\theta\mathbf e_\theta.
}
\tag{13}
\]

## 7. Implemented verification

The acceptance tests verify:

1. velocity fields add vectorially while background thermodynamics remain unchanged;
2. disk-average axial velocity equals \(v_i\);
3. the far wake approaches \(2v_i\) and \(R_R/\sqrt2\);
4. the radial profile has the required area normalization;
5. integrated angular-momentum flux equals the prescribed signed torque;
6. rotating the complete geometry rotates the returned velocity without changing its intrinsic solution;
7. a lateral exhaust bends into downward rotor wash;
8. reversing rotor torque mirrors the lateral plume trajectory while preserving the axial/downwash trajectory.

## 8. Validity limits

This field should be treated as a first-order hover or axial-flow model. It currently omits:

- upstream induction;
- finite blade count and blade passage;
- tip and root vortices;
- wake skew and deformation in forward flight;
- rotor-fuselage interaction;
- ground effect;
- vortex-ring and turbulent-wake states;
- radial or azimuthal variation in disk loading beyond the selected compact profile;
- time dependence and gust response.

The discontinuity at the actuator-disk plane and compact wake boundary is acceptable for cases whose plume source begins inside the downstream wake. A later prescribed/free-wake or CFD-grid field should replace this model for high-fidelity aircraft studies.

## 9. Next calibration sequence

1. Fit \(L_w\) and radial exponent \(n\) to measured axial velocity profiles.
2. Fit or replace the swirl profile using torque and tangential-velocity measurements.
3. Add a skewed wake centerline for low advance ratio.
4. Add tail-rotor and multiple-rotor compositions using the same velocity-field protocol.
5. Add a grid-backed field for fuselage airwake and high-advance-ratio operation.
6. Validate plume trajectory and dilution without re-fitting the already calibrated free-jet entrainment closure.

## 10. Research anchors

The implementation is intentionally lower fidelity than the following references, which establish the hierarchy beyond the present actuator-disk closure:

- K. Kawachi, *An Extension of the Local Momentum Theory to a Distorted Wake Model of a Hovering Rotor*, NASA-TM-81258, 1981.
- H. A. Saberi, *Analytical Model of Rotor Wake Aerodynamics in Ground Effect*, NASA-CR-166533, 1983.
- H. C. Curtiss Jr. and R. M. McKillip Jr., *Studies of a Flat Wake Rotor Theory*, NASA-CR-190936, 1992.
- C. P. Coleman, *A Survey of Theoretical and Experimental Coaxial Rotor Aerodynamic Research*, NASA-TP-3675, 1997.
- M. Ramasamy, N. P. Gold, and M. J. Bhagwat, *Rotor Hover Performance and Flowfield Measurements with Untwisted and Highly-Twisted Blades*, 36th European Rotorcraft Forum, 2010.
