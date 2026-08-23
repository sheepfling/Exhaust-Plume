# Validated First Shock-Cell Plan

## 1. Purpose

Replace the current point-and-parabola construction with a planar,
method-of-characteristics-style first-cell solver whose equations,
compatibility conditions, free boundary, and failure modes are explicit.

This phase does not claim an axisymmetric solution. Its purpose is to establish
a physically interpretable and numerically convergent first shock cell that can
be compared against theory, experiment, and later higher-fidelity models.

## 2. Scope

Supported:

- Uniform circular-nozzle exit represented by a planar half-domain.
- Constant-\(\gamma\), calorically perfect gas.
- Mild underexpansion.
- Mild overexpansion with an attached weak-shock solution and a validated
  uniform exit state.
- Quiescent ambient pressure.
- One coherent cell.
- Closed, finite zones suitable for later revolution and ray tracing.

Explicitly unsupported in this phase:

- Detached shocks.
- Mach disks or Mach reflection.
- Internal nozzle separation.
- Flight coflow.
- Turbulent mixing within the cell.
- Reacting flow.
- Axisymmetric characteristic source terms.

Unsupported cases return structured status.

## 3. Governing equations

## 3.1 Mach angle

\[
\boxed{
\mu(M)=\sin^{-1}\left(\frac{1}{M}\right).
}
\]

## 3.2 Prandtl-Meyer function

\[
\boxed{
\nu(M)
=
\sqrt{\frac{\gamma+1}{\gamma-1}}
\tan^{-1}
\sqrt{
\frac{\gamma-1}{\gamma+1}(M^2-1)
}
-
\tan^{-1}\sqrt{M^2-1}.
}
\]

The expansion turn is:

\[
\boxed{
\Delta\theta=\nu(M_2)-\nu(M_1).
}
\]

The inverse \(M=\nu^{-1}(\nu,\gamma)\) shall use a bounded scalar root solve on
the supersonic branch.

## 3.3 Planar characteristic slopes

Define:

\[
C^+:
\quad
\frac{dy}{dx}=\tan(\theta+\mu),
\]

\[
C^-:
\quad
\frac{dy}{dx}=\tan(\theta-\mu).
\]

For steady, planar, irrotational, isentropic flow:

\[
\boxed{
K_{C^+}=\theta-\nu=\text{constant along }C^+,
}
\]

\[
\boxed{
K_{C^-}=\theta+\nu=\text{constant along }C^-.
}
\]

At the intersection of a \(C^+\) line carrying \(K_{C^+}\) and a \(C^-\) line
carrying \(K_{C^-}\),

\[
\boxed{
\theta
=
\frac{K_{C^+}+K_{C^-}}{2},
}
\]

\[
\boxed{
\nu
=
\frac{K_{C^-}-K_{C^+}}{2}.
}
\]

Then invert \(\nu\) to recover \(M\).

## 3.4 Characteristic intersection geometry

For an incoming characteristic from point \(A\) with angle
\(\psi_A=\theta_A+\mu_A\), and one from point \(B\) with angle
\(\psi_B=\theta_B-\mu_B\),

\[
y-y_A=\tan\psi_A(x-x_A),
\]

\[
y-y_B=\tan\psi_B(x-x_B).
\]

Solve this as a forward ray intersection and report both ray parameters,
condition number, and residual.

For increased accuracy, use averaged endpoint slopes during grid marching:

\[
\psi_{A\to P}
=
\frac{
(\theta_A+\mu_A)+(\theta_P+\mu_P)
}{2},
\]

\[
\psi_{B\to P}
=
\frac{
(\theta_B-\mu_B)+(\theta_P-\mu_P)
}{2}.
\]

The point solve then becomes a small nonlinear iteration because the endpoint
state and geometry are coupled. Use fixed-point iteration or a bounded
two-variable root solve with residual diagnostics.

## 3.5 Centerline condition

At \(y=0\),

\[
\boxed{\theta=0.}
\]

For a characteristic reaching the centerline, combine its invariant with
\(\theta=0\) to calculate the reflected state.

No line should be reflected through a matrix operation alone; the state
compatibility condition must also be applied.

## 3.6 Free-boundary conditions

The plume boundary is a streamline:

\[
\boxed{
\frac{dy_b}{dx}=\tan\theta_b.
}
\]

