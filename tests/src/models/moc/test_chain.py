from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  MocCellClosureStatus,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainGeometryFidelity,
  MocChainTerminationDecision,
  MocChainStatus,
  MocChainTerminationReason,
  MocCharacteristicTraceStatus,
  MocCharacteristicCell,
  CharacteristicFamily,
  CharacteristicState,
  continue_moc_cell_chain,
  validate_characteristic_trace,
)


def _mesh(offset_m: float) -> tuple[MocCharacteristicCell, ...]:
  return (
    MocCharacteristicCell(
      cell_index=0,
      cell_kind='test-lower',
      vertices_xr_m=((offset_m, 0.0), (offset_m + 1.0, 0.0), (offset_m + 1.0, 1.0)),
      centerline_indices=(0, 1),
      boundary_indices=(0,),
    ),
    MocCharacteristicCell(
      cell_index=1,
      cell_kind='test-upper',
      vertices_xr_m=((offset_m, 0.0), (offset_m + 1.0, 1.0), (offset_m, 1.0)),
      centerline_indices=(0, 1),
      boundary_indices=(0,),
    ),
  )


def _cell(
    index: int,
    start_x_m: float,
    *,
    fidelity: MocChainGeometryFidelity = MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
    closure: MocCellClosureStatus = MocCellClosureStatus.CLOSED,
) -> MocChainCell:
  return MocChainCell(
    cell_index=index,
    start_x_m=start_x_m,
    end_x_m=start_x_m + 1.0,
    mesh=_mesh(start_x_m),
    geometry_fidelity=fidelity,
    physical_closure=closure,
  )


def _stateful_cell(
  index: int,
  start_x_m: float,
  *,
  total_pressure_Pa: float = 1.0e6,
  boundary_kind: MocChainBoundaryKind = MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE,
) -> MocChainCell:
  boundary = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=start_x_m + offset,
        y_m=0.1 * (2 - offset),
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=total_pressure_Pa,
    )
    for offset in range(3)
  )
  return MocChainCell(
    cell_index=index,
    start_x_m=start_x_m,
    end_x_m=start_x_m + 1.0,
    mesh=_mesh(start_x_m),
    geometry_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
    physical_closure=MocCellClosureStatus.CLOSED,
    continuation_boundary=boundary,
    continuation_boundary_kind=boundary_kind,
  )


def test_open_seed_does_not_start_moc_chain_continuation() -> None:
  calls: list[int] = []

  def solver(_current: MocChainCell, index: int) -> MocChainCell:
    calls.append(index)
    return _cell(index, 1.0)

  result = continue_moc_cell_chain(
    _cell(1, 0.0, closure=MocCellClosureStatus.PENDING),
    solver,
  )

  assert result.status is MocChainStatus.OPEN_CELL
  assert result.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert result.cell_count == 1
  assert calls == []


def test_resolved_moc_chain_requires_explicit_axial_continuity() -> None:
  def solver(_current: MocChainCell, index: int) -> MocChainCell:
    return _cell(index, 1.0)

  result = continue_moc_cell_chain(_cell(1, 0.0), solver)

  assert result.status is MocChainStatus.INVALID_INPUT
  # The callback's candidate starts at the previous end, so the solver must
  # be given the current boundary rather than a hard-coded coordinate.
  assert result.termination_reason is MocChainTerminationReason.INVALID_INPUT
  assert 'share an axial boundary' in result.message


def test_resolved_moc_chain_continues_until_solver_returns_none() -> None:
  calls: list[int] = []

  def solver(current: MocChainCell, index: int) -> MocChainCell | None:
    calls.append(index)
    if index == 3:
      return None
    return _cell(index, current.end_x_m)

  result = continue_moc_cell_chain(
    _cell(1, 0.0),
    solver,
    MocChainContinuationPolicy(max_cells=4),
  )

  assert result.status is MocChainStatus.SOLVER_TERMINATED
  assert result.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert result.cell_count == 2
  assert result.resolved
  assert calls == [2, 3]
  assert result.as_report()['geometry_fidelity_counts'] == {'resolved-planar-moc': 2}


def test_explicit_physical_termination_is_not_inferred_from_none() -> None:
  result = continue_moc_cell_chain(
    _cell(1, 0.0),
    lambda _current, _index: MocChainTerminationDecision(
      physical_termination=True,
      message='ambient-equilibrium condition satisfied',
      diagnostics={'termination_metric': 2.0e-6},
    ),
  )

  assert result.status is MocChainStatus.PHYSICALLY_TERMINATED
  assert result.termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert result.physical_termination is True
  assert result.cell_count == 1
  assert result.as_report()['diagnostics'] == {'termination_metric': 2.0e-6}


def test_reduced_order_candidate_is_rejected_at_moc_fidelity_boundary() -> None:
  def solver(current: MocChainCell, index: int) -> MocChainCell:
    return _cell(
      index,
      current.end_x_m,
      fidelity=MocChainGeometryFidelity.SCALED_REDUCED_ORDER,
    )

  result = continue_moc_cell_chain(_cell(1, 0.0), solver)

  assert result.status is MocChainStatus.FIDELITY_BOUNDARY
  assert result.termination_reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert result.cell_count == 1
  assert 'shock-train lane' in result.message


