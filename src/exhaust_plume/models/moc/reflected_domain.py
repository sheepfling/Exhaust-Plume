"""Explicit reflected-domain remeshing for continued planar-MOC cells.

The outgoing front of a terminal reflection patch is a single ``C-``
characteristic.  Reusing that line as an entire new source boundary makes a
triangular source mesh degenerate, so a continued reflected domain needs two
different pieces of data:

* the exact prior ``C-`` front, used as the reflection/alternating-family
  anchor; and
* a newly solved centerline ``C+`` source row and outer source curve.

This module validates that seam and assembles the bounded source field from
the explicit Cauchy data.  It does not invent the free boundary, infer entropy
losses, fit a shock, or promote an open field to a physical chain cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, tan
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
  from exhaust_plume.models.moc.coupled import MocAmbientPhysicalFieldResult
  from exhaust_plume.models.moc.physical_cell import MocPhysicalPostShockFieldResult

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientPressureBoundaryResult,
  validate_ambient_pressure_boundary,
)
from exhaust_plume.models.moc.boundary import (
  MocFreeBoundaryPointResult,
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainCell,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCharacteristicTraceResult,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  centerline_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  MocSourceStripContinuationResult,
  MocSourceStripContinuationStatus,
  assemble_source_characteristic_strip,
  assemble_source_characteristic_strip_with_source_pressures,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocReflectedTracePolarity,
  MocReflectedTracePolarityResult,
  MocReflectedTraceCompressionProfile,
  MocTerminalReflectionPatchResult,
  build_reflected_trace_compression_profile,
  classify_reflected_trace_polarity,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
  assemble_euler_ambient_physical_field,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  fit_euler_consistent_shock_boundary_from_geometry,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocReflectedDomainOuterSourceStatus',
  'MocReflectedDomainOuterSourceResult',
  'MocReflectedDomainAlternatingSourceStatus',
  'MocReflectedDomainAlternatingSourceResult',
  'MocReflectedDomainAlternatingPhysicalFieldStatus',
  'MocReflectedDomainAlternatingPhysicalFieldResult',
  'MocReflectedDomainSolverOwnedFirstCellStatus',
  'MocReflectedDomainSolverOwnedFirstCellTrial',
  'MocReflectedDomainSolverOwnedFirstCellResult',
  'MocReflectedDomainGlobalShockRemeshStatus',
  'MocReflectedDomainGlobalShockRemeshAttempt',
  'MocReflectedDomainGlobalShockRemeshResult',
  'MocReflectedDomainGlobalEulerShockBoundaryStatus',
  'MocReflectedDomainGlobalEulerShockBoundaryResult',
  'MocReflectedDomainRemeshStatus',
  'MocReflectedDomainRemeshRequest',
  'MocReflectedDomainRemeshResult',
  'build_reflected_domain_remesh_request_from_outer_source',
  'solve_reflected_domain_alternating_source',
  'solve_reflected_domain_alternating_physical_field',
  'solve_reflected_domain_solver_owned_first_cell',
  'solve_reflected_domain_global_shock_remesh',
  'solve_reflected_domain_global_euler_shock_boundary',
  'solve_reflected_domain_outer_source_curve',
  'solve_reflected_domain_remesh',
)


class MocReflectedDomainRemeshStatus(str, Enum):
  """Outcome of an explicit reflected-domain source remesh."""

  CONVERGED_BOUNDED_FIELD = 'converged_bounded_reflected_domain_field'
  INVALID_INPUT = 'invalid_input'
  INCOMING_TRACE_FAILURE = 'reflected_domain_incoming_trace_failure'
  REFLECTION_SEAM_FAILURE = 'reflected_domain_reflection_seam_failure'
  CENTERLINE_SOURCE_FAILURE = 'reflected_domain_centerline_source_failure'
  OUTER_SOURCE_FAILURE = 'reflected_domain_outer_source_failure'
  POLARITY_FAILURE = 'reflected_domain_polarity_failure'
  FIELD_FAILURE = 'reflected_domain_field_failure'


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  """Compare a state at a seam without replacing caller-owned data."""

  return (
    abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad)
    <= state_tolerance * max(1.0, abs(actual.theta_rad), abs(expected.theta_rad))
    and abs(actual.mach - expected.mach)
    <= state_tolerance * max(1.0, abs(actual.mach), abs(expected.mach))
    and abs(actual.gamma - expected.gamma)
    <= state_tolerance * max(1.0, abs(actual.gamma), abs(expected.gamma))
  )


def _pressure_matches(actual: float, expected: float, tolerance: float) -> bool:
  return abs(float(actual) - float(expected)) <= tolerance * max(
    1.0,
    abs(float(actual)),
    abs(float(expected)),
  )


class MocReflectedDomainOuterSourceStatus(str, Enum):
  """Outcome of a bounded ambient-pressure outer-source march."""

  CONVERGED = 'converged_ambient_outer_source_curve'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'outer_source_seed_failure'
  BOUNDARY_FAILURE = 'outer_source_boundary_failure'
  FIELD_FAILURE = 'outer_source_characteristic_field_failure'
####


class MocReflectedDomainAlternatingSourceStatus(str, Enum):
  """Outcome of a bounded alternating-family reflected remesh."""

  CONVERGED = 'converged_alternating_family_source_band'
  INVALID_INPUT = 'invalid_input'
  INCOMING_TRACE_FAILURE = 'alternating_source_incoming_trace_failure'
  SEED_FAILURE = 'alternating_source_seed_failure'
  ANCHOR_FAILURE = 'alternating_source_reflection_anchor_failure'
  CENTERLINE_FAILURE = 'alternating_source_centerline_failure'
  BOUNDARY_FAILURE = 'alternating_source_ambient_boundary_failure'
  FIELD_FAILURE = 'alternating_source_field_failure'


class MocReflectedDomainAlternatingPhysicalFieldStatus(str, Enum):
  """Outcome of coupling an alternating source band to a shock field."""

  CONVERGED_AMBIENT_CLOSED = (
    'converged_alternating_source_ambient_closed_physical_field'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FIELD_FAILURE = 'alternating_physical_source_field_failure'
  SHOCK_FAILURE = 'alternating_physical_shock_failure'
  FIELD_FAILURE = 'alternating_physical_field_failure'


class MocReflectedDomainSolverOwnedFirstCellStatus(str, Enum):
  """Outcome of the source-owned first-cell endpoint iteration."""

  CONVERGED_CENTERLINE_ENDPOINT = (
    'converged_solver_owned_centerline_endpoint'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FIELD_FAILURE = 'solver_owned_first_cell_source_failure'
  FIELD_FAILURE = 'solver_owned_first_cell_field_failure'
  BOUNDARY_BRACKET_FAILURE = 'solver_owned_first_cell_boundary_bracket_failure'
  SHOOTING_FAILURE = 'solver_owned_first_cell_shooting_failure'
  ITERATION_LIMIT = 'solver_owned_first_cell_iteration_limit'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainOuterSourceResult:
  """A solver-generated outer ``C-`` source curve for a reflected remesh.

  The first outer state is an explicit prior-boundary seed.  Each later state
  is generated by marching the corresponding centerline ``C+`` state to an
  ambient-pressure, streamline-tangent endpoint.  The source rows are then
  checked by the same characteristic-strip assembler used by a reflected
  remesh.

  This closes only the outer-source boundary condition.  The centerline row,
  source pressure lineage, shock entropy loss, downstream perimeter, and
  chain-cell promotion remain separate gates.
  """

  status: MocReflectedDomainOuterSourceStatus
  centerline_source_states: tuple[CharacteristicState, ...]
  outer_source_states: tuple[CharacteristicState, ...]
  reference_total_pressure_Pa: float | None
  centerline_total_pressure_Pa: tuple[float, ...]
  outer_total_pressure_Pa: tuple[float, ...]
  previous_boundary_state: CharacteristicState | None
  previous_boundary_total_pressure_Pa: float | None
  ambient_pressure_Pa: float | None
  point_results: tuple[MocFreeBoundaryPointResult, ...] = ()
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None
  source_strip: MocSourceCharacteristicStripResult | None = None
  message: str = ''
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  position_tolerance_m: float = 1.0e-3
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainOuterSourceStatus):
      raise TypeError(
        'status must be a MocReflectedDomainOuterSourceStatus'
      )
    centerline = tuple(self.centerline_source_states)
    outer = tuple(self.outer_source_states)
    point_results = tuple(self.point_results)
    centerline_pressures = tuple(
      float(value) for value in self.centerline_total_pressure_Pa
    )
    outer_pressures = tuple(
      float(value) for value in self.outer_total_pressure_Pa
    )
    if any(
      not isinstance(state, CharacteristicState)
      for state in (*centerline, *outer)
    ):
      raise TypeError(
        'outer-source result rows must contain CharacteristicState values'
      )
    if len(centerline_pressures) not in (0, len(centerline)):
      raise ValueError(
        'centerline_total_pressure_Pa must match the centerline source row'
      )
    if len(outer_pressures) not in (0, len(outer)):
      raise ValueError(
        'outer_total_pressure_Pa must match the outer source row'
      )
    if any(
      not isfinite(value) or value <= 0.0
      for value in (*centerline_pressures, *outer_pressures)
    ):
      raise ValueError(
        'outer-source pressure rows must contain finite positive values'
      )
    if self.reference_total_pressure_Pa is not None:
      reference = float(self.reference_total_pressure_Pa)
      if not isfinite(reference) or reference <= 0.0:
        raise ValueError(
          'reference_total_pressure_Pa must be finite and positive when supplied'
        )
      object.__setattr__(self, 'reference_total_pressure_Pa', reference)
    if self.previous_boundary_state is not None and not isinstance(
      self.previous_boundary_state,
      CharacteristicState,
    ):
      raise TypeError(
        'previous_boundary_state must be a CharacteristicState or None'
      )
    for name in (
      'previous_boundary_total_pressure_Pa',
      'ambient_pressure_Pa',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      normalized = float(value)
      if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      object.__setattr__(self, name, normalized)
    if any(
      not isinstance(result, MocFreeBoundaryPointResult)
      for result in point_results
    ):
      raise TypeError(
        'point_results must contain MocFreeBoundaryPointResult values'
      )
    if self.ambient_boundary is not None and not isinstance(
      self.ambient_boundary,
      MocAmbientPressureBoundaryResult,
    ):
      raise TypeError(
        'ambient_boundary must be a MocAmbientPressureBoundaryResult or None'
      )
    if self.source_strip is not None and not isinstance(
      self.source_strip,
      MocSourceCharacteristicStripResult,
    ):
      raise TypeError(
        'source_strip must be a MocSourceCharacteristicStripResult or None'
      )
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or (
        value <= 0.0
        and name in (
          'position_tolerance_m',
          'invariant_tolerance',
          'pressure_tolerance',
        )
      ):
        raise ValueError(f'{name} must be finite and valid')
      object.__setattr__(self, name, value)
    object.__setattr__(self, 'centerline_source_states', centerline)
    object.__setattr__(self, 'outer_source_states', outer)
    object.__setattr__(self, 'centerline_total_pressure_Pa', centerline_pressures)
    object.__setattr__(self, 'outer_total_pressure_Pa', outer_pressures)
    object.__setattr__(self, 'point_results', point_results)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainOuterSourceStatus.CONVERGED
  ####

  @property
  def outer_source_curve_verified(self) -> bool:
    return bool(
      self.converged
      and len(self.outer_source_states) == len(self.centerline_source_states)
      and self.ambient_boundary is not None
      and self.ambient_boundary.converged
    )
  ####

  @property
  def source_field_verified(self) -> bool:
    return bool(
      self.outer_source_curve_verified
      and self.source_strip is not None
      and self.source_strip.converged
      and self.source_strip.topology.forms_closed_zone
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The generated source curve is not a closed shock-cell solution."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    pressure_range = None
    all_pressures = (
      *self.centerline_total_pressure_Pa,
      *self.outer_total_pressure_Pa,
    )
    if all_pressures:
      pressure_range = (min(all_pressures), max(all_pressures))
    return {
      'status': self.status.value,
      'converged': self.converged,
      'outer_source_curve_verified': self.outer_source_curve_verified,
      'source_field_verified': self.source_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'source_model': 'solver-owned-ambient-pressure-outer-source-march',
      'centerline_source_count': len(self.centerline_source_states),
      'outer_source_count': len(self.outer_source_states),
      'attempted_boundary_point_count': len(self.point_results),
      'reference_total_pressure_Pa': self.reference_total_pressure_Pa,
      'centerline_total_pressure_Pa': list(self.centerline_total_pressure_Pa),
      'outer_total_pressure_Pa': list(self.outer_total_pressure_Pa),
      'total_pressure_range_Pa': pressure_range,
      'previous_boundary_total_pressure_Pa': (
        self.previous_boundary_total_pressure_Pa
      ),
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'point_statuses': [result.status.value for result in self.point_results],
      'ambient_boundary': (
        None
        if self.ambient_boundary is None
        else self.ambient_boundary.as_report()
      ),
      'source_strip': (
        None if self.source_strip is None else self.source_strip.as_report()
      ),
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingSourceResult:
  """A bounded source band generated by alternating ``C-``/``C+`` marches.

  The prior terminal reflection front supplies one exact ``C-`` seed.  The
  solver reflects that seed to the centerline, marches a ``C+`` characteristic
  to an ambient-pressure/tangent outer point, and repeats.  The resulting
  local two-triangle cells are intentionally distinct from the older
  triangular source-strip contract: older source rows require every
  cross-pairing to remain forward, while this alternating band only claims
  the two neighboring characteristic seams that it actually solved.

  This is a bounded research field.  It carries no shock entropy production,
  mixed-regime downstream perimeter, or physical chain-cell promotion.
  """

  status: MocReflectedDomainAlternatingSourceStatus
  reflection_patch: MocTerminalReflectionPatchResult | None
  centerline_source_states: tuple[CharacteristicState, ...]
  outer_source_states: tuple[CharacteristicState, ...]
  centerline_total_pressure_Pa: tuple[float, ...]
  outer_total_pressure_Pa: tuple[float, ...]
  outer_seed_state: CharacteristicState | None
  outer_seed_total_pressure_Pa: float | None
  ambient_pressure_Pa: float | None
  incoming_trace_validation: MocCharacteristicTraceResult | None
  incoming_trace_polarity: MocReflectedTracePolarityResult | None
  centerline_results: tuple[CharacteristicPointResult, ...] = ()
  point_results: tuple[MocFreeBoundaryPointResult, ...] = ()
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None
  cells: tuple[MocCharacteristicCell, ...] = ()
  topology: MocTopologyResult | None = None
  reflection_anchor_verified: bool = False
  alternating_seam_verified: bool = False
  message: str = ''
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  position_tolerance_m: float = 1.0e-3
  trace_forward_tolerance_m: float = 1.0e-4
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-8
  incoming_handoff: tuple[MocChainBoundarySample, ...] = ()

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainAlternatingSourceStatus):
      raise TypeError(
        'status must be a MocReflectedDomainAlternatingSourceStatus'
      )
    if self.reflection_patch is not None and not isinstance(
      self.reflection_patch,
      MocTerminalReflectionPatchResult,
    ):
      raise TypeError(
        'reflection_patch must be a MocTerminalReflectionPatchResult or None'
      )
    centerline = tuple(self.centerline_source_states)
    outer = tuple(self.outer_source_states)
    centerline_pressures = tuple(
      float(value) for value in self.centerline_total_pressure_Pa
    )
    outer_pressures = tuple(
      float(value) for value in self.outer_total_pressure_Pa
    )
    centerline_results = tuple(self.centerline_results)
    point_results = tuple(self.point_results)
    cells = tuple(self.cells)
    if any(
      not isinstance(state, CharacteristicState)
      for state in (*centerline, *outer)
    ):
      raise TypeError(
        'alternating source rows must contain CharacteristicState values'
      )
    if len(centerline_pressures) not in (0, len(centerline)):
      raise ValueError(
        'centerline_total_pressure_Pa must match the centerline source row'
      )
    if len(outer_pressures) not in (0, len(outer)):
      raise ValueError(
        'outer_total_pressure_Pa must match the outer source row'
      )
    if any(
      not isfinite(value) or value <= 0.0
      for value in (*centerline_pressures, *outer_pressures)
    ):
      raise ValueError(
        'alternating source pressure rows must contain finite positive values'
      )
    for name in ('outer_seed_total_pressure_Pa', 'ambient_pressure_Pa'):
      value = getattr(self, name)
      if value is None:
        continue
      normalized = float(value)
      if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      object.__setattr__(self, name, normalized)
    if self.outer_seed_state is not None and not isinstance(
      self.outer_seed_state,
      CharacteristicState,
    ):
      raise TypeError(
        'outer_seed_state must be a CharacteristicState or None'
      )
    if self.incoming_trace_validation is not None and not isinstance(
      self.incoming_trace_validation,
      MocCharacteristicTraceResult,
    ):
      raise TypeError(
        'incoming_trace_validation must be a MocCharacteristicTraceResult or None'
      )
    if self.incoming_trace_polarity is not None and not isinstance(
      self.incoming_trace_polarity,
      MocReflectedTracePolarityResult,
    ):
      raise TypeError(
        'incoming_trace_polarity must be a MocReflectedTracePolarityResult or None'
      )
    if any(
      not isinstance(result, CharacteristicPointResult)
      for result in centerline_results
    ):
      raise TypeError(
        'centerline_results must contain CharacteristicPointResult values'
      )
    if any(
      not isinstance(result, MocFreeBoundaryPointResult)
      for result in point_results
    ):
      raise TypeError(
        'point_results must contain MocFreeBoundaryPointResult values'
      )
    if self.ambient_boundary is not None and not isinstance(
      self.ambient_boundary,
      MocAmbientPressureBoundaryResult,
    ):
      raise TypeError(
        'ambient_boundary must be a MocAmbientPressureBoundaryResult or None'
      )
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError(
        'cells must contain MocCharacteristicCell values'
      )
    if self.topology is not None and not isinstance(
      self.topology,
      MocTopologyResult,
    ):
      raise TypeError('topology must be a MocTopologyResult or None')
    for name in (
      'reflection_anchor_verified',
      'alternating_seam_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'position_tolerance_m',
      'trace_forward_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or (
        value <= 0.0
        and name in (
          'position_tolerance_m',
          'trace_forward_tolerance_m',
          'invariant_tolerance',
          'pressure_tolerance',
        )
      ):
        raise ValueError(f'{name} must be finite and valid')
      object.__setattr__(self, name, value)
    incoming_handoff = tuple(self.incoming_handoff)
    if any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in incoming_handoff
    ):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', incoming_handoff)
    object.__setattr__(self, 'centerline_source_states', centerline)
    object.__setattr__(self, 'outer_source_states', outer)
    object.__setattr__(self, 'centerline_total_pressure_Pa', centerline_pressures)
    object.__setattr__(self, 'outer_total_pressure_Pa', outer_pressures)
    object.__setattr__(self, 'centerline_results', centerline_results)
    object.__setattr__(self, 'point_results', point_results)
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainAlternatingSourceStatus.CONVERGED
  ####

  @property
  def node_count(self) -> int:
    return len(self.centerline_source_states) + len(self.outer_source_states)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def source_field_verified(self) -> bool:
    return bool(
      self.converged
      and self.reflection_anchor_verified
      and self.alternating_seam_verified
      and len(self.centerline_source_states) >= 3
      and len(self.centerline_source_states) == len(self.outer_source_states)
      and len(self.centerline_results) == len(self.centerline_source_states)
      and len(self.point_results) == len(self.centerline_source_states)
      and all(result.converged for result in self.centerline_results)
      and all(result.converged for result in self.point_results)
      and self.ambient_boundary is not None
      and self.ambient_boundary.converged
      and self.topology is not None
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
    )
  ####

  @property
  def state_sampling_available(self) -> bool:
    return self.source_field_verified
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The alternating source band has no shock or downstream closure."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def _endpoint_sample(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> tuple[CharacteristicState, float] | None:
    for state, pressure in (
      *zip(
        self.centerline_source_states,
        self.centerline_total_pressure_Pa,
        strict=True,
      ),
      *zip(
        self.outer_source_states,
        self.outer_total_pressure_Pa,
        strict=True,
      ),
    ):
      if (
        abs(state.x_m - point_m[0]) <= position_tolerance_m
        and abs(state.y_m - point_m[1]) <= position_tolerance_m
      ):
        return state, pressure
    return None
  ####

  def _sample_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> tuple[CharacteristicState, float] | None:
    if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
      raise ValueError('point_m must contain two finite coordinates')
    if (
      not isfinite(float(position_tolerance_m))
      or position_tolerance_m <= 0.0
    ):
      raise ValueError('position_tolerance_m must be finite and positive')
    point = (float(point_m[0]), float(point_m[1]))
    endpoint = self._endpoint_sample(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    if endpoint is not None:
      state, pressure = endpoint
      return (
        CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=state.theta_rad,
          mach=state.mach,
          gamma=state.gamma,
        ),
        pressure,
      )
    for cell in self.cells:
      vertices = cell.vertices_xr_m
      if len(vertices) != 3:
        continue
      first, second, third = vertices
      denominator = (
        (second[1] - third[1]) * (first[0] - third[0])
        + (third[0] - second[0]) * (first[1] - third[1])
      )
      if abs(denominator) <= max(position_tolerance_m**2, 1.0e-24):
        continue
      weight_first = (
        (second[1] - third[1]) * (point[0] - third[0])
        + (third[0] - second[0]) * (point[1] - third[1])
      ) / denominator
      weight_second = (
        (third[1] - first[1]) * (point[0] - third[0])
        + (first[0] - third[0]) * (point[1] - third[1])
      ) / denominator
      weight_third = 1.0 - weight_first - weight_second
      weights = (weight_first, weight_second, weight_third)
      if min(weights) < -position_tolerance_m or max(weights) > 1.0 + position_tolerance_m:
        continue
      samples = tuple(
        self._endpoint_sample(
          (vertex[0], vertex[1]),
          position_tolerance_m=position_tolerance_m,
        )
        for vertex in vertices
      )
      if any(sample is None for sample in samples):
        continue
      resolved = tuple(sample for sample in samples if sample is not None)
      gamma = resolved[0][0].gamma
      theta = sum(
        weight * sample[0].theta_rad
        for weight, sample in zip(weights, resolved, strict=True)
      )
      nu = sum(
        weight * sample[0].nu_rad
        for weight, sample in zip(weights, resolved, strict=True)
      )
      mach_result = inverse_prandtl_meyer_angle_rad(nu, gamma)
      if not mach_result.converged or mach_result.value is None:
        return None
      return (
        CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=theta,
          mach=mach_result.value,
          gamma=gamma,
        ),
        sum(
          weight * sample[1]
          for weight, sample in zip(weights, resolved, strict=True)
        ),
      )
    if self.reflection_patch is not None:
      patch_state = self.reflection_patch.state_at(
        point,
        position_tolerance_m=position_tolerance_m,
      )
      patch_pressure = self.reflection_patch.total_pressure_at(
        point,
        position_tolerance_m=position_tolerance_m,
      )
      if patch_state is not None and patch_pressure is not None:
        return patch_state, patch_pressure
    return None
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Sample the retained patch or alternating band without extrapolation."""

    sample = self._sample_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    return None if sample is None else sample[0]
  ####

  def total_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Sample carried pressure from the retained patch or source band."""

    sample = self._sample_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    return None if sample is None else sample[1]
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Sample isentropic static pressure without leaving retained domains."""

    sample = self._sample_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sample is None:
      return None
    state, total_pressure = sample
    return _static_pressure_from_total_pressure(state, total_pressure)
  ####

  def as_report(self) -> dict[str, object]:
    pressures = (
      *self.centerline_total_pressure_Pa,
      *self.outer_total_pressure_Pa,
    )
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_model': 'solver-owned-alternating-family-ambient-pressure-remesh',
      'reflection_anchor_verified': self.reflection_anchor_verified,
      'alternating_seam_verified': self.alternating_seam_verified,
      'source_field_verified': self.source_field_verified,
      'state_sampling_available': self.state_sampling_available,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'canonical_alternating_remesh_solved': False,
      'reflection_patch_status': (
        None
        if self.reflection_patch is None
        else self.reflection_patch.status.value
      ),
      'incoming_trace_validation': (
        None
        if self.incoming_trace_validation is None
        else self.incoming_trace_validation.as_report()
      ),
      'incoming_trace_polarity': (
        None
        if self.incoming_trace_polarity is None
        else self.incoming_trace_polarity.as_report()
      ),
      'centerline_source_count': len(self.centerline_source_states),
      'outer_source_count': len(self.outer_source_states),
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'centerline_results': [
        result.status.value for result in self.centerline_results
      ],
      'boundary_results': [result.status.value for result in self.point_results],
      'centerline_total_pressure_Pa': list(self.centerline_total_pressure_Pa),
      'outer_total_pressure_Pa': list(self.outer_total_pressure_Pa),
      'total_pressure_range_Pa': (
        None if not pressures else [min(pressures), max(pressures)]
      ),
      'outer_seed_state': (
        None
        if self.outer_seed_state is None
        else {
          'point_m': [self.outer_seed_state.x_m, self.outer_seed_state.y_m],
          'theta_rad': self.outer_seed_state.theta_rad,
          'mach': self.outer_seed_state.mach,
          'gamma': self.outer_seed_state.gamma,
        }
      ),
      'outer_seed_total_pressure_Pa': self.outer_seed_total_pressure_Pa,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'ambient_boundary': (
        None
        if self.ambient_boundary is None
        else self.ambient_boundary.as_report()
      ),
      'topology': (
        None
        if self.topology is None
        else {
          'status': self.topology.status.value,
          'connected': self.topology.connected,
          'forms_closed_zone': self.topology.forms_closed_zone,
          'boundary_edge_count': self.topology.boundary_edge_count,
          'boundary_component_count': self.topology.boundary_component_count,
          'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
        }
      ),
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'position_tolerance_m': self.position_tolerance_m,
      'trace_forward_tolerance_m': self.trace_forward_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'incoming_handoff_points_m': [
        [sample.state.x_m, sample.state.y_m]
        for sample in self.incoming_handoff
      ],
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingPhysicalFieldResult:
  """A bounded alternating source band coupled to one physical shock field.

  The source band supplies the non-extrapolating upstream state and pressure
  callbacks.  The downstream shock turn is a solver-owned, local positive
  compression envelope that is zero at the ambient attachment and at the
  symmetry endpoint.  This creates a useful physical-field research seam
  without claiming that the envelope is the canonical reflected-plume
  free-boundary law.
  """

  status: MocReflectedDomainAlternatingPhysicalFieldStatus
  source_band: MocReflectedDomainAlternatingSourceResult | None
  field_result: MocAmbientPhysicalFieldResult | None
  start_point_m: tuple[float, float] | None
  outer_source_index: int | None
  compression_amplitude_rad: float | None
  sample_count: int
  outer_flow_angle_bracket: tuple[float, float] | None
  incoming_handoff: tuple[MocChainBoundarySample, ...] = ()
  continuation_law: str = (
    'alternating-source-local-compression-envelope'
  )
  attachment_source: str = 'alternating-outer-source-row'
  use_trace_referenced_profile: bool = False
  compression_envelope_skew: float = 0.0
  position_tolerance_m: float = 1.0e-9
  shock_angle_tolerance_rad: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainAlternatingPhysicalFieldStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainAlternatingPhysicalFieldStatus'
      )
    if self.source_band is not None and not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult or None'
      )
    if self.field_result is not None:
      from exhaust_plume.models.moc.coupled import MocAmbientPhysicalFieldResult

      if not isinstance(self.field_result, MocAmbientPhysicalFieldResult):
        raise TypeError(
          'field_result must be a MocAmbientPhysicalFieldResult or None'
        )
    if self.start_point_m is not None:
      if len(self.start_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.start_point_m
      ):
        raise ValueError('start_point_m must contain two finite coordinates')
      object.__setattr__(
        self,
        'start_point_m',
        (float(self.start_point_m[0]), float(self.start_point_m[1])),
      )
    if self.outer_source_index is not None:
      if (
        isinstance(self.outer_source_index, bool)
        or not isinstance(self.outer_source_index, int)
        or self.outer_source_index < 0
      ):
        raise ValueError(
          'outer_source_index must be a nonnegative integer or None'
        )
    if self.compression_amplitude_rad is not None:
      amplitude = float(self.compression_amplitude_rad)
      if not isfinite(amplitude) or amplitude <= 0.0:
        raise ValueError(
          'compression_amplitude_rad must be finite and positive when supplied'
        )
      object.__setattr__(self, 'compression_amplitude_rad', amplitude)
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 0
    ):
      raise ValueError('sample_count must be a nonnegative integer')
    if self.outer_flow_angle_bracket is not None:
      if len(self.outer_flow_angle_bracket) != 2 or not all(
        isfinite(float(value)) for value in self.outer_flow_angle_bracket
      ):
        raise ValueError(
          'outer_flow_angle_bracket must contain two finite values'
        )
      object.__setattr__(
        self,
        'outer_flow_angle_bracket',
        (
          float(self.outer_flow_angle_bracket[0]),
          float(self.outer_flow_angle_bracket[1]),
        ),
      )
    incoming_handoff = tuple(self.incoming_handoff)
    if any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in incoming_handoff
    ):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', incoming_handoff)
    if not isinstance(self.continuation_law, str) or not self.continuation_law:
      raise ValueError('continuation_law must be a non-empty string')
    if not isinstance(self.attachment_source, str) or not self.attachment_source:
      raise ValueError('attachment_source must be a non-empty string')
    if not isinstance(self.use_trace_referenced_profile, bool):
      raise TypeError('use_trace_referenced_profile must be a bool')
    envelope_skew = float(self.compression_envelope_skew)
    if not isfinite(envelope_skew) or abs(envelope_skew) > 1.0:
      raise ValueError(
        'compression_envelope_skew must be finite and within [-1, 1]'
      )
    object.__setattr__(self, 'compression_envelope_skew', envelope_skew)
    position_tolerance = float(self.position_tolerance_m)
    if not isfinite(position_tolerance) or position_tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    object.__setattr__(self, 'position_tolerance_m', position_tolerance)
    shock_angle_tolerance = float(self.shock_angle_tolerance_rad)
    if not isfinite(shock_angle_tolerance) or shock_angle_tolerance <= 0.0:
      raise ValueError(
        'shock_angle_tolerance_rad must be finite and positive'
      )
    object.__setattr__(self, 'shock_angle_tolerance_rad', shock_angle_tolerance)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_field_verified(self) -> bool:
    return bool(
      self.source_band is not None
      and self.source_band.source_field_verified
    )
  ####

  @property
  def shock_curve_verified(self) -> bool:
    if self.field_result is None or not self.field_result.converged:
      return False
    attachment = self.field_result.ambient_attachment
    shock = None if attachment is None else attachment.shock
    return bool(
      shock is not None
      and shock.converged
      and shock.shock_fit is not None
      and shock.shock_fit.converged
      and len(shock.shock_points_m) >= 3
    )
  ####

  @property
  def field(self):
    return None if self.field_result is None else self.field_result.field
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainAlternatingPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
      and self.source_field_verified
      and self.shock_curve_verified
      and self.physical_closure_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return bool(
      self.field_result is not None
      and self.field_result.physical_closure_verified
    )
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(
      self.field_result is not None
      and self.field_result.state_sampling_available
    )
  ####

  @property
  def upstream_coupling_verified(self) -> bool:
    return bool(
      self.field_result is not None
      and self.field_result.upstream_coupling_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return not (
      self.physical_closure_verified
      and self.state_sampling_available
      and self.upstream_coupling_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_coupled_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
  ) -> MocChainCell:
    if self.chain_promotion_blocked or self.field_result is None:
      raise ValueError(
        'alternating-source physical field is not eligible for chain promotion'
      )
    return self.field_result.as_coupled_chain_cell(
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      cell_index=cell_index,
    )
  ####

  def as_report(self) -> dict[str, object]:
    attachment = (
      None
      if self.field_result is None
      else self.field_result.ambient_attachment
    )
    shock = None if attachment is None else attachment.shock
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_field_verified': self.source_field_verified,
      'shock_curve_verified': self.shock_curve_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'state_sampling_available': self.state_sampling_available,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'canonical_reflected_domain_closed': False,
      'source_model': (
        None if self.source_band is None else self.source_band.as_report()
      ),
      'field_result': (
        None if self.field_result is None else self.field_result.as_report()
      ),
      'start_point_m': self.start_point_m,
      'outer_source_index': self.outer_source_index,
      'compression_amplitude_rad': self.compression_amplitude_rad,
      'sample_count': self.sample_count,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'continuation_law': self.continuation_law,
      'attachment_source': self.attachment_source,
      'use_trace_referenced_profile': self.use_trace_referenced_profile,
      'compression_envelope_skew': self.compression_envelope_skew,
      'position_tolerance_m': self.position_tolerance_m,
      'shock_sample_count': (
        None if shock is None else len(shock.shock_points_m)
      ),
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainSolverOwnedFirstCellTrial:
  """One retained compression-control trial for the first-cell solve.

  The trial contains no prescribed shock geometry.  Its shock and field are
  generated from the bounded alternating source band for the retained
  compression amplitude.  A missing field is retained as an invalid trial so
  the caller can distinguish a solver-domain failure from a physical root.
  """

  compression_amplitude_rad: float
  physical_field: MocReflectedDomainAlternatingPhysicalFieldResult | None
  endpoint_m: tuple[float, float] | None
  residual_m: float | None
  message: str = ''

  def __post_init__(self) -> None:
    amplitude = float(self.compression_amplitude_rad)
    if not isfinite(amplitude) or amplitude <= 0.0:
      raise ValueError(
        'compression_amplitude_rad must be finite and positive'
      )
    object.__setattr__(self, 'compression_amplitude_rad', amplitude)
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocReflectedDomainAlternatingPhysicalFieldResult,
    ):
      raise TypeError(
        'physical_field must be a '
        'MocReflectedDomainAlternatingPhysicalFieldResult or None'
      )
    if self.endpoint_m is not None:
      point = (float(self.endpoint_m[0]), float(self.endpoint_m[1]))
      if not all(isfinite(value) for value in point):
        raise ValueError('endpoint_m must contain finite coordinates')
      object.__setattr__(self, 'endpoint_m', point)
    if self.residual_m is not None:
      residual = float(self.residual_m)
      if not isfinite(residual):
        raise ValueError('residual_m must be finite when supplied')
      object.__setattr__(self, 'residual_m', residual)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether this trial produced a complete local physical field."""

    return bool(
      self.physical_field is not None
      and self.physical_field.converged
      and self.physical_field.field is not None
      and self.residual_m is not None
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'compression_amplitude_rad': self.compression_amplitude_rad,
      'converged': self.converged,
      'endpoint_m': self.endpoint_m,
      'residual_m': self.residual_m,
      'physical_field': (
        None
        if self.physical_field is None
        else self.physical_field.as_report()
      ),
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainSolverOwnedFirstCellResult:
  """Source-owned first-cell endpoint iteration result.

  The solver chooses a shock curve by coupling the generated alternating
  source band to a local compression-control family and iterates that control
  until the shock endpoint aligns with the next solver-generated centerline
  source state.  This removes the caller's shock-geometry seed from the
  first-cell path, while deliberately retaining the local compression family
  and source remesh as research boundary conditions.

  A converged result is a state-carrying local physical field, not a canonical
  reflected Euler/free-boundary solution.  The independent measurement must
  pass before the retained field is used as a research-chain seed.
  """

  status: MocReflectedDomainSolverOwnedFirstCellStatus
  source_band: MocReflectedDomainAlternatingSourceResult | None
  outer_source_index: int | None
  target_centerline_index: int | None
  target_centerline_point_m: tuple[float, float] | None
  compression_amplitude_bracket: tuple[float, float] | None
  selected_trial_index: int | None
  selected_compression_amplitude_rad: float | None
  selected_physical_field: MocReflectedDomainAlternatingPhysicalFieldResult | None
  closure_residual_m: float | None
  shooting_iterations: int
  trials: tuple[MocReflectedDomainSolverOwnedFirstCellTrial, ...]
  message: str = ''
  bracket_scan_sample_count: int = 0
  compression_envelope_skew: float = 0.0

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainSolverOwnedFirstCellStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainSolverOwnedFirstCellStatus'
      )
    if self.source_band is not None and not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a '
        'MocReflectedDomainAlternatingSourceResult or None'
      )
    for name in ('outer_source_index', 'target_centerline_index'):
      value = getattr(self, name)
      if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
      ):
        raise ValueError(f'{name} must be a nonnegative integer when supplied')
    if self.target_centerline_point_m is not None:
      point = (
        float(self.target_centerline_point_m[0]),
        float(self.target_centerline_point_m[1]),
      )
      if not all(isfinite(value) for value in point):
        raise ValueError(
          'target_centerline_point_m must contain finite coordinates'
        )
      object.__setattr__(self, 'target_centerline_point_m', point)
    if self.compression_amplitude_bracket is not None:
      bracket = (
        float(self.compression_amplitude_bracket[0]),
        float(self.compression_amplitude_bracket[1]),
      )
      if (
        not all(isfinite(value) and value > 0.0 for value in bracket)
        or bracket[0] >= bracket[1]
      ):
        raise ValueError(
          'compression_amplitude_bracket must contain two ordered positive values'
        )
      object.__setattr__(self, 'compression_amplitude_bracket', bracket)
    if self.selected_trial_index is not None and (
      isinstance(self.selected_trial_index, bool)
      or not isinstance(self.selected_trial_index, int)
      or self.selected_trial_index < 0
    ):
      raise ValueError(
        'selected_trial_index must be a nonnegative integer when supplied'
      )
    if self.selected_compression_amplitude_rad is not None:
      amplitude = float(self.selected_compression_amplitude_rad)
      if not isfinite(amplitude) or amplitude <= 0.0:
        raise ValueError(
          'selected_compression_amplitude_rad must be finite and positive'
        )
      object.__setattr__(self, 'selected_compression_amplitude_rad', amplitude)
    if self.selected_physical_field is not None and not isinstance(
      self.selected_physical_field,
      MocReflectedDomainAlternatingPhysicalFieldResult,
    ):
      raise TypeError(
        'selected_physical_field must be a '
        'MocReflectedDomainAlternatingPhysicalFieldResult or None'
      )
    if self.closure_residual_m is not None:
      residual = float(self.closure_residual_m)
      if not isfinite(residual):
        raise ValueError('closure_residual_m must be finite when supplied')
      object.__setattr__(self, 'closure_residual_m', residual)
    if (
      isinstance(self.shooting_iterations, bool)
      or not isinstance(self.shooting_iterations, int)
      or self.shooting_iterations < 0
    ):
      raise ValueError('shooting_iterations must be a nonnegative integer')
    if (
      isinstance(self.bracket_scan_sample_count, bool)
      or not isinstance(self.bracket_scan_sample_count, int)
      or self.bracket_scan_sample_count < 0
    ):
      raise ValueError(
        'bracket_scan_sample_count must be a nonnegative integer'
      )
    envelope_skew = float(self.compression_envelope_skew)
    if not isfinite(envelope_skew) or abs(envelope_skew) > 1.0:
      raise ValueError(
        'compression_envelope_skew must be finite and within [-1, 1]'
      )
    object.__setattr__(self, 'compression_envelope_skew', envelope_skew)
    trials = tuple(self.trials)
    if any(
      not isinstance(trial, MocReflectedDomainSolverOwnedFirstCellTrial)
      for trial in trials
    ):
      raise TypeError(
        'trials must contain MocReflectedDomainSolverOwnedFirstCellTrial values'
      )
    if self.selected_trial_index is not None and self.selected_trial_index >= len(trials):
      raise ValueError('selected_trial_index must select a retained trial')
    object.__setattr__(self, 'trials', trials)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether endpoint shooting and the selected field both converged."""

    return bool(
      self.status
      is MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT
      and self.selected_physical_field is not None
      and self.selected_physical_field.converged
      and self.selected_physical_field.physical_closure_verified
      and self.closure_residual_m is not None
    )
  ####

  @property
  def local_physical_field_verified(self) -> bool:
    """Whether the selected trial retained a complete local field."""

    return bool(
      self.selected_physical_field is not None
      and self.selected_physical_field.converged
      and self.selected_physical_field.physical_closure_verified
      and self.selected_physical_field.state_sampling_available
      and self.selected_physical_field.upstream_coupling_verified
    )
  ####

  @property
  def field(self) -> MocPhysicalPostShockFieldResult | None:
    """Return the selected raw physical field, when one was retained."""

    return (
      None
      if self.selected_physical_field is None
      else self.selected_physical_field.field
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Require both the scalar endpoint gate and local field gates."""

    return bool(self.converged and self.local_physical_field_verified)
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(
      self.selected_physical_field is not None
      and self.selected_physical_field.state_sampling_available
    )
  ####

  @property
  def upstream_coupling_verified(self) -> bool:
    return bool(
      self.selected_physical_field is not None
      and self.selected_physical_field.upstream_coupling_verified
    )
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The reflected global free-boundary solve remains an open gate."""

    return False
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    """The coupled two-dimensional Euler residual remains open."""

    return False
  ####

  @property
  def external_validation_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Require independent measurement before chain promotion."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Represent unresolved endpoint closure as a non-physical chain stop."""

    if self.converged:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = (
        'solver-owned first-cell endpoint field is locally closed but remains '
        'a research result; canonical reflected free-boundary, Euler, and '
        'external-validation gates block chain promotion'
      )
    elif self.status is MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = 'solver-owned first-cell endpoint iteration rejected its inputs'
    elif self.status is MocReflectedDomainSolverOwnedFirstCellStatus.SOURCE_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = (
        'solver-owned first-cell endpoint iteration could not sample its '
        'bounded alternating source band'
      )
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'solver-owned first-cell endpoint iteration did not close; no '
        'continued cell may be inferred from its trial fields'
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'solver_owned_first_cell_status': self.status.value,
        'local_physical_field_verified': self.local_physical_field_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_physical_field_verified': self.local_physical_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'state_sampling_available': self.state_sampling_available,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_promotion_decision': self.as_chain_termination_decision().as_report(),
      'source_band': (
        None if self.source_band is None else self.source_band.as_report()
      ),
      'outer_source_index': self.outer_source_index,
      'target_centerline_index': self.target_centerline_index,
      'target_centerline_point_m': self.target_centerline_point_m,
      'compression_amplitude_bracket': self.compression_amplitude_bracket,
      'selected_trial_index': self.selected_trial_index,
      'selected_compression_amplitude_rad': self.selected_compression_amplitude_rad,
      'selected_physical_field': (
        None
        if self.selected_physical_field is None
        else self.selected_physical_field.as_report()
      ),
      'closure_residual_m': self.closure_residual_m,
      'shooting_iterations': self.shooting_iterations,
      'bracket_scan_sample_count': self.bracket_scan_sample_count,
      'compression_envelope_skew': self.compression_envelope_skew,
      'trial_count': len(self.trials),
      'trials': tuple(trial.as_report() for trial in self.trials),
      'message': self.message,
    }
  ####


