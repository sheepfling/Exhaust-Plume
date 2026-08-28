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
from math import isfinite
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
  from exhaust_plume.models.moc.coupled import MocAmbientPhysicalFieldResult

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
  MocTerminalReflectionPatchResult,
  classify_reflected_trace_polarity,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocReflectedDomainOuterSourceStatus',
  'MocReflectedDomainOuterSourceResult',
  'MocReflectedDomainAlternatingSourceStatus',
  'MocReflectedDomainAlternatingSourceResult',
  'MocReflectedDomainAlternatingPhysicalFieldStatus',
  'MocReflectedDomainAlternatingPhysicalFieldResult',
  'MocReflectedDomainRemeshStatus',
  'MocReflectedDomainRemeshRequest',
  'MocReflectedDomainRemeshResult',
  'build_reflected_domain_remesh_request_from_outer_source',
  'solve_reflected_domain_alternating_source',
  'solve_reflected_domain_alternating_physical_field',
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
    return None
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Sample a state inside the bounded alternating band only."""

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
    """Sample carried total pressure inside the bounded band."""

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
    """Sample isentropic static pressure inside the bounded band."""

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
      'shock_sample_count': (
        None if shock is None else len(shock.shock_points_m)
      ),
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
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

  The first outer source point is an ambient-pressure point, so the physical
  shock starts as an explicit zero-strength Mach-wave attachment.  Interior
  shock turns are obtained from the sampled alternating upstream state plus a
  non-negative ``4*s*(1-s)`` compression envelope.  The envelope is a
  bounded research boundary condition: it makes entropy production explicit
  and prevents the fast source band from being silently promoted as a
  canonical reflected-plume shock law.

  The source callbacks remain bounded by ``source_band``.  If a candidate
  shock leaves that finite source domain, the underlying physical solver
  returns a typed upstream-field failure; no extrapolated state is inserted.
  """

  continuation_law = 'alternating-source-local-compression-envelope'
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
  source_state = band.outer_source_states[resolved_outer_index]
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
    _index: int,
    point_m: tuple[float, float],
  ) -> float:
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
