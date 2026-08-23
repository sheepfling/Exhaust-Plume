# Release Gates and Definition of Done

## 1. Purpose

This document defines what evidence is required before a phase, branch, or
release may be called complete. Passing unit tests alone is insufficient for a
scientific codebase; each phase needs equation verification, numerical
convergence evidence, validity behavior, documentation, and reproducible
artifacts.

## 2. Evidence classes

Every phase report shall classify evidence as:

```text
E0 source review
E1 algebraic/unit verification
E2 conservation verification
E3 numerical convergence verification
E4 correlation or external-data validation
E5 uncertainty and applicability evidence
E6 packaging and consumer integration evidence
```

No external-data agreement should compensate for failed algebra or
conservation.

## 3. Common continuous-integration matrix

Minimum supported CI after the Python baseline migration:

```text
Python 3.12: full tests, Ruff, Pyright, build, installed-wheel smoke
Python 3.13: full or compatibility test lane when dependencies support it
Linux: required
Windows or macOS: at least one portability lane before stable release
```

Optional dependencies use separate lanes:

```text
plot
spectroscopy
chemistry
all-extras integration
```

The core installation shall remain usable without spectroscopy or chemistry
extras.

## 4. Common quality commands

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Additional release checks:

```text
install built wheel in a fresh environment
run import smoke test outside repository
run CLI --help and one minimal solve
validate JSON/YAML schemas
verify handoff/validation artifact checksums
```

## 5. Test expectations

### 5.1 Critical physics paths

Every equation branch and every structured failure branch must be exercised.
Coverage percentage is secondary to branch inventory, but critical equation
modules should have no known untested branch.

### 5.2 Regression tests

A regression fixture must record:

```text
case id
input schema version
model level
expected output and tolerance
reason the value is trusted
source equation or validation reference
whether value is a legacy anchor or corrected-physics anchor
```

### 5.3 Property tests

Where practical, use randomized/property tests for invariants:

```text
positive thermodynamic state
round-trip transformations
monotonic PM function
shock total-pressure loss
forward intersection symmetry
species sum and elemental conservation
nonnegative opacity
RTE limiting behavior
```

Random tests use fixed seeds in CI.

## 6. Numerical convergence requirements

A numerical solver is not phase-complete until a refinement study exists for
its dominant discretization.

### 6.1 Characteristic solver

Refine characteristic count and track:

```text
first-cell length
maximum radius
boundary pressure residual
centerline state
zone area
invariant residual
```

### 6.2 ODE mixing solver

Refine ODE tolerances and output sampling independently. Verify conserved
fluxes and event location stability.

### 6.3 Ray tracer

Refine image resolution, axial/radial field resolution, and intersection
thresholds separately.

### 6.4 Spectral solver

Refine spectral grid, cross-section interpolation grid, and line-wing cutoff or
band model settings.

### 6.5 Acceptance pattern

For output \(Q_h\) at refinement scale \(h\), report

\[
\Delta_h=|Q_h-Q_{h/r}|.
\]

Where asymptotic behavior is observed, estimate order

\[
p
\approx
\frac{\ln\left(|Q_h-Q_{h/r}|/|Q_{h/r}-Q_{h/r^2}|\right)
}{\ln r}.
\]

A nonmonotonic sequence must be reported and investigated; it is not evidence
of convergence merely because the finest two values look close.

## 7. Performance regression policy

Performance is measured only on validated benchmark cases. Record:

```text
wall time
peak resident memory
problem dimensions
hardware and software environment
backend
```

A PR that slows a benchmark materially must explain the tradeoff. Initial
policy: investigate regressions greater than 20% in median runtime or memory,
but do not reject a correctness fix solely to preserve a flawed fast path.

Benchmark thresholds become release gates only after stable baseline hardware
or normalized CI benchmarks are established.

## 8. Documentation gate

Every completed phase updates:

```text
public API documentation
governing equations and assumptions
validity limits
input/output units
example configuration
failure/status interpretation
validation report
migration notes when public behavior changes
```

Code comments should cite equation identifiers or source documents, not repeat
long derivations.

## 9. Artifact reproducibility gate

Every validation or calibration result includes:

```text
input file
code commit or version
schema version
calibration id/version
source data ids and checksums
solver tolerances
random seed if applicable
commands to reproduce
machine-readable metrics
plots as derived artifacts
```

A plot without its generating data and command is not sufficient evidence.

# Phase gates

## 10. Phase 0 — Foundation corrections

### Entry

- Current branch baseline recorded.
- Existing public API inventory generated.

### Required evidence

```text
correct throat-area equation
area--Mach branch inversion
explicit gas molecular weight
stagnation enthalpy semantics
weak/strong zero-turn limits
maximum attached-turn detection
target-pressure shock validity
forward ray intersection
corrected precursor geometry
matched-flow classification
legacy migration behavior
```

### Exit

- All Phase 0 tests and quality commands pass.
- No successful public closed zone contains nonfinite coordinates.
- Corrected behavior changes have migration notes.
- Wheel and CLI smoke tests pass.
- Phase 0 report is committed.

## 11. Phase 1 — Validated first cell

### Entry

Complete Phase 0 gate.

### Required evidence

```text
PM inverse verification
interior characteristic compatibility
centerline compatibility
ambient-pressure free boundary
mild underexpanded cell
mild attached overexpanded cell
detached/separation validity failures
closed-zone topology
fan-resolution convergence
first-cell correlation comparison
at least one external reference family
```

### Exit

