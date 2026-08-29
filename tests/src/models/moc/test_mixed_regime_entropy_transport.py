from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMixedRegimeEntropyTransportStatus,
  MocMixedRegimePerimeterRequest,
  MocMixedRegimeFieldSample,
  MocPostShockBoundaryState,
  build_mixed_regime_entropy_handoff,
  solve_mixed_regime_subsonic_field,
  solve_mixed_regime_entropy_transport_boundary,
  solve_normal_shock_terminal,
  validate_mixed_regime_boundary,
)
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimeEntropyTransportMeasurementStatus,
  measure_mixed_regime_entropy_transport_boundary,
)


def _request() -> MocMixedRegimePerimeterRequest:
  terminal = solve_normal_shock_terminal(
    CharacteristicState(
      x_m=1.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_pressure_Pa=100000.0,
  )
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  patch = (
    MocPostShockBoundaryState(
      point_m=(0.8, 0.2),
      state=CharacteristicState(
        x_m=0.8,
        y_m=0.2,
        theta_rad=0.1,
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    ),
    MocPostShockBoundaryState(
      point_m=(0.9, 0.1),
      state=CharacteristicState(
        x_m=0.9,
        y_m=0.1,
        theta_rad=0.05,
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.75e6,
    ),
  )
  return MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )


def _request_handoff_field():
  request = _request()
  boundary = validate_mixed_regime_boundary(
    request.terminal,
    request.supersonic_patch,
    supersonic_patch_converged=True,
    subsonic_samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=request.terminal_downstream_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=request.terminal_downstream_pressure_Pa,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=request.terminal.upstream_state.gamma,
      )
      for point in (
        request.terminal_point_m,
        (request.terminal_point_m[0] + 0.1, request.terminal_point_m[1] + 0.1),
        (request.terminal_point_m[0] + 0.2, request.terminal_point_m[1] + 0.1),
        (request.terminal_point_m[0] + 0.2, request.terminal_point_m[1]),
        request.terminal_point_m,
      )
    ),
  )
  field = solve_mixed_regime_subsonic_field(boundary, radial_divisions=2)
  handoff = build_mixed_regime_entropy_handoff(request)
  return request, handoff, field


def _terminal_source_map(handoff, field):
  assert handoff.terminal_sample_index is not None
  terminal_arc = handoff.cumulative_arc_length_m[handoff.terminal_sample_index]
  return (
    tuple(terminal_arc for _ in field.nodes),
    tuple(0 for _ in field.nodes),
  )


def test_entropy_transport_binds_an_explicit_source_map_without_promotion() -> None:
  request, handoff, field = _request_handoff_field()
  source_arc, streamline_ids = _terminal_source_map(handoff, field)

  result = solve_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    field,
    source_arc,
    streamline_ids,
  )

  assert result.status is MocMixedRegimeEntropyTransportStatus.CONVERGED_REFERENCE
  assert result.converged
  assert result.field_boundary_verified
  assert result.source_profile_verified
  assert result.streamline_assignment_verified
  assert result.terminal_seam_verified
  assert result.entropy_transport_verified
  assert result.node_count == field.node_count
  assert result.streamline_count == 1
  assert result.maximum_total_pressure_residual_Pa == pytest.approx(
    0.0,
    abs=1.0e-8,
  )
  assert result.maximum_entropy_coordinate_residual == pytest.approx(
    0.0,
    abs=1.0e-12,
  )
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False

  measurement = measure_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    field,
    result,
  )

  assert measurement.status is MocMixedRegimeEntropyTransportMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.transport_verified
  assert measurement.handoff_verified
  assert measurement.field_boundary_verified
  assert measurement.entropy_transport_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_entropy_transport_disables_source_extrapolation() -> None:
  request, handoff, field = _request_handoff_field()
  source_arc, streamline_ids = _terminal_source_map(handoff, field)

  result = solve_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    field,
    (source_arc[0] + 1.0e-3, *source_arc[1:]),
    streamline_ids,
  )

  assert result.status is MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE
  assert not result.converged
  assert not result.entropy_transport_verified
  assert 'extrapolation' in result.message


def test_entropy_transport_rejects_pressure_lineage_residuals() -> None:
  request, handoff, field = _request_handoff_field()
  source_arc, streamline_ids = _terminal_source_map(handoff, field)
  changed_node = replace(
    field.nodes[0],
    total_pressure_Pa=field.nodes[0].total_pressure_Pa * 0.99,
  )
  changed_field = replace(field, nodes=(changed_node, *field.nodes[1:]))

  result = solve_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    changed_field,
    source_arc,
    streamline_ids,
  )

  assert result.status is MocMixedRegimeEntropyTransportStatus.RESIDUAL_FAILURE
  assert not result.converged
  assert result.maximum_total_pressure_residual_Pa is not None
  assert result.maximum_total_pressure_residual_Pa > 0.0
  assert not result.entropy_transport_verified

  valid_result = solve_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    field,
    source_arc,
    streamline_ids,
  )
  changed_result = replace(
    valid_result,
    entropy_transport_verified=False,
  )
  measurement = measure_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    field,
    changed_result,
  )

  assert measurement.status is MocMixedRegimeEntropyTransportMeasurementStatus.CONSISTENCY_FAILURE
  assert not measurement.converged
  assert not measurement.transport_verified


def test_entropy_transport_requires_two_nodes_per_explicit_streamline() -> None:
  request, handoff, field = _request_handoff_field()
  source_arc, _ = _terminal_source_map(handoff, field)

  result = solve_mixed_regime_entropy_transport_boundary(
    request,
    handoff,
    field,
    source_arc,
    tuple(range(field.node_count)),
  )

  assert result.status is MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE
  assert not result.converged
  assert 'at least two nodes' in result.message
