# Coding-Agent Execution Protocol

## 1. Mission

Implement the handoff plans in dependency order while preserving mathematical
traceability, public compatibility where practical, and strict verification
gates.

Do not optimize for the largest possible code change. Optimize for the smallest
reviewable change that proves one physical or architectural claim.

## 2. Branch policy

Starting branch:

```text
feature/initial-work
```

Recommended phase branches:

```text
feature/foundation-corrections
feature/validated-first-cell
feature/finite-shock-train
feature/integral-mixing-plume
feature/gray-radiative-transfer
feature/spectral-radiation
feature/thermochemistry
```

Within a phase, use issue branches when possible:

```text
task/FND-002-correct-choked-mass-flow
task/FND-005-oblique-shock-roots
```

Do not commit directly to the source branch.

## 3. Required reading before code changes

Read:

```text
README.md
01_model_contract_and_architecture.md
the plan for the active phase
08_validation_and_test_matrix.md
09_issue_backlog.md
this execution protocol
```

Then inspect the current branch versions of all files named by the issue.

If the branch differs materially from the documented source blobs, report the
difference before applying the plan.

## 4. Scope rules

1. Implement only the active issue.
2. Do not bundle unrelated renames, formatting, dependency upgrades, or
   architecture moves.
3. Preserve existing TODOs unless the issue explicitly resolves them.
4. When resolving a TODO, mention it in the completion report.
5. Do not delete working public APIs without a compatibility path or explicit
   migration approval.
6. Do not hide a failed physical solve behind a warning and nominal result.
7. Do not add empirical constants without provenance and applicability fields.
8. Do not call a planar result axisymmetric.
9. Do not claim model validation from unit tests alone.
10. Do not silently change units or angle conventions.

## 5. Python standards

Target:

```text
Python 3.12+
```

Required style:

- Full type annotations on public and private functions.
- `from __future__ import annotations`.
- `numpy.typing.NDArray` for array contracts.
- Pydantic v2 for validated configuration and interchange models.
- NumPy/SciPy for numerical algorithms.
- Pytest for tests.
- Ruff and Pyright clean.
- Concise, durable docstrings focused on contract and assumptions.
- Preserve TODO comments.
- End every newly written or materially modified scope with a standalone
  `####` marker, following the project-owner convention.
- Do not bulk-reformat untouched legacy scopes solely to change existing scope
  markers.

Avoid:

- `Any` where a durable type can be expressed.
- Bare dictionaries as public result contracts.
- Global mutable configuration.
- Hidden unit conversion.
- Catch-all exception handling around numerical failure.
- Unbounded nonlinear root solves when a physical bracket exists.

## 6. Numerical standards

### Root solving

- Prefer bounded scalar solvers.
- Report bracket, iterations, residual, and convergence.
- Validate the physical branch after solving.
- Do not accept a root outside its admissible interval.

### Geometry

- Normalize direction vectors or document scale.
- Return ray parameters.
- Check forward direction.
- Report condition number and residual.
- Reject degenerate geometry.

### ODE integration

- Use state variables tied to conserved fluxes.
- Use event functions for physical termination.
- Retain the last valid state on failure.
- Report solver tolerances and step statistics.

### Arrays

- Validate shape, dtype, finiteness, and monotonic grids.
- Make immutable public arrays read-only.
- Avoid implicit broadcasting in public contracts when dimensions can be
  ambiguous.

## 7. Equation traceability

Every new physics function must include:

```text
equation
assumptions
input units
output units
valid domain
failure behavior
```

A code comment or docstring should refer to the corresponding handoff section
or a stable primary reference.

For a correlation or closure, also include:

```text
calibration source
applicability range
coefficient uncertainty
```

## 8. Test-first expectation

For a known defect:

1. Add a test that fails on the current branch.
2. Confirm the failure represents the documented defect.
3. Implement the smallest correction.
4. Run focused tests.
5. Run the full phase quality gate.

For new capability:

1. Add analytic verification cases.
2. Implement the reference or simplest transparent solver.
3. Add failure and limit cases.
4. Add convergence tests.
5. Only then add performance optimizations.

## 9. Quality commands

Before every completed issue:

```bash
python -m pytest <focused tests>
python -m ruff check <changed paths>
python -m pyright
```

Before every phase PR:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Run the installed-wheel smoke test if package structure or exports changed.

## 10. Commit policy

Use small commits with a clear prefix:

```text
fix(FND-002): correct choked throat-area exponent
test(FND-002): add mass-flow inversion benchmarks
refactor(FND-003): route explicit gas properties
feat(MOC-005): solve ambient-pressure free boundary
docs(TRN-006): document termination result contract
```

A commit should not mix behavior, broad formatting, and unrelated tests.

## 11. Completion report format

Every issue completion report must contain:

### Summary

What changed and why.

### Equations or contracts implemented

List exact equations, branch choices, units, and assumptions.

### Files changed

List paths and purpose.

### Tests added

List test IDs from the validation matrix where possible.

### Commands run

Include exact commands and pass/fail status.

### Numerical evidence

Provide residuals, reference values, or convergence evidence.

### Compatibility

Describe deprecations, wrappers, or schema changes.

### Remaining limitations

State what the implementation still does not model.

### Follow-on issue

Name the next dependency-ready issue.

## 12. Failure protocol

When implementation reveals that the plan is inconsistent with the branch:

1. Stop the affected physical change.
2. Preserve any independent tests or diagnostics that are still valid.
3. Report:
   - branch evidence;
   - violated assumption;
   - smallest plan amendment;
   - affected dependent issues.
4. Do not invent a workaround that weakens physics or hides failure.

## 13. Dependency changes

A new dependency requires:

```text
reason
runtime or optional classification
minimum version
license review note
fallback behavior
CI update
```

SciPy and Pydantic are expected additions. HAPI and Cantera should remain
optional.

## 14. Data and fixture policy

Every external fixture includes:

```text
source
retrieval date
license or usage note
raw/processed distinction
processing script
checksum
units
case metadata
```

Do not manually transcribe large reference datasets without a reproducible
processing script.

## 15. Performance policy

1. Preserve a transparent reference implementation.
2. Profile before optimizing.
3. Add equivalence tests before a faster kernel.
4. Report time and memory for benchmark sizes.
5. Do not sacrifice deterministic results or diagnostics for speed without a
   documented option.

## 16. Documentation policy

Update the relevant handoff/model document when:

- assumptions change;
- a correlation is calibrated;
- a public contract changes;
- a validity boundary is discovered;
- a planned phase is intentionally deferred.

Do not allow code behavior and the mathematical model note to diverge.

## 17. Definition of done

An issue is done only when:

- requested behavior is implemented;
- analytic or regression tests pass;
- failure behavior is tested;
- typing and linting pass;
- assumptions and units are documented;
- no unrelated changes are included;
- completion report is produced.

A phase is done only when its acceptance gate in the phase plan passes.
