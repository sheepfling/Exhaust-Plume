# v1 lifecycle cleanup

The three primary products share one provider lifecycle:

```text
ProductProvider
    → ProductSession
        → ProductSnapshot
            → CapabilitySpec + typed request
                → typed v1 result
```

The product payloads remain independent:

- `plume.visual.sectioned-tube@1` returns geometry and feature channels;
- `plume.signature.spectral-radiant-intensity@1` returns unresolved source
  spectral radiant intensity; and
- `plume.optical.spectral-ray-transfer@1` returns resolved source radiance and
  background transmittance.

## Completed migration slice

`ShockCellVisualProvider` now adapts the bounded straight shock-cell solver
into the canonical visual product. It uses the same typed request/result and
immutable snapshot contract as the prescribed, straight analytical, and
signature-table providers.

Termination metadata is now defined in `contracts.termination`, independent of
the old provider snapshot ABI. The old snapshot module re-exports those types
for compatibility.

## Compatibility-only surfaces

The following modules remain importable for the 0.1.x release line but are
closed to new product work:

- `exhaust_plume.api.contracts` and `exhaust_plume.api.lifecycle`;
- `exhaust_plume.contracts.snapshot`;
- `exhaust_plume.providers.lifecycle` and `exhaust_plume.providers.static`;
- the pre-v1 DTOs under `exhaust_plume.products`.

`exhaust_plume.providers.compatibility` is the explicit compatibility import
boundary for the old provider lifecycle and static fixture. Removal requires a
new major-version migration review; no GPU, FPA, or ray-intersection work is
part of this cleanup.

## Validation

The cleanup slice passes 280 tests, Ruff, Pyright, deterministic public-schema
and fixture validation, a wheel/sdist build, and the installed-wheel smoke
test. The remaining legacy warnings are deliberate compatibility notices for
`calculatePlumeZones` and related solver names; they are not new product
interfaces.
