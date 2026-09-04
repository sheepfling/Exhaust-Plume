from __future__ import annotations

from dataclasses import replace
from math import tan

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocChainBoundarySample,
  MocChainPlannerKind,
  MocChainStatus,
  MocChainTerminationReason,
  MocEulerCompanionFieldChainMock,
  MocEulerAmbientBoundaryMarchStatus,
  MocEulerAmbientCompanionBoundaryStatus,
  MocEulerAmbientShockFieldStatus,
  MocEulerAmbientShockFieldChainMock,
  MocEulerAmbientAttachmentWedgeStatus,
  MocEulerCompanionFieldStatus,
  MocEulerShockBoundaryOrientation,
  MocEulerShockBoundaryStatus,
  assemble_euler_ambient_shock_field,
  assemble_euler_ambient_shock_field_from_companion,
  assemble_euler_consistent_companion_characteristic_strip,
  fit_euler_consistent_shock_boundary,
  march_euler_ambient_boundary,
  plan_euler_companion_field_chain_probe,
  plan_euler_companion_field_chain_mock,
  plan_euler_companion_field_reference,
  plan_euler_ambient_shock_field_chain_mock,
  plan_euler_ambient_shock_field_reference,
  solve_euler_ambient_companion_boundary_reference,
  solve_attached_compression_to_turn,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_euler_consistent_attached_shock_segment,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.validation import (
  MocEulerAmbientCompanionBoundaryAuditStatus,
  MocEulerAmbientShockFieldAuditStatus,
  MocEulerAmbientShockFieldChainAuditStatus,
  MocEulerCompanionFieldAuditStatus,
  MocEulerCompanionFieldChainAuditStatus,
  MocEulerCompanionFieldChainRefinementCase,
  MocEulerCompanionFieldChainRefinementMeasurementStatus,
  MocPhysicalFieldEulerAuditStatus,
  measure_moc_ambient_companion_boundary,
  measure_moc_euler_ambient_shock_field,
  measure_moc_euler_ambient_shock_field_chain,
  measure_moc_chain_planner,
  measure_moc_euler_companion_field,
  measure_moc_euler_companion_field_chain,
  measure_moc_euler_companion_field_chain_refinement,
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
####


def _euler_companion_field_for_resolution(sample_count: int):
  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.2,
  )
  assert compression.beta_rad is not None
  shock_angle = 0.2 - compression.beta_rad
  points = tuple(
    (
      0.5 + index * (-0.5 / (sample_count - 1) / tan(shock_angle)),
      0.5 - index * (0.5 / (sample_count - 1)),
    )
    for index in range(sample_count)
  )
  shock_boundary = fit_euler_consistent_shock_boundary(
    tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.2,
        mach=2.0,
        gamma=1.4,
      )
      for point in points
    ),
    (100000.0,) * sample_count,
    points,
    (0.0,) * sample_count,
  )
  ambient_pressure = shock_boundary.downstream_total_pressure_Pa[0] / (
    1.0 + 0.5 * (1.4 - 1.0) * 2.0**2
  ) ** (1.4 / (1.4 - 1.0))
  companion = solve_euler_ambient_companion_boundary_reference(
    shock_boundary,
    ambient_pressure,
    separation_m=0.8,
  )
  return assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    companion.samples,
  )
####


def _euler_exact_ambient_fixture(sample_count: int = 6):
  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.2,
  )
  assert compression.beta_rad is not None
  shock_angle = 0.2 - compression.beta_rad
  points = tuple(
    (
      0.5 + index * (-0.1 / (sample_count - 1) / tan(shock_angle)),
      0.5 - index * (0.1 / (sample_count - 1)),
    )
    for index in range(sample_count)
  )
  shock_boundary = fit_euler_consistent_shock_boundary(
    tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.2,
        mach=2.0,
        gamma=1.4,
      )
      for point in points
    ),
    (100000.0,) * sample_count,
    points,
    (0.0,) * sample_count,
  )
  assert shock_boundary.converged
  return shock_boundary, shock_boundary.downstream_static_pressure_Pa[0]
####


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
####


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
####


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
####


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
####


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
####


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
####


