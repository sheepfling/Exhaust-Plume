"""Source-bound point sampling for retained model-lane cell fields."""

from __future__ import annotations

from math import hypot
from urllib.parse import quote

from exhaust_plume.contracts.common_v1 import (
  ApplicabilityStatus,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  canonical_digest,
)
from exhaust_plume.contracts.errors import (
  InvalidProductRequestError,
  ProductOutsideApplicabilityError,
)
from exhaust_plume.contracts.local_field_v1 import (
  SpatialLocalFieldChannel,
  SpatialLocalFieldRequest,
  SpatialLocalFieldResult,
)
from exhaust_plume.contracts.model_lane_visualization_v1 import (
  ModelLaneField,
  ModelLaneVisualizationResult,
)
from exhaust_plume.contracts.capability import SPATIAL_LOCAL_FIELD_CAPABILITY

__all__ = (
  'evaluate_model_lane_local_field',
  'model_lane_field_channel_id',
  'model_lane_local_field_ids',
)


def model_lane_field_channel_id(field_id: str, channel_id: str) -> str:
  """Return a stable, path-safe ID for one channel within a retained field."""

  if not field_id or not channel_id:
    raise ValueError('field_id and channel_id must not be empty')
  return f'{quote(field_id, safe="")}/{quote(channel_id, safe="")}'


def model_lane_local_field_ids(
  source: ModelLaneVisualizationResult,
) -> tuple[str, ...]:
  """List exact field/channel IDs available in a model-lane result."""

  if not isinstance(source, ModelLaneVisualizationResult):
    raise TypeError('source must be a ModelLaneVisualizationResult')
  return tuple(
    model_lane_field_channel_id(field.field_id, channel_id)
    for field in source.fields
    for channel_id in field.channels
  )


def _inside_polygon(
  point: tuple[float, float],
  polygon: tuple[tuple[float, float], ...],
) -> tuple[bool, bool]:
  """Return (contained, on_boundary) using a scale-aware boundary check."""

  x, r = point
  coordinate_scale = max(
    1.0,
    abs(x),
    abs(r),
    *(abs(value) for vertex in polygon for value in vertex),
  )
  tolerance_m = 1.0e-12 * coordinate_scale
  inside = False
  for index, first in enumerate(polygon):
    second = polygon[(index + 1) % len(polygon)]
    dx = second[0] - first[0]
    dr = second[1] - first[1]
    edge_length = hypot(dx, dr)
    cross = (x - first[0]) * dr - (r - first[1]) * dx
    if (
      abs(cross) <= tolerance_m * max(edge_length, tolerance_m)
      and min(first[0], second[0]) - tolerance_m
      <= x
      <= max(first[0], second[0]) + tolerance_m
      and min(first[1], second[1]) - tolerance_m
      <= r
      <= max(first[1], second[1]) + tolerance_m
    ):
      return True, True
    if (first[1] > r) != (second[1] > r):
      crossing_x = first[0] + (r - first[1]) * dx / dr
      if x < crossing_x:
        inside = not inside
  return inside, False


def _sample_cell(
  field: ModelLaneField,
  channel_id: str,
  point_xr_m: tuple[float, float],
) -> tuple[float | None, float | None, SampleStatus]:
  channel = field.channels[channel_id]
  matches: list[tuple[int, bool]] = []
  for index, polygon in enumerate(field.polygons_xr_m):
    contained, on_boundary = _inside_polygon(point_xr_m, polygon)
    if contained:
      matches.append((index, on_boundary))
  if not matches:
    return None, None, SampleStatus(
      code=SampleStatusCode.OUTSIDE_APPLICABILITY,
      message='point lies outside retained cell-field support',
    )
  if len(matches) > 1:
    return None, None, SampleStatus(
      code=SampleStatusCode.INVALID_SAMPLE,
      message='point lies on an ambiguous shared or overlapping cell boundary',
    )
  cell_index = matches[0][0]
  value = channel.values[cell_index]
  if value is None:
    return None, None, SampleStatus(
      code=SampleStatusCode.INVALID_SAMPLE,
      message='containing cell has no value for this channel',
    )
  uncertainty = (
    None
    if channel.uncertainties is None
    else channel.uncertainties[cell_index]
  )
  return value, uncertainty, SampleStatus(code=SampleStatusCode.OK)


