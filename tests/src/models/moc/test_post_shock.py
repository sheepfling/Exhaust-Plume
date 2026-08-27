from __future__ import annotations

from dataclasses import replace
from math import cos, sin

import pytest

from exhaust_plume.models.moc import (
  CharacteristicPointResult,
  CharacteristicState,
  MocCharacteristicCell,
  MocCharacteristicNode,
  MocCellClosureStatus,
  MocChainBoundaryKind,
  MocChainGeometryFidelity,
  MocChainPlannerKind,
  MocChainTerminationDecision,
  MocChainStatus,
  MocChainTerminationReason,
  MocPostShockBoundaryState,
  MocAmbientBoundaryStatus,
  MocPostShockChainCellSolve,
  MocPostShockClosureStatus,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldStatus,
  MocPostShockCharacteristicZoneResult,
  MocPostShockFirstLayerStatus,
  MocPostShockContinuationStatus,
  MocPostShockZoneStatus,
  MocPostShockZoneSamplingStatus,
  MocPostShockZoneShockSolveResult,
  MocShockBoundaryFitStatus,
  MocShockBoundaryFitResult,
  MocPrescribedPostShockChainMock,
  MocSolverGeneratedPostShockChainReference,
  MocFieldCoupledPostShockChainReference,
  MocPrimitiveStatus,
  assemble_post_shock_characteristic_zone,
  assemble_post_shock_characteristic_field,
  assemble_post_shock_first_layer,
  continue_post_shock_characteristics_to_centerline,
  continue_post_shock_characteristics_to_centerline_open,
  continue_post_shock_characteristic_chain,
  plan_post_shock_characteristic_chain,
  plan_post_shock_zone_chain,
  plan_solver_generated_post_shock_chain_reference,
  plan_field_coupled_post_shock_chain_reference,
  plan_prescribed_post_shock_chain_mock,
  fit_attached_shock_boundary,
  sample_post_shock_zone_along_shock_path,
  solve_marched_attached_shock_from_post_shock_zone,
  solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination,
  solve_uniform_attached_shock_field,
  solve_attached_compression_to_turn,
  validate_closed_post_shock_field,
  validate_post_shock_ambient_boundary,
)


def _prescribed_boundary() -> tuple[MocPostShockBoundaryState, ...]:
  points = (
    (0.76, 0.165),
    (0.78, 0.110),
    (0.80, 0.055),
    (0.82, 0.0),
  )
  return tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.1 * (3 - index),
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    )
    for index, point in enumerate(points)
  )


def _open_post_shock_zone_fixture() -> MocPostShockCharacteristicZoneResult:
  samples = list(_prescribed_boundary())
  samples[-1] = MocPostShockBoundaryState(
    point_m=(0.82, 0.02),
    state=CharacteristicState(
      x_m=0.82,
      y_m=0.02,
      theta_rad=-0.05,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_total_pressure_Pa=2.0e6,
    downstream_total_pressure_Pa=1.8e6,
  )
  continuation = continue_post_shock_characteristics_to_centerline_open(tuple(samples))
  first_layer = assemble_post_shock_first_layer(continuation)
  return assemble_post_shock_characteristic_zone(
    continuation,
    first_layer,
    tuple(samples),
  )


def _fitted_attached_boundary() -> tuple[tuple[float, float], ...]:
  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.2,
  )
  assert compression.beta_rad is not None
  shock_angle = -0.2 - compression.beta_rad
  start = (0.5, 0.5)
  step = 0.5 / (3.0 * abs(sin(shock_angle)))
  return tuple(
    (
      start[0] + index * step * cos(shock_angle),
      start[1] + index * step * sin(shock_angle),
    )
    for index in range(4)
  )


def _closed_post_shock_candidate():
  points = _fitted_attached_boundary()
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )
  shock_fit = fit_attached_shock_boundary(
    upstream_states,
    (100000.0,) * 4,
    points,
    (0.0,) * 4,
  )
  continuation = continue_post_shock_characteristics_to_centerline(
    shock_fit.boundary_states,
  )
  axis_points = tuple(segment.centerline_point_m for segment in continuation.segments)
  cells = [
    MocCharacteristicCell(
      cell_index=index,
      cell_kind='closed-post-shock-strip',
      vertices_xr_m=(
        points[index],
        points[index + 1],
        axis_points[index + 1],
        axis_points[index],
      ),
      centerline_indices=(index, index + 1),
      boundary_indices=(index, index + 1),
    )
    for index in range(2)
  ]
  cells.append(
    MocCharacteristicCell(
      cell_index=2,
      cell_kind='closed-post-shock-terminal',
      vertices_xr_m=(points[2], points[3], axis_points[2]),
      centerline_indices=(2, 3),
      boundary_indices=(2, 3),
    )
  )
  states_by_point = {
    sample.point_m: sample.state
    for sample in shock_fit.boundary_states
  }
  states_by_point.update(
    {
      segment.centerline_point_m: segment.centerline_state
      for segment in continuation.segments
    }
  )
  nodes = tuple(
    MocCharacteristicNode(
      centerline_index=index,
      boundary_index=index,
      point_m=point,
      state=state,
        point_result=CharacteristicPointResult(
          status=MocPrimitiveStatus.CONVERGED,
          state=state,
          point_m=point,
          invariant_residual_plus=0.0,
          invariant_residual_minus=0.0,
          geometry_residual=0.0,
          iterations=0,
        ),
        total_pressure_Pa=1.8e6,
      )
    for index, (point, state) in enumerate(states_by_point.items())
  )
  return shock_fit, continuation, nodes, tuple(cells)


