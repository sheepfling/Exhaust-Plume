# Validation operator-registry reconciliation

The recovered Version 8 corpus is content-valid, but its embedded alignment
overlay is not wire-compatible with the committed operator registry yet. This
is a contract reconciliation item, not a data-integrity failure.

## Observed inventories

| Source | Product IDs | Alignment mappings | Operator IDs | Gate-eligible mappings |
| --- | ---: | ---: | ---: | ---: |
| Recovered `plume_validation_data_v8.zip` | 3 primary products | 78 | 35 `operator.*` IDs | 10 |
| Committed alignment directory | 8 catalog products | N/A | 16 `op.*` IDs | N/A |

The three primary product IDs agree exactly:

- `plume.visual.sectioned-tube@1`
- `plume.signature.spectral-radiant-intensity@1`
- `plume.optical.spectral-ray-transfer@1`

The operator namespaces do not agree. Examples include
`operator.extract.sectioned_tube_mach_disk_position` in the recovered corpus
and `op.visual.feature-extractor` in the committed registry. Similar-looking
names are not aliases until their input product, observable, metadata,
uncertainty, and benchmark scope are proven equivalent.

## Release treatment

The typed `ValidationRegistry` loads only the committed registry and therefore
does not accept the recovered overlay as if it were already reconciled. The
corpus may be used for source-corpus integrity and alignment analysis, but no
external product claim is promoted to accepted status from an unresolved
operator ID.

The separate `plume_mvp_validation_alignment_v1.zip` named by the handoff is
still required. When recovered, compare its operator registry and crosswalk to
both inventories. If it does not provide an authoritative crosswalk, add one
explicitly with semantic review and tests; do not use string similarity or
prefix replacement as an automatic mapping rule.

## Consequence for product gates

- VIS can use the corpus's shock-feature mappings only after the feature
  operator is mapped to the canonical visual provider output and its metric
  domain is declared.
- SIG can use sensor-space and relative-shape mappings only with an explicit
  line-of-sight/band operator; they do not become intrinsic `J_lambda` claims.
- RAY/FPA mappings remain downstream and require a ray-transfer provider,
  pixel/detector operator, and cross-product lineage checks.

This keeps the recovered data useful immediately while preventing a merge
conflict in governance metadata from becoming a false validation result.
