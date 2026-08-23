# Migration, Release, and Compatibility Plan

## 1. Purpose

The current package has a small public API and an installed-wheel smoke test.
This plan introduces corrected contracts without forcing an immediate breaking
rewrite of every existing caller.

The migration must preserve two truths simultaneously:

1. Old calls remain runnable for a documented compatibility interval.
2. New scientific results never hide legacy dry-air assumptions, naming errors,
   or user-selected cell count behind the corrected API.

## 2. Current public surface

The reviewed branch exports these names from `exhaust_plume`:

```text
MODULE_NAME
VERSION
__version__
EngineParameters
ExpansionFanState
FlowState
ObliqueShockState
ZoneCoordinates
ZoneResult
ZoneType
calcNozzleExitFlowState
calculatePlumeZones
```

The migration should keep these importable while adding the new canonical API.

## 3. Compatibility phases

## Phase C0 — Additive foundation

- Add new modules and canonical APIs.
- Preserve current exports unchanged.
- Add tests for both surfaces.
- Correct internal equations where behavior was objectively defective.
- Emit no deprecation warning for imports alone.

## Phase C1 — Runtime deprecation

- Legacy function calls emit typed warnings.
- Warning text identifies the replacement and hidden assumptions.
- Serialized new results use only new names.
- Documentation examples prefer the new API.

## Phase C2 — Legacy adapter isolation

- Move old behavior entirely under `exhaust_plume.compat`.
- Top-level exports re-export those adapters.
- Internal production modules do not import compatibility modules.
- CI runs a dedicated legacy suite.

## Phase C3 — Removal decision

Before 1.0, the project may remove legacy APIs only after:

```text
at least one documented release boundary
migration guide published
known first-party consumers migrated
legacy usage measured or explicitly accepted
```

If 1.0 is approaching, freeze the final compatibility decision in a separate
ADR.

## 4. Function migration

## 4.1 Nozzle exit

Legacy:

```python
calcNozzleExitFlowState(
    mach,
    total_temperature,
    total_pressure,
    gamma,
)
```

Canonical:

```python
derive_uniform_nozzle_exit(
    config: IsentropicNozzleExitConfig,
) -> NozzleExitState
```

Legacy adapter behavior:

```text
construct explicit dry-air gas model
emit LegacyDryAirAssumptionWarning
call canonical implementation
return legacy FlowState view
record source_kind = LEGACY_DRY_AIR_ADAPTER
```

Do not silently alter the legacy density result before the warning/adaptation
path exists; otherwise existing regressions become difficult to interpret.

## 4.2 Plume-zone solve

Legacy:

```python
calculatePlumeZones(
    nozzle_mach,
    nozzle_total_temperature,
    nozzle_total_pressure,
    nozzle_radius,
    atmospheric_pressure,
    gamma,
    num_expansion_lines,
    num_compression_lines,
    num_plumes,
)
```

Canonical:

```python
solve_shock_cells(
    config: ShockCellSolveConfig,
) -> ShockCellSolveResult
```

Mapping:

| Legacy parameter | Canonical field | Notes |
|---|---|---|
| `nozzle_mach` | `exit.mach` | same physical quantity |
| `nozzle_total_temperature` | `exit.total_temperature_K` | units made explicit |
| `nozzle_total_pressure` | `exit.total_pressure_Pa` | units made explicit |
| `nozzle_radius` | `exit.radius_m` | same physical quantity |
| `atmospheric_pressure` | `ambient.pressure_Pa` | ambient temperature/composition supplied by adapter |
| `gamma` | `exit.gas.gamma` | legacy gas remains explicit dry air |
| `num_expansion_lines` | `num_expansion_characteristics` | resolution control |
| `num_compression_lines` | legacy construction option | no direct long-term physical contract |
| `num_plumes` | `max_cells` | deprecated semantic rename |

The wrapper returns the current tuple shape during compatibility. New
diagnostics may be added under:

```text
details['solver_diagnostics_v1']
```

without deleting `points` or `plume_fit` until the compatibility boundary.

## 5. Type and field migration

## 5.1 FlowState

Legacy fields:

```text
mach
static_pressure
static_temperature
static_density
gamma
```

Canonical fields:

```text
mach
static_pressure_Pa
static_temperature_K
density_kgpm3
flow_angle_rad
gas
```

Legacy property aliases remain read-only and emit no warning for simple scalar
access during the first compatibility stage. Construction through legacy field
names is deprecated sooner than property access.

## 5.2 ZoneResult

Legacy `ZoneResult` combines state, transition metadata, and geometry. The
canonical model separates:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

Adapter rules:

