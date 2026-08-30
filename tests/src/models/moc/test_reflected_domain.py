from __future__ import annotations

from dataclasses import replace
from math import cos, sin

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientPhysicalFieldResult,
  MocAmbientPhysicalFieldStatus,
  MocBoundedUpstreamFieldSource,
  MocChainBoundarySample,
  MocChainContinuationPolicy,
  MocChainTerminationReason,
  MocPostShockChainCellSolve,
  MocReflectedDomainRemeshRequest,
  MocReflectedDomainAlternatingSourceStatus,
  MocReflectedDomainAlternatingPhysicalFieldStatus,
  MocReflectedDomainSolverOwnedFirstCellStatus,
  MocReflectedDomainGlobalShockRemeshStatus,
  MocReflectedDomainGlobalEulerShockBoundaryStatus,
  MocReflectedDomainOuterSourceStatus,
  MocReflectedDomainRemeshStatus,
  MocSolverGeneratedAmbientClosedPostShockChainReference,
  MocSourceStripContinuationStatus,
  MocTerminalReflectionPatchAmbientClosureChainReference,
  assemble_terminal_trace_centerline_patch,
  build_reflected_domain_remesh_request_from_outer_source,
  inverse_prandtl_meyer_angle_rad,
  plan_reflected_domain_remesh_ambient_closed_chain,
  plan_reflected_domain_alternating_source_chain,
  plan_reflected_domain_alternating_source_chain_from_physical_field,
  plan_reflected_domain_alternating_source_chain_sequence,
  plan_reflected_domain_solver_owned_first_cell_chain,
  plan_reflected_domain_global_shock_remesh_chain,
  plan_reflected_domain_global_shock_remesh_chain_from_physical_field,
  plan_reflected_domain_remesh_shock_chain,
  plan_reflected_domain_remesh_shock_chain_sequence,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_reflected_domain_remesh,
  solve_reflected_domain_alternating_source,
  solve_reflected_domain_alternating_physical_field,
  solve_reflected_domain_solver_owned_first_cell,
  solve_reflected_domain_global_shock_remesh,
  solve_reflected_domain_global_euler_shock_boundary,
  solve_reflected_domain_outer_source_curve,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.models.moc import solve_reflected_free_boundary
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.validation.moc_measurements import (
  MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase,
  MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus,
  MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus,
  MocReflectedDomainAlternatingSourceMeasurementStatus,
  MocReflectedDomainSolverOwnedFirstCellMeasurementStatus,
  MocReflectedDomainGlobalShockRemeshMeasurementStatus,
  MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus,
  MocReflectedDomainOuterSourceMeasurementStatus,
  MocReflectedDomainRemeshMeasurementStatus,
  measure_moc_reflected_domain_alternating_source,
  measure_moc_reflected_domain_alternating_physical_field_chain_refinement,
  measure_moc_reflected_domain_alternating_physical_field_chain,
  measure_moc_reflected_domain_alternating_physical_field,
  measure_moc_reflected_domain_solver_owned_first_cell,
  measure_moc_reflected_domain_global_shock_remesh,
  measure_moc_reflected_domain_global_euler_shock_boundary,
  measure_moc_reflected_domain_outer_source_curve,
  measure_moc_reflected_domain_remesh,
)


def _canonical_field():
  upstream = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )
  shock = solve_marched_attached_shock_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  result = solve_marched_attached_shock_with_ambient_centerline_physical_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.02,
    0.12,
    sample_count=9,
  )
  assert result.field is not None
  assert result.field.physical_closure_verified
  return result.field


def _patch():
  field = _canonical_field()
  patch = assemble_terminal_trace_centerline_patch(
    field.as_open_shock_ambient_strip()
  )
  assert patch.converged
  return field, patch


def _request(*, declared_polarity=None, incoming_handoff=()):
  field, patch = _patch()
  anchor = patch.outgoing_trace_states[-1]
  total_pressure = patch.outgoing_trace_total_pressure_Pa[-1]
  centerline = []
  outer = []
  for index in range(6):
    k_plus = anchor.k_plus - 0.002 * index
    inversion = inverse_prandtl_meyer_angle_rad(-k_plus, anchor.gamma)
    assert inversion.value is not None
    axis_x = anchor.x_m + 0.015 * index
    axis_state = CharacteristicState(
      x_m=axis_x,
      y_m=0.0,
      theta_rad=0.0,
      mach=inversion.value,
      gamma=anchor.gamma,
    )
    theta = 0.06 - 0.004 * index
    outer_inversion = inverse_prandtl_meyer_angle_rad(
      theta - k_plus,
      anchor.gamma,
    )
    assert outer_inversion.value is not None
    outer_probe = CharacteristicState(
      x_m=axis_x,
      y_m=0.0,
      theta_rad=theta,
      mach=outer_inversion.value,
      gamma=anchor.gamma,
    )
    characteristic_angle = 0.5 * (
      axis_state.mu_rad
      + outer_probe.theta_rad
      + outer_probe.mu_rad
    )
    ordinate = 0.10 + 0.012 * index
    outer.append(
      CharacteristicState(
        x_m=axis_x + ordinate * cos(characteristic_angle) / sin(
          characteristic_angle
        ),
        y_m=ordinate,
        theta_rad=theta,
        mach=outer_inversion.value,
        gamma=anchor.gamma,
      )
    )
    centerline.append(axis_state)
  request = MocReflectedDomainRemeshRequest(
    reflection_patch=patch,
    centerline_source_states=tuple(centerline),
    outer_source_states=tuple(outer),
    total_pressure_Pa=total_pressure,
    incoming_handoff=tuple(incoming_handoff),
    declared_polarity=declared_polarity,
  )
  return field, patch, request


def _outer_source_fixture() -> tuple[NozzleExitState, AmbientState, object]:
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(
    exit_state,
    ambient,
    characteristic_count=8,
  )
  reflected = solve_reflected_free_boundary(fan, exit_state, ambient)
  assert reflected.converged
  return exit_state, ambient, reflected


def _handoff(field):
  return tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )


def _alternating_physical_chain_results(seed, sample_count):
  current = seed
  results = []
  for _ in range(2):
    strip = current.as_open_shock_ambient_strip(
      trace_position_tolerance_m=3.0e-3,
      trace_forward_tolerance_m=1.0e-4,
    )
    patch = assemble_terminal_trace_centerline_patch(
      strip,
      trace_position_tolerance_m=3.0e-3,
      trace_forward_tolerance_m=1.0e-4,
    )
    assert patch.converged
    ambient_pressure = current.ambient_boundary.ambient_pressure_Pa
    assert ambient_pressure is not None
    handoff = _handoff(current)
    source = solve_reflected_domain_alternating_source(
      patch,
      ambient_pressure,
      incoming_handoff=handoff,
    )
    assert source.converged
    result = solve_reflected_domain_alternating_physical_field(
      source,
      compression_amplitude_rad=0.05,
      use_outer_seed_attachment=True,
      sample_count=sample_count,
      shock_angle_tolerance_rad=0.02,
      incoming_handoff=handoff,
    )
    assert result.converged
    assert result.field is not None
    results.append(result)
    current = result.field
  return tuple(results)


