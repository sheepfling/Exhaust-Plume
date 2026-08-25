# CELL-001 — Implement a finite coherent shock train

## Metadata

- **Phase:** Downstream straight plume
- **Target release:** `0.2.0a2`
- **Priority:** P1
- **Dependencies:** `HND-003`
- **Suggested branch:** `work/cell-001`

## Objective

Extend the validated first cell into a finite train with physical decay and explicit termination.

## Scope

- Model coherent-core shrinkage, pressure-oscillation decay, and local cell spacing.
- Use reduced-order downstream cells only after the validated first cell.
- Distinguish physical termination, applicability failure, and requested truncation.
- Calibrate and validate on disjoint cases.

## Deliverables

- Finite shock-train model.
- Termination diagnostics.
- Calibration/validation report.

## Acceptance criteria

- [ ] Cell count is an output, not a caller-selected physical answer.
- [ ] Pressure/geometry oscillations decay monotonically under the selected closure.
- [ ] Physical termination is distinguishable from safety limits.

## Required tests and evidence

- [ ] Zero-decay and strong-decay limits.
- [ ] Sensitivity and uncertainty.
- [ ] Validation against observed cell spacing/decay.

## Suggested repository paths

- `src/exhaust_plume/models/shock_train/`
- `tests/validation/`

## Non-goals

- No turbulent mixing replacement.

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
