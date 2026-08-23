from __future__ import annotations

import pytest

from exhaust_plume.contracts import (
  GeometryClaim,
  Pose,
  RadiationClaim,
  VisualSampling,
  VisualSectionedTubeRequest,
)
from exhaust_plume.contracts.errors import ProviderConfigurationError
from exhaust_plume.contracts.specs_v1 import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.providers import StraightVisualDefinition, StraightVisualProvider


def _snapshot():
  definition = StraightVisualDefinition(
    frame_id='source-local',
    length_m=4.0,
    initial_radius_major_m=0.5,
    initial_radius_minor_m=0.25,
    divergence_angle_rad=0.05,
    base_section_count=9,
  )
  return StraightVisualProvider().create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
####


def test_straight_visual_provider_emits_deterministic_straight_sections() -> None:
  request = VisualSectionedTubeRequest(
    output_frame_id='source-local',
    sampling=VisualSampling(maximum_section_count=3),
    requested_channels=('core_radius_fraction', 'opacity_weight'),
  )
  first = _snapshot().evaluate(VISUAL_SECTIONED_TUBE_V1, request)
  second = _snapshot().evaluate(VISUAL_SECTIONED_TUBE_V1, request)
  assert first.model_dump() == second.model_dump()
  assert [section.center_m for section in first.sections] == [
    (0.0, 0.0, 0.0),
    (2.0, 0.0, 0.0),
    (4.0, 0.0, 0.0),
  ]
  assert first.metadata.claims.geometry is GeometryClaim.ILLUSTRATIVE
  assert first.metadata.claims.radiation is RadiationClaim.APPEARANCE_ONLY
  assert first.metadata.provenance.provider_id == 'visual.straight-parametric'
  assert first.channels['core_radius_fraction'][0] > 0.0
  assert first.channels['opacity_weight'] == (1.0, 1.0, 1.0)
####


def test_straight_visual_definition_rejects_nonphysical_terminal_radius() -> None:
  with pytest.raises(ProviderConfigurationError, match='non-positive'):
    StraightVisualDefinition(
      frame_id='source-local',
      length_m=4.0,
      initial_radius_major_m=0.1,
      initial_radius_minor_m=0.1,
      divergence_angle_rad=-0.7,
    )
  ####
####
