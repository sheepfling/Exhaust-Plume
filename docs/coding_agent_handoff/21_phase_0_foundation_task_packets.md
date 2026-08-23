# Phase 0 Foundation-Corrections Task Packets

## 1. Purpose

This document converts `FND-*` backlog items into a sequence of small,
reviewable pull requests. The coding agent should complete one packet at a time,
run the complete quality gate, and provide the completion report defined in the
execution protocol.

Phase 0 changes mathematical foundations and API contracts. No MOC rewrite,
shock-train decay model, integral plume, or radiation feature belongs in this
phase.

## 2. Phase 0 branch and baseline

Primary integration branch:

```text
feature/foundation-corrections
```

Recommended short-lived branches:

```text
agent/fnd-a-contracts
agent/fnd-b-nozzle-equations
agent/fnd-c-shock-validity
agent/fnd-d-geometry
agent/fnd-e-regime-compat
agent/fnd-f-quality-gate
```

Before Packet FND-A:

```bash
python -m pip install -e '.[test,quality]'
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Record current pass/fail status and do not misattribute pre-existing failures to
a later packet.

## 3. Packet FND-A — Explicit gas and nozzle contracts

### Maps to

```text
FND-001
FND-003 contract portion
FND-013 partial
```

### Goal

Introduce typed, immutable gas/nozzle input contracts and one canonical source
for the specific gas constant without changing the plume geometry yet.

### Required reading

```text
01_model_contract_and_architecture.md
02_foundation_corrections_plan.md sections on gas and nozzle state
14_api_contracts_and_serialization.md sections 3 through 8
```

### Expected files

```text
src/exhaust_plume/models/gas/__init__.py
src/exhaust_plume/models/gas/contracts.py
src/exhaust_plume/models/gas/calorically_perfect.py
src/exhaust_plume/models/nozzle/__init__.py
src/exhaust_plume/models/nozzle/contracts.py
src/exhaust_plume/models/nozzle/exit_state.py
tests/src/models/gas/test_calorically_perfect.py
tests/src/models/nozzle/test_exit_state.py
```

The exact package path may be adjusted to repository conventions, but gas and
nozzle contracts must not remain embedded in `plume_solve.py`.

### Required implementation

- `CaloricallyPerfectGas` or equivalent immutable contract.
- Explicit `gamma` and `molar_mass_kg_per_mol`.
- Derived

  \[
  R=R_u/\overline W.
  \]

- `NozzleExitInput` and `NozzleExitState` contracts.
- Static state derived from total state using the canonical gas.
- Fully typed public methods and NumPy types where arrays are accepted.
- No hidden dry-air default in new APIs.

### Compatibility

The old `calcNozzleExitFlowState` remains callable and delegates to the new
implementation using an explicitly documented dry-air compatibility value.
It emits a diagnostic or deprecation warning only if doing so does not break
existing tests unexpectedly; warning rollout may be deferred to Packet FND-E.

### Tests

```text
specific gas constant matches R_u / molar mass
changing molar mass changes density consistently
static-to-total round trip
velocity equals M sqrt(gamma R T)
invalid gamma, molar mass, pressure, temperature, and Mach are rejected
new public objects are immutable
legacy wrapper reproduces the new dry-air compatibility calculation
```

### Non-goals

```text
variable cp(T)
species chemistry
CEA integration
shock geometry
renaming num_plumes
```

### Done when

- all new and old tests pass;
- no active new gas API imports `MOLAR_MASS_DRY_AIR_kg` internally;
- package-root export changes are documented;
- `ruff` and `pyright` pass for added modules.

## 4. Packet FND-B — Correct nozzle equations and energy naming

### Maps to

```text
FND-002
FND-004
FND-003 remaining implementation
```

### Goal

Correct the choked mass-flow equation, establish branch-explicit area--Mach
inversion, and remove misleading energy terminology.

### Expected files

```text
src/exhaust_plume/models/plume/motor_parameters.py
src/exhaust_plume/models/nozzle/area_mach.py
src/exhaust_plume/util/aero/flow_state.py
tests/src/models/plume/test_motor_parameters.py
tests/src/models/nozzle/test_area_mach.py
tests/src/util/aero/test_flow_state.py
```

### Required equations

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

\[
\frac{A}{A^*}
=
\frac1M
\left[
\frac{2}{\gamma+1}
\left(1+\frac{\gamma-1}{2}M^2\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

\[
h_0=c_pT_0,
\qquad
c_p=\frac{\gamma R}{\gamma-1}.
\]

### Required implementation

- Correct the missing factor of \(1/2\) in the throat-area exponent.
- Implement an explicit `MachBranch` enum or literal for area--Mach inversion.
- Use a bracketed scalar solver according to Document 13.
- Rename or replace `specific_total_energy_Jpkg`.
- Preserve the legacy property as a deprecated alias only if required.
- Correct density property names such as `kgps`/`kpgs` to unit-accurate names,
  retaining aliases where necessary.

### Tests

```text
sonic A/A* = 1
known subsonic and supersonic area--Mach values
area -> Mach -> area round trip on both branches
choked mass flow reconstructed from calculated throat area
molar-mass sensitivity
stagnation enthalpy equals cp T0
legacy energy alias warning and documented numerical meaning
```

### Numerical anchors

Tests should compute reference values independently from the production
function or use high-precision constants checked into the test with the
supporting equation in a comment.

### Non-goals

```text
changing plume geometry
introducing variable gamma
adding shock-train termination
```

### Done when

- the corrected equation is documented in source and mathematical notes;
- no test preserves the incorrect exponent as desired behavior;
- both area--Mach branches have deterministic bracket tests;
- compatibility aliases are covered by migration tests.

## 5. Packet FND-C — Oblique-shock branches and validity

### Maps to

```text
FND-005
FND-006
```

### Goal

Make weak/strong branch behavior explicit, implement the correct zero-turn
limits, and reject detached or unattainable target-pressure shocks.

### Expected files

```text
src/exhaust_plume/util/aero/oblique_shock.py
src/exhaust_plume/util/aero/shock_validity.py
tests/src/util/aero/test_oblique_shock.py
tests/src/util/aero/test_shock_validity.py
```

### Required implementation

- Internal radians.
- `ShockBranch` with stable values.
- `calculate_max_attached_turn(M, gamma)`.
- Branch-specific `solve_shock_angle`.
- Exact limits:

  \[
  \beta_{weak}(0)=\sin^{-1}(1/M),
  \qquad
  \beta_{strong}(0)=\pi/2.
  \]

- Direct target-pressure construction through \(M_{n1}\) and \(\beta\).
- Maximum normal-shock pressure-ratio check.
- Structured `DETACHED_SHOCK_REQUIRED` and strong-branch statuses.
- Verification of downstream state, total-temperature conservation, and
  stagnation-pressure loss.

### Tests

```text
weak zero-turn limit at several Mach numbers
strong zero-turn limit
weak and strong roots satisfy theta-beta-M residual
maximum-turn point is a local maximum
request above theta_max returns detached status
pressure target below upstream is rejected
pressure target above normal-shock limit is rejected
direct target-pressure solution reaches requested pressure
weak-only policy rejects a strong-branch target
```

### Non-goals

```text
Mach-disk geometry
nozzle separation
full first-cell construction
```

### Done when

- no public weak-shock path returns 90 degrees for zero turn;
- all non-solutions are structured and tested;
- old callers receive a compatible exception or result mapping;
- branch selection is explicit in code and serialization.

## 6. Packet FND-D — Robust geometry primitives and precursor fix

### Maps to

```text
FND-008
FND-009
FND-010 geometry portion
```

### Goal

Replace unchecked point-only intersections with forward-ray results and fix the
overexpanded precursor centerline geometry.

### Expected files

```text
src/exhaust_plume/geometry/__init__.py
src/exhaust_plume/geometry/contracts.py
src/exhaust_plume/geometry/intersections.py
src/exhaust_plume/geometry/polygons.py
src/exhaust_plume/models/plume/plume_solve.py
tests/src/geometry/test_intersections.py
tests/src/geometry/test_polygons.py
tests/src/models/plume/test_overexpanded_precursor.py
```

### Required implementation

- `Ray2D` and `RayIntersectionResult`.
- Direct 2-by-2 solve with determinant, condition number, parameters, residual,
  and status.
- Forward-parameter checks.
- Legacy point-only wrapper where needed.
- Parameterized ray--parabola intersection for temporary compatibility.
- Precursor centerline relation:

  \[
  \Delta x=R/\tan\beta.
  \]

- Radian-only trigonometry inside geometry.
- Polygon signed area and self-intersection validation.

### Tests

```text
orthogonal forward rays
intersection at one origin
parallel rays
near-parallel ill-conditioned rays
intersection behind first ray
intersection behind second ray
scale invariance across meter magnitudes
parabola root selection by forward parameter
precursor analytic triangle geometry
polygon area, winding, duplicate vertex, and self-intersection
```

### Non-goals

```text
removing every legacy parabola use
full MOC free boundary
3D mesh generation rewrite
```

### Done when

- successful intersections report positive/near-zero forward parameters;
- no successful result relies on a pseudoinverse least-squares point;
- precursor coordinates satisfy the analytic angle relation;
- geometry failures cannot be mistaken for finite valid polygons.

## 7. Packet FND-E — Regime classification, result separation, and compatibility

### Maps to

```text
FND-007
FND-010 remaining
FND-011
FND-012 partial
```

### Goal

Add explicit matched/underexpanded/overexpanded classification, separate open
transitions from closed zones, and migrate repeated `plume` terminology to
`cell` terminology.

### Expected files

```text
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/models/shock_cells/regime.py
src/exhaust_plume/compat/legacy_plume.py
src/exhaust_plume/models/plume/plume_solve.py
src/exhaust_plume/models/plume/run_plume_solve.py
tests/src/models/shock_cells/test_regime.py
tests/src/compat/test_legacy_plume.py
tests/src/models/plume/test_plume_solver.py
```

### Required implementation

- `ExpansionRegime` enum.
- Dimensionless pressure residual.
- Configurable matched-flow tolerance.
- Matched flow returns zero shock cells.
- `max_cells` safety ceiling in the new API.
- `cell_index` in new result contracts.
- Separate `FlowTransition`, `CharacteristicSegment`, `ShockSegment`, and
  `ClosedZone` types, or the minimum additive subset required to ensure public
  successful closed zones contain no placeholder `NaN` polygons.
- Legacy wrappers for `num_plumes` and `plume_index`.
- Structured termination and validity metadata in `details` compatibility view.

### Regime-controlled test cases

Construct test total pressure from target \(p_e/p_a\), rather than naming a
case from guessed total-pressure values:

```text
0.90 mildly overexpanded
1.00 matched
1.10 mildly underexpanded
2.00 strongly underexpanded validity case
```

### Tests

```text
classification around both tolerance boundaries
matched flow zero-cell behavior
max_cells = 0 safety behavior
legacy num_plumes mapping
new cell_index and old plume_index alias
no successful ClosedZone contains NaN
regression test names match their actual regimes
```

### Non-goals

```text
predicting physical cell count
MOC free-boundary replacement
calibrated shock decay
```

### Done when

- the new API never calls one shock cell a plume;
- matched flow creates no artificial wave system;
- compatibility semantics are explicit;
- current misnamed underexpanded test is corrected or replaced.

## 8. Packet FND-F — Documentation, quality, and Phase 0 gate

### Maps to

```text
FND-012 remaining
FND-013
Phase 0 gate
```

### Goal

Complete the source documentation, migration evidence, equation regressions,
quality configuration, and package validation required before Phase 1.

### Expected files

```text
README.md
docs/mathematical_model.tex
docs/coding_agent_handoff implementation status
pyproject.toml
pyrightconfig.json
.github/workflows/*
tests/installed_smoke.py
tests/src/validation/test_phase_0_gate.py
```

### Required implementation

- Update mathematical documentation with corrected equations and model limits.
- Add API and CLI migration examples.
- Move project baseline to Python 3.12 if approved by repository policy.
- Add or verify Pydantic, SciPy, pytest, Ruff, Pyright, and build dependencies.
- Ensure all new source is in Pyright scope.
- Add wheel-install smoke tests for new public imports.
- Create a machine-readable Phase 0 gate report.

### Required commands

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Also install the built wheel into a clean virtual environment and run the public
API and CLI smoke tests outside the source checkout.

### Phase 0 evidence table

The completion report shall include numerical evidence for:

```text
choked throat equation
area--Mach inversion both branches
molar-mass density effect
stagnation enthalpy
weak and strong zero-turn shock limits
maximum attached turn and detached detection
target-pressure shock
matched-flow zero-cell behavior
forward-ray intersection
corrected precursor geometry
closed-zone finite topology
```

### Done when

- every Phase 0 manifest gate passes;
- the wheel smoke test passes;
- known legacy behavior changes are documented;
- no Phase 1 code is present;
- the coding-agent completion report identifies remaining model-form limits.

## 9. Packet dependency graph

```text
FND-A contracts
   ↓
FND-B nozzle equations and energy
   ↓
FND-C shock validity ─────┐
                         ├─→ FND-E regime/contracts
FND-D geometry ──────────┘
   ↓
FND-F quality gate
```

FND-C and FND-D may proceed in parallel after FND-A/B if they touch separate
files, but they must be integrated before FND-E.

## 10. Phase 0 stop conditions

Stop and request review when:

```text
a public compatibility choice is not covered by Document 15
a required equation conflicts with an existing documented convention
a source test relies on the known incorrect equation
the corrected behavior causes broad unexplained regression beyond the known
change set
a new dependency or schema change is needed beyond the approved plan
a requested shock state is outside the attached-shock model
```

Do not bypass a stop condition with a warning and approximate continuation.