- Matched flow returns zero cells.
- Underexpanded and mild overexpanded reference cases converge.
- Boundary pressure and tangent residuals pass.
- Centerline \(\theta=0\) residual passes.
- No case requiring a Mach disk is mislabeled successful.
- Phase 1 validation report is committed.

## 12. Phase 2 — Finite shock train

### Entry

Complete Phase 1 gate and approved calibration schema.

### Required evidence

```text
coherent-core shrinkage closure
pressure-amplitude decay closure
local cell spacing
physical termination
safety truncation
calibration provenance
sensitivity and identifiability
calibration/validation split
```

### Exit

- Cell count is an output.
- Physical and safety endpoints are distinguishable.
- Calibration applicability is checked at runtime.
- Uncertainty or sensitivity is reported.
- No illustrative calibration is a production default.

## 13. Phase 3 — Integral mixing plume

### Entry

Complete Phase 2 gate and a defined shock-train exit-state mapping.

### Required evidence

```text
mass balance
axial momentum balance
total enthalpy balance
frozen species balance
entrainment closure
state recovery
ODE convergence
equilibrium persistence events
axisymmetric field reconstruction
```

### Exit

- Conservative flux residuals pass.
- Zero-entrainment limit is verified.
- The field approaches ambient in enabled equilibrium cases.
- Physical and domain termination remain separate.
- Phase 3 report includes closure applicability.

## 14. Phase 4 — Gray radiative transfer

### Entry

A finite axisymmetric plume field or analytic test geometry is available.

### Required evidence

```text
Planck function and units
homogeneous slab analytic solution
zero-opacity limit
optically thin limit
optically thick limit
layer ordering
analytic chord lengths
ray-segment ordering
orientation-integral check
IR-domain termination
```

### Exit

- Exact segment RTE matches analytic cases.
- Ray geometry converges.
- Successful images contain finite nonnegative radiance.
- IR endpoint is not conflated with flow endpoint.

## 15. Phase 5 — Molecular spectral radiation

### Entry

Complete Phase 4 gate and approved spectroscopy-data policy.

### Required evidence

```text
cross-section generation reference
units and spectral-coordinate Jacobians
T/p interpolation error
mixture opacity
cache provenance
spectral convergence
atmosphere/sensor separation
heated-plume validation
```

### Exit

- Cross sections reproduce direct reference calculations within tolerance.
- Spectral/band outputs converge.
- Database/version metadata is preserved.
- At least one measured or authoritative plume-radiation case is compared.

## 16. Phase 6 — Thermochemistry and particles

### Entry

Complete Phase 3 and Phase 5 gates.

### Required evidence

```text
composition conversion
mixture thermodynamics
enthalpy inversion
CEA import provenance
frozen and equilibrium limits
elemental conservation
finite-rate energy coupling
particle zero limit
particle optical-table provenance
```

### Exit

- Species mass fractions and elements balance.
- Energy release matches species enthalpy change.
- Frozen chemistry recovers Phase 5 behavior.
- Particle-off behavior recovers the molecular model.
- Chemistry and particle optional dependencies are isolated.

## 17. Phase 7 design gate

Before axisymmetric CFD or flight effects begin, approve a separate design that
selects:

```text
axisymmetric MOC, internal finite volume, or external CFD coupling
turbulence closure
Mach-disk topology handling
nozzle-profile interface
chemistry coupling
GPU strategy
validation datasets
```

Phase 7 must not emerge accidentally as scattered patches to the reduced-order
solver.

# Release definitions

## 18. Research preview release

May contain provisional calibrations and limited model levels. Must clearly
state:

```text
not validated for certification or operational prediction
supported regimes
known missing physics
example versus validated calibration status
```

## 19. Beta release

Requires:

- all gates for advertised model levels;
- stable schema major version;
- migration guide;
- external validation report;
- uncertainty/applicability metadata;
- packaged examples and installed-wheel tests.

## 20. Stable release

Requires:

- no known critical correctness defect in advertised regimes;
- at least one independent validation family per advertised high-level output;
- documented public API support policy;
- calibration/data provenance and licensing review;
- reproducible release artifacts;
- changelog and migration notes.

## 21. Definition of done for an issue

An issue is done only when:

```text
scope implemented
non-goals remain untouched
equations/contracts traceable
tests cover success and failure paths
numerical residuals reported
public compatibility addressed
docs updated
quality commands pass
completion report supplied
follow-on limitations identified
```

## 22. Definition of done for a pull request

A PR is done only when:

- linked issues are complete;
- review comments are resolved;
- no hidden coefficient, unit, or validity assumption was introduced;
- changes are small enough to review coherently;
- CI and local quality evidence agree;
- generated artifacts are reproducible;
- the merge target remains in a releasable state.

## 23. No-go conditions

Do not release an advertised capability when:

```text
a known wrong equation remains on the active path
a root failure is logged but returned as success
matched flow creates shock cells
detached/Mach-disk cases are forced through attached topology
successful geometry contains NaNs or self intersections
calibration and validation data overlap without disclosure
spectral units or coordinate Jacobians are ambiguous
chemistry violates elemental or energy conservation
large model-form limitations are hidden from output metadata
```

## 24. Final phase-report template

```text
Phase and version
Scope completed
Equations/contracts implemented
Source and calibration provenance
Verification matrix
Convergence evidence
Validation evidence
Uncertainty/sensitivity
Performance
Public API/schema changes
Known limits and no-go regimes
Reproduction commands
Release recommendation: GO / GO WITH LIMITATIONS / NO-GO
```