def _static_pressure_from_total_pressure(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  return float(total_pressure_Pa) / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))


class MocReflectedDomainGlobalShockRemeshStatus(str, Enum):
  """Outcome of a bounded global reflected-shock remesh sweep."""

  CONVERGED_ENDPOINT = 'converged_global_reflected_shock_endpoint'
  NO_ENDPOINT_CLOSURE = 'global_reflected_shock_no_endpoint_closure'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FIELD_FAILURE = 'global_reflected_shock_source_field_failure'
  ATTEMPT_FAILURE = 'global_reflected_shock_attempt_failure'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalShockRemeshAttempt:
  """One globally selected source pair and compression-profile trial."""

  outer_source_index: int
  target_centerline_index: int
  compression_envelope_skew: float
  first_cell_result: MocReflectedDomainSolverOwnedFirstCellResult

  def __post_init__(self) -> None:
    for name in ('outer_source_index', 'target_centerline_index'):
      value = getattr(self, name)
      if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
      ):
        raise ValueError(f'{name} must be a nonnegative integer')
    skew = float(self.compression_envelope_skew)
    if not isfinite(skew) or abs(skew) > 1.0:
      raise ValueError(
        'compression_envelope_skew must be finite and within [-1, 1]'
      )
    object.__setattr__(self, 'compression_envelope_skew', skew)
    if not isinstance(
      self.first_cell_result,
      MocReflectedDomainSolverOwnedFirstCellResult,
    ):
      raise TypeError(
        'first_cell_result must be a '
        'MocReflectedDomainSolverOwnedFirstCellResult'
      )
  ####

  @property
  def converged(self) -> bool:
    return self.first_cell_result.converged
  ####

  @property
  def residual_m(self) -> float | None:
    return self.first_cell_result.closure_residual_m
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'outer_source_index': self.outer_source_index,
      'target_centerline_index': self.target_centerline_index,
      'compression_envelope_skew': self.compression_envelope_skew,
      'converged': self.converged,
      'residual_m': self.residual_m,
      'first_cell_result': self.first_cell_result.as_report(),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalShockRemeshResult:
  """A bounded whole-path reflected-shock remesh and its retained attempts.

  The sweep changes only solver-owned source selection and the bounded global
  compression-profile shape.  Every attempt is a complete first-cell solve
  or a typed failure.  A locally aligned endpoint is still a research result:
  the canonical reflected free boundary, coupled Euler residual, and chain
  promotion remain closed gates.
  """

  status: MocReflectedDomainGlobalShockRemeshStatus
  source_band: MocReflectedDomainAlternatingSourceResult | None
  attempts: tuple[MocReflectedDomainGlobalShockRemeshAttempt, ...]
  selected_attempt_index: int | None
  selected_residual_m: float | None
  outer_source_indices: tuple[int, ...]
  target_centerline_indices: tuple[int, ...]
  compression_envelope_skews: tuple[float, ...]
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalShockRemeshStatus):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalShockRemeshStatus'
      )
    if self.source_band is not None and not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult or None'
      )
    attempts = tuple(self.attempts)
    if any(
      not isinstance(
        attempt,
        MocReflectedDomainGlobalShockRemeshAttempt,
      )
      for attempt in attempts
    ):
      raise TypeError(
        'attempts must contain MocReflectedDomainGlobalShockRemeshAttempt values'
      )
    object.__setattr__(self, 'attempts', attempts)
    for name in ('outer_source_indices', 'target_centerline_indices'):
      values = tuple(getattr(self, name))
      if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
      ):
        raise ValueError(f'{name} must contain nonnegative integers')
      object.__setattr__(self, name, values)
    skews = tuple(float(value) for value in self.compression_envelope_skews)
    if any(not isfinite(value) or abs(value) > 1.0 for value in skews):
      raise ValueError(
        'compression_envelope_skews must be finite values within [-1, 1]'
      )
    object.__setattr__(self, 'compression_envelope_skews', skews)
    if self.selected_attempt_index is not None and (
      isinstance(self.selected_attempt_index, bool)
      or not isinstance(self.selected_attempt_index, int)
      or self.selected_attempt_index < 0
      or self.selected_attempt_index >= len(attempts)
    ):
      raise ValueError('selected_attempt_index must select a retained attempt')
    if self.selected_residual_m is not None:
      residual = float(self.selected_residual_m)
      if not isfinite(residual):
        raise ValueError('selected_residual_m must be finite when supplied')
      object.__setattr__(self, 'selected_residual_m', residual)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def selected_attempt(self) -> MocReflectedDomainGlobalShockRemeshAttempt | None:
    return (
      None
      if self.selected_attempt_index is None
      else self.attempts[self.selected_attempt_index]
    )
  ####

  @property
  def attempt_count(self) -> int:
    return len(self.attempts)
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocReflectedDomainGlobalShockRemeshStatus.CONVERGED_ENDPOINT
      and self.selected_attempt is not None
      and self.selected_attempt.converged
      and self.selected_residual_m is not None
    )
  ####

  @property
  def source_field_verified(self) -> bool:
    return bool(
      self.source_band is not None
      and self.source_band.source_field_verified
    )
  ####

  @property
  def local_endpoint_verified(self) -> bool:
    return bool(self.converged)
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The global remesh remains below the canonical physical closure gate."""

    return False
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    return False
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    return False
  ####

  @property
  def external_validation_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = self.message or 'global reflected-shock remesh rejected its inputs'
    elif self.status is MocReflectedDomainGlobalShockRemeshStatus.SOURCE_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = self.message or 'global reflected-shock remesh lacks a bounded source field'
    elif self.converged:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = (
        'global reflected-shock endpoint is locally aligned but canonical '
        'free-boundary, Euler, and external-validation gates block promotion'
      )
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        self.message
        or 'global reflected-shock remesh did not close its endpoint; no '
        'continued cell may be inferred'
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'termination_model': 'global-reflected-shock-remesh',
        'status': self.status.value,
        'source_field_verified': self.source_field_verified,
        'local_endpoint_verified': self.local_endpoint_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_field_verified': self.source_field_verified,
      'local_endpoint_verified': self.local_endpoint_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'selected_attempt_index': self.selected_attempt_index,
      'selected_residual_m': self.selected_residual_m,
      'outer_source_indices': self.outer_source_indices,
      'target_centerline_indices': self.target_centerline_indices,
      'compression_envelope_skews': self.compression_envelope_skews,
      'attempt_count': len(self.attempts),
      'attempts': tuple(attempt.as_report() for attempt in self.attempts),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'source_band': (
        None if self.source_band is None else self.source_band.as_report()
      ),
      'message': self.message,
    }
  ####


class MocReflectedDomainGlobalEulerShockBoundaryStatus(str, Enum):
  """Outcome of the bounded global Euler shock-field reconciliation."""

  CONVERGED = 'converged_global_euler_shock_field'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FRONTIER_FAILURE = 'global_euler_source_frontier_failure'
  GEOMETRY_FAILURE = 'global_euler_shock_geometry_failure'
  SHOCK_BOUNDARY_FAILURE = 'global_euler_shock_boundary_failure'
  AMBIENT_FIELD_FAILURE = 'global_euler_ambient_field_failure'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryResult:
  """A globally remeshed exact-Euler shock field on a bounded source band.

  The input global remesh supplies a finite candidate shock path.  This result
  re-samples that path in the solver-owned alternating source field, enforces
  explicit zero-strength Mach-wave endpoint tangents, and then assembles the
  exact ambient/centerline characteristic field.  A converged result closes a
  local reflected/free-boundary field only; external validation and chain-cell
  promotion remain separate hard gates.
  """

  status: MocReflectedDomainGlobalEulerShockBoundaryStatus
  global_remesh: MocReflectedDomainGlobalShockRemeshResult | None
  selected_attempt_index: int | None
  outer_source_index: int | None
  target_centerline_index: int | None
  initial_shock_points_m: tuple[tuple[float, float], ...] = ()
  remeshed_shock_points_m: tuple[tuple[float, float], ...] = ()
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None
  physical_field: MocEulerAmbientPhysicalFieldResult | None = None
  source_frontier_state: CharacteristicState | None = None
  source_frontier_total_pressure_Pa: float | None = None
  source_frontier_verified: bool = False
  first_endpoint_tangent_residual_rad: float | None = None
  last_endpoint_tangent_residual_rad: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalEulerShockBoundaryStatus):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalEulerShockBoundaryStatus'
      )
    if self.global_remesh is not None and not isinstance(
      self.global_remesh,
      MocReflectedDomainGlobalShockRemeshResult,
    ):
      raise TypeError(
        'global_remesh must be a MocReflectedDomainGlobalShockRemeshResult or None'
      )
    for name in (
      'selected_attempt_index',
      'outer_source_index',
      'target_centerline_index',
    ):
      value = getattr(self, name)
      if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
      ):
        raise ValueError(f'{name} must be a nonnegative integer or None')
    if self.selected_attempt_index is not None and self.global_remesh is not None and (
      self.selected_attempt_index >= len(self.global_remesh.attempts)
    ):
      raise ValueError('selected_attempt_index must select a retained global attempt')
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'physical_field must be a MocEulerAmbientPhysicalFieldResult or None'
      )
    if self.source_frontier_state is not None and not isinstance(
      self.source_frontier_state,
      CharacteristicState,
    ):
      raise TypeError('source_frontier_state must be a CharacteristicState or None')
    if self.source_frontier_total_pressure_Pa is not None:
      pressure = float(self.source_frontier_total_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError(
          'source_frontier_total_pressure_Pa must be finite and positive'
        )
      object.__setattr__(self, 'source_frontier_total_pressure_Pa', pressure)
    for name in (
      'first_endpoint_tangent_residual_rad',
      'last_endpoint_tangent_residual_rad',
    ):
      value = getattr(self, name)
      if value is not None and not isfinite(float(value)):
        raise ValueError(f'{name} must be finite when supplied')
    if not isinstance(self.source_frontier_verified, bool):
      raise TypeError('source_frontier_verified must be a bool')
    initial_points = tuple(
      (float(point[0]), float(point[1])) for point in self.initial_shock_points_m
    )
    remeshed_points = tuple(
      (float(point[0]), float(point[1])) for point in self.remeshed_shock_points_m
    )
    if any(
      not all(isfinite(value) for value in point)
      for point in (*initial_points, *remeshed_points)
    ):
      raise ValueError('shock point sequences must contain finite coordinates')
    object.__setattr__(self, 'initial_shock_points_m', initial_points)
    object.__setattr__(self, 'remeshed_shock_points_m', remeshed_points)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.CONVERGED
      and self.source_frontier_verified
      and self.shock_boundary is not None
      and self.shock_boundary.converged
      and self.physical_field is not None
      and self.physical_field.converged
      and self.physical_field.physical_closure_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return bool(self.converged)
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The canonical production free-boundary audit remains a later gate."""

    return False
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    """The exact local field is not the independent production audit."""

    return False
  ####

  @property
  def external_validation_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.converged:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or (
          'global exact-Euler shock field closed locally, but independent '
          'Euler-cell, refinement, reflected-free-boundary, and external '
          'validation gates block promotion'
          if self.converged
          else 'global exact-Euler shock field did not close its bounded boundary'
        )
      ),
      diagnostics={
        'termination_model': 'global-reflected-euler-shock-boundary',
        'status': self.status.value,
        'source_frontier_verified': self.source_frontier_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'selected_attempt_index': self.selected_attempt_index,
      'outer_source_index': self.outer_source_index,
      'target_centerline_index': self.target_centerline_index,
      'initial_shock_points_m': [list(point) for point in self.initial_shock_points_m],
      'remeshed_shock_points_m': [list(point) for point in self.remeshed_shock_points_m],
      'source_frontier_verified': self.source_frontier_verified,
      'source_frontier_state': (
        None
        if self.source_frontier_state is None
        else {
          'x_m': self.source_frontier_state.x_m,
          'y_m': self.source_frontier_state.y_m,
          'theta_rad': self.source_frontier_state.theta_rad,
          'mach': self.source_frontier_state.mach,
          'gamma': self.source_frontier_state.gamma,
        }
      ),
      'source_frontier_total_pressure_Pa': self.source_frontier_total_pressure_Pa,
      'first_endpoint_tangent_residual_rad': self.first_endpoint_tangent_residual_rad,
      'last_endpoint_tangent_residual_rad': self.last_endpoint_tangent_residual_rad,
      'shock_boundary': (
        None if self.shock_boundary is None else self.shock_boundary.as_report()
      ),
      'physical_field': (
        None if self.physical_field is None else self.physical_field.as_report()
      ),
      'global_remesh': (
        None if self.global_remesh is None else self.global_remesh.as_report()
      ),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####


def solve_reflected_domain_global_euler_shock_boundary(
  global_remesh: MocReflectedDomainGlobalShockRemeshResult,
  *,
  selected_attempt_index: int | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  maximum_boundary_iterations: int = 16,
) -> MocReflectedDomainGlobalEulerShockBoundaryResult:
  """Close one bounded global-remesh shock against its source frontier.

  The global compression/profile sweep retains a sampled shock path that can
  end at a continuous point on the source band's centerline edge rather than
  at the next discrete axis vertex.  This bridge preserves that path's
  ordinates, projects only its first and last segments onto the exact local
  Mach-wave tangents, re-samples the bounded alternating field, and then runs
  the exact Euler ambient/centerline assembler.

  The endpoint projection is deliberately deterministic and local.  It does
  not invent states outside ``source_band``, change the selected global
  attempt, or infer a continued ``MocChainCell``.  A converged result is a
  locally closed exact-Euler field with a continuous source-frontier seam;
  independent cell/refinement and external validation remain required.
  """

  resolved_attempt_index = selected_attempt_index
  resolved_outer_index: int | None = None
  resolved_target_index: int | None = None
  source_band = (
    global_remesh.source_band
    if isinstance(global_remesh, MocReflectedDomainGlobalShockRemeshResult)
    else None
  )
  initial_points: tuple[tuple[float, float], ...] = ()
  remeshed_points: tuple[tuple[float, float], ...] = ()
  curve: MocEulerShockBoundaryCurveResult | None = None
  physical_field: MocEulerAmbientPhysicalFieldResult | None = None
  source_frontier_state: CharacteristicState | None = None
  source_frontier_pressure: float | None = None
  source_frontier_verified = False
  first_endpoint_residual: float | None = None
  last_endpoint_residual: float | None = None

  def failure(
    status: MocReflectedDomainGlobalEulerShockBoundaryStatus,
    message: str,
  ) -> MocReflectedDomainGlobalEulerShockBoundaryResult:
    return MocReflectedDomainGlobalEulerShockBoundaryResult(
      status=status,
      global_remesh=(
        global_remesh
        if isinstance(global_remesh, MocReflectedDomainGlobalShockRemeshResult)
        else None
      ),
      selected_attempt_index=resolved_attempt_index,
      outer_source_index=resolved_outer_index,
      target_centerline_index=resolved_target_index,
      initial_shock_points_m=initial_points,
      remeshed_shock_points_m=remeshed_points,
      shock_boundary=curve,
      physical_field=physical_field,
      source_frontier_state=source_frontier_state,
      source_frontier_total_pressure_Pa=source_frontier_pressure,
      source_frontier_verified=source_frontier_verified,
      first_endpoint_tangent_residual_rad=first_endpoint_residual,
      last_endpoint_tangent_residual_rad=last_endpoint_residual,
      message=message,
    )

  if not isinstance(global_remesh, MocReflectedDomainGlobalShockRemeshResult):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT,
      'global_remesh must be a MocReflectedDomainGlobalShockRemeshResult',
    )
  if not isinstance(branch, ShockBranch):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
    )
  resolved_tolerances: dict[str, float] = {}
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('residual_tolerance', residual_tolerance),
  ):
    if isinstance(value, bool):
      numeric_value = float('nan')
    else:
      try:
        numeric_value = float(value)
      except (TypeError, ValueError):
        numeric_value = float('nan')
    if not isfinite(numeric_value) or numeric_value <= 0.0:
      return failure(
        MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT,
        f'{name} must be finite and positive',
      )
    resolved_tolerances[name] = numeric_value
  if (
    isinstance(maximum_boundary_iterations, bool)
    or not isinstance(maximum_boundary_iterations, int)
    or maximum_boundary_iterations < 1
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT,
      'maximum_boundary_iterations must be a positive integer',
    )
  position_tolerance_m = resolved_tolerances['position_tolerance_m']
  invariant_tolerance = resolved_tolerances['invariant_tolerance']
  pressure_tolerance = resolved_tolerances['pressure_tolerance']
  tangent_tolerance = resolved_tolerances['tangent_tolerance']
  shock_angle_tolerance_rad = resolved_tolerances['shock_angle_tolerance_rad']
  residual_tolerance = resolved_tolerances['residual_tolerance']
  if source_band is None or not source_band.source_field_verified:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'global Euler shock closure requires a verified bounded source band',
    )
  if resolved_attempt_index is None:
    resolved_attempt_index = global_remesh.selected_attempt_index
  if (
    isinstance(resolved_attempt_index, bool)
    or not isinstance(resolved_attempt_index, int)
    or resolved_attempt_index < 0
    or resolved_attempt_index >= len(global_remesh.attempts)
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT,
      'selected_attempt_index must select a retained global remesh attempt',
    )
  attempt = global_remesh.attempts[resolved_attempt_index]
  resolved_outer_index = attempt.outer_source_index
  resolved_target_index = attempt.target_centerline_index
  if (
    resolved_outer_index >= len(source_band.outer_source_states)
    or resolved_target_index >= len(source_band.centerline_source_states)
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'global remesh attempt references a source index outside the retained band',
    )
  selected_field = attempt.first_cell_result.selected_physical_field
  candidate_field = None if selected_field is None else selected_field.field
  if candidate_field is None:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected global remesh attempt does not retain a physical shock field',
    )
  initial_points = tuple(candidate_field.shock_boundary_points_m)
  if len(initial_points) < 3:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'selected global remesh shock field must retain at least three points',
    )
  if any(
    len(point) != 2 or not all(isfinite(float(value)) for value in point)
    for point in initial_points
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'selected global remesh shock field contains non-finite geometry',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    for first, second in zip(initial_points, initial_points[1:])
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'selected global remesh shock field must advance downstream and downward',
    )
  target_y = source_band.target_centerline_y_m
  target_theta = source_band.target_centerline_flow_angle_rad
  if abs(initial_points[-1][1] - target_y) > position_tolerance_m:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected shock endpoint does not lie on the source centerline frontier',
    )

  outer_source = source_band.outer_source_states[resolved_outer_index]
  first_point = initial_points[0]
  if (
    abs(first_point[0] - outer_source.x_m) > position_tolerance_m
    or abs(first_point[1] - outer_source.y_m) > position_tolerance_m
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected shock start does not reproduce its selected outer source point',
    )
  sampled_first = source_band.state_at(
    first_point,
    position_tolerance_m=position_tolerance_m,
  )
  if sampled_first is None:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected shock start is outside the bounded source band',
    )
  if not _state_matches(
    sampled_first,
    outer_source,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=invariant_tolerance,
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected shock start does not reproduce the selected outer source state',
    )

  frontier_point = initial_points[-1]
  source_frontier_state = source_band.state_at(
    frontier_point,
    position_tolerance_m=position_tolerance_m,
  )
  source_frontier_pressure = source_band.total_pressure_at(
    frontier_point,
    position_tolerance_m=position_tolerance_m,
  )
  if (
    source_frontier_state is None
    or source_frontier_pressure is None
    or not isfinite(float(source_frontier_pressure))
    or source_frontier_pressure <= 0.0
    or abs(source_frontier_state.y_m - target_y) > position_tolerance_m
    or abs(source_frontier_state.theta_rad - target_theta) > invariant_tolerance
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected shock endpoint is not a state-carrying source centerline point',
    )
  centerline_xs = tuple(state.x_m for state in source_band.centerline_source_states)
  if (
    frontier_point[0] < centerline_xs[0] - position_tolerance_m
    or frontier_point[0] > centerline_xs[-1] + position_tolerance_m
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'selected shock endpoint lies outside the retained centerline source edge',
    )
  source_frontier_verified = True

  try:
    first_tangent = sampled_first.theta_rad - sampled_first.mu_rad
    last_tangent = source_frontier_state.theta_rad - source_frontier_state.mu_rad
    first_slope = tan(first_tangent)
    last_slope = tan(last_tangent)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'source frontier Mach-wave endpoint tangent is not finite',
    )
  if (
    not isfinite(first_slope)
    or not isfinite(last_slope)
    or first_slope >= 0.0
    or last_slope >= 0.0
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'source frontier Mach-wave endpoint tangents do not descend toward the centerline',
    )
  remeshed = list(initial_points)
  remeshed[1] = (
    first_point[0] + (initial_points[1][1] - first_point[1]) / first_slope,
    initial_points[1][1],
  )
  remeshed[-2] = (
    frontier_point[0]
    - (frontier_point[1] - initial_points[-2][1]) / last_slope,
    initial_points[-2][1],
  )
  remeshed_points = tuple(remeshed)
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    for first, second in zip(remeshed_points, remeshed_points[1:])
  ):
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'Mach-wave endpoint projection broke shock-point ordering',
    )
  first_endpoint_residual = abs(
    (remeshed_points[1][1] - remeshed_points[0][1])
    / (remeshed_points[1][0] - remeshed_points[0][0])
    - first_slope
  )
  last_endpoint_residual = abs(
    (remeshed_points[-1][1] - remeshed_points[-2][1])
    / (remeshed_points[-1][0] - remeshed_points[-2][0])
    - last_slope
  )

  upstream_states: list[CharacteristicState] = []
  upstream_pressures: list[float] = []
  for index, point in enumerate(remeshed_points):
    state = source_band.state_at(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    pressure = source_band.static_pressure_at(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    if (
      state is None
      or pressure is None
      or not isfinite(float(pressure))
      or pressure <= 0.0
    ):
      return failure(
        MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
        f'remeshed shock point {index} left the bounded source band',
      )
    upstream_states.append(state)
    upstream_pressures.append(float(pressure))
  try:
    curve = fit_euler_consistent_shock_boundary_from_geometry(
      tuple(upstream_states),
      tuple(upstream_pressures),
      remeshed_points,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      residual_tolerance=residual_tolerance,
      allow_zero_strength_endpoints=True,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SHOCK_BOUNDARY_FAILURE,
      f'global Euler shock boundary reconciliation raised: {error}',
    )
  if not curve.converged or not curve.local_euler_verified:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SHOCK_BOUNDARY_FAILURE,
      f'global Euler shock boundary reconciliation did not converge: {curve.message}',
    )
  ambient_pressure = source_band.ambient_pressure_Pa
  if ambient_pressure is None:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.SOURCE_FRONTIER_FAILURE,
      'source band does not retain an ambient pressure for exact field closure',
    )
  try:
    physical_field = assemble_euler_ambient_physical_field(
      curve,
      ambient_pressure,
      target_centerline_y_m=target_y,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      maximum_boundary_iterations=maximum_boundary_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.AMBIENT_FIELD_FAILURE,
      f'global Euler ambient/centerline assembly raised: {error}',
    )
  if not physical_field.converged or not physical_field.physical_closure_verified:
    return failure(
      MocReflectedDomainGlobalEulerShockBoundaryStatus.AMBIENT_FIELD_FAILURE,
      'global Euler shock boundary closed locally, but its ambient/centerline '
      f'field did not pass closure gates: {physical_field.message}',
    )
  return MocReflectedDomainGlobalEulerShockBoundaryResult(
    status=MocReflectedDomainGlobalEulerShockBoundaryStatus.CONVERGED,
    global_remesh=global_remesh,
    selected_attempt_index=resolved_attempt_index,
    outer_source_index=resolved_outer_index,
    target_centerline_index=resolved_target_index,
    initial_shock_points_m=initial_points,
    remeshed_shock_points_m=remeshed_points,
    shock_boundary=curve,
    physical_field=physical_field,
    source_frontier_state=source_frontier_state,
    source_frontier_total_pressure_Pa=source_frontier_pressure,
    source_frontier_verified=True,
    first_endpoint_tangent_residual_rad=first_endpoint_residual,
    last_endpoint_tangent_residual_rad=last_endpoint_residual,
    message=(
      'global remeshed shock coupled to a continuous source-centerline '
      'frontier and a closed exact-Euler ambient/centerline field; independent '
      'cell, refinement, and external validation remain pending'
    ),
  )


