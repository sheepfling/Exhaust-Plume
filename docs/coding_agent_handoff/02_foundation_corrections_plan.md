# Foundation Corrections Implementation Plan

## 1. Purpose

Correct known defects in the existing branch before adding new geometry,
mixing, radiation, or chemistry. This phase is complete only when every item
below has a focused regression test and the full quality gate passes.

## 2. Files in scope

Primary:

```text
src/exhaust_plume/models/plume/motor_parameters.py
src/exhaust_plume/models/plume/plume_solve.py
src/exhaust_plume/util/aero/flow_state.py
src/exhaust_plume/util/aero/oblique_shock.py
src/exhaust_plume/util/aero/normal_shock.py
src/exhaust_plume/util/aero/isentropic_flow.py
tests/src/models/plume/test_motor_parameters.py
tests/src/models/plume/test_plume_solver.py
tests/src/util/aero/
```

New modules may be introduced under `models/gas`, `models/nozzle`, and
`models/shock_cells`, but existing APIs must retain compatibility wrappers.

## 3. FND-001: Correct choked throat area

### Existing defect

The existing exponent in the throat-area equation is twice the correct value.

### Correct equation

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

### Implementation

Replace the exponent:

```python
(gamma + 1.0) / (gamma - 1.0)
```

with:

```python
(gamma + 1.0) / (2.0 * (gamma - 1.0))
```

Refactor the mass-flow function into a forward helper:

```python
calc_mass_flow_rate(...)
```

and verify that throat-area and mass-flow calculations invert one another.

### Tests

- Parameterized values of \(\gamma\), \(R\), \(T_0\), \(p_0\), and \(A^*\).
- Compare against the closed-form forward relation.
- Verify monotonicity:
  - larger \(A^*\) gives larger \(\dot m\);
  - larger \(p_0\) gives larger \(\dot m\);
  - larger \(T_0\) gives lower \(\dot m\) for fixed \(A^*\).

## 4. FND-002: Honor gas molecular weight everywhere

### Existing defect

The active nozzle state and one `EngineParameters` density path use dry-air
molecular weight even when another molecular weight is supplied.

### Correct equations

\[
R=\frac{R_u}{W},
\qquad
\rho=\frac{p}{RT}.
\]

### Implementation

Add one explicit gas input to every state-construction path:

```text
specific_gas_constant_JpkgK
```

or:

```text
molecular_weight_kgpmol
```

Prefer a `GasProperties` contract carrying both with consistency validation.

Remove dry-air imports from generic plume/nozzle calculations. Keep dry air
only as an explicit default in atmosphere-specific code or compatibility
wrappers.

### Tests

For identical \(p,T,\gamma,M\), compare two gases:

\[
\frac{\rho_1}{\rho_2}=\frac{R_2}{R_1}.
\]

Verify:

- density changes with molecular weight;
- speed of sound changes with \(R\);
- Mach remains unchanged when explicitly supplied;
- velocity changes as \(M\sqrt{\gamma RT}\).

## 5. FND-003: Correct total-energy naming

### Existing defect

The current property named `specific_total_energy_Jpkg` returns:

\[
\frac{p_0}{\rho_0}=RT_0.
\]

This is neither total enthalpy nor total specific energy.

### Implementation

Add:

```text
specific_gas_work_Jpkg = p / rho
specific_total_enthalpy_Jpkg = cp * T0
specific_total_energy_Jpkg = cv * T + u^2 / 2
```

Use precise names. Deprecate the old property with a compatibility warning if
it is public.

For constant \(\gamma\),

\[
c_p=\frac{\gamma R}{\gamma-1},
\qquad
c_v=\frac{R}{\gamma-1}.
\]

### Tests

Verify:

\[
h_0=h+\frac{u^2}{2}
\]

and, for the calorically perfect model,

\[
h_0=c_pT_0.
\]

## 6. FND-004: Correct weak-shock zero-turn behavior

### Existing defect

The current oblique-shock implementation forces \(\beta=90^\circ\) for
\(\theta=0\) on both branches.

### Correct limits

Weak branch:

\[
\boxed{
\lim_{\theta\to0}\beta=\mu=\sin^{-1}(1/M)
}
\]

Strong branch:

\[
\boxed{
\lim_{\theta\to0}\beta=\pi/2.
}
\]

### Implementation

Separate branch handling explicitly. Avoid exact equality as the only trigger;
use a small-angle limit that remains numerically stable.

Prefer solving the \(\theta\)-\(\beta\)-\(M\) residual with a bounded root
solver over relying only on the closed cubic expression:

\[
f(\beta)
=
\tan\theta
-
2\cot\beta
\frac{M^2\sin^2\beta-1}
{M^2(\gamma+\cos2\beta)+2}.
\]

Weak root bracket:

\[
\beta\in(\mu,\beta_{\max}).
\]

Strong root bracket:

\[
\beta\in(\beta_{\max},\pi/2).
\]

Use `scipy.optimize.brentq` or `root_scalar(..., method="brentq")`.

### Tests

- \(\theta=0\) weak branch equals Mach angle.
- \(\theta=0\) strong branch equals \(\pi/2\).
- Small positive turns converge continuously.
- Weak angle is less than strong angle.
- Returned residual is below configured tolerance.

## 7. FND-005: Detect detached shocks

### Correct criterion

An attached solution exists only when:

\[
\theta\le
\theta_{\max}(M,\gamma)
=
\max_{\mu<\beta<\pi/2}\theta(M,\beta,\gamma).
\]

### Implementation

Add:

