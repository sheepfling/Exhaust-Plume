# MIX-001 — Correct and harden the straight integral continuation

## Metadata

- **Phase:** Downstream straight plume
- **Target release:** `0.2.0a2`
- **Priority:** P1
- **Dependencies:** `HND-001`
- **Suggested branch:** `work/mix-001`

## Objective

Review the existing top-hat continuation as a conservation kernel before calibration.

## Scope

- Write the governing relative/absolute momentum and energy equations explicitly.
- Correct ambient-velocity momentum handling where required.
- Separate kernel conservation from entrainment closure.
- Add structured termination and failure statuses.

## Deliverables

- Revised straight integral kernel.
- Equation and invariant documentation.
- Exact regression cases.

## Acceptance criteria

- [ ] Quiescent and moving-ambient invariants close.
- [ ] Zero entrainment reproduces constant fluxes.
- [ ] Failures return partial valid histories with structured status where safe.

## Required tests and evidence

- [ ] Exact free-jet limits.
- [ ] Moving-ambient manufactured solutions.
- [ ] Species and energy closure.

## Suggested repository paths

- `src/exhaust_plume/models/integral/straight.py`
- `docs/`

## Non-goals

- No empirical calibration.
- No Gaussian reconstruction.

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
