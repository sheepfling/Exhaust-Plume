# Signature angular timeline v1

`exhaust_plume.products.signature_timeline` adapts a compatible collection of
public `SpectralSignatureRequest` / `SpectralSignatureResult` pairs into
renderer-neutral angular and time-series views. The request is retained because
the public result intentionally does not duplicate its direction or wavelength
axes.

The adapter accepts only strictly increasing, exact snapshot times with one
unchanged direction frame, direction-vector sequence, and wavelength axis.
It does not resample changing grids or interpolate between snapshots. A caller
that needs either operation must supply an explicit product-level operator and
record it in result lineage.

Angular maps use the declared source-to-observer unit vectors directly. For a
portable display plane they map `atan2(y, x)` to azimuth about +z and
`atan2(z, hypot(x, y))` to elevation from the xy plane, in the request's
declared direction frame. That convention is visual only; it does not create a
new physical axis or assert that a provider is axisymmetric.

`SignatureAngularBinning` is an explicit equirectangular display aggregation.
It reports the exact source direction indices in each cell. When multiple valid
directions occupy a cell, the displayed value is their arithmetic mean; this is
not angular interpolation. Empty cells and cells containing only invalid
samples remain `None`, never zero. `SignatureDirectionSeries` similarly keeps
invalid time samples masked.

The resulting maps carry spectral radiant intensity `Jλ [W sr⁻¹ m⁻¹]`. They do
not report spectral radiance, detector counts, apparent intensity, or an FPA
image. `SignatureTimeline.source_trajectory()` exposes only declared source
poses in a shared pose frame; it applies no coordinate transforms or inferred
observer trajectories.

For a moving launch vehicle, retain the result/request pair at each mission
sample and build this timeline after the prescribed mission evaluator has
resolved the state-specific flow and optical closures. The view itself does not
advance a mission, solve dynamics, infer atmosphere or chemistry, or upgrade
the source model's radiation and validation claims.
