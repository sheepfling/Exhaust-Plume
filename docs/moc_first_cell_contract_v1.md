# Planar MOC first-cell contract v1

This document freezes the numerical boundary for the next solver fidelity
lane. It is intentionally separate from the compatibility-backed
`shock-cell-basic-v1` provider. The basic provider remains engineering-
approximate visual geometry until a later validated MOC provider is accepted.

## Scope of this tranche

The implementation in `exhaust_plume.models.moc` currently provides:

- radians-based Prandtl–Meyer evaluation and a bracketed inverse;
- the finite asymptotic-angle domain check;
- Mach angle and planar `K+ = theta - nu`, `K- = theta + nu` invariants;
- compatible interior characteristic points from one `C+` and one `C-` ray;
- centerline compatibility with an exact `theta = 0` boundary state;
- an open, triangular underexpanded expansion-fan mesh from the nozzle lip to
  ambient-pressure axis intersections;
- an attached-compression pressure inversion with weak/strong branch status
  and a supersonic-downstream check;
- a local ambient-pressure tangent segment with explicit finite extent,
  pressure residual, and tangent residual;
- mesh connectivity diagnostics that distinguish a topologically bounded
  polygon from an unresolved physical boundary;
- structured scalar, invariant, and forward-ray geometry residuals.

The fan mesh is intentionally open: it does not close the compression side,
solve a free-boundary/shock endpoint, or claim a physical Mach-disk location.
No public provider is wired to these primitives yet. The module does not claim
axisymmetric, reacting, viscous, or experimentally validated plume physics.

## State and units

The independent plane is `(x, y)` in metres, with `+x` downstream and
`theta` measured counter-clockwise from `+x`. Mach, `gamma`, `nu`, and `mu`
are dimensionless or radians as named. Every state is supersonic (`M > 1`);
the sonic limit is represented only by scalar inversion at `M = 1`.

For a state `(theta, nu)`, the invariants are

```text
K+ = theta - nu
K- = theta + nu
```

An interior point formed from an incoming `C+` state `A` and `C-` state `B`
uses

```text
theta_P = (K+_A + K-_B) / 2
nu_P    = (K-_B - K+_A) / 2
```

The state is solved before geometry. Characteristic directions use the
average of the source and target angles, and intersections are required to be
forward on both parameterized rays. A finite least-squares or backward point
is never reported as a converged MOC point.

## Failure and acceptance semantics

`ScalarRootResult` and `CharacteristicPointResult` preserve status, residual,
iteration count, and bracket/intersection diagnostics. The following are
distinct:

- `outside_domain`: the requested Prandtl–Meyer state is not finite or would
  require an asymptotic Mach number;
- `geometry_failure`: characteristic rays are parallel, ill-conditioned, or
  intersect behind a source;
- `invariant_failure`: the geometry exists but compatibility residuals exceed
  tolerance;
- `max_iterations`: a declared numerical limit was reached.

The current tests establish dense forward/inverse round trips, near-sonic and
high-Mach conditioning, pressure-ratio inversion, invariant closure, and
forward centerline/interior geometry. They are primitive evidence only; they
do not authorize replacing the basic provider or accepting a product claim.

## Next gates before provider integration

1. Close the ambient-pressure free boundary and compression side, with
   explicit shock-endpoint semantics; the current pressure and tangent
   primitives do not choose a physical location.
2. Demonstrate grid/refinement convergence for underexpanded and mild attached
   overexpanded reference cases.
3. Compare an independent cold-jet case through an explicit measurement
   operator and uncertainty model.
4. Only then route an explicitly versioned MOC provider through the visual
   product contract; downstream shock-train and optical/FPA products remain
   separate lanes.
