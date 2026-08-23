# Exhaust-Plume Coding-Agent Handoff — Version 4

## Purpose

This repository-ready directory is the implementation handoff for evolving
`sheepfling/Exhaust-Plume` on `feature/initial-work` from an idealized
shock-cell geometry study into a staged, verified plume-flow and
infrared-signature provider package.

Recommended repository placement:

```text
docs/coding_agent_handoff/
```

Copy the directory without flattening it so relative links, manifests,
registries, source plans, and prompts remain valid.

## Start here

Version 4 adds one authoritative program-level execution plan:

- [`34_comprehensive_work_plan.md`](34_comprehensive_work_plan.md) — complete
  architecture, workstreams, milestones M0–M15, dependencies, gates, parallel
  lanes, validation, migration, risks, and completion criteria.
- [`35_first_execution_wave.md`](35_first_execution_wave.md) — exact opening
  branch/PR sequence through provider contracts, corrected physics foundation,
  `ShockCellAnalyticalProvider`, and `SignatureTableProvider`.
- [`36_coding_agent_program_lead_prompt.md`](36_coding_agent_program_lead_prompt.md)
  — coordinating prompt that selects and executes one dependency-ready work
  packet at a time.
- [`work_plan.yaml`](work_plan.yaml) — machine-readable milestones, critical
  path, parallel paths, deliverables, gates, and immediate queue.
- [`execution_graph.yaml`](execution_graph.yaml) — machine-readable work-unit
  dependency graph.

## Core architecture decision

There are **two major consumer use cases, not two incompatible plume APIs**:

1. **Signature consumer** — needs intrinsic unresolved spectral radiant
   intensity versus time, wavelength, and source-to-observer direction;
   geometry may remain internal or absent.
2. **Spatial/physical consumer** — needs conservative support, geometry, local
   flow/thermochemical state, optical-medium state, resolved ray transfer, or
   focal-plane products.

Straight, curved, rotor-washed, tabulated, analytical, imported-field, and
future GPU/CFD implementations use one provider/session/snapshot lifecycle.
Morphology, flow fidelity, radiation fidelity, time behavior, and execution
behavior remain orthogonal metadata. Geometry is an optional capability.

## Source snapshot

```text
repository: sheepfling/Exhaust-Plume
branch: feature/initial-work
snapshot date: 2026-08-22
handoff version: 4
```

Reviewed source blobs:

```text
src/exhaust_plume/models/plume/plume_solve.py
  sha: 25768f15afafa5863f5cb30a0aaee0d8a04aaf8d

src/exhaust_plume/models/plume/motor_parameters.py
  sha: ad3a436ef5c971c64a0291e136dfa0cba7eb020e

src/exhaust_plume/util/aero/oblique_shock.py
  sha: 8d98ccd5820052832ff8e210f7e5931574a893a3

docs/mathematical_model.tex
  sha: 6758309c7af8ffa306d9f6ddee9e76539cdf02b6
```

Re-audit a file before implementing its packet if its blob SHA has changed.

## Current model classification

The reviewed implementation should be treated as:

> An inviscid, constant-\(\gamma\), planar shock-cell construction with
> approximate geometry.

It is not yet a validated axisymmetric MOC solution, a physical predictor of
shock-cell count, a turbulent mixing model, a reacting rocket plume, or a
spectral radiative-transfer model. One physical plume contains a sequence of
shock cells; repeated construction passes are not separate plumes.

## Document layers

### Layer A — Unified provider architecture

- [`00_unified_plume_architecture.md`](00_unified_plume_architecture.md)
- [`28_consumer_profiles_and_query_contracts.md`](28_consumer_profiles_and_query_contracts.md)
- [`29_provider_taxonomy_and_composition.md`](29_provider_taxonomy_and_composition.md)
- [`30_provider_contracts_v1.md`](30_provider_contracts_v1.md)
- [`31_unified_conformance_and_testing.md`](31_unified_conformance_and_testing.md)
- [`32_merged_implementation_roadmap.md`](32_merged_implementation_roadmap.md)
- [`33_coding_agent_interface_kickoff_prompt.md`](33_coding_agent_interface_kickoff_prompt.md)

### Layer B — Physics and validation

1. [`01_model_contract_and_architecture.md`](01_model_contract_and_architecture.md) — units, assumptions, model levels, contracts, and module boundaries.
2. [`02_foundation_corrections_plan.md`](02_foundation_corrections_plan.md) — equation, gas-property, shock, regime, and geometry corrections.
3. [`03_validated_first_cell_plan.md`](03_validated_first_cell_plan.md) — planar characteristic compatibility, free boundary, and first-cell solve.
4. [`04_shock_train_and_termination_plan.md`](04_shock_train_and_termination_plan.md) — coherent-core decay, downstream cells, and physical termination.
5. [`05_integral_mixing_plume_plan.md`](05_integral_mixing_plume_plan.md) — entrainment, mass, momentum, enthalpy, species, and field reconstruction.
6. [`06_spectral_ir_plan.md`](06_spectral_ir_plan.md) — gray and molecular line-of-sight radiation versus view angle.
7. [`07_thermochemistry_and_particles_plan.md`](07_thermochemistry_and_particles_plan.md) — frozen/equilibrium/finite-rate chemistry and particles.
8. [`08_validation_and_test_matrix.md`](08_validation_and_test_matrix.md) — analytic cases, conservation, convergence, and external validation.

