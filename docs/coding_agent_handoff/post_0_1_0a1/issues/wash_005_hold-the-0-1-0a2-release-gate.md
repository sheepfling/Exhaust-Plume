# WASH-005 — Hold the 0.1.0a2 release gate

## Metadata

- **Phase:** Washed plume productization
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-010`, `WASH-004`, `RLS-002`
- **Suggested branch:** `work/wash-005`

## Objective

Release the canonical API and first live washed-plume provider together under one verified alpha.

## Scope

- Run the complete release matrix from the candidate commit.
- Regenerate canonical schemas/fixtures.
- Exercise visual, signature, validation, and washed-provider workflows from the installed wheel.
- Publish limitations and calibration status.

## Deliverables

- 0.1.0a2 release-gate report.
- Release notes and artifact hashes.
- Provider conformance summary.

## Acceptance criteria

- [ ] All canonical providers pass.
- [ ] No duplicate schema authority remains.
- [ ] No result overclaims physical radiation or calibrated helicopter accuracy.
- [ ] Wheel and source tree produce identical golden outputs.

## Required tests and evidence

- [ ] Python 3.10–3.13 matrix.
- [ ] Installed-wheel consumer smoke.
- [ ] Generated-asset drift check.

## Suggested repository paths

- `docs/`
- `.github/workflows/`
- `fixtures/`

## Non-goals

- No MOC completion requirement.
- No gray radiation.

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
