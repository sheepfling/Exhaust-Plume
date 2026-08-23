# Coding-Agent Kickoff Prompt

Use the following prompt to begin Phase 0.

---

You are implementing the foundation-corrections phase for the public repository
`sheepfling/Exhaust-Plume`, starting from branch
`feature/initial-work`.

Read these handoff files before editing code:

```text
docs/coding_agent_handoff/README.md
docs/coding_agent_handoff/01_model_contract_and_architecture.md
docs/coding_agent_handoff/02_foundation_corrections_plan.md
docs/coding_agent_handoff/08_validation_and_test_matrix.md
docs/coding_agent_handoff/09_issue_backlog.md
docs/coding_agent_handoff/10_coding_agent_execution_protocol.md
```

The reviewed source snapshot used these key blobs:

```text
plume_solve.py:
25768f15afafa5863f5cb30a0aaee0d8a04aaf8d

motor_parameters.py:
ad3a436ef5c971c64a0291e136dfa0cba7eb020e

oblique_shock.py:
8d98ccd5820052832ff8e210f7e5931574a893a3
```

First compare the current branch to that snapshot. If the affected code has
changed materially, document the differences and adapt only where the
mathematical intent remains valid.

Create or use:

```text
feature/foundation-corrections
```

Execute Phase 0 in dependency order. Start with the smallest reviewable group:

```text
FND-001  gas and nozzle contracts
FND-002  choked mass-flow/throat-area correction
FND-003  explicit gas properties and removal of hidden dry-air assumptions
FND-004  energy/enthalpy naming correction
```

Do not begin first-cell MOC, shock-train termination, radiation, or chemistry
work during this group.

Required mathematical corrections include:

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}},
\]

\[
R=R_u/W,
\qquad
\rho=p/(RT),
\]

\[
h_0=h+u^2/2=c_pT_0.
\]

Requirements:

- Python 3.12+.
- Full type annotations.
- Pydantic v2 for validated contracts.
- NumPy/SciPy where numerical work is required.
- Pytest, Ruff, and Pyright clean.
- Preserve existing TODOs.
- End every newly written or materially modified scope with `####`.
- Do not bulk-reformat untouched code.
- Add a failing regression test before fixing each known defect.
- Keep public compatibility wrappers where practical.
- Never log an error and return a nominal success state.
- Use SI units and radians internally.

At the end of this issue group, produce a completion report with:

```text
summary
equations/contracts implemented
files changed
tests added
commands run
numerical evidence
compatibility impact
remaining limitations
next dependency-ready issue
```

Run at minimum:

```bash
python -m pytest <focused tests>
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Do not proceed to the next issue group until this group passes the full quality
gate.

---
