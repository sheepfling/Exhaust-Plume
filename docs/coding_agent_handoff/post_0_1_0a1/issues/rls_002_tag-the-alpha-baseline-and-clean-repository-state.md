# RLS-002 — Verify alpha tag and repository hygiene

## Metadata

- **Phase:** Release integrity
- **Target release:** `0.1.0a1`
- **Priority:** P0
- **Dependencies:** `RLS-001`
- **Suggested branch:** `work/rls-002`

## Objective

Verify that the already-created alpha tag and repository cleanup are consistent with the final release-gate evidence, then prepare development for the next alpha without rewriting release history.

## Current-state facts to verify, not recreate

- Annotated tag `v0.1.0a1` exists and targets release commit `8b37e48b65321403bb3eb4ed0fdfe949dc9f1506`.
- That release commit and `main@49d6ffd1839258ce14319e157002005c6d2230e1` share tree `bfd587778b15da8e9b10213d7e680e48b5ae6e1e`.
- PRs #1 and #2 are closed.
- No `feature/*` branches remain.
- `main` is protected and requires `test (3.10)`, `test (3.11)`, `test (3.12)`, and `test (3.13)`.

## Scope

- Verify the existing `v0.1.0a1` tag/release content against the `RLS-001` gate report and artifact hashes.
- Confirm that PRs #1 and #2 remain closed as integrated/superseded history.
- Confirm there are no surviving fully merged `feature/*` branches.
- Confirm branch protection still requires the Python 3.10–3.13 CI matrix.
- Publish or amend release notes so they link the tag, wheel, gate report, and known limitations.
- Advance the development version after the release baseline is accepted, recommended `0.1.0a2.dev0`.

## Deliverables

- Release-integrity record tying tag, release commit/tree, `main` merge tree, artifacts, and gate evidence together.
- Repository-hygiene verification record.
- Version bump for subsequent development.

## Acceptance criteria

- [ ] The release tag/tree is proven equivalent to the content validated by `RLS-001`.
- [ ] Release notes point to the final gate evidence and artifact hashes.
- [ ] PRs #1 and #2 are closed and no stale `feature/*` branch remains.
- [ ] `main` still requires all four Python CI checks.
- [ ] The post-release development version is no longer the already-released alpha.

## Required tests and evidence

- [ ] Resolve the annotated tag to its target commit and tree.
- [ ] Compare the tagged release tree to the validated `main` tree.
- [ ] Install and report package version from the tagged wheel.
- [ ] Verify release archive hashes against the recorded manifest.
- [ ] Record current branch-protection contexts and open-PR/branch inventory.

## Suggested repository paths

- `.github/`
- `src/exhaust_plume/constants.py`
- `docs/`

## Non-goals

- No source refactor.
- No retagging or release-history rewrite unless a separately approved release-integrity decision requires it.
- No recreation of already-closed PRs or already-deleted feature branches.

## Completion report

The PR description must include:

- Exact base SHA and head SHA.
- Release tag target commit and tree identity.
- Compatibility impact.
- Quality and installed-wheel evidence.
- Repository-hygiene verification.
- Remaining limitations.
- Confirmation that no downstream packet was implemented opportunistically.
