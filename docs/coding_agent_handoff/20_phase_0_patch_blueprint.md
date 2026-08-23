# Phase 0 File-by-File Patch Blueprint

## 1. Purpose

This document tells the coding agent exactly how to turn the foundation plan
into a reviewable sequence of patches without beginning first-cell MOC,
shock-train, radiation, or chemistry work.

The branch snapshot reviewed by this handoff exposes the package primarily
through:

```text
src/exhaust_plume/__init__.py
src/exhaust_plume/models/plume/__init__.py
```

The installed-wheel smoke test imports `calculatePlumeZones` from the top-level
package and calls the legacy signature. Preserve that path while introducing
the new API.

## 2. Phase 0 target tree

Create:

```text
src/exhaust_plume/models/gas/
  __init__.py
  contracts.py
  calorically_perfect.py

src/exhaust_plume/models/nozzle/
  __init__.py
  contracts.py
  area_mach.py
  exit_state.py

src/exhaust_plume/models/shock_cells/
  __init__.py
  contracts.py
  regime.py
  geometry.py
  oblique_shock.py

src/exhaust_plume/compat/
  __init__.py
  plume_v0.py

src/exhaust_plume/exceptions.py
src/exhaust_plume/warnings.py
```

Do not move every existing aerodynamic helper in the first patch. Introduce
new modules, route corrected behavior through them, and leave thin legacy
re-exports until downstream tests have migrated.

## 3. Commit sequence

Each numbered group should be independently reviewable and leave the repository
passing focused tests. Squashing may occur only after review if project policy
requires it.

## Commit 0 — Capture the baseline

### Work

- Record the branch HEAD and reviewed file SHAs in the PR description.
- Run the complete current quality suite.
- Add no physics changes.
- Create a short regression note containing current expected failures or
  warnings, if any.

### Commands

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

### Stop condition

If the current branch is already failing, distinguish pre-existing failures
from work introduced by Phase 0 before continuing.

## Commit 1 — Introduce errors, warnings, and validated gas contracts

### New files

```text
src/exhaust_plume/exceptions.py
src/exhaust_plume/warnings.py
src/exhaust_plume/models/gas/contracts.py
src/exhaust_plume/models/gas/calorically_perfect.py
```

### Required types

```text
GasModelKind
GasPropertiesConfig
GasProperties
InvalidStateError
LegacyApiWarning
LegacyDryAirAssumptionWarning
```

### Required equations

\[
R=R_u/W,
\qquad
p=\rho RT,
\qquad
a=\sqrt{\gamma RT}.
\]

### Tests

Create:

```text
tests/src/models/gas/test_contracts.py
tests/src/models/gas/test_calorically_perfect.py
```

Test consistency of `R` and `W`, composition normalization, density, sound
speed, and invalid values.

### Compatibility

Do not change current exports yet.

## Commit 2 — Correct mass flow and throat area

### New or modified files

```text
src/exhaust_plume/models/nozzle/area_mach.py
src/exhaust_plume/models/plume/motor_parameters.py
```

### Required functions

```text
calc_mass_flow_parameter
calc_mass_flow_rate
calc_choked_throat_area
calc_area_mach_ratio
solve_mach_from_area_ratio
```

Use snake-case names for new APIs. Existing camel-style functions remain as
wrappers.

### Required equation

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{
(\gamma+1)/(2(\gamma-1))
}.
\]

### Tests

- Forward/inverse mass-flow round trip.
- Subsonic and supersonic area-Mach roots are distinguished.
- The existing incorrect exponent fails the new regression fixture.
- Array and scalar behavior are either both supported and tested or explicitly
  separated.

## Commit 3 — Add the corrected nozzle-exit state path

### New files

```text
src/exhaust_plume/models/nozzle/contracts.py
src/exhaust_plume/models/nozzle/exit_state.py
```

### Required functions

```text
derive_uniform_nozzle_exit
validate_mass_flow_consistency
```

### Work

- Accept an explicit gas model.
- Derive static state from total state and Mach.
- Derive velocity and mass flow.
- Cross-check supplied mass flow if present.
- Retain total-state round-trip residuals.

### Tests

- Static/total round trip.
- Density and velocity change correctly with molecular weight.
- Mass flow equals \(\rho uA\).
- Inconsistent supplied mass flow returns a failed validation or structured
  diagnostic according to the contract.

