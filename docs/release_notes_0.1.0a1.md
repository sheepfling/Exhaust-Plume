# Exhaust Plume `0.1.0a1`

The `0.1.0a1` release is the reproducible merged baseline for the initial
visual and spectral lookup products. It is identified by the immutable tag
[`v0.1.0a1`](https://github.com/sheepfling/Exhaust-Plume/releases/tag/v0.1.0a1)
and its release evidence is recorded in
[`docs/release_gate_0.1.0a1.md`](release_gate_0.1.0a1.md).

## Included

- Prescribed sectioned-tube visual product and mesh export helpers.
- Unresolved spectral radiant-intensity lookup and CSV/JSON export.
- Versioned public contract schemas and deterministic contract fixtures.
- Shock-cell analytical and conservative plume interface compatibility paths.
- Reproducible source and wheel artifacts whose hashes are recorded in
  [`docs/release_gate_0.1.0a1.sha256`](release_gate_0.1.0a1.sha256).

## Verification

The merged baseline passed Ruff, Pyright, 238 pytest cases, package build,
fresh installed-wheel smoke, all four CLI help checks, and the Python 3.10 to
3.13 CI matrix. The complete evidence is in the release-gate report.

## Known limitations

This alpha does not claim validated infrared physics, resolved spectral ray
transfer, a canonical washed-plume provider, validated method-of-
characteristics shock-train physics, or downstream acceleration. The visual
fixture is prescribed integration data, not a calibrated plume measurement.
Existing compatibility and numerical diagnostics remain documented in the
release-gate report.
