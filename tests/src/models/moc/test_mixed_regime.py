from dataclasses import replace
from math import atan2, pi, sqrt

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMixedRegimeBoundaryStatus,
  MocMixedRegimeClosureStatus,
  MocMixedRegimeControlSection,
  MocMixedRegimeControlSectionStatus,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionStatus,
  MocMixedRegimeFieldStatus,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  MocMixedRegimeFreeBoundaryStatus,
  MocMixedRegimePlanarSolveStatus,
  MocMixedRegimePlanarPotentialReference,
  MocMixedRegimePlanarFrozenProfileReference,
  MocMixedRegimePerimeterRequest,
  MocPrescribedMixedRegimeClosureMock,
  MocPostShockBoundaryState,
  run_mixed_regime_closure_solver,
  run_mixed_regime_planar_field_solver,
  solve_mixed_regime_planar_potential_reference,
  solve_mixed_regime_planar_frozen_profile_reference,
  solve_normal_shock_terminal,
  solve_mixed_regime_compressible_potential_field,
  solve_mixed_regime_downstream_condition,
  solve_mixed_regime_downstream_perimeter,
  solve_mixed_regime_downstream_free_boundary,
  solve_mixed_regime_downstream_free_boundary_from_control_section,
  solve_mixed_regime_subsonic_field,
  validate_mixed_regime_boundary,
  validate_mixed_regime_control_section,
  validate_mixed_regime_downstream_condition,
)
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimeControlSectionMeasurementStatus,
  MocMixedRegimeFreeBoundaryMeasurementStatus,
  MocMixedRegimeFreeBoundaryRefinementCase,
  MocMixedRegimeFreeBoundaryRefinementMeasurementStatus,
  MocMixedRegimePotentialMeasurementStatus,
  measure_mixed_regime_control_section,
  measure_mixed_regime_free_boundary_reference,
  measure_mixed_regime_free_boundary_refinement,
  measure_mixed_regime_compressible_potential_field,
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


def _samples(terminal, *, interior_total_pressure: float | None = None):
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  gamma = terminal.upstream_state.gamma
  points = ((1.0, 0.0), (1.1, 0.1), (1.2, 0.1), (1.2, 0.0), (1.0, 0.0))
  return tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=terminal.downstream_mach,
      flow_angle_rad=terminal.downstream_flow_angle_rad,
      static_pressure_Pa=terminal.downstream_pressure_Pa,
      total_pressure_Pa=(
        terminal.downstream_total_pressure_Pa
        if index in (0, len(points) - 1) or interior_total_pressure is None
        else interior_total_pressure
      ),
      gamma=gamma,
    )
    for index, point in enumerate(points)
  )


def _terminal_equivalent_control_section(request):
  terminal_x, terminal_y = request.terminal_point_m
  gamma = request.terminal.upstream_state.gamma
  points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  samples = tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=request.terminal_downstream_mach,
      flow_angle_rad=request.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=request.terminal_downstream_pressure_Pa,
      total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
      gamma=gamma,
    )
    for point in points
  )
  return MocMixedRegimeControlSection(
    points_m=points,
    samples=samples,
    normal_angle_rad=0.0,
  )


def _slip_wall_samples(terminal):
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  gamma = terminal.upstream_state.gamma
  terminal_x, terminal_y = terminal.shock_point_m
  points = (
    (terminal_x, terminal_y),
    (terminal_x + 0.1, terminal_y),
    (terminal_x + 0.1, terminal_y + 0.1),
    (terminal_x, terminal_y + 0.1),
    (terminal_x, terminal_y),
  )
  flow_angles = (0.0, 0.0, pi, pi, 0.0)
  return tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=terminal.downstream_mach,
      flow_angle_rad=flow_angle,
      static_pressure_Pa=terminal.downstream_pressure_Pa,
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=gamma,
    )
    for point, flow_angle in zip(points, flow_angles, strict=True)
  )


def _slip_wall_boundary_and_condition(terminal):
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_slip_wall_samples(terminal),
  )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )
  assert condition.converged
  return boundary, condition


def _pressure_outflow_boundary_and_condition(terminal):
  assert terminal.downstream_pressure_Pa is not None
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )
  assert condition.converged
  return boundary, condition


def _single_edge_slip_wall_boundary_and_condition(terminal):
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_total_pressure_Pa is not None
  gamma = terminal.upstream_state.gamma
  sonic_factor = 0.5 * (gamma - 1.0)
  reference_speed = terminal.downstream_mach / sqrt(
    1.0 + sonic_factor * terminal.downstream_mach ** 2
  )
  transverse_speed = 0.05
  x_terminal, y_terminal = terminal.shock_point_m
  points = (
    (x_terminal, y_terminal),
    (x_terminal + 0.1, y_terminal),
    (x_terminal + 0.1, y_terminal + 0.1),
    (x_terminal, y_terminal + 0.1),
    (x_terminal, y_terminal),
  )
  velocities = (
    (reference_speed, 0.0),
    (reference_speed, 0.0),
    (reference_speed, transverse_speed),
    (reference_speed, transverse_speed),
  )
  samples = []
  for point, (q_x, q_y) in zip(points[:-1], velocities, strict=True):
    speed_squared = q_x * q_x + q_y * q_y
    mach = sqrt(speed_squared / (1.0 - sonic_factor * speed_squared))
    samples.append(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=mach,
        flow_angle_rad=atan2(q_y, q_x),
        static_pressure_Pa=(
          terminal.downstream_total_pressure_Pa
          / (1.0 + sonic_factor * mach ** 2) ** (gamma / (gamma - 1.0))
        ),
        total_pressure_Pa=terminal.downstream_total_pressure_Pa,
        gamma=gamma,
      )
    )
  samples.append(samples[0])
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=tuple(samples),
  )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )
  assert condition.converged
  return boundary, condition


def test_scalar_mixed_regime_boundary_handoff_is_valid_but_not_field_closure() -> None:
  terminal = _terminal()
  result = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  assert result.status is MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF
  assert result.converged
  assert result.supersonic_patch_verified
  assert result.terminal_continuity_verified
  assert result.perimeter_geometry_verified
  assert result.total_pressure_lineage_verified
  assert result.mixed_regime_field_complete is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked


