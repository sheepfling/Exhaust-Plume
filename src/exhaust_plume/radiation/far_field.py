"""Bounded orthographic integration from resolved rays to a signature result."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from exhaust_plume.contracts.common_v1 import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  ProductClaims,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  canonical_digest,
)
from exhaust_plume.contracts.ray_transfer_v1 import (
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  SpectralRayTransferRequest,
  SpectralRayTransferResult,
)
from exhaust_plume.contracts.signature_v1 import (
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SpectralSignatureRequest,
  SpectralSignatureResult,
)

__all__ = (
  'FarFieldRayIntegration',
  'far_field_from_rays',
)


@dataclass(frozen=True, slots=True)
class FarFieldRayIntegration:
  """Orthographic ray grouping and projected-area weights.

  Each ray represents a projected image-plane cell.  The area weights are
  therefore already projected areas in square metres; no additional cosine
  factor is applied by :func:`far_field_from_rays`.
  """

  direction_frame_id: str
  source_to_observer_directions: tuple[tuple[float, float, float], ...]
  ray_direction_indices: tuple[int, ...]
  ray_projected_area_weights_m2: tuple[float, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.direction_frame_id, str) or not self.direction_frame_id:
      raise ValueError('direction_frame_id must not be empty')
    ####
    directions = tuple(
      tuple(float(component) for component in direction)
      for direction in self.source_to_observer_directions
    )
    if not directions:
      raise ValueError('source_to_observer_directions must not be empty')
    ####
    for direction in directions:
      if len(direction) != 3 or not all(isfinite(component) for component in direction):
        raise ValueError('source-to-observer directions must be finite 3-vectors')
      ####
      norm = sqrt(sum(component * component for component in direction))
      if abs(norm - 1.0) > 1.0e-6:
        raise ValueError('source-to-observer directions must be unit length')
      ####
    ####
    indices = tuple(self.ray_direction_indices)
    weights = tuple(float(weight) for weight in self.ray_projected_area_weights_m2)
    if len(indices) != len(weights) or not indices:
      raise ValueError('ray direction indices and projected-area weights must have matching non-empty lengths')
    ####
    if any(not isinstance(index, int) or isinstance(index, bool) for index in indices):
      raise ValueError('ray direction indices must be integers')
    ####
    if any(index < 0 or index >= len(directions) for index in indices):
      raise ValueError('ray direction indices must address a supplied direction')
    ####
    if set(indices) != set(range(len(directions))):
      raise ValueError('every supplied direction must have at least one ray')
    ####
    if any(not isfinite(weight) or weight <= 0.0 for weight in weights):
      raise ValueError('ray projected-area weights must be finite and positive')
    ####
    object.__setattr__(self, 'source_to_observer_directions', directions)
    object.__setattr__(self, 'ray_direction_indices', indices)
    object.__setattr__(self, 'ray_projected_area_weights_m2', weights)
  ####
####


def _failure_status(
    statuses: tuple[SampleStatus, ...],
    direction_index: int,
) -> SampleStatus:
  codes = tuple(status.code for status in statuses)
  if codes and all(code is codes[0] for code in codes):
    code = codes[0]
  else:
    code = SampleStatusCode.BACKEND_FAILURE
  ####
  details = '; '.join(
    status.message or status.code.value
    for status in statuses
  )
  return SampleStatus(
    code=code,
    message=f'direction group {direction_index} contains an invalid ray: {details}',
    retryable=any(status.retryable for status in statuses),
  )
####


def far_field_from_rays(
    ray_request: SpectralRayTransferRequest,
    ray_result: SpectralRayTransferResult,
    integration: FarFieldRayIntegration,
    *,
    allow_partial_results: bool = False,
    operating_point_id: str | None = None,
) -> SpectralSignatureResult:
  """Integrate resolved source radiance into directional spectral intensity.

  The operator is the orthographic sum

  ``J_lambda(direction) = sum(L_lambda(ray) * projected_area(ray))``.

  Background transmittance is intentionally excluded because this adapter
  produces intrinsic plume source intensity.  The ray request is required so
  the wavelength-grid identity and parent request digest remain explicit.
  """

  if not isinstance(ray_request, SpectralRayTransferRequest):
    raise TypeError('ray_request must be SpectralRayTransferRequest')
  ####
  if not isinstance(ray_result, SpectralRayTransferResult):
    raise TypeError('ray_result must be SpectralRayTransferResult')
  ####
  if not isinstance(integration, FarFieldRayIntegration):
    raise TypeError('integration must be FarFieldRayIntegration')
  ####
  if not isinstance(allow_partial_results, bool):
    raise TypeError('allow_partial_results must be bool')
  ####
  if integration.direction_frame_id != ray_request.ray_frame_id:
    raise ValueError('signature direction frame must match ray request frame')
  ####
  ray_request_digest = canonical_digest(ray_request)
  if ray_result.metadata.capability != SPECTRAL_RAY_TRANSFER_CAPABILITY:
    raise ValueError('ray_result must identify the canonical spectral ray-transfer capability')
  ####
  if ray_result.metadata.request_digest_sha256 != ray_request_digest:
    raise ValueError('ray request does not match the ray result request digest')
  ####
  if ray_result.metadata.output_frame_id != ray_request.ray_frame_id:
    raise ValueError('ray result output frame must match the ray request frame')
  ####
  ray_count = len(ray_request.ray_origins_m)
  wavelength_count = len(ray_request.wavelengths_m)
  if len(ray_result.source_spectral_radiance) != ray_count:
    raise ValueError('ray result row count must match the ray request')
  ####
  if any(len(row) != wavelength_count for row in ray_result.source_spectral_radiance):
    raise ValueError('ray result wavelength count must match the ray request')
  ####
  if len(integration.ray_direction_indices) != ray_count:
    raise ValueError('integration ray count must match the ray request')
  ####
  signature_request = SpectralSignatureRequest(
    direction_frame_id=integration.direction_frame_id,
    operating_point_id=operating_point_id,
    source_to_observer_directions=integration.source_to_observer_directions,
    wavelengths_m=ray_request.wavelengths_m,
    allow_partial_results=allow_partial_results,
  )
  signature_request_digest = canonical_digest(signature_request)
  direction_count = len(integration.source_to_observer_directions)
  values = [[0.0 for _ in range(wavelength_count)] for _ in range(direction_count)]
  grouped_statuses: list[list[SampleStatus]] = [[] for _ in range(direction_count)]
  grouped_valid = [True] * direction_count
  grouped_ray_count = [0] * direction_count
  for ray_index, direction_index in enumerate(integration.ray_direction_indices):
    grouped_ray_count[direction_index] += 1
    status = ray_result.ray_status[ray_index]
    row_valid = status.code is SampleStatusCode.OK and all(ray_result.validity_mask[ray_index])
    if not row_valid:
      grouped_valid[direction_index] = False
      grouped_statuses[direction_index].append(
        status if status.code is not SampleStatusCode.OK else SampleStatus(
          code=SampleStatusCode.INVALID_SAMPLE,
          message='ray validity mask contains an invalid wavelength',
        )
      )
      continue
    ####
    area = integration.ray_projected_area_weights_m2[ray_index]
    for wavelength_index, radiance in enumerate(ray_result.source_spectral_radiance[ray_index]):
      values[direction_index][wavelength_index] += radiance * area
    ####
  ####
  if any(count == 0 for count in grouped_ray_count):
    raise ValueError('every signature direction must have at least one ray')
  ####
  if any(not valid for valid in grouped_valid) and not allow_partial_results:
    invalid_directions = tuple(index for index, valid in enumerate(grouped_valid) if not valid)
    raise ValueError(
      f'ray groups {invalid_directions} contain invalid or partial ray results; '
      'set allow_partial_results=True to preserve an invalid output row',
    )
  ####
  output_values: list[tuple[float, ...]] = []
  output_masks: list[tuple[bool, ...]] = []
  output_statuses: list[SampleStatus] = []
  for direction_index, valid in enumerate(grouped_valid):
    if valid:
      output_values.append(tuple(values[direction_index]))
      output_masks.append((True,) * wavelength_count)
      output_statuses.append(SampleStatus(code=SampleStatusCode.OK))
      continue
    ####
    output_values.append((0.0,) * wavelength_count)
    output_masks.append((False,) * wavelength_count)
    output_statuses.append(_failure_status(tuple(grouped_statuses[direction_index]), direction_index))
  ####
  parent_applicability = ray_result.metadata.applicability
  applicability_reasons = list(parent_applicability.reasons)
  if any(not valid for valid in grouped_valid):
    applicability_reasons.append('one or more ray direction groups were incomplete')
  ####
  applicability_status = parent_applicability.status
  if any(not valid for valid in grouped_valid) and applicability_status is ApplicabilityStatus.INSIDE:
    applicability_status = ApplicabilityStatus.MARGINAL
  ####
  parent_claims = ray_result.metadata.claims
  parent_provenance = ray_result.metadata.provenance
  integration_digest = canonical_digest(integration)
  metadata = ResultMetadata(
    capability=SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
    result_id=canonical_digest({
      'parent_result_id': ray_result.metadata.result_id,
      'signature_request': signature_request_digest,
      'integration': integration_digest,
    })[:24],
    request_digest_sha256=signature_request_digest,
    snapshot=ray_result.metadata.snapshot,
    output_frame_id=integration.direction_frame_id,
    claims=ProductClaims(
      geometry=parent_claims.geometry,
      radiation=parent_claims.radiation,
      time_model=parent_claims.time_model,
      derivation=Derivation.ADAPTED,
      consistency=ConsistencyLevel.CO_GENERATED,
    ),
    applicability=ApplicabilityReport(
      status=applicability_status,
      reasons=tuple(applicability_reasons),
    ),
    provenance=ResultProvenance(
      model_lineage_id=canonical_digest({
        'adapter': 'far-field-from-rays-v1',
        'parent_model_lineage_id': parent_provenance.model_lineage_id,
      }),
      provider_id='plume.adapter.far-field-from-rays',
      provider_version='1.0.0',
      configuration_digest_sha256=integration_digest,
      asset_digests_sha256=parent_provenance.asset_digests_sha256,
      parent_result_ids=(ray_result.metadata.result_id,),
      metadata={
        'integration_operator': 'orthographic_projected_area_sum',
        'ray_request_digest_sha256': ray_request_digest,
        'wavelength_grid_digest_sha256': canonical_digest(ray_request.wavelengths_m),
        'ray_count': str(ray_count),
        'direction_count': str(direction_count),
        'area_weight_units': 'm^2 projected image-plane cell area',
        'source_term': 'source_spectral_radiance only; background excluded',
      },
    ),
    warnings=ray_result.metadata.warnings + (
      ('one or more ray direction groups were returned as invalid partial results',)
      if any(not valid for valid in grouped_valid) else ()
    ),
  )
  return SpectralSignatureResult(
    metadata=metadata,
    spectral_radiant_intensity=tuple(output_values),
    validity_mask=tuple(output_masks),
    direction_status=tuple(output_statuses),
    absolute_standard_uncertainty=None,
  )
####
