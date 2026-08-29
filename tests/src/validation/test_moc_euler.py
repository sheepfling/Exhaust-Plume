from __future__ import annotations

from dataclasses import replace

from exhaust_plume.models.moc import (
  CharacteristicState,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
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
