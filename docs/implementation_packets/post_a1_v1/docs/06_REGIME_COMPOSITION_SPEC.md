# Shock-to-mixing composition specification

## Current limitation

The release can construct a `PlumeFluxSection` directly from a nozzle exit, but a true composite provider needs a downstream section after the coherent shock-cell region is weak enough for the pressure-matched integral model.

## Handoff quantities

At a handoff plane with normal `n`, preserve:

\[
\dot m=\int_A \rho u_n\,dA,
\]

\[
\mathbf P=\int_A \rho u_n\mathbf u\,dA+\int_A(p-p_a)\mathbf n\,dA,
\]

\[
\dot H=\int_A\rho u_n\left(h+\frac{|\mathbf u|^2}{2}\right)dA,
\]

and every species mass flow.

## Transition diagnostics

Require persistent satisfaction of:

- mean pressure mismatch tolerance;
- pressure-oscillation amplitude tolerance;
- successive-cell momentum/energy change tolerance;
- finite closed-section geometry;
- valid pressure-thrust accounting.

A fixed number of shock diamonds is not a physical transition rule.

## Composite provider

```text
ShockCellAnalyticalProvider
  -> pressure-aware downstream PlumeFluxSection
      -> StraightIntegralPlumeProvider or WashedIntegralPlumeProvider
          -> one immutable composite snapshot
```

The composite result must retain one provenance/derivation chain and distinguish physical transition, requested construction truncation, downstream domain limit, equilibrium, and failure.
