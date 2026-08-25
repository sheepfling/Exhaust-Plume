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
  averaged-characteristic compatibility axis intersections, with direct
  lip-ray intersections retained as a separate geometry diagnostic;
- an attached-compression pressure inversion with weak/strong branch status
  and a supersonic-downstream check;
- a turn-prescribed attached-compression state solve with weak/strong branch
  status, downstream supersonic-state reconstruction, and explicit detached
  turn rejection;
- a mild-overexpanded lip-shock branch with an explicit first centerline
  intersection and rejection of unsupported pressure ratios;
- a local ambient-pressure tangent segment with explicit finite extent,
  pressure residual, and tangent residual;
- a reflected `C+` march from centerline-compatible states to a sequence of
  ambient-pressure boundary points with per-point geometry and residual
  diagnostics;
- an assembled reflected characteristic lattice with axis-strip, interior,
  and free-boundary cells plus connected one-perimeter topology diagnostics;
- a boundary-side attached shock-to-centerline segment candidate with explicit
  turn, branch, positioned downstream characteristic state, and
  forward-endpoint diagnostics;
- a prescribed-boundary post-shock continuation primitive that marches
  downstream `C-` characteristics from sampled shock states to the symmetry
  line while checking forward geometry, invariant residuals, and total-
  pressure loss;
- mesh connectivity diagnostics that distinguish a topologically bounded
  polygon from an unresolved physical boundary;
- a shared averaged-characteristic fan/reflected interface whose combined
  cells pass connected one-perimeter topology checks;
- structured scalar, invariant, and forward-ray geometry residuals.

The fan mesh is intentionally open: it does not close the compression side,
solve a free-boundary/shock endpoint, or claim a physical Mach-disk location.
The turn-prescribed compression primitive is state-side evidence only: it
does not select a shock location, assemble a reflected characteristic, or
close the first-cell topology.
The reflected-boundary march and characteristic-zone assembler now assemble
the centerline, interior, and pressure-matched boundary network. The result is
still physically open until a compression/shock endpoint and post-shock
characteristic continuation are solved. The current shock-to-centerline
operation reconstructs a positioned downstream supersonic state and its
total-pressure loss, but it remains only a boundary-side candidate; it does
not prove that downstream characteristics or total-pressure bookkeeping close
across the full plume cell. The prescribed-boundary continuation primitive now
proves individual downstream `C-` traces when a sampled post-shock boundary is
supplied. It deliberately does not fit the shock or synthesize the missing
downstream `C+` interior field from the two-point candidate, so canonical
first-cell closure remains open.
No public provider is wired to these primitives yet. The module does not claim
axisymmetric, reacting, viscous, or experimentally validated plume physics.

## External source review

The NASA-CR-169257 underexpanded-jet study is useful as a topology warning,
not as a bound validation fixture for this repository. It covers Mach 1.4 and
2.1 convergent-nozzle jets and describes the higher-pressure case as having
intercepting compression waves connected by a normal shock or Riemann-wave
region. That behavior is consistent with keeping shock coalescence and
post-shock continuation as explicit implementation gates rather than closing
the current open lattice with a single geometric segment. The report is source
context only here; no digitized NASA flowfield or independent MOC solution is
accepted as a provider-bound reference in this branch.

Source: [NASA NTRS record 19820022412](https://ntrs.nasa.gov/citations/19820022412)
and its public report [NASA-CR-169257 PDF](https://ntrs.nasa.gov/api/citations/19820022412/downloads/19820022412.pdf).

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

1. Supply a sampled, shock-fitted downstream boundary and assemble/validate
   the characteristic zones adjacent to the shock-to-centerline candidate,
   including explicit post-shock total-pressure bookkeeping and shock-endpoint
   topology.
2. Demonstrate grid/refinement convergence for the assembled reflected zone,
   underexpanded, and mild attached overexpanded reference cases.
3. Compare an independent cold-jet case through an explicit measurement
   operator and uncertainty model.
4. Only then route an explicitly versioned MOC provider through the visual
   product contract; downstream shock-train and optical/FPA products remain
   separate lanes.
