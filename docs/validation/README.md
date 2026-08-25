# Validation corpus intake

The merged validation handoff describes two external, content-addressed
archives. The Version 8 corpus archive has now been recovered from a
user-provided attachment and verified against its expected digest. The
separately named product-alignment archive is still missing; the recovered
corpus contains an embedded alignment overlay, but that is not silently treated
as the separately hashed archive.

The intake gate is:

```bash
python scripts/verify_validation_corpus.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --alignment /path/to/plume_mvp_validation_alignment_v1.zip \
  --output validation-intake-report.json
```

The command succeeds only when both files exist, match their recorded SHA-256
digests, are valid ZIP archives, and contain no path-traversal or duplicate
members. It never extracts or modifies the supplied archives.

After the corpus archive passes intake, run the alignment preflight against the
same file:

```bash
python scripts/validate_external_corpus_alignment.py \
  --corpus /path/to/plume_validation_data_v8.zip \
  --output external-alignment-preflight.json
```

The preflight verifies the 17 benchmark definitions, 19 source records, 60
indexed products, 78 mappings, 20-row summary, seven cross-product rules, 11
gates, and all 137 internal checksums. It reports unresolved operator IDs and
provider-comparison gates as release blockers rather than treating a
structurally valid corpus as product validation.

The recovered corpus intake evidence is recorded in
[`corpus_intake_report_v1.json`](corpus_intake_report_v1.json). It matched the
handoff SHA-256, passed safe-ZIP inspection, verified all 137 internal checksum
entries, and passed all 57 source-corpus tests. Do not create synthetic
replacements for the still-missing alignment archive. Keep raw observations
separate from derived tables, digitized curves, modeled states, and
product-alignment records.

The handoff currently reports 17 benchmark definitions, 19 source records, 60
indexed products, 78 alignment mappings, 11 validation gates, and 57 source-
corpus tests. Those counts are claims about the referenced archive until the
archive itself is recovered and independently verified.

The intake gate is a prerequisite for external validation claims. Corpus
integrity tests are not product validation: repository contract tests and
physics regressions must still be run through the named VIS, SIG, and future
RAY/FPA measurement operators before a product claim is accepted.

## Typed claim registry

`exhaust_plume.validation.claims` loads the committed product catalog,
measurement-operator registry, and evidence-level taxonomy without importing
or rewriting experimental observations. It provides typed
`BenchmarkDefinition`, `MeasurementOperatorSpec`, and `ValidationClaim`
records. Quantitative claims require an explicit operator, uncertainty, and
provenance; an unacquired evidence level cannot be marked accepted.