def evaluate_model_lane_local_field(
  source: ModelLaneVisualizationResult,
  request: SpatialLocalFieldRequest,
) -> SpatialLocalFieldResult:
  """Sample exact containing-cell values from one immutable lane result.

  Points are expressed in the source result's output frame as ``(x, r, 0)``
  in its declared axial-radial meridional plane. The adapter returns retained
  cell values; it does not interpolate across cells or extrapolate outside the
  supplied polygons.
  """

  if not isinstance(source, ModelLaneVisualizationResult):
    raise TypeError('source must be a ModelLaneVisualizationResult')
  if not isinstance(request, SpatialLocalFieldRequest):
    raise TypeError('request must be a SpatialLocalFieldRequest')
  if request.coordinate_frame_id != source.metadata.output_frame_id:
    raise InvalidProductRequestError(
      'local-field coordinate frame must match the exact model-lane result frame'
    )
  if source.applicability.status is ApplicabilityStatus.OUTSIDE:
    raise ProductOutsideApplicabilityError(
      'model-lane source result is outside its declared applicability domain'
    )

  channel_sources: dict[str, tuple[ModelLaneField, str]] = {}
  for field in source.fields:
    for channel_id in field.channels:
      channel_sources[model_lane_field_channel_id(field.field_id, channel_id)] = (
        field,
        channel_id,
      )
  missing = tuple(field_id for field_id in request.field_ids if field_id not in channel_sources)
  if missing:
    available = tuple(channel_sources)
    raise InvalidProductRequestError(
      f'unknown model-lane field channel ID(s) {missing!r}; available IDs: {available!r}'
    )

  output_channels: list[SpatialLocalFieldChannel] = []
  invalid_sample_count = 0
  for requested_id in request.field_ids:
    field, channel_id = channel_sources[requested_id]
    model_channel = field.channels[channel_id]
    values: list[float | None] = []
    uncertainties: list[float | None] | None = (
      [] if model_channel.uncertainties is not None else None
    )
    statuses: list[SampleStatus] = []
    for point in request.points_m:
      scale = max(1.0, abs(point[0]), abs(point[1]))
      in_meridional_plane = abs(point[2]) <= 1.0e-12 * scale
      nonnegative_radius = point[1] >= -1.0e-12 * scale
      if not in_meridional_plane or not nonnegative_radius:
        value, uncertainty, status = None, None, SampleStatus(
          code=SampleStatusCode.OUTSIDE_APPLICABILITY,
          message=(
            'point is outside the declared x-r meridional support; '
            'expected coordinates (x, r, 0) with r >= 0'
          ),
        )
      else:
        value, uncertainty, status = _sample_cell(
          field,
          channel_id,
          (point[0], max(0.0, point[1])),
        )
      values.append(value)
      statuses.append(status)
      if uncertainties is not None:
        uncertainties.append(uncertainty)
      if status.code is not SampleStatusCode.OK:
        invalid_sample_count += 1
    output_channels.append(
      SpatialLocalFieldChannel(
        field_id=requested_id,
        semantic=model_channel.semantic,
        unit=model_channel.unit,
        sampling_method='nearest-cell',
        values=tuple(values),
        sample_status=tuple(statuses),
        absolute_standard_uncertainty=(
          None if uncertainties is None else tuple(uncertainties)
        ),
      )
    )

  if invalid_sample_count and not request.allow_partial_results:
    raise ProductOutsideApplicabilityError(
      f'{invalid_sample_count} local-field sample(s) are outside support or ambiguous; '
      'set allow_partial_results=True to preserve per-point statuses'
    )

  request_digest = canonical_digest(request)
  source_digest = canonical_digest(source.model_dump(mode='json'))
  metadata = ResultMetadata(
    capability=SPATIAL_LOCAL_FIELD_CAPABILITY,
    result_id=canonical_digest({
      'source_result_id': source.metadata.result_id,
      'source_result_digest_sha256': source_digest,
      'request_digest_sha256': request_digest,
    })[:24],
    request_digest_sha256=request_digest,
    snapshot=source.metadata.snapshot,
    output_frame_id=source.metadata.output_frame_id,
    claims=source.metadata.claims,
    applicability=source.metadata.applicability,
    provenance=ResultProvenance(
      model_lineage_id=source.metadata.provenance.model_lineage_id,
      provider_id=source.metadata.provenance.provider_id,
      provider_version=source.metadata.provenance.provider_version,
      configuration_digest_sha256=(
        source.metadata.provenance.configuration_digest_sha256
      ),
      asset_digests_sha256=source.metadata.provenance.asset_digests_sha256,
      parent_result_ids=(source.metadata.result_id,),
      metadata={
        **source.metadata.provenance.metadata,
        'local_field_sampling': 'containing-cell-value; no interpolation',
        'local_field_source_digest_sha256': source_digest,
        'local_field_source_lane': source.lane_id.value,
      },
    ),
    warnings=(
      *source.metadata.warnings,
      'local-field values are retained cell values; no interpolation or extrapolation was applied',
      'query points use the source-frame x-r meridional plane as (x, r, 0), with r >= 0',
    ),
  )
  return SpatialLocalFieldResult(
    metadata=metadata,
    coordinate_frame_id=request.coordinate_frame_id,
    points_m=request.points_m,
    field_ids=request.field_ids,
    channels=tuple(output_channels),
  )