For a quiescent ambient and neglected surface tension,

\[
\boxed{p_b=p_a.}
\]

At constant stagnation pressure on an isentropic boundary segment,

\[
\boxed{
M_b
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}
-1
\right]
}.
}
\]

The boundary state must satisfy both the pressure condition and the incoming
characteristic invariant. The boundary point is then found from the incoming
characteristic and a tangent segment whose slope is the local flow angle.

The free boundary must not be replaced by an unconstrained polynomial fit.

## 3.7 Oblique shock equations

For upstream \(M_1\), shock angle \(\beta\), and turn \(\theta\),

\[
\tan\theta
=
2\cot\beta
\frac{
M_1^2\sin^2\beta-1
}{
M_1^2(\gamma+\cos2\beta)+2
}.
\]

Set:

\[
M_{n1}=M_1\sin\beta.
\]

Then:

\[
\frac{p_2}{p_1}
=
1+\frac{2\gamma}{\gamma+1}(M_{n1}^2-1),
\]

\[
\frac{\rho_2}{\rho_1}
=
\frac{(\gamma+1)M_{n1}^2}
{2+(\gamma-1)M_{n1}^2},
\]

\[
\frac{T_2}{T_1}
=
\frac{p_2/p_1}{\rho_2/\rho_1},
\]

\[
M_{n2}^2
=
\frac{
1+\frac{\gamma-1}{2}M_{n1}^2
}{
\gamma M_{n1}^2-\frac{\gamma-1}{2}
},
\]

\[
M_2=\frac{M_{n2}}{\sin(\beta-\theta)}.
\]

The total-pressure ratio is:

\[
\boxed{
\frac{p_{02}}{p_{01}}
=
\left[
\frac{(\gamma+1)M_{n1}^2}
{(\gamma-1)M_{n1}^2+2}
\right]^{\gamma/(\gamma-1)}
\left[
\frac{\gamma+1}
{2\gamma M_{n1}^2-(\gamma-1)}
\right]^{1/(\gamma-1)}.
}
\]

## 4. First-cell data structures

### 4.1 CharacteristicPoint

```text
x_m
y_m
mach
flow_angle_rad
mach_angle_rad
prandtl_meyer_rad
static_pressure_Pa
static_temperature_K
density_kgpm3
total_pressure_Pa
total_temperature_K
source_kind
```

### 4.2 CharacteristicSegment

```text
kind: C_PLUS | C_MINUS
start_point
end_point
invariant_value_rad
intersection_diagnostics
```

### 4.3 ShockSegment

```text
start_point
end_point
upstream_state
downstream_state
shock_angle_rad
turn_angle_rad
total_pressure_ratio
status
```

### 4.4 FreeBoundaryPoint

```text
point
flow_state
boundary_tangent_rad
pressure_residual
characteristic_residual
```

### 4.5 ClosedZone

```text
vertices_xy_m
flow_state
zone_kind
cell_index
area_m2
```

### 4.6 FirstCellResult

```text
regime
characteristic_points
characteristic_segments
shock_segments
free_boundary
closed_zones
cell_start_x_m
cell_end_x_m
cell_length_m
maximum_radius_m
centerline_pressure_extrema_Pa
status
diagnostics
```

## 5. Underexpanded first-cell algorithm

1. Validate the exit state and classify the regime.
2. If matched, return zero cells.
3. Calculate the ambient-pressure boundary Mach \(M_b\).
4. Calculate the total lip expansion:
   \[
   \Delta\theta_{\mathrm{lip}}
   =
   \nu(M_b)-\nu(M_e).
   \]
5. Discretize the expansion fan into \(N\) characteristic states. Use equal
   increments in \(\nu\), not arbitrary equal geometry angles:
   \[
   \nu_i
   =
   \nu_e
   +
   \frac{i}{N}
   (\nu_b-\nu_e).
   \]
6. March the characteristics from the lip to the centerline using forward
   intersection solves and centerline compatibility.
7. Reflect the wave system using characteristic invariants and the
   \(\theta=0\) centerline condition.
8. Solve the free-boundary state and point at every boundary intersection using:
   - incoming characteristic invariant;
   - \(p=p_a\);
   - boundary tangent equal to local flow direction.
