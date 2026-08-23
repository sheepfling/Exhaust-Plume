from __future__ import annotations

import pytest

from exhaust_plume.contracts import (
  Pose,
  ProductOutsideApplicabilityError,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSampling,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  run_visual_provider_conformance,
)
from exhaust_plume.contracts.errors import ProviderClosedError
from exhaust_plume.contracts.specs_v1 import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.providers import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
)


def _definition() -> PrescribedVisualDefinition:
  sections = tuple(
    VisualSection(
      arc_length_m=float(index),
      center_m=(float(index), 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=0.5 + 0.1 * index,
      radius_minor_m=0.25 + 0.05 * index,
    )
    for index in range(4)
  )
  return PrescribedVisualDefinition(
    frame_id='source-local',
    sections=sections,
    channels={'mixing_weight': (0.0, 0.25, 0.75, 1.0)},
  )


def test_prescribed_provider_uses_one_immutable_snapshot_for_visual_evaluation() -> None:
  provider = PrescribedVisualProvider(PrescribedVisualConfiguration())
  session = provider.create_session(definition=_definition())
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
  assert snapshot.supports(VISUAL_SECTIONED_TUBE_CAPABILITY)
  result = snapshot.evaluate(
    VISUAL_SECTIONED_TUBE_V1,
    VisualSectionedTubeRequest(
      output_frame_id='source-local',
      sampling=VisualSampling(maximum_section_count=2),
      requested_channels=('mixing_weight',),
    ),
  )
  assert isinstance(result, VisualSectionedTubeResult)
  assert len(result.sections) == 2
  assert result.channels['mixing_weight'] == (0.0, 1.0)
  assert result.metadata.snapshot.snapshot_id == snapshot.metadata.snapshot_id
  assert result.metadata.capability == VISUAL_SECTIONED_TUBE_CAPABILITY


def test_prescribed_provider_rejects_unsupported_frame_and_channel() -> None:
  session = PrescribedVisualProvider().create_session(definition=_definition())
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
  with pytest.raises(ProductOutsideApplicabilityError):
    snapshot.evaluate(
      VISUAL_SECTIONED_TUBE_V1,
      VisualSectionedTubeRequest(
        output_frame_id='world',
        sampling=VisualSampling(maximum_section_count=2),
      ),
    )
  with pytest.raises(ValueError, match='unsupported visual channels'):
    snapshot.evaluate(
      VISUAL_SECTIONED_TUBE_V1,
      VisualSectionedTubeRequest(
        output_frame_id='source-local',
        sampling=VisualSampling(maximum_section_count=2),
        requested_channels=('unknown_channel',),
      ),
    )


def test_prescribed_provider_closes_session() -> None:
  session = PrescribedVisualProvider().create_session(definition=_definition())
  session.close()
  with pytest.raises(ProviderClosedError):
    session.create_snapshot(
      time_s=0.0,
      source_pose=Pose(
        frame_id='world',
        translation_m=(0.0, 0.0, 0.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
      dynamic_state={},
      ambient_state={},
    )


def test_prescribed_provider_passes_the_shared_visual_conformance_harness() -> None:
  provider = PrescribedVisualProvider()

  def snapshot_factory():
    session = provider.create_session(definition=_definition())
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

  report = run_visual_provider_conformance(
    provider.descriptor,
    snapshot_factory,
    VisualSectionedTubeRequest(
      output_frame_id='source-local',
      sampling=VisualSampling(maximum_section_count=3),
      requested_channels=('mixing_weight',),
    ),
  )
  assert report.passed is True
  assert report.section_count == 3
