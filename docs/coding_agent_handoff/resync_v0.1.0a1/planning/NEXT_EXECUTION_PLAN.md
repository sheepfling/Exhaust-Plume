# Next execution plan after v0.1.0a1

## P0 — External validation foundation

### VAL-001 — Validation claim + measurement-operator architecture
Add typed benchmark definitions, validation claims, measurement-operator identifiers, uncertainty/provenance, evidence levels, claim ceilings, and registry loading. Import the semantics from the Version 8 alignment package without mutating experimental source values.

**Gate:** experiments remain source-centric; runtime products remain consumer-centric; comparison requires an explicit operator.

### VAL-002 — Canonical shock-cell benchmark
Wire `CJ-UEJ-001` into quantitative tests for axial pressure, velocity, Mach number, shock-cell phase, and spacing.

**Gate:** first external component/product evidence for the straight analytical path; cold-jet scope remains explicit.

### VAL-003 — Hot-plume feature benchmark
Wire `RP-HOTWAKE-001` into Mach-disk-position and unsteady-frequency comparisons.

**Gate:** feature-level visual/flow validation with published evidence scope; no unsupported full-envelope claim.

## P0 — Shock-cell physics completion

### PHYS-001 — Coherent finite shock train
Extend the current first/low-order construction to a coherent train with local spacing, coherent-core shrinkage, oscillation decay, and topology diagnostics.

### PHYS-002 — Physical termination
Replace requested construction count as the only practical end mechanism with explicit weak-wave / ambient-equilibrium / domain termination semantics. Report physical vs truncation reason.

**Gate:** cell count is an output; safety maximum is only a bound.

## P1 — Conservative downstream composition

### MIX-001 — Neutral flux-section handoff
Implement/finish a neutral `PlumeFluxSection` equivalent preserving mass, vector momentum, total enthalpy, and optional species/passive-scalar flux.

### MIX-002 — Straight integral provider composition
Connect shock-cell output to the existing straight integral kernel through the neutral handoff and expose downstream support/local fields through standard capabilities.

**Gate:** conservation closes across the handoff and zero-mixing/limiting cases are explicit.

## P1 — Curved / washed provider productization

### CURVE-001 — Curved provider lifecycle
Wrap the existing curved kernel behind the same provider/session/snapshot lifecycle. Do not create a morphology-specific consumer API.

### CURVE-002 — AmbientFlowField / rotor wash
Implement a standard ambient-flow contract that can accept actuator-disk, prescribed, measured, or imported wake fields.

### CURVE-003 — Curved VIS/support adapter
Expose centerline tube/section geometry, conservative support, and applicable field channels through the existing VIS/support contracts.

### CURVE-004 — Curved validation
Use `RW-IGE-001` first, then HART-II when acquired. Require zero-crossflow equivalence, rigid-transform covariance, frame continuity, and conservation.

## P1 — Physical ray transfer

### RAY-001 — Gray transfer kernel
Implement exact homogeneous-segment transfer, source radiance, background transmittance, miss-ray behavior, layer ordering, and analytic slab/chord tests.

### RAY-002 — Axisymmetric ray geometry + batching
Connect current/next plume fields to the ray-transfer product contract.

### CROSS-001 — FarFieldFromRays
Implement

`J_lambda(s_hat) = integral_Aperp L_lambda,source dA`

and enforce cross-product semantics and provenance.

### RAD-VAL-001 — External optical gates
Use EMAP, BSUV2, Fastrac, and Al/Si evidence through the declared measurement operators. Do not promote relative spectra to absolute source intensity.

## P2 — Spectral/chemical fidelity

Proceed only after gray transfer and external-observable gates are stable:

- molecular cross sections / opacity assets;
- temperature/pressure interpolation;
- variable-property thermodynamics;
- CEA boundary-state adapter;
- frozen/equilibrium reference paths;
- finite-rate afterburning;
- particle population, temperature, absorption/emission/scattering;
- atmosphere/detector adapters;
- imported CFD/RANS/LES fields;
- GPU/transient/general-3D execution.

## Governance / cleanup

Before large new public API work, resolve whether `exhaust_plume/api/*` or `exhaust_plume/contracts/*` + `products/*` is the authoritative public surface. Prefer deprecation/isolation over two independently evolving contract families.

There were no open repository issues at the resync point. Convert the backlog in this packet into dependency-ordered GitHub issues rather than relying on stale issue names from the older handoff.
