from __future__ import annotations

from dataclasses import replace
from math import atan2, cos, log, pi, sin, sqrt

import pytest

from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainGeometryFidelity,
  MocTransonicCharacteristicTransportRequest,
  MocTransonicCharacteristicTransportStatus,
  MocTransonicCharacteristicTransportTermination,
  MocTransonicPlacementRequest,
  MocTransonicPlacementStatus,
  MocTransonicShockInterfaceRequest,
  MocTransonicShockInterfaceStatus,
  MocTransonicShockFieldAttachmentRequest,
  MocTransonicShockFieldAttachmentStatus,
  MocTransonicShockState,
  assemble_euler_ambient_physical_field,
  fit_euler_consistent_shock_boundary,
  solve_euler_ambient_first_wedge_characteristic_remesh,
  solve_euler_ambient_first_wedge_entropy_carry,
  solve_euler_ambient_first_wedge_entropy_characteristic_field,
  solve_attached_compression_to_turn,
  solve_moc_transonic_characteristic_transport,
  solve_moc_transonic_placement,
  solve_moc_transonic_shock_interface,
  solve_moc_transonic_shock_field_attachment,
)
from exhaust_plume.validation import (
  measure_moc_transonic_characteristic_transport,
  measure_moc_transonic_shock_interface,
  measure_moc_transonic_placement,
  measure_moc_transonic_shock_field_attachment,
)


def _internal_field():
  sample_count = 9
  points = tuple(
    (
      0.5 + 4.93 * distance - 3.36 * distance * distance,
      0.5 - distance,
    )
    for distance in (
      index * 0.5 / (sample_count - 1)
      for index in range(sample_count)
    )
  )
  turns = (0.005, 0.14, 0.20, 0.22, 0.22, 0.20, 0.18, 0.17, 0.081637491676426)
  tangent_angles = tuple(
    atan2(second[1] - first[1], second[0] - first[0])
    for first, second in (
      (points[0], points[1]),
      *zip(points[:-2], points[2:]),
      (points[-2], points[-1]),
    )
  )
  upstream_states = []
  for point, turn, tangent_angle in zip(
    points,
    turns,
    tangent_angles,
    strict=True,
  ):
    compression = solve_attached_compression_to_turn(
      upstream_mach=2.0,
      gamma=1.4,
      upstream_pressure_Pa=100000.0,
      target_turn_rad=turn,
    )
    assert compression.beta_rad is not None
    upstream_states.append(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=tangent_angle + compression.beta_rad,
        mach=2.0,
        gamma=1.4,
      )
    )
  ####
  shock = fit_euler_consistent_shock_boundary(
    tuple(upstream_states),
    (100000.0,) * sample_count,
    points,
    tuple(
      state.theta_rad - turn
      for state, turn in zip(upstream_states, turns, strict=True)
    ),
  )
  physical_field = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )
  candidate = solve_euler_ambient_first_wedge_characteristic_remesh(physical_field)
  entropy_trial = solve_euler_ambient_first_wedge_entropy_carry(candidate)
  return solve_euler_ambient_first_wedge_entropy_characteristic_field(
    entropy_trial
  )
####