def test_downstream_slip_wall_condition_is_separate_from_scalar_boundary_handoff() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_slip_wall_samples(terminal),
  )

  result = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )

  assert result.status is MocMixedRegimeDownstreamConditionStatus.CONVERGED
  assert result.converged
  assert result.physical_condition_verified
  assert result.tangency_condition_verified
  assert result.pressure_condition_verified
  assert result.maximum_tangent_residual_rad == pytest.approx(0.0)
  assert result.chain_promotion_blocked


def test_downstream_condition_rejects_a_geometrically_closed_but_nontangent_perimeter() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  result = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )

  assert result.status is MocMixedRegimeDownstreamConditionStatus.TANGENCY_FAILURE
  assert not result.converged
  assert not result.physical_condition_verified
  assert result.boundary is boundary
  assert result.maximum_tangent_residual_rad is not None
  assert result.maximum_tangent_residual_rad > 0.0
  assert result.chain_promotion_blocked


def test_downstream_ambient_condition_requires_tangency_and_static_pressure() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_slip_wall_samples(terminal),
  )
  assert terminal.downstream_pressure_Pa is not None

  result = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )

  assert result.status is MocMixedRegimeDownstreamConditionStatus.CONVERGED
  assert result.tangency_condition_verified
  assert result.pressure_condition_verified
  assert result.maximum_pressure_residual_Pa == pytest.approx(0.0)
  assert result.chain_promotion_blocked


def test_downstream_condition_callback_preserves_exact_terminal_and_patch_seams() -> None:
  terminal = _terminal()
  patch = _supersonic_patch()
  boundary = validate_mixed_regime_boundary(
    terminal,
    patch,
    supersonic_patch_converged=True,
    subsonic_samples=_slip_wall_samples(terminal),
  )
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )

  result = solve_mixed_regime_downstream_condition(
    request,
    lambda received: boundary if received is request else None,
    condition_kind=MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )

  assert result.status is MocMixedRegimeDownstreamConditionStatus.CONVERGED
  assert result.boundary is boundary
  assert result.chain_promotion_blocked

  mismatched = replace(boundary, supersonic_patch=())
  mismatch_result = solve_mixed_regime_downstream_condition(
    request,
    lambda _received: mismatched,
    condition_kind=MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )

  assert mismatch_result.status is MocMixedRegimeDownstreamConditionStatus.BOUNDARY_FAILURE
  assert not mismatch_result.converged
  assert 'supersonic patch' in mismatch_result.message


def test_explicit_downstream_perimeter_solver_returns_conditioned_reference_field() -> None:
  terminal = _terminal()
  patch = _supersonic_patch()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )
  points = (
    terminal.shock_point_m,
    (terminal.shock_point_m[0] + 0.1, terminal.shock_point_m[1] + 0.1),
    (terminal.shock_point_m[0] + 0.2, terminal.shock_point_m[1] + 0.1),
    (terminal.shock_point_m[0] + 0.2, terminal.shock_point_m[1]),
    terminal.shock_point_m,
  )
  specification = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=points,
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )

  def sample_at(
    received: MocMixedRegimePerimeterRequest,
    _index: int,
    point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=received.terminal_downstream_mach,
      flow_angle_rad=received.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=received.terminal_downstream_pressure_Pa,
      total_pressure_Pa=received.terminal_downstream_total_pressure_Pa,
      gamma=received.terminal.upstream_state.gamma,
    )

  result = solve_mixed_regime_downstream_perimeter(
    request,
    specification,
    sample_at,
    radial_divisions=2,
  )

  assert result.status is MocMixedRegimeClosureStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert result.perimeter_spec is specification
  assert result.downstream_condition is not None
  assert result.downstream_condition.converged
  assert result.field is not None
  assert result.field.radial_divisions == 2
  assert result.field.downstream_condition is result.downstream_condition


def test_explicit_downstream_perimeter_solver_never_repairs_a_changed_sample_point() -> None:
  terminal = _terminal()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  patch = _supersonic_patch()
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )
  point = terminal.shock_point_m
  specification = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      point,
      (point[0] + 0.1, point[1] + 0.1),
      (point[0] + 0.2, point[1] + 0.1),
      (point[0] + 0.2, point[1]),
      point,
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )

  result = solve_mixed_regime_downstream_perimeter(
    request,
    specification,
    lambda _request, _index, sample_point: MocMixedRegimeFieldSample(
      point_m=(sample_point[0] + 0.01, sample_point[1]),
      mach=terminal.downstream_mach,
      flow_angle_rad=terminal.downstream_flow_angle_rad,
      static_pressure_Pa=terminal.downstream_pressure_Pa,
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=terminal.upstream_state.gamma,
    ),
  )

  assert result.status is MocMixedRegimeClosureStatus.SEAM_FAILURE
  assert not result.converged
  assert result.field is None
  assert 'changed the explicit perimeter coordinate' in result.message


def test_prescribed_mixed_regime_closure_mock_is_explicit_reference_only() -> None:
  terminal = _terminal()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
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

  mock = MocPrescribedMixedRegimeClosureMock()
  result = mock.solve(request)

  assert result.status is MocMixedRegimeClosureStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert result.chain_promotion_blocked
  assert result.request is request
  assert result.field is not None
  assert result.field.radial_divisions == mock.radial_divisions
  assert result.perimeter_spec is not None
  assert result.perimeter_spec.model == mock.model
  assert result.perimeter_spec.condition_kind is mock.condition_kind
  report = mock.as_report()
  assert report['planning_only'] is True
  assert report['production_claim_allowed'] is False
  assert report['condition_kind'] == 'prescribed-pressure-outflow-section'


def test_elliptic_subsonic_reference_field_closes_only_its_declared_mesh_model() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  field = solve_mixed_regime_subsonic_field(boundary)

  assert field.status is MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD
  assert field.converged
  assert field.node_count == 5
  assert field.cell_count == 4
  assert field.topology.forms_closed_zone
  assert field.topology.nonmanifold_edge_count == 0
  assert field.model_closure_verified
  assert field.downstream_condition_verified is False
  assert field.physical_closure_verified is False
  assert field.mixed_regime_field_complete is False
  assert field.chain_promotion_blocked
  assert field.model == 'elliptic-isentropic-subsonic-reference'


