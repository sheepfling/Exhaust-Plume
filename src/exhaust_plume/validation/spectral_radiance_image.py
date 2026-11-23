"""Bind exact ray-transfer samples to a pre-detector spectral image grid."""

from __future__ import annotations

from collections import defaultdict
from math import fsum

from exhaust_plume.contracts.capability import IMAGE_SPECTRAL_RADIANCE_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  Derivation,
  SampleStatus,
  SampleStatusCode,
  canonical_digest,
)
from exhaust_plume.contracts.ray_transfer_v1 import (
  SpectralRayTransferRequest,
  SpectralRayTransferResult,
)
from exhaust_plume.contracts.spectral_radiance_image_v1 import (
  SpectralRadianceImageRequest,
  SpectralRadianceImageResult,
)
from exhaust_plume.validation.fpa_operators import FpaPixelGeometry


SPECTRAL_RADIANCE_IMAGE_ADAPTER_ID = 'adapter.spectral-radiance-image-from-ray-transfer@1'


def _validate_ray_inputs(
    ray_request: SpectralRayTransferRequest,
    ray_result: SpectralRayTransferResult,
    geometry: FpaPixelGeometry,
) -> str:
  if not isinstance(ray_request, SpectralRayTransferRequest):
    raise TypeError('ray_request must be SpectralRayTransferRequest')
  ####
  if not isinstance(ray_result, SpectralRayTransferResult):
    raise TypeError('ray_result must be SpectralRayTransferResult')
  ####
  if not isinstance(geometry, FpaPixelGeometry):
    raise TypeError('geometry must be FpaPixelGeometry')
  ####
  if ray_result.metadata.request_digest_sha256 != canonical_digest(ray_request):
    raise ValueError('ray-transfer result request digest does not match the exact request')
  ####
  if ray_result.metadata.output_frame_id != ray_request.ray_frame_id:
    raise ValueError('ray-transfer result frame does not match the exact request')
  ####
  ray_count = len(ray_request.ray_origins_m)
  wavelength_count = len(ray_request.wavelengths_m)
  if len(geometry.ray_pixel_indices_row_col) != ray_count:
    raise ValueError('pixel geometry must map exactly one pixel for every requested ray')
  ####
  if (
      len(ray_result.source_spectral_radiance) != ray_count
      or any(len(row) != wavelength_count for row in ray_result.source_spectral_radiance)
  ):
    raise ValueError('ray-transfer result shape does not match the exact request axes')
  ####
  return canonical_digest(ray_result)
####


def make_spectral_radiance_image_request(
    ray_request: SpectralRayTransferRequest,
    ray_result: SpectralRayTransferResult,
    *,
    geometry: FpaPixelGeometry,
    pixel_frame_id: str,
) -> SpectralRadianceImageRequest:
  """Create the immutable projection request from exact ray and pixel inputs."""

  ray_result_digest = _validate_ray_inputs(ray_request, ray_result, geometry)
  return SpectralRadianceImageRequest(
    pixel_frame_id=pixel_frame_id,
    ray_frame_id=ray_request.ray_frame_id,
    ray_transfer_request_digest_sha256=canonical_digest(ray_request),
    ray_transfer_result_id=ray_result.metadata.result_id,
    ray_transfer_result_digest_sha256=ray_result_digest,
    pixel_geometry_sha256=canonical_digest(geometry),
    width_px=geometry.width_px,
    height_px=geometry.height_px,
    ray_pixel_indices_row_col=geometry.ray_pixel_indices_row_col,
    ray_collection_weights_m2_sr=geometry.ray_collection_weights_m2_sr,
  )
####


