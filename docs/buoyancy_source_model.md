# Hydrostatic Buoyancy Source Model

## Status

This note defines the first buoyancy increment for the pressure-matched curved-plume solver. It adds buoyancy through the existing external source-term interface; it does not alter the conservative state or hide buoyancy inside the entrainment coefficient.

The implementation is intended for a slender plume embedded in a locally hydrostatic ambient atmosphere. It uses the plume and ambient densities already reconstructed by the non-Boussinesq thermodynamic closure.

## 1. Reduced net force

Let the gravitational acceleration vector be \(\mathbf g\), pointing downward. Hydrostatic ambient pressure satisfies

\[
\nabla p_a = \rho_a \mathbf g.
\]

The gravitational force on a plume segment of cross-sectional area \(A\) and unit centerline length is

\[
\mathbf F_g' = \rho A\mathbf g.
\]

The ambient pressure gradient supplies

\[
\mathbf F_p' = -A\nabla p_a = -\rho_a A\mathbf g.
\]

The reduced net force per unit centerline length is therefore

\[
\boxed{
\mathbf F_b'=(\rho-\rho_a)A\mathbf g
}.
\]

For \(\rho<\rho_a\), the coefficient is negative and the force points opposite gravity: upward. No Boussinesq density linearization is used.

## 2. Energy bookkeeping

The current curved-plume energy state is

\[
\dot{\mathcal H}=\dot m\left(h+\frac12V^2\right),
\]

which does not include gravitational potential energy. The reduced buoyancy force combines gravity and hydrostatic pressure work, so its mechanical work must enter the energy equation:

\[
\boxed{
\dot q_b' = \mathbf F_b'\cdot\mathbf V
}.
\]

The momentum and energy equations become

\[
\frac{d\mathbf P}{ds}
=\mathcal E_m\mathbf U_a+\mathbf F_b'+\mathbf F_{\mathrm{other}}',
\]

\[
\frac{d\dot{\mathcal H}}{ds}
=\mathcal E_m\left(h_a+\frac12U_a^2\right)
+\mathbf F_b'\cdot\mathbf V
+\dot q_{\mathrm{other}}'.
\]

This pairing prevents buoyant acceleration from creating a false temperature change. For a non-entraining calorically perfect plume, buoyancy changes kinetic energy while static enthalpy remains constant.

## 3. Exact vertical limit

Consider a constant-density plume traveling upward parallel to the buoyancy force, with no ambient velocity and no entrainment. Continuity gives

\[
A=\frac{\dot m}{\rho V}.
\]

For a light plume, define the positive reduced acceleration

\[
a_b=g\frac{\rho_a-\rho}{\rho}.
\]

The scalar momentum equation is

\[
\dot m\frac{dV}{ds}
=(\rho_a-\rho)Ag
=\dot m\frac{a_b}{V}.
\]

Therefore

\[
\boxed{
V(s)^2=V_0^2+2a_b s
},
\]

and

\[
\boxed{
A(s)=\frac{\dot m}{\rho V(s)},
\qquad
b(s)=\sqrt{\frac{A(s)}{\pi}}
}.
\]

Because \(d\dot{\mathcal H}/ds=\mathbf F_b'\cdot\mathbf V\), the increase in total-energy flux equals the increase in kinetic-energy flux and \(T(s)=T_0\). This closed-form limit is used as a regression oracle.

## 4. Composition

`CompositeCurvedPlumeSourceTermModel` adds independent source-term closures. This allows buoyancy to coexist with later form-drag, radiation-loss, chemistry, or wall-interaction models without coupling their parameters or changing the integrator.

## 5. Validity limits

The model requires:

- local plume pressure approximately equal to ambient pressure;
- an ambient pressure field that is hydrostatic under the supplied gravity vector;
- a slender cross-section over which \(\rho_a\), \(\rho\), and \(\mathbf g\) can be treated as uniform;
- no ground, fuselage, or wall contact;
- no unresolved separated-flow pressure forces.

It does not represent rotor pressure jumps, blade-vortex pressure fluctuations, airframe suction regions, or wall-jet attachment. Those require either an explicitly sampled pressure-gradient field or a higher-fidelity flowfield handoff.

## 6. Acceptance tests

The increment is accepted only when:

1. the vertical constant-density solution matches \(V^2=V_0^2+2a_bs\);
2. the same solution remains isothermal to integration tolerance;
3. a horizontal light plume bends upward with the predicted initial curvature;
4. neutral density produces zero buoyancy;
5. rotating the complete source, ambient flow, and gravity vector rotates the solution without changing scalar histories;
6. composite source terms exactly sum force and energy contributions.
