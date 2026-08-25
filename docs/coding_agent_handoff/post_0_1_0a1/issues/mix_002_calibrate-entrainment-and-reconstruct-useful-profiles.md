# MIX-002 — Calibrate entrainment and reconstruct useful profiles

## Metadata

- **Phase:** Downstream straight plume
- **Target release:** `0.2.0a2`
- **Priority:** P1
- **Dependencies:** `MIX-001`
- **Suggested branch:** `work/mix-002`

## Objective

Turn the conservation kernel into a defensible straight mixing model.

## Scope

- Calibrate free-jet entrainment against round-jet width, centerline velocity, mass-flow growth, and dilution data.
- Add top-hat and flux-preserving Gaussian profile reconstruction.
- Separate velocity, thermal, and species widths where evidence requires.
- Propagate coefficient uncertainty.

## Deliverables

- Calibrated entrainment closure.
- Profile reconstruction module.
- Calibration and holdout validation report.

## Acceptance criteria

- [ ] Calibration and validation datasets are disjoint.
- [ ] Mass, momentum, enthalpy, and species remain conservative under profile reconstruction.
- [ ] Predicted spreading and dilution errors are quantified.

## Required tests and evidence

- [ ] Profile quadrature closure.
- [ ] Calibration sensitivity.
- [ ] Holdout dataset validation.

## Suggested repository paths

- `src/exhaust_plume/models/integral/`
- `docs/validation/`
- `tests/validation/`

## Non-goals

- No rotor-specific coefficient fitting.

## Completion report

The PR description must include:

- Exact base SHA and head SHA.
- Contract or equation changes.
- Units, frames, and lifecycle semantics.
- Compatibility impact.
- Success and structured-failure evidence.
- Ruff, Pyright, Pytest, build, and installed-wheel results.
- Remaining limitations.
- Confirmation that no downstream packet was implemented opportunistically.