def _shock_state_for_node(node) -> MocTransonicShockState:
  gamma = node.state.gamma
  gas_constant = 287.05
  total_temperature = 1500.0
  upstream_mach = node.state.mach
  upstream_total_pressure = node.total_pressure_Pa
  upstream_static_pressure = upstream_total_pressure / (
    1.0 + 0.5 * (gamma - 1.0) * upstream_mach**2
  ) ** (gamma / (gamma - 1.0))
  upstream_static_temperature = total_temperature / (
    1.0 + 0.5 * (gamma - 1.0) * upstream_mach**2
  )
  upstream_density = upstream_static_pressure / (
    gas_constant * upstream_static_temperature
  )
  pressure_ratio = 1.0 + 2.0 * gamma / (gamma + 1.0) * (
    upstream_mach**2 - 1.0
  )
  density_ratio = (gamma + 1.0) * upstream_mach**2 / (
    (gamma - 1.0) * upstream_mach**2 + 2.0
  )
  downstream_static_pressure = upstream_static_pressure * pressure_ratio
  downstream_density = upstream_density * density_ratio
  downstream_static_temperature = upstream_static_temperature * (
    pressure_ratio / density_ratio
  )
  downstream_mach = sqrt(
    (1.0 + 0.5 * (gamma - 1.0) * upstream_mach**2)
    / (gamma * upstream_mach**2 - 0.5 * (gamma - 1.0))
  )
  downstream_total_pressure = downstream_static_pressure * (
    1.0 + 0.5 * (gamma - 1.0) * downstream_mach**2
  ) ** (gamma / (gamma - 1.0))
  upstream_sound_speed = sqrt(
    gamma * gas_constant * upstream_static_temperature
  )
  downstream_sound_speed = sqrt(
    gamma * gas_constant * downstream_static_temperature
  )
  upstream_speed = upstream_mach * upstream_sound_speed
  downstream_speed = downstream_mach * downstream_sound_speed
  entropy_increase = (
    gamma * gas_constant / (gamma - 1.0)
  ) * log(downstream_static_temperature / upstream_static_temperature) - (
    gas_constant * log(pressure_ratio)
  )
  return MocTransonicShockState(
    upstream_total_pressure_Pa=upstream_total_pressure,
    upstream_total_temperature_K=total_temperature,
    downstream_total_pressure_Pa=downstream_total_pressure,
    total_pressure_ratio=downstream_total_pressure / upstream_total_pressure,
    gamma=gamma,
    gas_constant_J_kgK=gas_constant,
    upstream_mach=upstream_mach,
    downstream_mach=downstream_mach,
    upstream_static_pressure_Pa=upstream_static_pressure,
    downstream_static_pressure_Pa=downstream_static_pressure,
    upstream_static_temperature_K=upstream_static_temperature,
    downstream_static_temperature_K=downstream_static_temperature,
    upstream_density_kg_m3=upstream_density,
    downstream_density_kg_m3=downstream_density,
    upstream_sound_speed_m_s=upstream_sound_speed,
    downstream_sound_speed_m_s=downstream_sound_speed,
    upstream_speed_m_s=upstream_speed,
    downstream_speed_m_s=downstream_speed,
    entropy_increase_JpkgK=entropy_increase,
    upstream_flow_angle_rad=node.state.theta_rad,
  )
####


def test_solver_owned_attachment_matches_audited_field_node() -> None:
  field = _internal_field()
  request = MocTransonicShockFieldAttachmentRequest(
    upstream_field=field,
    shock_state=_shock_state_for_node(field.nodes[0]),
    state_tolerance=1.0e-8,
    pressure_tolerance_fraction=1.0e-8,
  )

  result = solve_moc_transonic_shock_field_attachment(request)
  audit = measure_moc_transonic_shock_field_attachment(result)

  assert result.status is MocTransonicShockFieldAttachmentStatus.CONVERGED_BOUNDED_ATTACHMENT
  assert result.attachment_verified
  assert result.selected_node_index == 0
  assert audit.converged
  assert audit.field_match_verified
  assert audit.geometry_binding_verified
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_attachment_rejects_missing_field_sampling_and_branch_mismatch() -> None:
  field = _internal_field()
  state = _shock_state_for_node(field.nodes[0])
  unavailable_field = replace(field, internal_characteristic_closure_verified=False)
  unavailable = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=unavailable_field,
      shock_state=state,
    )
  )
  assert unavailable.status is MocTransonicShockFieldAttachmentStatus.FIELD_REQUIRED

  mismatch = replace(state, upstream_mach=state.upstream_mach + 0.5)
  rejected = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=mismatch,
      state_tolerance=1.0e-8,
      pressure_tolerance_fraction=1.0e-8,
    )
  )
  assert rejected.status is MocTransonicShockFieldAttachmentStatus.NO_ADMISSIBLE_FIELD_MATCH
  assert not rejected.attachment_verified
####


def test_attachment_measurement_rejects_tampered_selection() -> None:
  field = _internal_field()
  result = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=_shock_state_for_node(field.nodes[0]),
    )
  )
  tampered = replace(
    result,
    selected_node_index=(result.selected_node_index or 0) + 1,
  )
  audit = measure_moc_transonic_shock_field_attachment(tampered)
  assert not audit.converged
  assert not audit.field_match_verified
####


