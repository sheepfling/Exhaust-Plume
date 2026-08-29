from __future__ import annotations

from dataclasses import replace
from math import tan

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocChainBoundarySample,
  MocChainTerminationReason,
  MocEulerAmbientCompanionBoundaryStatus,
  MocEulerCompanionFieldStatus,
  MocEulerShockBoundaryOrientation,
  MocEulerShockBoundaryStatus,
  assemble_euler_consistent_companion_characteristic_strip,
  fit_euler_consistent_shock_boundary,
  solve_euler_ambient_companion_boundary_reference,
  solve_attached_compression_to_turn,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_euler_consistent_attached_shock_segment,
)
from exhaust_plume.validation import (
  MocEulerAmbientCompanionBoundaryAuditStatus,
  MocEulerCompanionFieldAuditStatus,
  MocPhysicalFieldEulerAuditStatus,
  measure_moc_ambient_companion_boundary,
  measure_moc_euler_companion_field,
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


def test_solver_owned_ambient_companion_boundary_feeds_the_open_strip() -> None:
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
  shock_boundary = fit_euler_consistent_shock_boundary(
    upstream_states,
    (100000.0,) * len(points),
    points,
    (0.0,) * len(points),
  )

  ambient_pressure = shock_boundary.downstream_total_pressure_Pa[0] / (
    1.0 + 0.5 * (1.4 - 1.0) * 2.0**2
  ) ** (1.4 / (1.4 - 1.0))
  companion = solve_euler_ambient_companion_boundary_reference(
    shock_boundary,
    ambient_pressure,
    separation_m=0.8,
    seed_flow_angle_rad=0.0,
  )

  assert companion.status is MocEulerAmbientCompanionBoundaryStatus.CONVERGED_AMBIENT_COMPANION_BOUNDARY
  assert companion.converged
  assert companion.state_sampling_available
  assert len(companion.samples) == len(points)
  assert companion.maximum_static_pressure_residual is not None
  assert companion.maximum_static_pressure_residual < 1.0e-12
  assert companion.maximum_companion_invariant_residual is not None
  assert companion.maximum_companion_invariant_residual < 1.0e-12
  assert companion.minimum_shock_clearance_m is not None
  assert companion.minimum_shock_clearance_m > 0.79
  assert companion.physical_closure_verified is False
  assert companion.chain_promotion_blocked
  boundary_audit = measure_moc_ambient_companion_boundary(companion)
  assert boundary_audit.status is (
    MocEulerAmbientCompanionBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
  )
  assert boundary_audit.local_boundary_consistency_verified
  assert boundary_audit.sampling_verified
  assert boundary_audit.pressure_verified
  assert boundary_audit.invariant_verified
  assert boundary_audit.geometry_verified
  assert boundary_audit.fidelity_flags_verified
  assert boundary_audit.as_report()['operator_id'] == (
    'op.moc.euler-ambient-companion-boundary-audit'
  )

  field = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    companion.samples,
  )
  assert field.converged
  assert field.companion_boundary_contract_verified
  assert field.pressure_lineage_verified
  audit = measure_moc_euler_companion_field(field)
  assert audit.status is MocEulerCompanionFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.cell_euler_residuals_verified
  assert field.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )
  assert companion.as_report()['status'] == 'converged_ambient_companion_boundary'

  spoofed_boundary = replace(
    companion,
    samples=(
      replace(
        companion.samples[0],
        state=replace(
          companion.samples[0].state,
          y_m=companion.samples[0].state.y_m + 0.01,
        ),
      ),
      *companion.samples[1:],
    ),
  )
  spoofed_boundary_audit = measure_moc_ambient_companion_boundary(
    spoofed_boundary
  )
  assert spoofed_boundary_audit.status is (
    MocEulerAmbientCompanionBoundaryAuditStatus.GEOMETRY_FAILURE
  )
  assert not spoofed_boundary_audit.local_boundary_consistency_verified


def test_euler_companion_strip_uses_explicit_second_characteristic_boundary() -> None:
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
  shock_boundary = fit_euler_consistent_shock_boundary(
    upstream_states,
    (100000.0,) * len(points),
    points,
    (0.0,) * len(points),
  )
  companion = tuple(
    MocChainBoundarySample(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1] + 0.5,
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      pressure,
    )
    for point, pressure in zip(
      points,
      shock_boundary.downstream_total_pressure_Pa,
      strict=True,
    )
  )

  field = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    companion,
  )

  assert field.status is MocEulerCompanionFieldStatus.CONVERGED_OPEN_COMPANION_FIELD
  assert field.converged
  assert field.node_count == len(points)
  assert field.cell_count == len(points) - 1
  assert field.topology.connected
  assert field.topology.forms_closed_zone
  assert field.shock_boundary_local_euler_verified
  assert field.companion_boundary_contract_verified
  assert field.pressure_lineage_verified
  assert field.state_sampling_available
  assert field.physical_closure_verified is False
  assert field.chain_promotion_blocked
  chain_decision = field.as_chain_termination_decision()
  assert chain_decision.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert chain_decision.physical_termination is False
  assert chain_decision.diagnostics['chain_promotion_blocked'] is True
  report = field.as_report()
  assert report['shock_boundary_orientation'] == 'mixed-characteristic-boundary'
  assert report['topology_forms_closed_zone'] is True
  assert report['chain_termination_decision']['reason'] == 'open-physical-closure'

  audit = measure_moc_euler_companion_field(field)
  assert audit.status is MocEulerCompanionFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.converged
  assert audit.local_euler_consistency_verified
  assert audit.shock_jump_verified
  assert audit.cell_euler_residuals_finite
  assert audit.field_topology_verified
  assert audit.boundary_geometry_verified
  assert audit.pressure_lineage_verified
  assert audit.promotion_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.as_report()['operator_id'] == 'op.moc.euler-companion-field-audit'

  spoofed = replace(field, chain_promotion_blocked=False)
  spoofed_audit = measure_moc_euler_companion_field(spoofed)
  assert spoofed_audit.status is MocEulerCompanionFieldAuditStatus.FIELD_FAILURE
  assert not spoofed_audit.local_euler_consistency_verified

  bad_companion = list(companion)
  bad_companion[0] = MocChainBoundarySample(
    bad_companion[0].state,
    bad_companion[0].total_pressure_Pa * 1.01,
  )
  rejected = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    bad_companion,
  )
  assert rejected.status is MocEulerCompanionFieldStatus.PRESSURE_FAILURE
  assert not rejected.converged
  assert rejected.chain_promotion_blocked
