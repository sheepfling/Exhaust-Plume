# Phase 1 Validated First-Cell Task Packets

## 1. Purpose

This document converts the validated first-cell plan into reviewable pull
requests. Phase 1 begins only after the complete Phase 0 gate passes.

The Phase 1 deliverable is one verified planar first shock cell for:

```text
matched flow
mild underexpansion
mild attached overexpansion with a validated exit state
```

Strong underexpansion requiring a Mach disk, detached shocks, and internal
nozzle separation remain structured out-of-validity results.

## 2. Entry gate

Required evidence before work starts:

```text
correct gas/nozzle contracts
correct choked equation
branch-safe area--Mach and PM inverses
weak/strong shock limits
maximum attached-turn detection
forward-ray intersections
explicit regime classification
matched-flow zero-cell behavior
no public NaN closed zones
all Phase 0 quality commands pass
```

Primary branch:

```text
feature/validated-first-cell
```

## 3. Packet MOC-A — Characteristic primitives and PM inverse hardening

### Maps to

```text
MOC-001
MOC-002
```

### Goal

Create immutable characteristic contracts and a high-confidence radians-based
Prandtl--Meyer inverse suitable for grid marching.

### Expected files

```text
src/exhaust_plume/models/shock_cells/characteristics.py
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/util/aero/prandtl_meyer.py
tests/src/models/shock_cells/test_characteristic_contracts.py
tests/src/util/aero/test_prandtl_meyer.py
```

### Required implementation

- `CharacteristicFamily` with stable `c_plus` and `c_minus` values.
- `CharacteristicPoint` containing point, \(M\), \(\theta\), \(\mu\), \(\nu\),
  \(K_+\), and \(K_-\).
- `CharacteristicSegment` containing family, endpoints, state provenance, and
  residuals.
- PM inverse using the algorithm in Document 13.
- Exact domain handling at \(M=1\) and \(\nu=0\).
- Explicit maximum PM angle.

### Tests

```text
nu(M) monotonic for M > 1
M -> nu -> M round trip across representative Mach values
nu = 0 returns M = 1
nu near maximum has bounded behavior
out-of-range nu is rejected
K invariants match theta and nu
contracts are immutable and finite
```

### Done when

- no characteristic code uses degree-valued internal fields;
- PM inversion has residual and bracket diagnostics;
- characteristic serialization has stable family names.

## 4. Packet MOC-B — Interior and centerline point solvers

### Maps to

```text
MOC-003
MOC-004
```

### Goal

Implement planar compatibility and averaged-slope geometry for interior and
centerline characteristic points.

### Expected files

```text
src/exhaust_plume/models/shock_cells/planar_characteristics.py
tests/src/models/shock_cells/test_planar_interior_point.py
tests/src/models/shock_cells/test_planar_centerline_point.py
```

### Governing equations

\[
K_+=\theta-\nu,
\qquad
K_-=\theta+\nu.
\]

At a \(C^+/C^-\) intersection:

\[
\theta_P=\frac{K_++K_-}{2},
\qquad
\nu_P=\frac{K_--K_+}{2}.
\]

At the centerline:

\[
y=0,
\qquad
\theta=0.
\]

### Required implementation

- Pure `solve_interior_characteristic_point` function.
- Pure `solve_centerline_characteristic_point` function.
- Averaged endpoint slope iteration.
- Forward-intersection enforcement.
- Separate state-compatibility and geometry residuals.
- Structured no-intersection and ill-conditioning statuses.

### Tests

```text
synthetic invariant intersection with analytic state
symmetric sources produce centerline-consistent point
swapping source order preserves the physical point when families are swapped
averaged-slope refinement reduces geometry residual
parallel characteristic failure
backward intersection failure
centerline theta exactly zero
invariant residual below tolerance
```

### Done when

- compatibility is not implemented as coordinate reflection alone;
- returned point is downstream of both source rays;
- tests separate state and geometry convergence.

## 5. Packet MOC-C — Ambient-pressure free-boundary solver

### Maps to

