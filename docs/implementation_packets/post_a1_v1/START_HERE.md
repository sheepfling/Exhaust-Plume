# START HERE — Post-`v0.1.0a1` Exhaust-Plume Implementation Packet

This packet supersedes the older opening-wave sequence for work that has already landed. It is anchored to:

```text
repository: sheepfling/Exhaust-Plume
branch:     main
commit:     49d6ffd1839258ce14319e157002005c6d2230e1
tag:        v0.1.0a1
release:    0.1.0a1
```

Read in this order:

1. `docs/00_EXECUTIVE_SUMMARY.md`
2. `docs/01_RELEASE_BASELINE_AND_GAP_ANALYSIS.md`
3. `docs/02_CANONICAL_ARCHITECTURE.md`
4. `docs/03_RELEASE_ROADMAP.md`
5. `planning/work_plan.yaml`
6. The next dependency-ready file in `work_packets/`
7. `docs/11_CODING_AGENT_DIRECTIVE.md`
8. `qa/VALIDATION_REPORT.md`

## Immediate command

Begin with **A1-000**, not with a feature branch from the pre-release baseline. Every implementation branch must start from `main@49d6ffd1839258ce14319e157002005c6d2230e1` or a later reviewed main commit.

## Binding boundary

- `exhaust_plume.api` is the target canonical v1 product/transport authority.
- Straight, shock-cell, washed, table, imported, and future GPU models are providers.
- Visual, unresolved signature, and resolved ray transfer remain independent products.
- No product may infer unsupported physics from another product.
