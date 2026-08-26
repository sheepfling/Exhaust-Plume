from __future__ import annotations

from exhaust_plume.models.moc import (
  MocCellClosureStatus,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainGeometryFidelity,
  MocChainStatus,
  MocChainTerminationReason,
  MocCharacteristicCell,
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