def test_prescribed_post_shock_c_minus_traces_reach_centerline() -> None:
  result = continue_post_shock_characteristics_to_centerline(_prescribed_boundary())

  assert result.status is MocPostShockContinuationStatus.CONVERGED_PRESCRIBED_BOUNDARY
  assert result.converged
  assert len(result.segments) == 4
  assert len(result.centerline_states) == 4
  assert result.maximum_geometry_residual_m == pytest.approx(0.0, abs=1.0e-12)
  assert result.maximum_absolute_invariant_residual is not None
  assert result.maximum_absolute_invariant_residual < 1.0e-10
  assert result.segments[-1].centerline_point_m == pytest.approx((0.82, 0.0))
  assert all(segment.centerline_state.theta_rad == pytest.approx(0.0) for segment in result.segments)
  assert 'shock fitting' in result.message


def test_open_post_shock_c_minus_traces_keep_a_terminal_shock_interface() -> None:
  samples = list(_prescribed_boundary())
  samples[-1] = MocPostShockBoundaryState(
    point_m=(0.82, 0.02),
    state=CharacteristicState(
      x_m=0.82,
      y_m=0.02,
      theta_rad=-0.05,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_total_pressure_Pa=2.0e6,
    downstream_total_pressure_Pa=1.8e6,
  )

  result = continue_post_shock_characteristics_to_centerline_open(tuple(samples))

  assert result.status is MocPostShockContinuationStatus.CONVERGED_OPEN_BOUNDARY
  assert result.converged
  assert result.segments[-1].shock_point_m == pytest.approx((0.82, 0.02))
  assert result.segments[-1].centerline_point_m[1] == pytest.approx(0.0)
  assert result.segments[-1].centerline_state.theta_rad == pytest.approx(0.0)
  assert 'separate terminal model' in result.message

  first_layer = assemble_post_shock_first_layer(result)
  zone = assemble_post_shock_characteristic_zone(result, first_layer, tuple(samples))
  assert first_layer.converged
  assert zone.status is MocPostShockZoneStatus.CONVERGED_OPEN
  assert zone.physical_closure_status == 'open'
  assert zone.state_sampling_available

  first_cell = zone.cells[0]
  sample_point = tuple(
    sum(vertex[coordinate] for vertex in first_cell.vertices_xr_m)
    / len(first_cell.vertices_xr_m)
    for coordinate in (0, 1)
  )
  sampled_state = zone.state_at(sample_point)
  sampled_total_pressure = zone.total_pressure_at(sample_point)
  sampled_static_pressure = zone.static_pressure_at(sample_point)
  assert sampled_state is not None
  assert sampled_state.mach > 1.0
  assert sampled_total_pressure is not None
  assert sampled_total_pressure > 0.0
  assert sampled_static_pressure is not None
  assert sampled_static_pressure > 0.0
  assert zone.state_at((10.0, 10.0)) is None
  assert zone.total_pressure_at((10.0, 10.0)) is None


def test_open_post_shock_zone_path_probe_is_bounded_and_pressure_aware() -> None:
  zone = _open_post_shock_zone_fixture()
  first_cell = zone.cells[0]
  centroid = tuple(
    sum(vertex[coordinate] for vertex in first_cell.vertices_xr_m)
    / len(first_cell.vertices_xr_m)
    for coordinate in (0, 1)
  )
  path = (
    (centroid[0] - 2.0e-4, centroid[1]),
    centroid,
  )

  result = sample_post_shock_zone_along_shock_path(zone, path)

  assert result.status is MocPostShockZoneSamplingStatus.CONVERGED_POST_SHOCK_ZONE_FIELD
  assert result.converged
  assert result.sampled_count == 2
  assert result.first_missing_sample_index is None
  assert all(pressure > 0.0 for pressure in result.upstream_pressure_Pa)

  bounded = sample_post_shock_zone_along_shock_path(
    zone,
    (*path, (centroid[0] + 0.2, centroid[1])),
  )
  assert bounded.status is MocPostShockZoneSamplingStatus.OUTSIDE_DOMAIN
  assert bounded.sampled_count == 2
  assert bounded.first_missing_sample_index == 2


def test_post_shock_zone_next_shock_carries_a_typed_terminal_to_the_chain() -> None:
  zone = _open_post_shock_zone_fixture()
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  current = seed_field.as_chain_cell(start_x_m=0.5, end_x_m=0.85)

  def downstream_flow_angle_at(
    _index: int,
    point: tuple[float, float],
  ) -> float:
    return 0.02 * max(0.0, min(1.0, point[1] / 0.001))

  solved = solve_marched_attached_shock_from_post_shock_zone(
    zone,
    (0.854, 0.001),
    downstream_flow_angle_at=downstream_flow_angle_at,
    sample_count=5,
  )
  assert isinstance(solved, MocPostShockZoneShockSolveResult)
  assert solved.shock.subsonic_terminal_required
  assert solved.coupling.status is MocPostShockZoneSamplingStatus.CONVERGED_POST_SHOCK_ZONE_FIELD
  assert solved.upstream_coupling_verified
  assert not solved.physical_closure_verified

  decision = solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination(
    current,
    2,
    current.continuation_boundary,
    zone,
    start_point_m=(0.854, 0.001),
    end_x_m=1.35,
    downstream_flow_angle_at=downstream_flow_angle_at,
    sample_count=5,
  )
  assert isinstance(decision, MocChainTerminationDecision)
  assert decision.physical_termination
  assert decision.reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert decision.diagnostics['termination_model'] == 'normal-shock-terminal'
  assert decision.diagnostics['upstream_field_model'] == 'bounded-open-post-shock-zone'


def test_post_shock_zone_partial_shock_march_preserves_the_upstream_gap() -> None:
  zone = _open_post_shock_zone_fixture()
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  current = seed_field.as_chain_cell(start_x_m=0.5, end_x_m=0.85)

  solved = solve_marched_attached_shock_from_post_shock_zone(
    zone,
    (0.9, 0.01),
    downstream_flow_angle_rad=0.0,
    sample_count=5,
    position_tolerance_m=1.0e-8,
  )

  assert solved.shock.status.value == 'upstream_field_failure'
  assert solved.shock.failed_sample_index == 4
  assert len(solved.shock.shock_points_m) == 4
  assert solved.coupling.status is MocPostShockZoneSamplingStatus.OUTSIDE_DOMAIN
  assert solved.coupling.sampled_count == 4
  assert solved.coupling.first_missing_sample_index == 4

  decision = solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination(
    current,
    2,
    current.continuation_boundary,
    zone,
    start_point_m=(0.9, 0.01),
    end_x_m=1.35,
    downstream_flow_angle_rad=0.0,
    sample_count=5,
    position_tolerance_m=1.0e-8,
  )
  assert isinstance(decision, MocChainTerminationDecision)
  assert not decision.physical_termination
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.diagnostics['coupling_status'] == 'outside_post_shock_zone_domain'
  assert decision.diagnostics['sampled_count'] == 4
  assert decision.diagnostics['first_missing_sample_index'] == 4


def test_post_shock_zone_planner_records_a_typed_terminal_stop() -> None:
  zone = _open_post_shock_zone_fixture()
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  seed = seed_field.as_chain_cell(start_x_m=0.5, end_x_m=0.85)

  planner = plan_post_shock_zone_chain(
    seed,
    zone,
    start_point_m=(0.854, 0.001),
    end_x_m=1.35,
    downstream_flow_angle_at=lambda _index, point: (
      0.02 * max(0.0, min(1.0, point[1] / 0.001))
    ),
    sample_count=5,
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.physical_termination
  assert planner.chain.cell_count == 1
  assert len(planner.steps) == 1
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.steps[0].result_termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert planner.steps[0].result_physical_termination is True
  assert 'one-step-domain' in planner.claim_status


def test_sampled_attached_shock_fit_produces_pressure_losing_boundary_states() -> None:
  points = _fitted_attached_boundary()
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )

  result = fit_attached_shock_boundary(
    upstream_states,
    (100000.0,) * 4,
    points,
    (0.0,) * 4,
  )

  assert result.status is MocShockBoundaryFitStatus.CONVERGED_FITTED
  assert result.converged
  assert len(result.boundary_states) == 4
  assert result.maximum_shock_angle_residual_rad is not None
  assert result.maximum_shock_angle_residual_rad < 1.0e-10
  assert all(
    sample.downstream_total_pressure_Pa < sample.upstream_total_pressure_Pa
    for sample in result.boundary_states
  )
  assert result.boundary_states[-1].point_m[1] == pytest.approx(0.0, abs=1.0e-12)


def test_attached_shock_fit_rejects_a_tangent_mismatch() -> None:
  points = list(_fitted_attached_boundary())
  points[1] = (points[1][0], points[1][1] + 0.01)
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )

  result = fit_attached_shock_boundary(
    upstream_states,
    (100000.0,) * 4,
    tuple(points),
    (0.0,) * 4,
  )

  assert result.status is MocShockBoundaryFitStatus.GEOMETRY_FAILURE
  assert not result.converged
  assert 'tangent disagrees' in result.message


