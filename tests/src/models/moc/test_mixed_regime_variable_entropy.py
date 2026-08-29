from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMixedRegimeControlSection,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
  MocMixedRegimeVariableEntropyFreeBoundaryStatus,
  MocPostShockBoundaryState,
  build_mixed_regime_entropy_handoff,
  solve_mixed_regime_variable_entropy_free_boundary,
  solve_normal_shock_terminal,
)
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus,
  measure_mixed_regime_variable_entropy_free_boundary,
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
  terminal_total_pressure = terminal.downstream_total_pressure_Pa
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
      upstream_total_pressure_Pa=0.99 * terminal_total_pressure,
      downstream_total_pressure_Pa=0.95 * terminal_total_pressure,
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
      upstream_total_pressure_Pa=0.98 * terminal_total_pressure,
      downstream_total_pressure_Pa=0.90 * terminal_total_pressure,
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


def _request_handoff_and_section():
  request = _request()
  handoff = build_mixed_regime_entropy_handoff(request)
  assert handoff.converged
  terminal_x, terminal_y = request.terminal_point_m
  gamma = request.terminal.upstream_state.gamma
  fractions = (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)
  section_height = 0.05
  section_x = terminal_x + 0.02
  samples = []
  for fraction in fractions:
    source_arc = handoff.cumulative_arc_length_m[-1] * (1.0 - fraction)
    total_pressure = handoff.total_pressure_at_arc_length(source_arc)
    static_pressure = total_pressure / (
      1.0 + 0.5 * (gamma - 1.0) * request.terminal_downstream_mach**2
    ) ** (gamma / (gamma - 1.0))
    samples.append(
      MocMixedRegimeFieldSample(
        point_m=(section_x, terminal_y + fraction * section_height),
        mach=request.terminal_downstream_mach,
        flow_angle_rad=0.0,
        static_pressure_Pa=static_pressure,
        total_pressure_Pa=total_pressure,
        gamma=gamma,
      )
    )
  section = MocMixedRegimeControlSection(
    points_m=tuple(sample.point_m for sample in samples),
    samples=tuple(samples),
    normal_angle_rad=0.0,
  )
  return request, handoff, section


def _solve(*, axial_station_count: int = 7):
  request, handoff, section = _request_handoff_and_section()
  result = solve_mixed_regime_variable_entropy_free_boundary(
    request,
    handoff,
    section,
    ambient_pressure_Pa=0.98 * handoff.samples[0].downstream_total_pressure_Pa,
    downstream_length_m=0.2,
    initial_outlet_height_m=0.04,
    axial_station_count=axial_station_count,
  )
  return request, handoff, section, result


def test_variable_entropy_reference_closes_local_mesh_and_measures_independently() -> None:
  request, handoff, section, result = _solve()

  assert result.status is (
    MocMixedRegimeVariableEntropyFreeBoundaryStatus.CONVERGED_REFERENCE
  )
  assert result.converged
  assert result.source_streamline_mapping_verified
  assert result.entropy_transport_verified
  assert result.continuity_verified
  assert result.free_boundary_condition_verified
  assert result.field_topology_verified
  assert result.maximum_entrance_continuity_residual is not None
  assert result.maximum_entrance_continuity_residual > 0.0
  assert result.maximum_transverse_momentum_residual is not None
  assert result.maximum_transverse_momentum_residual > 0.0
  assert result.maximum_mass_flow_residual == pytest.approx(0.0, abs=1.0e-12)
  assert result.field is not None
  assert result.field.topology.forms_closed_zone
  assert result.field.model == result.model
  assert result.field.physical_closure_verified is False
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert len(set(result.source_total_pressure_by_transverse_index_Pa)) > 1

  measurement = measure_mixed_regime_variable_entropy_free_boundary(
    request,
    handoff,
    section,
    result,
  )

  assert measurement.status is (
    MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.reference_verified
  assert measurement.request_verified
  assert measurement.handoff_verified
  assert measurement.control_section_verified
  assert measurement.source_streamline_mapping_verified
  assert measurement.field_boundary_verified
  assert measurement.downstream_condition_verified
  assert measurement.field_topology_verified
  assert measurement.continuity_verified
  assert measurement.entropy_transport_verified
  assert measurement.free_boundary_condition_verified
  assert measurement.reported_flags_verified
  assert measurement.reference_model_verified
  assert measurement.physical_closure_verified is False
  assert measurement.canonical_euler_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_variable_entropy_reference_refines_without_changing_source_lineage() -> None:
  _, coarse_handoff, _, coarse = _solve(axial_station_count=5)
  request, fine_handoff, section, fine = _solve(axial_station_count=9)

  assert coarse.converged
  assert fine.converged
  assert coarse.node_count < fine.node_count
  assert coarse.cell_count < fine.cell_count
  assert fine.source_total_pressure_by_transverse_index_Pa == pytest.approx(
    coarse.source_total_pressure_by_transverse_index_Pa,
  )
  assert fine.outlet_height_m == pytest.approx(coarse.outlet_height_m, rel=1.0e-7)
  measurement = measure_mixed_regime_variable_entropy_free_boundary(
    request,
    fine_handoff,
    section,
    fine,
  )
  assert measurement.reference_verified
  assert measurement.node_count == fine.node_count
  assert measurement.cell_count == fine.cell_count
  assert measurement.maximum_continuity_residual is not None
  assert measurement.maximum_continuity_residual <= 0.25


def test_variable_entropy_reference_requires_solver_owned_source_pressure() -> None:
  request, handoff, section = _request_handoff_and_section()
  changed_total_pressure = section.samples[1].total_pressure_Pa * 0.99
  changed_static_pressure = changed_total_pressure / (
    1.0
    + 0.5
    * (section.samples[1].gamma - 1.0)
    * section.samples[1].mach**2
  ) ** (section.samples[1].gamma / (section.samples[1].gamma - 1.0))
  changed_sample = replace(
    section.samples[1],
    static_pressure_Pa=changed_static_pressure,
    total_pressure_Pa=changed_total_pressure,
  )
  changed_section = replace(
    section,
    samples=(section.samples[0], changed_sample, *section.samples[2:]),
  )

  result = solve_mixed_regime_variable_entropy_free_boundary(
    request,
    handoff,
    changed_section,
    ambient_pressure_Pa=0.98 * handoff.samples[0].downstream_total_pressure_Pa,
    downstream_length_m=0.2,
    initial_outlet_height_m=0.04,
  )

  assert result.status is (
    MocMixedRegimeVariableEntropyFreeBoundaryStatus.CONTROL_SECTION_FAILURE
  )
  assert not result.converged
  assert 'reverse entropy mapping' in result.message


def test_variable_entropy_measurement_rejects_promotion_flag_mutation() -> None:
  request, handoff, section, result = _solve()
  changed_result = replace(result, canonical_euler_verified=True)

  measurement = measure_mixed_regime_variable_entropy_free_boundary(
    request,
    handoff,
    section,
    changed_result,
  )

  assert measurement.status is (
    MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONSISTENCY_FAILURE
  )
  assert not measurement.reference_verified
  assert not measurement.canonical_euler_verified
