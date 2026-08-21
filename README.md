# Exhaust-Plume

A standalone implementation of a compressible exhaust-plume model.

It contains the zone solver, expansion-fan and oblique-shock relations, nozzle/motor parameter helpers, projected-area calculations, plotting runner, and plume tests.

## Scope

- Underexpanded and overexpanded plume zone construction.
- Prandtl–Meyer expansion fans.
- Isentropic flow relations.
- Normal and oblique shock relations.
- Nozzle area/Mach and motor-parameter helpers.
- 2D zone geometry, revolved 3D meshes, and projected areas.

## Model contract

The model uses SI units internally: pressure in pascals, temperature in kelvin, density in kg/m³, length in meters, and angles in degrees unless a function name or field says otherwise. The current nozzle-exit helper uses the dry-air molar mass; `EngineParameters` accepts an explicit molar mass for engine calculations.

The plume geometry is a method-of-characteristics-style study model with ideal-gas, isentropic, expansion-fan, and oblique-shock relations. It is intended for exploratory engineering studies, not certification analysis. Very low or very high Mach numbers and extreme pressure ratios remain known failure regions.

The governing equations and conservation checks are summarized in [`docs/mathematical_model.tex`](docs/mathematical_model.tex).

## Command-line use

Install the project and run the default study:

```bash
python -m pip install -e '.[plot]'
exhaust-plume --help
exhaust-plume --nozzle-mach 4.13 --nozzle-pressure-atm 69 --nozzle-temperature-K 2000
```

The runner prints the calculated zones. Add `--show-plots` when a graphical session is available.

## Python use

```python
from exhaust_plume import calculatePlumeZones

zones, details = calculatePlumeZones(
    nozzle_mach=4.13,
    nozzle_total_temperature=2000.0,
    nozzle_total_pressure=69.0 * 101325.0,
    nozzle_radius=1.0,
    atmospheric_pressure=101325.0,
    gamma=1.33,
    num_expansion_lines=2,
    num_compression_lines=1,
    num_plumes=1,
)
```

`zones` contains immutable flow-state results and their 2D geometry. `details` contains construction points and the fitted plume boundary used by the solver.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest
python -m build
```

The scientific API only requires the dependencies listed under `[project].dependencies`. Install the `plot` extra for the command-line runner and graphical output.
