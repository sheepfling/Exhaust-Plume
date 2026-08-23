# First Execution Wave: Coding-Agent Work Plan

## 1. Purpose

This document expands the immediate queue in
`34_comprehensive_work_plan.md` into a branch- and PR-level execution plan.
It covers the work needed to reach:

```text
M0  reproducible baseline
M1  provider contract foundation
M2  corrected physics foundation and exit-state boundary
M3  ShockCellAnalyticalProvider
M10 SignatureTableProvider, in an independent parallel lane
```

No method-of-characteristics replacement, finite shock-train calibration,
integral mixing implementation, curved-plume dynamics, or production radiation
physics belongs in this execution wave.

## 2. Wave completion state

At the end of this wave:

- signature and spatial consumers are represented by stable capability
  contracts;
- fake providers prove that geometry is optional;
- generic plume physics no longer hides dry-air properties;
- nozzle mass-flow, energy/enthalpy, oblique-shock limits, regime
  classification, and precursor geometry are corrected;
- successful public closed zones contain no placeholder nonfinite geometry;
- legacy total-condition and new exit-state APIs share one corrected core;
- the corrected analytical solver is exposed through neutral spatial
  capabilities;
- a direct signature-table provider serves the signature use case without any
  geometry dependency;
- Phase 1 MOC work can begin without reopening provider or foundation
  semantics.

## 3. Dependency and merge sequence

```text
M0 baseline
   |
   +---------------------------+
   |                           |
   v                           v
M1 / I0 provider contracts   M2 / FND-A gas/nozzle contracts
   |                           |
   v                           v
I0 conformance              FND-B nozzle/enthalpy corrections
                               |
                         +-----+-----+
                         |           |
                         v           v
                      FND-C        FND-D
                      shocks       geometry
                         |           |
                         +-----+-----+
                               v
                             FND-E
                    regime/results/migration
                               |
                               v
                             FND-F
                       foundation gate
                               |
                               v
                              I1
                    exit-state core boundary
                               |
                    +----------+----------+
                    |                     |
                    v                     v
                 M3 / I2              M10 / I6
        analytical spatial provider   signature table
```

`M10 / I6` may begin after M1 and merge independently of M2/M3 because it has
no dependency on analytical shock-cell physics.

## 4. M0 — Architecture and repository baseline

### Branch

```text
chore/plume-baseline-inventory
```

### Required work

- Record repository commit, package version, source branch, and reviewed file
  SHAs.
- Run and record:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

- Install the built wheel in a fresh environment and run imports and CLI help
  outside the repository.
- Inventory public functions, classes, enums, CLI options, return structures,
  and documented unit conventions.
- Capture current representative numerical outputs without labeling them as
  physically correct merely because they are reproducible.
- Classify fixtures as:

```text
legacy_anchor
corrected_anchor
untrusted_visual_anchor
```

- Review the open decisions in Document 26 and confirm that none blocks M1 or
  M2.

### Deliverables

```text
docs/baseline/current_api_inventory.md
docs/baseline/current_quality_results.md
tests/fixtures/legacy_baseline/
```

### Gate

No behavior changes. A clean checkout can reproduce the baseline evidence.

## 5. M1 / I0 — Provider contract foundation

### Branch

```text
feature/provider-contract-foundation
```

### Required reading

```text
00_unified_plume_architecture.md
28_consumer_profiles_and_query_contracts.md
29_provider_taxonomy_and_composition.md
30_provider_contracts_v1.md
31_unified_conformance_and_testing.md
33_coding_agent_interface_kickoff_prompt.md
```

### Expected package structure

```text
src/exhaust_plume/contracts/
  capability.py
  descriptor.py
  errors.py
  execution.py
  provenance.py
  radiometry.py
  snapshot.py
  spatial.py

src/exhaust_plume/providers/
  __init__.py
```

### Required contracts

- `PlumeProvider`.
- `PlumeSession`.
- `PlumeSnapshot`.
- `CapabilityId` and explicit major versions.
- `PlumeProviderDescriptor`.
- `ProviderFidelity`.
- `ProviderExecutionProfile`.
- `ProviderApplicability`.
- `PlumeProvenance`.
- Typed provider, lifecycle, domain, and capability errors.
- Canonical plume-local frame and source-to-observer direction semantics.

### Fake providers

1. Signature-only provider with no geometry.
2. Spatial-only provider with no radiation.
3. Ray-transfer provider that also exposes native directional intensity.
4. Provider with snapshot invalidation semantics.

### Conformance tests

