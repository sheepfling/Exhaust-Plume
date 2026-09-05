# Radiant Plume documentation

**Radiant Plume** is the human-facing capability-family name for the exhaust-plume work in this repository.

> From shape, to signature, to sightline.

Radiant Plume is intentionally narrower than a complete infrared scene or sensor simulation environment. It is the propulsive-plume capability that can live inside a larger future IR simulation ecosystem while keeping the existing package name, provider lifecycle, and versioned `plume.*` technical contracts stable.

## Start here

- [Radiant Plume capability family](radiant_plume.md) — branding, scope, three product lanes, naming policy, and maturity boundary.
- [MVP product alignment](mvp_product_alignment.md) — canonical product/code boundaries and allowed derivations.
- [Interface contracts v1](interface_contracts_v1.md) — technical capability identities and lifecycle semantics.
- [Product MVP guide](product_mvp.md) — executable visualization and signature workflows and their current limitations.
- [Mathematical model](mathematical_model.tex) — governing equations and current analytical plume model.
- [Validity envelope](validity_envelope.md) — current finite study envelope and validation matrix.

## Product map

| Human-facing lane | Technical product | Capability ID |
| --- | --- | --- |
| **Radiant Plume Shape** | Visual sectioned-tube geometry | `plume.visual.sectioned-tube@1` |
| **Radiant Plume Signature** | Unresolved spectral radiant intensity | `plume.signature.spectral-radiant-intensity@1` |
| **Radiant Plume Sightline** | Resolved spectral ray transfer | `plume.optical.spectral-ray-transfer@1` |

The human-facing names are presentation and product-family language. The capability IDs remain the durable machine-facing contract names.
