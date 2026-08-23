"""Regime-aware, low-order shock-cell result contracts."""

from __future__ import annotations

from exhaust_plume.models.shock_cells.contracts import (
    AnalyticalFirstCellSolution,
    ClosedZone,
    FlowTransition,
    ShockCell,
    ShockCellSolveConfig,
    ShockCellSolveResult,
    ShockSegment,
    SolverStatus,
    TerminationReason,
)
from exhaust_plume.models.shock_cells.regime import ExpansionRegime, classify_expansion_regime, dimensionless_pressure_residual
from exhaust_plume.models.shock_cells.solve import solve_first_cell_from_exit_state, solve_shock_cells

__all__ = (
    "ClosedZone",
    "AnalyticalFirstCellSolution",
    "ExpansionRegime",
    "FlowTransition",
    "ShockCell",
    "ShockCellSolveConfig",
    "ShockCellSolveResult",
    "ShockSegment",
    "SolverStatus",
    "TerminationReason",
    "classify_expansion_regime",
    "dimensionless_pressure_residual",
    "solve_shock_cells",
    "solve_first_cell_from_exit_state",
)