def test_exact_euler_ambient_march_closes_pressure_and_tangent_boundary() -> None:
  shock_boundary, ambient_pressure = _euler_exact_ambient_fixture()

  march = march_euler_ambient_boundary(shock_boundary, ambient_pressure)

  assert march.status is MocEulerAmbientBoundaryMarchStatus.CONVERGED
  assert march.converged
  assert march.state_sampling_available
  assert len(march.boundary_samples) == len(shock_boundary.shock_points_m)
  assert march.ambient_boundary.converged
  assert march.maximum_absolute_pressure_residual is not None
  assert march.maximum_absolute_pressure_residual < 1.0e-10
  assert march.maximum_absolute_invariant_residual is not None
  assert march.maximum_absolute_invariant_residual < 1.0e-10
  assert march.physical_closure_verified is False
  assert march.chain_promotion_blocked
  assert march.production_claim_allowed is False
  assert march.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )
####


def test_exact_euler_ambient_field_blocks_generic_attachment_stencil() -> None:
  shock_boundary, ambient_pressure = _euler_exact_ambient_fixture()

  field = assemble_euler_ambient_shock_field(
    shock_boundary,
    ambient_pressure,
  )
  audit = measure_moc_euler_ambient_shock_field(field)

  assert field.status is MocEulerAmbientShockFieldStatus.ATTACHMENT_GEOMETRY_FAILURE
  assert not field.converged
  assert field.ambient_march is not None
  assert field.ambient_march.converged
  assert field.attachment_wedge is not None
  assert field.attachment_wedge.status is (
    MocEulerAmbientAttachmentWedgeStatus.NO_FORWARD_INTERSECTION
  )
  assert len(field.attachment_wedge.trials) == 5
  assert not any(trial.accepted for trial in field.attachment_wedge.trials)
  assert field.field is None
  assert field.physical_closure_verified is False
  assert field.chain_promotion_blocked
  assert field.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  assert audit.status is MocEulerAmbientShockFieldAuditStatus.FIELD_FAILURE
  assert not audit.converged
  assert audit.shock_geometry_verified
  assert audit.shock_jump_verified
  assert audit.ambient_sample_alignment_verified
  assert audit.ambient_direction_verified
  assert audit.ambient_boundary_verified
  assert audit.entropy_lineage_verified
  assert not audit.companion_field_verified
  assert audit.promotion_flags_verified
  assert audit.maximum_shock_jump_mass_residual is not None
  assert audit.maximum_shock_jump_mass_residual < 1.0e-8
  assert audit.maximum_ambient_pressure_residual is not None
  assert audit.maximum_ambient_pressure_residual < 1.0e-10
  assert audit.as_report()['operator_id'] == (
    'op.moc.euler-ambient-shock-field-audit'
  )
####


def test_exact_euler_ambient_field_planner_retains_attachment_stop() -> None:
  shock_boundary, ambient_pressure = _euler_exact_ambient_fixture()
  field = assemble_euler_ambient_shock_field(
    shock_boundary,
    ambient_pressure,
  )

  reference = plan_euler_ambient_shock_field_reference(field)
  chain = plan_euler_ambient_shock_field_chain_mock(
    field,
    mock=MocEulerAmbientShockFieldChainMock(
      total_field_count=3,
      axial_translation_m=2.0,
    ),
  )
  audit = measure_moc_euler_ambient_shock_field_chain(chain)

  assert reference.resolved is False
  assert reference.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert reference.diagnostics['continued_cell_callback_invoked'] is False
  assert chain.field_count == 1
  assert chain.continued_field_count == 0
  assert chain.steps == ()
  assert chain.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert chain.chain_promotion_blocked
  assert chain.physical_closure_verified is False
  assert chain.production_claim_allowed is False
  assert audit.status is MocEulerAmbientShockFieldChainAuditStatus.FIELD_FAILURE
  assert not audit.converged
  assert audit.field_count == 1
  assert audit.field_audits_verified is False
  assert audit.chain_promotion_blocked
  assert audit.as_report()['operator_id'] == (
    'op.moc.euler-ambient-shock-field-chain-audit'
  )
####


