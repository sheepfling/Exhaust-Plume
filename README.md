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
- Provider/session/snapshot contracts and a straight analytical spatial provider.
- Generic versioned visual, unresolved spectral, and resolved ray-transfer
  interface contracts, with schemas, fixtures, and a prescribed visual
  contract provider.
- A straight parametric visual provider and a neutral table-backed directional
  spectral lookup provider.
- MVP workflows for visual mesh/OBJ/PNG export and signature-table
  JSON/CSV/PNG lookup reporting.
- Explicit equivalent-area circular throat/exit geometry, choked-flow
  consistency checks, and a reproducible validity matrix spanning finite
  atmospheric-to-near-vacuum ambient pressures.

## Model contract

The model uses SI units internally: pressure in pascals, temperature in kelvin, density in kg/m³, and length in meters. Legacy flow-state angle fields and wrappers remain in degrees; new shock-validity and geometry APIs use radians. New nozzle and ambient construction requires an explicit gas object; the legacy total-condition wrapper retains an explicit dry-air compatibility assumption.

The plume geometry is a method-of-characteristics-style study model with ideal-gas, isentropic, expansion-fan, and oblique-shock relations. It is intended for exploratory engineering studies, not certification analysis. Very low or very high Mach numbers and extreme pressure ratios remain known failure regions.

The governing equations and conservation checks are summarized in [`docs/mathematical_model.tex`](docs/mathematical_model.tex).

### Simulation inputs

The core `calculatePlumeZones` call requires the following finite scalar data:

| Input | Units | Constraint | Role |
| --- | --- | --- | --- |
| `nozzle_mach` | — | `> 1` | Supersonic exit Mach number |
| `nozzle_total_temperature` | K | `> 0` | Exit stagnation temperature |
| `nozzle_total_pressure` | Pa | `> 0` | Exit stagnation pressure |
| `nozzle_radius` | m | `> 0` | Exit radius for the 2-D geometry seed |
| `atmospheric_pressure` | Pa | `> 0` | Ambient pressure used for regime selection |
| `gamma` | — | `> 1` | Constant ratio of specific heats |
| `num_expansion_lines` | count | `>= 2` | Discrete expansion-fan resolution |
| `num_compression_lines` | count | `>= 1` | Discrete compression-wave resolution |
| `num_plumes` | count | `>= 1` | Number of construction passes appended |

The core solver has no defaults. The CLI supplies study defaults and derives
ambient pressure from geopotential altitude using the packaged layered standard
atmosphere model. `EngineParameters` is a separate textbook helper for mass
flow, throat-area, and exit-Mach calculations; it is not currently an alternate
input object for `calculatePlumeZones`.

### Solver flow

1. Convert total exit conditions to the static exit state with the isentropic
   relations. The regime uses `(p_exit - p_atmosphere) / p_atmosphere` and an
   explicit matched-flow tolerance.
2. For an underexpanded exit, calculate discrete Prandtl–Meyer expansion
   states, reflect their characteristic geometry across the centerline, then
   apply oblique compression waves toward ambient pressure.
3. For an overexpanded exit, prepend an oblique-shock pressure-equalization
   precursor and a centerline compression before applying the reflected
   construction.
4. Build 2-D zone polygons from validated forward-ray intersections. The
   reflected outer boundary remains a quadratic study approximation.
5. Return zone flow states, phase metadata, construction points, and the
   diagnostic boundary fit.

`ZoneType` describes the local relation (`Isentropic`, `ExpansionFan`, or
`ObliqueShock`); it is not a global regime or solver mode. The full equations,
phase definitions, coordinate convention, and limitations are in the LaTeX
model note.

### Outputs and scope

Each `ZoneResult` contains static flow properties, derived total properties,
`plume_index`, `group_number`, `group_index`, a phase label, `beta`/`theta`
angles in degrees, a `ZoneType`, and `coordinates.corners_ru` in the right/up
plane. The `details` mapping currently contains `points` labeled A–K and a
`plume_fit` diagnostic. Callers should check polygon coordinates for finite
values because some nonterminal compression subdivisions can still carry
placeholder geometry. New canonical results expose `cell_index` and omit
invalid polygons from the spatial provider.

For new code, construct explicit `NozzleExitState` and `AmbientState` objects
and call `solve_shock_cells(ShockCellSolveConfig(...))`. Matched flow returns
zero cells with `NO_PRESSURE_MISMATCH`; `max_cells=0` returns zero cells with a
construction-limit status. `ShockCellAnalyticalProvider` advertises only
`spatial-support`, `axisymmetric-zone-field`, and `projected-area`. Radiation
physics, chemistry, curved-flow, and accelerated execution are outside this
foundation. The versioned ray-transfer DTO defines consumer-facing semantics
only and remains interface-only. The spectral product currently uses a
neutral lookup provider, not a physical spectroscopy or radiation model. The
generic interface boundary is documented in
[`docs/interface_contracts_v1.md`](docs/interface_contracts_v1.md).
The product-level MVP workflow is documented in
[`docs/product_mvp.md`](docs/product_mvp.md).
The finite study envelope and pressure/throat matrix are documented in
[`docs/validity_envelope.md`](docs/validity_envelope.md).

