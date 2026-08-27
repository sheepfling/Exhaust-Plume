from __future__ import annotations

from dataclasses import replace
from math import pi, tan

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientBoundarySample,
  MocChainContinuationPolicy,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCharacteristicCell,
  MocPhysicalPostShockFieldResult,
  MocPhysicalPostShockFieldStatus,
  MocPhysicalPostShockFieldContinuationSolve,
  MocPostShockBoundaryState,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
  assemble_ambient_boundary_post_shock_field,
  continue_ambient_closed_post_shock_chain,
  march_post_shock_ambient_boundary,
  plan_ambient_closed_post_shock_chain,
  solve_marched_attached_shock_field,
  validate_ambient_pressure_boundary,
  validate_moc_mesh,
)


def _shock_fit() -> MocShockBoundaryFitResult:
  points = ((0.0, 0.5), (0.2, 0.25), (0.4, 0.0))
  states = tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    )
    for point in points
  )
  return MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=states,
    shock_angle_residuals_rad=(0.0,) * len(states),
    maximum_shock_angle_residual_rad=0.0,
  )


def test_coupled_post_shock_field_rejects_an_outer_boundary_without_axis_end() -> None:
  ambient_pressure = 100000.0
  mach = 2.0
  gamma = 1.4
  total_pressure = ambient_pressure * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (gamma / (gamma - 1.0))
  boundary = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=0.0,
        mach=mach,
        gamma=gamma,
      ),
      total_pressure_Pa=total_pressure,
    )
    for index in range(3)
  )

  result = assemble_ambient_boundary_post_shock_field(
    _shock_fit(),
    boundary,
    ambient_pressure,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE
  assert not result.converged
  assert 'ambient boundary must terminate' in result.message


def test_coupled_post_shock_field_requires_an_accepted_ambient_trace() -> None:
  boundary = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=pi / 4.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.8e6,
    )
    for index in range(3)
  )

  result = assemble_ambient_boundary_post_shock_field(
    _shock_fit(),
    boundary,
    100000.0,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.AMBIENT_BOUNDARY_FAILURE
  assert not result.converged
  assert result.ambient_boundary.pressure_residuals


def test_legacy_ambient_field_cannot_promote_without_family_orientation_evidence() -> None:
  boundary = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=pi / 4.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.8e6,
    )
    for index in range(3)
  )
  result = assemble_ambient_boundary_post_shock_field(
    _shock_fit(),
    boundary,
    100000.0,
  )
  legacy_converged = replace(
    result,
    status=MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED,
    message='synthetic legacy promotion probe',
  )

  assert legacy_converged.converged
  assert legacy_converged.physical_closure_verified is False
  with pytest.raises(ValueError, match='family orientation'):
    legacy_converged.as_chain_cell(start_x_m=0.0, end_x_m=1.0)


