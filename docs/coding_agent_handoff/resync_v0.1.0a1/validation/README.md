# Validation corpus snapshot

This directory records the Version 8 validation corpus used by the post-`0.1.0a1` execution plan.

The source corpus is experiment-centric: measured tables, digitized published figures, modeled source states, derived summaries, and acquisition backlogs remain separate evidence layers. Runtime VIS/SIG/RAY DTOs must not replace these observations.

## Corpus status

- Corpus version: `0.8.0`
- Benchmark definitions: 17
- Source records: 19
- Indexed products: 60
- Alignment mappings: 78
- Cross-product rules: 7
- Validation gates: 11
- Validation tests in the source corpus: 57 passing

## Immediate benchmark lanes

- `CJ-UEJ-001`: canonical cold underexpanded-jet pressure, velocity, Mach, shock phase and spacing.
- `RP-HOTWAKE-001`: hot solid-motor chamber pressure, Mach-disk position, and unsteady frequency features.
- `RW-IGE-001`: rotor outwash velocity profiles for curved/washed-plume validation.
- `RP-BSUV2-001`: high-altitude sensor-space UV spectral radiance.
- `RP-EMAP-RAD-001`: relative UV/visible and FTIR spectral shape plus radiative heat flux.
- `RP-ALSI-001`: band radiance, power, and composition-response cohort.
- `RP-FASTRAC-001`: near-nozzle extinction/radiance plausibility envelope.
- `RP-IMP-001`: NASA CR-150348 acquisition backlog; no appendix values were inferred.

## Integrity

The complete source archive used for this handoff has SHA-256:

`79c2a34dd4c43bd976ceb8773fdccd78a2592d903bf03ca57c2aef82f882e9aa  plume_validation_data_v8.zip`

The companion alignment archive has SHA-256:

`569aa7f0572f454a1a539b2fbecd977107aced9cab8eb2e65f01c814f8494ceb  plume_mvp_validation_alignment_v1.zip`

The repository handoff intentionally carries the execution plan, evidence taxonomy, measurement-operator registry, product alignment, and corpus summary rather than treating a generated ZIP as a runtime package dependency.
