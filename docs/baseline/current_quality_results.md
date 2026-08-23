# Current Quality Results

Baseline captured on 2026-08-22 from commit
`86195b394048ed97f876879041ad4d7af48a963f` using Python 3.12.3 on macOS.

## Quality commands

| Command | Result | Evidence |
| --- | --- | --- |
| `python -m pytest` | Not runnable | This shell has no `python` executable. |
| `python3 -m pytest` | PASS | 30 passed, 8 runtime warnings, 1.36 s. |
| `python -m ruff check .` | Not runnable | This shell has no `python` executable. |
| `python3 -m ruff check .` | PASS | All checks passed. |
| `python -m pyright` | Not runnable | This shell has no `python` executable. |
| `python3 -m pyright` | PASS | 0 errors, 0 warnings, 0 informations. |
| `python -m build` | Not runnable | This shell has no `python` executable. |
| `python3 -m build` | BLOCKED | Isolated build could not download `setuptools>=68` because network access is unavailable. |
| `python3 -m build --no-isolation` | PASS | Built sdist and `exhaust_plume-0.1.0a0-py3-none-any.whl`. The build backend emitted a non-fatal git-file-list warning. |

The pytest warnings are existing runtime warnings from
`projected_areas.py:84` while plotting exclusion angles with an infinite
intermediate value. They are recorded as baseline noise, not treated as
validation evidence.

## Installed-wheel smoke

The wheel installed successfully into a fresh isolated virtual environment
with `--no-index --no-deps`. Running `tests/installed_smoke.py` then stopped at
the first import because the fresh environment had no `numpy`. Installing the
declared runtime dependencies was not possible offline. A complete installed
wheel smoke remains required once an environment with the declared dependency
wheels is available.

## Archive integrity

`sha256sum -c docs/coding_agent_handoff/SHA256SUMS.txt` passed for all 63
handoff files.

## Representative legacy anchor

The fixture in `tests/fixtures/legacy_baseline/representative_underexpanded_case.json`
records one reproducible solver output. It is a `legacy_anchor`: it preserves
current behavior for migration diagnostics and is not a claim of physical
validation or corrected-physics truth.