def _reference_seed_field():
  result = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert result.field is not None
  return result.field


def test_reflected_domain_remesh_uses_a_new_outer_curve_after_the_single_c_minus_front():
  _field, patch, request = _request()

  result = solve_reflected_domain_remesh(request)

  assert result.status is MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD
  assert result.converged
  assert result.state_sampling_available
  assert result.incoming_trace_validation is not None
  assert result.incoming_trace_validation.converged
  assert result.incoming_trace_polarity is not None
  assert result.incoming_trace_polarity.converged
  assert result.reflection_seam_verified
  assert result.centerline_source_verified
  assert result.outer_source_verified
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.topology.forms_closed_zone
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  continuation = result.as_source_continuation()
  assert continuation.status is MocSourceStripContinuationStatus.CONVERGED_EXTENDED
  assert continuation.strip is result.source_strip
  report = result.as_report()
  assert report['request']['incoming_trace_reused_as_outer_source'] is False
  assert report['request']['outer_source_is_new_curve'] is True
  assert report['request']['incoming_trace_family'] == 'C-'
  assert report['request']['centerline_source_family'] == 'C+'
  assert report['chain_termination_decision']['reason'] == (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
  )
  assert patch.outgoing_trace_states[-1].y_m == pytest.approx(0.0)


def test_reflected_domain_remesh_rejects_reusing_the_single_c_minus_front_as_a_curve():
  _field, patch, request = _request()
  reused = patch.outgoing_trace_states[:6]
  changed = replace(
    request,
    outer_source_states=reused,
    centerline_source_states=request.centerline_source_states,
  )

  result = solve_reflected_domain_remesh(changed)

  assert result.status is MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE
  assert result.state_sampling_available is False
  assert 'single C- front cannot be reused' in result.message
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  )


def test_reflected_domain_remesh_measurement_rechecks_raw_bounded_field_data():
  _field, _patch, request = _request()
  remesh = solve_reflected_domain_remesh(request)
  assert remesh.converged

  tampered = replace(
    remesh,
    reflection_seam_verified=False,
    centerline_source_verified=False,
    outer_source_verified=False,
    source_field_verified=False,
  )
  measurement = measure_moc_reflected_domain_remesh(tampered)

  assert measurement.status is MocReflectedDomainRemeshMeasurementStatus.CONVERGED
  assert measurement.bounded_remesh_verified
  assert measurement.incoming_trace_verified
  assert measurement.polarity_verified
  assert measurement.reflection_seam_verified
  assert measurement.centerline_source_verified
  assert measurement.outer_source_verified
  assert measurement.total_pressure_verified
  assert measurement.source_topology_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_reflected_domain_remesh_measurement_preserves_single_front_rejection():
  _field, patch, request = _request()
  reused = solve_reflected_domain_remesh(
    replace(
      request,
      outer_source_states=patch.outgoing_trace_states[:6],
    )
  )

  measurement = measure_moc_reflected_domain_remesh(reused)

  assert measurement.status is MocReflectedDomainRemeshMeasurementStatus.SOURCE_FAILURE
  assert measurement.converged is False
  assert measurement.outer_source_verified is False
  assert measurement.bounded_remesh_verified is False


def test_reflected_domain_remesh_rejects_a_wrong_reflection_anchor():
  _field, _patch, request = _request()
  changed_centerline = (
    replace(request.centerline_source_states[0], x_m=1.0),
    *request.centerline_source_states[1:],
  )

  result = solve_reflected_domain_remesh(
    replace(request, centerline_source_states=changed_centerline)
  )

  assert result.status is MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE
  assert result.reflection_seam_verified is False
  assert result.chain_promotion_blocked


def test_reflected_domain_remesh_records_observed_polarity_without_promoting_it():
  _field, _patch, first = _request()
  observed = solve_reflected_domain_remesh(first).incoming_trace_polarity
  assert observed is not None
  _field, _patch, request = _request(declared_polarity=observed.status)

  result = solve_reflected_domain_remesh(request)

  assert result.converged
  assert result.incoming_trace_polarity is not None
  assert result.incoming_trace_polarity.status is observed.status
  assert result.as_report()['request']['declared_polarity'] == observed.status.value


def test_reflected_domain_remesh_exposes_a_bounded_physical_solver_source():
  _field, _patch, request = _request()
  remesh = solve_reflected_domain_remesh(request)

  source = MocBoundedUpstreamFieldSource.from_reflected_domain_remesh(remesh)

  assert source.model == 'bounded-reflected-domain-cauchy-remesh'
  assert source.preferred_start_point_m == pytest.approx(
    (
      request.outer_source_states[0].x_m,
      request.outer_source_states[0].y_m,
    )
  )
  assert source.domain_x_extent_m is not None
  assert source.domain_y_extent_m is not None
  start = source.preferred_start_point_m
  assert start is not None
  state = source.state_at(start)
  pressure = source.static_pressure_at(start)
  assert state is not None
  assert state.x_m == pytest.approx(start[0])
  assert state.y_m == pytest.approx(start[1])
  assert pressure is not None
  assert pressure > 0.0
  assert source.state_at(
    (
      source.domain_x_extent_m[1] + 0.1,
      source.domain_y_extent_m[1] + 0.1,
    )
  ) is None
  report = source.as_report()
  assert report['extrapolation_allowed'] is False
  assert report['upstream_coupling_verified'] is False


def test_reflected_domain_remesh_carries_source_family_total_pressure():
  _field, _patch, request = _request()
  total_pressure = request.total_pressure_Pa
  centerline_pressures = tuple(
    total_pressure * (1.0 - 0.002 * index)
    for index in range(len(request.centerline_source_states))
  )
  outer_pressures = tuple(
    total_pressure * (0.99 - 0.0015 * index)
    for index in range(len(request.outer_source_states))
  )
  variable_request = replace(
    request,
    centerline_total_pressure_Pa=centerline_pressures,
    outer_total_pressure_Pa=outer_pressures,
  )

  result = solve_reflected_domain_remesh(variable_request)

  assert result.converged
  assert result.source_strip is not None
  assert variable_request.variable_total_pressure
  assert result.source_strip.total_pressure_model == 'source-family-carried-total-pressure'
  assert result.source_strip.total_pressure_at(
    (
      variable_request.outer_source_states[3].x_m,
      variable_request.outer_source_states[3].y_m,
    )
  ) == pytest.approx(outer_pressures[3])
  assert all(
    node.total_pressure_Pa == pytest.approx(
      outer_pressures[node.boundary_index]
    )
    for node in result.source_strip.nodes
  )
  report = result.as_report()
  assert report['request']['variable_total_pressure'] is True
  assert report['request']['nonuniform_entropy_data_carried'] is True
  assert report['request']['nonuniform_entropy_remesh_solved'] is False
  assert report['physical_closure_verified'] is False
  measurement = measure_moc_reflected_domain_remesh(result)
  assert measurement.converged
  assert measurement.total_pressure_verified
  assert measurement.source_sampling_verified
  assert measurement.production_claim_allowed is False


