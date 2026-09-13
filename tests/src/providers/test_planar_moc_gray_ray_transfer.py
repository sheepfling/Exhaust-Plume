from __future__ import annotations

from math import exp

import pytest

from exhaust_plume import (
  Pose,
  SPECTRAL_RAY_TRANSFER_V1,
  SampleStatusCode,
  SpectralRayTransferRequest,
)
from exhaust_plume.contracts.errors import ProviderConfigurationError
from exhaust_plume.providers import (
  PlanarMocGrayRayTransferDefinition,
  PlanarMocGrayRayTransferProvider,
)


def _definition() -> PlanarMocGrayRayTransferDefinition:
  return PlanarMocGrayRayTransferDefinition(
    frame_id='sensor',
    polygons_xr_m=(
      ((-1.0, -1.0), (0.0, -1.0), (0.0, 1.0), (-1.0, 1.0)),
      ((0.0, -1.0), (1.0, -1.0), (1.0, 1.0), (0.0, 1.0)),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6),
    source_function_w_sr_m_by_cell=((2.0, 2.0), (4.0, 4.0)),
    absorption_coefficient_per_m_by_cell=((1.0, 1.0), (1.0, 1.0)),
    extrusion_depth_m=0.25,
    field_id='retained-planar-field',
  )


def _snapshot():
  session = PlanarMocGrayRayTransferProvider().create_session(definition=_definition())
  return session.create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )


def test_planar_provider_composes_cell_wise_transfer_in_ray_order() -> None:
  result = _snapshot().evaluate(
    SPECTRAL_RAY_TRANSFER_V1,
    SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((-2.0, 0.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(5.0,),
      wavelengths_m=(1.0e-6, 2.0e-6),
    ),
  )

  transmission = exp(-1.0)
  expected_source = (2.0 + 4.0 * transmission) * (1.0 - transmission)
  assert result.hit_mask == (True,)
  assert result.plume_intersection_t_m == ((1.0, 3.0),)
  assert result.optical_depth == ((2.0, 2.0),)
  assert result.source_spectral_radiance[0] == pytest.approx(
    (expected_source, expected_source),
  )
  assert result.metadata.provenance.provider_id == 'plume.planar-moc-gray-ray-transfer'
  assert result.metadata.provenance.metadata['field_id'] == 'retained-planar-field'
  assert result.metadata.provenance.metadata['extrusion_depth_m'] == '0.25'
  assert result.metadata.claims.geometry.value == 'illustrative'


def test_planar_provider_preserves_miss_and_out_of_plane_validity() -> None:
  result = _snapshot().evaluate(
    SPECTRAL_RAY_TRANSFER_V1,
    SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((-2.0, 2.0, 0.0), (-2.0, 0.0, 1.0)),
      ray_directions=((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
      ray_t_min_m=(0.0, 0.0),
      ray_t_max_m=(5.0, 5.0),
      wavelengths_m=(1.0e-6, 2.0e-6),
    ),
  )

  assert result.hit_mask == (False, False)
  assert result.ray_status[0].code is SampleStatusCode.OK
  assert result.ray_status[1].code is SampleStatusCode.OUTSIDE_APPLICABILITY
  assert result.validity_mask == ((True, True), (False, False))
  assert result.metadata.applicability.status.value == 'marginal'


def test_planar_definition_rejects_nonmatching_cells_and_invalid_geometry() -> None:
  base = _definition()
  with pytest.raises(ProviderConfigurationError, match='polygon count'):
    PlanarMocGrayRayTransferDefinition(
      frame_id=base.frame_id,
      polygons_xr_m=base.polygons_xr_m,
      wavelengths_m=base.wavelengths_m,
      source_function_w_sr_m_by_cell=base.source_function_w_sr_m_by_cell[:1],
      absorption_coefficient_per_m_by_cell=base.absorption_coefficient_per_m_by_cell,
    )
  ####
  with pytest.raises(ProviderConfigurationError, match='invalid'):
    PlanarMocGrayRayTransferDefinition(
      frame_id=base.frame_id,
      polygons_xr_m=(((0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)),),
      wavelengths_m=base.wavelengths_m,
      source_function_w_sr_m_by_cell=((1.0, 1.0),),
      absorption_coefficient_per_m_by_cell=((1.0, 1.0),),
    )
