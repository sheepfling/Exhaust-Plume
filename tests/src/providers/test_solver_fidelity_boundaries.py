from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exhaust_plume.providers import (
  GrayRayTransferProvider,
  ShockCellVisualProvider,
  SignatureTableProvider,
  StraightAnalyticalProvider,
)

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'solver_fidelity_matrix_v1.json'


def _matrix() -> dict[str, Any]:
  return json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
####


def _active_descriptors() -> dict[str, Any]:
  providers = (
    GrayRayTransferProvider(),
    ShockCellVisualProvider(),
    StraightAnalyticalProvider(),
    SignatureTableProvider(),
  )
  return {provider.descriptor.provider_id: provider.descriptor for provider in providers}
####


def test_fidelity_matrix_has_separate_active_and_downstream_lanes() -> None:
  matrix = _matrix()
  assert matrix['matrix_id'] == 'solver-fidelity-matrix-v1'
  lanes = {lane['lane_id']: lane for lane in matrix['lanes']}
  assert lanes['planar-moc-primitives-v1']['status'] == 'primitive-validated-provider-pending'
  assert lanes['planar-moc-primitives-v1']['provider_ids'] == []
  assert lanes['shock-cell-basic-v1']['status'] == 'active'
  assert lanes['shock-cell-reduced-order-v1']['status'] == 'experimental'
  assert lanes['shock-cell-reduced-order-v1']['provider_ids'] == ['plume.shock-train-reduced-order']
  assert lanes['shock-cell-reduced-order-v1']['focal_plane_array'] == 'not_supported'
  assert lanes['signature-table-mvp-v1']['status'] == 'active'
  assert lanes['washed-integral-v1']['status'] == 'planned'
  assert lanes['optical-transfer-v1']['status'] == 'active'
  assert lanes['focal-plane-array-v1']['status'] == 'validated-downstream'
  assert lanes['shock-cell-basic-v1']['focal_plane_array'] == 'not_supported'
####


def test_active_provider_capabilities_match_their_fidelity_lane() -> None:
  lanes = {
    lane['lane_id']: lane
    for lane in _matrix()['lanes']
    if lane['status'] == 'active'
  }
  descriptors = _active_descriptors()
  for lane in lanes.values():
    advertised = set(lane['advertised_capabilities'])
    forbidden = set(lane['forbidden_capabilities'])
    assert advertised.isdisjoint(forbidden)
    for provider_id in lane['provider_ids']:
      descriptor = descriptors[provider_id]
      actual = {capability.wire_id for capability in descriptor.supported_capabilities}
      assert actual == advertised
      assert actual.isdisjoint(forbidden)
      assert f"fidelity profile: {lane['lane_id']}" in descriptor.notes
####


def test_basic_lane_explicitly_blocks_signature_ray_and_detector_promotion() -> None:
  basic = next(
    lane for lane in _matrix()['lanes']
    if lane['lane_id'] == 'shock-cell-basic-v1'
  )
  forbidden = set(basic['forbidden_capabilities'])
  assert 'plume.signature.spectral-radiant-intensity@1' in forbidden
  assert 'plume.optical.spectral-ray-transfer@1' in forbidden
  assert 'plume.image.spectral-radiance@1' in forbidden
  assert basic['complexity_policy'].startswith('frozen-ceiling')
####


def test_fpa_lane_requires_ray_transfer_and_detector_contracts() -> None:
  fpa = next(
    lane for lane in _matrix()['lanes']
    if lane['lane_id'] == 'focal-plane-array-v1'
  )
  assert fpa['provider_ids'] == []
  assert 'plume.optical.spectral-ray-transfer@1' in fpa['requires']
  assert 'detector-response-contract' in fpa['requires']
  assert fpa['focal_plane_array'] == 'downstream-adapter'
####