@pytest.mark.parametrize(
  ('radial_divisions', 'expected_node_count', 'expected_cell_count'),
  ((2, 9, 12), (3, 13, 20), (4, 17, 28)),
)
def test_radial_elliptic_reference_field_refines_without_promoting_the_chain(
  radial_divisions: int,
  expected_node_count: int,
  expected_cell_count: int,
) -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  field = solve_mixed_regime_subsonic_field(
    boundary,
    radial_divisions=radial_divisions,
  )

  assert field.status is MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD
  assert field.converged
  assert field.radial_divisions == radial_divisions
  assert field.model == 'elliptic-isentropic-radial-reference'
  assert field.node_count == expected_node_count
  assert field.cell_count == expected_cell_count
  assert field.topology.forms_closed_zone
  assert field.topology.nonmanifold_edge_count == 0
  assert field.model_closure_verified
  assert field.downstream_condition_verified is False
  assert field.physical_closure_verified is False
  assert field.mixed_regime_field_complete is False
  assert field.chain_promotion_blocked
  assert field.maximum_thermodynamic_residual is not None
  assert field.maximum_thermodynamic_residual <= 1.0e-8
  assert field.maximum_harmonic_residual is not None
  assert field.maximum_harmonic_residual <= 1.0e-12
  assert field.maximum_velocity_divergence_residual is not None
  assert field.maximum_velocity_divergence_residual <= 1.0e-12


def test_condition_qualified_elliptic_reference_field_can_be_attached() -> None:
  terminal = _terminal()
  boundary, condition = _pressure_outflow_boundary_and_condition(terminal)

  field = solve_mixed_regime_subsonic_field(
    boundary,
    downstream_condition=condition,
  )

  assert field.converged
  assert field.model_closure_verified
  assert field.downstream_condition is condition
  assert field.downstream_condition_verified
  assert field.physical_closure_verified
  assert field.mixed_regime_field_complete
  assert condition.tangency_condition_applicable is False
  assert condition.tangent_residuals_rad == ()


@pytest.mark.parametrize(
  ('radial_divisions', 'expected_node_count', 'expected_cell_count'),
  ((1, 5, 4), (2, 9, 12), (3, 13, 20)),
)
def test_compressible_potential_reference_solves_a_declared_subsonic_field(
  radial_divisions: int,
  expected_node_count: int,
  expected_cell_count: int,
) -> None:
  terminal = _terminal()
  boundary, condition = _pressure_outflow_boundary_and_condition(terminal)

  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    radial_divisions=radial_divisions,
    downstream_condition=condition,
  )

  assert field.status is MocMixedRegimeFieldStatus.CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD
  assert field.converged
  assert field.model == 'compressible-isentropic-potential-reference'
  assert field.radial_divisions == radial_divisions
  assert field.node_count == expected_node_count
  assert field.cell_count == expected_cell_count
  assert field.topology.forms_closed_zone
  assert field.model_closure_verified
  assert field.physical_closure_verified
  assert field.mixed_regime_field_complete
  assert field.chain_promotion_blocked
  assert field.downstream_condition is condition
  assert len(field.velocity_potential) == field.node_count
  assert field.maximum_mass_conservation_residual is not None
  assert field.maximum_mass_conservation_residual <= 1.0e-8
  assert field.maximum_boundary_velocity_residual is not None
  assert field.maximum_boundary_velocity_residual <= 1.0e-8
  assert field.potential_circulation_residual is not None
  assert field.potential_circulation_residual <= 1.0e-8
  assert field.maximum_mach is not None
  assert field.maximum_mach < 1.0


def test_compressible_potential_reference_gates_no_penetration_for_tangent_condition() -> None:
  terminal = _terminal()
  boundary, condition = _single_edge_slip_wall_boundary_and_condition(terminal)

  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    downstream_condition=condition,
  )

  assert field.status is MocMixedRegimeFieldStatus.RESIDUAL_FAILURE
  assert not field.converged
  assert field.downstream_condition is condition
  assert field.maximum_boundary_normal_velocity_residual is not None
  assert field.maximum_boundary_normal_velocity_residual > 1.0e-8
  assert not field.model_closure_verified
  assert 'boundary_normal_velocity' in field.message


def test_compressible_potential_reference_reports_nonlinear_iterations() -> None:
  terminal = _terminal()
  patch = _supersonic_patch()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  gamma = terminal.upstream_state.gamma
  sonic_factor = 0.5 * (gamma - 1.0)
  reference_speed = terminal.downstream_mach / (
    1.0 + sonic_factor * terminal.downstream_mach * terminal.downstream_mach
  ) ** 0.5
  quadratic_strength = 0.02
  points = (
    terminal.shock_point_m,
    (terminal.shock_point_m[0] + 0.1, terminal.shock_point_m[1] + 0.1),
    (terminal.shock_point_m[0] + 0.2, terminal.shock_point_m[1] + 0.1),
    (terminal.shock_point_m[0] + 0.2, terminal.shock_point_m[1]),
    terminal.shock_point_m,
  )

  def sample_at(point: tuple[float, float]) -> MocMixedRegimeFieldSample:
    q_x = reference_speed + 2.0 * quadratic_strength * (
      point[0] - terminal.shock_point_m[0]
    )
    q_y = -2.0 * quadratic_strength * (point[1] - terminal.shock_point_m[1])
    speed_squared = q_x * q_x + q_y * q_y
    enthalpy_factor = 1.0 - sonic_factor * speed_squared
    mach = (speed_squared / enthalpy_factor) ** 0.5
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=mach,
      flow_angle_rad=atan2(q_y, q_x),
      static_pressure_Pa=(
        terminal.downstream_total_pressure_Pa
        * enthalpy_factor ** (gamma / (gamma - 1.0))
      ),
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=gamma,
    )

  boundary = validate_mixed_regime_boundary(
    terminal,
    patch,
    supersonic_patch_converged=True,
    subsonic_samples=tuple(sample_at(point) for point in points),
  )
  assert boundary.converged

  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    radial_divisions=2,
  )

  assert field.status is MocMixedRegimeFieldStatus.CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD
  assert field.model_closure_verified
  assert field.nonlinear_iteration_count >= 1
  assert field.maximum_mass_conservation_residual is not None
  assert field.maximum_mass_conservation_residual <= 1.0e-8