def test_reflected_domain_outer_source_curve_is_solved_and_assembled():
  exit_state, ambient, reflected = _outer_source_fixture()

  result = solve_reflected_domain_outer_source_curve(
    reflected.centerline_states,
    reflected.boundary_states[0],
    ambient.pressure_Pa,
    exit_state.total_pressure_Pa,
  )

  assert result.status is MocReflectedDomainOuterSourceStatus.CONVERGED
  assert result.converged
  assert result.outer_source_curve_verified
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.total_pressure_model == (
    'uniform-isentropic-source-strip'
  )
  assert len(result.point_results) == len(reflected.centerline_states) - 1
  assert all(point.converged for point in result.point_results)
  assert result.ambient_boundary is not None
  assert result.ambient_boundary.converged
  assert tuple(result.outer_source_states[1:]) == pytest.approx(
    reflected.boundary_states[1:]
  )
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  report = result.as_report()
  assert report['source_model'] == (
    'solver-owned-ambient-pressure-outer-source-march'
  )
  assert report['outer_source_curve_verified'] is True
  assert report['source_field_verified'] is True
  assert report['physical_closure_verified'] is False
  measurement = measure_moc_reflected_domain_outer_source_curve(result)
  assert measurement.status is MocReflectedDomainOuterSourceMeasurementStatus.CONVERGED
  assert measurement.bounded_source_verified
  assert measurement.ambient_boundary_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_reflected_domain_alternating_source_band_closes_local_neighbor_seams():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None

  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  assert result.status is MocReflectedDomainAlternatingSourceStatus.CONVERGED
  assert result.converged
  assert result.source_field_verified
  assert result.reflection_anchor_verified
  assert result.alternating_seam_verified
  assert len(result.centerline_source_states) == 6
  assert len(result.outer_source_states) == 6
  assert len(result.centerline_results) == 6
  assert len(result.point_results) == 6
  assert all(item.converged for item in result.centerline_results)
  assert all(item.converged for item in result.point_results)
  assert result.node_count == 12
  assert result.cell_count == 10
  assert result.topology is not None
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.centerline_source_states[0] == pytest.approx(
    patch.outgoing_trace_states[-1]
  )
  assert result.outer_seed_state == patch.outgoing_trace_states[0]
  assert result.outer_source_states[0].x_m > result.centerline_source_states[0].x_m
  sample = result.state_at((2.2, 0.1))
  assert sample is not None
  assert result.total_pressure_at((2.2, 0.1)) == pytest.approx(
    patch.outgoing_trace_total_pressure_Pa[0]
  )
  assert result.state_at((1.0, -0.1)) is None
  report = result.as_report()
  assert report['source_model'] == (
    'solver-owned-alternating-family-ambient-pressure-remesh'
  )
  assert report['canonical_alternating_remesh_solved'] is False
  assert report['physical_closure_verified'] is False
  assert report['chain_promotion_blocked'] is True
  assert report['production_claim_allowed'] is False
  measurement = measure_moc_reflected_domain_alternating_source(result)
  assert measurement.status is (
    MocReflectedDomainAlternatingSourceMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.bounded_source_verified
  assert measurement.incoming_trace_verified
  assert measurement.reflection_anchor_verified
  assert measurement.centerline_recomputed_verified
  assert measurement.boundary_recomputed_verified
  assert measurement.alternating_seam_verified
  assert measurement.source_topology_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False


def test_reflected_domain_alternating_source_measurement_rejects_changed_raw_row():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  corrupted = replace(
    result,
    outer_source_states=(
      replace(result.outer_source_states[0], y_m=0.45),
      *result.outer_source_states[1:],
    ),
  )

  measurement = measure_moc_reflected_domain_alternating_source(corrupted)

  assert measurement.converged is False
  assert measurement.bounded_source_verified is False
  assert measurement.boundary_recomputed_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked is True


def test_reflected_domain_alternating_source_couples_to_physical_shock_field():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
  )

  assert result.status is (
    MocReflectedDomainAlternatingPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
  )
  assert result.converged
  assert result.source_field_verified
  assert result.shock_curve_verified
  assert result.physical_closure_verified
  assert result.state_sampling_available
  assert result.upstream_coupling_verified
  assert result.chain_promotion_blocked is False
  assert result.production_claim_allowed is False
  assert result.field is not None
  assert result.field.shock_boundary_points_m[0][0] == pytest.approx(
    source.outer_source_states[0].x_m,
  )
  assert result.field.shock_boundary_points_m[0][1] == pytest.approx(
    source.outer_source_states[0].y_m,
  )
  assert result.field.shock_boundary_points_m[-1][1] == pytest.approx(0.0)
  assert result.field.physical_closure_verified
  report = result.as_report()
  assert report['continuation_law'] == (
    'alternating-source-local-compression-envelope'
  )
  assert report['canonical_reflected_domain_closed'] is False
  assert report['production_claim_allowed'] is False

  measurement = measure_moc_reflected_domain_alternating_physical_field(result)

  assert measurement.converged
  assert measurement.source_field_verified
  assert measurement.attachment_point_verified
  assert measurement.attachment_pressure_verified
  assert measurement.zero_strength_attachment_verified
  assert measurement.envelope_verified
  assert measurement.shock_curve_verified
  assert measurement.physical_field_verified
  assert measurement.state_sampling_verified
  assert measurement.upstream_coupling_verified
  assert measurement.incoming_handoff_verified
  assert measurement.bounded_physical_field_verified
  assert measurement.physical_closure_verified
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False


def test_reflected_domain_alternating_physical_field_can_attach_at_retained_outer_seed():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
    use_outer_seed_attachment=True,
    use_trace_referenced_profile=True,
  )

  assert result.status is (
    MocReflectedDomainAlternatingPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
  )
  assert result.converged
  assert result.field is not None
  assert result.start_point_m == pytest.approx(
    (source.outer_seed_state.x_m, source.outer_seed_state.y_m),
  )
  assert result.field.shock_boundary_points_m[0] == pytest.approx(
    result.start_point_m,
  )
  assert result.as_report()['attachment_source'] == (
    'outer-seed-reflection-interface'
  )
  assert result.as_report()['use_trace_referenced_profile'] is True
  assert result.continuation_law == (
    'reflected-trace-referenced-compression-envelope'
  )
  measurement = measure_moc_reflected_domain_alternating_physical_field(result)
  assert measurement.converged
  assert measurement.attachment_point_verified
  assert measurement.upstream_coupling_verified