def test_closed_post_shock_field_requires_explicit_boundary_edges() -> None:
  shock_fit, continuation, nodes, cells = _closed_post_shock_candidate()

  result = validate_closed_post_shock_field(
    continuation,
    shock_fit,
    nodes,
    cells,
  )

  assert result.status is MocPostShockClosureStatus.CONVERGED_CLOSED
  assert result.converged
  assert result.physical_closure_verified
  assert result.topology.forms_closed_zone
  assert result.pressure_loss_verified
  assert result.state_sampling_available
  assert len(result.shock_boundary_states) == len(result.shock_boundary_points_m)
  assert len(result.axis_boundary_states) == len(result.axis_boundary_points_m)
  chain_cell = result.as_chain_cell(start_x_m=0.5, end_x_m=1.2)
  assert chain_cell.geometry_fidelity is MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
  assert chain_cell.physical_closure is MocCellClosureStatus.CLOSED
  assert chain_cell.continuation_boundary_kind is MocChainBoundaryKind.CENTERLINE_TRACE
  assert len(chain_cell.continuation_boundary) == len(result.axis_boundary_states)
  assert chain_cell.resolved
  report = result.as_report()
  assert report['state_sampling_available'] is True
  assert report['topology_forms_closed_zone'] is True


def test_shock_seeded_post_shock_field_closes_a_characteristic_fan() -> None:
  samples = _prescribed_boundary()
  shock_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=samples,
    shock_angle_residuals_rad=(0.0,) * len(samples),
    maximum_shock_angle_residual_rad=0.0,
  )

  result = assemble_post_shock_characteristic_field(shock_fit)

  assert isinstance(result, MocPostShockCharacteristicFieldResult)
  assert result.status is MocPostShockFieldStatus.CONVERGED_CLOSED
  assert result.converged
  assert result.physical_closure_verified
  assert result.characteristic_layer_count == 3
  assert result.node_count == 7
  assert result.cell_count == 9
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.minimum_forward_margin_m is not None
  assert result.minimum_forward_margin_m > 0.0
  assert result.pressure_loss_verified
  assert not result.upstream_shock_coupling_verified
  assert result.state_sampling_available
  assert result.domain_x_extent_m is not None
  assert result.domain_x_extent_m[1] > result.domain_x_extent_m[0]
  assert result.domain_y_extent_m == pytest.approx((0.0, 0.165), abs=1.0e-10)
  report = result.as_report()
  assert report['topology_forms_closed_zone'] is True
  assert report['domain_x_extent_m'] == pytest.approx(result.domain_x_extent_m)
  assert report['continuation_boundary_sample_count'] == len(
    result.continuation_boundary_states
  )
  assert all(node.total_pressure_Pa is not None for node in result.nodes)
  assert result.terminal_centerline_state is not None
  chain_cell = result.as_chain_cell(start_x_m=samples[0].point_m[0], end_x_m=1.5)
  assert chain_cell.resolved
  with pytest.raises(ValueError, match='upstream shock states'):
    result.as_coupled_chain_cell(start_x_m=samples[0].point_m[0], end_x_m=1.5)
  with pytest.raises(ValueError, match='reserved closure keys'):
    result.as_chain_cell(
      start_x_m=samples[0].point_m[0],
      end_x_m=1.5,
      diagnostics={'physical_closure_verified': False},
    )


