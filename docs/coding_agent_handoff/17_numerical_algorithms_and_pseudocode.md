# Numerical Algorithms and Pseudocode Specification

## 1. Purpose

This document turns the governing equations in the architecture and physics
plans into deterministic numerical procedures. It is normative for root
bracketing, geometry, characteristic marching, shock-cell iteration, mixing
integration, and line-of-sight radiative transfer.

The coding agent shall not replace a bracketed or bounded algorithm with an
unbounded Newton iteration merely because the latter is shorter. Every solver
must return structured convergence information rather than logging an error and
continuing with an approximate state.

## 2. Common numerical contract

Every numerical operation shall return a result containing at least:

```text
status
value
converged
iterations
residual_absolute
residual_relative
bracket_or_domain
warnings
```

Recommended generic status values are:

```text
CONVERGED
CONVERGED_AT_BOUNDARY
INVALID_INPUT
NO_BRACKET
OUTSIDE_PHYSICAL_DOMAIN
ILL_CONDITIONED
MAX_ITERATIONS
NONFINITE_RESULT
DETACHED_SHOCK_REQUIRED
NO_FORWARD_INTERSECTION
```

### 2.1 Residual normalization

For a scalar equation

\[
f(x)=0,
\]

define

\[
r_{\mathrm{abs}}=|f(x)|,
\]

and

\[
r_{\mathrm{rel}}
=
\frac{|f(x)|}{\max(s_f,\epsilon_f)},
\]

where \(s_f\) is a problem-specific scale. A solution is accepted only when
both the state increment and the normalized residual satisfy configured
criteria.

### 2.2 Tolerance hierarchy

Use separate tolerances for:

```text
state_rtol
state_atol
angle_atol_rad
geometry_atol_m
residual_rtol
residual_atol
condition_number_max
max_iterations
```

Do not use one global tolerance for pressure, angle, position, and spectral
radiance.

### 2.3 Finite-value rule

Inputs and outputs must be finite unless the public contract explicitly allows
an infinite asymptotic limit. Intermediate `NaN` values may be used privately
to detect a failed operation, but they must not appear in a successful public
result.

## 3. Scalar root-solving policy

Use `scipy.optimize.brentq` or an equivalent safeguarded bracketed method when
a continuous scalar residual has a known sign-changing interval.

Algorithm:

```text
1. Validate finite lower and upper bounds with lower < upper.
2. Evaluate f(lower) and f(upper).
3. Accept an endpoint only when its residual passes the configured test.
4. If the endpoint residuals do not bracket a sign change, return NO_BRACKET.
5. Run the bounded solver.
6. Re-evaluate the physical-domain constraints at the returned root.
7. Return root, residuals, iterations, and the final bracket.
```

Unbracketed Newton or secant methods may be used only as local accelerators
inside a safeguarded outer method and must never be the sole convergence path
for public physics solvers.

## 4. Supersonic area--Mach inversion

Define