def test_coupled_post_shock_field_accepts_an_explicit_axis_corner_before_axis_gate() -> None:
  shock = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.converged
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  march = march_post_shock_ambient_boundary(
    shock.shock_fit,
    ambient_pressure,
  )
  assert march.converged
  last = march.boundary_samples[-1]
  axis_state = CharacteristicState(
    x_m=last.point_m[0] - last.point_m[1] / tan(0.5 * last.state.theta_rad),
    y_m=0.0,
    theta_rad=0.0,
    mach=last.state.mach,
    gamma=last.state.gamma,
  )
  axis_corner = MocAmbientBoundarySample(
    point_m=(axis_state.x_m, axis_state.y_m),
    state=axis_state,
    total_pressure_Pa=last.total_pressure_Pa,
  )

  result = assemble_ambient_boundary_post_shock_field(
    shock.shock_fit,
    (*march.boundary_samples, axis_corner),
    ambient_pressure,
    position_tolerance_m=1.0e-3,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.AXIS_FAILURE
  assert result.ambient_boundary.converged
  assert result.node_count == 45
  assert result.cell_count == 45
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.ambient_boundary_points_m[-1] == axis_corner.point_m
  assert result.centerline_boundary_points_m[-1] == axis_corner.point_m


def _manufactured_closed_physical_field(
  incoming_handoff: tuple = (),
):
  """Build a small accepted field to exercise the physical chain adapter.

  The characteristic-cell assembler is tested independently above.  This
  manufactured result keeps the chain test focused on its handoff contract;
  it is never used by a product provider or validation report.
  """

  ambient_pressure = 100000.0
  gamma = 1.4
  mach = 2.0
  total_pressure = ambient_pressure * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (gamma / (gamma - 1.0))
  centerline_points = ((0.0, 0.0), (0.5, 0.0), (1.0, 0.0))
  centerline_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=0.0,
      mach=mach,
      gamma=gamma,
    )
    for point in centerline_points
  )
  shock_points = ((0.0, 0.8), (0.5, 0.4), (1.0, 0.0))
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.1,
      mach=mach,
      gamma=gamma,
    )
    for point in shock_points
  )
  ambient_samples = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 1.0),
      state=CharacteristicState(
        x_m=float(index),
        y_m=1.0,
        theta_rad=0.0,
        mach=mach,
        gamma=gamma,
      ),
      total_pressure_Pa=total_pressure,
    )
    for index in range(3)
  )
  ambient_boundary = validate_ambient_pressure_boundary(
    ambient_samples,
    ambient_pressure,
  )
  assert ambient_boundary.converged
  cell = MocCharacteristicCell(
    cell_index=0,
    cell_kind='manufactured-physical-chain-test-cell',
    vertices_xr_m=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
    centerline_indices=(0, 1),
    boundary_indices=(0, 1),
  )
  return MocPhysicalPostShockFieldResult(
    status=MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED,
    characteristic_layer_count=2,
    nodes=(),
    cells=(cell,),
    topology=validate_moc_mesh((cell,)),
    shock_boundary_points_m=shock_points,
    ambient_boundary_points_m=tuple(sample.point_m for sample in ambient_samples),
    centerline_boundary_points_m=centerline_points,
    centerline_boundary_states=centerline_states,
    centerline_boundary_total_pressure_Pa=(180000.0, 175000.0, 170000.0),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=0.0,
    maximum_absolute_invariant_residual=0.0,
    minimum_post_shock_total_pressure_ratio=0.8,
    maximum_post_shock_total_pressure_ratio=0.9,
    characteristic_family_orientation_verified=True,
    incoming_handoff_states=tuple(sample.state for sample in incoming_handoff),
    incoming_handoff_total_pressure_Pa=tuple(
      sample.total_pressure_Pa for sample in incoming_handoff
    ),
    upstream_shock_boundary_states=upstream_states,
    upstream_shock_boundary_total_pressure_Pa=(200000.0, 200000.0, 200000.0),
  )


def test_ambient_closed_physical_chain_requires_exact_incoming_handoff() -> None:
  seed = _manufactured_closed_physical_field()

  def solve_next(current, _next_index, _incoming):
    wrong_handoff = tuple(
      replace(sample, total_pressure_Pa=sample.total_pressure_Pa + 1.0)
      for sample in current.continuation_boundary
    )
    return MocPhysicalPostShockFieldContinuationSolve(
      field=_manufactured_closed_physical_field(wrong_handoff),
      end_x_m=current.end_x_m + 1.0,
    )

  result = continue_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=0.0,
    end_x_m=1.0,
    policy=MocChainContinuationPolicy(max_cells=2),
  )

  assert result.status.value == 'solver-failure'
  assert result.termination_reason is MocChainTerminationReason.SOLVER_ERROR
  assert result.cell_count == 1
  assert 'changed consumed total pressure sample' in result.message


def test_ambient_closed_physical_chain_and_planner_carry_multiple_cells() -> None:
  seed = _manufactured_closed_physical_field()

  def solve_next(current, next_index, incoming_handoff):
    if next_index > 3:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message='manufactured physical-field test chain exhausted',
      )
    return MocPhysicalPostShockFieldContinuationSolve(
      field=_manufactured_closed_physical_field(incoming_handoff),
      end_x_m=current.end_x_m + 1.0,
    )

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=0.0,
    end_x_m=1.0,
    policy=MocChainContinuationPolicy(max_cells=8),
  )
  report = planner.as_report()

  assert planner.production_claim_allowed is False
  assert planner.handoff_links_verified is True
  assert planner.chain.resolved is True
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert [step.result_kind for step in planner.steps] == [
    'physical-field-solve-returned',
    'physical-field-solve-returned',
    'termination-returned',
  ]
  assert report['steps'][1]['incoming_handoff_link_verified'] is True


def test_ambient_closed_physical_chain_rejects_open_seed_before_callback() -> None:
  seed = _manufactured_closed_physical_field()
  open_seed = replace(seed, characteristic_family_orientation_verified=False)
  called = False

  def solve_next(_current, _next_index, _incoming):
    nonlocal called
    called = True
    return None

  result = continue_ambient_closed_post_shock_chain(
    open_seed,
    solve_next,
    start_x_m=0.0,
    end_x_m=1.0,
  )

  assert result.status.value == 'open-cell'
  assert result.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert called is False
