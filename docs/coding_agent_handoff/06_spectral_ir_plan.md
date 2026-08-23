# Spectral Infrared Signature Plan

## 1. Purpose

Calculate plume spectral radiance as a function of:

```text
wavelength or wavenumber
viewing angle
image-plane location
sensor range
atmospheric path
sensor spectral response
```

The radiation model must operate on a volumetric temperature, pressure,
composition, velocity, and particle field. Projected area alone is not a
sufficient gas-plume radiation model.

## 2. Implementation stages

### IR-0: Planck and units

Implement Planck radiance, spectral-coordinate conversion, and unit tests.

### IR-1: Gray-gas analytic solver

Implement constant absorption in slabs and axisymmetric fields. Validate the
radiative-transfer equation before adding spectroscopy.

### IR-2: Piecewise axisymmetric ray tracer

Intersect rays with plume zones or gridded fields and solve ordered segment
transport.

### IR-3: Tabulated molecular cross sections

Use precomputed species cross sections on a \(T,p\) grid.

### IR-4: Line-by-line benchmark path

Use HITEMP/HAPI-derived line data for narrow spectral windows and reference
tests.

### IR-5: Atmospheric propagation and sensor response

Apply path transmittance, path radiance, range dilution, optics, and detector
band response.

### IR-6: Particles and scattering

Add only after the molecular no-scattering solver passes validation.

## 3. Spectral-coordinate contract

Do not mix wavelength and wavenumber arrays implicitly.

```text
SpectralCoordinateKind
  WAVELENGTH_M
  WAVENUMBER_PER_M
```

Every spectral result must carry:

```text
coordinate_kind
coordinate_values
spectral_density_unit
```

If converting spectral density, use the Jacobian. For example:

\[
I_\lambda\,d\lambda
=
I_{\tilde\nu}\,d\tilde\nu,
\qquad
\tilde\nu=\frac1\lambda.
\]

Therefore:

\[
\boxed{
I_{\tilde\nu}
=
I_\lambda
\left|
\frac{d\lambda}{d\tilde\nu}
\right|
=
I_\lambda\lambda^2.
}
\]

The implementation must test integral preservation under conversion.

## 4. Planck spectral radiance

In wavelength coordinates:

\[
\boxed{
B_\lambda(T)
=
\frac{2hc^2}{\lambda^5}
\left[
\exp\left(
\frac{hc}{\lambda k_BT}
\right)-1
\right]^{-1}.
}
\]

Units:

\[
\mathrm{W\,m^{-2}\,sr^{-1}\,m^{-1}}.
\]

Use stable numerical forms:

```text
expm1 for the denominator
large-exponent guard
positive wavelength and temperature validation
```

## 5. Axisymmetric viewing geometry

Let the plume axis be \(x\). Let \(\alpha\) be the angle from the plume axis to
the line of sight.

Line-of-sight unit vector:

\[
\hat{\mathbf d}
=
\begin{bmatrix}
\cos\alpha\\
\sin\alpha\\
0
\end{bmatrix}.
\]

Image-plane basis:

\[
\hat{\mathbf e}_u
=
\begin{bmatrix}
-\sin\alpha\\
\cos\alpha\\
0
\end{bmatrix},
\qquad
\hat{\mathbf e}_v
=
\begin{bmatrix}
0\\
0\\
1
\end{bmatrix}.
\]

A ray through image coordinate \((u,v)\) is:

\[
\boxed{
\mathbf r(s)
=
u\hat{\mathbf e}_u
+
v\hat{\mathbf e}_v
+
s\hat{\mathbf d}.
}
\]

Its axial position is:

\[
\boxed{
x(s)
=
-u\sin\alpha+s\cos\alpha.
}
\]

Its cylindrical radius is:

\[
\boxed{
r(s)
=
\sqrt{
\left(u\cos\alpha+s\sin\alpha\right)^2+v^2
}.
}
\]

This mapping samples any axisymmetric field \(\phi(x,r)\) along the ray.

## 6. Ray-domain construction

For a gridded field:

1. Determine the ray interval intersecting the field bounding box.
2. Find crossings of axial and radial cell boundaries.
3. Sort all crossing parameters \(s\).
4. Form nonoverlapping ordered segments.
5. Sample or volume-average each segment.
6. March from background toward the sensor.

For revolved polygon zones:

1. Represent each 2D \((x,r)\) polygon as an axisymmetric volume.
2. Solve ray-volume intersections.
3. Produce ordered path-length segments.
4. Reject overlapping volume ownership unless a documented priority exists.

Every segment shall contain:

```text
s_start_m
s_end_m
path_length_m
cell_id
temperature_K
pressure_Pa
species_mole_fractions
velocity_xyz_mps
absorption_coefficient_spectrum_per_m
```