```text
calc_max_attached_turn(...)
solve_oblique_shock_angle(...)
```

Return `DETACHED_SHOCK_REQUIRED` when the requested turn exceeds the maximum.

Do not log an error and return a nominal state.

### Tests

- A turn slightly below \(\theta_{\max}\) succeeds.
- A turn slightly above \(\theta_{\max}\) fails structurally.
- The failure contains \(M,\gamma,\theta,\theta_{\max}\).

## 8. FND-006: Add matched-flow regime

### Existing defect

The current `p_e <= p_a` branch treats exact pressure matching as
overexpansion and then requires at least one constructed pass.

### Correct classifier

\[
r_p=\frac{p_e-p_a}{p_a}.
\]

\[
|r_p|\le\epsilon_p
\Rightarrow
\text{MATCHED}.
\]

### Implementation

Add a regime enum:

```text
UNDEREXPANDED
MATCHED
OVEREXPANDED
```

For matched flow:

```text
zones = [nozzle_exit_zone]
cells = []
status = NO_PRESSURE_MISMATCH
```

Permit `max_cells = 0`.

### Tests

Use values derived directly from a target exit-pressure ratio:

```text
p_e / p_a = 0.90
p_e / p_a = 1.00
p_e / p_a = 1.10
```

Do not identify regimes through arbitrary total-pressure values.

## 9. FND-007: Correct precursor line geometry

### Existing defect

The precursor centerline intersection currently uses a degree-valued angle
inside `cos` and uses the wrong geometric relation.

### Correct geometry

For radial drop \(R\) and shock angle \(\beta\) measured from the axis,

\[
\boxed{
\Delta x=\frac{R}{\tan\beta}.
}
\]

### Implementation

Use internal radians:

```python
delta_x_m = radius_m / np.tan(shock_angle_rad)
```

Validate:

```text
delta_x_m > 0
finite(delta_x_m)
shock_angle_rad in (0, pi/2)
```

### Tests

- Hand-calculated line intersections for several angles.
- Exact \(45^\circ\) case gives \(\Delta x=R\).
- Geometry rejects near-zero or non-forward angles.

## 10. FND-008: Replace unvalidated line intersections

### Existing defect

A pseudoinverse produces a least-squares point even for parallel or backward
rays.

### Correct ray model

\[
\mathbf x_i(s_i)=\mathbf o_i+s_i\mathbf d_i,
\qquad
s_i\ge0.
\]

Solve:

\[
\mathbf o_1+s_1\mathbf d_1
=
\mathbf o_2+s_2\mathbf d_2.
\]

### Result contract

```text
RayIntersection2D
  point_xy_m
  parameter_1
  parameter_2
  residual_m
  condition_number
  status
```

Accept only if:

\[
s_1\ge-\epsilon_s,\qquad
s_2\ge-\epsilon_s,
\]

\[
\lVert
\mathbf o_1+s_1\mathbf d_1-
\mathbf o_2-s_2\mathbf d_2
\rVert
\le\epsilon_x.
\]

### Tests

- Exact perpendicular intersection.
- Skew numerical case with small residual.
- Parallel rays.
- Nearly parallel ill-conditioned rays.
- Intersection behind one origin.
- Scale invariance under direction-vector normalization.

## 11. FND-009: Remove public `NaN` polygons

### Existing defect

Some intermediate compression states use `NaN` placeholder coordinates.

### Implementation

Separate state transitions from closed regions:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

Only `ClosedZone` has a polygon and can be revolved or ray traced.

For compatibility, existing `ZoneResult` may temporarily wrap either:

```text
coordinates: ZoneCoordinates | None
```

but public geometry consumers must require a closed zone.

### Tests

- Every `ClosedZone` has finite coordinates.
- Polygon area is positive.
- No self-intersection.
- Unclosed transitions cannot enter mesh or radiation code.

## 12. FND-010: Rename repeated “plumes”

### Existing defect

`num_plumes` and `plume_index` describe repeated shock-cell construction passes,
not separate physical plumes.

### Migration

```text
num_plumes → max_cells
plume_index → cell_index
```

Maintain deprecated aliases for one release cycle.

### Tests

- Old keyword produces a deprecation warning.
- Supplying both old and new keywords raises a clear error.
- Serialized output uses new names.

## 13. FND-011: Harden scalar validation

Require:

```text
finite values
gamma > 1
mach > 1 for supersonic routines
pressure > 0
temperature > 0
density > 0
radius > 0
molecular weight > 0
specific gas constant > 0
integer counts are not bool
```

Every invalid state must fail before numerical work starts.

## 14. FND-012: Correct the current regime tests

The current nominal values:

\[
p_0=69\ \mathrm{atm},
\quad
M_e=4.13,
\quad
\gamma=1.33
\]

give:

\[
\frac{p_0}{p_e}=220.454330636,
\]

\[
p_e=0.312989996\ \mathrm{atm}
\]

and, for \(T_0=2000\ \mathrm K\),

\[
T_e=524.330440\ \mathrm K.
\]

At sea-level ambient pressure, this is overexpanded. Rename or replace any test
that calls it underexpanded.

At the branch's 10 km standard-atmosphere state,

\[
p_a\approx26436.27\ \mathrm{Pa},
\]

so the same exit state is mildly underexpanded.

## 15. Required quality gate

Run:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Phase 0 is complete only when:

- all existing tests pass or are deliberately migrated;
- all new defect tests pass;
- no ignored `NaN` or runtime warning is required in the corrected paths;
- no solver logs an error and returns a nominal success result;
- compatibility deprecations are documented.