def test_shock_seeded_field_does_not_promote_internal_characteristic_as_ambient_edge() -> None:
  samples = _prescribed_boundary()
  shock_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=samples,
    shock_angle_residuals_rad=(0.0,) * len(samples),
    maximum_shock_angle_residual_rad=0.0,
  )
  field = assemble_post_shock_characteristic_field(shock_fit)

  result = validate_post_shock_ambient_boundary(field, shock_fit, 101325.0)

  assert result.status is MocAmbientBoundaryStatus.PRESSURE_FAILURE
  assert not result.converged
  assert len(result.points_m) == 5
  assert result.maximum_absolute_pressure_residual is not None
  assert result.maximum_absolute_pressure_residual > 1.0
  assert 'outer perimeter validation failed' in result.message


def test_shock_seeded_field_rejects_a_zero_area_uniform_turn_closure() -> None:
  points = _fitted_attached_boundary()
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )
  shock_fit = fit_attached_shock_boundary(
    upstream_states,
    (100000.0,) * 4,
    points,
    (0.0,) * 4,
  )

  result = assemble_post_shock_characteristic_field(shock_fit)

  assert result.status is MocPostShockFieldStatus.GEOMETRY_FAILURE
  assert not result.converged
  assert 'zero_area' in result.message


def test_shock_seeded_post_shock_field_rejects_nonconverged_fit() -> None:
  result = assemble_post_shock_characteristic_field(
    fit_attached_shock_boundary(
      (),
      (),
      (),
      (),
    )
  )

  assert result.status is MocPostShockFieldStatus.SHOCK_FIT_REQUIRED
  assert not result.converged
  assert 'converged shock fit' in result.message