def test_bounded_transport_reaches_retained_field_boundary_with_audit() -> None:
  field = _internal_field()
  attachment = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=_shock_state_for_node(field.nodes[0]),
      state_tolerance=1.0e-8,
      pressure_tolerance_fraction=1.0e-8,
    )
  )
  result = solve_moc_transonic_characteristic_transport(
    MocTransonicCharacteristicTransportRequest(
      attachment=attachment,
      family=CharacteristicFamily.PLUS,
      step_length_m=1.0e-2,
      maximum_steps=64,
    )
  )
  audit = measure_moc_transonic_characteristic_transport(result)

  assert result.status is MocTransonicCharacteristicTransportStatus.CONVERGED_BOUNDED_TRANSPORT
  assert result.bounded_transport_verified
  assert result.termination is MocTransonicCharacteristicTransportTermination.FIELD_BOUNDARY
  assert len(result.samples) >= 2
  assert len(result.segments) == len(result.samples) - 1
  assert result.first_unavailable_point_m is not None
  assert audit.converged
  assert audit.rederived
  assert audit.sample_lineage_verified
  assert audit.geometry_verified
  assert audit.compatibility_verified
  assert audit.pressure_lineage_verified
  assert audit.boundary_stop_verified
  assert result.placement_verified is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_bounded_transport_preserves_typed_failure_and_rejects_strict_geometry() -> None:
  field = _internal_field()
  attachment = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=_shock_state_for_node(field.nodes[0]),
    )
  )
  result = solve_moc_transonic_characteristic_transport(
    MocTransonicCharacteristicTransportRequest(
      attachment=attachment,
      family=CharacteristicFamily.PLUS,
      geometry_tolerance=1.0e-6,
    )
  )

  assert result.status is MocTransonicCharacteristicTransportStatus.GEOMETRY_FAILURE
  assert not result.bounded_transport_verified
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_bounded_transport_places_a_scalar_branch_on_a_resolved_frontier() -> None:
  field = _internal_field()
  attachment = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=_shock_state_for_node(field.nodes[0]),
      state_tolerance=1.0e-8,
      pressure_tolerance_fraction=1.0e-8,
    )
  )
  transport = solve_moc_transonic_characteristic_transport(
    MocTransonicCharacteristicTransportRequest(
      attachment=attachment,
      family=CharacteristicFamily.PLUS,
      step_length_m=1.0e-2,
      maximum_steps=64,
    )
  )
  assert transport.bounded_transport_verified
  start = transport.samples[0]
  normal = attachment.geometry.shock_normal_angle_rad
  tangent = normal - 0.5 * pi
  half_length = 0.01
  frontier = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=start.point_m[0] + offset * cos(tangent),
        y_m=start.point_m[1] + offset * sin(tangent),
        theta_rad=start.state.theta_rad,
        mach=start.state.mach,
        gamma=start.state.gamma,
      ),
      total_pressure_Pa=start.total_pressure_Pa,
    )
    for offset in (-half_length, half_length)
  )
  result = solve_moc_transonic_placement(
    MocTransonicPlacementRequest(
      transport=transport,
      target_frontier=frontier,
      frontier_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
      frontier_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      frontier_source='test-resolved-neighboring-frontier',
    )
  )
  audit = measure_moc_transonic_placement(result)

  assert result.status is MocTransonicPlacementStatus.CONVERGED_BOUNDED_PLACEMENT
  assert result.placement_verified
  assert result.intersection_point_m == pytest.approx(start.point_m)
  assert result.state_seam_residual == pytest.approx(0.0)
  assert result.pressure_seam_residual == pytest.approx(0.0)
  assert audit.converged
  assert audit.rederived
  assert audit.frontier_fidelity_verified
  assert audit.frontier_geometry_verified
  assert audit.intersection_verified
  assert audit.state_seam_verified
  assert audit.pressure_seam_verified
  assert audit.shock_geometry_verified
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_transonic_placement_rejects_unresolved_frontier_and_missing_intersection() -> None:
  field = _internal_field()
  attachment = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=_shock_state_for_node(field.nodes[0]),
    )
  )
  transport = solve_moc_transonic_characteristic_transport(
    MocTransonicCharacteristicTransportRequest(
      attachment=attachment,
      family=CharacteristicFamily.PLUS,
    )
  )
  start = transport.samples[0]
  frontier = (
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=start.point_m[0] + 1.0,
        y_m=start.point_m[1] - 0.1,
        theta_rad=start.state.theta_rad,
        mach=start.state.mach,
        gamma=start.state.gamma,
      ),
      total_pressure_Pa=start.total_pressure_Pa,
    ),
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=start.point_m[0] + 1.1,
        y_m=start.point_m[1] - 0.1,
        theta_rad=start.state.theta_rad,
        mach=start.state.mach,
        gamma=start.state.gamma,
      ),
      total_pressure_Pa=start.total_pressure_Pa,
    ),
  )
  unresolved = solve_moc_transonic_placement(
    MocTransonicPlacementRequest(
      transport=transport,
      target_frontier=frontier,
      frontier_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
      frontier_fidelity=MocChainGeometryFidelity.SCALED_REDUCED_ORDER,
      frontier_source='test-reduced-frontier',
    )
  )
  missing = solve_moc_transonic_placement(
    MocTransonicPlacementRequest(
      transport=transport,
      target_frontier=frontier,
      frontier_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
      frontier_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      frontier_source='test-resolved-frontier-without-intersection',
    )
  )

  assert unresolved.status is MocTransonicPlacementStatus.FRONTIER_FIDELITY_FAILURE
  assert missing.status is MocTransonicPlacementStatus.FRONTIER_NOT_REACHED
  assert not unresolved.placement_verified
  assert not missing.placement_verified
  assert unresolved.chain_promotion_blocked
  assert missing.chain_promotion_blocked
