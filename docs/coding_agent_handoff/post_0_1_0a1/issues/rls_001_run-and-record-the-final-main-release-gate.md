# RLS-001 — Run and record the final main release gate

## Metadata

- **Phase:** Release integrity
- **Target release:** `0.1.0a1`
- **Priority:** P0
- **Dependencies:** None
- **Suggested branch:** `work/rls-001`

## Objective

Produce authoritative release evidence tied to the exact merged `main` commit rather than relying on pre-merge branch reports.

## Scope

- Check out `49d6ffd1839258ce14319e157002005c6d2230e1` from `main` in a clean environment.
- Run the Python 3.10–3.13 CI matrix and the same commands locally where practical.
- Regenerate schemas and fixtures and compare them byte-for-byte with checked-in assets.
- Build sdist and wheel, install the wheel outside the checkout, and exercise every installed CLI.
- Record warnings, test counts, artifact hashes, package version, and commit identity.

## Deliverables

- `docs/release_gate_0.1.0a1.json` with machine-readable results.
- `docs/release_gate_0.1.0a1.md` with human-readable interpretation.
- SHA-256 inventory for release artifacts and generated public assets.

## Acceptance criteria

- [ ] The report identifies `49d6ffd1839258ce14319e157002005c6d2230e1` and package version `0.1.0.a1`.
- [ ] Ruff, Pyright, Pytest, build, installed-wheel smoke, and all CLI smoke tests pass.
- [ ] Generated schemas and fixtures are deterministic.
- [ ] Known warnings are explicitly classified; no new warning is silently accepted.

## Required tests and evidence

- [ ] `python -m ruff check .`
- [ ] `python -m pyright`
- [ ] `python -m pytest` on Python 3.10, 3.11, 3.12, and 3.13
- [ ] `python -m build`
- [ ] Fresh-wheel imports and `--help` for all four CLIs
- [ ] Fixture and schema regeneration diff is empty

## Suggested repository paths

- `docs/`
- `scripts/`
- `.github/workflows/ci.yml`

## Non-goals

- No API redesign.
- No physics changes.
- No branch cleanup until the gate report is complete.

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
