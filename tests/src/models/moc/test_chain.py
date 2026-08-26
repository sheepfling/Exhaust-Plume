from __future__ import annotations

import pytest

from exhaust_plume.models.moc import (
  MocCellClosureStatus,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainGeometryFidelity,
  MocChainStatus,
  MocChainTerminationReason,
  MocCharacteristicCell,
  CharacteristicState,
  continue_moc_cell_chain,
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


def _stateful_cell(index: int, start_x_m: float) -> MocChainCell:
  boundary = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(
        x_m=start_x_m + offset,
        y_m=0.1 * (2 - offset),
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.0e6,
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
  assert calls == [(2, 3), (3, 3)]


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
