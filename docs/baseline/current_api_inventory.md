# Current API Inventory

Baseline captured on 2026-08-22 from commit `86195b394048ed97f876879041ad4d7af48a963f`.
The working branch is `feature/plume-interface-foundation`.

## Package identity

| Item | Current value |
| --- | --- |
| Distribution | `exhaust-plume` |
| Package version | `0.1.0.a0` |
| Python requirement | `>=3.10` in `pyproject.toml` |
| Core dependencies | `numpy`, `pyyaml` |
| Optional extras | `plot`, `quality`, `test` |
| Console script | `exhaust-plume` -> `exhaust_plume.models.plume.run_plume_solve:main` |

## Root exports

`exhaust_plume.__all__` currently exposes:

- Metadata: `MODULE_NAME`, `VERSION`, `__version__`.
- Flow states: `FlowState`, `ExpansionFanState`, `ObliqueShockState`.
- Geometry/results: `ZoneCoordinates`, `ZoneResult`, `ZoneType`.
- Solver helpers: `calcNozzleExitFlowState`, `calculatePlumeZones`.
- Motor helper: `EngineParameters`.

## Main solver contract

`calculatePlumeZones(...)` accepts finite scalar values for:

| Input | Current convention |
| --- | --- |
| `nozzle_mach` | Supersonic Mach number, `> 1` |
| `nozzle_total_temperature` | K |
| `nozzle_total_pressure` | Pa |
| `nozzle_radius` | m |
| `atmospheric_pressure` | Pa |
| `gamma` | Ratio of specific heats, `> 1` |
| `num_expansion_lines` | Integer, `>= 2` |
| `num_compression_lines` | Integer, `>= 1` |
| `num_plumes` | Integer, `>= 1` |

It returns `(list[ZoneResult], dict[str, Any])`. `ZoneResult` is a frozen
dataclass containing a `FlowState`, plume/group indices, a string label,
`ZoneType`, `beta`/`theta`, and `ZoneCoordinates`. The details mapping
currently contains construction `points` and a fitted `plume_fit` diagnostic.
The public details mapping is not a typed immutable contract.

`ZoneCoordinates.corners_ru` is a read-only NumPy array in the right/up plane.
Legacy public angle fields remain degrees, while new shock-validity and
geometry routines use radians as their canonical units.

## Supporting public surfaces

- `EngineParameters` stores mass flow, exit radius, total pressure and
  temperature, gamma, and molar mass; it derives exit area, throat area, exit
  Mach, total density, and static state properties.
- `FlowState` and its shock/expansion subclasses expose static state plus
  derived total state, Mach angle, sound speed, speed, and specific total
  energy.
- Aerodynamic relation modules provide isentropic, Prandtl–Meyer, normal-shock,
  oblique-shock, ideal-gas, and speed-of-sound functions.
- Atmosphere helpers provide scalar/array PDAS-style layered atmosphere states.
- Visualization helpers revolve planar geometry into meshes and calculate
  projected areas; plotting is an optional dependency.

## CLI surface

The runner supports `--show-plots`, `--num-plumes`, `--altitude-m`,
`--num-expansion-lines`, `--num-compression-lines`, `--nozzle-pressure-atm`,
`--nozzle-temperature-K`, `--nozzle-mach`, `--nozzle-radius`, and `--gamma`.
The CLI supplies study defaults and converts nozzle pressure from atm at the
boundary; the core solver receives Pa.

## Reviewed source blobs

The handoff’s reviewed blobs match the current branch:

| File | Git blob SHA |
| --- | --- |
| `src/exhaust_plume/models/plume/plume_solve.py` | `25768f15afafa5863f5cb30a0aaee0d8a04aaf8d` |
| `src/exhaust_plume/models/plume/motor_parameters.py` | `ad3a436ef5c971c64a0291e136dfa0cba7eb020e` |
| `src/exhaust_plume/util/aero/oblique_shock.py` | `8d98ccd5820052832ff8e210f7e5931574a893a3` |
| `docs/mathematical_model.tex` | `6758309c7af8ffa306d9f6ddee9e76539cdf02b6` |

## Current model classification

The implementation is an inviscid, constant-`gamma`, planar shock-cell
construction with approximate reflected-boundary geometry. It does not yet
provide a provider/session/snapshot lifecycle, explicit generic capabilities,
validated axisymmetric gas dynamics, physical plume termination, mixing,
thermochemistry, or spectral radiation.