## 7. Radiative-transfer equation

For local thermodynamic equilibrium, absorption/emission, and no scattering:

\[
\boxed{
\frac{dI_\lambda}{ds}
=
-\alpha_\lambda I_\lambda
+
\alpha_\lambda B_\lambda(T).
}
\]

Define optical depth:

\[
\boxed{
d\tau_\lambda=\alpha_\lambda ds.
}
\]

For a uniform segment \(i\),

\[
\Delta\tau_{\lambda,i}
=
\alpha_{\lambda,i}\Delta s_i.
\]

The exact segment update is:

\[
\boxed{
I_{\lambda,i+1}
=
I_{\lambda,i}
e^{-\Delta\tau_{\lambda,i}}
+
B_\lambda(T_i)
\left(
1-e^{-\Delta\tau_{\lambda,i}}
\right).
}
\]

Use a stable implementation for small optical depth:

```text
one_minus_transmittance = -expm1(-tau)
```

Then:

```text
I_out = I_in * exp(-tau) + B * one_minus_transmittance
```

## 8. Boundary and background radiance

The initial radiance may represent:

```text
cold space
sky
terrain
vehicle/nozzle surface
user-supplied image background
```

Use:

```text
BackgroundRadianceModel
```

with explicit spectral units.

A plume ray that intersects an opaque vehicle surface terminates at that
surface and uses the surface-emission/reflection boundary condition.

## 9. Gray-gas model

For constant gray absorption \(\alpha_g\),

\[
\alpha_\lambda=\alpha_g.
\]

This model is intentionally unphysical spectrally but is ideal for validating:

- ray lengths;
- segment ordering;
- optical-depth integration;
- angular behavior;
- image integration.

## 10. Molecular absorption

Use wavenumber or wavelength consistently. In a wavenumber implementation:

\[
\boxed{
\alpha_{\tilde\nu}
=
\sum_s
n_s
\sigma_s(\tilde\nu,T,p,\mathbf X).
}
\]

For species mole fraction \(X_s\),

\[
\boxed{
n_s=X_s\frac{p}{k_BT}.
}
\]

Line-by-line form:

\[
\boxed{
\sigma_s(\tilde\nu,T,p)
=
\sum_{\ell\in s}
S_{s\ell}(T)
f_{s\ell}(\tilde\nu;T,p).
}
\]

Where:

- \(S_{s\ell}\) is line intensity;
- \(f_{s\ell}\) is a normalized line profile;
- the first implementation uses a Voigt profile;
- pressure and Doppler broadening are included;
- line mixing and continuum terms are deferred unless a selected band requires
  them.

## 11. Cross-section generation architecture

Do not evaluate every spectroscopic line inside every ray segment.

Use an offline or cached table:

\[
\sigma_s(\tilde\nu,T_i,p_j).
\]

Recommended workflow:

```text
1. Select species and spectral windows.
2. Generate reference cross sections from HITEMP/HAPI.
3. Store versioned tables with source metadata.
4. Interpolate in log-pressure and temperature.
5. Multiply by local species number density during ray tracing.
```

Cross-section artifact metadata:

```text
species
isotopologue_policy
spectral_grid
temperature_grid
pressure_grid
line_database_version
line_shape_model
wing_cutoff
partition_function_source
generation_code_version
```

## 12. Velocity and Doppler shift

For line-of-sight velocity:

\[
\boxed{
v_{\mathrm{LOS}}
=
\mathbf u\cdot\hat{\mathbf d}.
}
\]

At first order:

\[
\frac{\Delta\tilde\nu}{\tilde\nu_0}
\approx
-\frac{v_{\mathrm{LOS}}}{c}.
\]

Doppler shifting can be deferred for broadband sensor results but should remain
in the data contract for high-resolution spectra.

## 13. Image and angular outputs

### Spectral radiance image

\[
\boxed{
I_\lambda(u,v;\alpha)
}
\]

with units:

\[
\mathrm{W\,m^{-2}\,sr^{-1}\,m^{-1}}.
\]

### Spectral radiant intensity

Integrate over projected source area:

\[
\boxed{
J_\lambda(\alpha)
=
\int_{A_\perp}
I_\lambda(u,v;\alpha)\,du\,dv.
}
\]

Units:

\[
\mathrm{W\,sr^{-1}\,m^{-1}}.
\]

### Far-field spectral irradiance

At range \(R\):

\[
\boxed{
E_{\lambda,\mathrm{source}}
=
\frac{J_\lambda}{R^2}.
}
\]

### Atmospheric propagation

\[
\boxed{
E_{\lambda,\mathrm{sensor}}
=
\tau_{\lambda,\mathrm{atm}}(R)
\frac{J_\lambda}{R^2}
+
E_{\lambda,\mathrm{path}}.
}
\]