def test_explicit_companion_exact_field_supports_audited_open_chain_mock() -> None:
  shock_boundary, ambient_pressure = _euler_exact_ambient_fixture()
  companion = solve_euler_ambient_companion_boundary_reference(
    shock_boundary,
    ambient_pressure,
    separation_m=0.8,
  )

  field = assemble_euler_ambient_shock_field_from_companion(
    shock_boundary,
    companion,
  )
  field_audit = measure_moc_euler_ambient_shock_field(field)
  chain = plan_euler_ambient_shock_field_chain_mock(
    field,
    mock=MocEulerAmbientShockFieldChainMock(
      total_field_count=3,
      axial_translation_m=2.0,
    ),
  )
  chain_audit = measure_moc_euler_ambient_shock_field_chain(chain)

  assert field.converged
  assert field.ambient_march is None
  assert field.ambient_companion_boundary is companion
  assert field_audit.converged
  assert field_audit.ambient_boundary_kind == (
    'explicit-separated-companion'
  )
  assert field_audit.ambient_sample_alignment_verified
  assert field_audit.ambient_direction_verified
  assert field_audit.ambient_boundary_verified
  assert chain.resolved
  assert chain.field_count == 3
  assert chain.continued_field_count == 2
  assert chain.handoff_links_verified
  assert chain.termination.reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert chain_audit.converged
  assert chain_audit.local_sequence_verified
  assert not chain.physical_closure_verified
  assert chain.chain_promotion_blocked
####


def test_exact_euler_ambient_march_rejects_reference_ambient_attachment() -> None:
  shock_boundary, _ = _euler_exact_ambient_fixture()
  reference_ambient_pressure = shock_boundary.downstream_total_pressure_Pa[0] / (
    1.0 + 0.5 * (1.4 - 1.0) * 2.0**2
  ) ** (1.4 / (1.4 - 1.0))

  march = march_euler_ambient_boundary(
    shock_boundary,
    reference_ambient_pressure,
  )

  assert march.status is MocEulerAmbientBoundaryMarchStatus.ATTACHMENT_FAILURE
  assert not march.converged
  assert march.attachment_relative_pressure_residual is not None
  assert abs(march.attachment_relative_pressure_residual) > 0.1
  assert march.chain_promotion_blocked
####


def test_exact_euler_ambient_field_requires_entropy_transport_for_variable_p0() -> None:
  shock_boundary, ambient_pressure = _euler_exact_ambient_fixture()
  variable_pressure = tuple(
    pressure if index == 0 else pressure * (1.0 - 0.01 * index)
    for index, pressure in enumerate(shock_boundary.downstream_total_pressure_Pa)
  )
  variable_upstream_pressure = tuple(
    pressure * (1.0 - 0.01 * index)
    for index, pressure in enumerate(shock_boundary.upstream_total_pressure_Pa)
  )
  variable_shock = replace(
    shock_boundary,
    upstream_total_pressure_Pa=variable_upstream_pressure,
    downstream_total_pressure_Pa=variable_pressure,
  )

  field = assemble_euler_ambient_shock_field(
    variable_shock,
    ambient_pressure,
  )
  audit = measure_moc_euler_ambient_shock_field(field)

  assert field.status is MocEulerAmbientShockFieldStatus.ENTROPY_TRANSPORT_REQUIRED
  assert field.field is None
  assert field.ambient_march is not None
  assert field.ambient_march.converged
  assert field.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  assert audit.status is MocEulerAmbientShockFieldAuditStatus.ENTROPY_FAILURE
  assert audit.ambient_boundary_verified
  assert not audit.entropy_lineage_verified
  assert audit.maximum_entropy_residual is not None
  assert audit.maximum_entropy_residual > 1.0e-3
  assert audit.chain_promotion_blocked
####


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
####


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
####


def test_euler_companion_field_has_a_typed_planner_boundary_without_chain_promotion() -> None:
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
  shock_boundary = fit_euler_consistent_shock_boundary(
    tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.2,
        mach=2.0,
        gamma=1.4,
      )
      for point in points
    ),
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
  )
  field = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    companion.samples,
  )

  field_planner = plan_euler_companion_field_reference(field)
  assert field_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert field_planner.resolved
  assert field_planner.physical_closure_verified is False
  assert field_planner.chain_promotion_blocked
  assert field_planner.termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert field_planner.diagnostics['continued_cell_callback_invoked'] is False

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
  assert generated.field is not None
  chain_planner = plan_euler_companion_field_chain_probe(
    generated.field,
    field,
    start_x_m=0.5,
    end_x_m=1.0,
  )
  assert chain_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert chain_planner.chain.status is MocChainStatus.SOLVER_TERMINATED
  assert chain_planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert chain_planner.chain.physical_termination is False
  assert chain_planner.chain.cell_count == 1
  assert chain_planner.chain.resolved
  assert chain_planner.steps[0].result_kind == 'termination-returned'
  assert chain_planner.steps[0].result_termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert chain_planner.diagnostics['euler_field_consumed_as_chain_seed'] is False
  assert chain_planner.diagnostics['upstream_field_replacement_policy'] == (
    'never-replace-on-boundary-probe'
  )

  planner_audit = measure_moc_chain_planner(chain_planner)
  assert planner_audit.converged
  assert planner_audit.termination_verified
  assert planner_audit.fidelity_isolation_verified
  assert planner_audit.physical_termination is False
  assert planner_audit.production_claim_allowed is False
