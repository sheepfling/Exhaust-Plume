# Changelog

## Version 4 — Comprehensive work plan

- Added `34_comprehensive_work_plan.md` as the authoritative dependency-ordered execution plan.
- Added `35_first_execution_wave.md` with the exact opening branch and PR sequence.
- Added `36_coding_agent_program_lead_prompt.md` for one-packet-at-a-time execution.
- Added `work_plan.yaml` with machine-readable milestones, dependencies, deliverables, gates, critical path, and parallel lanes.
- Rebuilt `execution_graph.yaml` around the unified interface and physics work IDs.
- Consolidated provider contracts, corrected physics, shock cells, mixing, curved plumes, radiometry, thermochemistry, validation, migration, and release control into one program.
- Updated README, handoff manifest, combined edition, checksums, and bundle validation.

# Handoff Pack Changelog

## Version 2 — 2026-08-22

Version 2 keeps the original physics roadmap and adds a consolidated
implementation layer:

- architecture decision records;
- exact public API and serialization contracts;
- a swappable plume-provider interface;
- equation-to-code-to-test traceability and a machine-readable registry;
- deterministic numerical algorithms and pseudocode;
- scientific-data, calibration, uncertainty, sensitivity, and applicability
  governance;
- a file-by-file Phase 0 patch blueprint;
- PR-sized Phase 0 and Phase 1 task packets;
- ready-to-paste coding-agent prompts and phase checklists;
- end-to-end acceptance scenarios;
- migration, release, and compatibility rules;
- a risk/open-decision register;
- phase release gates and definitions of done;
- machine-readable execution and handoff manifests.

The directory was curated to remove conflicting duplicate drafts, assign unique
sequential document numbers, repair internal references, and regenerate the
combined edition, checksums, and ZIP bundle.

## Version 1 — 2026-08-21

Initial handoff pack containing the model architecture, foundation, first-cell,
shock-train, mixing, spectral IR, thermochemistry, validation, issue backlog,
execution protocol, kickoff prompt, and source-provenance plans.

## Version 3 — unified provider/interface architecture

- Integrated the separate plume-interface planning package.
- Established two consumer profiles: unresolved signature and spatial/physical.
- Made geometry explicitly optional and permitted internal-only geometry.
- Separated morphology, flow fidelity, radiation fidelity, and execution behavior.
- Added provider/session/snapshot lifecycle and capability-major-version rules.
- Added conservative provider-to-provider flux-section composition.
- Added straight, curved/rotor-washed, table, imported-field, and GPU provider taxonomy.
- Added unified contract/conformance tests and merged interface/physics roadmap.
- Retained original interface plans under `source_interface_plans/` for provenance.