## Commit 4 — Correct energy and enthalpy semantics

### Modified files

```text
src/exhaust_plume/util/aero/flow_state.py
src/exhaust_plume/models/gas/calorically_perfect.py
run/plot code that uses specific_total_energy_Jpkg
```

### Work

Add precise properties:

```text
specific_gas_work_Jpkg
specific_static_internal_energy_Jpkg
specific_static_enthalpy_Jpkg
specific_total_energy_Jpkg
specific_total_enthalpy_Jpkg
```

For a calorically perfect gas:

\[
e=c_vT,
\qquad
h=c_pT,
\qquad
E=e+u^2/2,
\qquad
h_0=h+u^2/2.
\]

The old property behavior is preserved only through a deprecation alias whose
warning states that it historically returned \(RT_0\).

### Tests

- Enthalpy identity.
- Total-energy identity.
- Deprecated property warning.
- Plots and tables use the intended physical quantity and correct label.

## Commit 5 — Replace oblique-shock angle logic

### New or modified files

```text
src/exhaust_plume/models/shock_cells/oblique_shock.py
src/exhaust_plume/util/aero/oblique_shock.py
```

### Required functions

```text
theta_from_beta
calc_max_attached_turn
solve_oblique_shock_angle
solve_oblique_shock_to_pressure
```

### Work

- Use radians internally.
- Use analytic zero-turn limits.
- Use bounded scalar optimization/root solving.
- Return diagnostics and explicit detached-shock status.
- Replace nested log-and-continue behavior in pressure equalization.

### Tests

- Weak and strong zero-turn limits.
- Continuity for small turn angles.
- Residual checks.
- Below/above maximum-turn boundary.
- Pressure-target direct solution and unattainable target.

## Commit 6 — Add regime classification and matched-flow result

### New or modified files

```text
src/exhaust_plume/models/shock_cells/regime.py
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/models/plume/plume_solve.py
```

### Work

- Add `ExpansionRegime`.
- Calculate \(r_p=(p_e-p_a)/p_a\).
- Permit `max_cells=0`.
- Return no cells for matched flow.
- Correct current test names and values.

### Tests

Construct total pressure from target ratios:

```text
p_e / p_a = 0.90
p_e / p_a = 1.00
p_e / p_a = 1.10
```

Do not use ambiguous arbitrary total pressures as regime labels.

## Commit 7 — Add robust ray geometry and correct the precursor

### New or modified files

```text
src/exhaust_plume/models/shock_cells/geometry.py
src/exhaust_plume/models/plume/plume_solve.py
```

### Work

- Add `Ray2D` and `RayIntersection2D`.
- Reject parallel, ill-conditioned, backward, or high-residual intersections.
- Replace the precursor distance with \(R/\tan\beta\).
- Convert every internal geometry angle to radians.

### Tests

- Perpendicular, oblique, parallel, nearly parallel, and backward cases.
- Scale invariance under normalized directions.
- Exact 45-degree precursor case.
- Regression for the degree/radian defect.

## Commit 8 — Separate transitions from closed zones

### New or modified files

```text
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/models/plume/plume_solve.py
src/exhaust_plume/models/plume/visualization.py
```

### Work

- Introduce `FlowTransition`, `CharacteristicSegment`, `ShockSegment`, and
  `ClosedZone`.
- Prevent `NaN` placeholder geometry from entering public closed-zone results.
- Make visualization skip or reject non-closed transitions by type rather than
  by checking finiteness.

### Tests

- Polygon finiteness, area, orientation, and self-intersection.
- Transition objects cannot be passed to closed-zone consumers.
- Legacy `ZoneResult` wrapper remains usable.

## Commit 9 — Add compatibility adapters and migrate exports

### New or modified files

```text
src/exhaust_plume/compat/plume_v0.py
src/exhaust_plume/__init__.py
src/exhaust_plume/models/plume/__init__.py
```

### Work

- Preserve all current top-level export names.
- Add new canonical exports.
- Map `num_plumes` to `max_cells`.
- Emit typed deprecation warnings.
- Reject simultaneous old/new keyword specification.
- Preserve legacy dry-air behavior only in the old wrapper and mark it in
  diagnostics.

### Installed-wheel smoke test

Update `tests/installed_smoke.py` to exercise:

