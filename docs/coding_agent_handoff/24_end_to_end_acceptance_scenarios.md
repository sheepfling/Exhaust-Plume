# End-to-End Acceptance Scenarios

## 1. Purpose

These scenarios connect the individual phase tests into user-visible model
behavior. They define expected status, invariants, and result structure without
requiring every numerical value to be frozen prematurely.

Each scenario should eventually have:

```text
YAML input fixture
expected-status YAML
small scalar regression JSON
optional NPZ reference arrays
human-readable report or plot generated outside unit tests
```

## 2. Scenario E2E-001 — Matched uniform exit

### Purpose

Verify that the solver does not manufacture shock cells when exit and ambient
pressures match.

### Inputs

Construct total pressure from a selected \(M_e\), \(\gamma\), and
\(p_e=p_a\):

\[
p_0
=
p_a
\left(1+\frac{\gamma-1}{2}M_e^2\right)^{\gamma/(\gamma-1)}.
\]

Use explicit gas properties and a positive exit radius.

### Expected

```text
regime = MATCHED
status = NO_PRESSURE_MISMATCH
cells = empty
shock_train_end_x_m = 0 or null by schema decision
termination_reason = NO_PRESSURE_MISMATCH
was_domain_truncated = false
```

### Invariants

- Exit state round trips to supplied total state.
- No shock total-pressure loss exists.
- `max_cells=0` is accepted.
- Legacy wrapper returns a valid compatibility result without fake cells.

## 3. Scenario E2E-002 — Mild underexpanded first cell

### Purpose

Exercise a clean attached expansion/reflection/compression first-cell path.

### Inputs

Choose target

\[
\frac{p_e}{p_a}=1.10
\]

with moderate supersonic Mach and constant \(\gamma\). Derive \(p_0\) from the
exit ratio rather than selecting an arbitrary total pressure.

### Expected

```text
regime = UNDEREXPANDED
first-cell status = SUCCESS
one or more closed zones
all intersections forward
free-boundary pressure residual below tolerance
centerline angle residual below tolerance
```

### Invariants

- Expansion preserves total pressure and total temperature.
- Compression shock decreases total pressure.
- Closed zones are finite, non-self-intersecting, and positive area.
- First-cell length converges with characteristic refinement.
- Classical circular-jet spacing is reported as a comparison, not forced.

## 4. Scenario E2E-003 — Mild overexpanded exit with validated attached state

### Purpose

Exercise the external attached-shock path without implicitly claiming that
internal nozzle separation is absent.

### Inputs

Choose

\[
\frac{p_e}{p_a}=0.90
\]

and mark the uniform exit state as externally validated or explicitly accepted
for the reduced model.

### Expected

```text
regime = OVEREXPANDED
status = SUCCESS or documented attached-overexpanded status
precursor shock attached
centerline intersection downstream
```

### Invariants

- Precursor distance follows \(R/\tan\beta\).
- Shock pressure rise reaches the target within tolerance.
- Weak-branch shock angle is below the maximum-turn shock angle.
- Total pressure decreases across the shock.

### Negative companion

Run the same pressure ratio without the required validated-exit assumption when
the configured nozzle-separation gate considers it outside scope. Expected:

```text
status = NOZZLE_SEPARATION_NOT_MODELED
no fabricated external cell geometry
```

## 5. Scenario E2E-004 — Strong underexpansion outside attached-cell topology

### Purpose

Verify structured refusal rather than a plausible but invalid weak-shock train.

### Inputs

Select a pressure mismatch known by the model classifier to require a Mach-disk
or detached-shock topology.

### Expected

```text
status = MACH_DISK_REQUIRED or DETACHED_SHOCK_REQUIRED
validity flag identifies active limit
no downstream reduced cells generated as SUCCESS
```

### Invariants

- Maximum attached-turn or pressure-rise test explains the failure.
- Diagnostics retain requested and attainable limits.
- Radiation is blocked unless the caller explicitly supplies another flow
  field.

## 6. Scenario E2E-005 — Finite reduced shock train

### Purpose

Verify that cell count is predicted by termination policy and closure state,
not copied from a user request.

### Inputs

Use a valid first cell plus one calibration artifact. Set `max_cells` and
`max_axial_distance_m` above the expected physical endpoint.

### Expected

```text
cells_completed > 0
termination_reason is physical
was_domain_truncated = false
pressure amplitude decays
coherent-core diameter does not increase under the baseline closure
```

### Sensitivity companions

- Increase inward spreading rate: fewer cells or shorter core.
- Increase pressure-decay coefficient: earlier oscillation termination.
- Reduce safety domain below the physical endpoint: `DOMAIN_LIMIT` and
  `was_domain_truncated=true`.

No test should assert that a universal fixed cell count is correct.

## 7. Scenario E2E-006 — Integral frozen mixing plume

### Purpose

Verify conservative handoff from shock cells to a downstream mixing solution.

### Inputs

Initialize from the final coherent-core cross section with frozen exhaust and
ambient species.

### Expected

```text
mass flow grows through entrainment
velocity approaches ambient
thermal excess approaches ambient
species approach ambient composition
termination_reason = AMBIENT_EQUILIBRIUM or DOMAIN_LIMIT
```