```text
MOC-005
```

### Goal

Replace the unconstrained polynomial plume boundary with a boundary point solver
that satisfies pressure and streamline conditions.

### Expected files

```text
src/exhaust_plume/models/shock_cells/free_boundary.py
tests/src/models/shock_cells/test_free_boundary.py
```

### Governing conditions

\[
p_b=p_a,
\qquad
\frac{dr_b}{dx}=\tan\theta_b.
\]

The boundary state also satisfies the incoming characteristic invariant.

### Required implementation

- Calculate boundary Mach from \(p_0/p_a\) for the isentropic segment.
- Recover boundary \(\theta\) from the incoming invariant.
- Intersect the incoming characteristic and prior-boundary tangent as forward
  rays.
- Iterate averaged slopes.
- Return pressure, compatibility, tangent, and geometry residuals.
- Preserve the old parabola only as an opt-in diagnostic comparison, not the
  successful default path.

### Tests

```text
boundary pressure equals ambient
boundary tangent equals flow angle
incoming invariant preserved
forward geometry
matched boundary state degenerates cleanly
nonphysical boundary Mach is rejected
legacy parabola comparison does not affect returned solution
```

### Done when

- successful first-cell code can construct a boundary without polynomial fit;
- every boundary point contains residual diagnostics;
- no hidden global ambient pressure is used.

## 6. Packet MOC-D — Mild underexpanded first-cell assembly

### Maps to

```text
MOC-006
MOC-008 partial
```

### Goal

Assemble a complete closed first cell for a mildly underexpanded circular jet
using the planar characteristic and free-boundary primitives.

### Expected files

```text
src/exhaust_plume/models/shock_cells/first_cell.py
src/exhaust_plume/models/shock_cells/underexpanded.py
tests/src/models/shock_cells/test_underexpanded_first_cell.py
```

### Required algorithm

```text
1. Compute exit pressure mismatch.
2. Compute ambient-pressure boundary Mach and total PM turn.
3. Discretize the expansion fan.
4. March characteristics to the centerline.
5. Apply centerline compatibility.
6. March reflected characteristics to the free boundary.
7. Construct the recompression/shock closure using Phase 0 shock validity.
8. Produce closed zones only after topology validation.
9. Report first-cell length and all residuals.
```

### Required input cases

Use target static pressure ratios, for example:

```text
p_e / p_a = 1.02
p_e / p_a = 1.10
p_e / p_a = 1.50
```

The strongest case is accepted only if it remains within the implemented
attached topology.

### Tests

```text
correct UNDEREXPANDED classification
positive downstream cell length
ambient-pressure free boundary
centerline theta = 0
closed polygons finite, positive area, and non-self-intersecting
expansion states preserve stagnation pressure and temperature
compression shocks reduce stagnation pressure
result independent of source object mutation
```

### Done when

- one complete mild-underexpanded first cell is returned without legacy
  parabola fallback;
- all successful zones pass topology checks;
- failure cases return structured partial diagnostics.

## 7. Packet MOC-E — Mild attached overexpanded first-cell assembly

### Maps to

```text
MOC-007
MOC-008 remaining
```

### Goal

Assemble the external first-cell topology for a mildly overexpanded jet when the
uniform exit state is explicitly declared valid.

### Expected files

```text
src/exhaust_plume/models/shock_cells/overexpanded.py
tests/src/models/shock_cells/test_overexpanded_first_cell.py
```

### Required algorithm

```text
1. Require nozzle_solution_validated = true or a validated exit profile id.
2. Solve the lip shock needed for pressure adjustment.
3. Reject detached or disallowed strong-branch requirements.
4. Intersect the shock with the centerline using R / tan(beta).
5. Apply downstream shock state and centerline compatibility.
6. Continue the characteristic/free-boundary construction.
7. Validate closed-zone topology and residuals.
```

### Input cases

```text
p_e / p_a = 0.98
p_e / p_a = 0.90
one case requiring detached shock
one case blocked because nozzle exit was not validated
```

### Tests

