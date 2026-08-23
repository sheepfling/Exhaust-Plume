# Developing Shear and Forced-Crossflow Entrainment

## Status

This note defines a configurable entrainment closure for the conservative curved-plume kernel. Mass, momentum, energy, and tracer equations remain unchanged. The closure only supplies

\[
\mathcal E_m=\frac{d\dot m}{ds}.
\]

The implemented coefficients are calibration parameters. No value in this note should be interpreted as a universally validated helicopter-exhaust constant.

## 1. Local kinematics

Let

\[
\mathbf t=\frac{\mathbf V}{V}
\]

be the plume tangent. The axial relative speed is

\[
W_\parallel=
\left|\left(\mathbf V-\mathbf U_a\right)\cdot\mathbf t\right|.
\]

The ambient component normal to the plume is

\[
\mathbf U_\perp
=\mathbf U_a-(\mathbf U_a\cdot\mathbf t)\mathbf t,
\qquad
U_\perp=\|\mathbf U_\perp\|.
\]

For a circular cross-section, the shear perimeter is \(2\pi b\) and the width presented to crossflow is \(2b\).

## 2. Developing shear entrainment

The shear component is

\[
\boxed{
\mathcal E_s
=2\pi b\,\alpha_s f_{\mathrm{dev}}
\sqrt{\rho\rho_a}\,W_\parallel
}.
\]

The density factor is non-Boussinesq and symmetric in plume and ambient density. It is a closure choice that must be tested against variable-density jet data.

The development factor is

\[
\boxed{
f_{\mathrm{dev}}(s)
=1-(1-f_0)e^{-s/L_{\mathrm{dev}}}
}.
\]

It satisfies

\[
f_{\mathrm{dev}}(0)=f_0,
\qquad
f_{\mathrm{dev}}(\infty)=1.
\]

This prevents a source from being forced to use a fully developed turbulent-jet entrainment rate immediately at the outlet.

## 3. Forced crossflow component

The forced component is

\[
\boxed{
\mathcal E_f
=2b\,C_f\rho_a U_\perp
}.
\]

The model treats this as mass intercepted and incorporated because ambient flow crosses the plume envelope. It remains separate from any future form-drag or added-mass force; fitting crossflow trajectory does not automatically identify both entrainment and drag.

## 4. Combination family

The two rates are combined using

\[
\boxed{
\mathcal E_m
=\left(\mathcal E_s^{p_e}+\mathcal E_f^{p_e}\right)^{1/p_e}
}.
\]

Special cases are

\[
p_e=1:
\quad
\mathcal E_m=\mathcal E_s+\mathcal E_f,
\]

and

\[
p_e=2:
\quad
\mathcal E_m=\sqrt{\mathcal E_s^2+\mathcal E_f^2}.
\]

The combination exponent is explicit because current research does not justify silently choosing one rule for every outlet, density ratio, and crossflow regime.

## 5. Exact developing free-jet solution

For a quiescent, equal-density ambient with no body force and \(C_f=0\), momentum flux is constant. Let the source radius, speed, and mass flow be \(b_0\), \(V_0\), and \(\dot m_0\). Define

\[
S_{\mathrm{eff}}(s)
=s-(1-f_0)L_{\mathrm{dev}}
\left(1-e^{-s/L_{\mathrm{dev}}}\right).
\]

The top-hat solution is

\[
\boxed{
\frac{\dot m(s)}{\dot m_0}
=1+\frac{2\alpha_s}{b_0}S_{\mathrm{eff}}(s)
},
\]

\[
\boxed{
V(s)=V_0\frac{\dot m_0}{\dot m(s)},
\qquad
b(s)=b_0\frac{\dot m(s)}{\dot m_0}
},
\]

and

\[
\boxed{
Y_e(s)=\frac{\dot m_0}{\dot m(s)}
}.
\]

The implementation is regression-tested directly against these equations.

## 6. Diagnostics

`CurvedPlumeEntrainmentComponents` reports:

- development factor;
- axial relative speed;
- normal ambient speed;
- shear entrainment rate;
- forced entrainment rate;
- combined entrainment rate.

These quantities should be retained during calibration so a plausible total rate cannot hide an incorrect balance between mechanisms.

## 7. Calibration order

The intended identification order is:

1. fit \(\alpha_s\), \(f_0\), and \(L_{\mathrm{dev}}\) using quiescent round-jet width, mass-flow, and velocity data;
2. validate variable-density behavior before changing \(C_f\);
3. fit \(C_f\) and \(p_e\) using uniform-crossflow trajectory and dilution data;
4. hold plume coefficients fixed while calibrating the rotor velocity field;
5. add an explicit crossflow-force closure only if trajectory errors remain systematic.

This order avoids fitting rotor-wake error, entrainment error, and form drag into one coefficient.

## 8. Current limitations

- circular top-hat cross-section only;
- no compressibility suppression factor;
- no Reynolds-number transition model;
- no slot/elliptical perimeter or projected-width model;
- no crossflow vortex-pair deformation;
- no stochastic gust or blade-passage modulation;
- no claim of helicopter-specific coefficient validation.
