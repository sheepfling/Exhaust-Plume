# WASH-003 — Expose washed visual and engineering products

## Metadata

- **Phase:** Washed plume productization
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `WASH-002`
- **Suggested branch:** `work/wash-003`

## Objective

Publish curved-plume results without leaking solver-private station or mesh types.

## Scope

- Map stations to canonical visual sectioned-tube geometry using rotation-minimizing frames.
- Map stations to canonical engineering flux-section products.
- Carry temperature, pressure, density, speed, dilution, curvature, and slenderness as explicitly named diagnostic channels.
- Compute conservative support bounds and reject invalid/folded geometry.

## Deliverables

- Canonical visual adapter.
- Canonical engineering adapter.
- Support-bound and geometry-quality diagnostics.

## Acceptance criteria

- [ ] Frames remain orthonormal and continuous.
- [ ] Visual and engineering products share snapshot identity and frame.
- [ ] Flux products reproduce the solver's conserved histories.
- [ ] High `kappa*b`, self-intersection risk, or failed stations are surfaced as applicability warnings or failures.

## Required tests and evidence

- [ ] Straight-limit and quarter-circle geometry.
- [ ] Rotation invariance.
- [ ] Flux-history equality.
- [ ] Invalid geometry and large-curvature diagnostics.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/providers/adapters.py`
- `src/exhaust_plume/models/plume/curved_plume_geometry.py`

## Non-goals

- No brightness/emissivity channel.
- No physical ray transfer.

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
