from __future__ import annotations

import json
from pathlib import Path

import scripts.validate_lane_releases as lane_release_validator
from scripts.validate_lane_releases import build_lane_release_manifest


def test_lane_release_manifest_separates_local_release_from_external_acceptance() -> None:
  report = build_lane_release_manifest()
  lanes = {lane['lane_id']: lane for lane in report['lanes']}

  assert report['checks']['low_fidelity_promotion_detected'] is False
  assert report['checks']['fpa_provider_guard_passed'] is True
  assert report['checks']['mission_time_composition_passed'] is True
  assert report['umbrella_release']['release_ready'] is False
  assert report['mission_time_composition']['lane_id'] == 'mission-time-product-composition-v1'
  assert report['mission_time_composition']['mission_times_s'] == [0.0, 5.0, 10.0]

  assert lanes['shock-cell-basic-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['shock-cell-basic-v1']['external_validation_status'] == 'pending'
  assert lanes['shock-cell-basic-v1']['claim_ceiling']
  assert lanes['signature-table-mvp-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['signature-table-mvp-v1']['external_validation_status'] == 'pending'
  assert lanes['optical-transfer-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['curved-optical-transfer-v1']['product_report_status'] == 'diagnostic-only'
  assert lanes['curved-optical-transfer-v1']['local_release_status'] == 'not-released-validation-pending'
  assert lanes['curved-optical-transfer-v1']['external_validation_status'] == 'pending'
  assert lanes['focal-plane-array-v1']['local_release_status'] == 'scoped-downstream-boundary'
  assert lanes['focal-plane-array-v1']['provider_ids'] == []

  assert lanes['planar-moc-primitives-v1']['local_release_ready'] is False
  assert lanes['shock-cell-reduced-order-v1']['local_release_ready'] is False
  assert lanes['washed-integral-v1']['local_release_status'] == 'scoped-local-release'
  assert lanes['washed-integral-v1']['product_evidence_source'] == (
    'committed-product-report.lanes.visual.standardized_model_lanes'
  )
####


def test_lane_manifest_binds_the_validated_code_or_audited_follow_on() -> None:
  freeze = json.loads(
    Path('docs/validation/release_freeze_v1.json').read_text(encoding='utf-8'),
  )
  assert freeze['head_commit'] == freeze['validated_code_commit']
  report = build_lane_release_manifest()
  assert report['source_commit'] == freeze['validated_code_commit']
  provenance = report['release_provenance']
  assert provenance['recorded_freeze_head_commit'] == freeze['head_commit']
  assert provenance['validated_code_commit'] == freeze['validated_code_commit']
  assert report['checks']['release_freeze_matches_candidate_head'] is (
    provenance['candidate_head_commit'] == freeze['head_commit']
  )
  assert report['checks']['documentation_only_follow_on_verified'] is (
    provenance['documentation_only_follow_on_verified'] is True
  )
  assert provenance['candidate_head_matches_validated_code_commit'] is (
    provenance['candidate_head_commit'] == freeze['validated_code_commit']
  )
  assert report['checks']['candidate_worktree_clean'] is (
    provenance['candidate_worktree_clean'] is True
  )


def test_lane_manifest_accepts_allowlisted_documentation_follow_on(
  monkeypatch,
) -> None:
  freeze = json.loads(
    Path('docs/validation/release_freeze_v1.json').read_text(encoding='utf-8'),
  )
  candidate_head = 'documentation-follow-on'
  monkeypatch.setattr(
    lane_release_validator,
    '_git_head_commit',
    lambda: candidate_head,
  )
  monkeypatch.setattr(
    lane_release_validator,
    '_git_worktree_clean',
    lambda: True,
  )
  monkeypatch.setattr(
    lane_release_validator,
    '_git_changed_paths',
    lambda base_commit, candidate_commit: {
      'docs/product_suite_completion_plan_v1.md',
      'docs/validation/lane_release_manifest_v1.json',
      'docs/validation/release_freeze_v1.json',
    },
  )

  report = build_lane_release_manifest()
  provenance = report['release_provenance']
  assert candidate_head != freeze['head_commit']
  assert provenance['documentation_only_follow_on_verified'] is True
  assert report['checks']['release_freeze_matches_candidate_head'] is False
  assert report['checks']['release_provenance_ready'] is True
  assert not any(
    'release freeze does not identify the current candidate HEAD' in blocker
    for blocker in report['umbrella_release']['blockers']
  )
####