def test_reflected_domain_alternating_source_chain_projects_fresh_bands_automatically():
  seed = _canonical_field()

  planner = plan_reflected_domain_alternating_source_chain_from_physical_field(
    seed,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 4
  assert planner.chain.termination_reason is MocChainTerminationReason.MAX_CELL_LIMIT
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['source_derivation_automatic'] is True
  assert planner.diagnostics['use_outer_seed_attachment'] is True
  assert planner.diagnostics[
    'alternating_physical_field_chain_audit_accepted'
  ] is True
  assert planner.diagnostics['alternating_physical_field_chain_audit']['checks'] == {
    'source_geometry_freshness_verified': True,
    'handoff_links_verified': True,
    'fresh_domain_verified': True,
    'physical_closure_verified': True,
  }
  attempts = planner.diagnostics['alternating_source_attempts']
  assert len(attempts) == 3
  assert all(
    attempt['incoming_handoff_verified'] is True
    and attempt['fresh_source_band'] is True
    and attempt['fresh_source_geometry'] is True
    for attempt in attempts
  )


def test_reflected_domain_alternating_source_chain_one_cell_prefix_skips_source_projection():
  seed = _canonical_field()

  planner = plan_reflected_domain_alternating_source_chain_from_physical_field(
    seed,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    total_cell_count=1,
    policy=MocChainContinuationPolicy(max_cells=1, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.chain.physical_termination is False
  assert planner.diagnostics['configured_total_cell_count'] == 1
  assert planner.diagnostics['alternating_source_initial_band'] is None
  assert planner.diagnostics['alternating_source_attempt_count'] == 0
  assert planner.diagnostics['alternating_source_attempts'] == []
  assert planner.production_claim_allowed is False


def test_solver_owned_first_cell_retains_auditable_no_bracket_without_geometry():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_solver_owned_first_cell(
    source,
    outer_source_index=2,
    target_centerline_index=3,
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    sample_count=9,
  )

  assert result.status is (
    MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE
  )
  assert result.converged is False
  assert len(result.trials) == 2
  assert all(trial.physical_field is not None for trial in result.trials)
  assert all(trial.converged for trial in result.trials)
  assert result.selected_physical_field is not None
  assert result.local_physical_field_verified
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False

  measurement = measure_moc_reflected_domain_solver_owned_first_cell(result)

  assert measurement.status is (
    MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.target_centerline_verified
  assert measurement.amplitude_bracket_verified
  assert measurement.trial_amplitudes_verified
  assert measurement.trial_residuals_verified
  assert measurement.selected_trial_verified
  assert measurement.selected_field_verified
  assert measurement.scalar_endpoint_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.canonical_free_boundary_verified is False
  assert measurement.canonical_euler_verified is False
  assert measurement.external_validation_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.fidelity_isolation_verified

  invalid = solve_reflected_domain_solver_owned_first_cell(
    source,
    compression_amplitude_lower_rad=float('nan'),
    compression_amplitude_upper_rad=0.03,
  )
  assert invalid.status is MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT
  assert invalid.compression_amplitude_bracket is None


def test_solver_owned_first_cell_can_scan_only_inside_declared_bracket():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_solver_owned_first_cell(
    source,
    outer_source_index=2,
    target_centerline_index=3,
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    sample_count=9,
    maximum_bracket_scan_samples=3,
  )

  assert result.status is (
    MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE
  )
  assert result.bracket_scan_sample_count == 3
  assert len(result.trials) == 5
  assert all(
    0.007 <= trial.compression_amplitude_rad <= 0.03
    for trial in result.trials
  )
  measurement = measure_moc_reflected_domain_solver_owned_first_cell(result)
  assert measurement.converged
  assert measurement.trial_amplitudes_verified
  assert measurement.trial_residuals_verified
  assert measurement.fidelity_isolation_verified


def test_solver_owned_first_cell_planner_preserves_typed_research_stop():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  handoff = _handoff(field)
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=handoff,
  )
  planner = plan_reflected_domain_solver_owned_first_cell_chain(
    field,
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    outer_source_index=2,
    target_centerline_index=3,
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )
  assert planner.chain.physical_termination is False
  assert planner.handoff_links_verified is None
  assert planner.diagnostics[
    'solver_owned_first_cell_seed_handoff_verified'
  ] is True
  assert planner.diagnostics['solver_owned_first_cell_audit_accepted'] is True
  assert planner.diagnostics['solver_owned_first_cell']['status'] == (
    'solver_owned_first_cell_boundary_bracket_failure'
  )
  assert planner.diagnostics[
    'solver_owned_first_cell_independent_measurement'
  ]['status'] == 'converged'
  assert planner.production_claim_allowed is False


def test_solver_owned_first_cell_planner_rejects_mismatched_seed_handoff():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  planner = plan_reflected_domain_solver_owned_first_cell_chain(
    field,
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.STATE_NOT_CARRIED
  )
  assert planner.diagnostics[
    'solver_owned_first_cell_seed_handoff_verified'
  ] is False
  assert planner.diagnostics['solver_owned_first_cell'] is None
  assert planner.diagnostics[
    'solver_owned_first_cell_independent_measurement'
  ] is None


def test_global_reflected_shock_remesh_retains_bounded_profile_sweep_without_closure():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  assert result.status is MocReflectedDomainGlobalShockRemeshStatus.NO_ENDPOINT_CLOSURE
  assert result.attempt_count == 2
  assert result.selected_attempt_index is not None
  assert result.selected_residual_m is not None
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )

  measurement = measure_moc_reflected_domain_global_shock_remesh(result)

  assert measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.attempt_count == 2
  assert measurement.source_field_verified
  assert measurement.attempt_identity_verified
  assert measurement.attempt_shape_verified
  assert measurement.attempt_residuals_verified
  assert measurement.selected_attempt_verified
  assert measurement.global_endpoint_verified is False
  assert measurement.no_endpoint_closure_verified
  assert measurement.physical_closure_verified is False
  assert measurement.fidelity_isolation_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False

  tampered_attempt = replace(
    result.attempts[0],
    compression_envelope_skew=0.25,
  )
  tampered = replace(
    result,
    attempts=(tampered_attempt, *result.attempts[1:]),
  )
  tampered_measurement = measure_moc_reflected_domain_global_shock_remesh(
    tampered,
  )
  assert tampered_measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.ATTEMPT_FAILURE
  )
  assert tampered_measurement.attempt_identity_verified is False


def test_global_euler_shock_boundary_closes_continuous_source_frontier():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  global_result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  result = solve_reflected_domain_global_euler_shock_boundary(global_result)

  assert result.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert result.source_frontier_verified
  assert result.selected_attempt_index == global_result.selected_attempt_index
  assert result.outer_source_index == 2
  assert result.target_centerline_index == 3
  assert result.source_frontier_state is not None
  assert result.source_frontier_state.y_m == pytest.approx(
    source.target_centerline_y_m,
  )
  assert result.source_frontier_state.theta_rad == pytest.approx(
    source.target_centerline_flow_angle_rad,
  )
  centerline_xs = tuple(
    state.x_m for state in source.centerline_source_states
  )
  assert centerline_xs[2] < result.source_frontier_state.x_m < centerline_xs[3]
  assert result.initial_shock_points_m != result.remeshed_shock_points_m
  assert result.first_endpoint_tangent_residual_rad == pytest.approx(0.0)
  assert result.last_endpoint_tangent_residual_rad == pytest.approx(0.0)
  assert result.shock_boundary is not None
  assert result.shock_boundary.converged
  assert result.shock_boundary.local_euler_verified
  assert result.shock_boundary.orientation.value == 'mixed-characteristic-boundary'
  assert result.shock_boundary.zero_strength_endpoints_allowed
  assert result.physical_field is not None
  assert result.physical_field.converged
  assert result.physical_field.physical_closure_verified
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )

  measurement = measure_moc_reflected_domain_global_euler_shock_boundary(result)
  assert measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.local_euler_consistency_verified
  assert measurement.source_frontier_verified
  assert measurement.endpoint_tangents_verified
  assert measurement.upstream_sampling_verified
  assert measurement.ambient_boundary_verified
  assert measurement.physical_closure_verified
  assert measurement.fidelity_isolation_verified

  tampered = replace(result, first_endpoint_tangent_residual_rad=0.25)
  tampered_measurement = (
    measure_moc_reflected_domain_global_euler_shock_boundary(tampered)
  )
  assert tampered_measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.GEOMETRY_FAILURE
  )
  assert tampered_measurement.endpoint_tangents_verified is False
  assert tampered_measurement.converged is False

  report = result.as_report()
  assert report['source_frontier_verified'] is True
  assert report['shock_boundary']['zero_strength_endpoints_allowed'] is True
  assert report['physical_field']['physical_closure_verified'] is True