def _next_chain_field(handoff) -> MocPostShockChainCellSolve:
  points = (
    (1.20, 0.20),
    (1.22, 0.14),
    (1.24, 0.08),
    (1.26, 0.04),
    (1.28, 0.0),
  )
  angles = (-0.30, -0.20, -0.10, -0.05, 0.0)
  samples = tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=angle,
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=1.8e6,
      downstream_total_pressure_Pa=1.6e6,
    )
    for point, angle in zip(points, angles, strict=True)
  )
  fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=samples,
    shock_angle_residuals_rad=(0.0,) * len(samples),
    maximum_shock_angle_residual_rad=0.0,
    upstream_states=tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.35 + 0.08 * index,
        mach=2.0,
        gamma=1.4,
      )
      for index, point in enumerate(points)
    ),
    upstream_total_pressure_Pa=(1.8e6,) * len(samples),
  )
  return MocPostShockChainCellSolve(
    field=assemble_post_shock_characteristic_field(
      fit,
      incoming_handoff=handoff,
    ),
    end_x_m=2.0,
  )


def test_post_shock_chain_re_solves_with_state_and_pressure_handoff() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  assert seed_field.as_chain_cell(
    start_x_m=0.7,
    end_x_m=1.0,
  ).continuation_boundary_kind is MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
  calls: list[tuple[int, int, float]] = []

  def solve_next(current, index, handoff):
    calls.append((index, len(handoff), handoff[0].total_pressure_Pa))
    if index == 3:
      return None
    return _next_chain_field(handoff)

  result = continue_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.7,
    end_x_m=1.0,
  )

  assert result.status is MocChainStatus.SOLVER_TERMINATED
  assert result.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert result.cell_count == 2
  assert result.resolved
  assert all(cell.carries_state for cell in result.cells)
  assert calls == [
    (2, 5, pytest.approx(1.8e6)),
    (3, 6, pytest.approx(1.6e6)),
  ]