def test_compressible_potential_reference_tolerates_roundoff_on_collinear_edges() -> None:
  terminal = _terminal()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  gamma = terminal.upstream_state.gamma
  x_terminal, y_terminal = terminal.shock_point_m
  # The second point is intended to lie on the bottom edge.  Its tiny
  # positive ordinate creates a negative cross product at the first vertex
  # after floating-point coordinate construction, but is far below the
  # declared positional tolerance.
  points = (
    (x_terminal, y_terminal),
    (x_terminal + 0.1, y_terminal + 1.0e-12),
    (x_terminal + 0.2, y_terminal),
    (x_terminal + 0.2, y_terminal + 0.1),
    (x_terminal + 0.1, y_terminal + 0.1),
    (x_terminal, y_terminal + 0.1),
    (x_terminal, y_terminal),
  )
  samples = tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=terminal.downstream_mach,
      flow_angle_rad=terminal.downstream_flow_angle_rad,
      static_pressure_Pa=terminal.downstream_pressure_Pa,
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=gamma,
    )
    for point in points
  )
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=samples,
    position_tolerance_m=1.0e-10,
  )

  assert boundary.converged
  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    position_tolerance_m=1.0e-10,
  )

  assert field.status is MocMixedRegimeFieldStatus.CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD
  assert field.converged
  assert field.model_closure_verified
  assert field.potential_circulation_residual is not None
  assert field.potential_circulation_residual <= 1.0e-8


def test_compressible_potential_reference_rejects_incompatible_boundary_circulation() -> None:
  terminal = _terminal()
  samples = list(_samples(terminal))
  samples[1] = replace(samples[1], flow_angle_rad=0.5)
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=tuple(samples),
  )
  assert boundary.converged

  field = solve_mixed_regime_compressible_potential_field(boundary)

  assert field.status is MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE
  assert not field.converged
  assert field.model == 'compressible-isentropic-potential-reference'
  assert field.potential_circulation_residual is not None
  assert field.potential_circulation_residual > 0.0
  assert 'not single-valued' in field.message


def test_independent_potential_measurement_rechecks_the_solver_field() -> None:
  terminal = _terminal()
  boundary, condition = _pressure_outflow_boundary_and_condition(terminal)
  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    radial_divisions=2,
    downstream_condition=condition,
  )

  measurement = measure_mixed_regime_compressible_potential_field(field)

  assert measurement.status is MocMixedRegimePotentialMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.reference_model_verified
  assert measurement.boundary_verified
  assert measurement.potential_layout_verified
  assert measurement.downstream_condition_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.maximum_mass_conservation_residual is not None
  assert measurement.maximum_mass_conservation_residual <= 1.0e-8
  assert measurement.maximum_boundary_velocity_residual is not None
  assert measurement.maximum_boundary_velocity_residual <= 1.0e-8

  tampered = replace(
    field,
    velocity_potential=(field.velocity_potential[0] + 0.01, *field.velocity_potential[1:]),
  )
  tampered_measurement = measure_mixed_regime_compressible_potential_field(tampered)

  assert tampered_measurement.status is MocMixedRegimePotentialMeasurementStatus.RESIDUAL_FAILURE
  assert not tampered_measurement.converged
  assert tampered_measurement.reference_model_verified is False


def test_independent_potential_measurement_recomputes_tangent_boundary_normal_flux() -> None:
  terminal = _terminal()
  boundary, condition = _single_edge_slip_wall_boundary_and_condition(terminal)
  unconstrained = solve_mixed_regime_compressible_potential_field(boundary)
  assert unconstrained.converged

  field = replace(unconstrained, downstream_condition=condition)
  measurement = measure_mixed_regime_compressible_potential_field(field)

  assert measurement.status is MocMixedRegimePotentialMeasurementStatus.RESIDUAL_FAILURE
  assert not measurement.converged
  assert measurement.maximum_boundary_normal_velocity_residual is not None
  assert measurement.maximum_boundary_normal_velocity_residual > 1.0e-8
  assert not measurement.reference_model_verified


def test_field_solver_rejects_a_condition_from_a_different_scalar_boundary() -> None:
  terminal = _terminal()
  boundary, condition = _slip_wall_boundary_and_condition(terminal)
  other_boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  result = solve_mixed_regime_subsonic_field(
    other_boundary,
    downstream_condition=condition,
  )

  assert result.status is MocMixedRegimeFieldStatus.BOUNDARY_FAILURE
  assert not result.converged
  assert result.downstream_condition is None
  assert 'exact scalar boundary' in result.message


def test_mixed_regime_reference_rejects_nonpositive_radial_divisions() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  with pytest.raises(ValueError, match='radial_divisions must be a positive integer'):
    solve_mixed_regime_subsonic_field(boundary, radial_divisions=0)

  with pytest.raises(ValueError, match='radial_divisions must be a positive integer'):
    solve_mixed_regime_subsonic_field(boundary, radial_divisions=True)


def test_mixed_regime_closure_callback_requires_the_exact_terminal_seam() -> None:
  terminal = _terminal()
  boundary, condition = _pressure_outflow_boundary_and_condition(terminal)
  unqualified_field = solve_mixed_regime_subsonic_field(boundary)
  field = solve_mixed_regime_subsonic_field(
    boundary,
    downstream_condition=condition,
  )
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
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
  seen: list[MocMixedRegimePerimeterRequest] = []

  unqualified_result = run_mixed_regime_closure_solver(
    request,
    lambda _request: unqualified_field,
  )
  assert unqualified_result.status is MocMixedRegimeClosureStatus.FIELD_FAILURE
  assert not unqualified_result.converged
  assert unqualified_result.physical_closure_verified is False

  result = run_mixed_regime_closure_solver(
    request,
    lambda received: (seen.append(received) or field),
  )

  assert result.status is MocMixedRegimeClosureStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert seen == [request]

  other_terminal = solve_normal_shock_terminal(
    CharacteristicState(2.0, 0.0, 0.0, 2.0, 1.4),
    upstream_pressure_Pa=100000.0,
  )
  other_boundary = validate_mixed_regime_boundary(
    other_terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(other_terminal),
  )
  mismatched = solve_mixed_regime_subsonic_field(other_boundary)
  mismatch_result = run_mixed_regime_closure_solver(request, lambda _request: mismatched)
  assert mismatch_result.status is MocMixedRegimeClosureStatus.SEAM_FAILURE
  assert not mismatch_result.converged


