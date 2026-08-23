# Radiometry and External-Consumer Integration

## Unresolved source contract

The intrinsic far-field plume product should be spectral radiant intensity:

\[
I_\lambda(t,\hat{s})
\qquad
\left[\frac{\mathrm W}{\mathrm{sr}\,\mathrm m}\right]
\]

where `hat{s}` is the unit vector from the source toward the observer, expressed in the plume/source-local frame.

This quantity is independent of:

- sensor range;
- atmosphere;
- aperture size;
- optical throughput;
- focal length;
- detector quantum efficiency;
- detector noise;
- detection threshold.

Those belong downstream.

## Why the query should be batched

The API should be an evaluator, not an eagerly materialized 4-D tensor.

Typical query dimensions:

```text
n_view x n_wavelength
```

Time is normally bound to a snapshot or supplied as an epoch to the external-consumer source adapter.

For an axisymmetric plume:

\[
I_\lambda(t,\hat{s}) = I_\lambda(t,\mu),
\qquad
\mu = \hat{s}\cdot\hat{x}_{plume}
\]

but the generic API should still use 3-D direction vectors so non-axisymmetric plumes work without changing the contract.

## Resolved ray-transfer contract

For image/focal-plane rendering, the provider should return the affine plume transfer along each observer ray:

\[
L_{\lambda,out}
=
L_{\lambda,source}
+
T_\lambda L_{\lambda,background}
\]

The ray result contains:

```text
source_spectral_radiance_w_m2_sr_m
background_transmittance
```

This allows composition with vehicle surfaces, sky, terrain, Earth background, or other scene sources.

Returning only plume radiance would not represent attenuation of things behind the plume.

## Direction convention for rays

Use an observer-centric ray query:

```text
observer_origin_plume_m
observer_to_scene_direction_plume
maximum_distance_m
wavelength_m
```

## Far-field intensity derived from rays

A ray-transfer provider can be adapted into an unresolved source by orthographic integration:

\[
I_\lambda(\hat{s})
=
\int_{A_\perp}
L_{\lambda,source}(\mathbf b,\hat{s})\,dA_\perp
\]

The unit conversion is:

\[
\frac{\mathrm W}{\mathrm{m^2\,sr\,m}}\,\mathrm{m^2}
=
\frac{\mathrm W}{\mathrm{sr\,m}}
\]

The reverse transformation is impossible in general: unresolved intensity cannot reconstruct a resolved image.

## The external consumer should own the source port

The consumer's core radiometric interface should be source-domain only:

```text
epoch_tai_ns
wavelength grid
source-local source-to-observer directions
    -> directional spectral intensity
```

Exhaust-Plume should not import a consumer package. Instead, an integration adapter wraps an Exhaust-Plume session and state provider.

## Source pose is separate from source emission

The consumer also needs a `SourcePoseProvider`:

```text
epoch
 -> source position in GCRS
 -> source-from-GCRS quaternion
```

Do not assume the plume axis is identical to the target velocity direction. A velocity-aligned provider may be a low-fidelity pose implementation, but the interface should remain explicit.

For sensor position `r_s`, source position `r_p`, and source-from-inertial rotation `C_P<-I`:

\[
R = ||r_s-r_p||
\]

\[
\hat{d}^I = \frac{r_s-r_p}{R}
\]

\[
\hat{d}^P = C_{P\leftarrow I}\hat{d}^I
\]

`hat{d}^P` is passed to the source evaluator.

## External-consumer point-source propagation

For a source whose directional spectral radiant intensity is `I_lambda`:

\[
E_\lambda
=
\frac{\tau_\lambda I_\lambda}{R^2}
\]

where `tau_lambda` is path transmittance and `E_lambda` is spectral irradiance at the aperture plane.

Collected electrons may be calculated as:

\[
N_e
=
t_{exp} A_{ap}
\int
E_\lambda
T_{opt}(\lambda)
\eta(\lambda)
\frac{\lambda}{hc}
\,d\lambda
\]

with:

- `t_exp`: exposure time;
- `A_ap`: entrance-aperture area;
- `T_opt`: optical throughput;
- `eta`: quantum efficiency.

A simple point-source SNR model can then use:

\[
SNR
=
\frac{N_e}{
\sqrt{
N_e + N_{background} + N_{dark}
+ n_{pixel}\sigma_{read}^2 + \sigma_{other}^2
}}
\]

Only after this should the consumer generate the final canonical detection record and covariance.

## Recommended external-consumer pipeline

```text
1. observation geometry
2. visibility gating
3. source pose transform
4. source evaluation
5. atmosphere/path propagation
6. aperture/optics integration
7. detector electron model
8. noise and SNR
9. detection probability/threshold
10. centroid/image formation
11. canonical measurement record
```

## Batch scheduling

At a given epoch, group observations by:

```text
(source_id, epoch_tai_ns, wavelength_grid_id)
```

Then evaluate all surviving sensor directions in one source call. This avoids recreating the same plume snapshot for every sensor-target pair.

## Point-source validity

Directional intensity assumes a sufficiently unresolved source.

A provider should expose either:

```text
minimum_valid_observer_range_m
```

or enough spatial-extent information for the consumer to test:

\[
\chi = R / D_{source}
\]

When the point-source criterion fails, the consumer should reject the approximation or route the observation to the resolved-ray renderer.

## Composite unresolved sources

For independent unresolved components:

\[
I_{\lambda,total} = \sum_k I_{\lambda,k}
\]

This supports multiple engine plumes, hot nozzle hardware, vehicle skin, and other source components.

For resolved rendering, simple addition is not always valid because components may occult or attenuate one another.
