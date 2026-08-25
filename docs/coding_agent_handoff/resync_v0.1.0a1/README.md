# Exhaust-Plume v0.1.0a1 Resync + Next-Work Handoff

This bundle reconciles the live `sheepfling/Exhaust-Plume` `main` branch with the earlier MVP, physics, curved-plume, and validation plans.

## Authoritative repository baseline

- Repository: `sheepfling/Exhaust-Plume`
- Branch: `main`
- `main` commit: `49d6ffd1839258ce14319e157002005c6d2230e1`
- Commit message: `Merge 0.1.0a1 release into main`
- Release-prep commit: `8b37e48b65321403bb3eb4ed0fdfe949dc9f1506`
- Shared tree SHA: `bfd587778b15da8e9b10213d7e680e48b5ae6e1e`
- Release version: `0.1.0a1` / package constant `0.1.0.a1`

The identical tree SHA means live `main` already contains the `0.1.0a1` release tree. No source delta must be reconciled before beginning the next tranche.

## Start here

1. Read `RESYNC_REPORT.md`.
2. Read `planning/NEXT_EXECUTION_PLAN.md`.
3. Use `planning/backlog.csv` or `planning/backlog.yaml` to cut GitHub issues/PRs.
4. Give `CODING_AGENT_PROMPT.md` plus this entire directory to the coding agent.
5. Use the validation and alignment material under `validation/` and `alignment/` as the external evidence/validation basis.

## Core conclusion

Do **not** restart at the old BASE/API foundation tasks. `0.1.0a1` already has the common lifecycle, versioned VIS/SIG/RAY contracts, conformance machinery, straight analytical/visual paths, a table-backed signature MVP, corrected nozzle/shock-cell foundation, straight integral code, and a substantial curved-plume numerical kernel.

The critical path has moved to:

`external validation -> validated shock train -> conservative downstream handoff -> curved-provider productization -> physical ray transfer -> ray-derived signature -> molecular/particle radiation`
