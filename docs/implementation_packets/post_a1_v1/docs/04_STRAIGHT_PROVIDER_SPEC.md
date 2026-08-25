# `StraightIntegralPlumeProvider` specification

## Purpose

Wrap the landed straight integral continuation as the zero-crossflow reference provider for the washed model.

## Required physics correction

The current continuation holds axial momentum constant even when entrained ambient fluid carries nonzero axial momentum. In a uniform ambient field, the provider must implement:

\[
\frac{d\dot m}{ds}=E,
\qquad
\frac{dP}{ds}=E U_a,
\qquad
\frac{d\dot H}{ds}=E\left(h_a+\frac{U_a^2}{2}\right).
\]

Therefore the exact invariants are:

\[
P-\dot m U_a=\mathrm{constant},
\]

\[
\dot H-\dot m\left(h_a+\frac{U_a^2}{2}\right)=\mathrm{constant}.
\]

Quiescent ambient reduces to constant momentum.

## Provider boundary

Input:

- pressure-matched `PlumeFluxSection`;
- uniform ambient thermodynamic/velocity state;
- explicit entrainment configuration;
- finite domain and output sampling configuration.

Products:

- `plume.visual.sectioned-tube@1`;
- `plume.engineering.flux-section@1`.

No signature or ray-transfer advertisement.

## Tests

1. Zero entrainment preserves source state and radius.
2. Quiescent free jet matches the exact top-hat solution.
3. Uniform coflow/counterflow preserves relative momentum and relative energy invariants.
4. Exhaust tracer mass flow is constant.
5. Coordinate and unit validation reject malformed handoffs.
6. Domain termination is explicitly nonphysical.
7. Canonical product snapshots are deterministic and immutable.
8. Compatibility outputs, where retained, are generated from canonical results rather than a second calculation.
