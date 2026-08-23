# Release cleanup: `0.1.0a1`

## Baseline

- Default branch baseline: `main@49d6ffd1839258ce14319e157002005c6d2230e1`.
- Canonical release tag: `v0.1.0a1`.
- Tag target: `8b37e48b65321403bb3eb4ed0fdfe949dc9f1506`, contained by the
  baseline merge commit; release history was not rewritten.
- Release gate: [`release_gate_0.1.0a1.md`](release_gate_0.1.0a1.md).
- Release notes: [`release_notes_0.1.0a1.md`](release_notes_0.1.0a1.md).

## Repository hygiene

The following PRs were open while the alpha baseline was finalized and are
integrated into `main`; their discussion history is preserved by closing them
as superseded/integrated:

- [PR #1](https://github.com/sheepfling/Exhaust-Plume/pull/1): conservative
  curved-plume kernel and analytical regressions — closed as integrated.
- [PR #2](https://github.com/sheepfling/Exhaust-Plume/pull/2): MVP data
  products and the shock-zone visual adapter — closed as integrated.

The following remote feature refs were checked with an ancestor comparison
before deletion. Every listed tip is fully contained in `main`:

- `feature/curved-plume-kernel`
- `feature/initial-work`
- `feature/mvp-product-alignment`
- `feature/mvp-product-contracts`
- `feature/mvp-product-contracts-integration`
- `feature/plume-interface-foundation`

All six remote refs and their matching local stale refs were deleted after the
ancestor checks. No branch containing commits absent from `main` was deleted.

## Main protection

`main` is protected with strict required status checks:

- `test (3.10)`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`

Administrative enforcement is enabled; force-pushes and branch deletion are
disabled. Pull-request review requirements remain unchanged because the
packet only requires the CI matrix at this gate.

The GitHub release entry is
[`v0.1.0a1`](https://github.com/sheepfling/Exhaust-Plume/releases/tag/v0.1.0a1)
and includes the release notes plus the wheel and sdist artifacts.

## Development transition

Development now reports `0.1.0.a2.dev0` (`0.1.0a2.dev0` in package metadata).
No source refactor or downstream packet implementation is included in this
transition.