####


def _placed_transonic_placement():
  field = _internal_field()
  attachment = solve_moc_transonic_shock_field_attachment(
    MocTransonicShockFieldAttachmentRequest(
      upstream_field=field,
      shock_state=_shock_state_for_node(field.nodes[0]),
      state_tolerance=1.0e-8,
      pressure_tolerance_fraction=1.0e-8,
    )
  )
  transport = solve_moc_transonic_characteristic_transport(
    MocTransonicCharacteristicTransportRequest(
      attachment=attachment,
      family=CharacteristicFamily.PLUS,
      step_length_m=1.0e-2,
      maximum_steps=64,
    )
  )
  start = transport.samples[0]
  normal = attachment.geometry.shock_normal_angle_rad
  tangent = normal - 0.5 * pi
  half_length = 0.01
  frontier = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=start.point_m[0] + offset * cos(tangent),
        y_m=start.point_m[1] + offset * sin(tangent),
        theta_rad=start.state.theta_rad,
        mach=start.state.mach,
        gamma=start.state.gamma,
      ),
      total_pressure_Pa=start.total_pressure_Pa,
    )
    for offset in (-half_length, half_length)
  )
  return solve_moc_transonic_placement(
    MocTransonicPlacementRequest(
      transport=transport,
      target_frontier=frontier,
      frontier_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
      frontier_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      frontier_source='test-resolved-neighboring-frontier',
    )
  )
####


def test_transonic_interface_carries_audited_downstream_sample() -> None:
  placement = _placed_transonic_placement()
  result = solve_moc_transonic_shock_interface(
    MocTransonicShockInterfaceRequest(placement=placement)
  )
  audit = measure_moc_transonic_shock_interface(result)

  assert result.status is (
    MocTransonicShockInterfaceStatus.CONVERGED_BOUNDED_INTERFACE
  )
  assert result.converged
  assert result.interface_verified
  assert result.upstream_sample is not None
  assert result.downstream_sample is not None
  assert result.downstream_sample.mach < 1.0
  assert result.downstream_sample.total_pressure_Pa < (
    result.upstream_sample.total_pressure_Pa
  )
  assert audit.converged
  assert audit.rederived
  assert audit.placement_verified
  assert audit.geometry_verified
  assert audit.upstream_state_verified
  assert audit.frontier_state_verified
  assert audit.upstream_pressure_verified
  assert audit.frontier_pressure_verified
  assert audit.downstream_state_verified
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_transonic_interface_rejects_unverified_placement_and_tampering() -> None:
  placement = _placed_transonic_placement()
  unresolved = replace(
    placement,
    status=MocTransonicPlacementStatus.FRONTIER_NOT_REACHED,
  )
  rejected = solve_moc_transonic_shock_interface(
    MocTransonicShockInterfaceRequest(placement=unresolved)
  )
  assert rejected.status is MocTransonicShockInterfaceStatus.PLACEMENT_REQUIRED
  assert not rejected.converged
  assert rejected.chain_promotion_blocked

  result = solve_moc_transonic_shock_interface(
    MocTransonicShockInterfaceRequest(placement=placement)
  )
  assert result.downstream_sample is not None
  tampered_sample = replace(
    result.downstream_sample,
    mach=0.95,
  )
  tampered = replace(result, downstream_sample=tampered_sample)
  audit = measure_moc_transonic_shock_interface(tampered)
  assert not audit.converged
  assert not audit.downstream_state_verified
####