def solve_reflected_domain_alternating_source(
  reflection_patch: MocTerminalReflectionPatchResult,
  ambient_pressure_Pa: float,
  total_pressure_Pa: float | None = None,
  *,
  source_sample_count: int = 6,
  outer_seed_state: CharacteristicState | None = None,
  outer_seed_total_pressure_Pa: float | None = None,
  centerline_total_pressure_Pa: Sequence[float] = (),
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  declared_polarity: MocReflectedTracePolarity | None = None,
  position_tolerance_m: float = 1.0e-3,
  trace_forward_tolerance_m: float = 1.0e-4,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  maximum_iterations: int = 16,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
) -> MocReflectedDomainAlternatingSourceResult:
  """March a bounded alternating reflected-domain source band.

  The first ``C-`` centerline reflection must reproduce the exact endpoint of
  ``reflection_patch.outgoing_trace_samples``.  Each subsequent cycle then
  solves one ``C+`` ambient-pressure/tangent endpoint and reflects that new
  outer state with one ``C-`` characteristic.  The returned band contains
  only local two-triangle cells whose neighboring alternating seams were
  explicitly solved; it does not claim the full triangular source-strip
  cross-pairing or a downstream shock closure.

  ``centerline_total_pressure_Pa`` is optional explicit pressure lineage.  If
  omitted, the retained patch pressure is carried uniformly.  If supplied,
  its first value must match the exact patch anchor pressure and each value
  must exceed ambient pressure.  The solver transports these values; it does
  not infer shock entropy or authorize a physical chain cell.
  """

  patch = (
    reflection_patch
    if isinstance(reflection_patch, MocTerminalReflectionPatchResult)
    else None
  )
  try:
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    ambient_pressure = float('nan')
  if total_pressure_Pa is None:
    if (
      patch is not None
      and patch.outgoing_trace_total_pressure_Pa
    ):
      reference_pressure = float(patch.outgoing_trace_total_pressure_Pa[0])
    else:
      reference_pressure = float('nan')
  else:
    try:
      reference_pressure = float(total_pressure_Pa)
    except (TypeError, ValueError):
      reference_pressure = float('nan')
  try:
    supplied_pressures = tuple(
      float(value) for value in centerline_total_pressure_Pa
    )
  except (TypeError, ValueError):
    supplied_pressures = ()
    pressure_row_error = True
  else:
    pressure_row_error = False
  try:
    target_y = float(target_centerline_y_m)
    target_theta = float(target_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    target_y = float('nan')
    target_theta = float('nan')
  try:
    resolved_incoming_handoff = tuple(incoming_handoff)
  except TypeError:
    resolved_incoming_handoff = ()
    incoming_handoff_error = True
  else:
    incoming_handoff_error = any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in resolved_incoming_handoff
    )
  try:
    seed_pressure = (
      float(outer_seed_total_pressure_Pa)
      if outer_seed_total_pressure_Pa is not None
      else reference_pressure
    )
  except (TypeError, ValueError):
    seed_pressure = float('nan')
  try:
    resolved_position_tolerance = float(position_tolerance_m)
    resolved_trace_forward_tolerance = float(trace_forward_tolerance_m)
    resolved_invariant_tolerance = float(invariant_tolerance)
    resolved_pressure_tolerance = float(pressure_tolerance)
  except (TypeError, ValueError) as error:
    raise ValueError('MOC alternating-source tolerances must be numeric') from error
  for name, value in (
    ('position_tolerance_m', resolved_position_tolerance),
    ('trace_forward_tolerance_m', resolved_trace_forward_tolerance),
    ('invariant_tolerance', resolved_invariant_tolerance),
    ('pressure_tolerance', resolved_pressure_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    isinstance(source_sample_count, bool)
    or not isinstance(source_sample_count, int)
    or source_sample_count < 3
  ):
    source_sample_count = 0
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')

  centerline: list[CharacteristicState] = []
  outer: list[CharacteristicState] = []
  centerline_pressures: list[float] = []
  outer_pressures: list[float] = []
  centerline_results: list[CharacteristicPointResult] = []
  point_results: list[MocFreeBoundaryPointResult] = []
  incoming_validation: MocCharacteristicTraceResult | None = None
  incoming_polarity: MocReflectedTracePolarityResult | None = None
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None
  cells: list[MocCharacteristicCell] = []
  topology: MocTopologyResult | None = None
  reflection_anchor_verified = False
  alternating_seam_verified = False

  resolved_seed = outer_seed_state

  def failure(
    status: MocReflectedDomainAlternatingSourceStatus,
    message: str,
  ) -> MocReflectedDomainAlternatingSourceResult:
    return MocReflectedDomainAlternatingSourceResult(
      status=status,
      reflection_patch=patch,
      centerline_source_states=tuple(centerline),
      outer_source_states=tuple(outer),
      centerline_total_pressure_Pa=tuple(centerline_pressures),
      outer_total_pressure_Pa=tuple(outer_pressures),
      outer_seed_state=resolved_seed,
      outer_seed_total_pressure_Pa=(
        seed_pressure
        if isfinite(seed_pressure) and seed_pressure > 0.0
        else None
      ),
      ambient_pressure_Pa=(
        ambient_pressure
        if isfinite(ambient_pressure) and ambient_pressure > 0.0
        else None
      ),
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=incoming_polarity,
      centerline_results=tuple(centerline_results),
      point_results=tuple(point_results),
      ambient_boundary=ambient_boundary,
      cells=tuple(cells),
      topology=topology,
      reflection_anchor_verified=reflection_anchor_verified,
      alternating_seam_verified=alternating_seam_verified,
      message=message,
      target_centerline_y_m=(target_y if isfinite(target_y) else 0.0),
      target_centerline_flow_angle_rad=(
        target_theta if isfinite(target_theta) else 0.0
      ),
      position_tolerance_m=resolved_position_tolerance,
      trace_forward_tolerance_m=resolved_trace_forward_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      incoming_handoff=resolved_incoming_handoff,
    )

  if source_sample_count == 0:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'source_sample_count must be an integer of at least three',
    )
  if incoming_handoff_error:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'incoming_handoff must contain MocChainBoundarySample values',
    )
  if (
    not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or not isfinite(reference_pressure)
    or reference_pressure <= ambient_pressure
    or not isfinite(target_y)
    or not isfinite(target_theta)
    or pressure_row_error
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'ambient/reference pressures and centerline target values must be finite and valid',
    )
  if abs(target_y) > resolved_position_tolerance or abs(target_theta) > resolved_invariant_tolerance:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'the alternating source primitive currently supports only the y=0, theta=0 symmetry centerline',
    )
  if len(supplied_pressures) not in (0, source_sample_count):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'centerline_total_pressure_Pa must match source_sample_count when supplied',
    )
  resolved_centerline_pressures = (
    (reference_pressure,) * source_sample_count
    if not supplied_pressures
    else supplied_pressures
  )
  if any(
    not isfinite(value) or value <= ambient_pressure
    for value in resolved_centerline_pressures
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'alternating source total-pressure values must be finite and exceed ambient pressure',
    )
  if patch is None:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'reflection_patch must be a MocTerminalReflectionPatchResult',
    )
  if not patch.converged:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      'alternating source remesh requires a converged terminal reflection patch',
    )
  incoming = patch.outgoing_trace_samples
  incoming_validation = validate_characteristic_trace(
    incoming,
    CharacteristicFamily.MINUS,
    position_tolerance_m=resolved_position_tolerance,
    forward_position_tolerance_m=resolved_trace_forward_tolerance,
    invariant_tolerance=resolved_invariant_tolerance,
  )
  if not incoming_validation.converged:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INCOMING_TRACE_FAILURE,
      f'exact reflected C- front failed validation: {incoming_validation.message}',
    )
  incoming_polarity = classify_reflected_trace_polarity(
    incoming,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_theta,
    position_tolerance_m=resolved_position_tolerance,
    forward_position_tolerance_m=resolved_trace_forward_tolerance,
    invariant_tolerance=resolved_invariant_tolerance,
  )
  if not incoming_polarity.converged:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INCOMING_TRACE_FAILURE,
      f'exact reflected trace polarity failed validation: {incoming_polarity.message}',
    )
  if (
    declared_polarity is not None
    and declared_polarity is not incoming_polarity.status
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INCOMING_TRACE_FAILURE,
      'declared reflected trace polarity does not match the exact incoming front',
    )
  if len(incoming) < 2:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.INCOMING_TRACE_FAILURE,
      'the reflected C- front requires at least two samples',
    )
  if resolved_seed is None:
    resolved_seed = incoming[0].state
  if not isinstance(resolved_seed, CharacteristicState):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.SEED_FAILURE,
      'outer_seed_state must be a CharacteristicState when supplied',
    )
  if outer_seed_total_pressure_Pa is None:
    seed_pressure = incoming[0].total_pressure_Pa
  if (
    not isfinite(seed_pressure)
    or seed_pressure <= ambient_pressure
    or not _state_matches(
      resolved_seed,
      incoming[0].state,
      position_tolerance_m=resolved_position_tolerance,
      state_tolerance=resolved_invariant_tolerance,
    )
    or not _pressure_matches(
      seed_pressure,
      incoming[0].total_pressure_Pa,
      resolved_pressure_tolerance,
    )
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.SEED_FAILURE,
      'the alternating outer seed must reproduce the first exact outgoing-front state and pressure',
    )
  if (
    resolved_seed.y_m <= target_y + resolved_position_tolerance
    or abs(_static_pressure_from_total_pressure(resolved_seed, seed_pressure) - ambient_pressure)
    / ambient_pressure > resolved_pressure_tolerance
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.SEED_FAILURE,
      'the alternating outer seed must be above the centerline and ambient-pressure matched',
    )
  if (
    not _pressure_matches(
      reference_pressure,
      seed_pressure,
      resolved_pressure_tolerance,
    )
    or not _pressure_matches(
      resolved_centerline_pressures[0],
      incoming[-1].total_pressure_Pa,
      resolved_pressure_tolerance,
    )
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.ANCHOR_FAILURE,
      'the first alternating source pressure must preserve the exact reflection-front pressure',
    )

  previous_outer = resolved_seed
  previous_axis: CharacteristicState | None = None
  for index in range(source_sample_count):
    axis_result = centerline_characteristic_point(
      previous_outer,
      CharacteristicFamily.MINUS,
      position_tolerance_m=resolved_position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
    )
    centerline_results.append(axis_result)
    if not axis_result.converged or axis_result.state is None or axis_result.point_m is None:
      return failure(
        MocReflectedDomainAlternatingSourceStatus.CENTERLINE_FAILURE,
        f'alternating centerline sample {index} failed: {axis_result.message}',
      )
    axis_state = axis_result.state
    if index == 0:
      reflection_anchor_verified = bool(
        _state_matches(
          axis_state,
          incoming[-1].state,
          position_tolerance_m=resolved_position_tolerance,
          state_tolerance=resolved_invariant_tolerance,
        )
        and _pressure_matches(
          resolved_centerline_pressures[index],
          incoming[-1].total_pressure_Pa,
          resolved_pressure_tolerance,
        )
      )
      if not reflection_anchor_verified:
        return failure(
          MocReflectedDomainAlternatingSourceStatus.ANCHOR_FAILURE,
          'the first C- reflection of the outer seed did not reproduce the exact prior patch anchor',
        )
    elif (
      previous_axis is None
      or axis_state.x_m <= previous_axis.x_m + resolved_position_tolerance
      or axis_state.x_m <= previous_outer.x_m + resolved_position_tolerance
      or abs(axis_state.k_minus - previous_outer.k_minus) > resolved_invariant_tolerance
    ):
      return failure(
        MocReflectedDomainAlternatingSourceStatus.CENTERLINE_FAILURE,
        f'alternating centerline sample {index} failed downstream or C- compatibility ordering',
      )
    if (
      abs(axis_state.y_m - target_y) > resolved_position_tolerance
      or abs(axis_state.theta_rad - target_theta) > resolved_invariant_tolerance
    ):
      return failure(
        MocReflectedDomainAlternatingSourceStatus.CENTERLINE_FAILURE,
        f'alternating centerline sample {index} did not remain on the declared symmetry centerline',
      )
    centerline.append(axis_state)
    centerline_pressures.append(resolved_centerline_pressures[index])

    boundary_result = solve_ambient_pressure_free_boundary_point(
      axis_state,
      previous_outer,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=resolved_centerline_pressures[index],
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=resolved_position_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    point_results.append(boundary_result)
    if not boundary_result.converged or boundary_result.state is None or boundary_result.point_m is None:
      return failure(
        MocReflectedDomainAlternatingSourceStatus.BOUNDARY_FAILURE,
        f'alternating ambient boundary sample {index} failed: {boundary_result.message}',
      )
    next_outer = boundary_result.state
    if (
      next_outer.x_m <= previous_outer.x_m + resolved_position_tolerance
      or next_outer.x_m <= axis_state.x_m + resolved_position_tolerance
      or next_outer.y_m <= target_y + resolved_position_tolerance
      or abs(next_outer.k_plus - axis_state.k_plus) > resolved_invariant_tolerance
    ):
      return failure(
        MocReflectedDomainAlternatingSourceStatus.BOUNDARY_FAILURE,
        f'alternating ambient boundary sample {index} failed downstream, geometry, or C+ compatibility ordering',
      )
    outer.append(next_outer)
    outer_pressures.append(resolved_centerline_pressures[index])
    previous_axis = axis_state
    previous_outer = next_outer

  ambient_boundary = validate_ambient_pressure_boundary(
    tuple(
      MocAmbientBoundarySample(
        point_m=(state.x_m, state.y_m),
        state=state,
        total_pressure_Pa=pressure,
      )
      for state, pressure in zip(outer, outer_pressures, strict=True)
    ),
    ambient_pressure,
    position_tolerance_m=resolved_position_tolerance,
    pressure_tolerance=resolved_pressure_tolerance,
    tangent_tolerance=resolved_pressure_tolerance,
  )
  if not ambient_boundary.converged:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.BOUNDARY_FAILURE,
      f'alternating outer curve failed independent ambient acceptance: {ambient_boundary.message}',
    )

  for index in range(source_sample_count - 1):
    try:
      cells.extend((
        MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind='alternating-axis-step',
          vertices_xr_m=(
            (centerline[index].x_m, centerline[index].y_m),
            (centerline[index + 1].x_m, centerline[index + 1].y_m),
            (outer[index].x_m, outer[index].y_m),
          ),
          centerline_indices=(index, index + 1),
          boundary_indices=(index,),
        ),
        MocCharacteristicCell(
          cell_index=len(cells) + 1,
          cell_kind='alternating-boundary-step',
          vertices_xr_m=(
            (centerline[index + 1].x_m, centerline[index + 1].y_m),
            (outer[index + 1].x_m, outer[index + 1].y_m),
            (outer[index].x_m, outer[index].y_m),
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        ),
      ))
    except (TypeError, ValueError) as error:
      return failure(
        MocReflectedDomainAlternatingSourceStatus.FIELD_FAILURE,
        f'alternating characteristic cell {index} could not be assembled: {error}',
      )
  topology = validate_moc_mesh(cells)
  if (
    not topology.connected
    or not topology.forms_closed_zone
    or topology.nonmanifold_edge_count
  ):
    return failure(
      MocReflectedDomainAlternatingSourceStatus.FIELD_FAILURE,
      f'alternating source-band topology failed: {topology.message}',
    )
  alternating_seam_verified = bool(
    all(result.converged for result in centerline_results)
    and all(result.converged for result in point_results)
    and all(
      abs(axis.k_minus - previous.k_minus) <= resolved_invariant_tolerance
      for axis, previous in zip(centerline[1:], outer[:-1], strict=True)
    )
    and all(
      abs(boundary.k_plus - axis.k_plus) <= resolved_invariant_tolerance
      for axis, boundary in zip(centerline, outer, strict=True)
    )
  )
  if not alternating_seam_verified:
    return failure(
      MocReflectedDomainAlternatingSourceStatus.FIELD_FAILURE,
      'alternating source band did not retain every solved C-/C+ neighboring seam',
    )
  return MocReflectedDomainAlternatingSourceResult(
    status=MocReflectedDomainAlternatingSourceStatus.CONVERGED,
    reflection_patch=patch,
    centerline_source_states=tuple(centerline),
    outer_source_states=tuple(outer),
    centerline_total_pressure_Pa=tuple(centerline_pressures),
    outer_total_pressure_Pa=tuple(outer_pressures),
    outer_seed_state=resolved_seed,
    outer_seed_total_pressure_Pa=seed_pressure,
    ambient_pressure_Pa=ambient_pressure,
    incoming_trace_validation=incoming_validation,
    incoming_trace_polarity=incoming_polarity,
    centerline_results=tuple(centerline_results),
    point_results=tuple(point_results),
    ambient_boundary=ambient_boundary,
    cells=tuple(cells),
    topology=topology,
    reflection_anchor_verified=reflection_anchor_verified,
    alternating_seam_verified=alternating_seam_verified,
    message=(
      'alternating C-/C+ ambient-pressure source band converged as a bounded '
      'research remesh; shock entropy, mixed-regime closure, and promotion remain pending'
    ),
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_theta,
    position_tolerance_m=resolved_position_tolerance,
    trace_forward_tolerance_m=resolved_trace_forward_tolerance,
    invariant_tolerance=resolved_invariant_tolerance,
    pressure_tolerance=resolved_pressure_tolerance,
    incoming_handoff=resolved_incoming_handoff,
  )
