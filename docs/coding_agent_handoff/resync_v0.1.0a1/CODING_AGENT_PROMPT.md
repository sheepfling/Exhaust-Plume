# Coding-agent prompt — Exhaust-Plume post-0.1.0a1

Work from the live `sheepfling/Exhaust-Plume` default branch pinned by `SOURCE_BASELINE.json`.

Do not restart obsolete BASE/API foundation packets. First reproduce the pinned tree and current quality gates. Then execute one dependency-ready work packet from `planning/backlog.yaml` per PR.

Start with `VAL-001` unless the repository has materially advanced beyond the pinned SHA.

For every PR:

- preserve existing public compatibility unless the packet explicitly requires a versioned change;
- keep VIS, SIG, and RAY independently versioned;
- keep experimental observations separate from runtime product DTOs;
- declare every measurement operator used for external comparison;
- preserve provenance, applicability, uncertainty, validity, and claim scope;
- include unit/contract/conformance/numerical tests appropriate to the packet;
- run pytest, Ruff, Pyright, build, and installed-wheel smoke checks when available;
- report exact commands and results;
- do not implement downstream packets opportunistically;
- do not claim physical validation beyond the evidence level in the alignment material.

Primary evidence inputs are under `validation/` and `alignment/`.

The target critical path is:

`VAL-001 -> VAL-002 -> PHYS-001 -> PHYS-002 -> MIX-001 -> MIX-002 -> RAY-001 -> RAY-002 -> CROSS-001 -> RAD-VAL-001`

The curved lane may proceed after the neutral handoff foundation:

`CURVE-001 -> CURVE-002 -> CURVE-003 -> CURVE-004`