### Layer C — Project execution and source provenance

9. [`09_issue_backlog.md`](09_issue_backlog.md) — dependency-ordered physics issue backlog.
10. [`10_coding_agent_execution_protocol.md`](10_coding_agent_execution_protocol.md) — branch, scope, typing, numerical, testing, and reporting rules.
11. [`11_coding_agent_kickoff_prompt.md`](11_coding_agent_kickoff_prompt.md) — original Phase 0 kickoff prompt.
12. [`12_reference_sources.md`](12_reference_sources.md) — source and validation-fixture provenance.

### Layer D — Implementation specifications

13. [`13_architecture_decision_records.md`](13_architecture_decision_records.md) — settled decisions and review triggers.
14. [`14_api_contracts_and_serialization.md`](14_api_contracts_and_serialization.md) — enums, configuration, immutable results, schemas, and compatibility.
15. [`15_plume_provider_interface.md`](15_plume_provider_interface.md) — swappable analytical, curved, tabulated, and CFD provider interface.
16. [`16_equation_traceability_matrix.md`](16_equation_traceability_matrix.md) — equation-to-code-to-test ownership.
17. [`17_numerical_algorithms_and_pseudocode.md`](17_numerical_algorithms_and_pseudocode.md) — bracketed solves, MOC, ODE, ray, and RTE algorithms.
18. [`18_scientific_data_and_calibration_plan.md`](18_scientific_data_and_calibration_plan.md) — data identity, calibration, and artifacts.
19. [`19_uncertainty_and_sensitivity_methods.md`](19_uncertainty_and_sensitivity_methods.md) — residuals, identifiability, covariance, propagation, and applicability.

### Layer E — Agent work packets and release control

20. [`20_phase_0_patch_blueprint.md`](20_phase_0_patch_blueprint.md) — file-by-file corrected-foundation blueprint.
21. [`21_phase_0_foundation_task_packets.md`](21_phase_0_foundation_task_packets.md) — `FND-A` through `FND-F` packets.
22. [`22_phase_1_first_cell_task_packets.md`](22_phase_1_first_cell_task_packets.md) — `MOC-A` through `MOC-F` packets.
23. [`23_agent_prompts_and_gate_checklists.md`](23_agent_prompts_and_gate_checklists.md) — ready-to-paste prompts and concise gates.
24. [`24_end_to_end_acceptance_scenarios.md`](24_end_to_end_acceptance_scenarios.md) — cross-module scenarios.
25. [`25_migration_release_and_compatibility_plan.md`](25_migration_release_and_compatibility_plan.md) — additive migration, deprecation, schemas, and releases.
26. [`26_risk_register_and_open_decisions.md`](26_risk_register_and_open_decisions.md) — scientific, numerical, software, and delivery risks.
27. [`27_release_gates_and_definition_of_done.md`](27_release_gates_and_definition_of_done.md) — CI, evidence, convergence, phase gates, and no-go criteria.

### Layer F — Master execution control

34. [`34_comprehensive_work_plan.md`](34_comprehensive_work_plan.md) — authoritative complete work plan.
35. [`35_first_execution_wave.md`](35_first_execution_wave.md) — immediate branch/PR sequence.
36. [`36_coding_agent_program_lead_prompt.md`](36_coding_agent_program_lead_prompt.md) — one-packet-at-a-time program prompt.

## Machine-readable and combined artifacts

- [`work_plan.yaml`](work_plan.yaml)
- [`execution_graph.yaml`](execution_graph.yaml)
- [`provider_architecture.yaml`](provider_architecture.yaml)
- [`equation_registry.yaml`](equation_registry.yaml)
- [`handoff_manifest.yaml`](handoff_manifest.yaml)
- [`ALL_PLANS.md`](ALL_PLANS.md)
- [`SHA256SUMS.txt`](SHA256SUMS.txt)
- [`CHANGELOG.md`](CHANGELOG.md)

The original uploaded interface plans are retained under
`source_interface_plans/` for provenance. The merged documents above are
authoritative where wording differs.

## Recommended coding-agent start

Read:

```text
34_comprehensive_work_plan.md
35_first_execution_wave.md
36_coding_agent_program_lead_prompt.md
work_plan.yaml
execution_graph.yaml
```

Then execute:

```text
M0  architecture and repository baseline
M1  PR I0 provider contract foundation
M2  FND-A through FND-F and PR I1
M3  PR I2 ShockCellAnalyticalProvider
```

`M10 / PR I6 SignatureTableProvider` may proceed in a separate branch after
M1 because it does not depend on corrected analytical plume physics.

## Non-negotiable rules

1. SI units internally.
2. Radians internally; degrees only at CLI/display/legacy boundaries.
3. Explicit gas properties; no hidden dry-air rocket state.
4. Fully typed immutable public contracts.
5. Structured physical and numerical failures.
6. Physical termination and safety/domain truncation are different results.
7. Successful closed zones contain no placeholder nonfinite geometry.
8. Correlations and closures carry provenance and applicability.
9. Calibration and validation datasets are disjoint.
10. A revolved planar solution is not called axisymmetric gas dynamics.
11. Geometry is optional at the provider boundary.
12. Morphology and fidelity do not create separate consumer APIs.
13. Preserve TODOs unless the assigned task explicitly resolves them.
14. Use Python 3.12+, Pytest, Ruff, Pyright, and build checks.
