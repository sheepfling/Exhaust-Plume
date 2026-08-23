# Coding-Agent Prompt: Execute the Comprehensive Work Plan

Use `34_comprehensive_master_work_plan.md` as the execution coordinator and
`master_work_plan.yaml` as the dependency registry. Select exactly one ready PR
node whose dependencies are merged.

## Required behavior

1. Read the detailed documents referenced by the selected node.
2. Confirm the dependency gates before editing code.
3. State the branch name, files expected to change, equations/contracts, tests,
   and explicit non-goals.
4. Implement only that node.
5. Preserve existing TODOs unless the node explicitly resolves them.
6. Use Python 3.12+, complete type annotations, NumPy typing, Pytest, Ruff,
   Pyright, and the project `####` scope-ending convention.
7. Do not silently extrapolate, silently fall back to a lower model, or expose
   provider-private types through a neutral capability.
8. Report files changed, numerical/contract evidence, tests, quality commands,
   compatibility impact, and remaining limitations.
9. Stop after the selected node; do not start its successor.

## Initial selection

For a new execution, begin with `P00`. After `P00`, `P01` and `P04` may be
assigned independently. Merge the provider-contract path before adapting the
real solver.
