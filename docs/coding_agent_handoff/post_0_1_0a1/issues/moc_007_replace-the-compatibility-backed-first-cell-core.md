# MOC-007 — Replace the compatibility-backed first-cell core

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-006`, `API-010`
- **Suggested branch:** `work/moc-007`

## Objective

Swap the canonical straight analytical provider to the validated MOC implementation without changing its public product contract.

## Scope

- Route `solve_first_cell_from_exit_state` to the new MOC core.
- Retain the old low-order solver behind an explicit legacy or comparison path.
- Propagate MOC residuals, validation level, uncertainty, and applicability.
- Compare old and new output intentionally rather than preserving incorrect numerics.

## Deliverables

- New production first-cell core.
- Legacy comparison adapter.
- Migration and numerical-difference report.

## Acceptance criteria

- [ ] Canonical provider conformance remains green.
- [ ] All validation gates remain green.
- [ ] No public capability or wire version changes.
- [ ] Legacy callers receive documented behavior changes or an explicit legacy mode.

## Required tests and evidence

- [ ] Provider/direct MOC equivalence.
- [ ] Old/new comparison fixtures.
- [ ] Installed-wheel end-to-end visual workflow.

## Suggested repository paths

- `src/exhaust_plume/models/shock_cells/`
- `src/exhaust_plume/models/moc/`
- `src/exhaust_plume/providers/straight_analytical.py`

## Non-goals

- No finite shock train.
- No mixing continuation.

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