### Invariants

- Integrated mass increase equals entrained mass.
- Momentum-flux residual remains below tolerance.
- Total-enthalpy flux includes ambient entrainment.
- Every species remains nonnegative and normalized.
- Element totals are conserved in the nonreacting model.

## 8. Scenario E2E-007 — Gray homogeneous slab

### Purpose

Establish the exact radiative-transfer baseline independent of plume geometry.

### Inputs

Uniform \(T\), gray \(\alpha\), path length \(L\), and background radiance
\(I_0\).

### Exact result

\[
I_L
=
I_0e^{-\alpha L}
+B_\lambda(T)(1-e^{-\alpha L}).
\]

### Expected

- Numerical result matches analytic result over optically thin and thick ranges.
- Zero opacity returns the background.
- Large optical depth approaches Planck radiance.
- Small optical depth is linear to first order.

## 9. Scenario E2E-008 — Axisymmetric gray cylinder by angle

### Purpose

Verify ray geometry and integrated angular behavior.

### Inputs

A finite isothermal cylinder with constant absorption.

### Geometry reference

For a side-on ray at transverse impact parameter \(b\), the radial chord through
an infinite cylinder is

\[
L(b)=2\sqrt{R^2-b^2}.
\]

For the finite cylinder and general angle, use an independent analytic or
high-resolution geometric reference.

### Expected

- Per-ray path lengths converge to the reference.
- Image symmetry holds.
- Optically thin, fully visible integrated volume emission is approximately
  angle invariant.
- Optical thickness introduces physically explainable angle dependence.

## 10. Scenario E2E-009 — Two-layer self-absorption

### Purpose

Verify path ordering.

### Inputs

A hot emitting layer and a cooler absorbing layer with the same spectral band.

### Expected

```text
hot behind cool != cool behind hot
```

The code must reproduce the analytic two-segment recurrence exactly. Sorting
segments by zone ID instead of line-of-sight distance must fail the test.

## 11. Scenario E2E-010 — Frozen molecular plume spectrum

### Purpose

Connect a prescribed plume field to tabulated molecular cross sections.

### Inputs

- Frozen H2O/CO2/CO mixture or a propellant-appropriate explicit mixture.
- Small spectral window with a checked reference table.
- Axisymmetric temperature/pressure field.
- Several aspect angles.

### Expected

- Mixture opacity equals the number-density-weighted species sum.
- Cross-section interpolation stays inside table bounds.
- Spectral features move only when Doppler support is explicitly enabled.
- Band-integrated signal converges with spectral and image refinement.
- Result records table hashes and species set.

## 12. Scenario E2E-011 — Atmosphere and sensor separation

### Purpose

Verify that intrinsic plume intensity, atmospheric propagation, and detector
response remain distinct stages.

### Expected processing

```text
intrinsic spectral radiant intensity
    → atmospheric transmittance and path radiance
    → range dilution
    → sensor spectral response
```

### Invariants

- Changing range does not alter intrinsic plume intensity.
- Changing sensor response does not alter atmospheric transmission.
- Turning atmosphere off recovers inverse-square propagation.
- Band units are documented and dimensionally consistent.

## 13. Scenario E2E-012 — Upstream validity propagation

### Purpose

Prevent radiation from concealing invalid flow physics.

### Inputs

Use a flow result with `MACH_DISK_REQUIRED` or an out-of-calibration-domain
flag.

### Expected

- Default orchestration does not produce a nominally valid signature.
- An explicit expert override may render a supplied approximate field, but the
  radiation result carries all upstream validity flags.
- Serialized output identifies the override and model discrepancy risk.

## 14. Scenario fixture structure

```text
tests/scenarios/
  e2e_001_matched/
    input.yaml
    expected.yaml
  e2e_002_mild_underexpanded/
    input.yaml
    expected.yaml
  ...
```

`expected.yaml` should contain statuses, tolerances, and invariants—not large
opaque arrays.

Example:

```yaml
scenario_id: e2e_001_matched
expected:
  regime: matched
  status: no_pressure_mismatch
  cell_count: 0
checks:
  total_pressure_relative_residual_max: 1.0e-10
  total_temperature_relative_residual_max: 1.0e-10
```

## 15. Regression policy

Freeze exact scalar values only when they represent:

- analytic equations;
- stable contractual behavior;
- or a reviewed scientific reference fixture.

For iterative model outputs, prefer tolerance bands, conservation residuals,
convergence trends, and topology/status checks over bitwise equality.

## 16. End-to-end gate

- [ ] Matched flow yields zero cells.
- [ ] Mild underexpansion closes one validated cell.
- [ ] Mild overexpansion handles or rejects nozzle validity explicitly.
- [ ] Strong mismatch returns a topology status.
- [ ] Shock train terminates physically when the domain permits.
- [ ] Integral plume conserves fluxes.
- [ ] Gray RTE matches exact slabs.
- [ ] Ray geometry matches analytic chords.
- [ ] Layer ordering changes self-absorption correctly.
- [ ] Molecular spectra record table provenance.
- [ ] Atmosphere and sensor stages remain separable.
- [ ] Upstream validity flags propagate through every result.
