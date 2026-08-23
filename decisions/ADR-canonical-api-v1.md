# ADR — Canonical public API and v1 wire authority

- **Status:** Accepted for `API-008A`
- **Baseline:** `main@49d6ffd1839258ce14319e157002005c6d2230e1`
- **Target release:** `0.1.0a2`

## Decision

`exhaust_plume.api` is the only public semantic namespace for new plume
provider and product work. Its versioned wire facade is
`exhaust_plume.api.v1`.

The already-shipped Pydantic v1 models under `exhaust_plume.contracts` remain
the serialization authority. `exhaust_plume.api.v1` re-exports those exact
classes, capability specifications, schema registry, and schema generator;
it does not define a second model tree. Therefore the checked-in schemas and
fixtures continue to be generated from one model set.

The current review-witness DTOs in `exhaust_plume.api.contracts` remain
importable for 0.1.x compatibility, but they are not a source for new wire
fields or new provider semantics. Their lifecycle and DTO differences are
recorded in the [API-008A crosswalk](../docs/api_008a_symbol_wire_crosswalk.md)
and will be resolved through the subsequent API-008B/008C work.

The existing `products`, `providers`, and package-root imports remain
compatibility surfaces during 0.1.x. No provider is ported or removed in this
decision. New provider conformance work must target the canonical facade after
API-009 establishes the shared harness.

## Wire-field rules

- Existing v1 JSON field names, units, frame identifiers, enum values, and
  placeholder rules are frozen for 0.1.x.
- A field rename requires an explicit migration rule and a new capability major
  version; no silent aliasing is permitted in serialized output.
- `null` plus validity/status masks remain the representation for unavailable
  spectral samples; JSON NaN and infinity remain invalid.
- Visual geometry, unresolved signature, and resolved ray transfer remain
  separate products. A visual result cannot be used as a signature or optical
  medium by implication.
- Provider-private zones, stations, grids, and meshes do not become public
  wire DTOs. `PlumeFluxSection` remains the only physical regime handoff until
  the handoff packet explicitly refines it.

## Lifecycle boundary

The current `exhaust_plume.api` lifecycle names are the public semantic
boundary for the next API packet. The repository also contains legacy
`contracts` and provider lifecycle protocols with different construction and
dispatch methods. API-008B must select and adapt one implementation before a
new provider is added. API-008A intentionally makes no provider-port change.

## Compatibility window

| Surface | 0.1.x disposition | New-work rule | Planned action |
| --- | --- | --- | --- |
| `exhaust_plume.api.v1` | canonical facade | use directly | retain and extend only from the wire authority |
| `exhaust_plume.contracts` v1 models | wire authority and compatibility imports | prefer `api.v1` imports | retain through v1; add deprecation guidance after API-010 |
| `exhaust_plume.api.contracts` | review-witness compatibility DTOs | do not add fields | map or deprecate after API-008B/008C |
| `exhaust_plume.products` DTOs/workflows | implementation compatibility | use only through adapters | port providers in PRV-001..003 |
| `exhaust_plume.providers` implementations | existing providers | no new provider in API-008A | conform in API-009/PRV packets |
| package root | compatibility convenience exports | examples move to `api.v1` | curate at API-010 without deletion in 0.1.x |

## Rejected alternatives

### Keep both DTO systems authoritative

Rejected because it would allow field, lifecycle, and capability drift in every
future provider.

### Replace the shipped wire models immediately

Rejected because it would break the checked-in schemas, golden fixtures, and
working visual/signature consumers without a migration rule.

### Make `contracts` the permanent public namespace

Rejected because the architecture requires a stable public API boundary that
can evolve independently from the implementation package layout.
