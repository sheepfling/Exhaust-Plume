# Plume MVP Validation Alignment — Version 1

This package aligns the three MVP product contracts with the Version 7 source-centric validation corpus without rewriting the source data.

## Contents

- `MVP_DATA_PRODUCT_ALIGNMENT.md` — authoritative narrative and release position.
- `mvp_product_catalog.csv` — three primary and five supporting product semantics.
- `measurement_operator_registry.csv` — experiment-equivalent adapters required before scoring.
- `evidence_level_taxonomy.csv` — Levels 0-4 and permitted claim language.
- `mvp_product_coverage_summary.csv` — current coverage and principal gaps.
- `mvp_product_validation_spec.yaml` — machine-readable products, claim rules, and release suites.
- `cross_product_invariants.yaml` — SIG/RAY/VIS/support consistency requirements.
- `source_manifest.csv` — hashes of the planning and corpus sources.

## Key rule

A benchmark validates a product only after the provider output is passed through an explicit measurement operator that reproduces the experiment's coordinates, integration, response, and uncertainty semantics.
