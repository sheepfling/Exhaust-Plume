# PRV-004 — Add compatibility aliases and a deprecation schedule

## Metadata

- **Phase:** Canonical providers
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `PRV-001`, `PRV-002`, `PRV-003`
- **Suggested branch:** `work/prv-004`

## Objective

Keep 0.1.0a1 consumers functioning while preventing continued growth of duplicate APIs.

## Scope

- Route legacy imports and methods into canonical implementations.
- Emit targeted, documented deprecation warnings only where behavior changes.
- Publish a removal horizon no earlier than the next incompatible release.
- Update package-root exports and documentation to prefer canonical imports.

## Deliverables

- Compatibility module and alias table.
- Migration guide with old/new examples.
- Deprecation tests.

## Acceptance criteria

- [ ] Existing 0.1.0a1 examples still execute.
- [ ] New documentation imports only the canonical API.
- [ ] Warnings identify the exact replacement symbol.
- [ ] No duplicate provider implementation remains active.

## Required tests and evidence

- [ ] Installed-wheel compatibility smoke.
- [ ] Root-export inventory regression.
- [ ] Warning text and stack-level tests.

## Suggested repository paths

- `src/exhaust_plume/__init__.py`
- `src/exhaust_plume/compat/`
- `docs/`

## Non-goals

- No immediate removal of shipped names.
- No unrelated package reorganization.

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