```text
correct OVEREXPANDED classification
shock pressure ratio reaches the target within tolerance
precursor geometry matches beta
weak branch used for mild case
detached case returns DETACHED_SHOCK_REQUIRED
unvalidated strongly overexpanded exit returns NOZZLE_SEPARATION_NOT_MODELED
closed-zone topology passes for successful mild cases
```

### Done when

- the solver distinguishes external attached flow from nozzle-separation
  uncertainty;
- no strong or detached case is forced through the mild topology.

## 8. Packet MOC-F — First-cell correlation, convergence, and gate

### Maps to

```text
MOC-009
MOC-010
Phase 1 gate
```

### Goal

Add equivalent fully expanded jet properties, first-cell scale correlation,
resolution convergence, external benchmark fixtures, and release evidence.

### Expected files

```text
src/exhaust_plume/models/shock_cells/fully_expanded.py
src/exhaust_plume/models/shock_cells/correlations.py
tests/src/models/shock_cells/test_fully_expanded.py
tests/src/models/shock_cells/test_first_cell_convergence.py
tests/src/validation/test_first_cell_reference_cases.py
docs/validation/first_cell_phase_1_report.md
```

### Required equations

\[
M_j
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}-1
\right]
}.
\]

\[
\frac{A_j}{A_e}
=
\frac{\mathcal A(M_j)}{\mathcal A(M_e)},
\qquad
D_j=D_e\sqrt{A_j/A_e}.
\]

\[
L_{s,0}=1.306D_j\sqrt{M_j^2-1}.
\]

The correlation is a comparison metric, not a value imposed on the solved
geometry.

### Convergence study

Run at least three characteristic resolutions with an approximately constant
refinement ratio. Track:

```text
first-cell length
maximum radius
boundary pressure residual
centerline location
integrated zone area
maximum invariant residual
```

Estimate observed order where the data are in the asymptotic range. Do not
claim order from nonmonotonic coarse data.

### Validation fixtures

Add repository fixtures from approved primary sources for at least one
moderate-Mach circular jet. Store source, extraction method, units, and
uncertainty. Keep calibration and validation roles explicit even though Phase 1
has no fitted decay coefficients.

### Tests

```text
fully expanded state preserves total conditions
D_j and L_s are positive and dimensionally scaled
correlation scales linearly with D_e
matched flow reference returns no first-cell correlation claim
first-cell metrics converge with fan refinement
solver residuals decrease or meet tolerance under refinement
external reference error is reported, not hidden by loose assertion
```

### Phase 1 report

The report must include:

```text
implemented equations
model assumptions
underexpanded and overexpanded cases
convergence tables
correlation comparison
external-data comparison
validity failures
timing and memory measurements
known model-form uncertainty
```

### Done when

- all Phase 1 manifest gates pass;
- one underexpanded and one mild attached overexpanded cell converge;
- matched flow returns zero cells;
- detached and unvalidated separation cases are explicit;
- the free boundary meets pressure and tangent residuals;
- first-cell geometry has a documented convergence study;
- the implementation remains clearly labeled planar.

## 9. Packet dependency graph

```text
MOC-A contracts and PM inverse
   ↓
MOC-B interior/centerline
   ↓
MOC-C free boundary
   ├───────────────┐
   ↓               ↓
MOC-D underexpanded  MOC-E overexpanded
   └───────┬───────┘
           ↓
MOC-F convergence and validation gate
```

MOC-D and MOC-E may proceed in parallel after MOC-C if their shared assembly
interfaces are stable.

## 10. Phase 1 stop conditions

Stop and request review when:

```text
a first-cell case requires a Mach disk
a shock requires a detached or unapproved strong branch
a uniform overexpanded exit is not validated
the free-boundary solve has no forward intersection
zone topology changes under small tolerance perturbations
fan refinement does not approach a stable solution
correlation mismatch is large and unexplained
the implementation begins adding downstream empirical decay or mixing
```

A stopped case is valuable validation evidence. It must not be converted into a
nominal successful cell by adding geometry hacks.
