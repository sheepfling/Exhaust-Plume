# MOC-006 — Complete convergence and external validation evidence

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-004`, `MOC-005`
- **Suggested branch:** `work/moc-006`

## Objective

Demonstrate that the first-cell solver is numerically converged and physically credible within a declared domain.

## Scope

- Run mesh-resolution studies for underexpanded and overexpanded cases.
- Compare first-cell length, radius, and pressure behavior against accepted correlations and selected CFD/experimental data.
- Separate calibration cases from validation cases.
- Quantify residual, discretization, and model-form uncertainty.

## Deliverables

- Validation dataset registry and provenance.
- Convergence plots/tables.
- Validation report and declared applicability envelope.

## Acceptance criteria

- [ ] Observed quantities converge with refinement.
- [ ] Validation error and uncertainty are reported, not hidden in tolerances.
- [ ] Unsupported regions remain explicitly outside.
- [ ] No validation dataset is reused as both calibration and validation.

## Required tests and evidence

- [ ] Automated convergence suite.
- [ ] Independent correlation calculations.
- [ ] Regression tolerances derived from evidence.

## Suggested repository paths

- `docs/validation/`
- `tests/validation/`
- `tests/fixtures/physics/`

## Non-goals

- No finite downstream shock train.
- No certification claim.

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
