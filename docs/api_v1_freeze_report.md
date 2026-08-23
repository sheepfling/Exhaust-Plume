# API-010 — v1 API freeze report

Status: **accepted for the 0.1.0a2 development line**.

The canonical public authority is `exhaust_plume.api.v1`, backed by the
existing `exhaust_plume.contracts.*_v1` wire models. The lifecycle is
`ProductProvider → ProductSession → ProductSnapshot → one typed product`.
The frozen capability and asset inventory is recorded in
[`public_contract_freeze_v1.json`](../schemas/public_contract_freeze_v1.json).

The reviewed code head is `282fe02`, based on the merged alpha baseline
`49d6ffd`. The review includes API-008A/B/C, the API-009 conformance harness,
canonical-facade ports for the prescribed, straight analytical, and signature
providers, and the legacy prescribed compatibility shell.

## Accepted contract boundaries

- Sectioned-tube visualization is geometry/feature data only; it does not
  imply spectral signature or ray transfer.
- Signature lookup is unresolved source spectral radiant intensity. It does
  not claim atmospheric transmission, optics, detector response, or pixels.
- Ray transfer is a separate resolved product with explicit source radiance,
  background transmittance, validity, and hit/miss semantics.
- `PlumeFluxSection` remains a neutral conservative engineering handoff and is
  not a rendering mesh or radiometric field.
- Units are explicit SI quantities; frames are named right-handed frames and
  quaternions use `(x, y, z, w)` ordering.
- Unsupported capability, unsupported major, invalid request, and
  applicability failures remain distinct structured outcomes.

## Evidence

The final local gate recorded 270 passing tests, Ruff pass, Pyright pass,
deterministic Draft 2020-12 schema/fixture generation and drift validation,
successful package build, and a passing installed-wheel smoke test.

Four real providers pass the shared conformance harness. Legacy spatial/static
providers are explicitly waived because their older ABI has not been silently
promoted. Physical shock-train, washed-plume, optical-field, ray-intersection,
CPU/GPU, and FPA work remains deferred; none is needed to define v1 meaning.

The old prescribed API remains available through a compatibility shell backed
by the canonical provider. Existing root imports and 0.1.x envelopes remain
supported, with removal no earlier than a future incompatible release.
