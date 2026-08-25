from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_lane_releases import build_lane_release_manifest


def test_lane_release_manifest_separates_local_release_from_external_acceptance() -> None:
  report = build_lane_release_manifest()
  lanes = {lane['lane_id']: lane for lane in report['lanes']}

  assert report['checks']['low_fidelity_promotion_detected'] is False
  assert report['checks']['fpa_provider_guard_passed'] is True
  assert report['umbrella_release']['release_ready'] is False

  assert lanes['shock-cell-basic-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['shock-cell-basic-v1']['external_validation_status'] == 'pending'
  assert lanes['shock-cell-basic-v1']['claim_ceiling']
  assert lanes['signature-table-mvp-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['signature-table-mvp-v1']['external_validation_status'] == 'pending'
  assert lanes['optical-transfer-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['focal-plane-array-v1']['local_release_status'] == 'scoped-downstream-boundary'
  assert lanes['focal-plane-array-v1']['provider_ids'] == []

  assert lanes['planar-moc-primitives-v1']['local_release_ready'] is False
  assert lanes['shock-cell-reduced-order-v1']['local_release_ready'] is False
  assert lanes['washed-integral-v1']['local_release_status'] == 'planned'


def test_lane_manifest_uses_validated_code_tranche_when_head_is_docs_only() -> None:
  freeze = json.loads(
    Path('docs/validation/release_freeze_v1.json').read_text(encoding='utf-8'),
  )
  assert freeze['head_commit'] != freeze['validated_code_commit']
  assert build_lane_release_manifest()['source_commit'] == freeze['validated_code_commit']
