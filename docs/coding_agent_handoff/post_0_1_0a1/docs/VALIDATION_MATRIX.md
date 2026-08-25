# Validation and evidence matrix

| Layer | Required evidence |
|---|---|
| Release | Exact SHA/version, CI matrix, wheel smoke, CLI smoke, deterministic schemas/fixtures, artifact hashes |
| API | Import inventory, schema compatibility, lifecycle conformance, typed failures, deprecation tests |
| Handoff | Mass, vector momentum, pressure thrust, stagnation enthalpy, species, frame rotation, uncertainty |
| Washed kernel | Free-jet exact solution, uniform-crossflow exact solution, invariants, rotation, buoyancy/source terms |
| Washed geometry | Orthonormal frames, no flips, radius/plane checks, curvature/slenderness, support enclosure |
| MOC primitives | PM round trips, characteristic residuals, root bracketing, endpoint conditioning |
| MOC topology | Forward intersections, simple zones, boundary pressure, shock residual, centerline symmetry |
| MOC validation | Grid convergence, correlation comparison, independent CFD/experimental cases, uncertainty |
| Shock train | Cell-spacing/decay calibration, holdout validation, physical-vs-limit termination |
| Mixing | Free-jet calibration, holdout spreading/dilution, profile quadrature conservation |
| Rays | Analytic intersections, tangencies, misses, ordering, rotation, swept-geometry convergence |
| Gray transfer | Slab analytic solutions, layer ordering, thin/thick limits, miss semantics |
| Signature from rays | Projected-area quadrature convergence, angular symmetry, source-only semantics |

## Default quality gate

Every implementation PR runs:

```bash
python -m ruff check .
python -m pyright
python -m pytest
python -m build
```

Release PRs additionally install the wheel into a fresh environment and exercise every installed entry point outside the repository.