def test_global_euler_shock_boundary_rejects_invalid_tolerance_as_typed_result():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)
  global_result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(0.0,),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  result = solve_reflected_domain_global_euler_shock_boundary(
    global_result,
    pressure_tolerance=0.0,
  )

  assert result.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT
  assert result.converged is False
  assert result.global_remesh is global_result
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.INVALID_INPUT
  )


def test_global_reflected_shock_remesh_rejects_duplicate_profile_shapes():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(0,),
    target_centerline_indices=(1,),
    compression_envelope_skews=(0.0, 0.0),
  )

  assert result.status is MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT
  assert result.attempts == ()
  measurement = measure_moc_reflected_domain_global_shock_remesh(result)
  assert measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.INVALID_INPUT
  )
  assert measurement.converged is False


def test_global_reflected_shock_remesh_retains_invalid_attempts_without_bridging_them():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0, 0.75),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  assert result.status is MocReflectedDomainGlobalShockRemeshStatus.ATTEMPT_FAILURE
  assert result.attempt_count == 3
  assert result.selected_attempt_index is not None
  assert any(
    attempt.first_cell_result.status is MocReflectedDomainSolverOwnedFirstCellStatus.FIELD_FAILURE
    for attempt in result.attempts
  )
  measurement = measure_moc_reflected_domain_global_shock_remesh(result)
  assert measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.ATTEMPT_FAILURE
  )
  assert measurement.attempt_identity_verified
  assert measurement.attempt_shape_verified is False
  assert measurement.no_endpoint_closure_verified is False
  assert measurement.chain_promotion_blocked


def test_global_reflected_shock_remesh_planner_preserves_research_stop():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  handoff = _handoff(field)
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=handoff,
  )
  planner = plan_reflected_domain_global_shock_remesh_chain(
    field,
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  assert planner.chain.physical_termination is False
  assert planner.diagnostics[
    'global_reflected_shock_remesh_seed_handoff_verified'
  ] is True
  assert planner.diagnostics['global_reflected_shock_remesh_audit_accepted'] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_audit_accepted'
  ] is False
  euler_audits = planner.diagnostics[
    'global_reflected_shock_remesh_euler_audits'
  ]
  assert len(euler_audits) == 2
  assert all(
    row['field_available']
    and row['audit']['status'] == 'euler_audit_shock_jump_failure'
    for row in euler_audits
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_boundary_accepted'
  ] is False
  boundary_curves = planner.diagnostics[
    'global_reflected_shock_remesh_euler_boundary_curves'
  ]
  assert len(boundary_curves) == 2
  assert all(
    row['field_available']
    and row['curve'] is not None
    and row['curve']['chain_promotion_blocked']
    for row in boundary_curves
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_geometry_reconciliation_accepted'
  ] is True
  geometry_reconciliations = planner.diagnostics[
    'global_reflected_shock_remesh_euler_geometry_reconciliations'
  ]
  assert len(geometry_reconciliations) == 2
  assert all(
    row['field_available']
    and row['geometry_reconciliation']['status'] == 'converged_local_euler_shock'
    and row['geometry_reconciliation']['local_euler_verified']
    and row['geometry_reconciliation']['orientation'] == (
      'mixed-characteristic-boundary'
    )
    for row in geometry_reconciliations
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_ambient_physical_field_accepted'
  ] is False
  ambient_physical_fields = planner.diagnostics[
    'global_reflected_shock_remesh_euler_ambient_physical_fields'
  ]
  assert len(ambient_physical_fields) == 2
  assert all(
    row['field_available']
    and row['geometry_reconciliation_verified']
    and row['ambient_physical_field']['status'] == (
      'euler_physical_ambient_boundary_failure'
    )
    and not row['ambient_physical_field']['physical_closure_verified']
    for row in ambient_physical_fields
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_accepted'
  ] is True
  global_euler_closure = planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure'
  ]
  assert global_euler_closure['status'] == (
    'converged_global_euler_shock_field'
  )
  assert global_euler_closure['physical_closure_verified'] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_independent_audit_accepted'
  ] is True
  global_euler_measurement = planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_independent_measurement'
  ]
  assert global_euler_measurement['status'] == 'converged'
  assert global_euler_measurement['checks']['source_frontier_verified'] is True
  assert global_euler_measurement['checks']['physical_closure_verified'] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_required_for_promotion'
  ] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_independent_measurement'
  ]['status'] == 'converged'
  assert planner.production_claim_allowed is False


def test_global_reflected_shock_remesh_physical_field_adapter_derives_fresh_source():
  field = _canonical_field()
  planner = plan_reflected_domain_global_shock_remesh_chain_from_physical_field(
    field,
    start_x_m=0.5,
    end_x_m=1.0,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_from_physical_field'
  ] is True
  assert planner.diagnostics['source_projection_automatic'] is True
  assert planner.diagnostics['source_projection_verified'] is True
  assert planner.diagnostics['source_projection_handoff_verified'] is True
  assert planner.diagnostics['source_projection_strip']['status'] == (
    'converged_open_shock_ambient_strip'
  )
  assert planner.diagnostics['source_projection_reflection_patch']['status'] == (
    'converged_open_terminal_reflection_patch'
  )
  assert planner.diagnostics['source_projection_source_band']['source_field_verified'] is True
  assert planner.diagnostics['global_reflected_shock_remesh']['status'] == (
    'global_reflected_shock_no_endpoint_closure'
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_independent_measurement'
  ]['status'] == 'converged'
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_accepted'
  ] is True
  assert planner.diagnostics['physical_chain_cell_count'] == 0
  assert planner.diagnostics['chain_promotion_blocked'] is True
  assert planner.production_claim_allowed is False