- Capability registry equals actual capability objects.
- Unsupported capability and major-version mismatch fail explicitly.
- Definition/configuration/state inputs are not mutated.
- Public arrays are immutable or defensively copied.
- Deterministic providers repeat exactly.
- Signature wavelength and direction validation.
- Axisymmetric directional symmetry.
- Ray miss returns zero source radiance and unit transmittance.
- Rich-to-simple integration equivalence for the fixture provider.
- Provenance, applicability, and snapshot retention are preserved.

### Non-goals

- No adaptation of `calculatePlumeZones`.
- No new plume physics.
- No external-consumer dependency.
- No spectroscopy or curved-plume equations.

### Gate

All provider conformance tests pass and the current solver API remains
unchanged.

## 6. M2 / FND-A — Explicit gas and nozzle contracts

### Branch

```text
feature/gas-nozzle-contracts
```

### Required reading

```text
01_model_contract_and_architecture.md
02_foundation_corrections_plan.md
14_api_contracts_and_serialization.md
16_equation_traceability_matrix.md
20_phase_0_patch_blueprint.md
21_phase_0_foundation_task_packets.md
```

### Expected files

```text
src/exhaust_plume/models/gas/contracts.py
src/exhaust_plume/models/nozzle/contracts.py
src/exhaust_plume/models/nozzle/exit_state.py
```

### Required contracts

- `GasProperties` or equivalent frozen gas model.
- `NozzleExitState`.
- `AmbientState`.
- Explicit SI-unit field names.
- Internal radians.
- Molecular-weight / specific-gas-constant consistency.
- Optional normalized frozen species fractions.

### Tests

- Positive finite validation.
- Molecular weight and gas constant consistency.
- Species normalization, duplicate rejection, and immutable state.
- Serialization round trip where the contract is serializable.

### Non-goals

No changes to shock or plume geometry.

## 7. M2 / FND-B — Correct nozzle equations and energy semantics

### Branch

```text
fix/nozzle-foundation-equations
```

### Depends on

FND-A.

### Required equation

\[
A^*=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{
\frac{\gamma+1}{2(\gamma-1)}
}.
\]

### Work

- Add a forward choked mass-flow helper.
- Correct throat-area inversion.
- Verify area--Mach branch inversion.
- Route explicit gas properties through generic nozzle/plume calculations.
- Add precise static and total enthalpy properties.
- Deprecate ambiguous historical energy naming.
- Verify:

\[
h_0=h+\frac{u^2}{2}=c_pT_0.
\]

### Tests

- Forward/inverse choked mass flow.
- Supersonic area--Mach inversion.
- Molecular-weight sensitivity of density, sound speed, velocity, and mass
  flux.
- Isentropic static/total round trips.
- Total-enthalpy identity.
- Explicit deprecation behavior.

## 8. M2 / FND-C — Oblique-shock branches and validity

### Branch

```text
fix/oblique-shock-validity
```

### Depends on

FND-B. May be developed in parallel with FND-D after shared contracts merge.

### Work

- Implement bounded weak and strong roots of the
  \(\theta\)-\(\beta\)-\(M\) relation.
- Enforce:

\[
\lim_{\theta\rightarrow0}\beta_{weak}
=\sin^{-1}(1/M),
\qquad
\lim_{\theta\rightarrow0}\beta_{strong}=\pi/2.
\]

- Compute maximum attached turn.
- Return `DETACHED_SHOCK_REQUIRED` or equivalent structured validity.
- Add target-pressure feasibility checks.
- Report root residual and bracket diagnostics.

### Tests

- Weak and strong zero-turn limits.
- Branch ordering and residual across a grid.
- Below/above maximum-turn behavior.
- Shock mass/momentum/energy conservation.
- Total-pressure loss and total-temperature conservation.

## 9. M2 / FND-D — Geometry primitives and precursor correction

### Branch

```text
fix/plume-geometry-primitives
```

### Depends on

FND-B. May be developed in parallel with FND-C.

### Work

- Replace point-only pseudoinverse intersection with a diagnostic result:

```text
point
parameter_1
parameter_2
condition_number
residual
status
```

- Require forward ray parameters for physical intersections.
- Reject parallel, near-parallel, backward, and high-residual cases.
- Correct the overexpanded precursor centerline distance:

\[
\Delta x=\frac{R}{\tan\beta}.
\]

- Use radians internally.
- Separate flow transitions, characteristic segments, shock segments, and
  closed zones.

### Tests

- Exact orthogonal intersection.
- Parallel and ill-conditioned rejection.
- Backward intersection rejection.
- Analytic forty-five-degree precursor case.
- Regression against the degree/cosine defect.
- Closed-zone finiteness and topology checks.

## 10. M2 / FND-E — Regime, results, terminology, and compatibility

### Branch

```text
feature/corrected-plume-results
```

### Depends on

FND-C and FND-D.

