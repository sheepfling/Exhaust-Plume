# Consumer Profiles and Query Contracts

## 1. Why consumer profiles exist

Consumer profiles are convenience descriptions of common capability bundles.
They are not base classes and do not constrain provider implementations.

## 2. Signature profile

Required capability:

```text
directional-spectral-intensity v1
```

Optional capabilities:

```text
spatial-support v1
uncertainty v1
```

### Query

```python
@dataclass(frozen=True)
class DirectionalSpectralIntensityQuery:
  wavelength_m: NDArray[np.float64]       # (n_lambda,)
  source_to_observer_direction_plume: NDArray[np.float64]  # (n_view, 3)
####
```

Snapshot time is already bound to the `PlumeSnapshot`. If a stateless source
is preferred, time may be an explicit query coordinate, but the semantic
product remains the same.

### Result

```python
@dataclass(frozen=True)
class DirectionalSpectralIntensityResult:
  wavelength_m: NDArray[np.float64]
  source_to_observer_direction_plume: NDArray[np.float64]
  spectral_radiant_intensity_w_sr_m: NDArray[np.float64]  # (n_view, n_lambda)
  quality_flags: tuple[str, ...]
  provenance_id: str
####
```

### Physics quantity

\[
J_\lambda(\hat{\mathbf s})
=\int_{A_\perp}L_{\lambda,\mathrm{source}}(u,v,\hat{\mathbf s})\,du\,dv.
\]

A direct table provider may supply \(J_\lambda\) without evaluating the
integral at runtime.

## 3. Spatial engineering profile

Minimum useful capability:

```text
spatial-support v1
```

Typical additional capabilities:

```text
axisymmetric-zone-field v1
centerline-tube-field v1
local-flow-state v1
projected-area v1
```

Spatial support is intentionally weaker than a mesh. It answers where the
plume may contribute without claiming a unique plume surface.

### Conservative spatial support

```python
@dataclass(frozen=True)
class SpatialSupport:
  plume_frame_aabb_min_m: tuple[float, float, float]
  plume_frame_aabb_max_m: tuple[float, float, float]
  characteristic_extent_m: float
  support_definition: str
  is_conservative: bool
####
```

## 4. Resolved radiometry profile

Required capability:

```text
spectral-ray-transfer v1
```

Query:

```text
observer_origin_plume_m        (n_ray,3)
observer_to_scene_direction    (n_ray,3)
maximum_distance_m             (n_ray,)
wavelength_m                   (n_lambda,)
```

Result:

```text
source_spectral_radiance       (n_ray,n_lambda)
background_transmittance       (n_ray,n_lambda)
```

with transfer semantics

\[
L_{\lambda,\mathrm{out}}
=
L_{\lambda,\mathrm{source}}
+
T_\lambda L_{\lambda,\mathrm{background}}.
\]

Returning source radiance and transmittance separately is mandatory because a
plume can attenuate vehicle, terrain, sky, or Earth radiance behind it.

## 5. Physical-field coupling profile

Required capability:

```text
local-flow-state v1
```

or a provider-specific structured field capability such as
`axisymmetric-zone-field` or `centerline-tube-field`.

Canonical local state, when available:

\[
\mathbf q=
(\rho,p,T,\mathbf u,\mathbf Y,\text{particles}).
\]

Not every provider must supply every component. The capability schema must
state required/optional fields and quality flags.

## 6. Point-source validity

A signature product does not guarantee that the source is unresolved at an
arbitrary observer range.

Providers should expose at least one of:

```text
minimum_valid_observer_range_m
characteristic_extent_m
angular_validity_model
```

A consumer may evaluate

\[
\chi=\frac{R}{D_\mathrm{source}}.
\]

If its own point-source criterion fails, it should reject the approximation or
request resolved ray transfer when available.

## 7. Consumer selection algorithm

A consumer should:

1. declare the semantic product it needs;
2. inspect the provider descriptor;
3. request the capability and compatible major version;
4. validate wavelength/time/angular/spatial applicability;
5. batch queries according to the execution profile;
6. preserve returned provenance and quality flags.

It must not select a provider by testing whether it is named `LowFidelity` or
`CurvedPlume`.
