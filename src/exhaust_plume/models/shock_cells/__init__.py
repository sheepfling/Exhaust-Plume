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
from exhaust_plume.models.shock_cells.fully_expanded import (
  FullyExpandedJetResult,
  FullyExpandedStatus,
  derive_fully_expanded_jet,
)
from exhaust_plume.models.shock_cells.correlations import (
  FirstCellComparisonResult,
  FirstCellCorrelationResult,
  FirstCellCorrelationStatus,
  compare_first_cell_length,
  prandtl_pack_first_cell_spacing,
)

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
  "FullyExpandedJetResult",
  "FullyExpandedStatus",
  "derive_fully_expanded_jet",
  "FirstCellComparisonResult",
  "FirstCellCorrelationResult",
  "FirstCellCorrelationStatus",
  "compare_first_cell_length",
  "prandtl_pack_first_cell_spacing",
)