def test_mixed_regime_closure_rejects_same_length_but_different_supersonic_patch() -> None:
  terminal = _terminal()
  patch = _supersonic_patch()
  boundary = validate_mixed_regime_boundary(
    terminal,
    patch,
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )
  field = solve_mixed_regime_subsonic_field(boundary)
  altered_patch = (
    patch[0],
    MocPostShockBoundaryState(
      point_m=patch[1].point_m,
      state=CharacteristicState(
        x_m=patch[1].state.x_m,
        y_m=patch[1].state.y_m,
        theta_rad=patch[1].state.theta_rad + 0.01,
        mach=patch[1].state.mach,
        gamma=patch[1].state.gamma,
      ),
      upstream_total_pressure_Pa=patch[1].upstream_total_pressure_Pa,
      downstream_total_pressure_Pa=patch[1].downstream_total_pressure_Pa,
    ),
  )
  altered_boundary = validate_mixed_regime_boundary(
    terminal,
    altered_patch,
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )
  altered_field = replace(field, boundary=altered_boundary)
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )

  result = run_mixed_regime_closure_solver(request, lambda _request: altered_field)

  assert result.status is MocMixedRegimeClosureStatus.SEAM_FAILURE
  assert not result.converged
  assert 'exact supersonic patch' in result.message


def test_mixed_regime_perimeter_request_rejects_inconsistent_terminal_scalars() -> None:
  terminal = _terminal()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None

  with pytest.raises(ValueError, match='does not match the terminal shock result'):
    MocMixedRegimePerimeterRequest(
      terminal=terminal,
      terminal_point_m=terminal.shock_point_m,
      terminal_downstream_mach=terminal.downstream_mach,
      terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
      terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa + 1.0,
      terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      terminal_total_pressure_ratio=terminal.total_pressure_ratio,
      supersonic_patch=_supersonic_patch(),
    )


def test_mixed_regime_boundary_rejects_missing_scalar_field() -> None:
  result = validate_mixed_regime_boundary(
    _terminal(),
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=(),
  )

  assert result.status is MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE
  assert not result.converged
  assert result.supersonic_patch_verified
  assert result.chain_promotion_blocked


def test_mixed_regime_boundary_rejects_total_pressure_gain() -> None:
  terminal = _terminal()
  assert terminal.downstream_total_pressure_Pa is not None
  result = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(
      terminal,
      interior_total_pressure=terminal.downstream_total_pressure_Pa * 1.1,
    ),
  )

  assert result.status is MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE
  assert not result.converged
  assert result.terminal_continuity_verified
  assert not result.total_pressure_lineage_verified


def test_mixed_regime_boundary_distributed_profile_requires_explicit_opt_in() -> None:
  terminal = _terminal()
  assert terminal.downstream_total_pressure_Pa is not None
  result = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(
      terminal,
      interior_total_pressure=terminal.downstream_total_pressure_Pa * 1.1,
    ),
    allow_distributed_total_pressure_profile=True,
  )

  assert result.status is MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF
  assert result.converged
  assert result.total_pressure_lineage_verified
  assert result.maximum_total_pressure_gain_Pa is not None
  assert result.maximum_total_pressure_gain_Pa > 0.0
  assert 'distributed-profile' in result.message


def test_downstream_condition_can_select_only_the_declared_boundary_edges() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  result = validate_mixed_regime_downstream_condition(
    boundary,
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )

  assert result.converged
  assert result.condition_edge_indices == (0,)
  assert result.condition_sample_indices == (0, 1)
  assert result.pressure_residuals_Pa == (0.0, 0.0)


def test_control_section_validator_requires_explicit_flux_bearing_geometry() -> None:
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

  result = validate_mixed_regime_control_section(request, None)

  assert result.status is MocMixedRegimeControlSectionStatus.INVALID_INPUT
  assert not result.converged
  assert not result.physical_closure_verified
  assert result.chain_promotion_blocked
  assert 'area or mass flux' in result.message


def test_control_section_validator_accepts_terminal_equivalent_scalar_section() -> None:
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
  section = _terminal_equivalent_control_section(request)

  result = validate_mixed_regime_control_section(request, section)

  assert result.status is MocMixedRegimeControlSectionStatus.CONVERGED
  assert result.converged
  assert result.section is section
  assert result.section_measure_m == pytest.approx(0.02)
  assert result.mass_flux_proxy is not None
  assert result.mass_flux_proxy > 0.0
  assert result.minimum_normal_flux_factor == pytest.approx(1.0)
  assert result.maximum_isentropic_residual is not None
  assert result.maximum_isentropic_residual <= 1.0e-8
  assert result.maximum_terminal_state_residual == pytest.approx(0.0)
  assert not result.physical_closure_verified
  assert result.chain_promotion_blocked


def test_control_section_measurement_rechecks_the_section_independently() -> None:
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
  section = _terminal_equivalent_control_section(request)

  measurement = measure_mixed_regime_control_section(request, section)

  assert measurement.status is MocMixedRegimeControlSectionMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.request_verified
  assert measurement.geometry_verified
  assert measurement.state_verified
  assert measurement.flux_verified
  assert measurement.terminal_equivalent_verified
  assert measurement.mass_flux_proxy is not None
  assert measurement.mass_flux_proxy > 0.0
  assert not measurement.physical_closure_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_control_section_reference_uses_measure_and_rejects_varying_section_projection() -> None:
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
  section = _terminal_equivalent_control_section(request)

  result = solve_mixed_regime_downstream_free_boundary_from_control_section(
    request,
    section,
    ambient_pressure_Pa=0.8 * terminal.downstream_pressure_Pa,
    downstream_length_m=0.05,
    free_boundary_sample_count=7,
    radial_divisions=2,
  )

  assert result.status is MocMixedRegimeFreeBoundaryStatus.CONVERGED_REFERENCE
  assert result.converged
  assert result.physical_closure_verified
  assert result.effective_inlet_height_m == pytest.approx(section.section_measure_m)
  assert result.control_section is section
  assert result.control_section_validation is not None
  assert result.control_section_validation.converged
  assert result.model == 'solver-owned-control-section-quasi-1d-reference'
  assert result.chain_promotion_blocked

  terminal_x, terminal_y = request.terminal_point_m
  varying_mach = request.terminal_downstream_mach + 0.01
  gamma = request.terminal.upstream_state.gamma
  varying_static_pressure = request.terminal_downstream_total_pressure_Pa / (
    1.0 + 0.5 * (gamma - 1.0) * varying_mach**2
  ) ** (gamma / (gamma - 1.0))
  varying_points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  varying_section = MocMixedRegimeControlSection(
    points_m=varying_points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=varying_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=varying_static_pressure,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
      for point in varying_points
    ),
    normal_angle_rad=0.0,
  )

  varying_result = solve_mixed_regime_downstream_free_boundary_from_control_section(
    request,
    varying_section,
    ambient_pressure_Pa=0.8 * terminal.downstream_pressure_Pa,
    downstream_length_m=0.05,
  )

  assert varying_result.status is MocMixedRegimeFreeBoundaryStatus.CONTROL_SECTION_FAILURE
  assert not varying_result.converged
  assert varying_result.closure is None
  assert varying_result.control_section_validation is not None
  assert varying_result.control_section_validation.converged
  assert 'two-dimensional mixed-regime coupling' in varying_result.message
  assert varying_result.chain_promotion_blocked


