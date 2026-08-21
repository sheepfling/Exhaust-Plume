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
- Archived standalone solvers and the original explanatory slide deck.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest
```
