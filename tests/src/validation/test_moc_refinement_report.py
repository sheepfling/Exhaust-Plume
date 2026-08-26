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
  source_strip = report['geometry_cases']['reflected_source_characteristic_strip']
  simple_wave_extension = report['geometry_cases']['reflected_source_strip_constant_k_plus_extension']
  centerline_reflection_extension = report['geometry_cases'][
    'reflected_source_strip_centerline_reflection_extension'
  ]
  reflected_probe = report['geometry_cases']['reflected_zone_shock_coupling']
  trace_extension = report['geometry_cases']['reflected_boundary_trace_extension']
  planner = report['geometry_cases']['shock_cell_chain_planner_mock']
  invariant_closure = report['geometry_cases']['terminal_source_window_invariant_closure']
  ambient_strip = report['geometry_cases']['solver_generated_ambient_shock_strip']
  ambient_attachment = report['geometry_cases']['ambient_attachment_closure_probe']
  ambient_transition = report['geometry_cases']['ambient_attachment_transition_probe']
  ambient_closure = report['geometry_cases']['ambient_pressure_closure_probe']

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
  assert ambient_closure['status'] == 'ambient_boundary_failure'
  assert ambient_closure['physical_closure_verified'] is False
  assert ambient_closure['upstream_coupling_verified'] is False
  assert ambient_strip['accepted'] is True
  assert ambient_strip['status'] == 'converged_open_shock_ambient_strip'
  assert ambient_strip['strip']['node_count'] == 153
  assert ambient_strip['strip']['cell_count'] == 152
  assert ambient_strip['strip']['topology_forms_closed_zone'] is True
  assert ambient_strip['strip']['physical_closure_verified'] is False
  assert ambient_strip['strip']['chain_promotion_blocked'] is True
  assert ambient_attachment['status'] == 'converged_ambient_attachment_open_strip'
  assert ambient_attachment['expected_open_strip'] is True
  assert ambient_attachment['converged'] is True
  assert ambient_attachment['physical_closure_verified'] is False
  assert ambient_attachment['chain_promotion_blocked'] is True
  assert ambient_attachment['outer_downstream_flow_angle_rad'] == pytest.approx(0.05)
  assert ambient_attachment['attachment_pressure_residual'] == pytest.approx(0.0)
  assert ambient_attachment['shooting_iterations'] == 1
  assert ambient_attachment['strip']['status'] == 'converged_open_shock_ambient_strip'
  assert ambient_attachment['strip']['physical_closure_verified'] is False
  assert ambient_attachment['strip']['chain_promotion_blocked'] is True
  assert ambient_attachment['downstream_condition_status'] == 'linear-centerline-reference'
  assert ambient_transition['status'] == 'physically_terminated_at_normal_shock'
  assert ambient_transition['expected_physical_termination'] is True
  assert ambient_transition['converged'] is True
  assert ambient_transition['physical_termination'] is True
  assert ambient_transition['physical_closure_verified'] is False
  assert ambient_transition['chain_promotion_blocked'] is True
  assert ambient_transition['next_shock_handoff_kind'] == 'terminal-characteristic-trace'
  assert ambient_transition['next_shock_handoff_sample_count'] >= 3
  assert ambient_transition['termination_decision_available'] is True
  assert ambient_transition['physical_termination_decision']['reason'] == 'physical-termination'
  assert ambient_transition['downstream_shock']['physical_terminal_verified'] is True
  assert ambient_transition['reflection_patch']['physical_closure_verified'] is False
  terminal_candidate = ambient_strip['terminal_compression_candidate']
  terminal_patch = ambient_strip['terminal_reflection_patch']
  terminal_patch_shock_probe = ambient_strip['terminal_reflection_patch_shock_probe']
  assert ambient_strip['terminal_trace_acceptance_tolerance_m'] == pytest.approx(2.0e-4)
  assert terminal_candidate['status'] == 'converged_local_compression_candidate'
  assert terminal_candidate['converged'] is True
  assert terminal_candidate['physical_closure_verified'] is False
  assert terminal_candidate['chain_promotion_blocked'] is True
  assert terminal_candidate['accepted_for_chain'] is False
  assert terminal_patch['status'] == 'converged_open_terminal_reflection_patch'
  assert terminal_patch['converged'] is True
  assert terminal_patch['outgoing_trace_family'] == 'C-'
  assert terminal_patch['outgoing_trace_validation']['converged'] is True
  assert terminal_patch['combined_topology_forms_closed_zone'] is True
  assert terminal_patch['combined_topology_nonmanifold_edge_count'] == 0
  assert terminal_patch['physical_closure_verified'] is False
  assert terminal_patch_shock_probe['status'] == 'subsonic_terminal_required'
  assert terminal_patch_shock_probe['converged'] is False
  assert terminal_patch_shock_probe['upstream_coupling_verified'] is False
  assert terminal_patch_shock_probe['physical_closure_verified'] is False
  assert terminal_patch_shock_probe['chain_promotion_blocked'] is True
  assert terminal_patch_shock_probe['physical_terminal_verified'] is True
  assert terminal_patch_shock_probe['termination_decision_available'] is True
  assert terminal_patch_shock_probe['physical_termination_decision']['physical_termination'] is True
  assert terminal_patch_shock_probe['physical_termination_decision']['reason'] == 'physical-termination'
  assert terminal_patch_shock_probe['physical_termination_decision']['diagnostics']['termination_model'] == 'normal-shock-terminal'
  assert terminal_patch_shock_probe['coupling']['converged'] is True
  assert terminal_patch_shock_probe['shock']['normal_shock_terminal']['subsonic'] is True
  terminal_patch_refinement = report['geometry_cases']['terminal_reflection_patch_refinement']
  assert terminal_patch_refinement['status'] == (
    'diagnostic-terminal-patch-resolutions-reach-mixed-regime-gate'
  )
  assert [case['sample_count'] for case in terminal_patch_refinement['cases']] == [9, 17, 33]
  assert all(
    case['status'] == 'converged_open_terminal_reflection_patch'
    and case['shock_probe_status'] == 'subsonic_terminal_required'
    and case['shock_probe_coupling_sampled_count'] == case['shock_probe_sample_count']
    and case['physical_closure_verified'] is False
    for case in terminal_patch_refinement['cases']
  )
  axis_end_x = [case['axis_end_m'][0] for case in terminal_patch_refinement['cases']]
  assert abs(axis_end_x[-1] - axis_end_x[-2]) < abs(axis_end_x[-2] - axis_end_x[-3])
  assert source_strip['status'] == 'converged_open_source_strip'
  assert source_strip['node_count'] == 45
  assert source_strip['cell_count'] == 44
  assert source_strip['topology_forms_closed_zone'] is True
  assert source_strip['nonmanifold_edge_count'] == 0
  assert simple_wave_extension['status'] == 'converged_constant_k_plus_extension'
  assert simple_wave_extension['added_sample_count'] == 12
  assert simple_wave_extension['strip']['node_count'] == 231
  assert simple_wave_extension['strip']['cell_count'] == 230
  assert simple_wave_extension['shock_probe']['status'] == 'upstream_field_failure'
  assert simple_wave_extension['shock_probe']['sample_count'] > 1
  assert simple_wave_extension['shock_probe']['claim_status'] == 'constant-k-plus-simple-wave-extension; shock-closure-pending'
  assert centerline_reflection_extension['continuation_law'] == (
    'centerline-c-minus-reflection-plus-ambient-pressure'
  )
  assert centerline_reflection_extension['added_sample_count'] == 1
  assert centerline_reflection_extension['source_window_count'] == 10
  assert centerline_reflection_extension['frontier']['status'] == (
    'converged_source_frontier_probe'
  )
  assert centerline_reflection_extension['frontier']['valid_index_ranges'] == [[0, 2], [8, 9]]
  assert centerline_reflection_extension['frontier']['first_invalid_index'] == 3
  assert centerline_reflection_extension['frontier']['has_disjoint_ranges'] is True
  assert centerline_reflection_extension['remesh']['status'] == (
    'caustic_requires_new_characteristic_family'
  )
  assert centerline_reflection_extension['remesh']['failed_boundary_index'] == 0
  assert centerline_reflection_extension['remesh']['patch_cell_count'] == 2
  assert centerline_reflection_extension['remesh']['failed_boundary_indices'] == [0, 1]
  assert centerline_reflection_extension['remesh']['connected_with_base'] is False
  assert centerline_reflection_extension['remesh']['topology']['status'] == 'disconnected'
  assert centerline_reflection_extension['remesh']['caustic_event']['status'] == (
    'caustic_detected'
  )
  assert centerline_reflection_extension['remesh']['caustic_event']['boundary_interval'] == 0
  assert centerline_reflection_extension['remesh']['caustic_event']['requires_new_characteristic_family'] is True
  assert centerline_reflection_extension['remesh']['caustic_event']['caustic_point_m'][0] > 0.0
  caustic_seed = centerline_reflection_extension['caustic_shock_seed']
  assert caustic_seed['status'] == 'converged_one_sided_caustic_seed'
  assert caustic_seed['converged'] is True
  assert caustic_seed['shock_state_solved'] is False
  assert caustic_seed['physical_closure_verified'] is False
  assert caustic_seed['chain_promotion_blocked'] is True
  assert [edge['family'] for edge in caustic_seed['edge_states']] == ['C-', 'C-']
  caustic_shock_resolution = centerline_reflection_extension['caustic_shock_resolution']
  assert caustic_shock_resolution['status'] == (
    'no_entropy_admissible_caustic_shock_candidate'
  )
  assert caustic_shock_resolution['converged'] is False
  assert caustic_shock_resolution['shock_state_solved'] is False
  assert caustic_shock_resolution['physical_closure_verified'] is False
  assert caustic_shock_resolution['chain_promotion_blocked'] is True
  assert [candidate['status'] for candidate in caustic_shock_resolution['candidates']] == [
    'caustic_shock_state_mismatch',
    'no_positive_compression_turn',
  ]
  assert caustic_shock_resolution['candidates'][0]['compression']['converged'] is True
  assert centerline_reflection_extension['remesh']['chain_termination_available'] is True
  assert centerline_reflection_extension['remesh']['chain_termination_decision']['physical_termination'] is False
  assert centerline_reflection_extension['remesh']['chain_termination_decision']['reason'] == (
    'characteristic-caustic'
  )
  assert centerline_reflection_extension['claim_status'] == (
    'centerline-C-minus-reflection-boundary-law; '
    'triangular-domain-remesh-or-shock-closure-pending'
  )
  assert reflected_probe['status'] == 'upstream_field_failure'
  assert reflected_probe['claim_status'] == (
    'reflected-field-domain-bounded-shock-solver; downstream-boundary-and-'
    'shock-path-extension-pending'
  )
  assert reflected_probe['coupling']['status'] == 'outside_reflected_zone_domain'
  assert reflected_probe['coupling']['sampled_count'] == 1
  assert reflected_probe['coupling']['first_missing_sample_index'] == 1
  assert reflected_probe['reflected_zone_solver_expected_bounded_failure'] is True
  assert reflected_probe['reflected_zone_solver']['upstream_coupling_verified'] is False
  assert trace_extension['accepted'] is True
  assert trace_extension['field_status'] == 'converged_closed'
  assert trace_extension['shock_closure_status'] == 'reflected-boundary-trace-extension'
  assert planner['resolved'] is True
  assert planner['cell_count'] == 3
  assert planner['state_carry_count'] == 3
  assert planner['continuation_boundary_kinds'] == ['post-shock-field-perimeter']
  assert len(planner['terminal_trace_validation']) == 3
  assert all(
    entry['boundary_kind'] == 'post-shock-field-perimeter'
    and entry['trace']['status'] == 'not_applicable'
    and entry['geometry']['status'] == 'converged'
    for entry in planner['terminal_trace_validation']
  )
  assert invariant_closure['status'] == 'shooting_failure'
  assert invariant_closure['source_extension']['status'] == 'converged_terminal_source_window'
  assert invariant_closure['source_extension']['strip']['source_window_kind'] == 'terminal-source-window'
  assert invariant_closure['source_extension']['full_strip']['status'] == 'geometry_failure'
  assert invariant_closure['claim_status'].startswith('domain-bounded-invariant-shooting-attempt')
  assert report['failures'] == []
  ####
