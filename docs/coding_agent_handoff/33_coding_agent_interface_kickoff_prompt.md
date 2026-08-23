# Coding-Agent Prompt: Unified Provider Interface Foundation

Implement only the provider-interface foundation described by:

```text
00_unified_plume_architecture.md
28_consumer_profiles_and_query_contracts.md
29_provider_taxonomy_and_composition.md
30_provider_contracts_v1.md
31_unified_conformance_and_testing.md
32_merged_implementation_roadmap.md
10_coding_agent_execution_protocol.md
25_migration_release_and_compatibility_plan.md
```

## Scope

Create the additive provider/session/snapshot/capability contracts and a fake
provider conformance suite. Do not implement new plume physics, spectroscopy,
external-consumer integration, or curved-plume dynamics in this PR.

## Required design

- provider-specific strongly typed Definition/Configuration/OperatingState;
- generic capability-bearing snapshots;
- explicit capability IDs and major versions;
- separate morphology, fidelity, applicability, and execution metadata;
- two semantic product paths supported by contracts:
  - unresolved directional spectral intensity;
  - spatial/resolved products;
- geometry must remain optional;
- capability absence must raise a typed error;
- snapshot lifetime semantics must be representable;
- existing solver API must remain unchanged.

## Coding requirements

- Python 3.12+ project target where the migration plan allows it;
- complete type annotations;
- NumPy typing for numerical arrays;
- frozen public contracts;
- preserve existing TODOs;
- end every scope with `####` according to project convention;
- pytest, ruff, and pyright coverage;
- concise durable documentation only.

## Tests

At minimum add fake providers demonstrating:

1. a signature-only table-like provider with no geometry;
2. a spatial-only analytical-like provider with no radiation;
3. a provider exposing both ray transfer and directional intensity;
4. explicit unsupported capability failure;
5. capability version mismatch failure;
6. independent versus invalidatable snapshot semantics;
7. provider descriptor separation of morphology/fidelity/execution.

## Completion report

Report:

```text
files changed
contracts introduced
compatibility impact
tests added
pytest result
ruff result
pyright result
remaining non-goals
```

Do not proceed to physics refactoring in the same PR.
