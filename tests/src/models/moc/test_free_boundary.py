from __future__ import annotations

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
  solve_uniform_attached_shock_field,
)


def _uniform_reference(sample_count: int):
  return solve_uniform_attached_shock_field(
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
    sample_count=sample_count,
  )


def test_marched_attached_shock_generates_and_closes_the_field() -> None:
  result = _uniform_reference(17)

  assert result.status is MocFreeBoundaryShockStatus.CONVERGED_FIELD
  assert result.converged
  assert result.physical_closure_verified
  assert result.sample_count == 17
  assert result.endpoint_m is not None
  assert result.endpoint_m[1] == pytest.approx(0.0, abs=1.0e-12)
  assert result.maximum_shock_angle_residual_rad is not None
  assert result.maximum_shock_angle_residual_rad < 1.0e-2
  assert result.field is not None
  assert result.field.converged
  assert result.field.topology.forms_closed_zone
  assert result.field.topology.nonmanifold_edge_count == 0
  assert result.field.shock_closure_status == 'solver-generated-marched-attached-shock'
  assert result.field.pressure_loss_verified
  assert result.field.as_chain_cell(start_x_m=0.5, end_x_m=1.0).resolved


def test_marched_attached_shock_refines_endpoint_and_tangent_residual() -> None:
  coarse = _uniform_reference(9)
  medium = _uniform_reference(17)
  fine = _uniform_reference(33)

  assert coarse.converged and medium.converged and fine.converged
  assert coarse.maximum_shock_angle_residual_rad is not None
  assert medium.maximum_shock_angle_residual_rad is not None
  assert fine.maximum_shock_angle_residual_rad is not None
  assert medium.maximum_shock_angle_residual_rad < coarse.maximum_shock_angle_residual_rad
  assert fine.maximum_shock_angle_residual_rad < medium.maximum_shock_angle_residual_rad
  assert coarse.endpoint_m is not None
  assert medium.endpoint_m is not None
  assert fine.endpoint_m is not None
  assert abs(fine.endpoint_m[0] - medium.endpoint_m[0]) < abs(
    medium.endpoint_m[0] - coarse.endpoint_m[0]
  )


def test_uniform_constant_turn_rejects_zero_area_field() -> None:
  result = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.0,
    sample_count=9,
  )

  assert result.status is MocFreeBoundaryShockStatus.FIELD_FAILURE
  assert not result.converged
  assert result.field is not None
  assert 'zero_area' in result.message


def test_marched_shock_rejects_an_upstream_state_not_at_the_shock_point() -> None:
  result = solve_marched_attached_shock_field(
    lambda _point: CharacteristicState(0.0, 0.5, -0.2, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_rad=0.0,
    sample_count=5,
  )

  assert result.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  assert not result.converged
  assert 'does not lie' in result.message