####


def solve_reflected_domain_alternating_physical_field(
  source_band: MocReflectedDomainAlternatingSourceResult,
  compression_amplitude_rad: float,
  *,
  outer_source_index: int = 0,
  use_outer_seed_attachment: bool = False,
  use_trace_referenced_profile: bool = False,
  compression_envelope_skew: float = 0.0,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  attachment_angle_half_width_rad: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
) -> MocReflectedDomainAlternatingPhysicalFieldResult:
  """Couple an alternating source band to one ambient-closed shock field.

  The default first outer source point is an ambient-pressure point, so the
  physical shock starts as an explicit zero-strength Mach-wave attachment.
  ``use_outer_seed_attachment`` instead starts at the retained outgoing trace
  seed from the prior reflected patch.  That opt-in mode is the exact
  reflected-interface seam needed by a continued chain; the source sampler
  remains bounded because it can use the retained patch but never
  extrapolates beyond it or the alternating source cells.  Interior shock
  turns are obtained from the sampled alternating upstream state plus a
  non-negative ``4*s*(1-s)`` compression envelope.  The envelope is a
  bounded research boundary condition: it makes entropy production explicit
  and prevents the fast source band from being silently promoted as a
  canonical reflected-plume shock law.

  ``use_trace_referenced_profile`` is a separate, explicit research option.
  When enabled with ``use_outer_seed_attachment``, the exact reflected
  outgoing trace supplies the profile baseline.  It is kept separate from
  ordinary seed attachment because a profile can close one sampled field
  while still producing a terminal trace that is not suitable for the next
  remesh at that resolution.

  ``compression_envelope_skew`` shifts the bounded interior compression
  toward the start or end of the globally remeshed shock.  The range
  ``[-1, 1]`` preserves a non-negative envelope and zero-strength endpoints;
  it is a shape-control research parameter, not a derived Euler boundary
  condition.

  The source callbacks remain bounded by ``source_band``.  If a candidate
  shock leaves that finite source domain, the underlying physical solver
  returns a typed upstream-field failure; no extrapolated state is inserted.
  """

  continuation_law = 'alternating-source-local-compression-envelope'
  compression_profile: MocReflectedTraceCompressionProfile | None = None
  band = (
    source_band
    if isinstance(source_band, MocReflectedDomainAlternatingSourceResult)
    else None
  )
  try:
    amplitude = float(compression_amplitude_rad)
  except (TypeError, ValueError):
    amplitude = float('nan')
  try:
    envelope_skew = float(compression_envelope_skew)
  except (TypeError, ValueError):
    envelope_skew = float('nan')
  try:
    target_y = float(target_centerline_y_m)
    target_theta = float(target_centerline_flow_angle_rad)
    half_width = float(attachment_angle_half_width_rad)
  except (TypeError, ValueError):
    target_y = float('nan')
    target_theta = float('nan')
    half_width = float('nan')
  resolved_sample_count = (
    sample_count
    if isinstance(sample_count, int)
    and not isinstance(sample_count, bool)
    and sample_count >= 0
    else 0
  )
  resolved_outer_index = (
    outer_source_index
    if isinstance(outer_source_index, int)
    and not isinstance(outer_source_index, bool)
    and outer_source_index >= 0
    else None
  )
  resolved_seed_attachment = (
    use_outer_seed_attachment
    if isinstance(use_outer_seed_attachment, bool)
    else False
  )
  resolved_trace_profile = (
    use_trace_referenced_profile
    if isinstance(use_trace_referenced_profile, bool)
    else False
  )
  resolved_envelope_skew = envelope_skew
  attachment_source = (
    'outer-seed-reflection-interface'
    if resolved_seed_attachment
    else 'alternating-outer-source-row'
  )
  if resolved_trace_profile:
    continuation_law = 'reflected-trace-referenced-compression-envelope'
  elif abs(resolved_envelope_skew) > 0.0:
    continuation_law = 'alternating-source-skewed-compression-envelope'
  else:
    continuation_law = 'alternating-source-local-compression-envelope'
  resolved_incoming_handoff: tuple[MocChainBoundarySample, ...] = ()
  incoming_handoff_error = False
  if incoming_handoff is not None:
    try:
      resolved_incoming_handoff = tuple(incoming_handoff)
    except TypeError:
      incoming_handoff_error = True
    else:
      incoming_handoff_error = any(
        not isinstance(sample, MocChainBoundarySample)
        for sample in resolved_incoming_handoff
      )
  resolved_position_tolerance = 1.0e-9
  resolved_shock_angle_tolerance = 1.0e-2
  try:
    resolved_position_tolerance = float(position_tolerance_m)
    resolved_shock_angle_tolerance = float(shock_angle_tolerance_rad)
  except (TypeError, ValueError):
    pass
  if (
    not isfinite(resolved_position_tolerance)
    or resolved_position_tolerance <= 0.0
  ):
    resolved_position_tolerance = 1.0e-9
  bracket: tuple[float, float] | None = None
  start_point: tuple[float, float] | None = None

  def failure(
    status: MocReflectedDomainAlternatingPhysicalFieldStatus,
    message: str,
    *,
    field_result: MocAmbientPhysicalFieldResult | None = None,
  ) -> MocReflectedDomainAlternatingPhysicalFieldResult:
    return MocReflectedDomainAlternatingPhysicalFieldResult(
      status=status,
      source_band=band,
      field_result=field_result,
      start_point_m=start_point,
      outer_source_index=resolved_outer_index,
      compression_amplitude_rad=(
        amplitude if isfinite(amplitude) and amplitude > 0.0 else None
      ),
      sample_count=resolved_sample_count,
      outer_flow_angle_bracket=bracket,
      incoming_handoff=resolved_incoming_handoff,
      continuation_law=continuation_law,
      attachment_source=attachment_source,
      use_trace_referenced_profile=resolved_trace_profile,
      compression_envelope_skew=(
        resolved_envelope_skew
        if isfinite(resolved_envelope_skew)
        else 0.0
      ),
      position_tolerance_m=resolved_position_tolerance,
      shock_angle_tolerance_rad=(
        resolved_shock_angle_tolerance
        if isfinite(resolved_shock_angle_tolerance)
        and resolved_shock_angle_tolerance > 0.0
        else 1.0e-2
      ),
      message=message,
    )

  if band is None:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'source_band must be a MocReflectedDomainAlternatingSourceResult',
    )
  if incoming_handoff_error:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'incoming_handoff must contain MocChainBoundarySample values',
    )
  if not isinstance(use_outer_seed_attachment, bool):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'use_outer_seed_attachment must be a bool',
    )
  if not isinstance(use_trace_referenced_profile, bool):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'use_trace_referenced_profile must be a bool',
    )
  if (
    not isfinite(resolved_envelope_skew)
    or abs(resolved_envelope_skew) > 1.0
  ):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'compression_envelope_skew must be finite and within [-1, 1]',
    )
  if resolved_trace_profile and not resolved_seed_attachment:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'use_trace_referenced_profile requires use_outer_seed_attachment',
    )
  if not band.source_field_verified:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
      'alternating source band is not a verified bounded source field',
    )
  if (
    not isfinite(amplitude)
    or amplitude <= 0.0
    or not isfinite(target_y)
    or not isfinite(target_theta)
    or not isfinite(half_width)
    or half_width <= 0.0
  ):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'compression amplitude, centerline target, and attachment bracket must be finite and valid',
    )
  if (
    abs(target_y) > resolved_position_tolerance
    or abs(target_theta) > float(tangent_tolerance)
  ):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'alternating physical coupling currently supports only y=0, theta=0 symmetry closure',
    )
  if (
    not isinstance(resolved_outer_index, int)
    or resolved_outer_index >= len(band.outer_source_states)
  ):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'outer_source_index must select a state in the alternating outer source row',
    )
  if resolved_sample_count < 3:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'sample_count must be an integer of at least three',
    )
  if not isinstance(branch, ShockBranch):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('attachment_pressure_tolerance', attachment_pressure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    try:
      numeric_value = float(value)
    except (TypeError, ValueError):
      numeric_value = float('nan')
    if not isfinite(numeric_value) or numeric_value <= 0.0:
      return failure(
        MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
        f'{name} must be finite and positive',
      )
  for name, value in (
    ('maximum_segment_iterations', maximum_segment_iterations),
    ('maximum_boundary_iterations', maximum_boundary_iterations),
    ('maximum_shooting_iterations', maximum_shooting_iterations),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      return failure(
        MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT,
        f'{name} must be a positive integer',
      )
  ambient_pressure = band.ambient_pressure_Pa
  if ambient_pressure is None or not isfinite(float(ambient_pressure)) or ambient_pressure <= 0.0:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
      'alternating source band does not retain a finite ambient pressure',
    )
  source_state = (
    band.outer_seed_state
    if resolved_seed_attachment
    else band.outer_source_states[resolved_outer_index]
  )
  if source_state is None:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
      'alternating source band does not retain an outer seed attachment state',
    )
  if resolved_seed_attachment and resolved_trace_profile:
    if band.reflection_patch is None:
      return failure(
        MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
        'outer-seed attachment requires the exact reflected trace source',
      )
    try:
      compression_profile = build_reflected_trace_compression_profile(
        band.reflection_patch.outgoing_trace_samples,
        amplitude,
        target_centerline_y_m=target_y,
        target_centerline_flow_angle_rad=target_theta,
        envelope_skew=resolved_envelope_skew,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return failure(
        MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
        f'outer-seed reflected trace compression profile is invalid: {error}',
      )
    if not _state_matches(
      source_state,
      compression_profile.source_trace[0].state,
      position_tolerance_m=float(position_tolerance_m),
      state_tolerance=float(invariant_tolerance),
    ):
      return failure(
        MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
        'outer-seed attachment state does not match the exact reflected trace start',
      )
    continuation_law = compression_profile.model
  start_point = (source_state.x_m, source_state.y_m)
  bracket = (
    source_state.theta_rad - half_width,
    source_state.theta_rad + half_width,
  )
  sampled_start = band.state_at(
    start_point,
    position_tolerance_m=float(position_tolerance_m),
  )
  start_pressure = band.static_pressure_at(
    start_point,
    position_tolerance_m=float(position_tolerance_m),
  )
  if (
    sampled_start is None
    or not _state_matches(
      sampled_start,
      source_state,
      position_tolerance_m=float(position_tolerance_m),
      state_tolerance=float(invariant_tolerance),
    )
    or start_pressure is None
    or not isfinite(float(start_pressure))
    or abs(float(start_pressure) - float(ambient_pressure)) / float(ambient_pressure)
    > float(pressure_tolerance)
  ):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
      'alternating source attachment point does not reproduce its ambient-matched state and pressure',
    )
  denominator = source_state.y_m - target_y
  if denominator <= float(position_tolerance_m):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE,
      'alternating source attachment point must lie above the target centerline',
    )

  def downstream_flow_angle_at(
    index: int,
    point_m: tuple[float, float],
  ) -> float:
    if compression_profile is not None:
      return compression_profile.flow_angle_at(index, point_m)
    ordinate = float(point_m[1])
    fraction = (ordinate - target_y) / denominator
    if fraction < -1.0e-8 or fraction > 1.0 + 1.0e-8:
      raise ValueError(
        'alternating physical shock point lies outside the bounded source ordinate'
      )
    fraction = max(0.0, min(1.0, fraction))
    if abs(ordinate - target_y) <= max(
      float(position_tolerance_m),
      float(invariant_tolerance),
    ):
      return target_theta
    state = band.state_at(
      point_m,
      position_tolerance_m=float(position_tolerance_m),
    )
    if state is None:
      raise ValueError(
        'alternating physical shock point is outside the bounded source band'
      )
    envelope = 4.0 * fraction * (1.0 - fraction)
    envelope *= 1.0 + resolved_envelope_skew * (2.0 * fraction - 1.0)
    return float(state.theta_rad + amplitude * envelope)

  try:
    from exhaust_plume.models.moc.coupled import (
      MocAmbientPhysicalFieldResult,
      solve_marched_attached_shock_with_ambient_centerline_physical_field,
    )

    field_result = solve_marched_attached_shock_with_ambient_centerline_physical_field(
      band.state_at,
      band.static_pressure_at,
      start_point,
      float(ambient_pressure),
      bracket[0],
      bracket[1],
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      sample_count=resolved_sample_count,
      branch=branch,
      position_tolerance_m=float(position_tolerance_m),
      invariant_tolerance=float(invariant_tolerance),
      attachment_pressure_tolerance=float(attachment_pressure_tolerance),
      pressure_tolerance=float(pressure_tolerance),
      tangent_tolerance=float(tangent_tolerance),
      shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      incoming_handoff=(
        resolved_incoming_handoff if resolved_incoming_handoff else None
      ),
      allow_zero_strength_attachment=True,
      zero_strength_start_trace=(
        band.reflection_patch.outgoing_trace_samples
        if resolved_seed_attachment and band.reflection_patch is not None
        else None
      ),
      allow_zero_strength_endpoints=True,
      downstream_flow_angle_at=downstream_flow_angle_at,
      continuation_law=continuation_law,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SHOCK_FAILURE,
      f'alternating source physical shock solve raised: {error}',
    )
  if not isinstance(field_result, MocAmbientPhysicalFieldResult):
    return failure(
      MocReflectedDomainAlternatingPhysicalFieldStatus.SHOCK_FAILURE,
      'alternating source physical shock solve returned an invalid field result',
    )
  if (
    field_result.converged
    and field_result.physical_closure_verified
    and field_result.state_sampling_available
    and field_result.upstream_coupling_verified
  ):
    return MocReflectedDomainAlternatingPhysicalFieldResult(
      status=MocReflectedDomainAlternatingPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      source_band=band,
      field_result=field_result,
      start_point_m=start_point,
      outer_source_index=resolved_outer_index,
      compression_amplitude_rad=amplitude,
      sample_count=resolved_sample_count,
      outer_flow_angle_bracket=bracket,
      incoming_handoff=resolved_incoming_handoff,
      continuation_law=continuation_law,
      attachment_source=attachment_source,
      use_trace_referenced_profile=resolved_trace_profile,
      compression_envelope_skew=resolved_envelope_skew,
      position_tolerance_m=float(position_tolerance_m),
      shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
      message=(
        'alternating source band coupled to a state-carrying ambient-closed '
        'shock field through an explicit local compression envelope; canonical '
        'reflected free-boundary validation remains pending'
      ),
    )
  return failure(
    MocReflectedDomainAlternatingPhysicalFieldStatus.FIELD_FAILURE,
    f'alternating source physical field did not pass closure gates: {field_result.message}',
    field_result=field_result,
  )
