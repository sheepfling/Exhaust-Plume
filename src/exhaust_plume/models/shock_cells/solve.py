"""Compatibility-backed solver for the first simple straight construction pass."""

from __future__ import annotations

from typing import Any

from exhaust_plume.geometry import validate_polygon
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.shock_cells.contracts import (
    AnalyticalFirstCellSolution,
    ClosedZone,
    ShockCell,
    ShockCellSolveConfig,
    ShockCellSolveResult,
    SolverStatus,
    TerminationReason,
)
from exhaust_plume.models.shock_cells.regime import ExpansionRegime, classify_expansion_regime, dimensionless_pressure_residual
from exhaust_plume.util.aero.flow_state import FlowState

__all__ = ("solve_first_cell_from_exit_state", "solve_shock_cells")
###########################################


def _flow_from_exit_state(exit_state: NozzleExitState) -> FlowState:
  return FlowState(
      mach=exit_state.mach,
      static_pressure=exit_state.static_pressure_Pa,
      static_temperature=exit_state.static_temperature_K,
      static_density=exit_state.density_kgpm3,
      gamma=exit_state.gas.gamma,
  )
  ####


def _closed_zones(legacy_zones: list[Any], cell_index: int) -> tuple[ClosedZone, ...]:
  out: list[ClosedZone] = []
  for index, zone in enumerate(legacy_zones):
    vertices = zone.coordinates.corners_ru
    validation = validate_polygon(vertices)
    if not validation.is_valid:
      continue
    out.append(ClosedZone(
        zone_id=f"cell-{cell_index}-zone-{index + 1}",
        cell_index=cell_index,
        vertices_xr_m=vertices,
        flow=zone.asFlowState(),
    ))
  return tuple(out)
  ####


def solve_shock_cells(config: ShockCellSolveConfig) -> ShockCellSolveResult:
  """Solve at most the requested low-order straight construction cells.

  This foundation result deliberately stops at the requested construction
  ceiling.  It does not infer a physical cell count or add mixing, chemistry,
  radiation, or accelerated backends.
  """

  exit_state = config.exit_state
  ambient = config.ambient
  pressure_residual = dimensionless_pressure_residual(exit_state.static_pressure_Pa, ambient.pressure_Pa)
  regime = classify_expansion_regime(exit_state, ambient, pressure_match_rtol=config.pressure_match_rtol)
  base_details: dict[str, Any] = {
      "solver_diagnostics_v1": {
          "status": SolverStatus.CONVERGED.value,
          "pressure_residual": pressure_residual,
          "requested_max_cells": config.max_cells,
      },
      "regime": regime.value,
  }
  if regime is ExpansionRegime.MATCHED:
    base_details["termination"] = TerminationReason.NO_PRESSURE_MISMATCH.value
    return ShockCellSolveResult(regime, (), SolverStatus.CONVERGED, TerminationReason.NO_PRESSURE_MISMATCH, exit_state, ambient, pressure_residual, base_details)
  if config.max_cells == 0:
    base_details["termination"] = TerminationReason.MAX_CELL_LIMIT.value
    return ShockCellSolveResult(regime, (), SolverStatus.CONVERGED_AT_BOUNDARY, TerminationReason.MAX_CELL_LIMIT, exit_state, ambient, pressure_residual, base_details)

  from exhaust_plume.models.plume.plume_solve import calculatePlumeZonesFromExitState
  try:
    legacy_zones, legacy_details = calculatePlumeZonesFromExitState(
        exit_state=exit_state,
        atmospheric_pressure=ambient.pressure_Pa,
        num_expansion_lines=config.expansion_characteristics,
        num_compression_lines=config.compression_characteristics,
        num_plumes=1,
    )
  except (ValueError, ArithmeticError, FloatingPointError) as exc:
    base_details["solver_diagnostics_v1"] = {
        **base_details["solver_diagnostics_v1"],
        "status": SolverStatus.NUMERICAL_FAILURE.value,
        "message": str(exc),
    }
    return ShockCellSolveResult(regime, (), SolverStatus.NUMERICAL_FAILURE, TerminationReason.NUMERICAL_FAILURE, exit_state, ambient, pressure_residual, base_details)
  zones = _closed_zones(legacy_zones, cell_index=1)
  base_details.update(legacy_details)
  base_details["termination"] = TerminationReason.MAX_CELL_LIMIT.value
  if not zones:
    base_details["solver_diagnostics_v1"] = {
        **base_details["solver_diagnostics_v1"],
        "status": SolverStatus.OUTSIDE_MODEL_VALIDITY.value,
        "message": "No finite simple closed zones were produced",
    }
    return ShockCellSolveResult(regime, (), SolverStatus.OUTSIDE_MODEL_VALIDITY, TerminationReason.NUMERICAL_FAILURE, exit_state, ambient, pressure_residual, base_details)
  cell = ShockCell(cell_index=1, zones=zones)
  base_details["solver_diagnostics_v1"] = {
      **base_details["solver_diagnostics_v1"],
      "status": SolverStatus.CONVERGED_AT_BOUNDARY.value,
      "closed_zone_count": len(zones),
  }
  return ShockCellSolveResult(regime, (cell,), SolverStatus.CONVERGED_AT_BOUNDARY, TerminationReason.MAX_CELL_LIMIT, exit_state, ambient, pressure_residual, base_details)
  ####


def solve_first_cell_from_exit_state(
    exit_state: NozzleExitState,
    ambient_state: AmbientState,
    settings: ShockCellSolveConfig | None = None,
) -> AnalyticalFirstCellSolution:
  """Solve the bounded first-cell problem from explicit static states.

  The new provider boundary is intentionally state-based.  Existing total
  condition and legacy APIs continue to derive ``NozzleExitState`` first and
  can then call this function without changing their public signatures.
  ``settings`` carries only numerical and construction limits; when supplied,
  its exit and ambient states must match the explicit function arguments.
  """

  if settings is None:
    settings = ShockCellSolveConfig(exit=exit_state, ambient=ambient_state)
  elif settings.exit_state != exit_state or settings.ambient != ambient_state:
    raise ValueError('first-cell settings must use the supplied exit and ambient states')
  return AnalyticalFirstCellSolution(result=solve_shock_cells(settings))
  ####
