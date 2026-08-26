from __future__ import annotations

import pytest

from exhaust_plume.models.moc import MocCharacteristicCell
from exhaust_plume.validation.moc_measurements import (
  MocShockCellMeasurementStatus,
  MocShockCellObservation,
  measure_moc_shock_cell,
  measure_moc_shock_cell_chain,
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


def test_moc_chain_measurement_rejects_reordered_indices() -> None:
  result = measure_moc_shock_cell_chain(
    (
      _observation(cell_index=2),
      _observation(cell_index=1, shock_start_x_m=4.0),
    )
  )

  assert result.status is MocShockCellMeasurementStatus.CHAIN_FAILURE
  assert 'contiguous' in result.message
