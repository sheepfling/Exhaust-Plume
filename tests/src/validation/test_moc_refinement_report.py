from __future__ import annotations

from typing import Any

import pytest

from scripts.validate_moc_primitives import (
  _observed_refinement_order,
  _refinement_diagnostic,
  build_moc_primitive_report,
)


def _assert_chain_planner_measurement(
  measurement: dict[str, Any],
  *,
  physical_termination: bool,
) -> None:
  assert measurement['status'] == 'converged'
  assert measurement['operator_id'] == 'op.moc.chain-planner'
  assert all(
    value for value in measurement['checks'].values() if value is not None
  )
  assert measurement['physical_termination'] is physical_termination
  assert measurement['production_claim_allowed'] is False


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
  generated_chain_refinement = report['geometry_cases'][
    'solver_generated_chain_refinement'
  ]
  generated_chain_external_validation = report['geometry_cases'][
    'solver_generated_chain_external_validation'
  ]
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
  caustic_upstream_bridge = centerline_reflection_extension['caustic_upstream_bridge']
  caustic_upstream_continuation = centerline_reflection_extension[
    'caustic_upstream_continuation'
  ]
  caustic_remesh = centerline_reflection_extension['caustic_shock_remesh_execution']
  simple_wave_terminal = caustic_remesh['simple_wave_terminal']
  simple_wave_terminal_planner = caustic_remesh['simple_wave_terminal_planner']
  reflected_domain = report['geometry_cases']['solver_generated_reflected_domain_remesh']
  alternating_physical_chain_refinement = reflected_domain[
    'alternating_physical_field_chain_refinement'
  ]
  reflected_probe = report['geometry_cases']['reflected_zone_shock_coupling']
  reflected_chain_boundary = report['geometry_cases']['reflected_zone_chain_boundary_probe']
  trace_extension = report['geometry_cases']['reflected_boundary_trace_extension']
  planner = report['geometry_cases']['shock_cell_chain_planner_mock']
  invariant_closure = report['geometry_cases']['terminal_source_window_invariant_closure']
  ambient_strip = report['geometry_cases']['solver_generated_ambient_shock_strip']
  first_cell_research_chain = ambient_strip[
    'geometry_owned_first_cell_research_chain'
  ]
  first_cell_free_boundary_refinement = ambient_strip[
    'first_cell_terminal_closure_free_boundary_refinement_measurement'
  ]
  first_cell_terminal = report['geometry_cases']['solver_generated_first_cell_terminal_closure']
  first_cell_terminal_planner_summary = report['geometry_cases'][
    'solver_generated_first_cell_terminal_closure_planner'
  ]
  ambient_attachment = report['geometry_cases']['ambient_attachment_closure_probe']
  ambient_transition = report['geometry_cases']['ambient_attachment_transition_probe']
  ambient_closure = report['geometry_cases']['ambient_pressure_closure_probe']
  strong_subsonic_boundary = report['geometry_cases']['marched_strong_subsonic_boundary']
  mixed_regime_boundary = report['geometry_cases']['mixed_regime_boundary_contract']
  post_shock_zone_planner = report['geometry_cases']['post_shock_zone_chain_planner']
  ambient_pressure_field_coupled_chain_planner = report['geometry_cases'][
    'ambient_pressure_field_coupled_chain_planner'
  ]
  source_strip_chain_planner = report['geometry_cases'][
    'solver_generated_source_strip_chain_planner'
  ]
  source_strip_chain_sequence_planner = report['geometry_cases'][
    'solver_generated_source_strip_chain_sequence_planner'
  ]
  caustic_upstream_remesh_chain_sequence = report['geometry_cases'][
    'caustic_upstream_remesh_chain_sequence'
  ]
  downstream_condition = mixed_regime_boundary['downstream_condition_contract']
  positive_wall_condition = mixed_regime_boundary[
    'downstream_condition_positive_wall_fixture'
  ]
  positive_outflow_condition = mixed_regime_boundary[
    'downstream_condition_positive_outflow_fixture'
  ]
  frozen_profile_reference = mixed_regime_boundary[
    'planar_frozen_profile_reference'
  ]
  frozen_profile_configuration = mixed_regime_boundary[
    'planar_frozen_profile_reference_configuration'
  ]
  frozen_profile_measurement = mixed_regime_boundary[
    'planar_frozen_profile_reference_measurement'
  ]

  assert generated['status'] == 'converged_free_boundary_field'
  assert generated['field_status'] == 'converged_closed'
  assert generated['topology_forms_closed_zone'] is True
  assert generated['pressure_loss_verified'] is True
  assert refinement['status'] == 'diagnostic-all-solver-generated-resolutions-converged'
  assert len(refinement['cases']) == 3
  assert generated_chain['accepted'] is True
  assert generated_chain['resolved'] is True
  assert generated_chain['cell_count'] == 5
  assert generated_chain['state_carry_count'] == 5
  assert generated_chain['physical_termination'] is False
  assert generated_chain['claim_fidelity_ceiling'] == 'resolved-planar-moc'
  assert generated_chain['free_boundary_verified'] is False
  assert generated_chain['physical_chain_promotion_allowed'] is False
  assert generated_chain_refinement['status'] == 'converged'
  assert generated_chain_refinement['operator_id'] == (
    'op.moc.shock-cell-chain-refinement'
  )
  assert generated_chain_refinement['resolutions'] == [9, 17, 33]
  assert generated_chain_refinement['cell_count'] == 5
  assert all(generated_chain_refinement['checks'].values())
  assert generated_chain_refinement['claim_status'] == 'not_accepted'
  assert alternating_physical_chain_refinement['status'] == 'converged'
  assert alternating_physical_chain_refinement['operator_id'] == (
    'op.moc.reflected-domain-alternating-physical-field-chain-refinement'
  )
  assert alternating_physical_chain_refinement['resolutions'] == [17, 33]
  assert alternating_physical_chain_refinement['field_count'] == 2
  assert all(
    value is True
    for value in alternating_physical_chain_refinement['checks'].values()
    if value is not None
  )
  assert alternating_physical_chain_refinement['physical_closure_verified'] is False
  assert alternating_physical_chain_refinement['chain_promotion_blocked'] is True
  assert alternating_physical_chain_refinement['production_claim_allowed'] is False
  assert alternating_physical_chain_refinement['declared_tolerances'] == {
    'endpoint_tolerance_m': 1.0e-3,
    'shock_spacing_tolerance_m': 1.0e-4,
    'area_tolerance_m2': 1.5e-3,
    'maximum_radius_tolerance_m': 5.0e-4,
  }
  assert generated_chain_external_validation['status'] == (
    'blocked-missing-external-observations'
  )
  assert generated_chain_external_validation['comparison_operator_id'] == (
    'op.moc.shock-cell-external-comparison'
  )
  assert generated_chain_external_validation['dataset_status'] == (
    'no-indexed-moc-dataset-bound'
  )
  assert generated_chain_external_validation['dataset_count'] == 0
  assert generated_chain_external_validation['datasets'] == []
  assert generated_chain_external_validation['comparison'] is None
  assert generated_chain_external_validation['accepted_external_claim'] is False
  assert generated_chain_external_validation['claim_status'] == 'not_accepted'
  assert generated_chain_external_validation['split_audit']['status'] == (
    'blocked-missing-split'
  )
  assert generated_chain_external_validation['split_audit']['dataset_count'] == 0
  assert generated_chain_external_validation['split_audit']['verified'] is False
  assert first_cell_research_chain['planner_kind'] == 'upstream-coupled-research'
  assert first_cell_research_chain['resolved'] is True
  assert first_cell_research_chain['cell_count'] == 2
  assert first_cell_research_chain['continued_cell_count'] == 1
  assert first_cell_research_chain['research_audit_accepted'] is True
  assert first_cell_research_chain['first_cell_handoff_verified'] is True
  assert first_cell_research_chain['continued_chain_audit_verified'] is True
  assert first_cell_research_chain['handoff_links_verified'] is True
  assert first_cell_research_chain['chain_promotion_blocked'] is True
  assert first_cell_research_chain['production_claim_allowed'] is False
  assert first_cell_research_chain['research_chain_measurement']['status'] == (
    'converged'
  )
  assert first_cell_research_chain['research_chain_measurement']['operator_id'] == (
    'op.moc.first-cell-geometry-owned-research-chain'
  )
  assert generated_chain_external_validation['model_chain_measurement']['status'] == (
    'converged'
  )
  assert 'no synthetic observations' in generated_chain_external_validation[
    'conversion_policy'
  ]
  assert generated_chain_planner['planner_kind'] == 'solver-generated-reference'
  assert generated_chain_planner['planning_only'] is True
  assert generated_chain_planner['production_claim_allowed'] is False
  assert generated_chain_planner['planner_step_count'] == 5
  assert generated_chain_planner['handoff_links_verified'] is True
  assert generated_chain_planner['diagnostics']['solver_generated_chain_reference']['model'] == (
    'solver-generated-post-shock-chain-reference'
  )
  assert generated_chain_planner['diagnostics']['solver_generated_chain_reference']['production_claim_allowed'] is False
  generated_chain_planner_measurement = generated_chain_planner['planner_measurement']
  assert generated_chain_planner_measurement['status'] == 'converged'
  assert generated_chain_planner_measurement['planner_kind'] == 'solver-generated-reference'
  assert generated_chain_planner_measurement['counts'] == {
    'steps': 5,
    'chain_cells': 5,
    'handoff_links': 4,
  }
  assert all(generated_chain_planner_measurement['checks'].values())
  assert generated_chain_planner_measurement['physical_termination'] is False
  assert generated_chain_planner_measurement['production_claim_allowed'] is False
  assert [step['next_cell_index'] for step in generated_chain_planner['planner_steps']] == [2, 3, 4, 5, 6]
  assert all(
    step['boundary_kind'] == 'post-shock-field-perimeter'
    and step['incoming_handoff_sample_count'] >= 3
    and step['incoming_handoff_fingerprint']
    for step in generated_chain_planner['planner_steps']
  )
  assert all(
    step['result_consumed_handoff_sample_count'] >= 3
    and step['result_consumed_total_pressure_range_Pa']
    and step['result_consumed_handoff_fingerprint']
    for step in generated_chain_planner['planner_steps'][:4]
  )
  assert source_strip_chain_planner['accepted'] is True
  assert source_strip_chain_planner['planner']['planner_kind'] == (
    'upstream-coupled-research'
  )
  assert source_strip_chain_planner['planner']['planning_only'] is True
  assert source_strip_chain_planner['planner']['production_claim_allowed'] is False
  assert source_strip_chain_planner['planner']['chain']['termination_reason'] == (
    'characteristic-caustic'
  )
  assert source_strip_chain_planner['planner']['chain']['physical_termination'] is False
  assert source_strip_chain_planner['planner']['step_count'] == 1
  assert source_strip_chain_planner['planner']['diagnostics']['one_step_domain'] is True
  assert source_strip_chain_planner['planner']['diagnostics']['source_strip_reuse_policy'] == (
    'never-reuse-after-one-next-cell-attempt'
  )
  _assert_chain_planner_measurement(
    source_strip_chain_planner['planner_measurement'],
    physical_termination=False,
  )
  assert source_strip_chain_sequence_planner['accepted'] is True
  assert source_strip_chain_sequence_planner['planner']['planner_kind'] == (
    'upstream-coupled-research'
  )
  assert source_strip_chain_sequence_planner['planner']['planning_only'] is True
  assert source_strip_chain_sequence_planner['planner']['production_claim_allowed'] is False
  assert source_strip_chain_sequence_planner['planner']['chain']['termination_reason'] == (
    'characteristic-caustic'
  )
  assert source_strip_chain_sequence_planner['planner']['chain']['physical_termination'] is False
  assert source_strip_chain_sequence_planner['planner']['step_count'] == 1
  assert source_strip_chain_sequence_planner['planner']['diagnostics']['one_step_domain'] is False
  assert source_strip_chain_sequence_planner['planner']['diagnostics']['source_domain_count'] == 1
  assert source_strip_chain_sequence_planner['planner']['diagnostics']['source_domain_attempt_count'] == 1
  assert source_strip_chain_sequence_planner['planner']['diagnostics']['source_strip_reuse_policy'] == (
    'fresh-bounded-source-strip-required-per-cell'
  )
  _assert_chain_planner_measurement(
    source_strip_chain_sequence_planner['planner_measurement'],
    physical_termination=False,
  )
  assert all(
    step['incoming_handoff_link_verified'] is True
    for step in generated_chain_planner['planner_steps'][1:]
  )
  assert [step['result_kind'] for step in generated_chain_planner['planner_steps']] == [
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'termination-returned',
  ]
  assert [step['result_status'] for step in generated_chain_planner['planner_steps']] == [
    'converged_closed',
    'converged_closed',
    'converged_closed',
    'converged_closed',
    'solver-returned-no-next-cell',
  ]
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
  assert terminal_planner['planner_steps'][0]['result_kind'] == 'termination-returned'
  assert terminal_planner['planner_steps'][0]['result_status'] == 'physical-termination'
  assert terminal_planner['planner_steps'][0]['result_termination_reason'] == 'physical-termination'
  assert terminal_planner['planner_steps'][0]['result_physical_termination'] is True
  assert generated_chain_terminal['expected_physical_termination'] is True
  assert generated_chain_terminal['diagnostics']['termination_model'] == 'normal-shock-terminal'
  _assert_chain_planner_measurement(
    generated_chain_terminal['planner_measurement'],
    physical_termination=True,
  )
  generated_chain_measurement = generated_chain['chain_measurement_operator']
  assert generated_chain_measurement['status'] == 'converged'
  assert generated_chain_measurement['cell_count'] == 5
  assert generated_chain_measurement['handoff']['link_count'] == 4
  assert generated_chain_measurement['handoff']['links_verified'] is True
  assert field_coupled_chain_planner['accepted'] is True
  assert field_coupled_chain_planner['planner_kind'] == 'upstream-coupled-research'
  assert field_coupled_chain_planner['planning_only'] is True
  assert field_coupled_chain_planner['production_claim_allowed'] is False
  assert field_coupled_chain_planner['reference']['model'] == (
    'field-coupled-post-shock-chain-reference'
  )
  assert field_coupled_chain_planner['reference']['upstream_state_model'] == (
    'bounded-previous-post-shock-field'
  )
  assert field_coupled_chain_planner['upstream_field_replacement_policy'] == (
    'replace-only-after-complete-field-coupled-solve'
  )
  assert field_coupled_chain_planner['status'] == 'physically-terminated'
  assert field_coupled_chain_planner['planner_measurement']['status'] == 'converged'
  field_coupled_measurement_checks = field_coupled_chain_planner['planner_measurement']['checks']
  assert all(
    value
    for name, value in field_coupled_measurement_checks.items()
    if name != 'handoff_links_verified'
  )
  assert field_coupled_measurement_checks['handoff_links_verified'] is None
  assert field_coupled_chain_planner['planner_measurement']['physical_termination'] is True
  assert field_coupled_chain_planner['planner_measurement']['production_claim_allowed'] is False
  assert field_coupled_chain_planner['termination_reason'] == 'physical-termination'
  assert field_coupled_chain_planner['physical_termination'] is True
  assert field_coupled_chain_planner['cell_count'] == 1
  assert field_coupled_chain_planner['resolved'] is True
  assert field_coupled_chain_planner['planner_step_count'] == 1
  assert field_coupled_chain_planner['planner_steps'][0]['boundary_kind'] == (
    'post-shock-field-perimeter'
  )
  assert field_coupled_chain_planner['planner_steps'][0]['incoming_handoff_sample_count'] >= 3
  assert field_coupled_chain_planner['planner_steps'][0]['result_kind'] == 'termination-returned'
  assert field_coupled_chain_planner['planner_steps'][0]['result_status'] == 'physical-termination'
  assert field_coupled_chain_planner['chain_diagnostics']['termination_model'] == (
    'normal-shock-terminal'
  )
  assert field_coupled_chain_planner['chain_diagnostics']['upstream_field_model'] == (
    'bounded-post-shock-characteristic-field'
  )
  assert post_shock_zone_planner['accepted'] is True
  assert post_shock_zone_planner['physical_termination'] is True
  assert post_shock_zone_planner['claim_status'] == (
    'bounded-open-post-shock-zone-next-shock; '
    'mixed-regime-downstream-closure-pending'
  )
  assert post_shock_zone_planner['open_zone']['state_sampling_available'] is True
  zone_planner = post_shock_zone_planner['planner']
  assert zone_planner['planner_kind'] == 'upstream-coupled-research'
  assert zone_planner['planning_only'] is True
  assert zone_planner['production_claim_allowed'] is False
  assert zone_planner['step_count'] == 1
  assert zone_planner['chain']['status'] == 'physically-terminated'
  assert zone_planner['chain']['termination_reason'] == 'physical-termination'
  assert zone_planner['chain']['physical_termination'] is True
  assert zone_planner['chain']['diagnostics']['termination_model'] == (
    'normal-shock-terminal'
  )
  assert zone_planner['chain']['diagnostics']['upstream_field_model'] == (
    'bounded-open-post-shock-zone'
  )
  assert zone_planner['chain']['diagnostics']['upstream_sample_count'] == 4
  assert zone_planner['steps'][0]['boundary_kind'] == 'post-shock-field-perimeter'
  assert zone_planner['steps'][0]['result_kind'] == 'termination-returned'
  assert zone_planner['steps'][0]['result_status'] == 'physical-termination'
  assert zone_planner['steps'][0]['result_physical_termination'] is True
  _assert_chain_planner_measurement(
    post_shock_zone_planner['planner_measurement'],
    physical_termination=True,
  )
  assert ambient_pressure_field_coupled_chain_planner['accepted'] is True
  _assert_chain_planner_measurement(
    ambient_pressure_field_coupled_chain_planner['planner_measurement'],
    physical_termination=False,
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
  assert caustic_upstream_bridge['accepted'] is True
  assert caustic_upstream_bridge['status'] == 'diagnostic-bounded-caustic-upstream-bridge'
  assert caustic_upstream_bridge['bridge']['fields_converged'] is True
  bounded_source = caustic_upstream_bridge['bounded_source_audit']
  assert bounded_source['source']['model'] == 'bounded-caustic-upstream-bridge'
  assert bounded_source['source']['upstream_coupling_verified'] is False
  assert bounded_source['source']['extrapolation_allowed'] is False
  assert bounded_source['old_point_state_matches_bridge'] is True
  assert bounded_source['restarted_point_state_matches_bridge'] is True
  assert bounded_source['old_point_pressure_matches_bridge'] is True
  assert bounded_source['restarted_point_pressure_matches_bridge'] is True
  assert bounded_source['gap_state_is_none'] is True
  assert bounded_source['gap_pressure_is_none'] is True
  assert caustic_upstream_bridge['covered_path_audit']['status'] == (
    'converged_bounded_caustic_bridge_path'
  )
  assert caustic_upstream_bridge['gap_audit']['status'] == 'caustic_bridge_domain_gap'
  assert caustic_upstream_bridge['gap_audit']['first_missing_sample_index'] == 2
  assert caustic_upstream_bridge['explicit_old_side_no_fallback_audit']['status'] == (
    'caustic_bridge_selected_side_domain_gap'
  )
  assert caustic_upstream_bridge['shock']['upstream_coupling_verified'] is True
  assert caustic_upstream_bridge['shock']['physical_closure_verified'] is False
  candidate_shock = caustic_upstream_bridge['candidate_shock']
  assert candidate_shock['shock']['status'] == 'upstream_field_failure'
  assert candidate_shock['shock']['sample_count'] == 1
  assert candidate_shock['shock']['failed_sample_index'] == 1
  assert candidate_shock['shock']['failed_point_m'] is not None
  assert candidate_shock['coupling']['status'] == 'caustic_bridge_domain_gap'
  assert candidate_shock['coupling']['sampled_count'] == 1
  assert candidate_shock['coupling']['first_missing_sample_index'] == 1
  assert candidate_shock['coupling']['first_missing_point_m'] == (
    candidate_shock['shock']['failed_point_m']
  )
  assert candidate_shock['upstream_coupling_verified'] is False
  candidate_planner = caustic_upstream_bridge['candidate_planner']
  assert candidate_planner['production_claim_allowed'] is False
  assert candidate_planner['chain']['termination_reason'] == (
    'upstream-field-boundary'
  )
  assert candidate_planner['chain']['physical_termination'] is False
  assert candidate_planner['chain']['cell_count'] == 1
  assert candidate_planner['chain']['diagnostics'][
    'bridge_first_missing_sample_index'
  ] == 1
  assert candidate_planner['chain']['diagnostics'][
    'bridge_first_missing_point_m'
  ] == candidate_shock['coupling']['first_missing_point_m']
  _assert_chain_planner_measurement(
    caustic_upstream_bridge['candidate_planner_measurement'],
    physical_termination=False,
  )
  assert caustic_upstream_bridge['invariant_shock']['shock']['status'] == (
    'upstream_field_failure'
  )
  assert caustic_upstream_bridge['invariant_shock']['coupling']['status'] == (
    'caustic_bridge_domain_gap'
  )
  assert caustic_upstream_bridge['invariant_shock']['coupling'][
    'first_missing_sample_index'
  ] == 4
  assert caustic_upstream_bridge['invariant_shock']['physical_closure_verified'] is False
  assert caustic_upstream_bridge['planner']['production_claim_allowed'] is False
  assert caustic_upstream_bridge['planner']['chain']['termination_reason'] == (
    'open-physical-closure'
  )
  _assert_chain_planner_measurement(
    caustic_upstream_bridge['planner_measurement'],
    physical_termination=False,
  )
  assert caustic_upstream_bridge['invariant_planner']['production_claim_allowed'] is False
  assert caustic_upstream_bridge['invariant_planner']['chain']['termination_reason'] == (
    'upstream-field-boundary'
  )
  _assert_chain_planner_measurement(
    caustic_upstream_bridge['invariant_planner_measurement'],
    physical_termination=False,
  )
  assert caustic_upstream_bridge['physical_bridge_planner'] is not None
  physical_bridge_planner = caustic_upstream_bridge['physical_bridge_planner']
  assert physical_bridge_planner['planner_kind'] == 'upstream-coupled-research'
  assert physical_bridge_planner['planning_only'] is True
  assert physical_bridge_planner['production_claim_allowed'] is False
  assert physical_bridge_planner['step_count'] == 1
  assert physical_bridge_planner['chain']['status'] == 'solver-terminated'
  assert physical_bridge_planner['chain']['termination_reason'] == (
    'open-physical-closure'
  )
  assert physical_bridge_planner['chain']['cell_count'] == 1
  assert physical_bridge_planner['chain']['physical_termination'] is False
  assert physical_bridge_planner['chain']['diagnostics']['upstream_source'][
    'model'
  ] == 'bounded-caustic-upstream-bridge'
  assert physical_bridge_planner['chain']['diagnostics'][
    'start_point_provenance'
  ] == 'bounded-source-preferred'
  assert physical_bridge_planner['chain']['diagnostics'][
    'start_point_downstream_of_current_cell'
  ] is True
  _assert_chain_planner_measurement(
    caustic_upstream_bridge['physical_bridge_planner_measurement'],
    physical_termination=False,
  )
  assert caustic_upstream_continuation['status'] == (
    'solver-owned-bounded-caustic-upstream-continuation'
  )
  assert caustic_upstream_continuation['accepted'] is True
  assert caustic_upstream_continuation['event_sample_available'] is True
  branch_audit = caustic_upstream_continuation['branch_audit']
  assert branch_audit['status'] == (
    'caustic_continuation_branch_selection_required'
  )
  assert branch_audit['converged'] is False
  assert branch_audit['bridge'] is None
  assert branch_audit['restart_count'] == 2
  assert all(
    restart['converged'] is True
    and restart['caustic_handoff_verified'] is True
    for restart in branch_audit['restart_results']
  )
  continuation = caustic_upstream_continuation['continuation']
  assert continuation['status'] == (
    'converged_bounded_caustic_upstream_continuation'
  )
  assert continuation['converged'] is True
  assert continuation['selected_anchor_edge_index'] == 0
  assert continuation['seam_verified'] is True
  assert continuation['state_sampling_available'] is True
  assert continuation['bridge']['fields_converged'] is True
  assert continuation['physical_closure_verified'] is False
  assert continuation['chain_promotion_blocked'] is True
  assert continuation['chain_termination_decision']['reason'] == (
    'characteristic-caustic'
  )
  continuation_planner = caustic_upstream_continuation['planner']
  assert continuation_planner['planner_kind'] == 'upstream-coupled-research'
  assert continuation_planner['branch_audit_verified'] is True
  assert continuation_planner['resolved'] is True
  assert continuation_planner['physical_closure_verified'] is False
  assert continuation_planner['chain_promotion_blocked'] is True
  assert continuation_planner['termination']['reason'] == (
    'characteristic-caustic'
  )
  assert caustic_remesh['accepted'] is True
  assert caustic_remesh['status'] == 'diagnostic-coupled-caustic-remesh-execution'
  assert caustic_remesh['direct']['status'] == (
    'converged_coupled_caustic_shock_remesh'
  )
  assert caustic_remesh['direct']['remesh_seam_verified'] is True
  assert caustic_remesh['direct']['physical_closure_verified'] is False
  assert caustic_remesh['direct']['chain_promotion_blocked'] is True
  assert caustic_remesh['direct_measurement']['status'] == 'converged'
  assert caustic_remesh['direct_measurement']['checks']['bounded_remesh_verified'] is True
  assert caustic_remesh['direct_measurement']['checks']['incoming_handoff_verified'] is True
  assert caustic_remesh['direct_measurement']['physical_closure_verified'] is False
  assert caustic_remesh['direct_measurement']['chain_promotion_blocked'] is True
  assert caustic_remesh['direct_measurement']['field_topology']['forms_closed_zone'] is True
  assert caustic_remesh['planner']['planner_kind'] == 'upstream-coupled-research'
  assert caustic_remesh['planner']['planning_only'] is True
  assert caustic_remesh['planner']['production_claim_allowed'] is False
  assert caustic_remesh['planner']['step_count'] == 1
  assert caustic_remesh['planner']['steps'][0]['result_kind'] == 'termination-returned'
  assert caustic_remesh['planner']['chain']['cell_count'] == 1
  assert caustic_remesh['planner']['chain']['physical_termination'] is False
  assert caustic_remesh['planner']['chain']['termination_reason'] == (
    'open-physical-closure'
  )
  _assert_chain_planner_measurement(
    caustic_remesh['planner_measurement'],
    physical_termination=False,
  )
  upstream_cauchy = caustic_remesh['upstream_cauchy_remesh']
  assert upstream_cauchy['status'] == (
    'diagnostic-caustic-upstream-cauchy-remesh'
  )
  assert upstream_cauchy['accepted'] is True
  assert upstream_cauchy['remesh']['status'] == (
    'converged_bounded_caustic_upstream_field'
  )
  assert upstream_cauchy['remesh']['state_sampling_available'] is True
  assert upstream_cauchy['remesh']['event_seam_verified'] is True
  assert upstream_cauchy['remesh']['centerline_trace_verified'] is True
  assert upstream_cauchy['remesh']['outer_trace_verified'] is True
  assert upstream_cauchy['remesh']['source_field_verified'] is True
  assert upstream_cauchy['remesh']['physical_closure_verified'] is False
  assert upstream_cauchy['remesh']['chain_promotion_blocked'] is True
  assert upstream_cauchy['remesh']['request']['source_data_model'] == (
    'explicit-centerline-c-plus-and-outer-pre-shock-c-minus-traces'
  )
  assert upstream_cauchy['remesh']['request']['outer_trace_generation'] == (
    'caller-supplied-coupled-remesher-data'
  )
  assert upstream_cauchy['remesh']['strip']['topology_forms_closed_zone'] is True
  assert upstream_cauchy['direct_shock']['status'] == 'upstream_field_failure'
  assert upstream_cauchy['direct_shock']['sample_count'] == 4
  assert upstream_cauchy['direct_shock']['failed_sample_index'] == 4
  assert upstream_cauchy['planner']['planner_kind'] == (
    'upstream-coupled-research'
  )
  assert upstream_cauchy['planner']['planning_only'] is True
  assert upstream_cauchy['planner']['production_claim_allowed'] is False
  assert upstream_cauchy['planner']['step_count'] == 1
  assert upstream_cauchy['planner']['steps'][0]['result_kind'] == (
    'termination-returned'
  )
  assert upstream_cauchy['planner']['steps'][0]['result_termination_reason'] == (
    'upstream-field-boundary'
  )
  assert upstream_cauchy['planner']['chain']['cell_count'] == 1
  assert upstream_cauchy['planner']['chain']['physical_termination'] is False
  assert upstream_cauchy['planner']['chain']['termination_reason'] == (
    'upstream-field-boundary'
  )
  assert upstream_cauchy['planner']['diagnostics']['one_step_domain'] is True
  assert upstream_cauchy['planner']['diagnostics']['source_strip_reuse_policy'] == (
    'never-reuse-after-one-next-cell-attempt'
  )
  _assert_chain_planner_measurement(
    upstream_cauchy['planner_measurement'],
    physical_termination=False,
  )
  assert caustic_upstream_remesh_chain_sequence['status'] == (
    'diagnostic-caustic-upstream-remesh-chain-sequence'
  )
  assert caustic_upstream_remesh_chain_sequence['accepted'] is True
  caustic_remesh_sequence_planner = caustic_upstream_remesh_chain_sequence[
    'planner'
  ]
  assert caustic_remesh_sequence_planner['planner_kind'] == (
    'upstream-coupled-research'
  )
  assert caustic_remesh_sequence_planner['planning_only'] is True
  assert caustic_remesh_sequence_planner['production_claim_allowed'] is False
  assert caustic_remesh_sequence_planner['step_count'] == 3
  assert caustic_remesh_sequence_planner['chain']['cell_count'] == 3
  assert caustic_remesh_sequence_planner['chain']['physical_termination'] is False
  assert caustic_remesh_sequence_planner['chain']['termination_reason'] == (
    'upstream-field-boundary'
  )
  assert caustic_remesh_sequence_planner['handoff_links_verified'] is True
  sequence_attempts = caustic_upstream_remesh_chain_sequence[
    'provider_attempts'
  ]
  assert len(sequence_attempts) == 3
  assert sequence_attempts[1]['incoming_handoff_verified'] is True
  assert sequence_attempts[2]['incoming_handoff_verified'] is True
  assert sequence_attempts[2]['fresh_remesh'] is False
  assert sequence_attempts[2]['fresh_strip'] is False
  assert caustic_upstream_remesh_chain_sequence['provider_calls'] == [
    {
      'current_cell_index': 2,
      'next_cell_index': 3,
      'incoming_handoff_sample_count': 6,
    },
    {
      'current_cell_index': 3,
      'next_cell_index': 4,
      'incoming_handoff_sample_count': 6,
    },
  ]
  assert caustic_remesh_sequence_planner['diagnostics'][
    'one_step_domain'
  ] is False
  assert caustic_remesh_sequence_planner['diagnostics'][
    'upstream_remesh_domain_count'
  ] == 2
  assert caustic_remesh_sequence_planner['diagnostics'][
    'upstream_remesh_domain_attempt_count'
  ] == 3
  assert caustic_remesh_sequence_planner['diagnostics'][
    'upstream_remesh_reuse_policy'
  ] == 'fresh-bounded-caustic-remesh-required-per-cell'
  assert caustic_upstream_remesh_chain_sequence['prescribed_cell_solver'][
    'free_boundary_verified'
  ] is False
  assert caustic_upstream_remesh_chain_sequence['prescribed_cell_solver'][
    'physical_chain_promotion_allowed'
  ] is False
  _assert_chain_planner_measurement(
    caustic_upstream_remesh_chain_sequence['planner_measurement'],
    physical_termination=False,
  )
  assert caustic_remesh['bridge_coupled_remesh']['status'] == (
    'caustic_remesh_upstream_field_failure'
  )
  assert caustic_remesh['bridge_coupled_remesh']['upstream_bridge_verified'] is False
  assert caustic_remesh['bridge_coupled_remesh']['upstream_bridge_audit']['status'] == (
    'caustic_bridge_domain_gap'
  )
  assert caustic_remesh['bridge_coupled_remesh']['upstream_bridge_audit'][
    'first_missing_sample_index'
  ] == 1
  assert caustic_remesh['bridge_coupled_remesh']['shock']['failed_sample_index'] == 1
  assert caustic_remesh['bridge_coupled_measurement']['status'] == 'upstream_failure'
  assert caustic_remesh['bridge_coupled_measurement']['checks']['incoming_handoff_verified'] is False
  assert caustic_remesh['bridge_coupled_measurement']['bridge_status'] == (
    'caustic_bridge_selected_side_domain_gap'
  )
  assert caustic_remesh['bridge_coupled_measurement']['first_missing_sample_index'] == 1
  assert caustic_remesh['bridge_coupled_measurement']['first_missing_point_m'] == (
    caustic_remesh['bridge_coupled_remesh']['shock']['failed_point_m']
  )
  assert caustic_remesh['bridge_coupled_planner']['planner_kind'] == (
    'upstream-coupled-research'
  )
  assert caustic_remesh['bridge_coupled_planner']['diagnostics'][
    'strict_bridge_required'
  ] is True
  assert caustic_remesh['bridge_coupled_planner']['chain']['cell_count'] == 1
  assert caustic_remesh['bridge_coupled_planner']['chain']['physical_termination'] is False
  assert caustic_remesh['bridge_coupled_planner']['chain']['termination_reason'] == (
    'upstream-field-boundary'
  )
  assert caustic_remesh['bridge_coupled_planner']['chain']['diagnostics'][
    'remesh_report'
  ]['upstream_bridge_audit']['status'] == 'caustic_bridge_domain_gap'
  _assert_chain_planner_measurement(
    caustic_remesh['bridge_coupled_planner_measurement'],
    physical_termination=False,
  )
  assert simple_wave_terminal['status'] == (
    'converged_open_simple_wave_terminal_field'
  )
  assert simple_wave_terminal['converged'] is True
  assert simple_wave_terminal['trace']['status'] == (
    'converged_solver_owned_simple_wave_trace'
  )
  assert simple_wave_terminal['event_seam_verified'] is True
  assert simple_wave_terminal['local_bridge_state_verified'] is True
  assert simple_wave_terminal['upstream_coupling_verified'] is True
  assert simple_wave_terminal['shock_prefix_verified'] is True
  assert simple_wave_terminal['downstream_zone_verified'] is True
  assert simple_wave_terminal['terminal_verified'] is True
  assert simple_wave_terminal['physical_terminal_verified'] is True
  assert simple_wave_terminal['physical_closure_verified'] is False
  assert simple_wave_terminal['chain_promotion_blocked'] is True
  assert simple_wave_terminal_planner['planner_kind'] == (
    'upstream-coupled-research'
  )
  assert simple_wave_terminal_planner['planning_only'] is True
  assert simple_wave_terminal_planner['production_claim_allowed'] is False
  assert simple_wave_terminal_planner['step_count'] == 1
  assert simple_wave_terminal_planner['steps'][0]['result_kind'] == (
    'termination-returned'
  )
  assert simple_wave_terminal_planner['chain']['status'] == 'solver-terminated'
  assert simple_wave_terminal_planner['chain']['termination_reason'] == (
    'open-physical-closure'
  )
  assert simple_wave_terminal_planner['chain']['physical_termination'] is False
  assert simple_wave_terminal_planner['chain']['cell_count'] == 1
  assert simple_wave_terminal_planner['steps'][0][
    'incoming_handoff_sample_count'
  ] == 10
  assert simple_wave_terminal_planner['chain']['diagnostics'][
    'terminal_verified'
  ] is True
  assert simple_wave_terminal_planner['chain']['diagnostics'][
    'chain_promotion_blocked'
  ] is True
  _assert_chain_planner_measurement(
    caustic_remesh['simple_wave_terminal_planner_measurement'],
    physical_termination=False,
  )
  assert strong_subsonic_boundary['status'] == 'subsonic_terminal_required'
  assert strong_subsonic_boundary['subsonic_boundary_verified'] is True
  assert strong_subsonic_boundary['terminal_model_verified'] is False
  assert strong_subsonic_boundary['subsonic_shock_boundary']['branch'] == 'strong'
  assert strong_subsonic_boundary['subsonic_shock_boundary']['subsonic'] is True
  assert strong_subsonic_boundary['normal_shock_terminal'] is None
  assert mixed_regime_boundary['accepted'] is True
  flux_reference = mixed_regime_boundary[
    'solver_generated_control_section_flux_reference'
  ]
  flux_measurement = mixed_regime_boundary[
    'solver_generated_control_section_flux_measurement'
  ]
  assert flux_reference['model'] == (
    'solver-owned-control-section-flux-quasi-1d-reference'
  )
  assert flux_reference['control_section_projection_verified'] is False
  assert flux_reference['control_section_flux_verified'] is True
  assert flux_reference['chain_promotion_blocked'] is True
  assert flux_measurement['status'] == (
    'converged_solver_owned_free_boundary_measurement'
  )
  assert flux_measurement['checks']['control_section_verified'] is True
  assert flux_measurement['checks']['control_section_flux_verified'] is True
  assert flux_measurement['physical_closure_verified'] is True
  assert flux_measurement['chain_promotion_blocked'] is True
  closure_mock = mixed_regime_boundary['mixed_regime_closure_mock']
  assert closure_mock['model'] == (
    'prescribed-pressure-outflow-mixed-regime-closure-mock'
  )
  assert closure_mock['planning_only'] is True
  assert closure_mock['production_claim_allowed'] is False
  assert closure_mock['condition_kind'] == 'prescribed-pressure-outflow-section'
  assert closure_mock['streamwise_length_m'] == pytest.approx(0.02)
  assert closure_mock['transverse_length_m'] == pytest.approx(0.01)
  assert closure_mock['radial_divisions'] == 2
  assert downstream_condition['status'] == 'downstream-tangency-failure'
  assert downstream_condition['physical_condition_verified'] is False
  assert downstream_condition['chain_promotion_blocked'] is True
  assert positive_wall_condition['status'] == 'converged-downstream-condition'
  assert positive_wall_condition['physical_condition_verified'] is True
  assert positive_wall_condition['chain_promotion_blocked'] is True
  assert positive_outflow_condition['status'] == 'converged-downstream-condition'
  assert positive_outflow_condition['physical_condition_verified'] is True
  assert positive_outflow_condition['tangency_condition_applicable'] is False
  assert positive_outflow_condition['tangent_sample_count'] == 0
  assert positive_outflow_condition['pressure_condition_verified'] is True
  assert positive_outflow_condition['chain_promotion_blocked'] is True
  assert frozen_profile_configuration['model'] == (
    'control-section-frozen-profile-compressible-potential-reference'
  )
  assert frozen_profile_configuration['projection_model'] == (
    'piecewise-linear-frozen-transverse-profile'
  )
  assert frozen_profile_configuration['normal_profile_policy'] == (
    'constant-normal-component-required'
  )
  assert frozen_profile_configuration['extrapolation_allowed'] is False
  assert frozen_profile_configuration['production_claim_allowed'] is False
  assert frozen_profile_reference['status'] == (
    'converged-planar-downstream-handoff'
  )
  assert frozen_profile_reference['handoff_verified'] is True
  assert frozen_profile_reference['section_is_varying'] is True
  assert frozen_profile_reference['control_section_projection_verified'] is True
  assert frozen_profile_reference['projection_model'] == (
    'piecewise-linear-frozen-transverse-profile'
  )
  assert frozen_profile_reference['physical_closure_verified'] is False
  assert frozen_profile_reference['canonical_free_boundary_verified'] is False
  assert frozen_profile_reference['chain_promotion_blocked'] is True
  assert frozen_profile_reference['production_claim_allowed'] is False
  assert frozen_profile_measurement['status'] == (
    'converged_reference_measurement'
  )
  assert frozen_profile_measurement['checks']['reference_model_verified'] is True
  assert frozen_profile_measurement['checks']['boundary_verified'] is True
  assert frozen_profile_measurement['checks']['potential_layout_verified'] is True
  assert frozen_profile_measurement['checks']['downstream_condition_verified'] is True
  assert frozen_profile_measurement['physical_closure_verified'] is False
  assert frozen_profile_measurement['chain_promotion_blocked'] is True
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
  assert elliptic_field['model_closure_verified'] is True
  assert elliptic_field['downstream_condition_verified'] is False
  assert elliptic_field['physical_closure_verified'] is False
  assert elliptic_field['mixed_regime_field_complete'] is False
  assert elliptic_field['topology_forms_closed_zone'] is True
  assert elliptic_field['topology_nonmanifold_edge_count'] == 0
  assert elliptic_field['maximum_thermodynamic_residual'] <= 1.0e-8
  assert elliptic_field['maximum_harmonic_residual'] <= 1.0e-12
  assert elliptic_field['maximum_velocity_divergence_residual'] <= 1.0e-12
  elliptic_refinement = mixed_regime_boundary['elliptic_subsonic_field_refinement']
  assert [case['radial_divisions'] for case in elliptic_refinement] == [2, 3, 4]
  assert [case['node_count'] for case in elliptic_refinement] == [9, 13, 17]
  assert [case['cell_count'] for case in elliptic_refinement] == [12, 20, 28]
  assert all(
    case['status'] == 'converged_elliptic_subsonic_field'
    and case['model'] == 'elliptic-isentropic-radial-reference'
    and case['model_closure_verified'] is True
    and case['downstream_condition_verified'] is False
    and case['physical_closure_verified'] is False
    and case['chain_promotion_blocked'] is True
    for case in elliptic_refinement
  )
  conditioned_field = mixed_regime_boundary[
    'elliptic_subsonic_field_conditioned_fixture'
  ]
  assert conditioned_field['physical_closure_verified'] is True
  assert conditioned_field['mixed_regime_field_complete'] is True
  assert conditioned_field['downstream_condition_verified'] is True
  conditioned_refinement = mixed_regime_boundary[
    'elliptic_subsonic_field_conditioned_refinement'
  ]
  assert [case['radial_divisions'] for case in conditioned_refinement] == [2, 3, 4]
  assert all(
    case['physical_closure_verified'] is True
    and case['downstream_condition_verified'] is True
    and case['chain_promotion_blocked'] is True
    for case in conditioned_refinement
  )
  potential_field = mixed_regime_boundary[
    'compressible_potential_field_reference'
  ]
  assert potential_field['status'] == (
    'converged_compressible_potential_subsonic_field'
  )
  assert potential_field['model'] == (
    'compressible-isentropic-potential-reference'
  )
  assert potential_field['model_closure_verified'] is True
  assert potential_field['physical_closure_verified'] is True
  assert potential_field['chain_promotion_blocked'] is True
  assert potential_field['velocity_potential_sample_count'] == (
    potential_field['node_count']
  )
  assert potential_field['maximum_mass_conservation_residual'] <= 1.0e-8
  assert potential_field['maximum_boundary_velocity_residual'] <= 1.0e-8
  assert potential_field['potential_circulation_residual'] <= 1.0e-8
  potential_refinement = mixed_regime_boundary[
    'compressible_potential_field_refinement'
  ]
  assert [case['radial_divisions'] for case in potential_refinement] == [2, 3, 4]
  assert [case['node_count'] for case in potential_refinement] == [9, 13, 17]
  assert [case['cell_count'] for case in potential_refinement] == [12, 20, 28]
  assert all(
    case['status'] == 'converged_compressible_potential_subsonic_field'
    and case['model'] == 'compressible-isentropic-potential-reference'
    and case['model_closure_verified'] is True
    and case['physical_closure_verified'] is True
    and case['downstream_condition_verified'] is True
    and case['chain_promotion_blocked'] is True
    and case['maximum_mass_conservation_residual'] <= 1.0e-8
    and case['maximum_boundary_velocity_residual'] <= 1.0e-8
    and case['potential_circulation_residual'] <= 1.0e-8
    for case in potential_refinement
  )
  potential_measurement = mixed_regime_boundary[
    'compressible_potential_measurement'
  ]
  assert potential_measurement['status'] == 'converged_reference_measurement'
  assert potential_measurement['operator_id'] == (
    'op.moc.mixed-regime-compressible-potential'
  )
  assert potential_measurement['converged'] is True
  assert potential_measurement['checks']['boundary_verified'] is True
  assert potential_measurement['checks']['potential_layout_verified'] is True
  assert potential_measurement['checks']['reference_model_verified'] is True
  assert potential_measurement['physical_closure_verified'] is False
  assert potential_measurement['chain_promotion_blocked'] is True
  potential_measurement_refinement = mixed_regime_boundary[
    'compressible_potential_measurement_refinement'
  ]
  assert [case['radial_divisions'] for case in potential_measurement_refinement] == [2, 3, 4]
  assert all(
    case['status'] == 'converged_reference_measurement'
    and case['checks']['reference_model_verified'] is True
    and case['physical_closure_verified'] is False
    and case['chain_promotion_blocked'] is True
    for case in potential_measurement_refinement
  )
  terminal_attachment_refinement = mixed_regime_boundary['terminal_attachment_refinement']
  assert [case['radial_divisions'] for case in terminal_attachment_refinement] == [2, 3, 4]
  assert all(
    case['mixed_regime_field_complete'] is True
    and case['physical_closure_verified'] is True
    and case['physical_termination_verified'] is True
    and case['chain_promotion_blocked'] is True
    and case['termination_decision']['physical_termination'] is True
    and case['termination_decision']['diagnostics']['mixed_regime_model'] == (
      'elliptic-isentropic-radial-reference'
    )
    for case in terminal_attachment_refinement
  )
  terminal_attachment = mixed_regime_boundary['terminal_attachment_contract_fixture']
  terminal_attachment_closure = mixed_regime_boundary['terminal_attachment_closure_result']
  terminal_closure_measurement = mixed_regime_boundary[
    'terminal_closure_measurement'
  ]
  terminal_attachment_measurement = mixed_regime_boundary[
    'terminal_attachment_measurement'
  ]
  assert terminal_attachment_closure['status'] == 'converged_mixed_regime_closure'
  assert terminal_attachment_closure['converged'] is True
  assert terminal_attachment_closure['physical_closure_verified'] is True
  assert terminal_attachment_closure['chain_promotion_blocked'] is True
  assert terminal_attachment_closure['perimeter_spec']['model'] == (
    'prescribed-pressure-outflow-mixed-regime-closure-mock'
  )
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
    'elliptic-isentropic-radial-reference'
  )
  assert terminal_closure_measurement['status'] == 'mixed_regime_failure'
  assert terminal_closure_measurement['physical_closure_verified'] is False
  assert terminal_closure_measurement['chain_promotion_blocked'] is True
  assert terminal_closure_measurement['checks']['terminal_shock_geometry_verified'] is True
  assert terminal_closure_measurement['checks']['terminal_pressure_loss_verified'] is True
  assert terminal_attachment_measurement['status'] == 'converged'
  assert terminal_attachment_measurement['converged'] is True
  assert terminal_attachment_measurement['physical_closure_verified'] is True
  assert terminal_attachment_measurement['physical_termination_verified'] is True
  assert terminal_attachment_measurement['chain_promotion_blocked'] is True
  assert terminal_attachment_measurement['checks']['mixed_regime_model_verified'] is True
  assert terminal_attachment_measurement['checks']['downstream_condition_verified'] is True
  assert terminal_attachment_measurement['residuals'][
    'maximum_thermodynamic_residual'
  ] <= 1.0e-8
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
  ambient_axis_closure = ambient_strip['ambient_axis_closure']
  assert ambient_strip['ambient_axis_closure_probe_accepted'] is True
  assert ambient_axis_closure['status'] == 'ambient_axis_pressure_failure'
  assert ambient_axis_closure['axis_candidate_verified'] is True
  assert ambient_axis_closure['ambient_pressure_verified'] is False
  assert ambient_axis_closure['axis_boundary_verified'] is False
  assert ambient_axis_closure['axis_boundary']['status'] == 'pressure_failure'
  assert ambient_axis_closure['physical_closure_verified'] is False
  assert ambient_axis_closure['chain_promotion_blocked'] is True
  assert ambient_axis_closure['relative_pressure_residual'] > 0.0
  ambient_axis_shoot = ambient_strip['ambient_axis_closure_shoot']
  assert ambient_strip['ambient_axis_closure_shoot_probe_accepted'] is True
  assert ambient_axis_shoot['status'] == 'ambient_axis_bracket_failure'
  assert ambient_axis_shoot['converged'] is False
  assert ambient_axis_shoot['trial_count'] == 2
  assert ambient_axis_shoot['physical_closure_verified'] is False
  assert ambient_axis_shoot['chain_promotion_blocked'] is True
  assert ambient_axis_shoot['axis_boundary_verified'] is False
  assert all(
    trial['axis_closure']['axis_candidate_verified'] is True
    and trial['axis_closure']['ambient_pressure_verified'] is False
    for trial in ambient_axis_shoot['trials']
  )
  ambient_axis_shoot_reference = ambient_strip[
    'ambient_axis_closure_shoot_reference'
  ]
  assert ambient_strip['ambient_axis_closure_shoot_reference_accepted'] is True
  assert ambient_axis_shoot_reference['status'] == (
    'converged_ambient_axis_pressure'
  )
  assert ambient_axis_shoot_reference['converged'] is True
  assert ambient_axis_shoot_reference['axis_pressure_closure_verified'] is True
  assert ambient_axis_shoot_reference['axis_boundary_verified'] is False
  assert ambient_axis_shoot_reference['physical_closure_verified'] is False
  assert ambient_axis_shoot_reference['chain_promotion_blocked'] is True
  assert ambient_axis_shoot_reference['trial_count'] >= 3
  assert abs(ambient_axis_shoot_reference['closure_residual']) <= 1.0e-8
  assert ambient_axis_shoot_reference['axis_closure']['axis_boundary_verified'] is False
  terminal_graph = first_cell_terminal['terminal_field']['terminal_boundary_graph']
  assert terminal_graph['status'] == 'converged_upstream_terminal_boundary_graph'
  assert terminal_graph['upstream_graph_closed'] is True
  assert terminal_graph['downstream_boundary_geometry_supplied'] is False
  assert terminal_graph['downstream_boundary_geometry_verified'] is False
  assert terminal_graph['physical_downstream_condition_supplied'] is False
  assert terminal_graph['physical_closure_verified'] is False
  assert terminal_graph['chain_promotion_blocked'] is True
  assert terminal_graph['maximum_upstream_join_residual_m'] <= 1.0e-10
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
  terminal_trace_polarity = ambient_strip[
    'terminal_reflection_patch_trace_polarity'
  ]
  terminal_trace_profile = ambient_strip[
    'terminal_reflection_patch_trace_profile'
  ]
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
  assert ambient_strip['terminal_reflection_patch_trace_profile_accepted'] is True
  assert terminal_trace_polarity['status'] == 'compression-required'
  assert terminal_trace_polarity['compression_sample_count'] == 16
  assert terminal_trace_polarity['expansion_sample_count'] == 0
  assert terminal_trace_profile['model'] == (
    'reflected-trace-referenced-compression-envelope'
  )
  assert terminal_trace_profile['canonical_expansion_remesh_solved'] is False
  assert terminal_trace_profile['production_claim_allowed'] is False
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
  _assert_chain_planner_measurement(
    terminal_patch_chain_probe['planner_measurement'],
    physical_termination=True,
  )
  terminal_patch_ambient_closure_chain = ambient_strip[
    'ambient_centerline_physical_terminal_patch_ambient_closure_chain'
  ]
  assert terminal_patch_ambient_closure_chain['chain']['cell_count'] == 3
  assert terminal_patch_ambient_closure_chain['step_count'] == 3
  assert terminal_patch_ambient_closure_chain['handoff_links_verified'] is True
  assert [
    step['result_kind']
    for step in terminal_patch_ambient_closure_chain['steps']
  ] == [
    'physical-field-solve-returned',
    'physical-field-solve-returned',
    'termination-returned',
  ]
  assert terminal_patch_ambient_closure_chain['diagnostics'][
    'terminal_reflection_patch_ambient_closure_chain_reference'
  ]['polarity_aware'] is True
  terminal_patch_field_chain_audit = ambient_strip[
    'ambient_centerline_physical_terminal_patch_field_chain_audit'
  ]
  assert ambient_strip[
    'ambient_centerline_physical_terminal_patch_field_chain_audit_accepted'
  ] is True
  assert terminal_patch_field_chain_audit['status'] == 'converged'
  assert terminal_patch_field_chain_audit['field_count'] == 3
  assert terminal_patch_field_chain_audit['audited_field_count'] == 3
  assert terminal_patch_field_chain_audit['handoff'] == {
    'link_count': 2,
    'links_verified': True,
  }
  assert terminal_patch_field_chain_audit['fresh_domain_verified'] is True
  assert terminal_patch_field_chain_audit['physical_closure_verified'] is True
  assert terminal_patch_field_chain_audit['chain_promotion_blocked'] is True
  assert terminal_patch_field_chain_audit['production_claim_allowed'] is False
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
  assert first_cell_terminal_planner_summary['accepted'] is True
  assert first_cell_terminal_planner_summary['status'] == 'prescribed-boundary-mock'
  assert first_cell_terminal_planner_summary['planner']['physical_termination'] is True
  first_cell_terminal_planner = ambient_strip['first_cell_terminal_closure_planner']
  assert first_cell_terminal_planner['planner_kind'] == 'prescribed-boundary-mock'
  assert first_cell_terminal_planner['planning_only'] is True
  assert first_cell_terminal_planner['production_claim_allowed'] is False
  assert first_cell_terminal_planner['resolved'] is True
  assert first_cell_terminal_planner['physical_closure_verified'] is True
  assert first_cell_terminal_planner['physical_termination'] is True
  assert first_cell_terminal_planner['chain_promotion_blocked'] is True
  assert first_cell_terminal_planner['termination']['physical_termination'] is True
  assert first_cell_terminal_planner['diagnostics']['mixed_regime_closure_attached'] is True
  assert first_cell_terminal_planner['diagnostics']['prescribed_mixed_regime_closure_mock']['production_claim_allowed'] is False
  assert first_cell_free_boundary_refinement['status'] == 'converged'
  assert first_cell_free_boundary_refinement['operator_id'] == (
    'op.moc.mixed-regime-free-boundary-refinement'
  )
  assert first_cell_free_boundary_refinement['resolutions'] == [5, 7, 9]
  assert first_cell_free_boundary_refinement['parameters']['perimeter_sample_counts'] == [8, 10, 12]
  assert all(first_cell_free_boundary_refinement['checks'].values())
  assert first_cell_free_boundary_refinement['physical_closure_verified'] is True
  assert first_cell_free_boundary_refinement['canonical_reflected_moc_closure_verified'] is False
  assert first_cell_free_boundary_refinement['chain_promotion_blocked'] is True
  assert first_cell_free_boundary_refinement['production_claim_allowed'] is False
  assert all(
    residual > 1.0
    for residual in first_cell_free_boundary_refinement['residuals'][
      'maximum_velocity_divergence_residuals'
    ]
  )
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
  caustic_shock_bridge = centerline_reflection_extension['caustic_shock_bridge']
  assert caustic_shock_bridge['status'] == (
    'diagnostic-invariant-conditioned-caustic-shock-bridge'
  )
  assert caustic_shock_bridge['accepted'] is True
  assert caustic_shock_bridge['bridge']['status'] == (
    'converged_local_caustic_shock_compatibility'
  )
  assert caustic_shock_bridge['bridge']['converged'] is True
  assert caustic_shock_bridge['bridge']['entropy_admissible'] is True
  assert caustic_shock_bridge['bridge']['invariant_residual'] is not None
  assert abs(caustic_shock_bridge['bridge']['invariant_residual']) <= 1.0e-10
  assert caustic_shock_bridge['bridge']['shock_curve_verified'] is False
  assert caustic_shock_bridge['bridge']['physical_closure_verified'] is False
  assert caustic_shock_bridge['bridge']['chain_promotion_blocked'] is True
  assert caustic_shock_bridge['remesh_preparation_accepted'] is True
  remesh_preparation = caustic_shock_bridge['remesh_preparation']
  assert remesh_preparation['status'] == (
    'ready_for_coupled_caustic_shock_remesh'
  )
  assert remesh_preparation['converged'] is True
  assert remesh_preparation['local_shock_state_ready'] is True
  assert remesh_preparation['shock_curve_verified'] is False
  assert remesh_preparation['downstream_field_verified'] is False
  assert remesh_preparation['physical_closure_verified'] is False
  assert remesh_preparation['chain_promotion_blocked'] is True
  assert remesh_preparation['request']['event_point_m'] == (
    caustic_seed['event']['caustic_point_m']
  )
  assert remesh_preparation['request']['required_outputs'] == [
    'shock_boundary_points_m',
    'shock_boundary_upstream_states',
    'shock_boundary_downstream_states',
    'shock_boundary_total_pressure_loss',
    'post_shock_characteristic_field',
    'exact_incoming_handoff',
  ]
  assert remesh_preparation['chain_termination_decision']['reason'] == (
    'characteristic-caustic'
  )
  assert remesh_preparation['chain_termination_decision']['physical_termination'] is False
  origin_envelope = centerline_reflection_extension[
    'caustic_family_band_origin_envelope'
  ]
  assert origin_envelope['status'] == (
    'diagnostic-caustic-origin-forward-envelope'
  )
  assert origin_envelope['accepted'] is True
  assert len(origin_envelope['cases']) == 2
  assert all(
    case['accepted'] is True
    and case['envelope']['status'] == (
      'caustic_forward_envelope_centerline_unreachable'
    )
    and case['envelope']['converged'] is False
    and case['envelope']['physical_closure_verified'] is False
    and case['envelope']['chain_promotion_blocked'] is True
    and case['envelope']['first_missing_sample_index'] == case['envelope']['sample_count']
    and case['envelope']['minimum_lower_boundary_margin_m'] < 0.0
    and case['envelope']['chain_termination_decision']['reason'] == (
      'characteristic-caustic'
    )
    for case in origin_envelope['cases']
  )
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
  band_chain_planner = centerline_reflection_extension[
    'caustic_family_band_chain_planner'
  ]
  assert band_chain_planner['status'] == 'diagnostic-caustic-band-next-shock-planner'
  assert band_chain_planner['accepted'] is True
  assert len(band_chain_planner['cases']) == 2
  assert all(
    case['accepted'] is True
    and case['planner_measurement']['physical_termination'] is False
    for case in band_chain_planner['cases']
  )
  for case in band_chain_planner['cases']:
    _assert_chain_planner_measurement(
      case['planner_measurement'],
      physical_termination=False,
    )
  invariant_chain = centerline_reflection_extension[
    'caustic_family_band_invariant_chain'
  ]
  assert invariant_chain['status'] == 'diagnostic-invariant-caustic-band-chain'
  assert invariant_chain['accepted'] is True
  assert invariant_chain['direct']['status'] == (
    'invariant_caustic_band_upstream_domain_failure'
  )
  assert invariant_chain['direct']['first_missing_sample_index'] == 4
  assert invariant_chain['direct']['shock']['status'] == 'upstream_field_failure'
  assert invariant_chain['direct']['shock']['sample_count'] == 4
  assert invariant_chain['direct']['shock_curve_verified'] is False
  assert invariant_chain['direct']['physical_closure_verified'] is False
  assert invariant_chain['direct']['chain_promotion_blocked'] is True
  assert invariant_chain['planner']['planner_kind'] == 'upstream-coupled-research'
  assert invariant_chain['planner']['planning_only'] is True
  assert invariant_chain['planner']['production_claim_allowed'] is False
  assert invariant_chain['planner']['chain']['status'] == 'solver-terminated'
  assert invariant_chain['planner']['chain']['termination_reason'] == (
    'upstream-field-boundary'
  )
  assert invariant_chain['planner']['chain']['diagnostics'][
    'first_missing_sample_index'
  ] == 4
  assert invariant_chain['planner']['steps'][0]['incoming_handoff_sample_count'] >= 3
  _assert_chain_planner_measurement(
    invariant_chain['planner_measurement'],
    physical_termination=False,
  )
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
  assert planner['planner_step_count'] == 5
  assert planner['handoff_links_verified'] is True
  assert planner['geometry_schedule_model'] == 'explicit-per-cell-schedule'
  assert planner['cell_axial_lengths_m'] == pytest.approx((0.46, 0.50, 0.54, 0.58))
  assert planner['shock_start_offsets_m'] == pytest.approx((0.16, 0.18, 0.20, 0.22))
  assert planner['shock_geometry_scales_per_cell'] == pytest.approx((1.00, 1.05, 1.10, 1.15))
  assert [entry['cell_index'] for entry in planner['per_cell_geometry_schedule']] == [2, 3, 4, 5]
  assert [entry['axial_length_m'] for entry in planner['per_cell_geometry_schedule']] == pytest.approx(
    (0.46, 0.50, 0.54, 0.58)
  )
  assert [step['next_cell_index'] for step in planner['planner_steps']] == [2, 3, 4, 5, 6]
  assert all(
    step['boundary_kind'] == 'post-shock-field-perimeter'
    and step['incoming_handoff_sample_count'] >= 3
    and step['result_kind'] in ('field-solve-returned', 'termination-returned')
    for step in planner['planner_steps']
  )
  assert [step['result_kind'] for step in planner['planner_steps']] == [
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'termination-returned',
  ]
  assert [step['result_status'] for step in planner['planner_steps']] == [
    'converged_closed',
    'converged_closed',
    'converged_closed',
    'converged_closed',
    'solver-returned-no-next-cell',
  ]
  assert all(
    step['result_handoff_sample_count'] >= 3
    and step['result_handoff_fingerprint']
    for step in planner['planner_steps'][:4]
  )
  assert all(
    step['result_consumed_handoff_sample_count'] >= 3
    and step['result_consumed_total_pressure_range_Pa']
    and step['result_consumed_handoff_fingerprint']
    for step in planner['planner_steps'][:4]
  )
  assert all(
    step['incoming_handoff_link_verified'] is True
    for step in planner['planner_steps'][1:]
  )
  assert planner['cell_count'] == 5
  assert planner['state_carry_count'] == 5
  assert planner['continuation_boundary_kinds'] == ['post-shock-field-perimeter']
  assert planner['measurement_operator']['handoff']['link_count'] == 4
  assert planner['measurement_operator']['handoff']['links_verified'] is True
  planner_measurement = planner['planner_measurement']
  assert planner_measurement['status'] == 'converged'
  assert planner_measurement['operator_id'] == 'op.moc.chain-planner'
  assert planner_measurement['counts'] == {
    'steps': 5,
    'chain_cells': 5,
    'handoff_links': 4,
  }
  assert all(planner_measurement['checks'].values())
  assert planner_measurement['physical_termination'] is False
  assert planner_measurement['production_claim_allowed'] is False
  assert planner_measurement['claim_status'] == (
    'independent-planner-trace-audit; not-accepted'
  )
  assert len(planner['terminal_trace_validation']) == 5
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
  assert invariant_closure['source_extension']['last_converged_strip']['converged'] is True
  assert invariant_closure['source_extension']['last_converged_strip']['source_window_count'] == 191
  assert invariant_closure['source_extension']['frontier']['status'] == (
    'converged_source_frontier_probe'
  )
  assert invariant_closure['source_extension']['remesh']['status'] == (
    'caustic_requires_new_characteristic_family'
  )
  assert invariant_closure['source_extension']['remesh']['chain_termination_decision']['physical_termination'] is False
  assert invariant_closure['claim_status'].startswith('domain-bounded-invariant-shooting-attempt')
  assert report['failures'] == []
  ####