1. The legacy `calculatePlumeZones` call.
2. One new validated gas/nozzle call.
3. The matched-flow zero-cell path.
4. Import without optional plotting, spectroscopy, or chemistry packages.

## Commit 10 — Raise the quality baseline

### Modified files

```text
pyproject.toml
pyrightconfig.json
CI workflow files
```

### Work

- Require Python 3.12+.
- Add Pydantic v2 and SciPy if the Phase 0 implementation uses them in the base
  package.
- Move Pyright to Python 3.12.
- Expand type-checking coverage deliberately rather than flipping the complete
  legacy tree to strict in one unreviewable change.
- Add or update build-wheel smoke tests.

### Pyright rollout

Recommended:

```text
new modules: strict
legacy modules: basic until touched
```

Use per-file configuration or separate include groups if required. Every
materially modified function must be fully typed.

## 4. Legacy wrapper behavior

## 4.1 `calcNozzleExitFlowState`

Legacy call:

```python
calcNozzleExitFlowState(
    mach=...,
    total_temperature=...,
    total_pressure=...,
    gamma=...,
)
```

Behavior during compatibility period:

- Construct explicit dry-air `GasProperties`.
- Emit `LegacyDryAirAssumptionWarning` once per call site under normal warning
  filtering.
- Delegate to `derive_uniform_nozzle_exit`.
- Return a legacy-compatible `FlowState` view.

New callers must supply a gas contract.

## 4.2 `calculatePlumeZones`

Legacy behavior:

- Preserve positional and keyword parameters.
- Treat `num_plumes` as deprecated `max_cells`.
- Return the current tuple shape until the compatibility boundary.
- Include new diagnostics in the existing details mapping under a namespaced
  key rather than changing existing keys unexpectedly.

New behavior:

```python
solve_shock_cells(config: ShockCellSolveConfig) -> ShockCellSolveResult
```

## 5. Test file map

Create or expand:

```text
tests/src/models/gas/test_contracts.py
tests/src/models/gas/test_calorically_perfect.py
tests/src/models/nozzle/test_area_mach.py
tests/src/models/nozzle/test_exit_state.py
tests/src/models/shock_cells/test_regime.py
tests/src/models/shock_cells/test_oblique_shock.py
tests/src/models/shock_cells/test_geometry.py
tests/src/models/shock_cells/test_contracts.py
tests/src/compat/test_plume_v0.py
tests/installed_smoke.py
```

Tests should prefer `pytest` parameterization and `numpy.testing` over
`unittest.TestCase` for new modules.

## 6. Pull-request evidence table

The completion report must contain:

| Defect or contract | Failing test before fix | Correct equation or invariant | Final test |
|---|---|---|---|
| Choked exponent | test ID | throat-area equation | test ID |
| Hidden dry air | test ID | \(R=R_u/W\) | test ID |
| Energy naming | test ID | \(h_0=h+u^2/2\) | test ID |
| Weak zero turn | test ID | \(\beta_w=\mu\) | test ID |
| Detached shock | test ID | \(\theta\le\theta_{max}\) | test ID |
| Matched flow | test ID | \(|r_p|\le\epsilon_p\) | test ID |
| Precursor geometry | test ID | \(\Delta x=R/\tan\beta\) | test ID |
| Ray validity | test ID | forward parameters/residual | test ID |
| Closed zones | test ID | finite positive polygon | test ID |
| Legacy API | test ID | adapter mapping | test ID |

## 7. Phase 0 stop rules

Stop and report rather than expanding scope when:

- A correction requires a full first-cell free-boundary redesign.
- The branch has materially changed beyond the reviewed source and the planned
  adapter no longer maps cleanly.
- A legacy consumer requires undocumented behavior that conflicts with the
  corrected equations.
- A proposed root solver cannot produce a bounded residual and validity status.
- Optional chemistry or spectroscopy code is required to pass a base gas-
  dynamics test.

## 8. Phase 0 final gate

- [ ] Every known defect has a focused regression.
- [ ] Full tests pass.
- [ ] Ruff passes.
- [ ] Pyright passes at the documented coverage level.
- [ ] Wheel builds and installs in a clean environment.
- [ ] Legacy and new smoke calls pass.
- [ ] No public closed zone contains `NaN`.
- [ ] No generic gas path imports dry-air constants.
- [ ] No numerical failure logs an error and returns success.
- [ ] No Phase 1 MOC implementation was added prematurely.
