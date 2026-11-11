# Radiant Plume documentation

**Radiant Plume** is the human-facing capability-family name for the exhaust-plume work in this repository.

> Visualize the plume. Evaluate its signature. Compose the focal plane.

Radiant Plume is intentionally narrower than a complete infrared scene or sensor simulation environment. It is the propulsive-plume capability that can live inside a larger future IR simulation ecosystem while keeping the existing package name, provider lifecycle, and versioned `plume.*` technical contracts stable.

## Start here

- [Radiant Plume capability family](radiant_plume.md) — branding, scope, the product and capability map, naming policy, and maturity boundaries.
- [MVP product alignment](mvp_product_alignment.md) — canonical product/code boundaries and allowed derivations.
- [Interface contracts v1](interface_contracts_v1.md) — technical capability identities and lifecycle semantics.
- [Product MVP guide](product_mvp.md) — executable visualization and signature workflows and their current limitations.
- [Mathematical model](mathematical_model.tex) — governing equations and current analytical plume model.
- [Validity envelope](validity_envelope.md) — current finite study envelope and validation matrix.

## Product map

| Suite product | Presentation name | Technical output | Product boundary |
| --- | --- | --- | --- |
| **Visualization** | Radiant Plume Shape | `plume.visual.sectioned-tube@1` | Renderer-neutral plume geometry and supported field views; visualization does not establish radiometric validity. |
| **Signature** | Radiant Plume Signature | `plume.signature.spectral-radiant-intensity@1` | Unresolved source spectral radiant intensity; current table-backed results remain engineering data, not externally validated physical spectra. |
| **Focal-Plane Array (FPA)** | Focal-Plane Array | `plume.image.spectral-radiance@1` (registered downstream image identity) | Composes eligible source and ray data through camera, optics, and detector operators; the current deterministic boundary has no accepted measured-image claim. |

**Sightline** is the human-facing label for the resolved ray-transfer capability, `plume.optical.spectral-ray-transfer@1`. It is a supporting capability in downstream image formation, not a fourth top-level suite product. No provider currently advertises a validated FPA image capability.
