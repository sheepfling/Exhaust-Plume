from __future__ import annotations

from pathlib import Path

import pytest

from exhaust_plume.api import (
  Applicability,
  FeatureAssociation,
  FeatureChannel,
  ResultStatus,
  SectionedTubePayload,
  SectionedTubeResult,
  build_sectioned_tube_render_mesh,
  extract_sectioned_tube_channel_lines,
  extract_sectioned_tube_geometry,
  extract_sectioned_tube_line_data,
)

ROOT = Path(__file__).resolve().parents[3]


def _fixture_result() -> SectionedTubeResult:
  fixture_path = ROOT / 'tests' / 'fixtures' / 'sectioned_tube_washed_v1.json'
  return SectionedTubeResult.model_validate_json(fixture_path.read_text(encoding='utf-8'))
####


def test_contract_geometry_extracts_aligned_frame_aware_line_data() -> None:
  result = _fixture_result()

  geometry = extract_sectioned_tube_geometry(result)

  assert geometry.frame_id == 'aircraft-body'
  assert geometry.arc_length_m == (0.0, 1.0, 2.0, 3.0)
  assert geometry.centerline_m[2] == (2.0, 0.0, -0.4)
  assert geometry.tangent[1] == pytest.approx((0.995004165, 0.0, -0.099833417))
  assert geometry.normal_2[1] == pytest.approx((0.099833417, 0.0, 0.995004165))
  assert geometry.semi_axis_1_m == (0.2, 0.28, 0.36, 0.44)
  assert geometry.semi_axis_2_m == geometry.semi_axis_1_m
####


def test_contract_channel_lines_preserve_semantics_and_null_values() -> None:
  result = _fixture_result()
  vector_channel = FeatureChannel(
    channel_id='velocity',
    semantic='velocity_vector',
    unit='m/s',
    association=FeatureAssociation.CENTERLINE,
    component_count=2,
    values=(1.0, None, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
  )
  payload = SectionedTubePayload(
    sections=result.payload.sections,
    feature_channels=result.payload.feature_channels + (vector_channel,),
    support_definition=result.payload.support_definition,
  )
  result_with_vector = SectionedTubeResult(envelope=result.envelope, payload=payload)

  lines = extract_sectioned_tube_channel_lines(result_with_vector, channel_id='velocity')

  assert len(lines) == 2
  assert lines[0].channel_id == 'velocity'
  assert lines[0].component_index == 0
  assert lines[0].association is FeatureAssociation.CENTERLINE
  assert lines[0].values == (1.0, 2.0, 4.0, 6.0)
  assert lines[1].component_index == 1
  assert lines[1].values == (None, 3.0, 5.0, 7.0)
  assert all(line.frame_id == result.envelope.frame.frame_id for line in lines)
####


def test_contract_line_data_extracts_all_channels_with_shared_axis() -> None:
  result = _fixture_result()

  line_data = extract_sectioned_tube_line_data(result)

  assert line_data.geometry.frame_id == result.envelope.frame.frame_id
  assert len(line_data.channels) == len(result.payload.feature_channels)
  assert all(channel.arc_length_m == line_data.geometry.arc_length_m for channel in line_data.channels)
  assert {channel.channel_id for channel in line_data.channels} == {
    channel.channel_id for channel in result.payload.feature_channels
  }
####


def test_contract_mesh_uses_explicit_section_normals_and_retains_channels() -> None:
  result = _fixture_result()

  mesh = build_sectioned_tube_render_mesh(result, radial_segments=8)

  assert mesh.frame_id == result.envelope.frame.frame_id
  assert mesh.section_count == len(result.payload.sections)
  assert mesh.radial_segments == 8
  assert len(mesh.vertices) == 4 * 8 + 2
  assert len(mesh.faces) == 2 * 3 * 8 + 2 * 8
  assert mesh.vertices[0] == (0.0, 0.2, 0.0)
  assert mesh.vertices[8 + 2] == pytest.approx((1.027953357, 0.0, 0.178601166))
  assert mesh.feature_channels == result.payload.feature_channels
  assert mesh.minimum_m[0] == 0.0
  assert mesh.maximum_m[0] > 3.0
  assert mesh.model_dump()['capability_id'] == 'plume.visual.sectioned-tube@1'
####


def test_contract_visualization_rejects_failed_or_unsupported_results() -> None:
  result = _fixture_result()
  failed = SectionedTubeResult(
    envelope=result.envelope.model_copy(update={'status': ResultStatus.FAILED}),
    payload=result.payload,
  )
  unsupported = SectionedTubeResult(
    envelope=result.envelope.model_copy(update={
      'applicability': Applicability(
        supported=False,
        violations=('outside visual study domain',),
      ),
    }),
    payload=result.payload,
  )

  with pytest.raises(ValueError, match='FAILED'):
    extract_sectioned_tube_geometry(failed)
  ####
  with pytest.raises(ValueError, match='out-of-applicability'):
    build_sectioned_tube_render_mesh(unsupported)
  ####
  with pytest.raises(KeyError, match='unknown feature channel'):
    extract_sectioned_tube_channel_lines(result, channel_id='not-present')
  ####
####


def test_contract_mesh_rejects_non_integer_or_undersized_ring_resolution() -> None:
  result = _fixture_result()

  with pytest.raises(TypeError, match='integer'):
    build_sectioned_tube_render_mesh(result, radial_segments=True)
  ####
  with pytest.raises(ValueError, match='at least three'):
    build_sectioned_tube_render_mesh(result, radial_segments=2)
  ####
####
