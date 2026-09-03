from __future__ import annotations

import pytest

from exhaust_plume.api.v1 import (
  Pose,
  ProviderConfigurationError,
  ProviderClosedError,
  SPECTRAL_RADIANT_INTENSITY_V1,
  VISUAL_SECTIONED_TUBE_V1,
  VisualSampling,
  VisualSectionedTubeRequest,
)
from exhaust_plume.providers import (
  CurvedIntegralVisualDefinition,
  CurvedIntegralVisualProvider,
)

from src.products.test_model_visualization import _curved_result


def _request(frame_id: str = 'source-local') -> VisualSectionedTubeRequest:
  return VisualSectionedTubeRequest(
    output_frame_id=frame_id,
    sampling=VisualSampling(maximum_section_count=12),
    requested_channels=('temperature', 'pressure', 'curvature'),
  )


def test_curved_integral_provider_returns_standard_visual_product() -> None:
  provider = CurvedIntegralVisualProvider()
  definition = CurvedIntegralVisualDefinition(frame_id='source-local', result=_curved_result())
  session = provider.create_session(definition=definition)
  snapshot = session.create_snapshot(
    time_s=3.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(10.0, 20.0, 30.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={'throttle_fraction': 0.75},
    ambient_state={'altitude_m': 30000.0},
  )

  result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request())

  assert provider.descriptor.provider_id == 'plume.visual.curved-integral'
  assert result.metadata.output_frame_id == 'source-local'
  assert result.metadata.claims.geometry.value == 'engineering_approximate'
  assert result.metadata.claims.radiation.value == 'appearance_only'
  assert result.metadata.claims.time_model.value == 'steady'
  assert result.metadata.provenance.metadata['model_lane'] == 'washed-integral-v1'
  assert len(result.sections) <= 12
  assert result.sections[0].center_m != result.sections[-1].center_m
  assert snapshot.supports(SPECTRAL_RADIANT_INTENSITY_V1.capability) is False

  session.close()
  with pytest.raises(ProviderClosedError):
    session.create_snapshot(
      time_s=4.0,
      source_pose=snapshot.metadata.source_pose,
      dynamic_state={},
      ambient_state={},
    )


def test_curved_integral_provider_rejects_wrong_output_frame() -> None:
  session = CurvedIntegralVisualProvider().create_session(
    definition=CurvedIntegralVisualDefinition(frame_id='source-local', result=_curved_result())
  )
  snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )

  with pytest.raises(ProviderConfigurationError, match='output frame'):
    snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request('wrong-frame'))
