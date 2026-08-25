# MOC-001 — Freeze the mathematical contract for a validated first cell

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `RLS-001`
- **Suggested branch:** `work/moc-001`

## Objective

Define the independent MOC solver problem before replacing the compatibility-backed first-cell internals.

## Scope

- Specify unknowns, characteristic invariants, boundary conditions, topology, units, residuals, convergence criteria, and failure modes.
- Define matched, mild underexpanded, and mild attached-overexpanded topologies separately.
- Define the relationship between MOC states, closed zones, visual envelope, and control-surface handoff.
- Select independent analytical and published validation cases.

## Deliverables

- Mathematical specification.
- Equation traceability table.
- Reference-case registry with expected residuals.

## Acceptance criteria

- [ ] Every solver equation maps to a test or validation residual.
- [ ] Detached-shock and nozzle-separation cases are explicitly outside this model.
- [ ] The output contract can replace the current core without changing public providers.

## Required tests and evidence

- [ ] Dimensional consistency review.
- [ ] Independent hand calculations for reference cases.
- [ ] Topology review for each supported regime.

## Suggested repository paths

- `docs/`
- `tests/fixtures/physics/`

## Non-goals

- No production solver code.
- No finite shock train.

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