####


def test_euler_companion_field_chain_mock_repeats_open_frontiers_without_promotion() -> None:
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
  shock_boundary = fit_euler_consistent_shock_boundary(
    tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.2,
        mach=2.0,
        gamma=1.4,
      )
      for point in points
    ),
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
  )
  field = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    companion.samples,
  )

  planner = plan_euler_companion_field_chain_mock(
    field,
    mock=MocEulerCompanionFieldChainMock(
      total_field_count=3,
      axial_translation_m=2.0,
    ),
  )
  audit = measure_moc_euler_companion_field_chain(planner)

  assert planner.resolved
  assert planner.field_count == 3
  assert planner.continued_field_count == 2
  assert planner.handoff_links_verified is True
  assert planner.termination.reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert [step.result_kind for step in planner.steps] == [
    'field-solve-returned',
    'field-solve-returned',
    'termination-returned',
  ]
  assert [field.shock_boundary_points_m[0][0] for field in planner.fields] == pytest.approx(
    (0.5, 2.5, 4.5)
  )
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert audit.status is MocEulerCompanionFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.local_sequence_verified
  assert audit.as_report()['operator_id'] == (
    'op.moc.euler-companion-field-chain-audit'
  )
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False
####


def test_euler_companion_field_chain_refinement_remeasures_topology_and_shape() -> None:
  cases = tuple(
    MocEulerCompanionFieldChainRefinementCase(
      resolution=sample_count,
      chain=plan_euler_companion_field_chain_mock(
        _euler_companion_field_for_resolution(sample_count),
        mock=MocEulerCompanionFieldChainMock(
          total_field_count=3,
          axial_translation_m=2.0,
        ),
      ),
    )
    for sample_count in (9, 17, 33)
  )

  measurement = measure_moc_euler_companion_field_chain_refinement(
    cases,
    expected_resolutions=(9, 17, 33),
  )

  assert measurement.status is (
    MocEulerCompanionFieldChainRefinementMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.resolutions == (9, 17, 33)
  assert measurement.expected_resolutions_verified
  assert measurement.resolution_order_verified
  assert measurement.field_count == 3
  assert measurement.continued_field_count == 2
  assert measurement.field_count_consistent
  assert measurement.continued_field_count_consistent
  assert measurement.step_count_consistent
  assert measurement.sample_resolution_verified
  assert measurement.topology_verified
  assert measurement.geometry_shape_verified
  assert measurement.field_euler_audits_verified
  assert measurement.handoff_links_verified is True
  assert measurement.termination_sensitivity_verified is True
  assert measurement.fidelity_flags_verified
  assert measurement.cell_residual_trend_verified
  assert measurement.refinement_convergence_verified
  assert measurement.field_node_counts == ((9, 9, 9), (17, 17, 17), (33, 33, 33))
  assert measurement.field_cell_counts == ((8, 8, 8), (16, 16, 16), (32, 32, 32))
  assert all(
    residual <= 1.0e-10
    for residual in (
      *measurement.axial_extent_residuals_m,
      *measurement.shock_endpoint_residuals_m,
      *measurement.companion_endpoint_residuals_m,
      *measurement.interior_endpoint_residuals_m,
    )
  )
  assert measurement.maximum_cell_euler_residuals[0] > (
    measurement.maximum_cell_euler_residuals[-1]
  )
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.as_report()['operator_id'] == (
    'op.moc.euler-companion-field-chain-refinement'
  )

  out_of_order = measure_moc_euler_companion_field_chain_refinement(
    tuple(reversed(cases)),
    expected_resolutions=(9, 17, 33),
  )
  assert out_of_order.status is (
    MocEulerCompanionFieldChainRefinementMeasurementStatus.RESOLUTION_FAILURE
  )
  assert not out_of_order.converged
####
