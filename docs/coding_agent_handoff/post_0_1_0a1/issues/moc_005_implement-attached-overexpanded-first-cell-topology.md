# MOC-005 — Implement attached-overexpanded first-cell topology

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-003`
- **Suggested branch:** `work/moc-005`

## Objective

Replace the low-order overexpanded precursor with an attached-shock/MOC topology for the supported mild regime.

## Scope

- Use the weak attached oblique-shock branch and maximum-turn validity checks.
- Construct the post-shock characteristic field and compatible boundary.
- Reject detached-shock, separation, and infeasible pressure targets.

## Deliverables

- Attached-overexpanded first-cell solver.
- Shock and boundary residual report.
- Applicability map.

## Acceptance criteria

- [ ] Shock jump and theta-beta-Mach residuals close.
- [ ] Topology remains finite and forward.
- [ ] Cases beyond attached validity return `DETACHED_SHOCK_REQUIRED` or a more specific structured status.

## Required tests and evidence

- [ ] Mild overexpanded sweep.
- [ ] Maximum-turn boundary cases.
- [ ] Shock conservation.
- [ ] Grid refinement.

## Suggested repository paths

- `src/exhaust_plume/models/moc/`
- `src/exhaust_plume/util/aero/shock_validity.py`

## Non-goals

- No nozzle separation.
- No detached shock or Mach disk.

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