### Work

- Add explicit `UNDEREXPANDED`, `MATCHED`, and `OVEREXPANDED` regimes.
- Classify with:

\[
r_p=\frac{p_e-p_a}{p_a}
\]

  and a documented tolerance.
- Matched flow returns zero cells and `NO_PRESSURE_MISMATCH`.
- Rename repeated plume passes to cells or construction passes in new APIs.
- Retain legacy `num_plumes` only through a documented wrapper.
- Prevent invalid/open geometry from appearing as a successful `ClosedZone`.
- Add structured validity and termination reports.
- Replace misleading tests with cases built from target \(p_e/p_a\).

### Gate

The corrected result model is additive, migration behavior is explicit, and no
second legacy physics implementation exists.

## 11. M2 / FND-F — Foundation quality gate

### Branch

```text
chore/foundation-phase-gate
```

### Work

- Update equations, units, limitations, and migration documentation.
- Update equation registry and ADRs.
- Run full quality and installed-artifact checks.
- Confirm no successful public closed zone contains nonfinite coordinates.
- Record Phase 0 evidence under the classes in Document 27.

### Gate

Every Phase 0 criterion in Document 27 passes before I1 or M3 merges.

## 12. M2 / I1 — Corrected exit-state core boundary

### Branch

```text
refactor/exit-state-core-boundary
```

### Depends on

M1 contracts and FND-F gate.

### Required architecture

```text
legacy calculatePlumeZones(total conditions, ...)
  -> corrected NozzleExitState
      -> calculatePlumeZonesFromExitState(...)
          -> optional legacy result adapter
```

### Tests

- Equivalent legacy/new inputs reach the same corrected core result.
- Explicit gas properties propagate through every state.
- No duplicated shock or geometry solve exists.
- Provider definition/state can bind directly to the exit-state path.

## 13. M3 / I2 — `ShockCellAnalyticalProvider`

### Branch

```text
feature/shock-cell-analytical-provider
```

### Depends on

M1 and M2 complete.

### Initial capabilities

```text
spatial-support v1
axisymmetric-zone-field v1
projected-area v1
```

### Work

- Convert corrected solver output into neutral provider products.
- Do not expose legacy `ZoneResult` through generic capabilities.
- Preserve planar-flow provenance and geometry quality status.
- Expose applicability, validity, and termination separately.
- Advertise no spectral capability yet.

### Tests

- Provider/direct-solver numerical equivalence.
- Conservative spatial support.
- Invalid geometry is rejected rather than exported.
- Legacy construction limits are marked nonphysical.
- Capability absence fails explicitly.

## 14. M10 / I6 — `SignatureTableProvider`

### Branch

```text
feature/signature-table-provider
```

### Depends on

M1 only. This branch may proceed independently of M2 and M3.

### Work

- Define a versioned signature-table asset schema.
- Implement wavelength, direction, and optional time interpolation.
- Reject extrapolation by default.
- Include asset digest, coordinate convention, interpolation policy, and
  validity in provenance.
- Expose only `directional-spectral-intensity` unless an asset explicitly
  contains another standard capability.

### Tests

- Exact grid-point reproduction.
- Deterministic interpolation.
- Direction convention and symmetry.
- Extrapolation rejection.
- Asset-digest provenance.
- Same consumer code works against constant and table providers.

## 15. Conflict ownership

| Area | Owner packet | Other packets must not change |
|---|---|---|
| Provider lifecycle and capability semantics | I0 | physics equations |
| Gas/nozzle contracts | FND-A | provider capability semantics |
| Mass flow and enthalpy | FND-B | shock geometry |
| Oblique-shock solver | FND-C | line-intersection implementation |
| Geometry primitives | FND-D | shock thermodynamic equations |
| Regime/results/migration | FND-E | duplicate core equations |
| Quality/evidence | FND-F | unreviewed physics behavior |
| Exit-state boundary | I1 | provider-specific physics duplication |
| Analytical adapter | I2 | legacy behavior except via shared wrapper |
| Signature table | I6 | geometry assumptions |

A shared-contract change requires an ADR amendment and explicit review before
parallel branches rebase.

## 16. Wave-wide quality gate

Run:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Then:

- install the built wheel in a fresh environment;
- import and run CLI help outside the repository;
- execute one matched-flow solve;
- run the provider conformance suite;
- validate serialized schemas;
- compare legacy and exit-state paths;
- verify public array immutability;
- update ADR, equation, migration, manifest, and changelog records.

## 17. Stop condition

Do not begin `MOC-A` through `MOC-F` until M0, M1, M2, and M3 have passed their
gates. `SignatureTableProvider` may merge after M1 because it does not rely on
analytical plume physics.
