# Unified Provider Conformance and Testing

## 1. Test layers

Every provider has four independent test layers:

```text
contract conformance
provider-specific physics verification
cross-provider semantic equivalence
consumer integration
```

## 2. Universal snapshot invariants

Verify:

- descriptor capability registry equals actual capability objects;
- capability major versions are explicit;
- definition/configuration/operating-state inputs are not mutated;
- immutable or defensively copied result arrays;
- finite values unless the capability explicitly permits masks;
- provenance is present;
- applicability and quality flags are preserved;
- unsupported capabilities fail explicitly;
- deterministic providers reproduce identical results;
- snapshot retention rules are enforced.

## 3. Signature capability conformance

For `directional-spectral-intensity v1`:

Input requirements:

```text
wavelengths finite, positive, strictly increasing
view directions finite unit vectors
```

Output requirements:

```text
shape = (n_view,n_lambda)
finite
nonnegative
same requested ordering
correct units W/(sr m)
```

Axisymmetric invariant:

\[
J_\lambda(\hat{\mathbf s}_1)
=J_\lambda(\hat{\mathbf s}_2)
\]

whenever both directions have the same dot product with the plume axis.

## 4. Ray-transfer conformance

A miss must return exactly:

```text
source radiance = 0
background transmittance = 1
```

For consecutive homogeneous segments:

\[
L_{out}=S_2(1-T_2)+T_2\left[S_1(1-T_1)+T_1L_{bg}\right].
\]

The capability result must reproduce this composition.

## 5. Rich-to-simple equivalence

For a provider exposing both ray transfer and directional intensity, compare
native unresolved intensity against orthographic integration of ray source
radiance:

\[
J_\lambda(\hat{\mathbf s})
=\int L_{\lambda,source}\,dA_\perp.
\]

The comparison tolerance is provider/fidelity-specific and must be documented.

## 6. Signature table tests

- exact grid points reproduce stored data;
- interpolation is deterministic;
- extrapolation defaults to rejection;
- table asset digest participates in provenance;
- angular coordinate conventions are unit tested;
- table periodicity/symmetry assumptions are explicit.

## 7. Shock-cell provider tests

In addition to the physics verification suite:

- provider output matches direct solver output for legacy benchmark states;
- current geometry never leaks placeholder NaN polygons;
- current construction-limit termination is marked nonphysical;
- `maximum_construction_passes` maps deterministically to legacy `num_plumes`;
- provider capability absence prevents premature IR claims.

## 8. Curved provider tests

- zero crossflow reduces to the straight-provider baseline within tolerance;
- rigid rotation/translation of environmental inputs produces the equivalent
  transformed plume;
- transported frame remains continuous through zero-curvature regions;
- spatial support conservatively encloses the centerline/tube field;
- source/ray results remain in the canonical plume frame;
- curvature does not change signature/ray API semantics.

## 9. Cross-fidelity semantic tests

When multiple providers represent the same canonical condition, compare only
products they both claim.

Examples:

```text
shock analytical vs CFD surrogate:
  first-cell length
  spatial support
  selected pressure diagnostics

ray-derived signature vs signature table:
  J_lambda(direction)

straight integral vs curved provider at zero external flow:
  centerline
  radius
  integral fluxes
```

These tests verify semantic interoperability, not numerical identity between
different fidelity models.

## 10. Consumer swap test

One consumer pipeline must be exercised without code changes against at least:

```text
constant fixture source
signature-table source
analytical plume + ray adapter source
```

A spatial consumer should similarly be able to swap straight analytical and
curved reduced-order providers when both implement the requested capability.
