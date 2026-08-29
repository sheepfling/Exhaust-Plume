from __future__ import annotations

from dataclasses import replace
from math import tan

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocEulerShockBoundaryOrientation,
  MocEulerShockBoundaryStatus,
  fit_euler_consistent_shock_boundary,
  solve_attached_compression_to_turn,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_euler_consistent_attached_shock_segment,
)
from exhaust_plume.validation import (
  MocPhysicalFieldEulerAuditStatus,
  measure_moc_physical_field_euler_audit,
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


def test_euler_audit_reports_nonconservative_reference_and_retains_cells() -> None:
  field = _canonical_field()

  audit = measure_moc_physical_field_euler_audit(field)

  assert audit.status is MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE
  assert not audit.converged
  assert not audit.shock_jump_verified
  assert audit.cell_euler_residuals_finite
  assert len(audit.cell_euler_residuals) == field.cell_count
  assert not audit.local_euler_consistency_verified
  assert audit.maximum_shock_jump_mass_residual is not None
  assert audit.maximum_shock_jump_mass_residual > 0.1
  assert audit.physical_closure_verified is False
  assert audit.canonical_euler_verified is False
  assert audit.chain_promotion_blocked


def test_euler_audit_rejects_an_open_or_incomplete_field() -> None:
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

  audit = measure_moc_physical_field_euler_audit(shock)

  assert audit.status is MocPhysicalFieldEulerAuditStatus.INVALID_INPUT


def test_euler_consistent_shock_segment_closes_its_local_jump() -> None:
  segment = solve_euler_consistent_attached_shock_segment(
    CharacteristicState(
      x_m=0.5,
      y_m=0.5,
      theta_rad=0.2,
      mach=2.0,
      gamma=1.4,
    ),
    100000.0,
    0.0,
  )

  assert segment.status is MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK
  assert segment.converged
  assert segment.local_euler_verified
  assert segment.shock_end_m is not None
  assert segment.shock_end_m[0] > segment.shock_start_m[0]
  assert segment.shock_end_m[1] == 0.0
  assert segment.maximum_shock_jump_residual is not None
  assert segment.maximum_shock_jump_residual < 1.0e-10
  assert segment.physical_closure_verified is False
  assert segment.chain_promotion_blocked


def test_euler_consistent_shock_segment_rejects_the_reference_turn_direction() -> None:
  segment = solve_euler_consistent_attached_shock_segment(
    CharacteristicState(
      x_m=0.5,
      y_m=0.5,
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    100000.0,
    0.0,
  )

  assert segment.status is MocEulerShockBoundaryStatus.NONCOMPRESSIVE_TURN
  assert segment.converged is False
  assert segment.chain_promotion_blocked


def test_euler_consistent_shock_curve_records_mach_cone_orientation() -> None:
  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.2,
  )
  assert compression.beta_rad is not None
  shock_angle = 0.2 - compression.beta_rad
  points = tuple(
    (0.5 + index * (-0.1 / tan(shock_angle)), 0.5 - index * 0.1)
    for index in range(6)
  )
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )

  curve = fit_euler_consistent_shock_boundary(
    upstream_states,
    (100000.0,) * len(points),
    points,
    (0.0,) * len(points),
  )

  assert curve.status is MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK
  assert curve.converged
  assert curve.local_euler_verified
  assert curve.orientation is MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
  assert curve.companion_boundary_required
  assert not curve.two_family_cauchy_geometry_verified
  assert curve.maximum_shock_jump_residual is not None
  assert curve.maximum_shock_jump_residual < 1.0e-10
  assert curve.maximum_tangent_residual_rad is not None
  assert curve.maximum_tangent_residual_rad < 1.0e-10
  assert curve.physical_closure_verified is False
  assert curve.chain_promotion_blocked
  report = curve.as_report()
  assert report['orientation'] == 'mixed-characteristic-boundary'
  assert report['companion_boundary_required'] is True


def test_euler_consistent_shock_curve_rejects_reference_turn_direction() -> None:
  points = ((0.5, 0.5), (0.7, 0.4))
  result = fit_euler_consistent_shock_boundary(
    tuple(
      CharacteristicState(x_m=x, y_m=y, theta_rad=-0.2, mach=2.0, gamma=1.4)
      for x, y in points
    ),
    (100000.0, 100000.0),
    points,
    (0.0, 0.0),
  )

  assert result.status is MocEulerShockBoundaryStatus.NONCOMPRESSIVE_TURN
  assert not result.converged
  assert result.chain_promotion_blocked