def test_post_shock_planner_records_exact_handoff_steps_without_promotion_claim() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)

  planner = plan_post_shock_characteristic_chain(
    seed_field,
    lambda _current, index, handoff: (
      None if index == 3 else _next_chain_field(handoff)
    ),
    start_x_m=0.7,
    end_x_m=1.0,
    planner_kind=MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK,
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 2
  assert planner.planner_kind is MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
  assert planner.production_claim_allowed is False
  assert [step.next_cell_index for step in planner.steps] == [2, 3]
  assert [step.incoming_handoff_sample_count for step in planner.steps] == [5, 6]
  assert all(step.incoming_handoff_fingerprint for step in planner.steps)
  assert len({step.incoming_handoff_fingerprint for step in planner.steps}) == 2
  assert all(
    step.boundary_kind is MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
    for step in planner.steps
  )
  assert planner.handoff_links_verified is True
  assert all(
    step.result_handoff_fingerprint
    for step in planner.steps[:1]
  )
  assert all(
    step.incoming_handoff_link_verified is True
    for step in planner.steps[1:]
  )
  assert [step.result_kind for step in planner.steps] == [
    'field-solve-returned',
    'no-cell-returned',
  ]
  assert [step.result_status for step in planner.steps] == [
    'converged_closed',
    'none',
  ]
  assert planner.steps[0].result_end_x_m == pytest.approx(2.0)
  assert planner.steps[1].result_end_x_m is None


def test_prescribed_post_shock_chain_mock_is_reusable_and_nonproduction() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  mock = MocPrescribedPostShockChainMock()

  planner = plan_prescribed_post_shock_chain_mock(
    seed_field,
    start_x_m=0.7,
    end_x_m=1.0,
    mock=mock,
  )

  assert planner.resolved
  assert planner.chain.status is MocChainStatus.SOLVER_TERMINATED
  assert planner.chain.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert planner.chain.cell_count == mock.total_cell_count
  assert [step.next_cell_index for step in planner.steps] == [2, 3, 4]
  assert planner.planner_kind is MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['prescribed_chain_mock']['planning_only'] is True
  assert planner.diagnostics['prescribed_chain_mock']['production_claim_allowed'] is False
  assert planner.diagnostics['prescribed_chain_mock']['claim_fidelity_ceiling'] == (
    MocChainGeometryFidelity.PRESCRIBED_BOUNDARY_DIAGNOSTIC.value
  )
  assert planner.diagnostics['prescribed_chain_mock']['free_boundary_verified'] is False
  assert planner.diagnostics['prescribed_chain_mock']['physical_chain_promotion_allowed'] is False
  assert planner.handoff_links_verified is True
  assert [step.result_kind for step in planner.steps] == [
    'field-solve-returned',
    'field-solve-returned',
    'termination-returned',
  ]
  assert [step.result_status for step in planner.steps] == [
    'converged_closed',
    'converged_closed',
    'solver-returned-no-next-cell',
  ]
  assert planner.steps[-1].result_termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert planner.steps[-1].result_physical_termination is False
  assert all(
    step.result_boundary_kind is MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
    and step.result_handoff_sample_count is not None
    and step.result_handoff_sample_count >= 3
    and step.result_total_pressure_range_Pa is not None
    and step.result_handoff_fingerprint
    for step in planner.steps[:2]
  )
  assert all(
    step.incoming_handoff_link_verified is True
    for step in planner.steps[1:]
  )


def test_prescribed_post_shock_chain_mock_scales_without_changing_its_claim_ceiling() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  mock = MocPrescribedPostShockChainMock(total_cell_count=5)

  planner = plan_prescribed_post_shock_chain_mock(
    seed_field,
    start_x_m=0.7,
    end_x_m=1.0,
    mock=mock,
  )

  assert planner.resolved
  assert planner.chain.cell_count == 5
  assert [step.next_cell_index for step in planner.steps] == [2, 3, 4, 5, 6]
  assert [step.result_kind for step in planner.steps] == [
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'termination-returned',
  ]
  assert planner.handoff_links_verified is True
  fixture_report = planner.diagnostics['prescribed_chain_mock']
  assert fixture_report['total_cell_count_including_seed'] == 5
  assert fixture_report['claim_fidelity_ceiling'] == (
    MocChainGeometryFidelity.PRESCRIBED_BOUNDARY_DIAGNOSTIC.value
  )
  assert fixture_report['free_boundary_verified'] is False
  assert fixture_report['physical_chain_promotion_allowed'] is False
  assert planner.production_claim_allowed is False


def test_solver_generated_post_shock_reference_re_solves_multiple_cells() -> None:
  generated = solve_uniform_attached_shock_field(
    CharacteristicState(
      x_m=0.5,
      y_m=0.5,
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  seed_field = generated.field
  assert seed_field is not None
  assert seed_field.upstream_shock_coupling_verified

  reference = MocSolverGeneratedPostShockChainReference(total_cell_count=5)
  planner = plan_solver_generated_post_shock_chain_reference(
    seed_field,
    start_x_m=0.5,
    end_x_m=1.0,
    reference=reference,
  )

  assert planner.resolved
  assert planner.chain.status is MocChainStatus.SOLVER_TERMINATED
  assert planner.chain.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert planner.chain.cell_count == reference.total_cell_count
  assert all(cell.resolved for cell in planner.chain.cells)
  assert planner.planner_kind is MocChainPlannerKind.SOLVER_GENERATED_REFERENCE
  assert planner.production_claim_allowed is False
  assert planner.handoff_links_verified is True
  assert [step.next_cell_index for step in planner.steps] == [2, 3, 4, 5, 6]
  assert [step.result_kind for step in planner.steps] == [
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'field-solve-returned',
    'termination-returned',
  ]
  assert planner.diagnostics['solver_generated_chain_reference']['planning_only'] is True
  assert planner.diagnostics['solver_generated_chain_reference']['production_claim_allowed'] is False
  assert planner.diagnostics['solver_generated_chain_reference']['claim_fidelity_ceiling'] == (
    MocChainGeometryFidelity.RESOLVED_PLANAR_MOC.value
  )
  assert planner.diagnostics['solver_generated_chain_reference']['free_boundary_verified'] is False
  assert planner.diagnostics['solver_generated_chain_reference']['physical_chain_promotion_allowed'] is False


def test_field_coupled_post_shock_reference_uses_the_bounded_prior_field() -> None:
  generated = solve_uniform_attached_shock_field(
    CharacteristicState(
      x_m=0.5,
      y_m=0.5,
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=17,
  )
  assert generated.field is not None
  reference = MocFieldCoupledPostShockChainReference()

  planner = plan_field_coupled_post_shock_chain_reference(
    generated.field,
    start_x_m=0.5,
    end_x_m=0.9,
    reference=reference,
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.cell_count == 1
  assert planner.chain.physical_termination is True
  assert planner.chain.termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert planner.steps[0].result_termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert planner.diagnostics['field_coupled_chain_reference']['upstream_state_model'] == (
    'bounded-previous-post-shock-field'
  )
  assert planner.diagnostics['upstream_field_replacement_policy'] == (
    'replace-only-after-complete-field-coupled-solve'
  )


def test_prescribed_chain_mock_uses_a_solver_backed_attached_shock_fit() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  seed_cell = seed_field.as_chain_cell(start_x_m=0.7, end_x_m=1.0)
  mock = MocPrescribedPostShockChainMock()

  solved = mock.solve_next(seed_cell, 2, seed_cell.continuation_boundary)

  assert isinstance(solved, MocPostShockChainCellSolve)
  assert solved.field.shock_closure_status == 'fitted-attached-shock'
  assert solved.field.upstream_shock_coupling_verified is True
  assert solved.field.maximum_shock_angle_residual_rad is not None
  assert solved.field.maximum_shock_angle_residual_rad < 1.0e-8
  assert solved.field.pressure_loss_verified is True
  assert solved.field.upstream_total_pressure_range_Pa is not None
  assert solved.field.downstream_total_pressure_range_Pa is not None
  assert solved.field.downstream_total_pressure_range_Pa[1] < solved.field.upstream_total_pressure_range_Pa[0]
  assert len({round(state.mach, 8) for state in solved.field.shock_boundary_states}) > 1
  assert solved.field.incoming_handoff_total_pressure_Pa == tuple(
    sample.total_pressure_Pa for sample in seed_cell.continuation_boundary
  )


def test_prescribed_chain_mock_rejects_geometry_without_attached_fit() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)
  seed_cell = seed_field.as_chain_cell(start_x_m=0.7, end_x_m=1.0)
  mock = MocPrescribedPostShockChainMock(
    shock_ordinates_m=(0.20, 0.14, 0.08, 0.04, 0.0),
  )

  with pytest.raises(ValueError, match='rejected its shock geometry'):
    mock.solve_next(seed_cell, 2, seed_cell.continuation_boundary)


def test_post_shock_chain_accepts_explicit_physical_termination() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)

  result = continue_post_shock_characteristic_chain(
    seed_field,
    lambda _current, _index, _handoff: MocChainTerminationDecision(
      physical_termination=True,
      message='post-shock pressure and angle tolerances reached',
    ),
    start_x_m=0.7,
    end_x_m=1.0,
  )

  assert result.status is MocChainStatus.PHYSICALLY_TERMINATED
  assert result.termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert result.physical_termination is True
  assert result.cell_count == 1
  assert result.resolved


def test_post_shock_chain_rejects_a_changed_state_handoff() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)

  def solve_next(_current, _index, handoff):
    solved = _next_chain_field(handoff)
    field = solved.field
    changed_states = list(field.incoming_handoff_states)
    changed_states[0] = CharacteristicState(
      x_m=changed_states[0].x_m,
      y_m=changed_states[0].y_m,
      theta_rad=changed_states[0].theta_rad + 0.01,
      mach=changed_states[0].mach,
      gamma=changed_states[0].gamma,
    )
    return MocPostShockChainCellSolve(
      field=replace(field, incoming_handoff_states=tuple(changed_states)),
      end_x_m=2.0,
    )

  result = continue_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.7,
    end_x_m=1.0,
  )

  assert result.status is MocChainStatus.SOLVER_FAILURE
  assert result.termination_reason is MocChainTerminationReason.SOLVER_ERROR
  assert 'changed consumed state sample' in result.message


def test_post_shock_chain_rejects_a_reused_upstream_field_domain() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)

  def solve_next(_current, _index, handoff):
    solved = _next_chain_field(handoff)
    reused_points = tuple(
      (point[0] - 0.25, point[1])
      for point in solved.field.shock_boundary_points_m
    )
    return MocPostShockChainCellSolve(
      field=replace(solved.field, shock_boundary_points_m=reused_points),
      end_x_m=2.0,
    )

  result = continue_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.7,
    end_x_m=1.0,
  )

  assert result.status is MocChainStatus.SOLVER_FAILURE
  assert result.termination_reason is MocChainTerminationReason.SOLVER_ERROR
  assert 'start strictly downstream' in result.message


