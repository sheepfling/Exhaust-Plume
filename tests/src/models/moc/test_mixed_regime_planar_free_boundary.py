from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMixedRegimeControlSection,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
  MocMixedRegimePlanarFreeBoundaryStatus,
  MocPostShockBoundaryState,
  solve_mixed_regime_planar_free_boundary_reference,
  solve_normal_shock_terminal,
)
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimePlanarFreeBoundaryMeasurementStatus,
  measure_mixed_regime_planar_free_boundary_reference,
)


def _terminal():
  return solve_normal_shock_terminal(
    CharacteristicState(
      x_m=1.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_pressure_Pa=100000.0,
  )


def _supersonic_patch():
  return (
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
      downstream_total_pressure_Pa=1.8e6,
    ),
  )


def _request_and_section():
  terminal = _terminal()
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=_supersonic_patch(),
  )
  terminal_x, terminal_y = request.terminal_point_m
  gamma = request.terminal.upstream_state.gamma
  section_points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  section_samples = tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=request.terminal_downstream_mach,
      flow_angle_rad=request.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=request.terminal_downstream_pressure_Pa,
      total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
      gamma=gamma,
    )
    for point in section_points
  )
  return request, MocMixedRegimeControlSection(
    points_m=section_points,
    samples=section_samples,
    normal_angle_rad=0.0,
  )


def _solve(*, ambient_pressure_Pa: float):
  request, section = _request_and_section()
  return solve_mixed_regime_planar_free_boundary_reference(
    request,
    section,
    ambient_pressure_Pa=ambient_pressure_Pa,
    downstream_length_m=0.2,
    outlet_height_m=0.1,
  )


def test_parameterized_planar_free_boundary_closes_uniform_case_and_measures_independently() -> None:
  request, _ = _request_and_section()
  result = _solve(ambient_pressure_Pa=request.terminal_downstream_pressure_Pa)

  assert result.status is MocMixedRegimePlanarFreeBoundaryStatus.CONVERGED_REFERENCE
  assert result.converged
  assert result.physical_closure_verified
  assert result.shape_heights_m == pytest.approx((0.1,) * 8)
  assert result.field is not None
  assert result.field.model == 'compressible-isentropic-potential-reference'
  assert result.handoff is not None and result.handoff.converged
  assert not result.canonical_free_boundary_verified
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False

  measurement = measure_mixed_regime_planar_free_boundary_reference(result)

  assert measurement.status is (
    MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.physical_closure_verified
  assert measurement.request_verified
  assert measurement.control_section_verified
  assert measurement.perimeter_spec_verified
  assert measurement.boundary_verified
  assert measurement.downstream_condition_verified
  assert measurement.field_measurement_verified
  assert measurement.shape_geometry_verified
  assert measurement.free_boundary_residual_verified
  assert measurement.independent_boundary_normal_velocity_residual is not None
  assert measurement.independent_boundary_normal_velocity_residual <= 1.0e-8
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_parameterized_planar_free_boundary_changes_shape_for_pressure_mismatch() -> None:
  result = _solve(ambient_pressure_Pa=400000.0)

  assert result.status is MocMixedRegimePlanarFreeBoundaryStatus.CONVERGED_REFERENCE
  assert result.converged
  assert result.physical_closure_verified
  assert result.maximum_boundary_normal_velocity_residual is not None
  assert result.maximum_boundary_normal_velocity_residual <= 1.0e-8
  assert result.shape_heights_m != pytest.approx((0.1,) * 8)
  assert result.shape_heights_m[-1] == pytest.approx(0.1)

  measurement = measure_mixed_regime_planar_free_boundary_reference(result)

  assert measurement.converged
  assert measurement.physical_closure_verified
  assert measurement.shape_geometry_verified
  assert measurement.free_boundary_residual_verified
  assert measurement.maximum_tangent_residual_rad is not None
  assert measurement.maximum_tangent_residual_rad <= 2.0e-2


def test_parameterized_planar_free_boundary_rejects_unreachable_pressure() -> None:
  result = _solve(ambient_pressure_Pa=600000.0)

  assert result.status is MocMixedRegimePlanarFreeBoundaryStatus.PRESSURE_UNREACHABLE
  assert not result.converged
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False


def test_parameterized_planar_free_boundary_rejects_nonuniform_control_section() -> None:
  request, section = _request_and_section()
  changed_sample = replace(
    section.samples[1],
    total_pressure_Pa=section.samples[1].total_pressure_Pa * 0.99,
  )
  changed_section = replace(
    section,
    samples=(section.samples[0], changed_sample, section.samples[2]),
  )

  result = solve_mixed_regime_planar_free_boundary_reference(
    request,
    changed_section,
    ambient_pressure_Pa=400000.0,
    downstream_length_m=0.2,
    outlet_height_m=0.1,
  )

  assert result.status is MocMixedRegimePlanarFreeBoundaryStatus.CONTROL_SECTION_FAILURE
  assert not result.converged


def test_planar_free_boundary_measurement_rejects_tampered_geometry() -> None:
  result = _solve(ambient_pressure_Pa=400000.0)
  changed_shape = (result.shape_heights_m[0] + 0.001, *result.shape_heights_m[1:])
  tampered = replace(result, shape_heights_m=changed_shape)

  measurement = measure_mixed_regime_planar_free_boundary_reference(tampered)

  assert measurement.status is (
    MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE
  )
  assert not measurement.converged
  assert not measurement.shape_geometry_verified
  assert measurement.chain_promotion_blocked


def test_planar_free_boundary_measurement_rejects_tampered_potential() -> None:
  result = _solve(ambient_pressure_Pa=400000.0)
  assert result.field is not None
  changed_potential = (
    result.field.velocity_potential[0] + 0.001,
    *result.field.velocity_potential[1:],
  )
  tampered_field = replace(
    result.field,
    velocity_potential=changed_potential,
  )
  tampered = replace(result, field=tampered_field)

  measurement = measure_mixed_regime_planar_free_boundary_reference(tampered)

  assert measurement.status is (
    MocMixedRegimePlanarFreeBoundaryMeasurementStatus.FIELD_FAILURE
  )
  assert not measurement.converged
  assert not measurement.field_measurement_verified
  assert measurement.chain_promotion_blocked
