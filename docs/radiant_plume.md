# Radiant Plume

## Capability-family identity

**Radiant Plume** is the human-facing name for the propulsive-plume capability developed in this repository.

**Descriptor:** A modular propulsive-plume capability for visualization, infrared signatures, and resolved spectral ray transfer.

**Tagline:** *From shape, to signature, to sightline.*

The name is deliberately scoped below a complete IR scene, propagation, sensor, or detector simulation environment. Radiant Plume is intended to remain one composable capability family inside a possible broader future simulation ecosystem.

The repository/package name `exhaust-plume`, Python namespace `exhaust_plume`, and versioned `plume.*` capability identifiers are technical contracts and are not renamed by this branding decision.

## Three product lanes

Radiant Plume has three independently versioned consumer-facing lanes behind the common provider/session/snapshot lifecycle.

| Human-facing name | Technical product | Capability ID | Consumer intent |
| --- | --- | --- | --- |
| **Radiant Plume Shape** | Visual sectioned-tube geometry | `plume.visual.sectioned-tube@1` | Coarse visualization, scene placement, geometry-driven integration |
| **Radiant Plume Signature** | Unresolved spectral radiant intensity | `plume.signature.spectral-radiant-intensity@1` | Far-field or unresolved source-signature consumers |
| **Radiant Plume Sightline** | Resolved spectral ray transfer | `plume.optical.spectral-ray-transfer@1` | Imaging, focal-plane, and ray-resolved integrations |

These product names are presentation language only. They do not create a new omnibus result type, and support for one lane does not imply support for the others.

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

### Radiant Plume Sightline

Sightline is the human-facing name for resolved spectral ray transfer. Its v1 technical product returns source radiance and background transmittance separately over requested rays and wavelengths.

This separation allows a caller-owned scene background to remain outside the plume model. Sightline is the intended lane for future participating-medium rendering, imaging, and focal-plane integrations, but the existence of the contract does not itself claim that a validated physical radiation provider is implemented.

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

Use the following human-facing product names when an audience benefits from concise lane names:

- **Radiant Plume Shape**
- **Radiant Plume Signature**
- **Radiant Plume Sightline**

Use the existing technical capability IDs in code, schemas, fixtures, tests, and transport contracts:

- `plume.visual.sectioned-tube@1`
- `plume.signature.spectral-radiant-intensity@1`
- `plume.optical.spectral-ray-transfer@1`

Do not create `radiant_plume.*` duplicate capability IDs solely for branding.

## Current maturity boundary

The branding is intentionally broader than the presently implemented physical fidelity, but it must not obscure current limits.

At the current repository boundary:

- the visual lane has deterministic prescribed and analytical sectioned-tube workflows;
- the signature lane has a neutral table-backed lookup workflow and does not infer physical spectra from plume thermodynamics;
- the resolved ray-transfer lane has a public contract but does not yet claim a validated physical ray-transfer provider;
- the active analytical plume physics remains a constant-`gamma` ideal-gas study model;
- curved/washed plume work, advanced radiation, thermochemistry, detector effects, and accelerated execution remain separate follow-on fidelity paths unless explicitly implemented and validated.

Provider claims, applicability, provenance, uncertainty, and validation evidence remain authoritative. Branding never upgrades an engineering approximation into a validated physical product.

## Executive summary copy

> **Radiant Plume** is a modular propulsive-plume capability spanning three independently usable product lanes: **Shape** for geometry and visualization, **Signature** for unresolved spectral source intensity, and **Sightline** for resolved spectral ray transfer. Providers can range from prescribed and analytical models to curved, washed, imported-field, and future accelerated implementations while preserving common consumer contracts and explicit fidelity, provenance, and applicability semantics.
