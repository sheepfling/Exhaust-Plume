from __future__ import annotations

from pathlib import Path

from scripts import validate_product_lanes
from scripts.validate_product_lanes import (
  _external_summary,
  _run_cross_product_consistency,
  _run_fpa_boundary,
  _run_optical_lane,
  _run_signature_lane,
  _run_visual_lane,
)


def test_external_summary_redacts_machine_local_archive_path(monkeypatch) -> None:
  monkeypatch.setattr(
    validate_product_lanes,
    'preflight_corpus',
    lambda _: {
      'status': 'preflight-valid-pending-release-gates',
      'archive': {'path': '/machine-specific/archive.zip', 'status': 'verified'},
      'content_counts': {},
      'alignment': {'validation_gate_statuses': {}},
      'operator_reconciliation': {'crosswalk_status': 'pending'},
      'release_blockers': [],
    },
  )

  summary = _external_summary(Path('/machine-specific/archive.zip'))

  assert summary['archive'] == {'status': 'verified'}
####


def test_visual_lane_local_acceptance_is_separate_from_external_comparison() -> None:
  report = _run_visual_lane()
  assert report['status'] == 'passed'
  assert report['contract_conformance'] is True
  assert report['provider_ids'] == [
    'plume.straight-analytical',
    'plume.shock-cell-analytical',
  ]
  assert {entry['provider_id'] for entry in report['provider_reports']} == set(report['provider_ids'])
  assert report['local_geometry_invariants'] == 'passed'
  assert all(
    entry['local_geometry_invariants']['status'] == 'passed'
    for entry in report['provider_reports']
  )
  assert report['external_comparison']['status'] == 'pending'
####


def test_signature_lane_local_interpolation_and_lte_source_acceptance_are_separate() -> None:
  report = _run_signature_lane()
  assert report['status'] == 'passed'
  assert report['contract_interpolation_passed'] is True
  assert report['local_contract_invariants']['status'] == 'passed'
  assert report['explicit_lte_line_source']['status'] == 'passed'
  assert report['explicit_lte_line_source']['radiation_claim'] == 'spectral_engineering'
  assert report['explicit_lte_line_source']['optical_profile_mode'] == 'lte-line-by-line-voigt'
  assert report['explicit_lte_line_source']['production_claim_allowed'] == 'false'
  assert report['asset_sha256']
  assert report['measurement_space_operators']['sensor_space_probe']['status'] == 'passed'
  assert report['measurement_space_operators']['measurement_space_guard']['status'] == 'passed'
  assert report['measurement_space_operators']['measurement_space_guard']['cross_space_status'] == 'blocked-measurement-space-mismatch'
  assert report['external_comparison']['status'] == 'pending'
####


def test_optical_lane_passes_analytic_gray_transfer_without_promoting_external_claims() -> None:
  report = _run_optical_lane()

  assert report['status'] == 'passed'
  assert report['provider_id'] == 'plume.gray-ray-transfer'
  assert report['analytic_slab_and_chord_passed'] is True
  assert report['sensor_space_operators']['status'] == 'passed'
  assert report['external_comparison']['status'] == 'pending'
####


def test_fpa_boundary_does_not_advertise_an_unimplemented_provider() -> None:
  report = _run_fpa_boundary()
  assert report['status'] == 'boundary-validated-downstream'
  assert report['provider_advertised'] is False
  assert report['ray_provider_prerequisite_present'] is True
  assert report['pixel_detector_contract_passed'] is True
  assert report['camera_optics_contract_passed'] is True
  assert report['digitization_contract_passed'] is True
  assert report['visualization_projection_contract_passed'] is True
  assert report['visualization_operator_ids'] == (
    'op.sensor.fpa-pixel-detector',
    'op.sensor.fpa-digitization',
  )
  assert report['visualization_selected_pixel']['column_index'] == 1
  assert report['source_semantics'] == 'source-only'
####


def test_ray_to_signature_consistency_is_synthetic_and_lineage_preserving() -> None:
  report = _run_cross_product_consistency()
  assert report['status'] == 'passed'
  assert report['orthographic_area_integration_passed'] is True
  assert report['miss_group_zero_passed'] is True
  assert report['snapshot_lineage_preserved'] is True
  assert report['external_comparison']['status'] == 'synthetic-only'
####
