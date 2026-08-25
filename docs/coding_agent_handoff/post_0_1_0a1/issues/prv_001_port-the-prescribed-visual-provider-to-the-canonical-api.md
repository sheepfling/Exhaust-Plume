# PRV-001 — Port the prescribed visual provider to the canonical API

## Metadata

- **Phase:** Canonical providers
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-009`
- **Suggested branch:** `work/prv-001`

## Objective

Make the deterministic prescribed sectioned-tube provider the first fully conformant canonical provider.

## Scope

- Use canonical definition, configuration, session, snapshot, request, result, claims, and provenance types.
- Preserve existing fixture behavior and content hashes.
- Provide compatibility entry points for current imports.

## Deliverables

- Canonical prescribed visual provider.
- Compatibility aliases/adapters.
- Conformance registration and golden fixture.

## Acceptance criteria

- [ ] Provider passes the full visual conformance suite.
- [ ] Existing prescribed fixture serializes identically or through a documented versioned migration.
- [ ] No spectral capability is advertised.

## Required tests and evidence

- [ ] Static-time behavior.
- [ ] Closed-session behavior.
- [ ] Content hash determinism.
- [ ] Invalid geometry rejection.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/providers/prescribed_visual.py`
- `fixtures/`

## Non-goals

- No new geometry generation.
- No renderer or sidecar integration.

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