9. Where compression requires a discontinuity, solve an attached weak shock.
10. Reject the case if the requested turn exceeds the attached-shock maximum.
11. Build closed zones from ordered, finite vertices.
12. Calculate geometry and conservation diagnostics.
13. Repeat for increasing \(N\) during convergence testing.

## 6. Mild overexpanded first-cell algorithm

The external model may proceed only when the caller certifies a valid uniform
exit state.

1. Calculate the weak-shock solution required to raise pressure toward ambient.
2. Check the maximum attached turn.
3. Construct the lip shock as a forward ray.
4. Apply centerline symmetry at its reflection.
5. Continue with characteristic/free-boundary compatibility.
6. If the required compression is detached, return
   `DETACHED_SHOCK_REQUIRED`.
7. If the pressure ratio or topology indicates a Mach disk, return
   `MACH_DISK_REQUIRED`.
8. If nozzle separation is plausible but no validated exit profile is supplied,
   return `NOZZLE_SEPARATION_NOT_MODELED`.

This phase does not attempt to synthesize a separated nozzle exit.

## 7. First-cell correlation check

Define the fully expanded Mach:

\[
\boxed{
M_j
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}
-1
\right]
}.
}
\]

Define the area-Mach function:

\[
\mathcal A(M)
=
\frac{1}{M}
\left[
\frac{2}{\gamma+1}
\left(
1+\frac{\gamma-1}{2}M^2
\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

Then:

\[
\frac{A_j}{A_e}
=
\frac{\mathcal A(M_j)}{\mathcal A(M_e)},
\]

\[
D_j
=
D_e
\sqrt{
\frac{\mathcal A(M_j)}{\mathcal A(M_e)}
}.
\]

Use the classical nearly adapted circular-jet spacing only as a correlation
check:

\[
\boxed{
L_{s,\mathrm{corr}}
=
1.306D_j\sqrt{M_j^2-1}.
}
\]

Report:

\[
\epsilon_L
=
\frac{
L_{s,\mathrm{solver}}
-
L_{s,\mathrm{corr}}
}{
L_{s,\mathrm{corr}}
}.
\]

Do not force the computed geometry to equal the correlation.

For the branch's illustrative 10 km defaults:

\[
M_j\approx4.25733,
\qquad
D_j\approx2.13332\ \mathrm m,
\]

\[
L_{s,\mathrm{corr}}\approx11.5296\ \mathrm m.
\]

This is a regression anchor, not an experimental truth target.

## 8. Numerical strategy

Use:

```text
scipy.optimize.brentq       bounded scalar inversions
scipy.optimize.root_scalar  equivalent bounded roots
numpy.linalg.solve          well-conditioned 2x2 intersections
numpy.linalg.cond           intersection diagnostics
```

Do not use unconstrained root finding where physical brackets exist.

Every iterative calculation returns:

```text
converged
iterations
final_residual
bracket
status
```

## 9. Verification tests

### State-level

- \(\nu^{-1}(\nu(M))=M\).
- Characteristic invariants remain constant.
- Boundary pressure equals ambient.
- Centerline angle equals zero.
- Expansions preserve \(p_0,T_0\).
- Shocks preserve \(T_0\) and reduce \(p_0\).

### Geometry-level

- Every accepted ray parameter is forward.
- Every closed-zone vertex is finite.
- Every polygon area is positive.
- No polygon self-intersects.
- Adjacent zones share common interfaces within tolerance.
- Free-boundary slope matches local \(\theta\).

### Convergence-level

For fan resolutions \(N,2N,4N\), track:

```text
cell length
maximum radius
centerline pressure extrema
free-boundary pressure residual
```

Require asymptotic reduction in changes before declaring grid convergence.

## 10. Acceptance gate

Phase 1 is complete only when:

1. Matched flow returns zero cells.
2. A mild underexpanded case produces one finite, closed cell.
3. A mild attached overexpanded case produces one finite, closed cell.
4. Detached cases fail structurally.
5. The free-boundary pressure residual meets tolerance.
6. Centerline symmetry meets tolerance.
7. Conservation and total-pressure-loss checks pass.
8. Results converge with fan resolution.
9. Near-adapted first-cell scale is reasonably consistent with the correlation
   and any selected experimental benchmark.
10. The result is labeled `PLANAR_MOC`, not axisymmetric.
