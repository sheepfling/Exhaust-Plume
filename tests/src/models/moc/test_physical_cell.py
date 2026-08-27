from __future__ import annotations

from dataclasses import replace
from math import pi, tan

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientBoundarySample,
  MocPhysicalPostShockFieldStatus,
  MocPostShockBoundaryState,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
  assemble_ambient_boundary_post_shock_field,
  march_post_shock_ambient_boundary,
  solve_marched_attached_shock_field,
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