### Sensor-band signal

For normalized or calibrated detector response \(R_b(\lambda)\),

\[
\boxed{
S_b
=
\int
R_b(\lambda)
E_{\lambda,\mathrm{sensor}}
\,d\lambda.
}
\]

The sensor model must state whether \(S_b\) is radiometric power, photoelectron
rate, digital counts, or a normalized response.

## 14. Aspect-angle physics

Viewing angle enters through:

- ray path lengths;
- hot-core/cool-shear-layer ordering;
- self-absorption;
- vehicle/nozzle occlusion;
- finite field of view;
- non-axisymmetric structure;
- atmospheric path;
- line-of-sight velocity.

Important verification result:

> For a fully visible, optically thin, axisymmetric volume with isotropic
> emission, integrated unresolved emission should be nearly angle independent.

Strong angle dependence in that limit indicates a geometry or integration
error. Projected area and chord length should compensate in the volume
integral.

## 15. IR-domain termination

Shock-cell termination is not radiation termination.

For axial slice \(k\), compute its incremental band radiant intensity:

\[
\Delta J_{b,k}.
\]

Define:

\[
\boxed{
r_{\mathrm{IR},k}
=
\frac{
|\Delta J_{b,k}|
}{
\max\left(
\sum_{i\le k}|\Delta J_{b,i}|,
J_{\mathrm{floor}}
\right)
}.
}
\]

Terminate the radiation domain when:

\[
r_{\mathrm{IR},k}<\epsilon_{\mathrm{IR}}
\]

for a configured number of consecutive slices and for all required view
angles/bands.

Report:

```text
ir_domain_end_x_m
ir_termination_band
ir_termination_angles
incremental_contribution_ratios
```

## 16. Data contracts

### SpectralGrid

```text
coordinate_kind
values
units
spacing_kind
```

### RaySegment

```text
ray_id
segment_index
s_start_m
s_end_m
path_length_m
cell_id
thermodynamic_state
composition
velocity_xyz_mps
```

### RadianceImage

```text
view_angle_rad
u_grid_m
v_grid_m
spectral_grid
radiance
background_model_id
```

### AngularSignature

```text
view_angles_rad
spectral_grid
spectral_radiant_intensity
band_radiant_intensity
```

### SensorSignature

```text
range_m
view_angles_rad
atmospheric_path_id
sensor_response_id
spectral_irradiance
band_signal
```

## 17. Performance plan

- Vectorize spectral calculations over rays or segments where memory permits.
- Cache Planck radiance by unique \(T\) grid.
- Cache cross-section interpolation by quantized \(T,p\).
- Chunk spectral grids to bound memory.
- Use NumPy first.
- Add Numba, JAX, or compiled kernels only after profiling and numerical
  equivalence tests.
- Preserve a slow, transparent reference implementation.

## 18. Verification matrix

### Planck

- Wien peak shifts correctly with temperature.
- Stefan-Boltzmann integral agrees after appropriate angular integration.
- Spectral-coordinate conversion preserves integrated radiance.

### Homogeneous slab

For background \(I_0\), constant \(T,\alpha,L\):

\[
I_{\mathrm{out}}
=
I_0e^{-\alpha L}
+
B(T)(1-e^{-\alpha L}).
\]

The numerical solver must match this exactly within floating-point tolerance.

### Limiting behavior

- \(\alpha L=0\): output equals background.
- \(\alpha L\ll1\): excess radiance is linear in \(\alpha L\).
- \(\alpha L\gg1\): output approaches \(B(T)\).

### Layer ordering

A hot layer behind a cold absorbing layer must differ from the reverse order.

### Ray geometry

- Analytic chord through a cylinder.
- Analytic chord through a sphere test object.
- Tangent ray has zero path length within tolerance.
- Rotational symmetry across image azimuth.

### Angular integral

Optically thin integrated radiant intensity is nearly angle independent for a
fully visible axisymmetric test field.

### Spectroscopy

- Cached cross section reproduces the reference generator at grid nodes.
- Interpolation error is bounded at withheld \(T,p\) points.
- Mixture optical depth equals the sum of species optical depths.

## 19. Validation gate

Validation should progress from:

```text
analytic slab
synthetic axisymmetric field
heated nonreacting plume with measured T and p
measured spectral or band images
rocket-relevant plume
```

Do not use a complex rocket image as the first radiation debugging case.

## 20. Acceptance gate

Phase 4/5 is complete only when:

- analytic slab and ray-geometry cases pass;
- spectral units are unambiguous;
- segment order is correct;
- optically thin angular behavior is correct;
- cross-section tables are versioned and reproducible;
- atmospheric and sensor effects are separable from intrinsic plume radiance;
- IR-domain termination is separate from shock-train termination;
- a slow reference implementation remains available.