def test_integrated_flux_reference_retains_varying_control_section_flux() -> None:
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
  section = _terminal_equivalent_control_section(request)
  varying_mach = request.terminal_downstream_mach + 0.01
  gamma = request.terminal.upstream_state.gamma
  varying_static_pressure = request.terminal_downstream_total_pressure_Pa / (
    1.0 + 0.5 * (gamma - 1.0) * varying_mach**2
  ) ** (gamma / (gamma - 1.0))
  varying_section = replace(
    section,
    samples=tuple(
      replace(
        sample,
        mach=varying_mach,
        static_pressure_Pa=varying_static_pressure,
      )
      for sample in section.samples
    ),
  )

  result = solve_mixed_regime_downstream_free_boundary_from_control_section(
    request,
    varying_section,
    ambient_pressure_Pa=0.8 * terminal.downstream_pressure_Pa,
    downstream_length_m=0.05,
    free_boundary_sample_count=7,
    radial_divisions=2,
    use_integrated_flux=True,
  )

  assert result.status is MocMixedRegimeFreeBoundaryStatus.CONVERGED_REFERENCE
  assert result.converged
  assert result.physical_closure_verified
  assert result.control_section is varying_section
  assert result.control_section_validation is not None
  assert result.control_section_validation.converged
  assert result.control_section_projection_verified is False
  assert result.control_section_flux_proxy == pytest.approx(
    varying_section.mass_flux_proxy
  )
  assert result.control_section_flux_equivalent_height_m == pytest.approx(
    result.effective_inlet_height_m
  )
  assert result.control_section_flux_residual is not None
  assert result.control_section_flux_residual <= 1.0e-8
  assert result.control_section_flux_verified
  assert result.effective_inlet_height_m != pytest.approx(
    varying_section.section_measure_m
  )
  assert result.model == 'solver-owned-control-section-flux-quasi-1d-reference'
  assert result.chain_promotion_blocked

  measurement = measure_mixed_regime_free_boundary_reference(result)

  assert measurement.status is MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.control_section_verified
  assert measurement.control_section_flux_verified
  assert measurement.control_section_flux_residual is not None
  assert measurement.control_section_flux_residual <= 1.0e-8
  assert measurement.physical_closure_verified
  assert measurement.chain_promotion_blocked

  tampered = replace(
    result,
    control_section_flux_proxy=result.control_section_flux_proxy * 1.01,
  )
  tampered_measurement = measure_mixed_regime_free_boundary_reference(tampered)

  assert not tampered_measurement.converged
  assert tampered_measurement.control_section_verified
  assert tampered_measurement.control_section_flux_verified is False
  assert tampered_measurement.physical_closure_verified is False


def test_planar_downstream_handoff_requires_and_retains_a_varying_control_section() -> None:
  terminal = _terminal()
  patch = _supersonic_patch()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )
  terminal_x, terminal_y = request.terminal_point_m
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      (terminal_x, terminal_y),
      (terminal_x + 0.1, terminal_y + 0.1),
      (terminal_x + 0.2, terminal_y + 0.1),
      (terminal_x + 0.2, terminal_y),
      (terminal_x, terminal_y),
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )

  def sample_at(
    received: MocMixedRegimePerimeterRequest,
    _index: int,
    point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=received.terminal_downstream_mach,
      flow_angle_rad=received.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=received.terminal_downstream_pressure_Pa,
      total_pressure_Pa=received.terminal_downstream_total_pressure_Pa,
      gamma=received.terminal.upstream_state.gamma,
    )

  scalar_closure = solve_mixed_regime_downstream_perimeter(
    request,
    perimeter_spec,
    sample_at,
    radial_divisions=2,
  )
  assert scalar_closure.field is not None
  assert scalar_closure.field.physical_closure_verified

  varying_mach = request.terminal_downstream_mach + 0.01
  gamma = request.terminal.upstream_state.gamma
  varying_static_pressure = request.terminal_downstream_total_pressure_Pa / (
    1.0 + 0.5 * (gamma - 1.0) * varying_mach * varying_mach
  ) ** (gamma / (gamma - 1.0))
  section_points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  section = MocMixedRegimeControlSection(
    points_m=section_points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=varying_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=varying_static_pressure,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
      for point in section_points
    ),
    normal_angle_rad=0.0,
  )
  callback_arguments: list[object] = []

  def solve_field(
    received: MocMixedRegimePerimeterRequest,
    received_section: MocMixedRegimeControlSection,
    received_specification: MocMixedRegimeDownstreamPerimeterSpec,
  ) -> MocMixedRegimeFieldResult:
    callback_arguments.extend((received, received_section, received_specification))
    return replace(scalar_closure.field, control_section=received_section)

  result = run_mixed_regime_planar_field_solver(
    request,
    section,
    perimeter_spec,
    solve_field,
  )

  assert result.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF
  assert result.converged
  assert result.handoff_verified
  assert result.section_is_varying
  assert result.field is not scalar_closure.field
  assert result.field.control_section == section
  assert result.field_physical_closure_verified
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert callback_arguments == [request, section, perimeter_spec]
  assert result.closure is not None
  assert result.closure.converged
  assert result.closure.physical_closure_verified

  ignored_section = run_mixed_regime_planar_field_solver(
    request,
    section,
    perimeter_spec,
    lambda _request, _section, _specification: scalar_closure.field,
  )
  assert ignored_section.status is MocMixedRegimePlanarSolveStatus.SEAM_FAILURE
  assert 'control section' in ignored_section.message
  assert ignored_section.chain_promotion_blocked

  pressure_mismatch_spec = replace(
    perimeter_spec,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa + 1.0,
  )
  pressure_mismatch = run_mixed_regime_planar_field_solver(
    request,
    section,
    pressure_mismatch_spec,
    solve_field,
  )
  assert pressure_mismatch.status is MocMixedRegimePlanarSolveStatus.SEAM_FAILURE
  assert not pressure_mismatch.converged
  assert 'pressure samples' in pressure_mismatch.message
  assert pressure_mismatch.chain_promotion_blocked


