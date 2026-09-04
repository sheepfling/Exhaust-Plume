from __future__ import annotations

from exhaust_plume import Pose, SPECTRAL_RADIANT_INTENSITY_V1
from exhaust_plume.contracts import SpectralSignatureRequest
from exhaust_plume.providers import SignatureTableProvider
from exhaust_plume.validation.lane_contracts import (
  validate_signature_table_result,
  validate_straight_visual_result,
)

from scripts.validate_product_lanes import (
  _analytical_state,
  _signature_definition,
  _visual_request,
)
from exhaust_plume import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.providers import StraightAnalyticalDefinition, StraightAnalyticalProvider


_POSE = Pose(
  frame_id='world',
  translation_m=(0.0, 0.0, 0.0),
  rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
)


def test_visual_lane_invariants_reject_transverse_geometry() -> None:
  request = _visual_request('source-local')
  snapshot = StraightAnalyticalProvider().create_session(
    definition=StraightAnalyticalDefinition(nozzle_radius_m=1.0),
  ).create_snapshot(
    time_s=0.0,
    source_pose=_POSE,
    dynamic_state={'operating_state': _analytical_state(1.2)},
    ambient_state={},
  )
  result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, request)
  displaced = result.sections[1].model_copy(update={'center_m': (result.sections[1].center_m[0], 0.1, 0.0)})
  invalid_result = result.model_copy(update={'sections': (result.sections[0], displaced, *result.sections[2:])})

  report = validate_straight_visual_result(
    invalid_result,
    request,
    expected_output_frame_id='source-local',
  )

  assert report.status == 'failed'
  assert report.straight_axis_centerline is False
  assert 'straight_axis_centerline' in report.reasons
####


def test_signature_lane_invariants_require_the_declared_asset_digest() -> None:
  definition = _signature_definition()
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((0.0, 1.0, 0.0),),
    wavelengths_m=(1.0e-6, 2.0e-6),
  )
  snapshot = SignatureTableProvider().create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=_POSE,
    dynamic_state={},
    ambient_state={},
  )
  result = snapshot.evaluate(SPECTRAL_RADIANT_INTENSITY_V1, request)

  report = validate_signature_table_result(
    result,
    request,
    expected_asset_id=definition.asset_id,
    expected_asset_sha256='0' * 64,
  )

  assert report.status == 'failed'
  assert report.asset_provenance_present is True
  assert report.asset_identity_matches is False
  assert 'asset_identity_matches' in report.reasons
####
