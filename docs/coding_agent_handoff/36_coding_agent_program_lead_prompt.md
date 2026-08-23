# Coding-Agent Prompt: Program Lead and Next-Packet Executor

You are working in `sheepfling/Exhaust-Plume` against the branch and source
snapshot recorded in this handoff.

Read, in order:

```text
README.md
34_comprehensive_work_plan.md
35_first_execution_wave.md
00_unified_plume_architecture.md
10_coding_agent_execution_protocol.md
27_release_gates_and_definition_of_done.md
work_plan.yaml
execution_graph.yaml
```

Then inspect the repository and determine the first incomplete work packet or
PR whose listed dependencies and gate evidence are complete.

## Operating rule

Implement exactly one packet or PR. Do not implement the complete program in
one branch. Do not begin a downstream task merely because the current task is
small.

## Required preflight

1. Confirm repository branch and current commit.
2. Compare reviewed file SHAs with the handoff snapshot when the task touches
   those files.
3. Run and record relevant baseline tests before modification.
4. Read every detailed plan or task packet referenced by the selected work ID.
5. State the selected milestone/work ID, dependencies, expected files,
   equations/contracts, non-goals, and acceptance tests before editing.

## Architecture constraints

- Use the provider/session/snapshot lifecycle.
- Consumers depend on semantic capabilities, not provider implementations.
- Geometry remains optional.
- Morphology, fidelity, radiation model, and execution behavior remain
  orthogonal metadata.
- Intrinsic source signatures exclude range, atmosphere, optics, and detector
  response.
- Provider chaining uses neutral conserved handoffs or standard fields.
- Do not expose provider-private zone or mesh types through generic contracts.
- Do not silently extrapolate, silently fall back, or confuse truncation with
  physical termination.

## Coding constraints

- Python 3.12+.
- Complete type annotations.
- `numpy.typing.NDArray` for numerical arrays.
- Frozen or immutable public contracts.
- Pytest, Ruff, Pyright, and build checks.
- Preserve existing TODOs unless the selected work packet explicitly resolves
  them.
- End every Python scope with `####` according to project convention.
- No network access in tests.
- Heavy spectroscopy, chemistry, or accelerator dependencies remain optional.

## Scientific constraints

- Identify every implemented relation as a governing equation, correlation, or
  closure.
- Use SI units and radians internally.
- Add algebraic/unit verification before calibration.
- Add conservation verification where applicable.
- Add convergence evidence for every numerical solver.
- Keep calibration and validation cases disjoint.
- Carry applicability, provenance, quality, and termination metadata into
  results.

## Required completion report

Return:

```text
selected milestone/work ID and title
dependency and gate evidence
files changed
contracts/equations implemented
behavior and failure semantics
compatibility impact
tests added
numerical or conservation evidence
pytest result
ruff result
pyright result
build and wheel-smoke result
documentation/registry updates
remaining limitations
next eligible work IDs, without starting them
```

If a dependency or architecture decision is genuinely unresolved, stop and
report the exact blocking decision. Do not invent a local workaround that
changes shared consumer semantics.