def test_stateful_moc_chain_requires_a_downstream_state_boundary() -> None:
  result = continue_moc_cell_chain(
    _cell(1, 0.0),
    lambda _current, _index: None,
    MocChainContinuationPolicy(require_state_carry=True),
  )

  assert result.status is MocChainStatus.STATE_BOUNDARY
  assert result.termination_reason is MocChainTerminationReason.STATE_NOT_CARRIED
  assert 'state carry' in result.message


def test_stateful_moc_chain_preserves_boundary_samples_across_cells() -> None:
  calls: list[tuple[int, int]] = []

  def solver(current: MocChainCell, index: int) -> MocChainCell | None:
    calls.append((index, len(current.continuation_boundary)))
    if index == 3:
      return None
    return _stateful_cell(index, current.end_x_m)

  result = continue_moc_cell_chain(
    _stateful_cell(1, 0.0),
    solver,
    MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert result.status is MocChainStatus.SOLVER_TERMINATED
  assert result.resolved
  assert result.as_report()['state_carry_count'] == 2
  assert result.as_report()['continuation_boundary_maxima_nonincreasing'] is True
  assert result.as_report()['continuation_total_pressure_ranges_Pa'] == [
    {'cell_index': 1, 'minimum_Pa': 1.0e6, 'maximum_Pa': 1.0e6},
    {'cell_index': 2, 'minimum_Pa': 1.0e6, 'maximum_Pa': 1.0e6},
  ]
  assert calls == [(2, 3), (3, 3)]


def test_centerline_trace_is_a_distinct_state_carry_boundary() -> None:
  seed = _stateful_cell(
    1,
    0.0,
    boundary_kind=MocChainBoundaryKind.CENTERLINE_TRACE,
  )

  result = continue_moc_cell_chain(
    seed,
    lambda _current, _index: None,
    MocChainContinuationPolicy(require_state_carry=True),
  )

  assert result.status is MocChainStatus.SOLVER_TERMINATED
  assert result.resolved
  assert result.as_report()['continuation_boundary_kinds'] == ['centerline-trace']


def test_chain_pressure_report_flags_a_carried_pressure_increase() -> None:
  result = continue_moc_cell_chain(
    _stateful_cell(1, 0.0),
    lambda current, index: (
      None
      if index == 3
      else _stateful_cell(index, current.end_x_m, total_pressure_Pa=1.1e6)
    ),
    MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert result.status is MocChainStatus.SOLVER_TERMINATED
  assert result.as_report()['continuation_boundary_maxima_nonincreasing'] is False


def test_axial_section_boundary_rejects_nonplanar_state_samples() -> None:
  boundary = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=0.0 + index * 0.01,
        y_m=0.1 * index,
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.0e6,
    )
    for index in range(3)
  )

  with pytest.raises(ValueError, match='one x plane'):
    MocChainCell(
      cell_index=1,
      start_x_m=0.0,
      end_x_m=1.0,
      mesh=_mesh(0.0),
      geometry_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      physical_closure=MocCellClosureStatus.CLOSED,
      continuation_boundary=boundary,
      continuation_boundary_kind=MocChainBoundaryKind.AXIAL_SECTION,
    )
  ####


def test_characteristic_trace_validator_accepts_a_forward_c_plus_trace() -> None:
  base = CharacteristicState(
    x_m=0.0,
    y_m=0.0,
    theta_rad=0.08,
    mach=2.2,
    gamma=1.4,
  )
  direction = base.direction(CharacteristicFamily.PLUS)
  samples = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=base.x_m + distance * direction[0],
        y_m=base.y_m + distance * direction[1],
        theta_rad=base.theta_rad,
        mach=base.mach,
        gamma=base.gamma,
      ),
      total_pressure_Pa=1.0e6,
    )
    for distance in (0.0, 0.25, 0.5)
  )

  result = validate_characteristic_trace(
    samples,
    CharacteristicFamily.PLUS,
  )

  assert result.status is MocCharacteristicTraceStatus.CONVERGED
  assert result.converged
  assert result.sample_count == 3
  assert result.maximum_absolute_invariant_residual == 0.0
  assert result.maximum_geometry_residual_m is not None
  assert result.maximum_geometry_residual_m < 1.0e-12


def test_characteristic_trace_validator_does_not_hide_a_family_invariant_break() -> None:
  base = CharacteristicState(
    x_m=0.0,
    y_m=0.0,
    theta_rad=0.08,
    mach=2.2,
    gamma=1.4,
  )
  direction = base.direction(CharacteristicFamily.PLUS)
  samples = (
    MocChainBoundarySample(state=base, total_pressure_Pa=1.0e6),
    MocChainBoundarySample(
      state=replace(
        base,
        x_m=0.25 * direction[0],
        y_m=0.25 * direction[1],
        theta_rad=base.theta_rad + 0.01,
      ),
      total_pressure_Pa=1.0e6,
    ),
  )

  result = validate_characteristic_trace(
    samples,
    CharacteristicFamily.PLUS,
  )

  assert result.status is MocCharacteristicTraceStatus.INVARIANT_FAILURE
  assert not result.converged
  assert 'C+ invariant' in result.message
