# Rotation-Minimizing Geometry for Curved Plumes

## Status

This note documents the first three-dimensional geometry generated from a calculated curved-plume result. The geometry is a circular tube swept along the plume centerline with one radius per solver station.

The purpose is to support:

- engineering visualization;
- geometric diagnostics;
- later ray/volume intersection for infrared transport;
- a migration path to elliptical, sheet-like, and multi-lobed cross-sections.

It does not change the plume conservation equations.

## 1. Why a revolved mesh is insufficient

The original plume visualization revolves a two-dimensional boundary around one fixed axis. A rotor-wash-deflected plume has a spatially varying tangent and therefore requires a cross-sectional frame at every centerline station.

A Frenet frame is not suitable as the default because its normal depends on curvature and becomes undefined or numerically unstable on straight or nearly straight portions of the plume. The implementation instead uses a rotation-minimizing frame obtained by discrete parallel transport.

## 2. Centerline and cross-sectional state

For station index \(i\), the geometry consumes

\[
\mathbf r_i,\qquad
b_i,\qquad
\mathbf t_i,
\]

where \(\mathbf r_i\) is centerline position, \(b_i>0\) is the equivalent circular radius, and \(\mathbf t_i\) is a unit tangent.

If tangents are not supplied, endpoint one-sided differences and interior centered differences are used before normalization.

Each station carries an orthonormal right-handed frame

\[
\boxed{
\left(\mathbf t_i,\mathbf n_i,\mathbf b_i\right),
\qquad
\mathbf b_i=\mathbf t_i\times\mathbf n_i.
}
\tag{1}
\]

The symbol \(\mathbf b_i\) in Equation (1) is the binormal vector; the scalar plume radius remains \(b_i\).

## 3. Initial normal

A requested initial normal \(\mathbf n_*\) is projected into the first cross-sectional plane:

\[
\widetilde{\mathbf n}_0
=
\mathbf n_*
-
(\mathbf n_*\cdot\mathbf t_0)\mathbf t_0,
\]

\[
\boxed{
\mathbf n_0
=
\frac{\widetilde{\mathbf n}_0}
{\|\widetilde{\mathbf n}_0\|}.
}
\tag{2}
\]

A normal parallel to the first tangent is rejected. When no normal is supplied, the Cartesian basis direction least aligned with \(\mathbf t_0\) is selected and projected.

The initial normal controls only the angular phase of circular rings. It will become physically meaningful when elliptical or otherwise non-axisymmetric sections are introduced.

## 4. Discrete parallel transport

For adjacent unit tangents \(\mathbf t_{i-1}\) and \(\mathbf t_i\), define

\[
\mathbf c_i
=
\mathbf t_{i-1}\times\mathbf t_i,
\]

\[
s_i=\|\mathbf c_i\|,
\qquad
c_i=\mathbf t_{i-1}\cdot\mathbf t_i.
\]

When \(s_i>0\), the minimal-rotation axis is

\[
\widehat{\mathbf a}_i
=
\frac{\mathbf c_i}{s_i}.
\]

The previous normal is transported with Rodrigues' formula:

\[
\boxed{
\mathbf n_i^*
=
 c_i\mathbf n_{i-1}
+s_i\left(\widehat{\mathbf a}_i\times\mathbf n_{i-1}\right)
+(1-c_i)
\left(\widehat{\mathbf a}_i\cdot\mathbf n_{i-1}\right)
\widehat{\mathbf a}_i.
}
\tag{3}
\]

Numerical drift is removed by projecting into the new cross-sectional plane:

\[
\widetilde{\mathbf n}_i
=
\mathbf n_i^*
-
(\mathbf n_i^*\cdot\mathbf t_i)\mathbf t_i,
\]

\[
\boxed{
\mathbf n_i
=
\frac{\widetilde{\mathbf n}_i}
{\|\widetilde{\mathbf n}_i\|},
\qquad
\mathbf b_i
=
\mathbf t_i\times\mathbf n_i.
}
\tag{4}
\]

Parallel adjacent tangents retain the previous normal. Exactly antiparallel adjacent tangents are rejected because the minimal rotation is not unique.

This construction minimizes artificial twist and remains well defined on zero-curvature portions.

## 5. Circular rings

For \(K\ge3\) vertices per ring, define

\[
\theta_j=\frac{2\pi j}{K},
\qquad
j=0,\ldots,K-1.
\]

The ring vertices are

\[
\boxed{
\mathbf x_{i,j}
=
\mathbf r_i
+b_i
\left[
\cos\theta_j\,\mathbf n_i
+
\sin\theta_j\,\mathbf b_i
\right].
}
\tag{5}
\]

Equation (5) guarantees

\[
\|\mathbf x_{i,j}-\mathbf r_i\|=b_i
\]

and

\[
(\mathbf x_{i,j}-\mathbf r_i)\cdot\mathbf t_i=0.
\]

Successive rings are connected by two triangles per circumferential segment. Optional end caps add one center vertex and \(K\) triangles at each end.

For \(N\) rings, the open tube contains

\[
N K
\]

vertices and

\[
2(N-1)K
\]

triangles. A capped tube adds two vertices and \(2K\) triangles.

## 6. Result contract

`SweptTubeMesh` retains immutable arrays for

```text
centerline_m
radii_m
vertices_m
faces
tangents
normals
binormals
```

plus the ring resolution and cap flag. `ring_vertices_m` exposes the structured \((N,K,3)\) view needed by later section-based calculations.

Keeping centerline, radii, and frames alongside the triangle mesh avoids reverse-engineering physical stations from tessellated vertices.

## 7. Implemented verification

The tests establish:

1. exact vertex and triangle counts for open and capped tubes;
2. finite, immutable, valid-index mesh arrays;
3. every vertex lies at the requested radius in the local normal plane;
4. orthonormal frame construction;
5. no frame flip on a planar quarter circle containing straight-limit behavior;
6. full three-dimensional rotation invariance;
7. direct consistency with centerline, radius, and tangent histories returned by the curved-plume solver.

## 8. Validity and failure diagnostics

The tube is an equivalent circular envelope. It does not yet detect or resolve:

- self-intersection between nonadjacent rings;
- folding when station spacing is too large relative to curvature;
- cross-sectional distortion from jet-in-crossflow vortex pairs;
- elliptical or sheet-like suppressor outlets;
- wall clipping or airframe impingement;
- topology changes, plume splitting, or recirculation.

A necessary slenderness indicator is

\[
\boxed{
\kappa b\ll1,
}
\tag{6}
\]

where \(\kappa\) is centerline curvature. When \(\kappa b\) is not small, inner-side rings can crowd or intersect and the single-tube integral representation itself becomes questionable.

Mesh station spacing should also be small relative to both curvature radius and radius-growth length. The solver's sampled station spacing is currently used directly; adaptive geometric resampling is future work.

## 9. Next geometry increments

1. Add adjacent-ring quality metrics and nonadjacent self-intersection checks.
2. Resample centerline geometry independently from ODE output spacing.
3. Add elliptical sections transported by the same frame.
4. Add separate velocity, thermal, and species widths.
5. Add two-lobed or kidney-shaped scalar sections for strong crossflow.
6. Add airframe triangle-mesh intersection and impingement events.
7. Add analytic or accelerated ray intersections for spectral radiance.

The rotation-minimizing frame remains the appropriate orientation backbone for all of these extensions.
