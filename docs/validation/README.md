# Validation corpus intake

The merged validation handoff describes two external, content-addressed
archives. The archives are not present in the repository or in the public
release assets; this directory records the exact expected digests and keeps
their absence explicit.

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

Do not create synthetic replacements for the missing corpus. After recovery,
record the retrieval URL or source location, UTC retrieval time, license or
redistribution status, and the immutable local path in the intake manifest.
Keep raw observations separate from derived tables, digitized curves, modeled
states, and product-alignment records.

The handoff currently reports 17 benchmark definitions, 19 source records, 60
indexed products, 78 alignment mappings, 11 validation gates, and 57 source-
corpus tests. Those counts are claims about the referenced archive until the
archive itself is recovered and independently verified.

The intake gate is a prerequisite for external validation claims. Repository
contract tests and synthetic physics regressions may run before it, but they
must not be reported as validation against the missing corpus.
