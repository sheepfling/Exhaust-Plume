from __future__ import annotations

import pytest

from exhaust_plume import MocVisualDefinition, MocVisualProvider, Pose, VISUAL_SECTIONED_TUBE_V1, VisualSampling, VisualSectionedTubeRequest
from exhaust_plume.contracts.errors import ProviderConfigurationError
from src.models.moc.test_reflected_domain import _patch


def test_moc_visual_provider_exposes_research_envelope() -> None:
  session = MocVisualProvider().create_session(definition=MocVisualDefinition(frame_id='source-local', result=_patch()[0]))
  snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=Pose(frame_id='world', translation_m=(0.0, 0.0, 0.0), rotation_xyzw=(0.0, 0.0, 0.0, 1.0)),
    dynamic_state={},
    ambient_state={},
  )
  result = snapshot.evaluate(
    VISUAL_SECTIONED_TUBE_V1,
    VisualSectionedTubeRequest(
      output_frame_id='source-local',
      sampling=VisualSampling(maximum_section_count=8),
      requested_channels=('mach',),
    ),
  )
  assert result.metadata.provenance.provider_id == 'plume.visual.planar-moc'
  assert result.metadata.claims.geometry.value == 'illustrative'
  assert result.metadata.provenance.metadata['validation_level'] == 'RESEARCH_ONLY'
  assert result.metadata.provenance.metadata['production_claim_allowed'] == 'false'
  assert len(result.sections) <= 8


def test_moc_visual_provider_rejects_non_moc_result() -> None:
  with pytest.raises(ProviderConfigurationError, match='retained planar-MOC'):
    MocVisualDefinition(frame_id='source-local', result=object())
