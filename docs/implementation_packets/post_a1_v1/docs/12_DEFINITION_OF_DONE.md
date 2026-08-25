# Definition of Done

A packet is complete only when:

1. All listed acceptance criteria are implemented.
2. No out-of-scope product capability is advertised.
3. Public semantics are documented in units, frames, time policy, provenance, applicability, and fidelity terms.
4. Success and structured-failure tests exist.
5. Exact analytical/conservation evidence is included where applicable.
6. Ruff, Pyright, pytest, build, and installed-wheel smoke pass.
7. Python 3.10–3.13 CI passes.
8. Compatibility impact and migration instructions are explicit.
9. The packet’s status is updated in `planning/work_plan.yaml` only after merge.
10. No later-fidelity feature is used to conceal a failed earlier gate.
