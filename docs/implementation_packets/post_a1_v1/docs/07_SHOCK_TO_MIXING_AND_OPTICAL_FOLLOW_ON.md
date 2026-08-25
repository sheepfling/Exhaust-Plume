# Shock-to-Mixing and Optical Follow-On

## True conservative handoff

The current shock provider can construct an exit-section handoff. A composite physical path requires a declared downstream section where oscillatory near-field structure is sufficiently weak or explicitly integrated.

For handoff plane normal \(\mathbf n\):

\[
\dot m = \int_A \rho u_n\,dA,
\]

\[
\boldsymbol\Pi = \int_A \rho u_n\mathbf u\,dA + \int_A(p-p_a)\mathbf n\,dA,
\]

\[
\dot H_0 = \int_A \rho u_n h_0\,dA,
\qquad
\dot m_k = \int_A \rho u_nY_k\,dA.
\]

Do not drop residual pressure thrust.

## Transition diagnostics

At minimum track:

- mean pressure residual;
- pressure oscillation amplitude;
- cell-to-cell momentum/energy change;
- handoff persistence count;
- whether the event is physical, model-based, or domain-imposed.

## Composite provider

```text
ShockCellAnalyticalProvider
        -> downstream PlumeFluxSection
        -> StraightIntegralPlumeProvider or WashedIntegralPlumeProvider
        -> one composite snapshot/provenance chain
```

## Optical progression

1. exact/convergent ray intervals through support;
2. homogeneous gray LTE segment transfer;
3. multi-segment ordering;
4. curved support;
5. ray-derived spectral image and unresolved integration;
6. molecular opacity and thermochemistry.

The ray contract already separates source radiance from background transmittance; the physical implementation must preserve that meaning.