For an explicit throat/exit configuration, use `NozzleGeometry` with a
`ThroatConfiguration` and call `derive_nozzle_exit_from_geometry(...)`. The
active path supports circular equivalent areas and the supersonic branch. It
does not resolve nozzle wall contours, losses, separation, non-circular
sections, or rarefied flow.

The active plume model is constant-`gamma` ideal gas. It does not yet model
species composition, reactions, dissociation, vibrational energy, or
temperature-dependent specific heats. The broader thermodynamic helpers remain
available as reference material from the textbook work and are intentionally
not treated as all belonging to the active plume path.

### Future plume termination

The current solver has no physical plume-end condition. It can continue
building plausible-looking adiabatic and isentropic regions because those local
relations do not model entrainment, diffusion, viscous dissipation, or mixing
with the ambient flow. The plume-count and line-count inputs control
construction resolution; they do not predict plume lifetime.

The new provider reports requested construction truncation explicitly; it does
not claim a physical plume endpoint. Future work should choose and document one
termination policy:

- A weak-wave cutoff based on pressure, Mach, turning-angle, and total-pressure
  changes.
- An ambient-equilibrium criterion with residual tolerances and persistence
  over distance.
- A finite axial or radial study domain reported explicitly as truncation.
- An entrainment/mixing model that exchanges mass, momentum, and energy with
  the ambient.
- A higher-fidelity downstream coupling model for viscous, turbulent, or
  multispecies effects.

The eventual result contract should report the termination reason, ambient
residuals, last active wave type, and whether termination was physical or
domain-imposed. This design is documented as future work only; it is not
implemented yet.

### Product MVP workflows

The visual MVP loads a straight sectioned-tube definition, evaluates it through
the versioned snapshot lifecycle, and writes renderer-neutral result JSON,
triangle-mesh JSON, OBJ geometry, and an optional Matplotlib preview:

```bash
exhaust-plume-visualize \
  --config fixtures/products/visual_asset_v1.json \
  --output-dir visual-output
```

The simple straight solver can be adapted to the same visual contract through
`visual_definition_from_shock_cells` or `evaluate_shock_cell_visual`. That
adapter produces an engineering-approximate axisymmetric envelope and does not
claim conservative geometry or radiometric correctness.

The signature MVP loads a canonical table asset and request, evaluates the
asset-declared wavelength and direction-cosine policy, optionally interpolates
prescribed time slices, and writes JSON/CSV results plus spectrum, angular-cut,
and spectral/angular heatmap previews:

```bash
exhaust-plume-signature \
  --asset fixtures/products/signature_asset_v1.json \
  --request fixtures/products/signature_request_v1.json \
  --output-dir signature-output
```

Both commands use the optional `plot` extra for PNG previews. The signature
workflow is deliberately lookup-backed: it does not infer spectra from plume
thermodynamics, perform physical radiation transport, or model detector/FPA
effects. Out-of-domain lookup requests are rejected unless extrapolation is
explicitly enabled, and exact-only policies always require a stored node.

Run the declared geometry and pressure validation matrix with:

```bash
exhaust-plume-validate --output-dir validity-output
```

This produces machine-readable JSON and CSV reports. `outside` results are
expected for some near-vacuum or numerically difficult cases; they are part of
the applicability contract and are not converted into nominal geometry.

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
python -m pip install -e '.[dev]'
python -m scripts.ci
```

The single CI entry point runs the tests, Ruff, scope-marker validation,
Markdown linting with rumdl, Pyright, deterministic public-asset checks, and
an isolated wheel-install smoke test. Use `python -m scripts.ci` before
opening a pull request. Add `--fix` to `scripts.check_scope_markers` or
`scripts.check_rumdl` when applying their safe formatting fixes.

The scientific API only requires the dependencies listed under
`[project].dependencies`. Install the `plot` extra for the command-line runner
and graphical output.

Ruff checks the complete source and test tree. Pyright checks the release-facing
API, provider, product, radiation, and detector modules listed in
[`pyrightconfig.json`](pyrightconfig.json). The experimental MOC research tree
is intentionally governed by its numerical and conformance lanes until its
physical closure is accepted.

CI also installs the built wheel into a fresh virtual environment and runs `tests/installed_smoke.py` from outside the repository. That check discovers the installed package resources dynamically before exercising the public API and CLI help path.
