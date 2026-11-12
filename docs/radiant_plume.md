# Radiant Plume

## Capability-family identity

**Radiant Plume** is the human-facing name for the propulsive-plume capability developed in this repository.

**Descriptor:** A modular propulsive-plume capability for visualization, source signatures, and downstream focal-plane evaluation.

**Tagline:** *Visualize the plume. Evaluate its signature. Compose the focal plane.*

The name is deliberately scoped below a complete IR scene, propagation, sensor, or detector simulation environment. Radiant Plume is intended to remain one composable capability family inside a possible broader future simulation ecosystem.

The repository/package name `exhaust-plume`, Python namespace `exhaust_plume`, and versioned `plume.*` capability identifiers are technical contracts and are not renamed by this branding decision.

## Product suite and technical capabilities

The Exhaust-Plume suite is organized around three user-facing products. Visualization and Signature describe plume-source products; Focal-Plane Array (FPA) is a downstream composition product.

| Suite product | Presentation name | Technical contract or output | Boundary |
| --- | --- | --- | --- |
| **Visualization** | Radiant Plume Shape | `plume.visual.sectioned-tube@1` | Renderer-neutral geometry and supported field views; display geometry does not establish physical support or radiometric validity. |
| **Signature** | Radiant Plume Signature | `plume.signature.spectral-radiant-intensity@1` | Unresolved source spectral radiant intensity over wavelength and direction; table-backed engineering results do not claim validated physical spectra. |
| **Focal-Plane Array (FPA)** | Focal-Plane Array | `plume.image.spectral-radiance@1` (registered downstream image identity) | Composes eligible source/ray results through camera, optics, exposure, and detector operators. Current deterministic adapters are not an externally validated FPA provider. |

The current provider lifecycle also exposes the resolved spectral ray-transfer capability, `plume.optical.spectral-ray-transfer@1`. **Sightline** is its optional human-facing label. Ray transfer is a supporting capability for downstream image formation, not a fourth top-level suite product. No provider currently advertises a validated FPA image capability, and no measured-image claim is accepted.

Product names are presentation language; capability IDs remain the durable machine-facing contract names. Support for a source product does not imply support for downstream ray transfer or FPA composition.

### Radiant Plume Shape

Shape is the human-facing name for the visual geometry lane. Its v1 technical product is a sectioned centerline tube with oriented sections, radii, optional feature channels, and visual bounds.

Shape can represent straight, curved, washed, or asymmetric plume geometry when a provider supports those morphologies. A Shape result is not automatically a conservative physical support volume, radiative medium, or validated plume-end prediction.

### Radiant Plume Signature

Signature is the human-facing name for intrinsic unresolved source emission. Its v1 technical quantity is wavelength-resolved spectral radiant intensity,

\[
J_\lambda(t, \hat{\mathbf{s}})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}],
\]

as a function of time, wavelength, and source-to-observer direction.

Signature is source-only unless a different capability explicitly includes atmosphere, range, optics, or detector effects.

### Sightline: resolved ray-transfer capability

Sightline is the optional human-facing label for resolved spectral ray transfer. Its v1 technical capability returns source radiance and background transmittance separately over requested rays and wavelengths.

This separation allows a caller-owned scene background to remain outside the plume model. Sightline supports participating-medium rendering and downstream image composition, but it is not a separate top-level suite product and the contract does not claim that a validated physical radiation provider is implemented.

## Provider model

Morphology and fidelity belong to providers, not to separate public product families. The same product lane may be supplied by different providers with different applicability, provenance, and fidelity claims.

Expected provider families include:

- straight analytical exhaust plumes;
- shock-cell and shock-diamond plumes;
- curved or crossflow-deflected plumes;
- rotor- or prop-washed exhaust plumes;
- asymmetric or general three-dimensional plumes;
- tabulated or prescribed sources;
- imported CFD/RANS/LES fields;
- future accelerated or GPU transient providers.

The architecture keeps the following dimensions independent:

- morphology;
- flow fidelity;
- radiation fidelity;
- time model;
- execution backend;
- validation level.

A provider may expose only the capabilities it can support honestly.

## Relationship to a future IR ecosystem

Radiant Plume should be treated as one scene-element capability rather than the name of a complete simulation platform.

A future ecosystem could compose Radiant Plume with independent capabilities such as:

- atmosphere and propagation;
- vehicle and surface models;
- terrain and backgrounds;
- sensor optics and detector models;
- scene orchestration and time synchronization.

Keeping those concerns outside the Radiant Plume brand avoids over-claiming maturity and leaves room for the plume work to become a reusable component of a larger FLITES-like architecture later.

## Naming policy

Use **Radiant Plume** in presentations, roadmaps, product sheets, demonstrations, and high-level documentation.

Use these human-facing names for the three suite products:

- **Radiant Plume Shape** for Visualization
- **Radiant Plume Signature** for unresolved source emission
- **Focal-Plane Array (FPA)** for downstream camera/detector composition

Use **Sightline** only as an optional label for the resolved ray-transfer capability; do not present it as a fourth suite product.

Use the existing technical capability IDs in code, schemas, fixtures, tests, and transport contracts:

- `plume.visual.sectioned-tube@1`
- `plume.signature.spectral-radiant-intensity@1`
- `plume.optical.spectral-ray-transfer@1` (supporting ray-transfer capability)
- `plume.image.spectral-radiance@1` (registered downstream image identity; not advertised by current providers)

Do not create `radiant_plume.*` duplicate capability IDs solely for branding.

## Current maturity boundary

The branding is intentionally broader than the presently implemented physical fidelity, but it must not obscure current limits.

At the current repository boundary:

- the visual lane has deterministic prescribed and analytical sectioned-tube workflows;
- the signature lane has a neutral table-backed lookup workflow and does not infer physical spectra from plume thermodynamics;
- the resolved ray-transfer capability has a public contract but does not yet claim a validated physical provider;
- the deterministic downstream FPA adapters are engineering boundaries only; there is no provider-bound or measured-image validation claim;
- the active analytical plume physics remains a constant-`gamma` ideal-gas study model;
- curved/washed plume work, advanced radiation, thermochemistry, detector effects, and accelerated execution remain separate follow-on fidelity paths unless explicitly implemented and validated.

Provider claims, applicability, provenance, uncertainty, and validation evidence remain authoritative. Branding never upgrades an engineering approximation into a validated physical product.

## Executive summary copy

> **Radiant Plume** is a modular propulsive-plume capability with three user-facing products: **Shape/Visualization** for renderer-neutral plume views, **Signature** for unresolved source spectral radiant intensity, and **Focal-Plane Array** for downstream camera and detector composition. **Sightline** names the supporting resolved ray-transfer capability. Providers and adapters retain explicit fidelity, provenance, applicability, and validation boundaries.