def test_global_reflected_shock_remesh_physical_field_adapter_typed_projection_stop():
  field = _canonical_field()
  planner = plan_reflected_domain_global_shock_remesh_chain_from_physical_field(
    field,
    start_x_m=0.5,
    end_x_m=1.0,
    source_sample_count=2,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is MocChainTerminationReason.INVALID_INPUT
  assert planner.diagnostics['source_projection_automatic'] is True
  assert planner.diagnostics['source_projection_verified'] is False
  assert planner.diagnostics['source_projection_source_band']['status'] == (
    'invalid_input'
  )
  assert 'global_reflected_shock_remesh' not in planner.diagnostics
  assert planner.diagnostics['physical_chain_cell_count'] == 0
  assert planner.diagnostics['chain_promotion_blocked'] is True
  assert planner.production_claim_allowed is False


def test_reflected_domain_alternating_physical_field_chain_refinement_is_research_only():
  seed = _canonical_field()
  coarse = MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase(
    resolution=17,
    results=_alternating_physical_chain_results(seed, 17),
  )
  fine = MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase(
    resolution=33,
    results=_alternating_physical_chain_results(seed, 33),
  )

  measurement = (
    measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
      (coarse, fine),
      endpoint_tolerance_m=1.0e-3,
      shock_spacing_tolerance_m=1.0e-4,
      area_tolerance_m2=1.5e-3,
      maximum_radius_tolerance_m=5.0e-4,
    )
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.resolutions == (17, 33)
  assert measurement.field_count == 2
  assert measurement.resolution_order_verified
  assert measurement.resolution_metadata_verified
  assert measurement.field_count_consistent
  assert measurement.geometry_shape_verified
  assert measurement.solver_configuration_consistent
  assert measurement.source_geometry_freshness_verified
  assert measurement.pressure_loss_verified
  assert measurement.handoff_metadata_complete
  assert measurement.handoff_links_verified is True
  assert measurement.fresh_domain_verified
  assert measurement.refinement_convergence_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.as_report()['physical_closure_verified'] is False

  reversed_measurement = (
    measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
      (fine, coarse),
    )
  )
  assert reversed_measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.RESOLUTION_FAILURE
  )
  assert reversed_measurement.converged is False

  shape_mismatch = MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase(
    resolution=33,
    results=(fine.results[0],),
  )
  shape_measurement = (
    measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
      (coarse, shape_mismatch),
    )
  )
  assert shape_measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONSISTENCY_FAILURE
  )
  assert shape_measurement.field_count_consistent is False
  assert shape_measurement.converged is False


def test_reflected_domain_alternating_physical_field_rejects_unverified_source():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  corrupted = replace(
    source,
    status=MocReflectedDomainAlternatingSourceStatus.FIELD_FAILURE,
  )

  result = solve_reflected_domain_alternating_physical_field(
    corrupted,
    compression_amplitude_rad=0.05,
  )

  assert result.status is (
    MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE
  )
  assert result.converged is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True

  measurement = measure_moc_reflected_domain_alternating_physical_field(result)
  assert measurement.converged is False
  assert measurement.source_field_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked is True


def test_reflected_domain_alternating_physical_field_chain_rejects_nonfresh_domain():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  first_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert first_source.converged
  first_result = solve_reflected_domain_alternating_physical_field(
    first_source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(field),
  )
  assert first_result.converged
  assert first_result.field is not None

  second_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    source_sample_count=5,
    incoming_handoff=_handoff(first_result.field),
  )
  assert second_source.converged
  second_result = solve_reflected_domain_alternating_physical_field(
    second_source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(first_result.field),
  )
  assert second_result.converged
  assert second_result.field is not None

  measurement = measure_moc_reflected_domain_alternating_physical_field_chain(
    (first_result, second_result),
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE
  )
  assert measurement.converged is False
  assert measurement.field_count == 2
  assert len(measurement.field_measurements) == 2
  assert measurement.source_geometry_freshness_verified
  assert measurement.handoff_link_count == 1
  assert measurement.handoff_links_verified is True
  assert measurement.fresh_domain_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.physical_field_chain_measurement is not None
  assert measurement.physical_field_chain_measurement.converged is False
  assert measurement.physical_field_chain_measurement.status.value == 'domain_failure'
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False


def test_reflected_domain_alternating_physical_field_chain_rejects_copied_geometry():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert source.converged
  first_result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(field),
  )
  assert first_result.converged
  assert first_result.field is not None
  copied_source = replace(
    source,
    incoming_handoff=_handoff(first_result.field),
  )
  copied_result = solve_reflected_domain_alternating_physical_field(
    copied_source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(first_result.field),
  )
  assert copied_result.converged

  measurement = measure_moc_reflected_domain_alternating_physical_field_chain(
    (first_result, copied_result),
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.SOURCE_FRESHNESS_FAILURE
  )
  assert measurement.converged is False
  assert measurement.source_geometry_freshness_verified is False
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False


def test_reflected_domain_alternating_physical_field_chain_rejects_missing_source_band():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  assert source.converged
  result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
  )
  assert result.converged
  missing_source = replace(result, source_band=None)

  measurement = measure_moc_reflected_domain_alternating_physical_field_chain(
    (missing_source,),
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.SOURCE_FAILURE
  )
  assert measurement.converged is False
  assert measurement.source_geometry_freshness_verified is False
  assert measurement.chain_promotion_blocked is True