def test_post_shock_chain_rejects_a_total_pressure_reset() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)

  def solve_next(_current, _index, handoff):
    solved = _next_chain_field(handoff)
    return MocPostShockChainCellSolve(
      field=replace(
        solved.field,
        upstream_boundary_total_pressure_Pa=(2.0e6,) * 5,
      ),
      end_x_m=2.0,
    )

  result = continue_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.7,
    end_x_m=1.0,
  )

  assert result.status is MocChainStatus.SOLVER_FAILURE
  assert result.termination_reason is MocChainTerminationReason.SOLVER_ERROR
  assert 'reset total pressure' in result.message


def test_open_post_shock_zone_cannot_be_promoted_without_a_shock_edge() -> None:
  shock_fit, continuation, _nodes, _cells = _closed_post_shock_candidate()
  first_layer = assemble_post_shock_first_layer(continuation)
  open_zone = assemble_post_shock_characteristic_zone(
    continuation,
    first_layer,
    shock_fit.boundary_states,
  )

  result = validate_closed_post_shock_field(
    continuation,
    shock_fit,
    open_zone.nodes,
    open_zone.cells,
  )

  assert result.status is MocPostShockClosureStatus.GEOMETRY_FAILURE
  assert not result.converged
  assert 'shock boundary edge' in result.message