####


def solve_reflected_domain_solver_owned_first_cell(
  source_band: MocReflectedDomainAlternatingSourceResult,
  *,
  outer_source_index: int = 0,
  target_centerline_index: int | None = None,
  compression_amplitude_lower_rad: float = 0.005,
  compression_amplitude_upper_rad: float = 0.05,
  closure_tolerance_m: float = 1.0e-6,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  compression_envelope_skew: float = 0.0,
) -> MocReflectedDomainSolverOwnedFirstCellResult:
  """Iterate a solver-generated first-cell endpoint without shock geometry.

  The alternating source band owns both the candidate outer source row and the
  next centerline source row.  For one selected outer source point, this
  routine generates a physical shock field for each compression amplitude and
  adjusts that amplitude until the shock endpoint aligns with the next
  solver-generated centerline source point.  The endpoint target is therefore
  a local characteristic-interface condition, not a caller-prescribed shock
  curve.

  The compression family is intentionally explicit and local.  It is a
  research free-boundary reference, not the canonical reflected Euler solve:
  the upstream alternating remesh, local compression envelope, mixed-regime
  continuation, refinement, and external validation remain separate gates.
  When ``maximum_bracket_scan_samples`` is positive, the solver samples only
  interior amplitudes inside the caller's bracket before deciding that the
  endpoint residual has no sign change.  It may use two adjacent complete
  trials as a new bisection bracket, but it never bridges an invalid trial or
  extrapolates outside the declared amplitude interval.  Every failed or
  successful trial is retained, and a missing field is never replaced with an
  extrapolated state.

  ``compression_envelope_skew`` is held fixed during this scalar shoot.  A
  separate global remesh may sweep it across ``[-1, 1]``; keeping it fixed
  here makes each amplitude bracket a single, auditable family.
  """

  resolved_target_index: int | None = None

  def failure(
    status: MocReflectedDomainSolverOwnedFirstCellStatus,
    message: str,
    *,
    target_point: tuple[float, float] | None = None,
    bracket: tuple[float, float] | None = None,
    selected_index: int | None = None,
    selected_amplitude: float | None = None,
    selected_field: MocReflectedDomainAlternatingPhysicalFieldResult | None = None,
    residual: float | None = None,
    iterations: int = 0,
    trials: Sequence[MocReflectedDomainSolverOwnedFirstCellTrial] = (),
    bracket_scan_sample_count: int = 0,
    envelope_skew: float = 0.0,
  ) -> MocReflectedDomainSolverOwnedFirstCellResult:
    return MocReflectedDomainSolverOwnedFirstCellResult(
      status=status,
      source_band=(
        source_band
        if isinstance(source_band, MocReflectedDomainAlternatingSourceResult)
        else None
      ),
      outer_source_index=(
        outer_source_index
        if isinstance(outer_source_index, int)
        and not isinstance(outer_source_index, bool)
        and outer_source_index >= 0
        else None
      ),
      target_centerline_index=(
        resolved_target_index
        if isinstance(resolved_target_index, int)
        and not isinstance(resolved_target_index, bool)
        and resolved_target_index >= 0
        else None
      ),
      target_centerline_point_m=target_point,
      compression_amplitude_bracket=bracket,
      selected_trial_index=selected_index,
      selected_compression_amplitude_rad=selected_amplitude,
      selected_physical_field=selected_field,
      closure_residual_m=residual,
      shooting_iterations=iterations,
      trials=tuple(trials),
      bracket_scan_sample_count=bracket_scan_sample_count,
      compression_envelope_skew=envelope_skew,
      message=message,
    )

  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'source_band must be a MocReflectedDomainAlternatingSourceResult',
    )
  if (
    isinstance(outer_source_index, bool)
    or not isinstance(outer_source_index, int)
    or outer_source_index < 0
    or outer_source_index >= len(source_band.outer_source_states)
  ):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'outer_source_index must select a generated outer source state',
    )
  resolved_target_index = (
    outer_source_index + 1
    if target_centerline_index is None
    else target_centerline_index
  )
  if (
    isinstance(resolved_target_index, bool)
    or not isinstance(resolved_target_index, int)
    or resolved_target_index < 0
    or resolved_target_index >= len(source_band.centerline_source_states)
  ):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'target_centerline_index must select a generated centerline source state',
    )
  try:
    lower_amplitude = float(compression_amplitude_lower_rad)
    upper_amplitude = float(compression_amplitude_upper_rad)
    closure_tolerance = float(closure_tolerance_m)
    resolved_position_tolerance = float(position_tolerance_m)
    resolved_invariant_tolerance = float(invariant_tolerance)
    resolved_attachment_pressure_tolerance = float(attachment_pressure_tolerance)
    resolved_pressure_tolerance = float(pressure_tolerance)
    resolved_tangent_tolerance = float(tangent_tolerance)
    resolved_shock_angle_tolerance = float(shock_angle_tolerance_rad)
    resolved_envelope_skew = float(compression_envelope_skew)
  except (TypeError, ValueError):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'solver-owned first-cell tolerances and amplitude bounds must be numeric',
    )
  if (
    not all(
      isfinite(value) and value > 0.0
      for value in (
        lower_amplitude,
        upper_amplitude,
        closure_tolerance,
        resolved_position_tolerance,
        resolved_invariant_tolerance,
        resolved_attachment_pressure_tolerance,
        resolved_pressure_tolerance,
      resolved_tangent_tolerance,
      resolved_shock_angle_tolerance,
      )
    )
    or lower_amplitude >= upper_amplitude
  ):
    invalid_bracket = (
      (lower_amplitude, upper_amplitude)
      if all(
        isfinite(value) and value > 0.0
        for value in (lower_amplitude, upper_amplitude)
      )
      and lower_amplitude < upper_amplitude
      else None
    )
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'amplitude bounds and solver tolerances must be finite, positive, and ordered',
      bracket=invalid_bracket,
      envelope_skew=resolved_envelope_skew,
    )
  if not isfinite(resolved_envelope_skew) or abs(resolved_envelope_skew) > 1.0:
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'compression_envelope_skew must be finite and within [-1, 1]',
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'sample_count must be an integer of at least three',
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )
  for name, value in (
    ('maximum_segment_iterations', maximum_segment_iterations),
    ('maximum_boundary_iterations', maximum_boundary_iterations),
    ('maximum_shooting_iterations', maximum_shooting_iterations),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      return failure(
        MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
        f'{name} must be a positive integer',
        bracket=(lower_amplitude, upper_amplitude),
        envelope_skew=resolved_envelope_skew,
      )
  if (
    isinstance(maximum_bracket_scan_samples, bool)
    or not isinstance(maximum_bracket_scan_samples, int)
    or maximum_bracket_scan_samples < 0
  ):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'maximum_bracket_scan_samples must be a nonnegative integer',
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )
  if not isinstance(branch, ShockBranch):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )
  if not source_band.source_field_verified:
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.SOURCE_FIELD_FAILURE,
      'solver-owned first-cell iteration requires a verified bounded source band',
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )
  resolved_handoff = source_band.incoming_handoff
  if incoming_handoff is not None:
    try:
      resolved_handoff = tuple(incoming_handoff)
    except TypeError:
      return failure(
        MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
        'incoming_handoff must be an iterable of MocChainBoundarySample values',
        bracket=(lower_amplitude, upper_amplitude),
        envelope_skew=resolved_envelope_skew,
      )
    if any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in resolved_handoff
    ):
      return failure(
        MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
        'incoming_handoff must contain MocChainBoundarySample values',
        bracket=(lower_amplitude, upper_amplitude),
        envelope_skew=resolved_envelope_skew,
      )
  if resolved_handoff != source_band.incoming_handoff:
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT,
      'incoming_handoff must exactly match the source band handoff',
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )
  source_state = source_band.outer_source_states[outer_source_index]
  target_state = source_band.centerline_source_states[resolved_target_index]
  target_point = (target_state.x_m, target_state.y_m)
  if (
    abs(target_state.y_m - source_band.target_centerline_y_m)
    > resolved_position_tolerance
    or target_state.x_m <= source_state.x_m + resolved_position_tolerance
  ):
    return failure(
      MocReflectedDomainSolverOwnedFirstCellStatus.SOURCE_FIELD_FAILURE,
      'selected source and centerline states do not define a downstream endpoint',
      target_point=target_point,
      bracket=(lower_amplitude, upper_amplitude),
      envelope_skew=resolved_envelope_skew,
    )

  trials: list[MocReflectedDomainSolverOwnedFirstCellTrial] = []

  def evaluate(amplitude: float) -> MocReflectedDomainSolverOwnedFirstCellTrial:
    try:
      physical_field = solve_reflected_domain_alternating_physical_field(
        source_band,
        amplitude,
        outer_source_index=outer_source_index,
        use_outer_seed_attachment=False,
        target_centerline_y_m=source_band.target_centerline_y_m,
        target_centerline_flow_angle_rad=(
          source_band.target_centerline_flow_angle_rad
        ),
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=resolved_position_tolerance,
        invariant_tolerance=resolved_invariant_tolerance,
        attachment_pressure_tolerance=resolved_attachment_pressure_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
        tangent_tolerance=resolved_tangent_tolerance,
        shock_angle_tolerance_rad=resolved_shock_angle_tolerance,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        compression_envelope_skew=resolved_envelope_skew,
        incoming_handoff=resolved_handoff,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocReflectedDomainSolverOwnedFirstCellTrial(
        compression_amplitude_rad=amplitude,
        physical_field=None,
        endpoint_m=None,
        residual_m=None,
        message=f'physical-field trial raised: {error}',
      )
    endpoint = None
    residual = None
    if physical_field.field is not None and physical_field.field.shock_boundary_points_m:
      endpoint = physical_field.field.shock_boundary_points_m[-1]
      residual = endpoint[0] - target_point[0]
    if (
      residual is None
      or not physical_field.converged
      or not physical_field.physical_closure_verified
    ):
      return MocReflectedDomainSolverOwnedFirstCellTrial(
        compression_amplitude_rad=amplitude,
        physical_field=physical_field,
        endpoint_m=endpoint,
        residual_m=residual,
        message=(
          'physical-field trial did not produce a complete local field: '
          f'{physical_field.message}'
        ),
      )
    return MocReflectedDomainSolverOwnedFirstCellTrial(
      compression_amplitude_rad=amplitude,
      physical_field=physical_field,
      endpoint_m=endpoint,
      residual_m=residual,
      message='complete local physical field retained for endpoint iteration',
    )

  def best_trial_index() -> int | None:
    valid = tuple(
      (index, abs(trial.residual_m))
      for index, trial in enumerate(trials)
      if trial.residual_m is not None and trial.converged
    )
    return None if not valid else min(valid, key=lambda item: item[1])[0]

  def result_for(
    status: MocReflectedDomainSolverOwnedFirstCellStatus,
    message: str,
    iterations: int,
  ) -> MocReflectedDomainSolverOwnedFirstCellResult:
    selected_index = best_trial_index()
    selected_trial = (
      None if selected_index is None else trials[selected_index]
    )
    return failure(
      status,
      message,
      target_point=target_point,
      bracket=(lower_amplitude, upper_amplitude),
      selected_index=selected_index,
      selected_amplitude=(
        None
        if selected_trial is None
        else selected_trial.compression_amplitude_rad
      ),
      selected_field=(
        None if selected_trial is None else selected_trial.physical_field
      ),
      residual=(None if selected_trial is None else selected_trial.residual_m),
      iterations=iterations,
      trials=trials,
      bracket_scan_sample_count=maximum_bracket_scan_samples,
      envelope_skew=resolved_envelope_skew,
    )

  lower_trial = evaluate(lower_amplitude)
  trials.append(lower_trial)
  if (
    lower_trial.residual_m is not None
    and abs(lower_trial.residual_m) <= closure_tolerance
    and lower_trial.converged
  ):
    return result_for(
      MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT,
      'solver-owned first-cell endpoint aligned at the lower amplitude bound',
      0,
    )
  upper_trial = evaluate(upper_amplitude)
  trials.append(upper_trial)
  if (
    upper_trial.residual_m is not None
    and abs(upper_trial.residual_m) <= closure_tolerance
    and upper_trial.converged
  ):
    return result_for(
      MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT,
      'solver-owned first-cell endpoint aligned at the upper amplitude bound',
      0,
    )
  if lower_trial.residual_m is None or upper_trial.residual_m is None:
    return result_for(
      MocReflectedDomainSolverOwnedFirstCellStatus.FIELD_FAILURE,
      (
        'both compression-amplitude bracket endpoints must produce a complete '
        'local physical field: '
        f'lower={lower_trial.message}; upper={upper_trial.message}'
      ),
      0,
    )
  def find_adjacent_bracket() -> tuple[float, float, float, float] | None:
    ordered = tuple(
      sorted(trials, key=lambda trial: trial.compression_amplitude_rad)
    )
    for first, second in zip(ordered, ordered[1:]):
      if (
        not first.converged
        or not second.converged
        or first.residual_m is None
        or second.residual_m is None
      ):
        continue
      if first.residual_m * second.residual_m <= 0.0:
        return (
          first.compression_amplitude_rad,
          second.compression_amplitude_rad,
          first.residual_m,
          second.residual_m,
        )
    return None

  bracket = find_adjacent_bracket()
  if bracket is None and maximum_bracket_scan_samples:
    for scan_index in range(1, maximum_bracket_scan_samples + 1):
      amplitude = lower_amplitude + (
        upper_amplitude - lower_amplitude
      ) * scan_index / (maximum_bracket_scan_samples + 1)
      scan_trial = evaluate(amplitude)
      trials.append(scan_trial)
      if (
        scan_trial.residual_m is not None
        and scan_trial.converged
        and abs(scan_trial.residual_m) <= closure_tolerance
      ):
        return result_for(
          MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT,
          'solver-owned first-cell endpoint aligned at a bounded bracket-scan amplitude',
          0,
        )
      bracket = find_adjacent_bracket()
      if bracket is not None:
        break
  if bracket is None:
    return result_for(
      MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE,
      (
        'compression-amplitude bracket does not straddle the solver-owned '
        f'centerline endpoint residual after {maximum_bracket_scan_samples} '
        f'interior scan sample(s): lower={lower_trial.residual_m}, '
        f'upper={upper_trial.residual_m}'
      ),
      0,
    )

  current_lower, current_upper, current_lower_residual, _ = bracket
  completed_iterations = 0
  for iteration in range(1, maximum_shooting_iterations + 1):
    midpoint = 0.5 * (current_lower + current_upper)
    midpoint_trial = evaluate(midpoint)
    trials.append(midpoint_trial)
    completed_iterations = iteration
    if midpoint_trial.residual_m is None or not midpoint_trial.converged:
      return result_for(
        MocReflectedDomainSolverOwnedFirstCellStatus.SHOOTING_FAILURE,
        (
          'solver-owned endpoint iteration encountered an invalid midpoint '
          'and stopped without extrapolating the source field: '
          f'{midpoint_trial.message}'
        ),
        iteration,
      )
    if abs(midpoint_trial.residual_m) <= closure_tolerance:
      return result_for(
        MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT,
        'solver-owned first-cell endpoint aligned in the bounded amplitude shoot',
        iteration,
      )
    if current_lower_residual * midpoint_trial.residual_m <= 0.0:
      current_upper = midpoint
    else:
      current_lower = midpoint
      current_lower_residual = midpoint_trial.residual_m
  return result_for(
    MocReflectedDomainSolverOwnedFirstCellStatus.ITERATION_LIMIT,
    (
      'solver-owned first-cell endpoint iteration reached its amplitude '
      f'shoot limit after {completed_iterations} iterations'
    ),
    completed_iterations,
  )


def solve_reflected_domain_global_shock_remesh(
  source_band: MocReflectedDomainAlternatingSourceResult,
  *,
  outer_source_indices: Sequence[int] | None = None,
  target_centerline_indices: Sequence[int] | None = None,
  compression_amplitude_lower_rad: float = 0.005,
  compression_amplitude_upper_rad: float = 0.05,
  compression_envelope_skews: Sequence[float] = (-0.75, 0.0, 0.75),
  closure_tolerance_m: float = 1.0e-6,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  maximum_attempts: int = 64,
) -> MocReflectedDomainGlobalShockRemeshResult:
  """Sweep a bounded global shock-profile remesh over source interfaces.

  Each attempt delegates to
  :func:`solve_reflected_domain_solver_owned_first_cell` for one complete
  shock path.  The source-pair and skew sweeps are intentionally separate
  from the scalar amplitude shoot: an invalid field cannot be bridged by a
  neighboring trial, and a locally aligned endpoint still cannot become a
  canonical chain cell.  This is the next global-remesh seam, not the final
  reflected Euler/free-boundary solve.
  """

  def failure(
    status: MocReflectedDomainGlobalShockRemeshStatus,
    message: str,
    *,
    resolved_outer: Sequence[int] = (),
    resolved_target: Sequence[int] = (),
    resolved_skews: Sequence[float] = (),
    attempts: Sequence[MocReflectedDomainGlobalShockRemeshAttempt] = (),
    selected_index: int | None = None,
    selected_residual: float | None = None,
  ) -> MocReflectedDomainGlobalShockRemeshResult:
    return MocReflectedDomainGlobalShockRemeshResult(
      status=status,
      source_band=(
        source_band
        if isinstance(source_band, MocReflectedDomainAlternatingSourceResult)
        else None
      ),
      attempts=tuple(attempts),
      selected_attempt_index=selected_index,
      selected_residual_m=selected_residual,
      outer_source_indices=tuple(resolved_outer),
      target_centerline_indices=tuple(resolved_target),
      compression_envelope_skews=tuple(resolved_skews),
      message=message,
    )

  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'source_band must be a MocReflectedDomainAlternatingSourceResult',
    )
  if not source_band.source_field_verified:
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.SOURCE_FIELD_FAILURE,
      'global reflected-shock remesh requires a verified bounded source band',
    )
  if (
    isinstance(maximum_attempts, bool)
    or not isinstance(maximum_attempts, int)
    or maximum_attempts < 1
  ):
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'maximum_attempts must be a positive integer',
    )

  def resolve_indices(
    values: Sequence[int] | None,
    count: int,
    name: str,
  ) -> tuple[int, ...] | None:
    if values is None:
      return tuple(range(count))
    try:
      resolved = tuple(values)
    except TypeError:
      return None
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      or value >= count
      for value in resolved
    ):
      return None
    if len(set(resolved)) != len(resolved):
      return None
    return resolved

  resolved_outer = resolve_indices(
    outer_source_indices,
    len(source_band.outer_source_states),
    'outer_source_indices',
  )
  if resolved_outer is None or not resolved_outer:
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'outer_source_indices must contain unique in-range source indices',
    )
  explicit_targets = resolve_indices(
    target_centerline_indices,
    len(source_band.centerline_source_states),
    'target_centerline_indices',
  )
  if target_centerline_indices is not None and (
    explicit_targets is None or not explicit_targets
  ):
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'target_centerline_indices must contain unique in-range centerline indices',
      resolved_outer=resolved_outer,
    )
  try:
    resolved_skews = tuple(float(value) for value in compression_envelope_skews)
  except (TypeError, ValueError):
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'compression_envelope_skews must be an iterable of numeric values',
      resolved_outer=resolved_outer,
    )
  if not resolved_skews or any(
    not isfinite(value) or abs(value) > 1.0 for value in resolved_skews
  ):
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'compression_envelope_skews must contain values within [-1, 1]',
      resolved_outer=resolved_outer,
      resolved_skews=resolved_skews,
    )
  if len(set(resolved_skews)) != len(resolved_skews):
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'compression_envelope_skews must contain unique values',
      resolved_outer=resolved_outer,
      resolved_skews=resolved_skews,
    )
  target_pairs = (
    tuple(
      (outer_index, outer_index + 1)
      for outer_index in resolved_outer
      if outer_index + 1 < len(source_band.centerline_source_states)
    )
    if explicit_targets is None
    else tuple(
      (outer_index, target_index)
      for outer_index in resolved_outer
      for target_index in explicit_targets
    )
  )
  if not target_pairs:
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      'global remesh source pairs must contain at least one downstream centerline target',
      resolved_outer=resolved_outer,
      resolved_skews=resolved_skews,
    )
  attempt_count = len(target_pairs) * len(resolved_skews)
  if attempt_count > maximum_attempts:
    return failure(
      MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT,
      f'global remesh requests {attempt_count} attempts, exceeding maximum_attempts={maximum_attempts}',
      resolved_outer=resolved_outer,
      resolved_target=tuple(sorted({target for _, target in target_pairs})),
      resolved_skews=resolved_skews,
    )
  resolved_targets = tuple(sorted({target for _, target in target_pairs}))
  attempts: list[MocReflectedDomainGlobalShockRemeshAttempt] = []
  for outer_index, target_index in target_pairs:
    for skew in resolved_skews:
      first_cell = solve_reflected_domain_solver_owned_first_cell(
        source_band,
        outer_source_index=outer_index,
        target_centerline_index=target_index,
        compression_amplitude_lower_rad=compression_amplitude_lower_rad,
        compression_amplitude_upper_rad=compression_amplitude_upper_rad,
        closure_tolerance_m=closure_tolerance_m,
        incoming_handoff=incoming_handoff,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        attachment_pressure_tolerance=attachment_pressure_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        maximum_bracket_scan_samples=maximum_bracket_scan_samples,
        compression_envelope_skew=skew,
      )
      attempts.append(
        MocReflectedDomainGlobalShockRemeshAttempt(
          outer_source_index=outer_index,
          target_centerline_index=target_index,
          compression_envelope_skew=skew,
          first_cell_result=first_cell,
        )
      )

  valid_attempts = tuple(
    (index, attempt)
    for index, attempt in enumerate(attempts)
    if attempt.residual_m is not None
    and attempt.first_cell_result.status in (
      MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE,
      MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT,
    )
    and attempt.first_cell_result.local_physical_field_verified
  )
  complete_attempts = bool(attempts) and len(valid_attempts) == len(attempts)
  selected_index: int | None = None
  selected_residual: float | None = None
  if valid_attempts:
    selected_index, selected_attempt = min(
      valid_attempts,
      key=lambda item: abs(item[1].residual_m),
    )
    selected_residual = selected_attempt.residual_m
  converged_attempts = tuple(
    (index, attempt)
    for index, attempt in valid_attempts
    if attempt.converged
  )
  if converged_attempts and complete_attempts:
    selected_index, selected_attempt = min(
      converged_attempts,
      key=lambda item: abs(item[1].residual_m),
    )
    selected_residual = selected_attempt.residual_m
    status = MocReflectedDomainGlobalShockRemeshStatus.CONVERGED_ENDPOINT
    message = (
      'global reflected-shock remesh found a locally aligned endpoint in the '
      f'bounded source/profile sweep after {len(attempts)} attempt(s)'
    )
  elif valid_attempts and complete_attempts:
    status = MocReflectedDomainGlobalShockRemeshStatus.NO_ENDPOINT_CLOSURE
    message = (
      'global reflected-shock remesh retained bounded complete trials but no '
      f'endpoint root after {len(attempts)} attempt(s); no extrapolation or '
      'cross-family bracket was used'
    )
  else:
    status = MocReflectedDomainGlobalShockRemeshStatus.ATTEMPT_FAILURE
    message = (
      'global reflected-shock remesh produced no complete bounded trial; '
      'the retained typed first-cell outcomes identify the limiting source '
      'or characteristic-field seam'
    )
  return failure(
    status,
    message,
    resolved_outer=resolved_outer,
    resolved_target=resolved_targets,
    resolved_skews=resolved_skews,
    attempts=attempts,
    selected_index=selected_index,
    selected_residual=selected_residual,
  )