def test_planar_downstream_handoff_rejects_a_changed_perimeter() -> None:
  terminal = _terminal()
  patch = _supersonic_patch()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=patch,
  )
  section = _terminal_equivalent_control_section(request)
  point = request.terminal_point_m
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      point,
      (point[0] + 0.1, point[1] + 0.1),
      (point[0] + 0.2, point[1] + 0.1),
      (point[0] + 0.2, point[1]),
      point,
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )

  def sample_at(
    received: MocMixedRegimePerimeterRequest,
    _index: int,
    sample_point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    return MocMixedRegimeFieldSample(
      point_m=sample_point,
      mach=received.terminal_downstream_mach,
      flow_angle_rad=received.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=received.terminal_downstream_pressure_Pa,
      total_pressure_Pa=received.terminal_downstream_total_pressure_Pa,
      gamma=received.terminal.upstream_state.gamma,
    )

  scalar_closure = solve_mixed_regime_downstream_perimeter(
    request,
    perimeter_spec,
    sample_at,
  )
  assert scalar_closure.field is not None
  changed_boundary = replace(
    scalar_closure.field.boundary,
    perimeter_points_m=(
      point,
      (point[0] + 0.1, point[1] + 0.1),
      (point[0] + 0.2, point[1] + 0.1),
      (point[0] + 0.2, point[1] + 0.001),
      point,
    ),
  )
  assert scalar_closure.field.downstream_condition is not None
  changed_condition = replace(
    scalar_closure.field.downstream_condition,
    boundary=changed_boundary,
  )
  changed_field = replace(
    scalar_closure.field,
    boundary=changed_boundary,
    downstream_condition=changed_condition,
    control_section=section,
  )

  result = run_mixed_regime_planar_field_solver(
    request,
    section,
    perimeter_spec,
    lambda _request, _section, _specification: changed_field,
  )

  assert result.status is MocMixedRegimePlanarSolveStatus.PERIMETER_FAILURE
  assert not result.converged
  assert not result.handoff_verified
  assert result.field is changed_field
  assert result.chain_promotion_blocked
  assert 'perimeter geometry' in result.message


def test_planar_potential_reference_projects_a_varying_section_into_a_nonlinear_field() -> None:
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
  sonic_factor = 0.5 * (gamma - 1.0)
  terminal_speed = request.terminal_downstream_mach / sqrt(
    1.0 + sonic_factor * request.terminal_downstream_mach ** 2
  )
  section_points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  section_samples = []
  for point in section_points:
    tangential_speed = 0.12 * (point[1] - terminal_y)
    speed_squared = terminal_speed ** 2 + tangential_speed ** 2
    mach = sqrt(speed_squared / (1.0 - sonic_factor * speed_squared))
    static_pressure = request.terminal_downstream_total_pressure_Pa / (
      1.0 + sonic_factor * mach ** 2
    ) ** (gamma / (gamma - 1.0))
    section_samples.append(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=mach,
        flow_angle_rad=atan2(tangential_speed, terminal_speed),
        static_pressure_Pa=static_pressure,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
    )
  section = MocMixedRegimeControlSection(
    points_m=section_points,
    samples=tuple(section_samples),
    normal_angle_rad=0.0,
  )
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      (terminal_x, terminal_y),
      (terminal_x + 0.1, terminal_y),
      (terminal_x + 0.1, terminal_y + 0.1),
      (terminal_x, terminal_y + 0.1),
      (terminal_x, terminal_y),
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )

  result = MocMixedRegimePlanarPotentialReference(
    radial_divisions=2,
  ).solve(request, section, perimeter_spec)

  assert result.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF
  assert result.converged
  assert result.handoff_verified
  assert result.section_is_varying
  assert result.control_section_projection_verified
  assert result.maximum_control_section_projection_residual is not None
  assert result.maximum_control_section_projection_residual <= 1.0e-8
  assert result.projection_model == (
    'affine-control-section-potential-extension'
  )
  assert result.field is not None
  assert result.field.model == 'compressible-isentropic-potential-reference'
  assert result.field.control_section is section
  assert result.field.model_closure_verified
  assert result.field.velocity_potential
  assert result.field.nonlinear_update_residual is not None
  assert result.field.nonlinear_update_residual <= 1.0e-8
  assert result.field_physical_closure_verified
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.closure is not None
  assert result.closure.converged

  direct_result = solve_mixed_regime_planar_potential_reference(
    request,
    section,
    perimeter_spec,
    radial_divisions=2,
  )
  assert direct_result.as_report()['projection_model'] == (
    'affine-control-section-potential-extension'
  )

  non_affine_samples = list(section.samples)
  non_affine_samples[1] = replace(
    non_affine_samples[1],
    flow_angle_rad=atan2(0.003, terminal_speed),
  )
  non_affine_section = replace(
    section,
    samples=tuple(non_affine_samples),
  )
  rejected = MocMixedRegimePlanarPotentialReference(
    radial_divisions=2,
  ).solve(request, non_affine_section, perimeter_spec)
  assert rejected.status is MocMixedRegimePlanarSolveStatus.CONTROL_SECTION_FAILURE
  assert not rejected.converged
  assert not rejected.control_section_projection_verified
  assert 'affine' in rejected.message