def test_post_shock_first_downstream_cross_layer_is_explicitly_partial() -> None:
  continuation = continue_post_shock_characteristics_to_centerline(_prescribed_boundary())

  result = assemble_post_shock_first_layer(continuation)

  assert result.status is MocPostShockFirstLayerStatus.CONVERGED_FIRST_LAYER
  assert result.converged
  assert len(result.crossings) == 3
  assert result.minimum_forward_margin_m is not None
  assert result.minimum_forward_margin_m > 0.0
  assert result.maximum_absolute_invariant_residual is not None
  assert result.maximum_absolute_invariant_residual < 1.0e-10
  assert 'physical closure remain pending' in result.message


def test_post_shock_characteristic_zone_assembles_connected_open_field() -> None:
  samples = _prescribed_boundary()
  continuation = continue_post_shock_characteristics_to_centerline(samples)
  first_layer = assemble_post_shock_first_layer(continuation)

  result = assemble_post_shock_characteristic_zone(
    continuation,
    first_layer,
    samples,
  )

  assert isinstance(result, MocPostShockCharacteristicZoneResult)
  assert result.status is MocPostShockZoneStatus.CONVERGED_OPEN
  assert result.converged
  assert result.characteristic_count == 2
  assert result.node_count == 6
  assert result.cell_count == 5
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.physical_closure_status == 'open'
  assert result.shock_closure_status == 'prescribed-boundary-first-layer'
  assert result.pressure_loss_verified
  assert result.minimum_post_shock_total_pressure_ratio == pytest.approx(0.9)
  assert result.maximum_post_shock_total_pressure_ratio == pytest.approx(0.9)
  assert 'fitted shock closure' in result.message


def test_post_shock_zone_preserves_samplewise_total_pressure_ratios() -> None:
  samples = tuple(
    MocPostShockBoundaryState(
      point_m=sample.point_m,
      state=sample.state,
      upstream_total_pressure_Pa=upstream,
      downstream_total_pressure_Pa=downstream,
    )
    for sample, upstream, downstream in zip(
      _prescribed_boundary(),
      (2.0e6, 2.1e6, 2.0e6, 1.9e6),
      (1.8e6, 1.7e6, 1.6e6, 1.5e6),
      strict=True,
    )
  )
  continuation = continue_post_shock_characteristics_to_centerline(samples)
  first_layer = assemble_post_shock_first_layer(continuation)

  result = assemble_post_shock_characteristic_zone(continuation, first_layer, samples)

  assert result.status is MocPostShockZoneStatus.CONVERGED_OPEN
  assert result.minimum_post_shock_total_pressure_ratio == pytest.approx(1.5 / 1.9)
  assert result.maximum_post_shock_total_pressure_ratio == pytest.approx(0.9)


def test_post_shock_continuation_requires_total_pressure_loss() -> None:
  samples = list(_prescribed_boundary())
  samples[-1] = MocPostShockBoundaryState(
    point_m=samples[-1].point_m,
    state=samples[-1].state,
    upstream_total_pressure_Pa=1.8e6,
    downstream_total_pressure_Pa=1.8e6,
  )

  result = continue_post_shock_characteristics_to_centerline(samples)

  assert result.status is MocPostShockContinuationStatus.INVALID_INPUT
  assert 'strict total-pressure loss' in result.message


def test_post_shock_continuation_requires_centerline_terminal_sample() -> None:
  samples = list(_prescribed_boundary())
  samples[-1] = MocPostShockBoundaryState(
    point_m=(0.82, 0.01),
    state=CharacteristicState(
      x_m=0.82,
      y_m=0.01,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_total_pressure_Pa=2.0e6,
    downstream_total_pressure_Pa=1.8e6,
  )

  result = continue_post_shock_characteristics_to_centerline(samples)

  assert result.status is MocPostShockContinuationStatus.INVALID_INPUT
  assert 'final post-shock boundary sample must lie on the symmetry line' in result.message


def test_strict_chain_mode_rejects_a_prescribed_upstream_boundary() -> None:
  seed_fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=_prescribed_boundary(),
    shock_angle_residuals_rad=(0.0,) * 4,
    maximum_shock_angle_residual_rad=0.0,
  )
  seed_field = assemble_post_shock_characteristic_field(seed_fit)

  result = continue_post_shock_characteristic_chain(
    seed_field,
    lambda _current, _index, _handoff: None,
    start_x_m=0.7,
    end_x_m=1.0,
    require_upstream_shock_coupling=True,
  )

  assert result.status is MocChainStatus.STATE_BOUNDARY
  assert result.termination_reason is MocChainTerminationReason.STATE_NOT_CARRIED
  assert 'upstream shock states' in result.message
