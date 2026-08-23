# Provider Taxonomy and Composition

## 1. Taxonomy purpose

This taxonomy gives planning language for provider families without turning
those labels into incompatible public interfaces.

## 2. Four independent descriptors

### Morphology

```text
straight
curved
rotor-washed
crossflow-deflected
multi-source/general-3d
```

### Flow fidelity

```text
none/signature-only
empirical
reduced-order analytical
integral conservation model
imported field/surrogate
Euler/RANS/LES
```

### Radiation fidelity

```text
none
gray LTE
band/correlated-k
line-by-line LTE
non-LTE
particle/scattering coupled
```

### Time model

```text
steady
quasi-steady sequence
transient
stochastic/ensemble
```

These four descriptors plus validation/applicability metadata are sufficient
for selection and provenance. Do not collapse them into one ordinal fidelity.

## 3. Provider composition patterns

### Pattern A — Direct signature

```text
SignatureTableProvider
   -> directional-spectral-intensity
```

No geometry is exposed or required.

### Pattern B — Analytical flow + radiation adapters

```text
ShockCellAnalyticalProvider
   -> axisymmetric-zone-field
       + OpticalPropertyModel
         -> spectral-ray-transfer
             -> FarFieldFromRays
                 -> directional-spectral-intensity
```

### Pattern C — Near field + downstream continuation

```text
ShockCellAnalyticalProvider
   -> handoff state at shock-train termination
       -> IntegralStraightPlumeProvider
           -> CompositeSpatialPlume
```

The composite snapshot can expose a single spatial support and local-state
view while retaining segment provenance.

### Pattern D — Straight to curved environmental continuation

```text
Nozzle/near-field provider
   -> handoff flux state
       + AmbientFlowField
         -> CurvedIntegralPlumeProvider
```

The curved provider owns deflection and wash physics. The downstream consumer
still sees standard spatial/radiometric capabilities.

### Pattern E — High-fidelity field, low-bandwidth product

```text
CFD/LES offline run
   -> radiative postprocessing
       -> directional signature table
           -> SignatureTableProvider
```

This is a high-fidelity provenance product with a signature-only capability.
It demonstrates why capability is not fidelity.

## 4. Handoff state between providers

Provider chaining should use a neutral conservative handoff state rather than
passing one provider's internal zone type.

Recommended first contract:

```python
@dataclass(frozen=True)
class PlumeFluxSection:
  center_plume_m: tuple[float, float, float]
  normal_plume: tuple[float, float, float]
  area_m2: float
  mass_flow_kg_s: float
  momentum_flux_plume_n: tuple[float, float, float]
  total_enthalpy_flux_w: float
  species_mass_flow_kg_s: tuple[tuple[str, float], ...]
  pressure_pa: float
  characteristic_radius_m: float
  provider_metadata: Mapping[str, object]
####
```

The defining invariants are conservation quantities, not a particular
cross-sectional shape.

For a uniform section:

\[
\dot m=\rho u_n A,
\]

\[
\mathbf \Pi
=\dot m\,\mathbf u+(p-p_a)A\mathbf n,
\]

\[
\dot H_0=\dot m h_0.
\]

A richer provider may additionally expose profile moments or full fields.

## 5. Composite provider

A `CompositePlumeProvider` may orchestrate multiple provider segments while
presenting one snapshot.

Responsibilities:

- create each segment with explicit handoff contracts;
- combine spatial support conservatively;
- route spatial queries to the appropriate segment;
- compose ray transfer in front-to-back order;
- sum unresolved independent source intensity only when occlusion/attenuation
  assumptions allow it;
- preserve per-segment provenance.

It must not erase validity boundaries between segments.

## 6. Curved plume geometric contract

For reduced-order curved plumes, use centerline arc length \(s\):

\[
\mathbf c(s),\quad
\mathbf t(s)=\frac{d\mathbf c}{ds},\quad
A(s),\quad
R(s).
\]

A local query point may be parameterized by

\[
\mathbf x=\mathbf c(s)+\eta\mathbf n(s)+\zeta\mathbf b(s).
\]

The transported frame should use a numerically stable convention such as a
parallel-transport frame; Frenet frames are unsuitable at vanishing curvature.

Curvature is therefore a property of one spatial capability implementation,
not a new top-level plume interface.