- A canonical `ClosedZone` maps directly to a geometry-bearing legacy result.
- A transition without closed geometry maps to a legacy object with
  `coordinates=None`, not a fabricated `NaN` polygon, after the public type is
  made optional.
- Consumers requiring geometry must use an explicit closed-zone predicate.

## 5.3 Enum migration

Map legacy `ZoneType` values to canonical transition kinds:

| Legacy | Canonical |
|---|---|
| `Isentropic` | `ISENTROPIC` or state-only zone classification |
| `ExpansionFan` | `PRANDTL_MEYER_EXPANSION` |
| `ObliqueShock` | `OBLIQUE_SHOCK` |

Do not infer global regime from a local zone type.

## 6. CLI migration

Current CLI options remain accepted while aliases are added:

```text
--num-plumes          deprecated alias of --max-cells
--num-expansion-lines deprecated alias of --num-expansion-characteristics
```

New required or recommended options:

```text
--molecular-weight-kgpmol
--specific-gas-constant-jpkgk
--pressure-match-relative-tolerance
--max-axial-distance-m
--model-level
--calibration-id
```

Legacy CLI defaults that imply dry air must print a concise warning to stderr
and include the assumption in output diagnostics.

`--help` should group options by:

```text
nozzle exit
ambient
gas model
shock-cell numerics
termination
output/plotting
```

## 7. Package dependency migration

Current core dependencies are small. Add dependencies only when used by base
runtime paths.

### Core candidates

```text
numpy
scipy
pydantic >= 2
pyyaml
```

### Extras

```toml
plot = ["matplotlib"]
quality = ["pyright", "ruff"]
test = ["pytest", "build", "matplotlib"]
spectroscopy = ["hapi-package-name-as-verified"]
chemistry = ["cantera"]
all = ["...union of optional runtime extras..."]
```

Verify the actual distribution name before adding an HAPI dependency. Large
HITEMP datasets are data artifacts, not wheel dependencies.

## 8. Python and type-checking migration

The target is Python 3.12+ and fully typed new code.

Recommended sequence:

1. Change package metadata and CI matrix.
2. Change `pyrightconfig.json` to Python 3.12.
3. Enable strict checking on new packages.
4. Keep basic checking on untouched legacy modules.
5. Move a legacy module to strict when materially modified.
6. Include tests in type checking only after fixtures and test helpers have a
   manageable annotation policy.

Do not claim project-wide strict typing while most legacy files remain outside
the checked set.

## 9. Serialization migration

Legacy tuple/dictionary return values are not a durable archive format.
Introduce:

```text
schema_version
package_version
model_level
calibration_id
units
array artifact references
```

Migration rules:

- Readers accept older schema versions through explicit migration functions.
- Writers emit only the newest schema.
- Field renames are recorded in a migration table.
- Large arrays are referenced by content hash.
- Pickle is not an interchange format.

## 10. Test migration

Maintain three distinct suites:

```text
canonical API tests
legacy compatibility tests
installed-wheel smoke tests
```

The installed smoke test must verify:

- Package metadata and resources.
- Optional plotting is not installed by the core wheel.
- Legacy top-level import and call.
- Canonical gas/nozzle call.
- Canonical matched-flow zero-cell result.
- CLI `--help` from outside the checkout.

When a warning is expected, assert its exact class and important message
content rather than globally suppressing it.

## 11. Versioning and changelog

Every release note should separate:

```text
correctness fixes
new canonical APIs
deprecations
scientific model changes
calibration/data changes
known validity limits
```

A corrected governing equation is not merely an internal refactor; it belongs
under correctness and may change numerical outputs.

Calibration-only changes must identify the calibration artifact and should not
be hidden inside an unrelated patch release without documentation.

## 12. Rollback strategy

Every migration PR should be reversible without deleting scientific fixtures.

- Keep adapters isolated.
- Avoid irreversible data-format changes without a reader migration.
- Tag or record the last branch commit before each phase gate.
- Retain baseline numerical outputs for diagnosing changes, even when those
  outputs were physically wrong; label them as legacy regressions.

Rollback must not restore a known equation defect as the canonical path. It may
restore compatibility behavior behind a warning while the corrected path is
repaired.

## 13. Compatibility completion checklist

- [ ] Current top-level imports remain available during the declared interval.
- [ ] New APIs require explicit gas properties.
- [ ] Old dry-air behavior is visible through typed warnings and metadata.
- [ ] `num_plumes` maps to `max_cells` with conflict detection.
- [ ] Legacy tuple shape remains tested until removal.
- [ ] New result schemas are versioned.
- [ ] CLI aliases and warnings are tested.
- [ ] Core wheel imports without optional dependencies.
- [ ] Installed smoke covers legacy and canonical calls.
- [ ] Changelog distinguishes equations, APIs, and calibration changes.
