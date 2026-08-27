from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocCharacteristicCell,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainGeometryFidelity,
  MocPostShockBoundaryState,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
  MocPrescribedMixedRegimeClosureMock,
  assemble_post_shock_characteristic_field,
  plan_prescribed_post_shock_chain_mock,
  solve_marched_ambient_attachment_shock_cell_transition,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.validation.moc_measurements import (
  MocChainPlannerMeasurementStatus,
  MocTerminalClosureMeasurementStatus,
  MocTerminalClosureObservation,
  MocShockCellMeasurementStatus,
  MocShockCellObservation,
  measure_moc_terminal_closure,
  measure_moc_shock_cell,
  measure_moc_shock_cell_chain,
  measure_moc_chain_planner,
)


def _observation(
  *,
  cell_index: int = 1,
  shock_start_x_m: float = 0.0,
  pressure_loss: bool = True,
  centerline_points: tuple[tuple[float, float], ...] | None = None,
) -> MocShockCellObservation:
  shock = (
    (shock_start_x_m, 1.0),
    (shock_start_x_m + 1.0, 0.5),
    (shock_start_x_m + 2.0, 0.0),
  )
  if centerline_points is None:
    centerline_points = (
      (shock_start_x_m + 2.0, 0.0),
      (shock_start_x_m + 3.0, 0.0),
    )
  cells = (
    MocCharacteristicCell(
      cell_index=0,
      cell_kind='measurement-fixture',
      vertices_xr_m=(
        shock[0],
        shock[1],
        shock[2],
        centerline_points[-1],
      ),
      centerline_indices=(0,),
      boundary_indices=(0, 1),
    ),
  )
  return MocShockCellObservation(
    cell_index=cell_index,
    shock_boundary_points_m=shock,
    centerline_boundary_points_m=centerline_points,
    cells=cells,
    upstream_total_pressure_Pa=(2.0e6,) * len(shock),
    downstream_total_pressure_Pa=(1.8e6 if pressure_loss else 2.0e6,) * len(shock),
  )


def _terminal_field():
  reference = solve_uniform_attached_shock_field(
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
    sample_count=17,
  )
  assert reference.shock_fit is not None
  first = reference.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach * first.state.mach
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  transition = solve_marched_ambient_attachment_shock_cell_transition(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.0,
    0.1,
    sample_count=17,
  )
  assert transition.terminal_field is not None
  return transition.terminal_field


def _planner_fixture():
  points = (
    (0.76, 0.165),
    (0.78, 0.110),
    (0.80, 0.055),
    (0.82, 0.0),
  )
  boundary = tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.1 * (3 - index),
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    )
    for index, point in enumerate(points)
  )
  field = assemble_post_shock_characteristic_field(
    MocShockBoundaryFitResult(
      status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
      boundary_states=boundary,
      shock_angle_residuals_rad=(0.0,) * len(boundary),
      maximum_shock_angle_residual_rad=0.0,
    )
  )
  return plan_prescribed_post_shock_chain_mock(
    field,
    start_x_m=0.7,
    end_x_m=1.0,
  )


def test_moc_measurement_extracts_geometry_and_shock_pressure_loss() -> None:
  result = measure_moc_shock_cell(_observation())

  assert result.status is MocShockCellMeasurementStatus.CONVERGED
  assert result.converged
  assert result.axial_extent_m == pytest.approx((0.0, 3.0))
  assert result.axial_length_m == pytest.approx(3.0)
  assert result.maximum_radius_m == pytest.approx(1.0)
  assert result.mesh_area_m2 == pytest.approx(result.perimeter_area_m2)
  assert result.pressure_loss_verified is True
  assert result.minimum_total_pressure_ratio == pytest.approx(0.9)
  assert result.as_report()['claim_status'] == 'not_accepted'


def test_moc_measurement_requires_explicit_perimeter_edges() -> None:
  observation = _observation(
    centerline_points=((2.0, 0.0), (2.5, 0.0), (3.0, 0.0)),
  )

  result = measure_moc_shock_cell(observation)

  assert result.status is MocShockCellMeasurementStatus.GEOMETRY_FAILURE
  assert 'perimeter edges' in result.message


