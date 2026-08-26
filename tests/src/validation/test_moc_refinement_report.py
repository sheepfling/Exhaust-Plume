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
  generated_chain_planner = report['geometry_cases']['solver_generated_chain_planner']
  generated_chain_terminal = report['geometry_cases']['solver_generated_chain_terminal_probe']
  field_coupled_chain_planner = report['geometry_cases'][
    'solver_generated_field_coupled_chain_planner'
  ]
  source_strip = report['geometry_cases']['reflected_source_characteristic_strip']
  simple_wave_extension = report['geometry_cases']['reflected_source_strip_constant_k_plus_extension']
  centerline_reflection_extension = report['geometry_cases'][
    'reflected_source_strip_centerline_reflection_extension'
  ]
  reflected_probe = report['geometry_cases']['reflected_zone_shock_coupling']
  reflected_chain_boundary = report['geometry_cases']['reflected_zone_chain_boundary_probe']
  trace_extension = report['geometry_cases']['reflected_boundary_trace_extension']
  planner = report['geometry_cases']['shock_cell_chain_planner_mock']
  invariant_closure = report['geometry_cases']['terminal_source_window_invariant_closure']
  ambient_strip = report['geometry_cases']['solver_generated_ambient_shock_strip']
  ambient_attachment = report['geometry_cases']['ambient_attachment_closure_probe']
  ambient_transition = report['geometry_cases']['ambient_attachment_transition_probe']
  ambient_closure = report['geometry_cases']['ambient_pressure_closure_probe']
  strong_subsonic_boundary = report['geometry_cases']['marched_strong_subsonic_boundary']
  mixed_regime_boundary = report['geometry_cases']['mixed_regime_boundary_contract']

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
  assert generated_chain_planner['planner_kind'] == 'solver-generated-reference'
  assert generated_chain_planner['planning_only'] is True
  assert generated_chain_planner['production_claim_allowed'] is False
  assert generated_chain_planner['planner_step_count'] == 3
  assert [step['next_cell_index'] for step in generated_chain_planner['planner_steps']] == [2, 3, 4]
  assert all(
    step['boundary_kind'] == 'post-shock-field-perimeter'
    and step['incoming_handoff_sample_count'] >= 3
    for step in generated_chain_planner['planner_steps']
  )
  assert generated_chain_terminal['accepted'] is True
  assert generated_chain_terminal['status'] == 'physically-terminated'
  assert generated_chain_terminal['physical_termination'] is True
  assert generated_chain_terminal['cell_count'] == 1
  assert generated_chain_terminal['resolved'] is True
  assert generated_chain_terminal['termination_reason'] == 'physical-termination'
  terminal_planner = generated_chain_terminal['planner']
  assert terminal_planner['planner_kind'] == 'solver-generated-reference'
  assert terminal_planner['planning_only'] is True
  assert terminal_planner['production_claim_allowed'] is False
  assert terminal_planner['planner_step_count'] == 1
  assert terminal_planner['planner_steps'][0]['next_cell_index'] == 2
  assert terminal_planner['planner_steps'][0]['boundary_kind'] == 'post-shock-field-perimeter'
  assert generated_chain_terminal['expected_physical_termination'] is True
  assert generated_chain_terminal['diagnostics']['termination_model'] == 'normal-shock-terminal'
  assert field_coupled_chain_planner['accepted'] is True
  assert field_coupled_chain_planner['planner_kind'] == 'upstream-coupled-research'
  assert field_coupled_chain_planner['planning_only'] is True
  assert field_coupled_chain_planner['production_claim_allowed'] is False
  assert field_coupled_chain_planner['status'] == 'physically-terminated'
  assert field_coupled_chain_planner['termination_reason'] == 'physical-termination'
  assert field_coupled_chain_planner['physical_termination'] is True
  assert field_coupled_chain_planner['cell_count'] == 1
  assert field_coupled_chain_planner['resolved'] is True
  assert field_coupled_chain_planner['planner_step_count'] == 1
  assert field_coupled_chain_planner['planner_steps'][0]['boundary_kind'] == (
    'post-shock-field-perimeter'
  )
  assert field_coupled_chain_planner['planner_steps'][0]['incoming_handoff_sample_count'] >= 3
  assert field_coupled_chain_planner['chain_diagnostics']['termination_model'] == (
    'normal-shock-terminal'
  )
  assert field_coupled_chain_planner['chain_diagnostics']['upstream_field_model'] == (
    'bounded-post-shock-characteristic-field'
  )
  assert reflected_chain_boundary['accepted'] is True
  assert reflected_chain_boundary['physical_termination'] is False
  assert reflected_chain_boundary['status'] == 'solver-terminated'
  assert reflected_chain_boundary['termination_reason'] == 'upstream-field-boundary'
  assert reflected_chain_boundary['cell_count'] == 1
  assert reflected_chain_boundary['state_carry_count'] == 1
  assert reflected_chain_boundary['resolved'] is True
  assert reflected_chain_boundary['diagnostics']['coupling_status'] == (
    'outside_reflected_zone_domain'
  )
  assert reflected_chain_boundary['diagnostics']['coupling_sampled_count'] == 1
  assert reflected_chain_boundary['diagnostics']['first_missing_sample_index'] == 1
  assert strong_subsonic_boundary['status'] == 'subsonic_terminal_required'
  assert strong_subsonic_boundary['subsonic_boundary_verified'] is True
  assert strong_subsonic_boundary['terminal_model_verified'] is False
  assert strong_subsonic_boundary['subsonic_shock_boundary']['branch'] == 'strong'
  assert strong_subsonic_boundary['subsonic_shock_boundary']['subsonic'] is True
  assert strong_subsonic_boundary['normal_shock_terminal'] is None
  assert mixed_regime_boundary['accepted'] is True
  assert mixed_regime_boundary['physical_closure_verified'] is False
  assert mixed_regime_boundary['chain_promotion_blocked'] is True
  assert mixed_regime_boundary['missing_scalar_field']['status'] == 'subsonic_field_failure'
  assert mixed_regime_boundary['missing_scalar_field']['supersonic_patch_verified'] is True
  assert mixed_regime_boundary['scalar_perimeter_contract_fixture']['status'] == (
    'converged_subsonic_boundary_handoff'
  )
  assert mixed_regime_boundary['scalar_perimeter_contract_fixture']['converged'] is True
  assert mixed_regime_boundary['scalar_perimeter_contract_fixture']['physical_closure_verified'] is False
  assert mixed_regime_boundary['scalar_perimeter_contract_fixture']['mixed_regime_field_complete'] is False
  elliptic_field = mixed_regime_boundary['elliptic_subsonic_field_contract_fixture']
  assert elliptic_field['status'] == 'converged_elliptic_subsonic_field'
  assert elliptic_field['physical_closure_verified'] is True
  assert elliptic_field['mixed_regime_field_complete'] is True
  assert elliptic_field['topology_forms_closed_zone'] is True
  assert elliptic_field['topology_nonmanifold_edge_count'] == 0
  assert elliptic_field['maximum_thermodynamic_residual'] <= 1.0e-8
  assert elliptic_field['maximum_harmonic_residual'] <= 1.0e-12
  assert elliptic_field['maximum_velocity_divergence_residual'] <= 1.0e-12
  terminal_attachment = mixed_regime_boundary['terminal_attachment_contract_fixture']
  terminal_attachment_closure = mixed_regime_boundary['terminal_attachment_closure_result']
  assert terminal_attachment_closure['status'] == 'converged_mixed_regime_closure'
  assert terminal_attachment_closure['converged'] is True
  assert terminal_attachment_closure['physical_closure_verified'] is True
  assert terminal_attachment['physical_closure_verified'] is True
  assert terminal_attachment['mixed_regime_field_complete'] is True
  assert terminal_attachment['physical_termination_verified'] is True
  assert terminal_attachment['chain_promotion_blocked'] is True
  terminal_attachment_decision = mixed_regime_boundary['terminal_attachment_termination_decision']
  assert terminal_attachment_decision['physical_termination'] is True
  assert terminal_attachment_decision['reason'] == 'physical-termination'
  assert terminal_attachment_decision['diagnostics']['termination_model'] == (
    'normal-shock-plus-elliptic-subsonic-field'
  )
  assert terminal_attachment_decision['diagnostics']['mixed_regime_model'] == (
    'elliptic-isentropic-subsonic-reference'
  )
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
  terminal_field = ambient_transition['terminal_field']
  assert terminal_field['status'] == 'converged_closed_supersonic_terminal_region'
  assert terminal_field['supersonic_region_closed'] is True
  assert terminal_field['characteristic_field_evidence_verified'] is True
  assert terminal_field['mixed_regime_field_complete'] is False
  assert terminal_field['physical_closure_verified'] is False
  assert terminal_field['chain_promotion_blocked'] is True
  assert terminal_field['node_count'] > 0
  assert terminal_field['topology_forms_closed_zone'] is True
  assert terminal_field['topology_connected'] is True
  assert terminal_field['clipped_patch_cell_count'] > 0
  assert terminal_field['terminal_shock_boundary_sample_count'] == 17
  assert terminal_field['terminal_shock_upstream_sample_count'] == 17
  assert terminal_field['terminal_shock_supersonic_downstream_sample_count'] == 16
  assert terminal_field['terminal_shock_supersonic_downstream_maximum_angle_residual_rad'] <= 1.0e-2
  assert terminal_field['terminal_supersonic_downstream_patch_converged'] is True
  assert terminal_field['terminal_shock_supersonic_downstream_continuation']['status'] == 'converged_open_boundary'
  assert terminal_field['terminal_shock_supersonic_downstream_continuation']['segment_count'] == 16
  assert terminal_field['terminal_shock_supersonic_downstream_first_layer']['converged'] is True
  assert terminal_field['terminal_shock_supersonic_downstream_zone']['status'] == 'converged_open'
  assert terminal_field['terminal_shock_supersonic_downstream_zone']['cell_count'] == 119
  assert terminal_field['terminal_shock_supersonic_downstream_zone']['physical_closure_status'] == 'open'
  perimeter_request = terminal_field['mixed_regime_perimeter_request']
  assert perimeter_request['status'] == 'mixed-regime-perimeter-required'
  assert perimeter_request['perimeter_supplied'] is False
  assert perimeter_request['open_supersonic_zone_is_a_perimeter'] is False
  assert perimeter_request['supersonic_patch_sample_count'] == 16
  assert terminal_field['terminal_shock_boundary_edge_count'] > 0
  assert terminal_field['terminal_shock_boundary_coverage_verified'] is True
  assert terminal_field['terminal_shock_boundary_maximum_geometry_residual_m'] <= 1.0e-8
  assert ambient_transition['reflection_patch']['physical_closure_verified'] is False
  terminal_candidate = ambient_strip['terminal_compression_candidate']
  terminal_patch = ambient_strip['terminal_reflection_patch']
  terminal_patch_shock_probe = ambient_strip['terminal_reflection_patch_shock_probe']
  terminal_patch_chain_probe = ambient_strip['terminal_reflection_patch_chain_probe']
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
  assert terminal_patch_chain_probe['planner_expected_physical_termination'] is True
  assert terminal_patch_chain_probe['planner']['planner_kind'] == 'upstream-coupled-research'
  assert terminal_patch_chain_probe['planner']['planning_only'] is True
  assert terminal_patch_chain_probe['planner']['production_claim_allowed'] is False
  assert terminal_patch_chain_probe['planner']['step_count'] == 1
  first_cell = ambient_strip['first_cell_composite']
  assert first_cell['chain_termination_decision']['physical_termination'] is False
  assert first_cell['chain_termination_decision']['reason'] == 'open-physical-closure'
  assert first_cell['chain_termination_decision']['diagnostics']['termination_model'] == (
    'first-cell-open-physical-closure'
  )
  first_cell_terminal_closure = ambient_strip['first_cell_terminal_closure']
  assert first_cell_terminal_closure['status'] == (
    'converged_first_cell_supersonic_region'
  )
  assert first_cell_terminal_closure['converged'] is True
  assert first_cell_terminal_closure['supersonic_region_closed'] is True
  assert first_cell_terminal_closure['mixed_regime_field_complete'] is False
  assert first_cell_terminal_closure['physical_closure_verified'] is False
  assert first_cell_terminal_closure['chain_promotion_blocked'] is True
  assert first_cell_terminal_closure['physical_termination_verified'] is False
  assert first_cell_terminal_closure['downstream_shock']['physical_terminal_verified'] is True
  assert first_cell_terminal_closure['terminal_field']['status'] == (
    'converged_closed_supersonic_terminal_region'
  )
  assert first_cell_terminal_closure['terminal_field']['terminal_shock_boundary_coverage_verified'] is True
  assert first_cell_terminal_closure['terminal_field']['terminal_shock_boundary_sample_count'] == 18
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
    and case['first_cell_terminal_closure_status'] == (
      'converged_first_cell_supersonic_region'
    )
    and case['first_cell_terminal_closure_converged'] is True
    and case['first_cell_terminal_closure_supersonic_region_closed'] is True
    and case['first_cell_terminal_closure_mixed_regime_field_complete'] is False
    and case['first_cell_terminal_closure_physical_closure_verified'] is False
    and case['first_cell_terminal_closure_chain_promotion_blocked'] is True
    and case['first_cell_terminal_closure_physical_termination_verified'] is False
    and case['first_cell_terminal_closure_terminal_shock_boundary_coverage_verified'] is True
    for case in terminal_patch_refinement['cases']
  )
  axis_end_x = [case['axis_end_m'][0] for case in terminal_patch_refinement['cases']]
  assert abs(axis_end_x[-1] - axis_end_x[-2]) < abs(axis_end_x[-2] - axis_end_x[-3])
  terminal_composite_refinement = report['geometry_cases']['terminal_composite_refinement']
  assert terminal_composite_refinement['status'] == (
    'diagnostic-terminal-composite-resolutions-reach-supersonic-terminal-gate'
  )
  assert [case['sample_count'] for case in terminal_composite_refinement['cases']] == [9, 17, 33]
  assert all(
    case['status'] == 'physically_terminated_at_normal_shock'
    and case['terminal_field_status'] == 'converged_closed_supersonic_terminal_region'
    and case['terminal_field_converged'] is True
    and case['supersonic_region_closed'] is True
    and case['terminal_field_characteristic_field_evidence_verified'] is True
    and case['terminal_field_node_count'] > 0
    and case['topology_forms_closed_zone'] is True
    and case['topology_nonmanifold_edge_count'] == 0
    and case['terminal_shock_boundary_sample_count'] == case['sample_count']
    and case['terminal_shock_upstream_sample_count'] == case['sample_count']
    and case['terminal_shock_supersonic_downstream_sample_count'] == case['sample_count'] - 1
    and case['terminal_shock_supersonic_downstream_maximum_angle_residual_rad'] <= 1.0e-2
    and case['terminal_shock_boundary_coverage_verified'] is True
    and case['terminal_shock_boundary_maximum_geometry_residual_m'] <= 1.0e-8
    and case['physical_terminal_verified'] is True
    for case in terminal_composite_refinement['cases']
  )
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
  caustic_restart = centerline_reflection_extension['caustic_family_restart']
  assert caustic_restart['status'] == 'diagnostic-open-new-family-boundary-restarts'
  assert caustic_restart['accepted'] is True
  assert len(caustic_restart['cases']) == 2
  assert all(case['status'] == 'converged_open_caustic_family_boundary' for case in caustic_restart['cases'])
  assert all(case['physical_closure_verified'] is False for case in caustic_restart['cases'])
  assert all(case['chain_promotion_blocked'] is True for case in caustic_restart['cases'])
  assert all(case['boundary_sample_count'] == 6 for case in caustic_restart['cases'])
  assert all(case['source_strip']['converged'] is False for case in caustic_restart['cases'])
  assert all(case['family_band']['status'] == 'converged_open_caustic_family_band' for case in caustic_restart['cases'])
  assert all(case['family_band']['cell_count'] == 11 for case in caustic_restart['cases'])
  assert all(case['family_band']['step_count'] == 5 for case in caustic_restart['cases'])
  assert all(case['family_band']['topology']['connected'] is True for case in caustic_restart['cases'])
  assert all(case['family_band']['anchor_wedge_verified'] is True for case in caustic_restart['cases'])
  assert all(case['family_band']['physical_closure_verified'] is False for case in caustic_restart['cases'])
  assert all(case['family_band']['chain_promotion_blocked'] is True for case in caustic_restart['cases'])
  assert all(
    case['family_band']['chain_termination_decision']['reason'] == 'open-physical-closure'
    for case in caustic_restart['cases']
  )
  band_shock = centerline_reflection_extension['caustic_family_band_shock']
  assert band_shock['status'] == 'diagnostic-open-band-shock-coupling'
  assert band_shock['accepted'] is True
  assert len(band_shock['cases']) == 2
  assert all(case['shock']['status'] == 'subsonic_terminal_required' for case in band_shock['cases'])
  assert all(case['shock']['sample_count'] == 4 for case in band_shock['cases'])
  assert all(case['shock']['physical_closure_verified'] is False for case in band_shock['cases'])
  band_terminal_field = centerline_reflection_extension[
    'caustic_family_band_terminal_field'
  ]
  assert band_terminal_field['status'] == 'diagnostic-open-band-terminal-field'
  assert band_terminal_field['accepted'] is True
  assert len(band_terminal_field['cases']) == 2
  assert all(
    case['result']['status'] == 'converged_open_caustic_band_terminal_field'
    and case['result']['converged'] is True
    and case['result']['physical_terminal_verified'] is True
    and case['result']['physical_closure_verified'] is False
    and case['result']['chain_promotion_blocked'] is True
    and case['result']['shock']['status'] == 'subsonic_terminal_required'
    and case['result']['shock']['sample_count'] == 8
    and case['result']['shock_fit']['status'] == 'converged_fitted'
    and case['result']['shock_fit']['sample_count'] == 8
    and case['result']['continuation']['status'] == 'converged_open_boundary'
    and case['result']['continuation']['segment_count'] == 8
    and case['result']['first_layer']['status'] == 'converged_first_downstream_layer'
    and case['result']['first_layer']['crossing_count'] == 7
    and case['result']['zone']['status'] == 'converged_open'
    and case['result']['zone']['cell_count'] == 27
    and case['result']['zone']['topology_connected'] is True
    and case['result']['zone']['topology_forms_closed_zone'] is True
    and case['result']['zone']['topology_nonmanifold_edge_count'] == 0
    and case['result']['zone']['physical_closure_status'] == 'open'
    and case['result']['zone']['state_sampling_available'] is True
    and case['result']['zone']['shock_boundary_sample_count'] == 8
    and case['result']['zone']['axis_boundary_sample_count'] == 7
    and case['result']['chain_termination_decision']['physical_termination'] is False
    and case['result']['chain_termination_decision']['reason'] == 'open-physical-closure'
    for case in band_terminal_field['cases']
  )
  band_terminal_refinement = centerline_reflection_extension[
    'caustic_family_band_terminal_refinement'
  ]
  assert band_terminal_refinement['status'] == (
    'diagnostic-caustic-band-terminal-refinement'
  )
  assert band_terminal_refinement['accepted'] is True
  assert all(
    case['accepted'] is True
    and [resolution['sample_count'] for resolution in case['resolutions']] == [5, 7, 9, 11]
    and [resolution['shock_sample_count'] for resolution in case['resolutions']] == [4, 6, 8, 10]
    and [resolution['zone_cell_count'] for resolution in case['resolutions']] == [5, 14, 27, 44]
    and all(
      resolution['physical_terminal_verified'] is True
      and resolution['physical_closure_verified'] is False
      and resolution['chain_promotion_blocked'] is True
      and resolution['zone_physical_closure_status'] == 'open'
      for resolution in case['resolutions']
    )
    for case in band_terminal_refinement['cases']
  )
  band_terminal_measurement = centerline_reflection_extension[
    'caustic_family_band_terminal_measurement'
  ]
  assert band_terminal_measurement['status'] == (
    'diagnostic-independent-measurement-rejects-open-terminal-zone'
  )
  assert band_terminal_measurement['accepted'] is True
  assert all(
    case['expected_open_zone_rejection'] is True
    and case['measurement']['status'] == 'geometry_failure'
    and case['measurement']['message'] == (
      'shock and centerline boundaries must share their endpoint'
    )
    for case in band_terminal_measurement['cases']
  )
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
  assert planner['planner_kind'] == 'prescribed-boundary-mock'
  assert planner['planning_only'] is True
  assert planner['production_claim_allowed'] is False
  assert planner['planner_step_count'] == 3
  assert [step['next_cell_index'] for step in planner['planner_steps']] == [2, 3, 4]
  assert all(
    step['boundary_kind'] == 'post-shock-field-perimeter'
    and step['incoming_handoff_sample_count'] >= 3
    for step in planner['planner_steps']
  )
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