def test_planar_frozen_profile_reference_preserves_non_affine_data_without_extrapolation() -> None:
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
  sonic_factor = 0.5 * (gamma - 1.0)
  terminal_speed = request.terminal_downstream_mach / sqrt(
    1.0 + sonic_factor * request.terminal_downstream_mach ** 2
  )

  def sample_at(
    point: tuple[float, float],
    tangential_speed: float,
  ) -> MocMixedRegimeFieldSample:
    speed_squared = terminal_speed ** 2 + tangential_speed ** 2
    mach = sqrt(speed_squared / (1.0 - sonic_factor * speed_squared))
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=mach,
      flow_angle_rad=atan2(tangential_speed, terminal_speed),
      static_pressure_Pa=request.terminal_downstream_total_pressure_Pa / (
        1.0 + sonic_factor * mach * mach
      ) ** (gamma / (gamma - 1.0)),
      total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
      gamma=gamma,
    )

  section_points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  section = MocMixedRegimeControlSection(
    points_m=section_points,
    samples=tuple(
      sample_at(point, tangential_speed)
      for point, tangential_speed in zip(
        section_points,
        (0.002, 0.0, 0.002),
        strict=True,
      )
    ),
    normal_angle_rad=0.0,
  )
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      (terminal_x, terminal_y),
      (terminal_x + 0.1, terminal_y),
      (terminal_x + 0.1, terminal_y + 0.01),
      (terminal_x, terminal_y + 0.01),
      (terminal_x, terminal_y),
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )

  reference = MocMixedRegimePlanarFrozenProfileReference(radial_divisions=2)
  result = reference.solve(request, section, perimeter_spec)

  assert result.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF
  assert result.converged
  assert result.handoff_verified
  assert result.section_is_varying
  assert result.control_section_projection_verified
  assert result.maximum_control_section_projection_residual is not None
  assert result.maximum_control_section_projection_residual <= 1.0e-8
  assert result.projection_model == (
    'piecewise-linear-frozen-transverse-profile'
  )
  assert result.field is not None
  assert result.field.model == 'compressible-isentropic-potential-reference'
  assert result.field.control_section is section
  assert result.field.model_closure_verified
  assert result.field_physical_closure_verified
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  measurement = measure_mixed_regime_compressible_potential_field(result.field)
  assert measurement.converged
  assert measurement.reference_model_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert reference.as_report()['extrapolation_allowed'] is False

  outside_span_spec = replace(
    perimeter_spec,
    perimeter_points_m=(
      (terminal_x, terminal_y),
      (terminal_x + 0.1, terminal_y),
      (terminal_x + 0.1, terminal_y + 0.02),
      (terminal_x, terminal_y + 0.02),
      (terminal_x, terminal_y),
    ),
  )
  outside_span = solve_mixed_regime_planar_frozen_profile_reference(
    request,
    section,
    outside_span_spec,
    radial_divisions=2,
  )
  assert outside_span.status is MocMixedRegimePlanarSolveStatus.CONTROL_SECTION_FAILURE
  assert not outside_span.converged
  assert not outside_span.control_section_projection_verified
  assert 'extrapolation is disabled' in outside_span.message


def test_solver_owned_free_boundary_reference_shoots_height_and_closes_scalar_field() -> None:
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

  result = solve_mixed_regime_downstream_free_boundary(
    request,
    ambient_pressure_Pa=0.8 * terminal.downstream_pressure_Pa,
    effective_inlet_height_m=0.01,
    downstream_length_m=0.05,
    free_boundary_sample_count=7,
    radial_divisions=2,
  )

  assert result.status is MocMixedRegimeFreeBoundaryStatus.CONVERGED_REFERENCE
  assert result.converged
  assert result.physical_closure_verified
  assert result.field is not None
  assert result.field.model == 'solver-owned-subsonic-free-boundary-reference'
  assert result.field.mixed_regime_field_complete
  assert result.field.chain_promotion_blocked
  assert result.field.maximum_mass_conservation_residual is not None
  assert result.field.maximum_mass_conservation_residual <= 1.0e-8
  assert result.closure is not None
  assert result.closure.downstream_condition == result.downstream_condition
  assert result.closure.perimeter_spec == result.perimeter_spec
  assert result.downstream_condition is not None
  assert result.downstream_condition.condition_edge_indices
  assert result.downstream_condition.condition_sample_indices
  assert result.iteration_count > 0
  assert result.pressure_residual_Pa is not None
  assert result.pressure_residual_Pa <= 1.0e-8 * terminal.downstream_pressure_Pa
  assert result.production_claim_allowed is False
  assert result.chain_promotion_blocked


def test_independent_free_boundary_measurement_rechecks_the_reference_lane() -> None:
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
  result = solve_mixed_regime_downstream_free_boundary(
    request,
    ambient_pressure_Pa=0.8 * terminal.downstream_pressure_Pa,
    effective_inlet_height_m=0.01,
    downstream_length_m=0.05,
    free_boundary_sample_count=7,
    radial_divisions=2,
  )

  measurement = measure_mixed_regime_free_boundary_reference(result)

  assert measurement.status is MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.request_verified
  assert measurement.perimeter_spec_verified
  assert measurement.boundary_verified
  assert measurement.downstream_condition_verified
  assert measurement.closure_verified
  assert measurement.field_model_verified
  assert measurement.field_layout_verified
  assert measurement.scalar_root_verified
  assert measurement.mass_flow_verified
  assert measurement.physical_closure_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.maximum_velocity_divergence_residual is not None
  assert measurement.maximum_velocity_divergence_residual > 1.0

  assert result.outlet_height_m is not None
  tampered = replace(
    result,
    outlet_height_m=result.outlet_height_m * 1.1,
  )
  tampered_measurement = measure_mixed_regime_free_boundary_reference(tampered)

  assert tampered_measurement.status is not MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED
  assert not tampered_measurement.converged
  assert not tampered_measurement.scalar_root_verified


def test_independent_free_boundary_refinement_rechecks_declared_resolution() -> None:
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
  cases = tuple(
    MocMixedRegimeFreeBoundaryRefinementCase(
      resolution=resolution,
      result=solve_mixed_regime_downstream_free_boundary(
        request,
        ambient_pressure_Pa=0.8 * terminal.downstream_pressure_Pa,
        effective_inlet_height_m=0.01,
        downstream_length_m=0.05,
        free_boundary_sample_count=resolution,
        radial_divisions=2,
      ),
    )
    for resolution in (5, 7, 9)
  )

  measurement = measure_mixed_regime_free_boundary_refinement(cases)

  assert measurement.status is MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.resolutions == (5, 7, 9)
  assert measurement.perimeter_sample_counts[0] < measurement.perimeter_sample_counts[1]
  assert measurement.perimeter_sample_counts[1] < measurement.perimeter_sample_counts[2]
  assert measurement.request_consistent
  assert measurement.solver_parameters_consistent
  assert measurement.radial_divisions_consistent
  assert measurement.case_measurements_verified
  assert measurement.scalar_root_verified
  assert measurement.mass_flow_verified
  assert measurement.geometry_verified
  assert measurement.local_reference_closure_verified
  assert measurement.refinement_convergence_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert len(measurement.outlet_height_delta_residuals_m) == 2

  reversed_measurement = measure_mixed_regime_free_boundary_refinement(
    (cases[1], cases[0]),
  )

  assert reversed_measurement.status is MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.RESOLUTION_FAILURE
  assert not reversed_measurement.converged