def test_moc_measurement_keeps_pressure_loss_as_a_separate_gate() -> None:
  result = measure_moc_shock_cell(_observation(pressure_loss=False))

  assert result.status is MocShockCellMeasurementStatus.PRESSURE_FAILURE
  assert result.pressure_loss_verified is False
  assert 'reduce total pressure' in result.message


def test_moc_chain_measurement_preserves_cell_order_and_spacing() -> None:
  result = measure_moc_shock_cell_chain(
    (
      _observation(cell_index=1, shock_start_x_m=0.0),
      _observation(cell_index=2, shock_start_x_m=4.0),
    )
  )

  assert result.status is MocShockCellMeasurementStatus.CONVERGED
  assert result.shock_start_spacing_m == pytest.approx((4.0,))
  assert result.axial_extent_m == pytest.approx((0.0, 7.0))
  assert result.as_report()['cell_count'] == 2


def test_moc_chain_measurement_verifies_exact_state_pressure_handoff() -> None:
  handoff = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=3.0 + index,
        y_m=0.05 * (2 - index),
        theta_rad=0.01 * index,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.8e6 - 1.0e4 * index,
    )
    for index in range(3)
  )
  first = replace(
    _observation(cell_index=1, shock_start_x_m=0.0),
    outgoing_handoff=handoff,
    outgoing_boundary_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
  )
  second = replace(
    _observation(cell_index=2, shock_start_x_m=4.0),
    incoming_handoff=handoff,
    incoming_boundary_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
  )

  result = measure_moc_shock_cell_chain((first, second))

  assert result.status is MocShockCellMeasurementStatus.CONVERGED
  assert result.handoff_link_count == 1
  assert result.handoff_links_verified is True
  assert result.as_report()['handoff']['links_verified'] is True


def test_moc_chain_measurement_rejects_tampered_state_pressure_handoff() -> None:
  handoff = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=3.0 + index,
        y_m=0.05 * (2 - index),
        theta_rad=0.01 * index,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.8e6 - 1.0e4 * index,
    )
    for index in range(3)
  )
  tampered = replace(handoff[1], total_pressure_Pa=1.7e6)
  first = replace(
    _observation(cell_index=1, shock_start_x_m=0.0),
    outgoing_handoff=handoff,
    outgoing_boundary_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
  )
  second = replace(
    _observation(cell_index=2, shock_start_x_m=4.0),
    incoming_handoff=(handoff[0], tampered, handoff[2]),
    incoming_boundary_kind=MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
  )

  result = measure_moc_shock_cell_chain((first, second))

  assert result.status is MocShockCellMeasurementStatus.CHAIN_FAILURE
  assert result.handoff_link_count == 1
  assert result.handoff_links_verified is False
  assert 'exact state/pressure' in result.message


def test_moc_chain_measurement_rejects_reordered_indices() -> None:
  result = measure_moc_shock_cell_chain(
    (
      _observation(cell_index=2),
      _observation(cell_index=1, shock_start_x_m=4.0),
    )
  )

  assert result.status is MocShockCellMeasurementStatus.CHAIN_FAILURE
  assert 'contiguous' in result.message


def test_moc_chain_planner_measurement_recomputes_trace_handoffs() -> None:
  planner = _planner_fixture()

  result = measure_moc_chain_planner(planner)

  assert result.status is MocChainPlannerMeasurementStatus.CONVERGED
  assert result.converged
  assert result.chain_cell_count == 3
  assert result.step_count == 3
  assert result.chain_cells_contiguous
  assert result.chain_topology_verified
  assert result.step_sequence_verified
  assert result.incoming_handoffs_verified
  assert result.returned_handoffs_verified
  assert result.handoff_link_count == 2
  assert result.handoff_links_verified is True
  assert result.termination_verified
  assert result.fidelity_isolation_verified
  assert result.physical_termination is False
  assert result.production_claim_allowed is False
  assert result.as_report()['operator_id'] == 'op.moc.chain-planner'