def to_spectral_radiance_image(
    request: SpectralRadianceImageRequest,
    ray_request: SpectralRayTransferRequest,
    ray_result: SpectralRayTransferResult,
    *,
    geometry: FpaPixelGeometry,
) -> SpectralRadianceImageResult:
  """Project source radiance and transmittance onto the exact pixel grid.

  Each pixel is the normalized collection-weighted mean of its mapped rays.
  If any mapped ray is invalid, the whole pixel fails closed with neutral
  placeholders. This result contains no detector response or electron values.
  """

  if not isinstance(request, SpectralRadianceImageRequest):
    raise TypeError('request must be SpectralRadianceImageRequest')
  ####
  expected_request = make_spectral_radiance_image_request(
    ray_request,
    ray_result,
    geometry=geometry,
    pixel_frame_id=request.pixel_frame_id,
  )
  if request != expected_request:
    raise ValueError('spectral-radiance-image request does not bind the exact ray and pixel inputs')
  ####
  wavelength_count = len(ray_request.wavelengths_m)
  pixel_rays: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
  for ray_index, (pixel, weight) in enumerate(zip(
      request.ray_pixel_indices_row_col,
      request.ray_collection_weights_m2_sr,
      strict=True,
  )):
    pixel_rays[pixel].append((ray_index, weight))
  ####
  source_image: list[list[tuple[float, ...]]] = []
  transmittance_image: list[list[tuple[float, ...]]] = []
  validity_rows: list[list[bool]] = []
  status_rows: list[list[SampleStatus]] = []
  count_rows: list[list[int]] = []
  weight_rows: list[list[float]] = []
  for row_index in range(request.height_px):
    source_row: list[tuple[float, ...]] = []
    transmittance_row: list[tuple[float, ...]] = []
    validity_row: list[bool] = []
    status_row: list[SampleStatus] = []
    count_row: list[int] = []
    weight_row: list[float] = []
    for column_index in range(request.width_px):
      mapped = pixel_rays.get((row_index, column_index), [])
      ray_indices = [ray_index for ray_index, _ in mapped]
      weights = [weight for _, weight in mapped]
      total_weight = fsum(weights)
      failure_index = next((
        ray_index
        for ray_index in ray_indices
        if ray_result.ray_status[ray_index].code is not SampleStatusCode.OK
        or not all(ray_result.validity_mask[ray_index])
      ), None)
      if not mapped:
        valid = False
        status = SampleStatus(
          code=SampleStatusCode.INVALID_SAMPLE,
          message='no ray samples map to this pixel',
        )
      elif failure_index is not None:
        valid = False
        ray_status = ray_result.ray_status[failure_index]
        status = SampleStatus(
          code=(
            ray_status.code
            if ray_status.code is not SampleStatusCode.OK
            else SampleStatusCode.INVALID_SAMPLE
          ),
          message=f'ray {failure_index} is invalid: {ray_status.message or ray_status.code.value}',
          retryable=ray_status.retryable,
        )
      else:
        valid = True
        status = SampleStatus(code=SampleStatusCode.OK)
      ####
      if valid:
        source_pixel = tuple(
          fsum(
            weight * ray_result.source_spectral_radiance[ray_index][wavelength_index]
            for ray_index, weight in mapped
          ) / total_weight
          for wavelength_index in range(wavelength_count)
        )
        transmittance_pixel = tuple(
          fsum(
            weight * ray_result.background_transmittance[ray_index][wavelength_index]
            for ray_index, weight in mapped
          ) / total_weight
          for wavelength_index in range(wavelength_count)
        )
      else:
        source_pixel = (0.0,) * wavelength_count
        transmittance_pixel = (1.0,) * wavelength_count
      ####
      source_row.append(source_pixel)
      transmittance_row.append(transmittance_pixel)
      validity_row.append(valid)
      status_row.append(status)
      count_row.append(len(mapped))
      weight_row.append(total_weight)
    ####
    source_image.append(source_row)
    transmittance_image.append(transmittance_row)
    validity_rows.append(validity_row)
    status_rows.append(status_row)
    count_rows.append(count_row)
    weight_rows.append(weight_row)
  ####
  source_metadata = ray_result.metadata
  parent_ids = tuple(dict.fromkeys((
    *source_metadata.provenance.parent_result_ids,
    source_metadata.result_id,
  )))
  provenance_metadata = dict(source_metadata.provenance.metadata)
  provenance_metadata.update({
    'adapter_id': SPECTRAL_RADIANCE_IMAGE_ADAPTER_ID,
    'pixel_geometry_sha256': request.pixel_geometry_sha256,
    'ray_transfer_request_digest_sha256': request.ray_transfer_request_digest_sha256,
    'ray_transfer_result_digest_sha256': request.ray_transfer_result_digest_sha256,
    'spectral_radiance_image_request_digest_sha256': canonical_digest(request),
  })
  provenance = source_metadata.provenance.model_copy(update={
    'parent_result_ids': parent_ids,
    'metadata': provenance_metadata,
  })
  metadata = source_metadata.model_copy(update={
    'capability': IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
    'result_id': f'{source_metadata.result_id}:image:{canonical_digest(request)[:20]}',
    'request_digest_sha256': canonical_digest(request),
    'output_frame_id': request.pixel_frame_id,
    'claims': source_metadata.claims.model_copy(update={'derivation': Derivation.ADAPTED}),
    'provenance': provenance,
  })
  return SpectralRadianceImageResult(
    metadata=metadata,
    pixel_frame_id=request.pixel_frame_id,
    ray_frame_id=request.ray_frame_id,
    ray_transfer_request_digest_sha256=request.ray_transfer_request_digest_sha256,
    ray_transfer_result_id=request.ray_transfer_result_id,
    ray_transfer_result_digest_sha256=request.ray_transfer_result_digest_sha256,
    pixel_geometry_sha256=request.pixel_geometry_sha256,
    width_px=request.width_px,
    height_px=request.height_px,
    wavelengths_m=ray_request.wavelengths_m,
    source_spectral_radiance_W_m2_sr_m=tuple(tuple(row) for row in source_image),
    background_transmittance=tuple(tuple(row) for row in transmittance_image),
    validity_mask=tuple(tuple(row) for row in validity_rows),
    pixel_status=tuple(tuple(row) for row in status_rows),
    ray_sample_count=tuple(tuple(row) for row in count_rows),
    pixel_collection_weight_m2_sr=tuple(tuple(row) for row in weight_rows),
  )
####


__all__ = (
  'SPECTRAL_RADIANCE_IMAGE_ADAPTER_ID',
  'make_spectral_radiance_image_request',
  'to_spectral_radiance_image',
)