def solve_reflected_domain_outer_source_curve(
  centerline_source_states: Sequence[CharacteristicState],
  previous_boundary_state: CharacteristicState,
  ambient_pressure_Pa: float,
  total_pressure_Pa: float,
  *,
  centerline_total_pressure_Pa: Sequence[float] = (),
  previous_boundary_total_pressure_Pa: float | None = None,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  position_tolerance_m: float = 1.0e-3,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  maximum_iterations: int = 16,
) -> MocReflectedDomainOuterSourceResult:
  """Generate and assemble an ambient-pressure outer source curve.

  ``centerline_source_states[0]`` is the reflection anchor and is not marched
  to the outer boundary.  ``previous_boundary_state`` seeds the first outer
  source sample; each subsequent centerline state supplies a ``C+`` incoming
  characteristic to :func:`solve_ambient_pressure_free_boundary_point`.
  Supplied centerline total-pressure values are carried to the generated
  outer samples.  When omitted, the scalar reference pressure is used for the
  complete row.

  This is a bounded source-domain solver.  It does not infer the source row
  from a shock, solve entropy production, or close/promote a downstream cell.
  """

  try:
    centerline = tuple(centerline_source_states)
  except TypeError:
    centerline = ()
  try:
    reference_pressure = float(total_pressure_Pa)
  except (TypeError, ValueError):
    reference_pressure = float('nan')
  try:
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    ambient_pressure = float('nan')
  try:
    target_y = float(target_centerline_y_m)
    target_theta = float(target_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    target_y = float('nan')
    target_theta = float('nan')
  try:
    supplied_pressures = tuple(
      float(value) for value in centerline_total_pressure_Pa
    )
  except (TypeError, ValueError):
    supplied_pressures = ()
    pressure_row_error = True
  else:
    pressure_row_error = False
  try:
    previous_pressure = (
      reference_pressure
      if previous_boundary_total_pressure_Pa is None
      else float(previous_boundary_total_pressure_Pa)
    )
  except (TypeError, ValueError):
    previous_pressure = float('nan')
  reported_target_y = target_y if isfinite(target_y) else 0.0
  reported_target_theta = target_theta if isfinite(target_theta) else 0.0
  try:
    reported_position_tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    reported_position_tolerance = 1.0e-3
  if not isfinite(reported_position_tolerance) or reported_position_tolerance <= 0.0:
    reported_position_tolerance = 1.0e-3
  try:
    reported_invariant_tolerance = float(invariant_tolerance)
  except (TypeError, ValueError):
    reported_invariant_tolerance = 1.0e-10
  if not isfinite(reported_invariant_tolerance) or reported_invariant_tolerance <= 0.0:
    reported_invariant_tolerance = 1.0e-10
  try:
    reported_pressure_tolerance = float(pressure_tolerance)
  except (TypeError, ValueError):
    reported_pressure_tolerance = 1.0e-8
  if not isfinite(reported_pressure_tolerance) or reported_pressure_tolerance <= 0.0:
    reported_pressure_tolerance = 1.0e-8
  def failure(
    status: MocReflectedDomainOuterSourceStatus,
    message: str,
    *,
    outer: Sequence[CharacteristicState] = (),
    outer_pressures: Sequence[float] = (),
    point_results: Sequence[MocFreeBoundaryPointResult] = (),
    ambient_boundary: MocAmbientPressureBoundaryResult | None = None,
    source_strip: MocSourceCharacteristicStripResult | None = None,
  ) -> MocReflectedDomainOuterSourceResult:
    return MocReflectedDomainOuterSourceResult(
      status=status,
      centerline_source_states=centerline,
      outer_source_states=tuple(outer),
      reference_total_pressure_Pa=(
        reference_pressure
        if isfinite(reference_pressure) and reference_pressure > 0.0
        else None
      ),
      centerline_total_pressure_Pa=(
        supplied_pressures if len(supplied_pressures) == len(centerline)
        else ()
      ),
      outer_total_pressure_Pa=tuple(outer_pressures),
      previous_boundary_state=(
        previous_boundary_state
        if isinstance(previous_boundary_state, CharacteristicState)
        else None
      ),
      previous_boundary_total_pressure_Pa=(
        previous_pressure
        if isfinite(previous_pressure) and previous_pressure > 0.0
        else None
      ),
      ambient_pressure_Pa=(
        ambient_pressure
        if isfinite(ambient_pressure) and ambient_pressure > 0.0
        else None
      ),
      point_results=tuple(point_results),
      ambient_boundary=ambient_boundary,
      source_strip=source_strip,
      message=message,
      target_centerline_y_m=reported_target_y,
      target_centerline_flow_angle_rad=reported_target_theta,
      position_tolerance_m=reported_position_tolerance,
      invariant_tolerance=reported_invariant_tolerance,
      pressure_tolerance=reported_pressure_tolerance,
    )

  if (
    len(centerline) < 3
    or any(not isinstance(state, CharacteristicState) for state in centerline)
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'centerline source row requires at least three CharacteristicState values',
    )
  if not isinstance(previous_boundary_state, CharacteristicState):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'previous_boundary_state must be a CharacteristicState',
    )
  if (
    not isfinite(reference_pressure)
    or reference_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or not isfinite(target_y)
    or not isfinite(target_theta)
    or pressure_row_error
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'pressures and centerline target coordinates must be finite and valid',
    )
  if len(supplied_pressures) not in (0, len(centerline)):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'centerline_total_pressure_Pa must match the centerline source row',
    )
  centerline_pressures = (
    (reference_pressure,) * len(centerline)
    if not supplied_pressures
    else supplied_pressures
  )
  if any(
    not isfinite(value) or value <= 0.0
    for value in centerline_pressures
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'centerline total-pressure values must be finite and positive',
    )
  if not isfinite(previous_pressure) or previous_pressure <= 0.0:
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'previous_boundary_total_pressure_Pa must be finite and positive',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not isfinite(float(pressure_tolerance)) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  gamma = centerline[0].gamma
  if (
    abs(previous_boundary_state.gamma - gamma) > invariant_tolerance
    or any(abs(state.gamma - gamma) > invariant_tolerance for state in centerline)
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'centerline and previous outer states must use one common gamma',
    )
  if any(
    abs(state.y_m - target_y) > position_tolerance_m
    or abs(state.theta_rad - target_theta) > invariant_tolerance
    for state in centerline
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'centerline source states must lie on the target centerline with its declared flow angle',
    )
  if any(
    next_state.x_m <= state.x_m + position_tolerance_m
    for state, next_state in zip(centerline, centerline[1:])
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.INVALID_INPUT,
      'centerline source states must progress strictly downstream',
    )
  if (
    previous_boundary_state.y_m <= target_y + position_tolerance_m
    or previous_boundary_state.x_m <= centerline[0].x_m + position_tolerance_m
  ):
    return failure(
      MocReflectedDomainOuterSourceStatus.SEED_FAILURE,
      'previous outer boundary seed must be above and downstream of the first centerline source',
    )
  seed_static_pressure = _static_pressure_from_total_pressure(
    previous_boundary_state,
    previous_pressure,
  )
  seed_pressure_residual = (
    seed_static_pressure - ambient_pressure
  ) / ambient_pressure
  if abs(seed_pressure_residual) > pressure_tolerance:
    return failure(
      MocReflectedDomainOuterSourceStatus.SEED_FAILURE,
      'previous outer boundary seed does not match ambient static pressure',
      outer=(previous_boundary_state,),
      outer_pressures=(previous_pressure,),
    )

  outer_states: list[CharacteristicState] = [previous_boundary_state]
  outer_pressures: list[float] = [previous_pressure]
  point_results: list[MocFreeBoundaryPointResult] = []
  for index in range(1, len(centerline)):
    result = solve_ambient_pressure_free_boundary_point(
      centerline[index],
      outer_states[-1],
      CharacteristicFamily.PLUS,
      total_pressure_Pa=centerline_pressures[index],
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    point_results.append(result)
    if not result.converged or result.state is None or result.point_m is None:
      return failure(
        MocReflectedDomainOuterSourceStatus.BOUNDARY_FAILURE,
        f'outer source boundary sample {index} failed: {result.message}',
        outer=outer_states,
        outer_pressures=outer_pressures,
        point_results=point_results,
      )
    if (
      result.point_m[0] <= outer_states[-1].x_m + position_tolerance_m
      or result.point_m[1] <= target_y + position_tolerance_m
    ):
      return failure(
        MocReflectedDomainOuterSourceStatus.BOUNDARY_FAILURE,
        f'outer source boundary sample {index} failed downstream/above-centerline ordering',
        outer=outer_states,
        outer_pressures=outer_pressures,
        point_results=point_results,
      )
    outer_states.append(result.state)
    outer_pressures.append(centerline_pressures[index])

  ambient_boundary = validate_ambient_pressure_boundary(
    tuple(
      MocAmbientBoundarySample(
        point_m=(state.x_m, state.y_m),
        state=state,
        total_pressure_Pa=pressure,
      )
      for state, pressure in zip(outer_states, outer_pressures, strict=True)
    ),
    ambient_pressure,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=pressure_tolerance,
  )
  if not ambient_boundary.converged:
    return failure(
      MocReflectedDomainOuterSourceStatus.BOUNDARY_FAILURE,
      f'generated outer source curve failed ambient acceptance: {ambient_boundary.message}',
      outer=outer_states,
      outer_pressures=outer_pressures,
      point_results=point_results,
      ambient_boundary=ambient_boundary,
    )
  source_strip = assemble_source_characteristic_strip_with_source_pressures(
    centerline,
    outer_states,
    centerline_pressures,
    outer_pressures,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if not source_strip.converged:
    return failure(
      MocReflectedDomainOuterSourceStatus.FIELD_FAILURE,
      f'generated outer source curve failed characteristic-strip assembly: {source_strip.message}',
      outer=outer_states,
      outer_pressures=outer_pressures,
      point_results=point_results,
      ambient_boundary=ambient_boundary,
      source_strip=source_strip,
    )
  return MocReflectedDomainOuterSourceResult(
    status=MocReflectedDomainOuterSourceStatus.CONVERGED,
    centerline_source_states=centerline,
    outer_source_states=tuple(outer_states),
    reference_total_pressure_Pa=reference_pressure,
    centerline_total_pressure_Pa=centerline_pressures,
    outer_total_pressure_Pa=tuple(outer_pressures),
    previous_boundary_state=previous_boundary_state,
    previous_boundary_total_pressure_Pa=previous_pressure,
    ambient_pressure_Pa=ambient_pressure,
    point_results=tuple(point_results),
    ambient_boundary=ambient_boundary,
    source_strip=source_strip,
    target_centerline_y_m=reported_target_y,
    target_centerline_flow_angle_rad=reported_target_theta,
    position_tolerance_m=reported_position_tolerance,
    invariant_tolerance=reported_invariant_tolerance,
    pressure_tolerance=reported_pressure_tolerance,
    message=(
      'ambient-pressure outer source curve and bounded characteristic strip '
      'converged; shock entropy, downstream closure, and chain promotion remain pending'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainRemeshRequest:
  """Cauchy data for one new reflected-domain source field.

  ``reflection_patch.outgoing_trace_samples`` is intentionally retained as a
  separate incoming characteristic.  It is not used as ``outer_source_states``
  because it is one invariant-preserving line, not a two-dimensional source
  curve.  The first centerline source state must be the exact state obtained
  when that incoming line reaches the target centerline.  The remaining
  centerline row and the outer source curve are the coupled remesher's inputs.

  The legacy scalar source-strip path uses one uniform total pressure.  The
  optional source-row pressure arrays preserve a nonuniform entropy lineage
  through the bounded remesh: a node receives the pressure carried by its
  ``C-`` source family.  Those arrays are explicit solver inputs; this request
  still does not infer shock loss or solve an ambient free boundary.
  """

  reflection_patch: MocTerminalReflectionPatchResult
  centerline_source_states: tuple[CharacteristicState, ...]
  outer_source_states: tuple[CharacteristicState, ...]
  total_pressure_Pa: float
  incoming_handoff: tuple[MocChainBoundarySample, ...] = ()
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  declared_polarity: MocReflectedTracePolarity | None = None
  position_tolerance_m: float = 1.0e-3
  trace_forward_tolerance_m: float = 1.0e-4
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  centerline_total_pressure_Pa: tuple[float, ...] = ()
  outer_total_pressure_Pa: tuple[float, ...] = ()

  def __post_init__(self) -> None:
    if not isinstance(
      self.reflection_patch,
      MocTerminalReflectionPatchResult,
    ):
      raise TypeError(
        'reflection_patch must be a MocTerminalReflectionPatchResult'
      )
    try:
      centerline = tuple(self.centerline_source_states)
      outer = tuple(self.outer_source_states)
      handoff = tuple(self.incoming_handoff)
    except TypeError as error:
      raise TypeError(
        'reflected-domain source rows and incoming_handoff must be iterable'
      ) from error
    if len(centerline) < 3 or len(outer) < 3:
      raise ValueError(
        'reflected-domain source rows require at least three samples'
      )
    if len(centerline) != len(outer):
      raise ValueError(
        'reflected-domain centerline and outer source rows must have equal lengths'
      )
    if any(
      not isinstance(state, CharacteristicState)
      for state in (*centerline, *outer)
    ):
      raise TypeError(
        'reflected-domain source rows must contain CharacteristicState values'
      )
    if any(
      not isinstance(sample, MocChainBoundarySample) for sample in handoff
    ):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    if handoff and len(handoff) < 3:
      raise ValueError(
        'incoming_handoff requires at least three samples when supplied'
      )
    pressure = float(self.total_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('total_pressure_Pa must be finite and positive')
    try:
      centerline_pressures = tuple(
        float(value) for value in self.centerline_total_pressure_Pa
      )
      outer_pressures = tuple(
        float(value) for value in self.outer_total_pressure_Pa
      )
    except (TypeError, ValueError) as error:
      raise ValueError(
        'source-row total pressures must contain finite positive values'
      ) from error
    if not centerline_pressures:
      centerline_pressures = (pressure,) * len(centerline)
    if not outer_pressures:
      outer_pressures = (pressure,) * len(outer)
    if len(centerline_pressures) != len(centerline):
      raise ValueError(
        'centerline_total_pressure_Pa must match centerline_source_states'
      )
    if len(outer_pressures) != len(outer):
      raise ValueError(
        'outer_total_pressure_Pa must match outer_source_states'
      )
    if any(
      not isfinite(value) or value <= 0.0
      for value in (*centerline_pressures, *outer_pressures)
    ):
      raise ValueError(
        'source-row total pressures must contain finite positive values'
      )
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'position_tolerance_m',
      'trace_forward_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or (
        value <= 0.0
        and name in (
          'position_tolerance_m',
          'trace_forward_tolerance_m',
          'invariant_tolerance',
          'pressure_tolerance',
        )
      ):
        raise ValueError(f'{name} must be finite and valid')
    if self.declared_polarity is not None and not isinstance(
      self.declared_polarity,
      MocReflectedTracePolarity,
    ):
      raise TypeError(
        'declared_polarity must be a MocReflectedTracePolarity or None'
      )
    object.__setattr__(self, 'centerline_source_states', centerline)
    object.__setattr__(self, 'outer_source_states', outer)
    object.__setattr__(self, 'incoming_handoff', handoff)
    object.__setattr__(self, 'total_pressure_Pa', pressure)
    object.__setattr__(
      self,
      'centerline_total_pressure_Pa',
      centerline_pressures,
    )
    object.__setattr__(self, 'outer_total_pressure_Pa', outer_pressures)
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'position_tolerance_m',
      'trace_forward_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      object.__setattr__(self, name, float(getattr(self, name)))
  ####

  @property
  def incoming_trace(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the exact prior patch front used at the reflection seam."""

    return self.reflection_patch.outgoing_trace_samples
  ####

  @property
  def incoming_anchor(self) -> MocChainBoundarySample:
    """Return the centerline endpoint of the prior reflected ``C-`` front."""

    return self.incoming_trace[-1]
  ####

  @property
  def source_model(self) -> str:
    return (
      'explicit-reflected-domain-variable-entropy-cauchy-remesh'
      if self.variable_total_pressure
      else 'explicit-reflected-domain-cauchy-remesh'
    )
  ####

  @property
  def variable_total_pressure(self) -> bool:
    """Whether source-family pressure differs from the legacy scalar value."""

    values = (
      *self.centerline_total_pressure_Pa,
      *self.outer_total_pressure_Pa,
    )
    return any(
      not _pressure_matches(value, self.total_pressure_Pa, self.pressure_tolerance)
      for value in values
    )
  ####

  def as_report(self) -> dict[str, object]:
    incoming = self.incoming_trace
    return {
      'source_model': self.source_model,
      'reflection_patch_status': self.reflection_patch.status.value,
      'incoming_trace_family': CharacteristicFamily.MINUS.value,
      'incoming_trace_kind': 'prior-single-c-minus-reflection-front',
      'incoming_trace_sample_count': len(incoming),
      'incoming_trace_start_m': incoming[0].point_m if incoming else None,
      'incoming_trace_end_m': incoming[-1].point_m if incoming else None,
      'incoming_anchor_state': (
        None
        if not incoming
        else {
          'theta_rad': self.incoming_anchor.state.theta_rad,
          'mach': self.incoming_anchor.state.mach,
          'gamma': self.incoming_anchor.state.gamma,
        }
      ),
      'centerline_source_family': CharacteristicFamily.PLUS.value,
      'centerline_source_count': len(self.centerline_source_states),
      'outer_source_family': CharacteristicFamily.MINUS.value,
      'outer_source_count': len(self.outer_source_states),
      'outer_source_is_new_curve': True,
      'incoming_trace_reused_as_outer_source': False,
      'total_pressure_Pa': self.total_pressure_Pa,
      'centerline_total_pressure_Pa': list(self.centerline_total_pressure_Pa),
      'outer_total_pressure_Pa': list(self.outer_total_pressure_Pa),
      'variable_total_pressure': self.variable_total_pressure,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'declared_polarity': (
        None if self.declared_polarity is None else self.declared_polarity.value
      ),
      'position_tolerance_m': self.position_tolerance_m,
      'trace_forward_tolerance_m': self.trace_forward_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'entropy_model': (
        'source-family-carried-total-pressure'
        if self.variable_total_pressure
        else 'single-uniform-total-pressure-source-strip'
      ),
      'nonuniform_entropy_data_carried': self.variable_total_pressure,
      'nonuniform_entropy_remesh_solved': False,
    }
  ####


def build_reflected_domain_remesh_request_from_outer_source(
  reflection_patch: MocTerminalReflectionPatchResult,
  outer_source: MocReflectedDomainOuterSourceResult,
  *,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
  declared_polarity: MocReflectedTracePolarity | None = None,
  total_pressure_Pa: float | None = None,
) -> MocReflectedDomainRemeshRequest:
  """Bind a solved outer source curve to a reflected-remesh request.

  The adapter copies the generated rows and pressure lineage exactly.  It
  performs no interpolation or fallback, and it still leaves the reflected
  remesh's shock, downstream closure, and promotion gates to
  :func:`solve_reflected_domain_remesh`.
  """

  if not isinstance(reflection_patch, MocTerminalReflectionPatchResult):
    raise TypeError(
      'reflection_patch must be a MocTerminalReflectionPatchResult'
    )
  if not isinstance(outer_source, MocReflectedDomainOuterSourceResult):
    raise TypeError(
      'outer_source must be a MocReflectedDomainOuterSourceResult'
    )
  if not outer_source.source_field_verified:
    raise ValueError(
      'outer_source must carry a converged ambient source curve and '
      'characteristic field'
    )
  reference_pressure = (
    outer_source.reference_total_pressure_Pa
    if total_pressure_Pa is None
    else float(total_pressure_Pa)
  )
  if reference_pressure is None:
    raise ValueError(
      'outer_source must retain a reference total pressure when one is not supplied'
    )
  if not isfinite(reference_pressure) or reference_pressure <= 0.0:
    raise ValueError('total_pressure_Pa must be finite and positive')
  return MocReflectedDomainRemeshRequest(
    reflection_patch=reflection_patch,
    centerline_source_states=outer_source.centerline_source_states,
    outer_source_states=outer_source.outer_source_states,
    total_pressure_Pa=reference_pressure,
    incoming_handoff=tuple(incoming_handoff),
    target_centerline_y_m=outer_source.target_centerline_y_m,
    target_centerline_flow_angle_rad=(
      outer_source.target_centerline_flow_angle_rad
    ),
    declared_polarity=declared_polarity,
    position_tolerance_m=outer_source.position_tolerance_m,
    invariant_tolerance=outer_source.invariant_tolerance,
    pressure_tolerance=outer_source.pressure_tolerance,
    centerline_total_pressure_Pa=outer_source.centerline_total_pressure_Pa,
    outer_total_pressure_Pa=outer_source.outer_total_pressure_Pa,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainRemeshResult:
  """A bounded source field with an audited reflected-family seam."""

  status: MocReflectedDomainRemeshStatus
  request: MocReflectedDomainRemeshRequest | None
  source_strip: MocSourceCharacteristicStripResult | None
  incoming_trace_validation: MocCharacteristicTraceResult | None
  incoming_trace_polarity: MocReflectedTracePolarityResult | None
  reflection_seam_verified: bool
  centerline_source_verified: bool
  outer_source_verified: bool
  source_field_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainRemeshStatus):
      raise TypeError('status must be a MocReflectedDomainRemeshStatus')
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainRemeshRequest,
    ):
      raise TypeError(
        'request must be a MocReflectedDomainRemeshRequest or None'
      )
    if self.source_strip is not None and not isinstance(
      self.source_strip,
      MocSourceCharacteristicStripResult,
    ):
      raise TypeError(
        'source_strip must be a MocSourceCharacteristicStripResult or None'
      )
    if self.incoming_trace_validation is not None and not isinstance(
      self.incoming_trace_validation,
      MocCharacteristicTraceResult,
    ):
      raise TypeError(
        'incoming_trace_validation must be a MocCharacteristicTraceResult or None'
      )
    if self.incoming_trace_polarity is not None and not isinstance(
      self.incoming_trace_polarity,
      MocReflectedTracePolarityResult,
    ):
      raise TypeError(
        'incoming_trace_polarity must be a MocReflectedTracePolarityResult or None'
      )
    for name in (
      'reflection_seam_verified',
      'centerline_source_verified',
      'outer_source_verified',
      'source_field_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(
      self.converged
      and self.source_field_verified
      and self.source_strip is not None
      and self.source_strip.converged
      and self.source_strip.topology.connected
      and self.source_strip.topology.forms_closed_zone
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The source remesh has no shock or downstream physical closure."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_source_continuation(self) -> MocSourceStripContinuationResult:
    """Adapt the bounded domain to the existing source-chain planner."""

    if not self.state_sampling_available or self.source_strip is None:
      raise ValueError(
        'a reflected-domain source continuation requires a converged bounded '
        'source field'
      )
    request = self.request
    assert request is not None
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.CONVERGED_EXTENDED,
      strip=self.source_strip,
      plus_source_states=request.centerline_source_states,
      minus_source_states=request.outer_source_states,
      added_sample_count=0,
      axis_step_m=None,
      continuation_k_plus=None,
      message=(
        'reflected-domain Cauchy remesh adapted to the bounded source-strip '
        'planner; shock and physical closure remain separate'
      ),
      full_strip=self.source_strip,
      continuation_law=request.source_model,
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the remesh gate to a non-physical planner stop."""

    if self.status is MocReflectedDomainRemeshStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocReflectedDomainRemeshStatus.INCOMING_TRACE_FAILURE,
      MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE,
      MocReflectedDomainRemeshStatus.CENTERLINE_SOURCE_FAILURE,
      MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE,
      MocReflectedDomainRemeshStatus.POLARITY_FAILURE,
    ):
      reason = MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    elif self.status is MocReflectedDomainRemeshStatus.FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'reflected-domain remesh is a bounded source field, not a '
        'promotable physical shock-cell closure'
      ),
      diagnostics={
        'termination_model': 'reflected-domain-cauchy-remesh',
        'remesh_status': self.status.value,
        'reflection_seam_verified': self.reflection_seam_verified,
        'centerline_source_verified': self.centerline_source_verified,
        'outer_source_verified': self.outer_source_verified,
        'source_field_verified': self.source_field_verified,
        'state_sampling_available': self.state_sampling_available,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'reflection_seam_verified': self.reflection_seam_verified,
      'centerline_source_verified': self.centerline_source_verified,
      'outer_source_verified': self.outer_source_verified,
      'source_field_verified': self.source_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'request': None if self.request is None else self.request.as_report(),
      'incoming_trace_validation': (
        None
        if self.incoming_trace_validation is None
        else self.incoming_trace_validation.as_report()
      ),
      'incoming_trace_polarity': (
        None
        if self.incoming_trace_polarity is None
        else self.incoming_trace_polarity.as_report()
      ),
      'source_strip': (
        None if self.source_strip is None else self.source_strip.as_report()
      ),
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
  ####


def _failure(
  status: MocReflectedDomainRemeshStatus,
  *,
  request: MocReflectedDomainRemeshRequest | None = None,
  incoming_trace_validation: MocCharacteristicTraceResult | None = None,
  incoming_trace_polarity: MocReflectedTracePolarityResult | None = None,
  source_strip: MocSourceCharacteristicStripResult | None = None,
  reflection_seam_verified: bool = False,
  centerline_source_verified: bool = False,
  outer_source_verified: bool = False,
  source_field_verified: bool = False,
  message: str,
) -> MocReflectedDomainRemeshResult:
  return MocReflectedDomainRemeshResult(
    status=status,
    request=request,
    source_strip=source_strip,
    incoming_trace_validation=incoming_trace_validation,
    incoming_trace_polarity=incoming_trace_polarity,
    reflection_seam_verified=reflection_seam_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    source_field_verified=source_field_verified,
    message=message,
  )


def solve_reflected_domain_remesh(
  request: MocReflectedDomainRemeshRequest,
) -> MocReflectedDomainRemeshResult:
  """Validate and assemble one explicit reflected-domain source patch.

  The incoming patch front is validated as a single ``C-`` characteristic.
  The first centerline source state must reproduce its exact centerline
  endpoint.  The new source rows then pass through the ordinary compatibility
  assembler, which is the gate that verifies every diagonal seam.  No source
  row is inferred from the old front and no extrapolation is used.
  """

  if not isinstance(request, MocReflectedDomainRemeshRequest):
    return _failure(
      MocReflectedDomainRemeshStatus.INVALID_INPUT,
      message='request must be a MocReflectedDomainRemeshRequest',
    )
  patch = request.reflection_patch
  if not patch.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.INVALID_INPUT,
      request=request,
      message='reflected-domain remesh requires a converged reflection patch',
    )
  incoming = request.incoming_trace
  incoming_validation = validate_characteristic_trace(
    incoming,
    CharacteristicFamily.MINUS,
    position_tolerance_m=request.position_tolerance_m,
    forward_position_tolerance_m=request.trace_forward_tolerance_m,
    invariant_tolerance=request.invariant_tolerance,
  )
  if not incoming_validation.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.INCOMING_TRACE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      message=f'incoming reflected C- trace failed: {incoming_validation.message}',
    )
  polarity = classify_reflected_trace_polarity(
    incoming,
    target_centerline_y_m=request.target_centerline_y_m,
    target_centerline_flow_angle_rad=request.target_centerline_flow_angle_rad,
    position_tolerance_m=request.position_tolerance_m,
    forward_position_tolerance_m=request.trace_forward_tolerance_m,
    invariant_tolerance=request.invariant_tolerance,
  )
  if not polarity.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.INCOMING_TRACE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      message=f'incoming reflected trace polarity failed: {polarity.message}',
    )
  if (
    request.declared_polarity is not None
    and request.declared_polarity is not polarity.status
  ):
    return _failure(
      MocReflectedDomainRemeshStatus.POLARITY_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      message=(
        'declared reflected trace polarity does not match the exact incoming '
        f'trace evidence: declared={request.declared_polarity.value}, '
        f'observed={polarity.status.value}'
      ),
    )

  anchor = request.incoming_anchor
  centerline = request.centerline_source_states
  first_centerline = centerline[0]
  reflection_seam_verified = bool(
    abs(anchor.state.y_m - request.target_centerline_y_m)
    <= request.position_tolerance_m
    and abs(anchor.state.theta_rad - request.target_centerline_flow_angle_rad)
    <= request.invariant_tolerance
    and _state_matches(
      first_centerline,
      anchor.state,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.invariant_tolerance,
    )
    and _pressure_matches(
      anchor.total_pressure_Pa,
      request.total_pressure_Pa,
      request.pressure_tolerance,
    )
  )
  if not reflection_seam_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      message=(
        'the first new centerline C+ source state must reproduce the exact '
        'incoming C- reflection endpoint and total pressure'
      ),
    )

  common_gamma = first_centerline.gamma
  centerline_source_verified = bool(
    all(
      abs(state.gamma - common_gamma) <= request.invariant_tolerance
      and abs(state.y_m - request.target_centerline_y_m)
      <= request.position_tolerance_m
      and abs(state.theta_rad - request.target_centerline_flow_angle_rad)
      <= request.invariant_tolerance
      for state in centerline
    )
    and _pressure_matches(
      request.centerline_total_pressure_Pa[0],
      anchor.total_pressure_Pa,
      request.pressure_tolerance,
    )
    and all(
      next_state.x_m > state.x_m + request.position_tolerance_m
      for state, next_state in zip(centerline, centerline[1:])
    )
  )
  if not centerline_source_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.CENTERLINE_SOURCE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      reflection_seam_verified=reflection_seam_verified,
      message=(
        'new centerline C+ source states must remain on the target centerline, '
        'match its flow angle, and progress strictly downstream'
      ),
    )

  outer = request.outer_source_states
  outer_source_verified = bool(
    all(
      abs(state.gamma - common_gamma) <= request.invariant_tolerance
      and state.y_m > request.target_centerline_y_m + request.position_tolerance_m
      for state in outer
    )
    and all(
      next_state.x_m > state.x_m + request.position_tolerance_m
      for state, next_state in zip(outer, outer[1:])
    )
    and outer[0].x_m > first_centerline.x_m + request.position_tolerance_m
    and max(state.k_minus for state in outer)
    - min(state.k_minus for state in outer)
    > request.invariant_tolerance
  )
  if not outer_source_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      message=(
        'new outer source data must be a downstream, above-centerline curve '
        'with varying C- invariant; the prior single C- front cannot be reused'
      ),
    )

  incoming_pressure_uniform = all(
    _pressure_matches(
      sample.total_pressure_Pa,
      request.total_pressure_Pa,
      request.pressure_tolerance,
    )
    for sample in incoming
  )
  if not incoming_pressure_uniform and not request.variable_total_pressure:
    return _failure(
      MocReflectedDomainRemeshStatus.FIELD_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      outer_source_verified=outer_source_verified,
      message=(
        'the uniform source-strip remesh requires one uniform total pressure; '
        'provide source-row pressure data for variable-entropy transport'
      ),
    )

  if request.variable_total_pressure:
    strip = assemble_source_characteristic_strip_with_source_pressures(
      centerline,
      outer,
      request.centerline_total_pressure_Pa,
      request.outer_total_pressure_Pa,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
    )
  else:
    strip = assemble_source_characteristic_strip(
      centerline,
      outer,
      request.total_pressure_Pa,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
    )
  if not strip.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.FIELD_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      source_strip=strip,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      outer_source_verified=outer_source_verified,
      message=f'reflected-domain source field failed: {strip.message}',
    )
  sampled_anchor = strip.state_at(
    (first_centerline.x_m, first_centerline.y_m),
    position_tolerance_m=request.position_tolerance_m,
  )
  sampled_static_pressure = strip.static_pressure_at(
    (first_centerline.x_m, first_centerline.y_m),
    position_tolerance_m=request.position_tolerance_m,
  )
  sampled_total_pressure = strip.total_pressure_at(
    (first_centerline.x_m, first_centerline.y_m),
    position_tolerance_m=request.position_tolerance_m,
  )
  source_field_verified = bool(
    isinstance(sampled_anchor, CharacteristicState)
    and _state_matches(
      sampled_anchor,
      anchor.state,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.invariant_tolerance,
    )
    and sampled_static_pressure is not None
    and isfinite(float(sampled_static_pressure))
    and sampled_static_pressure > 0.0
    and sampled_total_pressure is not None
    and isfinite(float(sampled_total_pressure))
    and sampled_total_pressure > 0.0
    and _pressure_matches(
      sampled_total_pressure,
      request.centerline_total_pressure_Pa[0],
      request.pressure_tolerance,
    )
  )
  if not source_field_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.FIELD_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      source_strip=strip,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      outer_source_verified=outer_source_verified,
      message=(
        'reflected-domain source field did not reproduce the exact reflection '
        'anchor state and total pressure'
      ),
    )
  return MocReflectedDomainRemeshResult(
    status=MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD,
    request=request,
    source_strip=strip,
    incoming_trace_validation=incoming_validation,
    incoming_trace_polarity=polarity,
    reflection_seam_verified=reflection_seam_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    source_field_verified=True,
    message=(
      'explicit reflected-domain Cauchy remesh converged as a bounded source '
      'field; shock-loss inference, ambient closure, and promotion remain '
      'separate gates'
    ),
  )
