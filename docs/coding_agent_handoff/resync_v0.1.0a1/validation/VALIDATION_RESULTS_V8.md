# Version 8 Validation Results

## Scope

Version 8 adds an architecture-alignment layer connecting the Version 7 validation corpus to the three MVP products. It does not change any experimental measurement, modeled source state, digitized curve, or derived experimental summary from Version 7.

## Product-alignment checks

- Three exact primary product IDs are defined.
- Seventy-eight alignment records cover all 55 Version 7 corpus products.
- Every alignment declares a relationship, target, readiness state, and claim ceiling.
- Direct product-gate evidence requires a primary-product target, a direct or measurement-space relationship, and an explicit measurement operator.
- Scenario inputs, quality-control summaries, provenance, and acquisition backlogs cannot be promoted to direct product-gate evidence.
- All three primary products have at least one gate-eligible observation, with the documented scope limitations.
- Seven cross-product rules include the permitted `RAY -> SIG` derivation and prohibit unsupported `SIG -> RAY`, `VIS -> SIG`, `VIS -> RAY`, and `SIG -> VIS` inference.
- Eleven validation gates cover T0 contract, T1 component, T2 product, T3 cross-product, and T4 operational levels.
- The committed `mvp_product_coverage_summary.csv` contains one row for each
  of the eight catalog entries, and its product IDs and coverage fields are
  consistent with the catalog. The larger 20-row summary cited in the source
  corpus is not present in this public handoff and is not treated as a
  repository-local validation artifact.

## Regression and determinism checks

- All 55 Version 7 inventory products are byte-for-byte unchanged in Version 8.
- The alignment builder reproduced the eight generated/updated alignment files byte-for-byte on a second run.
- Python compilation passed for `src`, `scripts`, and `tests` in the source corpus.
- The configured 100-character source-line scan found no violations.
- `pytest` completed with 57 passing tests.
- The package checksum manifest verified 137 files.
- A clean ZIP extraction passed all 137 checksum checks, Python compilation, and the complete 57-test suite.

## Tooling limitation

Ruff and Pyright executables were not installed in the corpus-building runtime, so those two checks were not executed there.

## Claim-level result

| Product | Contract | Component | Product evidence | Cross-product | Current claim ceiling |
|---|---|---|---|---|---|
| VIS | External API harness | Ready | Partial | Synthetic/provider-generated | Shock-feature and ambient-forcing evidence; full hot-plume section envelope pending. |
| SIG | External API harness | Ready | Partial | Synthetic/provider-generated | Sensor-space and relative-shape evidence; complete intrinsic absolute time-angle spectrum pending. |
| RAY | External API harness | Ready | Partial | Synthetic/provider-generated | Optical components and integrated observables; independent per-ray source/transmittance truth pending. |

No stronger claim is authorized by Version 8.
