from __future__ import annotations

from scripts.validate_product_lanes import _run_fpa_boundary, _run_signature_lane, _run_visual_lane


def test_visual_lane_local_acceptance_is_separate_from_external_comparison() -> None:
  report = _run_visual_lane()
  assert report['status'] == 'passed'
  assert report['contract_conformance'] is True
  assert report['external_comparison']['status'] == 'pending'


def test_signature_lane_local_interpolation_acceptance_is_explicitly_table_only() -> None:
  report = _run_signature_lane()
  assert report['status'] == 'passed'
  assert report['contract_interpolation_passed'] is True
  assert report['external_comparison']['status'] == 'pending'


def test_fpa_boundary_does_not_advertise_an_unimplemented_provider() -> None:
  report = _run_fpa_boundary()
  assert report['status'] == 'boundary-valid-not-implemented'
  assert report['provider_advertised'] is False
