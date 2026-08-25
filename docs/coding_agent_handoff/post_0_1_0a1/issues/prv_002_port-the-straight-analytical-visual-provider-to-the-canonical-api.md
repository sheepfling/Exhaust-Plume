# PRV-002 — Port the straight analytical visual provider to the canonical API

## Metadata

- **Phase:** Canonical providers
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-009`
- **Suggested branch:** `work/prv-002`

## Objective

Expose the existing bounded first-cell visual provider through the canonical lifecycle without changing its current low-order physics.

## Scope

- Use explicit nozzle-exit and ambient state inputs.
- Preserve matched, mild-underexpanded, and mild-attached-overexpanded behavior.
- Preserve structured refusal for strong, detached, failed, or empty cases.
- Advertise visual capability only.
- Carry solver status and construction-boundary limitations into applicability metadata.

## Deliverables

- Canonical straight analytical provider/session/snapshot.
- Compatibility adapter for existing provider imports.
- Conformance and direct-solver equivalence tests.

## Acceptance criteria

- [ ] Matched flow requires and honors an explicit display domain.
- [ ] Direct first-cell solve and provider output agree at source stations.
- [ ] No signature or ray-transfer claim is inferred.
- [ ] Marginal construction boundaries remain labeled marginal.

## Required tests and evidence

- [ ] Matched/underexpanded/overexpanded fixture matrix.
- [ ] Strong-overexpanded structured failure.
- [ ] Provider/direct solver comparison.
- [ ] Serialization determinism.

## Suggested repository paths

- `src/exhaust_plume/providers/straight_analytical.py`
- `src/exhaust_plume/models/shock_cells/`
- `tests/src/providers/`

## Non-goals

- No MOC replacement.
- No complete plume or physical termination claim.

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
