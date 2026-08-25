from __future__ import annotations

from scripts.validate_product_lanes import (
  _run_cross_product_consistency,
  _run_fpa_boundary,
  _run_optical_lane,
  _run_signature_lane,
  _run_visual_lane,
)


def test_visual_lane_local_acceptance_is_separate_from_external_comparison() -> None:
  report = _run_visual_lane()
  assert report['status'] == 'passed'
  assert report['contract_conformance'] is True
  assert report['provider_ids'] == [
    'plume.straight-analytical',
    'plume.shock-cell-analytical',
  ]
  assert {entry['provider_id'] for entry in report['provider_reports']} == set(report['provider_ids'])
  assert report['external_comparison']['status'] == 'pending'


def test_signature_lane_local_interpolation_acceptance_is_explicitly_table_only() -> None:
  report = _run_signature_lane()
  assert report['status'] == 'passed'
  assert report['contract_interpolation_passed'] is True
  assert report['external_comparison']['status'] == 'pending'


def test_optical_lane_passes_analytic_gray_transfer_without_promoting_external_claims() -> None:
  report = _run_optical_lane()

  assert report['status'] == 'passed'
  assert report['provider_id'] == 'plume.gray-ray-transfer'
  assert report['analytic_slab_and_chord_passed'] is True
  assert report['external_comparison']['status'] == 'pending'


def test_fpa_boundary_does_not_advertise_an_unimplemented_provider() -> None:
  report = _run_fpa_boundary()
  assert report['status'] == 'boundary-valid-not-implemented'
  assert report['provider_advertised'] is False
  assert report['ray_provider_prerequisite_present'] is True
  assert report['pixel_detector_contract_passed'] is True
  assert report['source_semantics'] == 'source-only'


def test_ray_to_signature_consistency_is_synthetic_and_lineage_preserving() -> None:
  report = _run_cross_product_consistency()
  assert report['status'] == 'passed'
  assert report['orthographic_area_integration_passed'] is True
  assert report['miss_group_zero_passed'] is True
  assert report['snapshot_lineage_preserved'] is True
  assert report['external_comparison']['status'] == 'synthetic-only'
