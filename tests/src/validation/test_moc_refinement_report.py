from __future__ import annotations

import pytest

from scripts.validate_moc_primitives import _observed_refinement_order, _refinement_diagnostic


def test_open_lattice_refinement_order_is_only_a_numerical_diagnostic() -> None:
  probe = [
    {
      'coverage_area_m2': 1.0,
      'maximum_radius_m': 3.0,
      'open_extent_x_m': 5.0,
      'candidate_shock_endpoint_x_m': 7.0,
    },
    {
      'coverage_area_m2': 1.25,
      'maximum_radius_m': 2.5,
      'open_extent_x_m': 4.5,
      'candidate_shock_endpoint_x_m': 6.5,
    },
    {
      'coverage_area_m2': 1.3125,
      'maximum_radius_m': 2.375,
      'open_extent_x_m': 4.375,
      'candidate_shock_endpoint_x_m': 6.375,
    },
  ]

  report = _refinement_diagnostic(probe)

  assert report['status'] == 'diagnostic-monotone-finite-open-lattice'
  assert report['interpretation'] == 'open-lattice-only; physical first-cell closure remains pending'
  assert report['metrics']['coverage_area_m2']['monotone'] is True
  assert report['metrics']['maximum_radius_m']['monotone'] is True
  assert report['metrics']['open_extent_x_m']['monotone'] is True
  assert report['metrics']['candidate_shock_endpoint_x_m']['monotone'] is True
  assert report['metrics']['coverage_area_m2']['observed_order'] == pytest.approx(2.0)
  assert report['metrics']['maximum_radius_m']['observed_order'] == pytest.approx(2.0)
  assert report['metrics']['open_extent_x_m']['observed_order'] == pytest.approx(2.0)
  assert report['metrics']['candidate_shock_endpoint_x_m']['observed_order'] == pytest.approx(2.0)
  ####


def test_observed_refinement_order_does_not_infer_from_flat_sequence() -> None:
  assert _observed_refinement_order(1.0, 1.0, 1.0) is None
  assert _observed_refinement_order(1.0, float('inf'), 1.25) is None
  ####
