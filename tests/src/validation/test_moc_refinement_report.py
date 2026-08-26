from __future__ import annotations

import pytest

from scripts.validate_moc_primitives import (
  _observed_refinement_order,
  _refinement_diagnostic,
  build_moc_primitive_report,
)


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


def test_validation_report_retains_solver_generated_shock_and_chain_gates() -> None:
  report = build_moc_primitive_report()

  generated = report['geometry_cases']['solver_generated_attached_shock_field']
  refinement = report['geometry_cases']['solver_generated_shock_refinement']
  generated_chain = report['geometry_cases']['solver_generated_chain_reference']
  reflected_probe = report['geometry_cases']['reflected_zone_shock_coupling']
  trace_extension = report['geometry_cases']['reflected_boundary_trace_extension']
  planner = report['geometry_cases']['shock_cell_chain_planner_mock']

  assert generated['status'] == 'converged_free_boundary_field'
  assert generated['field_status'] == 'converged_closed'
  assert generated['topology_forms_closed_zone'] is True
  assert generated['pressure_loss_verified'] is True
  assert refinement['status'] == 'diagnostic-all-solver-generated-resolutions-converged'
  assert len(refinement['cases']) == 3
  assert generated_chain['accepted'] is True
  assert generated_chain['resolved'] is True
  assert generated_chain['cell_count'] == 3
  assert generated_chain['state_carry_count'] == 3
  assert generated_chain['physical_termination'] is False
  assert reflected_probe['status'] == 'upstream_field_failure'
  assert reflected_probe['claim_status'] == 'reflected-field-domain-bounded-probe; shock-path-extension-pending'
  assert trace_extension['accepted'] is True
  assert trace_extension['field_status'] == 'converged_closed'
  assert trace_extension['shock_closure_status'] == 'reflected-boundary-trace-extension'
  assert planner['resolved'] is True
  assert planner['cell_count'] == 3
  assert planner['state_carry_count'] == 3
  assert report['failures'] == []
  ####