\[
\mathcal A(M;\gamma)
=
\frac{1}{M}
\left[
\frac{2}{\gamma+1}
\left(1+\frac{\gamma-1}{2}M^2\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

For a requested ratio \(A/A^*\ge 1\), solve

\[
f(M)=\mathcal A(M;\gamma)-\frac{A}{A^*}=0.
\]

### 4.1 Subsonic branch

Use

\[
M\in(M_{\min},1),
\]

with a small positive \(M_{\min}\). The branch is monotone over this interval.

### 4.2 Supersonic branch

Use

\[
M\in(1,M_{\max}).
\]

Find \(M_{\max}\) by geometric expansion:

```text
M_high = 2
while A(M_high) < requested_ratio:
    M_high *= 2
    fail when M_high exceeds configured physical or numerical limit
```

The public API must require the branch explicitly. It must never infer a branch
from a starting guess.

### 4.3 Exact sonic ratio

When

\[
\left|A/A^*-1\right|\le\epsilon_A,
\]

return \(M=1\) with `CONVERGED_AT_BOUNDARY`.

## 5. Prandtl--Meyer inversion

For \(M\ge1\), define

\[
\nu(M)
=
\sqrt{\frac{\gamma+1}{\gamma-1}}
\tan^{-1}
\sqrt{\frac{\gamma-1}{\gamma+1}(M^2-1)}
-
\tan^{-1}\sqrt{M^2-1}.
\]

The maximum angle is

\[
\nu_{\max}
=
\frac{\pi}{2}
\left(
\sqrt{\frac{\gamma+1}{\gamma-1}}-1
\right).
\]

Given \(\nu_t\):

```text
1. Reject nu_t < 0 or nu_t > nu_max plus tolerance.
2. Return M = 1 when nu_t is approximately zero.
3. Set M_low = 1 + epsilon_M.
4. Expand M_high geometrically until nu(M_high) >= nu_t.
5. Solve nu(M) - nu_t = 0 with a bracketed method.
6. Verify M >= 1 and the angle residual.
```

The implementation shall expose the residual in radians even if a compatibility
wrapper accepts degrees.

## 6. Theta--beta--Mach solution

Define

\[
g(\beta;M,\gamma)
=
\tan^{-1}
\left[
2\cot\beta
\frac{M^2\sin^2\beta-1}
{M^2(\gamma+\cos2\beta)+2}
\right].
\]

The physical interval is

\[
\mu<\beta<\frac{\pi}{2},
\qquad
\mu=\sin^{-1}(1/M).
\]

### 6.1 Maximum attached turn

Calculate

\[
\theta_{\max}
=
\max_{\beta\in(\mu,\pi/2)}g(\beta).
\]

Use a bounded scalar maximization of \(-g\), preceded by a coarse deterministic
scan to establish a stable bounded interval around the maximum. Return both
\(\theta_{\max}\) and \(\beta_{\mathrm{peak}}\).

### 6.2 Weak and strong roots

For requested \(\theta\):

```text
if theta < 0:
    return INVALID_INPUT
if theta approximately 0:
    weak beta = Mach angle
    strong beta = pi / 2
if theta > theta_max plus tolerance:
    return DETACHED_SHOCK_REQUIRED
weak root bracket  = [mu + eps, beta_peak]
strong root bracket = [beta_peak, pi / 2 - eps]
solve g(beta) - theta = 0 on the requested branch
```

This explicitly fixes the current behavior in which both zero-turn branches
are forced to a normal shock.

## 7. Shock to a target static pressure

For an upstream state and desired pressure ratio

\[
R_p=\frac{p_2}{p_1}\ge1,
\]

the normal-shock pressure equation gives

\[
M_{n1}^2
=
1+
(R_p-1)\frac{\gamma+1}{2\gamma}.
\]

Therefore

\[
\beta
=
\sin^{-1}\left(\frac{M_{n1}}{M_1}\right).
\]

This direct construction is preferred over a nested pressure-angle bisection.
The algorithm is:

```text
1. Reject target pressure below upstream pressure.
2. Compute the maximum normal-shock pressure ratio at beta = pi / 2.
3. Reject a target above that limit.
4. Compute Mn1 from the requested pressure ratio.
5. Compute beta = asin(Mn1 / M1).
6. Compute theta from the theta--beta--Mach equation.
7. Compute beta_peak and theta_max.
8. If beta > beta_peak plus tolerance, classify the state as strong branch.
9. If only weak attached shocks are permitted, reject a strong-branch target.
10. Build the downstream state and verify the pressure residual and total-
    pressure loss.
```

The result must record `WEAK`, `STRONG`, or `DETACHED_REQUIRED` explicitly.

## 8. Two-dimensional forward-ray intersection

Represent each ray as

\[
\mathbf x_i(s_i)=\mathbf o_i+s_i\mathbf d_i,
\qquad s_i\ge0.
\]

Solve

\[
\begin{bmatrix}
 d_{1x} & -d_{2x}\\
 d_{1y} & -d_{2y}
\end{bmatrix}
\begin{bmatrix}s_1\\s_2\end{bmatrix}
=
\mathbf o_2-\mathbf o_1.
\]

### 8.1 Conditioning

Let the matrix be \(A\). Reject when

\[
\kappa_2(A)>\kappa_{\max}
\]

or when the determinant magnitude is below a scale-aware threshold.

The default successful path shall use a direct 2-by-2 solve, not a
pseudoinverse. A least-squares result may be returned only as a failed
diagnostic.

### 8.2 Forward constraint

Accept only when

\[
s_1\ge-\epsilon_s,
\qquad
s_2\ge-\epsilon_s.
\]

Clamp a parameter to zero only when it lies within tolerance of zero.

### 8.3 Residual

Report

\[
r_x
=
\left\|
\mathbf o_1+s_1\mathbf d_1
-
\mathbf o_2-s_2\mathbf d_2
\right\|_2.
\]

The result contract shall include the point, both ray parameters, determinant,
condition number, and residual.

## 9. Legacy line--parabola intersection

The fitted parabola is temporary compatibility behavior. While it remains:

```text
1. Parameterize the line as a ray, not as a global y = mx + b line.
2. Substitute x(s), y(s) into the polynomial.
3. Solve the resulting scalar polynomial for s.
4. Discard complex roots above tolerance.
5. Discard s < -epsilon_s.
6. Select the smallest forward s, not the smallest positive global x.
7. Return all candidate roots in diagnostics.
```

This prevents a valid-looking intersection on the wrong branch or behind the
origin.

## 10. Planar characteristic interior point

Suppose point \(A\) emits a \(C^+\) characteristic and point \(B\) emits a
\(C^-\) characteristic.

The invariants are

\[
K_+=\theta_A-\nu_A,
\qquad
K_-=\theta_B+\nu_B.
\]

The intersection state is

\[
\theta_P=\frac{K_++K_-}{2},
\qquad
\nu_P=\frac{K_--K_+}{2}.
\]

Invert \(\nu_P\) to obtain \(M_P\) and

\[
\mu_P=\sin^{-1}(1/M_P).
\]

Use averaged endpoint slopes:

\[
\psi_+
=
\frac{(\theta_A+\mu_A)+(\theta_P+\mu_P)}{2},
\]

\[
\psi_-
=
\frac{(\theta_B-\mu_B)+(\theta_P-\mu_P)}{2}.
\]

Then intersect the two forward rays.

Pseudocode:

```text
compute K_plus and K_minus
compute theta_P and nu_P
invert nu_P to M_P
compute mu_P
initialize point from source-state slopes
repeat:
    compute averaged characteristic directions
    intersect forward rays
    compare position update with geometry tolerance
until converged or max iterations
verify state invariants and intersection residual
```

Because the state is fixed by compatibility for a planar calorically perfect
flow, only the geometry normally requires fixed-point iteration.

## 11. Centerline characteristic point

At the centerline,

\[
y=0,
\qquad
\theta=0.
\]

For a \(C^+\) line with invariant \(K_+=\theta-\nu\),

\[
\nu_c=-K_+.
\]

For a \(C^-\) line with invariant \(K_-=\theta+\nu\),

\[
\nu_c=K_-.
\]

Algorithm:

```text
1. Apply the appropriate compatibility invariant.
2. Set theta_c = 0 exactly.
3. Invert nu_c to M_c.
4. Use the averaged incoming characteristic angle.
5. Intersect the characteristic with y = 0 as a forward ray.
6. Verify x_c is downstream and the invariant residual passes.
```

A geometric reflection matrix alone is not a centerline state solution.

## 12. Ambient-pressure free-boundary point

The free boundary satisfies

\[
p_b=p_a,
\qquad
\frac{dy_b}{dx}=\tan\theta_b.
\]

For a calorically perfect isentropic boundary with known stagnation pressure,
calculate \(M_b\) from \(p_0/p_a\), then \(\nu_b\).

For an incoming \(C^+\) characteristic carrying \(K_+\),

\[
\theta_b=K_++\nu_b.
\]

For an incoming \(C^-\) characteristic carrying \(K_-\),

\[
\theta_b=K_--\nu_b.
\]

Given the previous boundary point \(B_0\), solve the intersection of:

- the incoming characteristic ray from interior point \(A\); and
- the boundary tangent ray from \(B_0\).

Use averaged slopes between the old and new endpoint states and iterate until
both position and pressure/compatibility residuals converge.

## 13. First-cell assembly

The first-cell implementation shall be decomposed into pure operations:

```text
classify regime
construct exit state
construct initial lip wave or fan
march characteristic points to centerline
apply centerline compatibility
march reflected characteristics to free boundary
apply free-boundary compatibility
construct compression or shock closure
validate closed-zone topology
compute diagnostics and correlation comparison
```

### 13.1 Underexpanded case

```text
1. Compute the ambient-pressure boundary Mach and required PM turn.
2. Discretize the expansion into N characteristic states.
3. March the initial fan to the centerline.
4. Reflect through compatibility, not coordinate reflection alone.
5. March to the ambient-pressure free boundary.
6. Construct the recompression system.
7. Close the cell only when all boundaries intersect forward and all zones
   have positive area.
```

### 13.2 Mild attached overexpanded case

```text
1. Solve the lip shock needed to raise pressure toward ambient.
2. Reject when the required shock is detached or on a disallowed strong branch.
3. Intersect the shock with the centerline using delta_x = R / tan(beta).
4. Apply centerline shock/compatibility conditions.
5. Continue with the characteristic/free-boundary solve.
6. Reject when nozzle separation invalidates the supplied uniform exit state.
```

## 14. Closed-zone topology validation

For every closed polygon:

```text
finite coordinates
at least three distinct vertices
nonzero signed area
consistent winding
no nonadjacent edge intersection
no edge with length below tolerance
all vertices within the configured domain
```

The signed area is

\[
A
=
\frac12
\sum_i
(x_i y_{i+1}-x_{i+1}y_i).
\]

A successful zone collection must use one consistent winding convention.

## 15. Shock-train iteration

Pseudocode:

```text
cells = [validated_first_cell]
metrics = metrics(first_cell)
state = first_cell.exit_state
x = first_cell.x_end

while True:
    reason = evaluate_physical_termination(metrics, state, x)
    if reason is not None:
        return physical result

    reason = evaluate_safety_limits(cell_count, x)
    if reason is not None:
        return truncated result

    core = update_coherent_core(state, x, calibration)
    spacing = calculate_local_spacing(core, calibration)
    amplitude = integrate_amplitude_decay(metrics.amplitude, spacing)
    next_state = propagate_mean_state_and_total_pressure_loss(state)
    next_cell = construct_reduced_or_resolved_cell(...)

    validate next_cell and diagnostics
    append next_cell
    update x, state, metrics
```

The physical termination test must run before generating the next cell. The
safety-limit result must remain distinguishable from a physical endpoint.

## 16. Integral mixing-plume integration

The state vector should use conservative or positivity-preserving variables,
for example

\[
\mathbf q
=
\left[
\dot m,
\mathcal M,
\mathcal H,
\dot mY_1,\ldots,\dot mY_{N_s-1}
\right],
\]

where

\[
\mathcal M=\dot m u+(p-p_a)A,
\qquad
\mathcal H=\dot m h_0.
\]

At each ODE evaluation:

```text
1. Recover species fractions and final dependent species.
2. Recover thermodynamic state from mass, momentum, and enthalpy invariants.
3. Reject negative density, temperature, area, or species fractions outside
   configured projection tolerance.
4. Evaluate entrainment and optional chemistry/radiation source terms.
5. Return derivatives and event functions.
```

Use `scipy.integrate.solve_ivp` with explicit event functions for velocity,
temperature, composition, and domain termination. Record the solver method,
tolerances, rejected steps, and event that ended the integration.

## 17. Axisymmetric ray-segment construction

For each image-plane ray:

```text
1. Intersect the ray with the plume domain bounding volume.
2. Find every crossing with axial/radial cell boundaries.
3. Sort unique path parameters s.
4. Form intervals between adjacent crossings.
5. Sample the midpoint of each interval to identify the owning field cell.
6. Drop zero-length or outside-domain intervals.
7. Return ordered back-to-front segments with path length and local state.
```

Analytic cylinder and conical-frustum intersections should be used where
possible. General polygon-of-revolution intersections require deterministic
root finding and duplicate-root merging.

## 18. Radiative-transfer marching

For each spectral coordinate and ordered segment,

\[
I_{i+1}
=
I_i e^{-\Delta\tau_i}
+B_i\left(1-e^{-\Delta\tau_i}\right).
\]

Numerically stable implementation:

```text
transmittance = exp(-tau)
source_weight = -expm1(-tau)
I = I * transmittance + B * source_weight
```

Use `expm1` so the optically thin limit does not lose precision.

Vectorize over spectral coordinates. Chunk over rays or wavelengths when the
full array would exceed the configured memory budget.

## 19. Spectral cross-section interpolation

Cross-section tables use axes such as

```text
species
wavenumber
log_temperature or temperature
log_pressure or pressure
broadener composition id
```

Interpolation requirements:

```text
no extrapolation without an explicit policy
nonnegative interpolated cross sections
metadata-preserving unit conversion
bounded interpolation error checked against direct reference calculations
cache key includes database version, isotopologue policy, line profile,
wing cutoff, grid, T, p, and broadener definition
```

Interpolation should usually operate on the logarithm of positive cross
sections with a documented floor, followed by nonnegative reconstruction.

## 20. Determinism and reproducibility

All algorithms must be deterministic for fixed inputs unless uncertainty
sampling is explicitly enabled. Monte Carlo paths shall accept and record a
random seed.

A result artifact shall record:

```text
code version
input schema version
model level
solver tolerances
calibration id
spectroscopy database version
random seed when applicable
```

## 21. Acceptance gate

This numerical specification is implemented when:

- every public root solve is bracketed or bounded;
- physical-domain failures are structured statuses;
- the weak/strong shock branches are explicit;
- all geometry intersections enforce forward-ray constraints;
- MOC state compatibility and geometry residuals are separately reported;
- shock-train physical termination is distinct from safety truncation;
- mixing ODE events are explicit and tested;
- RTE marching uses the exact segment solution and stable thin-limit math;
- deterministic regression tests reproduce identical results for identical
  inputs;
- `pytest`, `ruff`, `pyright`, and package build checks pass.