def test_reflected_domain_alternating_source_planner_carries_one_cell_handoff():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  seed = _canonical_field()

  planner = plan_reflected_domain_alternating_source_chain(
    seed,
    source,
    start_x_m=0.5,
    end_x_m=2.0,
    compression_amplitude_rad=0.05,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.resolved
  assert planner.chain.cell_count == 2
  assert planner.chain.physical_termination is False
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert len(planner.steps) == 2
  assert planner.steps[0].result_kind == 'physical-field-solve-returned'
  assert planner.steps[0].incoming_handoff_link_verified is None
  assert planner.steps[1].result_kind == 'termination-returned'
  assert planner.handoff_links_verified is True
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['use_trace_referenced_profile'] is False
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['physical_closure_pending'] is True
  incoming_points = planner.chain.cells[1].diagnostics['boundary_geometry'][
    'incoming_handoff_points_m'
  ]
  assert incoming_points == [
    [sample.state.x_m, sample.state.y_m]
    for sample in planner.chain.cells[0].continuation_boundary
  ]


def test_reflected_domain_alternating_source_planner_can_opt_into_trace_profile():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  planner = plan_reflected_domain_alternating_source_chain(
    _canonical_field(),
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    use_outer_seed_attachment=True,
    use_trace_referenced_profile=True,
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 2
  assert planner.diagnostics['use_outer_seed_attachment'] is True
  assert planner.diagnostics['use_trace_referenced_profile'] is True


def test_reflected_domain_alternating_source_sequence_requires_fresh_bands_and_carries_multiple_cells():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  initial_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert initial_source.converged

  callback_calls = []

  def source_band_at(current_field, current, next_cell_index, incoming_handoff):
    callback_calls.append((current_field, current.cell_index, next_cell_index))
    if next_cell_index > 3:
      return None
    source = solve_reflected_domain_alternating_source(
      patch,
      ambient_pressure,
      source_sample_count=7 - next_cell_index,
      incoming_handoff=incoming_handoff,
    )
    assert source.converged
    return source

  planner = plan_reflected_domain_alternating_source_chain_sequence(
    field,
    initial_source,
    source_band_at,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.handoff_links_verified is True
  assert [step.result_kind for step in planner.steps] == [
    'physical-field-solve-returned',
    'physical-field-solve-returned',
    'termination-returned',
  ]
  assert len(callback_calls) == 2
  attempts = planner.diagnostics['alternating_source_attempts']
  assert len(attempts) == 3
  assert all(
    attempt['incoming_handoff_verified'] is True
    and attempt['fresh_source_band'] is True
    and attempt['fresh_source_geometry'] is True
    for attempt in attempts[:2]
  )
  assert attempts[-1]['provider_result'] is None
  assert planner.diagnostics['alternating_source_reuse_policy'] == (
    'fresh-alternating-source-band-and-exact-incoming-handoff-required-per-cell'
  )
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['external_validation_pending'] is True
  alternating_field_chain_audit = planner.diagnostics[
    'alternating_physical_field_chain_audit'
  ]
  assert alternating_field_chain_audit['status'] == 'domain_failure'
  assert planner.diagnostics[
    'alternating_physical_field_chain_audit_accepted'
  ] is False
  assert alternating_field_chain_audit['checks'] == {
    'source_geometry_freshness_verified': True,
    'handoff_links_verified': True,
    'fresh_domain_verified': False,
    'physical_closure_verified': False,
  }


def test_reflected_domain_alternating_source_sequence_rejects_copied_geometry():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert source.converged

  planner = plan_reflected_domain_alternating_source_chain_sequence(
    field,
    source,
    lambda _field, _current, _next, incoming: replace(
      source,
      incoming_handoff=incoming,
    ),
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert planner.chain.cell_count == 2
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  attempt = planner.diagnostics['alternating_source_attempts'][-1]
  assert attempt['role'] == 'alternating-source-band-freshness-gate'
  assert attempt['incoming_handoff_verified'] is True
  assert attempt['fresh_source_band'] is True
  assert attempt['fresh_source_geometry'] is False
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False


def test_reflected_domain_alternating_source_band_carries_explicit_pressure_row():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  pressure = patch.outgoing_trace_total_pressure_Pa[0]
  pressure_row = tuple(pressure * (1.0 - 0.005 * index) for index in range(6))

  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    pressure,
    centerline_total_pressure_Pa=pressure_row,
  )

  assert result.converged
  assert result.source_field_verified
  assert result.centerline_total_pressure_Pa == pytest.approx(pressure_row)
  assert result.outer_total_pressure_Pa == pytest.approx(pressure_row)
  assert result.total_pressure_at(
    (
      result.outer_source_states[3].x_m,
      result.outer_source_states[3].y_m,
    )
  ) == pytest.approx(pressure_row[3])
  assert result.as_report()['total_pressure_range_Pa'][0] == pytest.approx(
    pressure_row[-1]
  )


def test_reflected_domain_alternating_source_band_rejects_a_nonexact_seed():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None

  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    outer_seed_state=replace(patch.outgoing_trace_states[0], x_m=1.4),
  )

  assert result.status is MocReflectedDomainAlternatingSourceStatus.SEED_FAILURE
  assert result.source_field_verified is False
  assert result.physical_closure_verified is False


def test_reflected_domain_outer_source_curve_carries_explicit_pressure_rows():
  exit_state, ambient, reflected = _outer_source_fixture()
  total_pressure = exit_state.total_pressure_Pa
  centerline_pressures = tuple(
    total_pressure * (1.0 - 0.001 * index)
    for index in range(len(reflected.centerline_states))
  )

  result = solve_reflected_domain_outer_source_curve(
    reflected.centerline_states,
    reflected.boundary_states[0],
    ambient.pressure_Pa,
    total_pressure,
    centerline_total_pressure_Pa=centerline_pressures,
  )

  assert result.converged
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.total_pressure_model == (
    'source-family-carried-total-pressure'
  )
  assert result.centerline_total_pressure_Pa == pytest.approx(
    centerline_pressures
  )
  assert result.outer_total_pressure_Pa[0] == pytest.approx(total_pressure)
  assert result.outer_total_pressure_Pa[1:] == pytest.approx(
    centerline_pressures[1:]
  )
  assert result.source_strip.total_pressure_at(
    (
      result.outer_source_states[3].x_m,
      result.outer_source_states[3].y_m,
    )
  ) == pytest.approx(result.outer_total_pressure_Pa[3])
  assert result.as_report()['total_pressure_range_Pa'][1] == pytest.approx(
    total_pressure
  )
  measurement = measure_moc_reflected_domain_outer_source_curve(result)
  assert measurement.converged
  assert measurement.pressure_lineage_verified


def test_reflected_domain_outer_source_curve_rejects_nonambient_seed():
  exit_state, ambient, reflected = _outer_source_fixture()
  bad_seed = replace(reflected.boundary_states[0], mach=2.0)

  result = solve_reflected_domain_outer_source_curve(
    reflected.centerline_states,
    bad_seed,
    ambient.pressure_Pa,
    exit_state.total_pressure_Pa,
  )

  assert result.status is MocReflectedDomainOuterSourceStatus.SEED_FAILURE
  assert result.converged is False
  assert result.outer_source_curve_verified is False
  assert result.source_field_verified is False
  assert result.point_results == ()


def test_reflected_domain_outer_source_curve_binds_into_a_fresh_remesh_request():
  _field, patch, request = _request()
  seed = request.outer_source_states[0]
  ambient_pressure = 101325.0
  seed_pressure = ambient_pressure * (
    1.0 + 0.5 * (seed.gamma - 1.0) * seed.mach * seed.mach
  ) ** (seed.gamma / (seed.gamma - 1.0))
  generated = solve_reflected_domain_outer_source_curve(
    request.centerline_source_states,
    seed,
    ambient_pressure,
    request.total_pressure_Pa,
    previous_boundary_total_pressure_Pa=seed_pressure,
  )
  assert generated.converged

  bound_request = build_reflected_domain_remesh_request_from_outer_source(
    patch,
    generated,
    incoming_handoff=request.incoming_handoff,
  )

  assert bound_request.centerline_source_states == (
    generated.centerline_source_states
  )
  assert bound_request.outer_source_states == generated.outer_source_states
  assert bound_request.centerline_total_pressure_Pa == pytest.approx(
    generated.centerline_total_pressure_Pa
  )
  assert bound_request.outer_total_pressure_Pa == pytest.approx(
    generated.outer_total_pressure_Pa
  )
  remesh = solve_reflected_domain_remesh(bound_request)
  assert remesh.converged
  assert remesh.source_field_verified
  assert remesh.request is bound_request


def test_reflected_domain_ambient_closed_planner_connects_fresh_remeshes_to_physical_solver(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request(incoming_handoff=_handoff(seed))
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  assert initial_remesh.converged
  solver_calls = []
  remesh_calls = []

  def fake_physical_solver(
    _state_at,
    _pressure_at,
    start_point_m,
    ambient_pressure_Pa,
    _lower,
    _upper,
    **kwargs,
  ):
    incoming = tuple(kwargs['incoming_handoff'])
    solver_calls.append((start_point_m, ambient_pressure_Pa, incoming))
    field = replace(
      seed,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
    )
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      axis_closure_shoot=None,
      field=field,
      message='manufactured accepted physical-field solver result',
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )

  def remesh_at(current_field, current, next_cell_index, incoming_handoff):
    remesh_calls.append(
      (current_field, current.cell_index, next_cell_index, incoming_handoff)
    )
    _field, _patch, request = _request(incoming_handoff=incoming_handoff)
    offset = 0.001 * len(remesh_calls)
    request = replace(
      request,
      outer_source_states=tuple(
        replace(state, x_m=state.x_m + offset)
        for state in request.outer_source_states
      ),
    )
    return solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    remesh_at,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=3,
      cell_axial_length_m=0.4,
      ambient_pressure_Pa=101325.0,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.handoff_links_verified is True
  assert planner.production_claim_allowed is False
  assert len(solver_calls) == 2
  assert len(remesh_calls) == 1
  assert remesh_calls[0][0] is not seed
  assert planner.diagnostics['reflected_domain_remesh_attempt_count'] == 2
  assert all(
    attempt['fresh_remesh'] is True
    and attempt['fresh_source_field'] is True
    and attempt['incoming_handoff_verified'] is True
    for attempt in planner.diagnostics['reflected_domain_remesh_attempts']
  )
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['free_boundary_verified'] is False
  assert planner.diagnostics['physical_chain_promotion_allowed'] is False
  assert planner.diagnostics['external_validation_pending'] is True


def test_reflected_domain_ambient_closed_planner_rejects_mismatched_initial_handoff(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request()
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  solver_called = False

  def fake_physical_solver(*_args, **_kwargs):
    nonlocal solver_called
    solver_called = True
    raise AssertionError('physical solver must not run after a handoff failure')

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )
  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    lambda *_args: initial_remesh,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=2,
      cell_axial_length_m=0.4,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert solver_called is False
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is MocChainTerminationReason.STATE_NOT_CARRIED
  assert planner.steps[0].result_termination_reason is (
    MocChainTerminationReason.STATE_NOT_CARRIED
  )
  attempt = planner.diagnostics['reflected_domain_remesh_attempts'][0]
  assert attempt['role'] == 'reflected-domain-remesh-handoff-seam'
  assert attempt['incoming_handoff_verified'] is False


def test_reflected_domain_ambient_closed_planner_rejects_reused_remesh(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request(incoming_handoff=_handoff(seed))
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  assert initial_remesh.converged
  solver_calls = 0

  def fake_physical_solver(*_args, **kwargs):
    nonlocal solver_calls
    solver_calls += 1
    incoming = tuple(kwargs['incoming_handoff'])
    field = replace(
      seed,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
    )
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      axis_closure_shoot=None,
      field=field,
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )
  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    lambda *_args: initial_remesh,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=3,
      cell_axial_length_m=0.4,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert solver_calls == 1
  assert planner.chain.cell_count == 2
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.steps[-1].result_termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  attempt = planner.diagnostics['reflected_domain_remesh_attempts'][-1]
  assert attempt['role'] == 'reflected-domain-remesh-freshness-gate'
  assert attempt['fresh_remesh'] is False
  assert attempt['fresh_source_field'] is False


def test_reflected_domain_one_step_planner_keeps_the_remesh_below_physical_claims():
  _field, _patch, request = _request()
  field = _reference_seed_field()
  remesh = solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_shock_chain(
    field,
    remesh,
    start_point_m=request.outer_source_states[0].x_m,
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.production_claim_allowed is False
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['reflected_domain_remesh']['status'] == (
    MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD.value
  )
  assert planner.chain.physical_termination is False


def test_terminal_reflection_reference_report_keeps_chain_promotion_blocked():
  report = MocTerminalReflectionPatchAmbientClosureChainReference().as_report()

  assert report['planning_only'] is True
  assert report['production_claim_allowed'] is False
  assert report['physical_chain_promotion_allowed'] is False


def test_reflected_domain_sequence_requires_exact_handoff_for_each_new_remesh(
  monkeypatch: pytest.MonkeyPatch,
):
  _field, _patch, first_request = _request(incoming_handoff=_handoff(_canonical_field()))
  field = _reference_seed_field()
  first = solve_reflected_domain_remesh(first_request)
  assert first.converged
  calls = []

  def fake_source_solver(
    current,
    _next_cell_index,
    incoming_handoff,
    _source_strip,
    **kwargs,
  ):
    del kwargs
    next_field_result = solve_uniform_attached_shock_field(
      CharacteristicState(
        current.end_x_m + 0.01,
        0.25,
        -0.2,
        2.0,
        1.4,
      ),
      100000.0,
      (current.end_x_m + 0.01, 0.25),
      outer_downstream_flow_angle_rad=0.05,
      sample_count=9,
    )
    assert next_field_result.field is not None
    next_field = next_field_result.field
    incoming = tuple(incoming_handoff)
    field_with_handoff = replace(
      next_field,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
      upstream_boundary_total_pressure_Pa=(
        min(sample.total_pressure_Pa for sample in incoming),
      ) * len(next_field.upstream_boundary_states),
    )
    return MocPostShockChainCellSolve(
      field=field_with_handoff,
      end_x_m=current.end_x_m + 0.2,
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_chain_cell_from_source_strip_or_termination',
    fake_source_solver,
  )

  def remesh_at(current, next_cell_index, incoming_handoff):
    calls.append((current.cell_index, next_cell_index, incoming_handoff))
    _field, _patch, request = _request(incoming_handoff=incoming_handoff)
    return solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_shock_chain_sequence(
    field,
    first,
    remesh_at,
    start_point_at=lambda _current, _index, candidate: (
      candidate.request.outer_source_states[0].x_m,
      candidate.request.outer_source_states[0].y_m,
    ),
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert calls
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['reflected_domain_remesh_attempt_count'] >= 2
  assert planner.diagnostics['reflected_domain_reuse_policy'] == (
    'fresh-reflected-domain-remesh-required-per-cell'
  )
  assert planner.chain.physical_termination is False

  missing_provenance = plan_reflected_domain_remesh_shock_chain_sequence(
    field,
    first,
    lambda _current, _index, _handoff: first,
    start_point_at=lambda _current, _index, candidate: (
      candidate.request.outer_source_states[0].x_m,
      candidate.request.outer_source_states[0].y_m,
    ),
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )
  assert missing_provenance.chain.termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  assert missing_provenance.diagnostics['reflected_domain_remesh_attempts'][0][
    'role'
  ] == 'initial-reflected-domain-remesh'
