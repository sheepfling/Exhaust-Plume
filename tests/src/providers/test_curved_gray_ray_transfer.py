from __future__ import annotations

import pytest

from exhaust_plume import Pose, SPECTRAL_RAY_TRANSFER_V1, SpectralRayTransferRequest
from exhaust_plume.contracts.errors import ProviderConfigurationError
from exhaust_plume.geometry import SectionedTubeSupport
from exhaust_plume.providers import CurvedGrayRayTransferProvider, GrayRayTransferDefinition


def _definition(*, allow: bool = True) -> GrayRayTransferDefinition:
  return GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
      radii_m=(0.3, 0.3, 0.3),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6),
    source_function_w_sr_m=(2.0, 4.0),
    absorption_coefficient_per_m=(1.0, 2.0),
    allow_curved_support=allow,
  )
####


def test_curved_provider_transfers_through_curved_support() -> None:
  session = CurvedGrayRayTransferProvider().create_session(definition=_definition())
  snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=Pose(frame_id='world', translation_m=(0.0, 0.0, 0.0), rotation_xyzw=(0.0, 0.0, 0.0, 1.0)),
    dynamic_state={},
    ambient_state={},
  )
  result = snapshot.evaluate(
    SPECTRAL_RAY_TRANSFER_V1,
    SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((-1.0, 0.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(5.0,),
      wavelengths_m=(1.0e-6, 2.0e-6),
    ),
  )
  assert result.hit_mask == (True,)
  assert result.metadata.provenance.provider_id == 'plume.curved-gray-ray-transfer'
  assert result.metadata.provenance.metadata['support_geometry'].startswith('curved')
  assert result.metadata.claims.radiation.value == 'gray_approximate'
####


def test_curved_provider_requires_explicit_definition_opt_in() -> None:
  with pytest.raises(ProviderConfigurationError, match='allow curved'):
    CurvedGrayRayTransferProvider().create_session(definition=_definition(allow=False))
  ####
####