def test_moc_chain_planner_measurement_rejects_tampered_handoff_metadata() -> None:
  planner = _planner_fixture()
  tampered_step = replace(
    planner.steps[1],
    incoming_handoff_fingerprint='0' * 64,
  )
  tampered = replace(
    planner,
    steps=(planner.steps[0], tampered_step, *planner.steps[2:]),
  )

  result = measure_moc_chain_planner(tampered)

  assert result.status is MocChainPlannerMeasurementStatus.HANDOFF_FAILURE
  assert result.converged is False
  assert result.handoff_links_verified is None
  assert 'current-cell handoff' in result.message


def test_moc_chain_planner_measurement_rejects_reduced_order_cell() -> None:
  planner = _planner_fixture()
  reduced_order_cell = replace(
    planner.chain.cells[1],
    geometry_fidelity=MocChainGeometryFidelity.SCALED_REDUCED_ORDER,
  )
  tampered_chain = replace(
    planner.chain,
    cells=(planner.chain.cells[0], reduced_order_cell, planner.chain.cells[2]),
  )
  tampered = replace(planner, chain=tampered_chain)

  result = measure_moc_chain_planner(tampered)

  assert result.status is MocChainPlannerMeasurementStatus.FIDELITY_FAILURE
  assert result.fidelity_isolation_verified is False
  assert result.production_claim_allowed is False


def test_terminal_measurement_keeps_an_open_mixed_regime_boundary_blocked() -> None:
  field = _terminal_field()

  result = measure_moc_terminal_closure(
    MocTerminalClosureObservation(terminal_field=field)
  )

  assert result.status is MocTerminalClosureMeasurementStatus.MIXED_REGIME_FAILURE
  assert result.terminal_normal_shock_verified
  assert result.terminal_shock_geometry_verified
  assert result.terminal_pressure_loss_verified
  assert result.supersonic_patch_verified
  assert result.physical_closure_verified is False
  assert result.physical_termination_verified is False
  assert result.chain_promotion_blocked
  assert result.as_report()['counts']['terminal_shock_edge_count'] > 0


def test_terminal_measurement_rechecks_an_explicit_mixed_regime_attachment() -> None:
  field = _terminal_field()
  mock = MocPrescribedMixedRegimeClosureMock(radial_divisions=2)
  closure = mock.solve(field.mixed_regime_perimeter_request())

  result = measure_moc_terminal_closure(
    MocTerminalClosureObservation(
      terminal_field=field,
      mixed_regime_closure=closure,
    )
  )

  assert result.status is MocTerminalClosureMeasurementStatus.CONVERGED
  assert result.mixed_regime_request_verified
  assert result.mixed_regime_boundary_verified
  assert result.mixed_regime_model_verified
  assert result.downstream_condition_verified
  assert result.physical_closure_verified
  assert result.physical_termination_verified
  assert result.chain_promotion_blocked
  assert result.maximum_thermodynamic_residual == pytest.approx(0.0, abs=1.0e-12)
  assert result.as_report()['mixed_regime_topology']['forms_closed_zone'] is True


def test_terminal_measurement_does_not_trust_reported_mixed_regime_status() -> None:
  field = _terminal_field()
  mock = MocPrescribedMixedRegimeClosureMock(radial_divisions=2)
  closure = mock.solve(field.mixed_regime_perimeter_request())
  assert closure.field is not None
  corrupted_sample = replace(
    closure.field.nodes[0],
    static_pressure_Pa=closure.field.nodes[0].static_pressure_Pa * 1.1,
  )
  corrupted_field = replace(
    closure.field,
    nodes=(corrupted_sample, *closure.field.nodes[1:]),
  )
  corrupted_closure = replace(closure, field=corrupted_field)

  result = measure_moc_terminal_closure(
    MocTerminalClosureObservation(
      terminal_field=field,
      mixed_regime_closure=corrupted_closure,
    )
  )

  assert result.status is MocTerminalClosureMeasurementStatus.MIXED_REGIME_FAILURE
  assert result.mixed_regime_model_verified is False
  assert result.maximum_thermodynamic_residual is not None
  assert result.maximum_thermodynamic_residual > 1.0e-8
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
