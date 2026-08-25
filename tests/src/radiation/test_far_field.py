from __future__ import annotations

import pytest

from exhaust_plume import (
  Pose,
  SPECTRAL_RAY_TRANSFER_V1,
  SpectralRayTransferRequest,
)
from exhaust_plume.contracts import SampleStatus, SampleStatusCode
from exhaust_plume.providers import GrayRayTransferDefinition, GrayRayTransferProvider
from exhaust_plume.radiation import FarFieldRayIntegration, far_field_from_rays
from exhaust_plume.geometry import SectionedTubeSupport


def _definition() -> GrayRayTransferDefinition:
  return GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
      radii_m=(1.0, 1.0),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    source_function_w_sr_m=(2.0, 4.0, 8.0),
    absorption_coefficient_per_m=(0.5, 1.0, 2.0),
  )


def _request() -> SpectralRayTransferRequest:
  return SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0),) * 3,
    ray_t_min_m=(0.0, 0.0, 0.0),
    ray_t_max_m=(10.0, 10.0, 10.0),
    wavelengths_m=(1.5e-6, 2.5e-6),
  )


def _ray_result():
  snapshot = GrayRayTransferProvider().create_session(definition=_definition()).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  return snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, _request())


def _integration() -> FarFieldRayIntegration:
  return FarFieldRayIntegration(
    direction_frame_id='sensor',
    source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ray_direction_indices=(0, 0, 1),
    ray_projected_area_weights_m2=(0.25, 0.75, 1.0),
  )


def test_far_field_from_rays_integrates_projected_area_and_preserves_lineage() -> None:
  request = _request()
  ray_result = _ray_result()
  signature = far_field_from_rays(request, ray_result, _integration())

  expected = ray_result.source_spectral_radiance[0]
  assert signature.spectral_radiant_intensity == (expected, (0.0, 0.0))
  assert signature.validity_mask == ((True, True), (True, True))
  assert all(status.code is SampleStatusCode.OK for status in signature.direction_status)
  assert signature.metadata.provenance.parent_result_ids == (ray_result.metadata.result_id,)
  assert signature.metadata.provenance.provider_id == 'plume.adapter.far-field-from-rays'
  assert signature.metadata.claims.derivation.value == 'adapted'
  assert signature.metadata.claims.consistency.value == 'co_generated'
  assert signature.metadata.provenance.metadata['source_term'] == 'source_spectral_radiance only; background excluded'
  assert signature.metadata.provenance.metadata['wavelength_grid_digest_sha256']


def test_far_field_from_rays_is_deterministic_and_keeps_gray_claim_ceiling() -> None:
  request = _request()
  ray_result = _ray_result()
  first = far_field_from_rays(request, ray_result, _integration())
  second = far_field_from_rays(request, ray_result, _integration())

  assert first.model_dump(mode='json') == second.model_dump(mode='json')
  assert first.metadata.claims.radiation.value == 'gray_approximate'
  assert first.metadata.applicability.status.value == 'inside'


def test_far_field_from_rays_rejects_request_or_weight_mismatch() -> None:
  ray_result = _ray_result()
  with pytest.raises(ValueError, match='projected-area weights'):
    FarFieldRayIntegration(
      direction_frame_id='sensor',
      source_to_observer_directions=((1.0, 0.0, 0.0),),
      ray_direction_indices=(0,),
      ray_projected_area_weights_m2=(0.0,),
    )
  ####
  changed_request = _request().model_copy(update={'ray_t_max_m': (9.0, 10.0, 10.0)})
  with pytest.raises(ValueError, match='request digest'):
    far_field_from_rays(changed_request, ray_result, _integration())
  ####
  with pytest.raises(ValueError, match='ray count'):
    far_field_from_rays(
      _request(),
      ray_result,
      FarFieldRayIntegration(
        direction_frame_id='sensor',
        source_to_observer_directions=((1.0, 0.0, 0.0),),
        ray_direction_indices=(0,),
        ray_projected_area_weights_m2=(1.0,),
      ),
    )


def test_far_field_from_rays_can_preserve_an_invalid_partial_direction() -> None:
  request = _request()
  valid = _ray_result()
  partial = valid.__class__(
    metadata=valid.metadata,
    source_spectral_radiance=(
      valid.source_spectral_radiance[0],
      valid.source_spectral_radiance[1],
      (0.0, 0.0),
    ),
    background_transmittance=(
      valid.background_transmittance[0],
      valid.background_transmittance[1],
      (1.0, 1.0),
    ),
    validity_mask=(
      valid.validity_mask[0],
      valid.validity_mask[1],
      (False, False),
    ),
    ray_status=(
      valid.ray_status[0],
      valid.ray_status[1],
      SampleStatus(code=SampleStatusCode.BACKEND_FAILURE, message='synthetic failed ray'),
    ),
    hit_mask=(True, True, False),
    optical_depth=(valid.optical_depth[0], valid.optical_depth[1], (0.0, 0.0)),
    plume_intersection_t_m=(valid.plume_intersection_t_m[0], valid.plume_intersection_t_m[1], None),
  )
  signature = far_field_from_rays(
    request,
    partial,
    _integration(),
    allow_partial_results=True,
  )

  assert signature.validity_mask == ((True, True), (False, False))
  assert signature.spectral_radiant_intensity[1] == (0.0, 0.0)
  assert signature.direction_status[1].code is SampleStatusCode.BACKEND_FAILURE
  assert signature.metadata.applicability.status.value == 'marginal'


def test_far_field_from_rays_requires_the_canonical_result_type() -> None:
  with pytest.raises(TypeError, match='ray_result'):
    far_field_from_rays(_request(), object(), _integration())
