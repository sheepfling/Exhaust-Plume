"""Canonical result contracts for the simple straight shock-cell path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from exhaust_plume.geometry.contracts import GeometryStatus
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.contracts.termination import TerminationReason
from exhaust_plume.util.aero.flow_state import FlowState

__all__ = (
    "AnalyticalFirstCellSolution",
    "ClosedZone",
    "FlowTransition",
    "ShockCell",
    "ShockCellSolveConfig",
    "ShockCellSolveResult",
    "ShockSegment",
    "SolverStatus",
    "TerminationReason",
)


class SolverStatus(str, Enum):
  CONVERGED = "converged"
  CONVERGED_AT_BOUNDARY = "converged_at_boundary"
  INVALID_INPUT = "invalid_input"
  OUTSIDE_MODEL_VALIDITY = "outside_model_validity"
  PARTIAL_RESULT = "partial_result"
  NUMERICAL_FAILURE = "numerical_failure"
####


class ShockCellSolveConfig(BaseModel):
  """Explicit inputs and safety limits for the low-order straight path."""

  model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True, allow_inf_nan=False)

  exit_state: NozzleExitState = Field(alias="exit")
  ambient: AmbientState
  expansion_characteristics: int = Field(default=2, ge=2)
  compression_characteristics: int = Field(default=1, ge=1)
  pressure_match_rtol: float = Field(default=1.0e-4, gt=0.0)
  max_cells: int = Field(default=1, ge=0)
  permit_strong_shock_branch: bool = False
  permit_legacy_parabola_fallback: bool = False

  @property
  def exit(self) -> NozzleExitState:
    return self.exit_state
  ####
####


@dataclass(frozen=True)
class FlowTransition:
  """A state transition that may or may not have closed geometry."""

  cell_index: int
  kind: str
  upstream: FlowState
  downstream: FlowState
  geometry_status: GeometryStatus
####


@dataclass(frozen=True)
class ShockSegment:
  start_xr_m: np.ndarray
  end_xr_m: np.ndarray
  branch: str
  shock_angle_rad: float
  turn_angle_rad: float
  upstream: FlowState
  downstream: FlowState

  def __post_init__(self) -> None:
    for name in ("start_xr_m", "end_xr_m"):
      value = np.array(getattr(self, name), dtype=float, copy=True)
      if value.shape != (2,) or not np.isfinite(value).all():
        raise ValueError(f"{name} must be a finite point with shape (2,)")
      ####
      value.flags.writeable = False
      object.__setattr__(self, name, value)
    ####
  ####
####


@dataclass(frozen=True)
class ClosedZone:
  """A finite simple polygon with a state and explicit cell index."""

  zone_id: str
  cell_index: int
  vertices_xr_m: np.ndarray
  flow: FlowState
  geometry_status: GeometryStatus = GeometryStatus.VALID
  composition_mass_fractions: Optional[np.ndarray] = None

  def __post_init__(self) -> None:
    vertices = np.array(self.vertices_xr_m, dtype=float, copy=True)
    if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3 or not np.isfinite(vertices).all():
      raise ValueError("ClosedZone vertices must be a finite array with shape (N, 2), N >= 3")
    ####
    if self.geometry_status is not GeometryStatus.VALID:
      raise ValueError("A successful ClosedZone must have geometry_status=GeometryStatus.VALID")
    ####
    from exhaust_plume.geometry.polygons import validate_polygon
    polygon_status = validate_polygon(vertices)
    if not polygon_status.is_valid:
      raise ValueError(f"ClosedZone polygon is not valid: {polygon_status.status.value}")
    ####
    vertices.flags.writeable = False
    object.__setattr__(self, "vertices_xr_m", vertices)
    if self.composition_mass_fractions is not None:
      composition = np.array(self.composition_mass_fractions, dtype=float, copy=True)
      if composition.ndim != 1 or not np.isfinite(composition).all():
        raise ValueError("composition_mass_fractions must be finite and one-dimensional")
      ####
      composition.flags.writeable = False
      object.__setattr__(self, "composition_mass_fractions", composition)
    ####
  ####
####


@dataclass(frozen=True)
class ShockCell:
  cell_index: int
  zones: tuple[ClosedZone, ...]
####


@dataclass(frozen=True)
class ShockCellSolveResult:
  regime: Any
  cells: tuple[ShockCell, ...]
  status: SolverStatus
  termination_reason: TerminationReason
  exit_state: NozzleExitState
  ambient: AmbientState
  pressure_residual: float
  details: Mapping[str, Any]

  def __post_init__(self) -> None:
    object.__setattr__(self, "details", MappingProxyType(dict(self.details)))
  ####

  @property
  def zones(self) -> tuple[ClosedZone, ...]:
    return tuple(zone for cell in self.cells for zone in cell.zones)
  ####
####


@dataclass(frozen=True, slots=True)
class AnalyticalFirstCellSolution:
  """Named result boundary for the first analytical construction cell.

  ``ShockCellSolveResult`` remains the compatibility-facing low-order result.
  This wrapper gives the new provider lane an explicit semantic boundary while
  keeping the legacy solver result and its fields unchanged.
  """

  result: ShockCellSolveResult

  @property
  def regime(self) -> Any:
    return self.result.regime
  ####

  @property
  def cells(self) -> tuple[ShockCell, ...]:
    return self.result.cells
  ####

  @property
  def zones(self) -> tuple[ClosedZone, ...]:
    return self.result.zones
  ####

  @property
  def status(self) -> SolverStatus:
    return self.result.status
  ####

  @property
  def termination_reason(self) -> TerminationReason:
    return self.result.termination_reason
  ####

  @property
  def exit_state(self) -> NozzleExitState:
    return self.result.exit_state
  ####

  @property
  def ambient(self) -> AmbientState:
    return self.result.ambient
  ####

  @property
  def pressure_residual(self) -> float:
    return self.result.pressure_residual
  ####

  @property
  def details(self) -> Mapping[str, Any]:
    return self.result.details
  ####
####
