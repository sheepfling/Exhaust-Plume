from __future__ import annotations

from pathlib import Path

import pytest

from exhaust_plume.api import (
  AxisScale,
  CameraSpec,
  InvalidSamplePolicy,
  SectionedTubeResult,
  ViewSelection,
  VisualizationSpec,
  WavelengthDisplayUnit,
)

ROOT = Path(__file__).resolve().parents[3]


def _result() -> SectionedTubeResult:
  fixture_path = ROOT / 'tests' / 'fixtures' / 'sectioned_tube_washed_v1.json'
  return SectionedTubeResult.model_validate_json(fixture_path.read_text(encoding='utf-8'))
####


def test_visualization_spec_binds_to_result_and_round_trips_deterministically() -> None:
  result = _result()
  spec = VisualizationSpec.for_result(
    result,
    view_kind='visual.station-inspector',
    selection=ViewSelection(
      station_index=2,
      channel_id='temperature',
      component_index=0,
    ),
    x_scale=AxisScale.LOG10,
    invalid_sample_policy=InvalidSamplePolicy.TRANSPARENT,
    wavelength_display_unit=WavelengthDisplayUnit.UM,
    camera=CameraSpec(
      azimuth_deg=35.0,
      elevation_deg=20.0,
      distance_m=5.0,
      target_m=(1.0, 0.0, -0.2),
    ),
  )

  restored = VisualizationSpec.model_validate_json(spec.canonical_json())

  assert restored == spec
  assert spec.digest_sha256() == restored.digest_sha256()
  spec.validate_for_result(result)
  assert spec.selection.station_index == 2
  assert spec.camera is not None
  assert spec.camera.target_m == (1.0, 0.0, -0.2)
####


def test_visualization_spec_rejects_rebinding_to_a_different_result() -> None:
  result = _result()
  spec = VisualizationSpec.for_result(result, view_kind='visual.overview')
  different_result = result.model_copy(update={
    'envelope': result.envelope.model_copy(update={'content_sha256': '3' * 64}),
  })

  with pytest.raises(ValueError, match='different product result'):
    spec.validate_for_result(different_result)
####


def test_visualization_spec_validates_selection_and_view_names() -> None:
  with pytest.raises(ValueError, match='greater than or equal to 0'):
    ViewSelection(station_index=-1)
  with pytest.raises(ValueError, match='String should match pattern'):
    VisualizationSpec(
      capability_id='plume.visual.sectioned-tube@1',
      schema_version='1.0.0',
      provider_id='provider',
      snapshot_id='snapshot',
      content_sha256='1' * 64,
      frame_id='world',
      view_kind='Not A View',
    )
####
