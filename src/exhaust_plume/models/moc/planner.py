"""Planning and audit wrappers for the isolated planar-MOC chain lane.

The chain solvers own numerical acceptance.  This module owns the lightweight
planner view used by validation and research orchestration: it records every
incoming handoff before a callback is invoked and preserves the solver's
typed termination decision.  The prescribed-boundary mode is an executable
mock only; it cannot raise a cell's fidelity or closure claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import Any, Callable

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainResult,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCellClosureStatus,
  MocCellContinuationSolver,
  MocChainGeometryFidelity,
  continue_moc_cell_chain,
)
from exhaust_plume.models.moc.caustic_restart import MocCausticFamilyBandResult
from exhaust_plume.models.moc.caustic_bridge import MocCausticBridgeStatus, MocCausticUpstreamBridge
from exhaust_plume.models.moc.caustic_remesh import (
  MocCausticShockRemeshRequest,
  MocCausticShockRemeshResult,
  solve_caustic_shock_remesh,
  solve_caustic_shock_remesh_from_upstream_bridge,
)
from exhaust_plume.models.moc.caustic_terminal import (
  solve_caustic_simple_wave_terminal_remesh,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldContinuationSolve,
  MocPhysicalPostShockFieldResult,
  continue_ambient_closed_post_shock_chain,
)
from exhaust_plume.models.moc.first_cell_closure import (
  MocFirstCellTerminalClosureResult,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocPostShockCharacteristicZoneResult,
  MocPostShockFieldContinuationSolver,
  assemble_post_shock_characteristic_field,
  continue_post_shock_characteristic_chain,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeControlSection,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFreeBoundaryResult,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
  solve_mixed_regime_downstream_perimeter,
  solve_mixed_regime_downstream_free_boundary,
  solve_mixed_regime_downstream_free_boundary_from_control_section,
)
from exhaust_plume.models.moc.mixed_regime_planar import (
  MocMixedRegimePlanarFieldSolver,
  MocMixedRegimePlanarSolveResult,
  run_mixed_regime_planar_field_solver,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState
from exhaust_plume.models.moc.source_strip import MocSourceStripContinuationResult
from exhaust_plume.models.moc.terminal_patch import MocTerminalReflectionPatchResult
from exhaust_plume.models.moc.terminal_patch_solver import (
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination,
)
from exhaust_plume.models.moc.coupled import (
  solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination,
)
from exhaust_plume.models.moc.free_boundary import (
  solve_marched_attached_shock_chain_cell,
  solve_marched_attached_shock_from_caustic_upstream_bridge,
  solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary,
  solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination,
  solve_marched_attached_shock_chain_cell_from_post_shock_field_with_invariant_boundary_or_termination,
  solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination,
  solve_marched_attached_shock_chain_cell_from_source_strip_or_termination,
)
from exhaust_plume.models.moc.family_band_solver import (
  MocCausticFamilyBandEnvelopeStatus,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination,
  trace_caustic_family_band_forward_envelope,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocChainPlannerKind',
  'MocChainPlannerStep',
  'MocChainPlannerResult',
  'MocFirstCellTerminalClosurePlannerResult',
  'MocPrescribedMixedRegimeClosureMock',
  'MocSolverGeneratedMixedRegimeClosureReference',
  'MocPrescribedPostShockChainMock',
  'MocSolverGeneratedPostShockChainReference',
  'MocFieldCoupledPostShockChainReference',
  'plan_moc_chain',
  'plan_post_shock_characteristic_chain',
  'plan_post_shock_field_chain',
  'plan_source_strip_shock_chain',
  'plan_source_strip_shock_chain_sequence',
  'plan_post_shock_field_invariant_chain',
  'plan_prescribed_post_shock_chain_mock',
  'plan_solver_generated_post_shock_chain_reference',
  'plan_field_coupled_post_shock_chain_reference',
  'plan_terminal_reflection_patch_chain',
  'plan_post_shock_zone_chain',
  'plan_caustic_family_band_chain',
  'plan_caustic_family_band_invariant_chain',
  'plan_caustic_origin_envelope_chain',
  'plan_caustic_upstream_bridge_chain',
  'plan_caustic_upstream_bridge_invariant_chain',
  'plan_caustic_shock_remesh_chain',
  'plan_caustic_shock_remesh_chain_from_upstream_bridge',
  'plan_caustic_simple_wave_terminal_chain',
  'plan_caustic_remesh_downstream_field_chain',
  'plan_caustic_remesh_downstream_field_invariant_chain',
  'plan_ambient_pressure_field_chain',
  'plan_ambient_closed_post_shock_chain',
  'plan_first_cell_terminal_closure',
  'plan_prescribed_first_cell_terminal_closure_mock',
  'plan_solver_generated_first_cell_terminal_closure_reference',
  'plan_solver_generated_first_cell_terminal_closure_reference_from_control_section',
  'plan_first_cell_terminal_closure_with_planar_handoff',
)


class MocChainPlannerKind(str, Enum):
  """Provenance label for a planner run."""

  PRESCRIBED_BOUNDARY_MOCK = 'prescribed-boundary-mock'
  SOLVER_GENERATED_REFERENCE = 'solver-generated-reference'
  UPSTREAM_COUPLED_RESEARCH = 'upstream-coupled-research'
####


@dataclass(frozen=True, slots=True)
class MocChainPlannerStep:
  """One callback invocation and the exact handoff it was given."""

  current_cell_index: int
  next_cell_index: int
  current_end_x_m: float
  boundary_kind: MocChainBoundaryKind | None
  incoming_handoff_sample_count: int
  incoming_total_pressure_range_Pa: tuple[float, float] | None
  incoming_handoff_fingerprint: str | None = None
  incoming_handoff_link_verified: bool | None = None
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_end_x_m: float | None = None
  result_geometry_fidelity: MocChainGeometryFidelity | None = None
  result_physical_closure: MocCellClosureStatus | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None
  result_boundary_kind: MocChainBoundaryKind | None = None
  result_handoff_sample_count: int | None = None
  result_total_pressure_range_Pa: tuple[float, float] | None = None
  result_handoff_fingerprint: str | None = None

  def __post_init__(self) -> None:
    if isinstance(self.current_cell_index, bool) or self.current_cell_index < 1:
      raise ValueError('current_cell_index must be a positive integer')
    if isinstance(self.next_cell_index, bool) or self.next_cell_index != self.current_cell_index + 1:
      raise ValueError('next_cell_index must immediately follow current_cell_index')
    if not isfinite(float(self.current_end_x_m)):
      raise ValueError('current_end_x_m must be finite')
    if self.boundary_kind is not None and not isinstance(
        self.boundary_kind,
        MocChainBoundaryKind,
    ):
      raise TypeError('boundary_kind must be a MocChainBoundaryKind or None')
    if isinstance(self.incoming_handoff_sample_count, bool) or self.incoming_handoff_sample_count < 0:
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    pressure_range = self.incoming_total_pressure_range_Pa
    if pressure_range is not None:
      if len(pressure_range) != 2:
        raise ValueError('incoming_total_pressure_range_Pa must contain two values')
      minimum, maximum = (float(value) for value in pressure_range)
      if (
        not isfinite(minimum)
        or not isfinite(maximum)
        or minimum <= 0.0
        or maximum < minimum
      ):
        raise ValueError('incoming total-pressure range must be finite and ordered')
      object.__setattr__(self, 'incoming_total_pressure_range_Pa', (minimum, maximum))
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    if self.result_status is not None and not isinstance(self.result_status, str):
      raise TypeError('result_status must be a string or None')
    if self.result_end_x_m is not None and not isfinite(float(self.result_end_x_m)):
      raise ValueError('result_end_x_m must be finite when supplied')
    if self.result_geometry_fidelity is not None and not isinstance(
        self.result_geometry_fidelity,
        MocChainGeometryFidelity,
    ):
      raise TypeError(
        'result_geometry_fidelity must be a MocChainGeometryFidelity or None'
      )
    if self.result_physical_closure is not None and not isinstance(
        self.result_physical_closure,
        MocCellClosureStatus,
    ):
      raise TypeError(
        'result_physical_closure must be a MocCellClosureStatus or None'
      )
    if self.result_termination_reason is not None and not isinstance(
        self.result_termination_reason,
        MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )
    if self.result_physical_termination is not None and not isinstance(
        self.result_physical_termination,
        bool,
    ):
      raise TypeError('result_physical_termination must be a bool or None')
    if self.incoming_handoff_link_verified is not None and not isinstance(
        self.incoming_handoff_link_verified,
        bool,
    ):
      raise TypeError('incoming_handoff_link_verified must be a bool or None')
    if self.result_boundary_kind is not None and not isinstance(
        self.result_boundary_kind,
        MocChainBoundaryKind,
    ):
      raise TypeError('result_boundary_kind must be a MocChainBoundaryKind or None')
    if self.result_handoff_sample_count is not None:
      if (
        isinstance(self.result_handoff_sample_count, bool)
        or self.result_handoff_sample_count < 0
      ):
        raise ValueError('result_handoff_sample_count must be nonnegative when supplied')
    result_pressure_range = self.result_total_pressure_range_Pa
    if result_pressure_range is not None:
      if len(result_pressure_range) != 2:
        raise ValueError('result_total_pressure_range_Pa must contain two values')
      minimum, maximum = (float(value) for value in result_pressure_range)
      if (
        not isfinite(minimum)
        or not isfinite(maximum)
        or minimum <= 0.0
        or maximum < minimum
      ):
        raise ValueError('result total-pressure range must be finite and ordered')
      object.__setattr__(self, 'result_total_pressure_range_Pa', (minimum, maximum))
    if self.result_handoff_fingerprint is not None and not isinstance(
        self.result_handoff_fingerprint,
        str,
    ):
      raise TypeError('result_handoff_fingerprint must be a string or None')
  ####

  @classmethod
  def from_boundary(
    cls,
    current: MocChainCell,
    next_cell_index: int,
    boundary: tuple[MocChainBoundarySample, ...],
    *,
    previous_result_handoff_fingerprint: str | None = None,
  ) -> 'MocChainPlannerStep':
    pressure_range = None
    if boundary:
      pressures = tuple(sample.total_pressure_Pa for sample in boundary)
      pressure_range = (min(pressures), max(pressures))
    incoming_fingerprint = _handoff_fingerprint(boundary)
    return cls(
      current_cell_index=current.cell_index,
      next_cell_index=next_cell_index,
      current_end_x_m=current.end_x_m,
      boundary_kind=(
        current.continuation_boundary_kind if boundary else None
      ),
      incoming_handoff_sample_count=len(boundary),
      incoming_total_pressure_range_Pa=pressure_range,
      incoming_handoff_fingerprint=incoming_fingerprint,
      incoming_handoff_link_verified=(
        None
        if previous_result_handoff_fingerprint is None
        else incoming_fingerprint is not None
        and incoming_fingerprint == previous_result_handoff_fingerprint
      ),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'current_cell_index': self.current_cell_index,
      'next_cell_index': self.next_cell_index,
      'current_end_x_m': self.current_end_x_m,
      'boundary_kind': None if self.boundary_kind is None else self.boundary_kind.value,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_total_pressure_range_Pa': self.incoming_total_pressure_range_Pa,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_end_x_m': self.result_end_x_m,
      'result_geometry_fidelity': (
        None
        if self.result_geometry_fidelity is None
        else self.result_geometry_fidelity.value
      ),
      'result_physical_closure': (
        None
        if self.result_physical_closure is None
        else self.result_physical_closure.value
      ),
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
      'result_boundary_kind': (
        None
        if self.result_boundary_kind is None
        else self.result_boundary_kind.value
      ),
      'result_handoff_sample_count': self.result_handoff_sample_count,
      'result_total_pressure_range_Pa': self.result_total_pressure_range_Pa,
      'result_handoff_fingerprint': self.result_handoff_fingerprint,
    }
  ####

  def with_solver_result(self, result: object) -> 'MocChainPlannerStep':
    """Attach the typed result returned for this planned handoff."""

    if isinstance(result, MocChainTerminationDecision):
      return replace(
        self,
        result_kind='termination-returned',
        result_status=result.reason.value,
        result_termination_reason=result.reason,
        result_physical_termination=result.physical_termination,
      )
    if isinstance(result, MocPostShockChainCellSolve):
      field = result.field
      boundary = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          field.continuation_boundary_states,
          field.continuation_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      return replace(
        self,
        result_kind='field-solve-returned',
        result_status=field.status.value,
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=(
          MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
          if field.converged
          else None
        ),
        result_physical_closure=(
          MocCellClosureStatus.CLOSED
          if field.physical_closure_verified
          else MocCellClosureStatus.OPEN
        ),
        **_result_handoff_fields(
          boundary,
          MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
        ),
      )
    if isinstance(result, MocPhysicalPostShockFieldContinuationSolve):
      field = result.field
      boundary = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          field.centerline_boundary_states,
          field.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      return replace(
        self,
        result_kind='physical-field-solve-returned',
        result_status=field.status.value,
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=(
          MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
          if field.physical_closure_verified
          else None
        ),
        result_physical_closure=(
          MocCellClosureStatus.CLOSED
          if field.physical_closure_verified
          else MocCellClosureStatus.OPEN
        ),
        **_result_handoff_fields(
          boundary,
          MocChainBoundaryKind.CENTERLINE_TRACE,
        ),
      )
    if isinstance(result, MocChainCell):
      return replace(
        self,
        result_kind='cell-returned',
        result_status='resolved' if result.resolved else 'unresolved',
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=result.geometry_fidelity,
        result_physical_closure=result.physical_closure,
        **_result_handoff_fields(
          result.continuation_boundary,
          result.continuation_boundary_kind,
        ),
      )
    if result is None:
      return replace(
        self,
        result_kind='no-cell-returned',
        result_status='none',
      )
    return replace(
      self,
      result_kind='invalid-result-returned',
      result_status=type(result).__name__,
    )
  ####

  def with_solver_error(self, error: BaseException) -> 'MocChainPlannerStep':
    """Record a callback exception before the chain converts it to failure."""

    return replace(
      self,
      result_kind='solver-error',
      result_status=type(error).__name__,
    )
  ####


def _handoff_fingerprint(
  boundary: tuple[MocChainBoundarySample, ...],
) -> str | None:
  """Return a deterministic audit fingerprint for an exact typed handoff.

  The digest is provenance bookkeeping, not a physical validation result.  It
  lets a serialized planner report identify the full state/pressure boundary
  that was presented to a callback without duplicating every sample in the
  report.  ``float.hex`` keeps the representation deterministic across JSON
  serialization and preserves signed zero when it is present.
  """

  if not boundary:
    return None
  payload = '\n'.join(
    '|'.join(
      (
        state_value.hex()
        for state_value in (
          sample.state.x_m,
          sample.state.y_m,
          sample.state.theta_rad,
          sample.state.mach,
          sample.state.gamma,
          sample.total_pressure_Pa,
        )
      )
    )
    for sample in boundary
  )
  return sha256(payload.encode('ascii')).hexdigest()


def _source_strip_fingerprint(
  continuation: MocSourceStripContinuationResult,
) -> str | None:
  """Return a deterministic identity for a consumed source-strip domain."""

  strip = continuation.strip
  if strip is None:
    return None

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = '\n'.join((
    f'total-pressure:{strip.total_pressure_Pa.hex()}',
    f'window-start:{strip.source_window_start_index}',
    f'window-total:{strip.source_window_total_count}',
    'plus:' + '\n'.join(
      state_payload(state) for state in strip.plus_source_states
    ),
    'minus:' + '\n'.join(
      state_payload(state) for state in strip.minus_source_states
    ),
  ))
  return sha256(payload.encode('ascii')).hexdigest()


def _result_handoff_fields(
  boundary: tuple[MocChainBoundarySample, ...],
  boundary_kind: MocChainBoundaryKind | None,
) -> dict[str, Any]:
  """Return the outgoing handoff audit fields for a returned cell/field."""

  pressure_range = None
  if boundary:
    pressures = tuple(sample.total_pressure_Pa for sample in boundary)
    pressure_range = (min(pressures), max(pressures))
  return {
    'result_boundary_kind': boundary_kind if boundary else None,
    'result_handoff_sample_count': len(boundary),
    'result_total_pressure_range_Pa': pressure_range,
    'result_handoff_fingerprint': _handoff_fingerprint(boundary),
  }


@dataclass(frozen=True, slots=True)
class MocChainPlannerResult:
  """A chain result plus planner provenance and callback audit steps."""

  chain: MocChainResult
  planner_kind: MocChainPlannerKind
  steps: tuple[MocChainPlannerStep, ...] = ()
  claim_status: str = ''
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.chain, MocChainResult):
      raise TypeError('chain must be a MocChainResult')
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    steps = tuple(self.steps)
    if any(not isinstance(step, MocChainPlannerStep) for step in steps):
      raise TypeError('steps must contain MocChainPlannerStep values')
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def resolved(self) -> bool:
    return self.chain.resolved
  ####

  @property
  def physical_termination(self) -> bool:
    return self.chain.physical_termination
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """Whether this planner provenance may be called production evidence."""

    return False
  ####

  @property
  def handoff_links_verified(self) -> bool | None:
    """Whether every continued callback consumed the prior result handoff."""

    if len(self.steps) < 2:
      return None
    return all(step.incoming_handoff_link_verified is True for step in self.steps[1:])

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'step_count': len(self.steps),
      'handoff_links_verified': self.handoff_links_verified,
      'steps': [step.as_report() for step in self.steps],
      'chain': self.chain.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocPrescribedMixedRegimeClosureMock:
  """Explicit synthetic terminal closure fixture for planner validation.

  The fixture supplies a small rectangular perimeter and a constant scalar
  subsonic state, then routes both through the real mixed-regime perimeter
  adapter.  It exists to exercise the exact terminal seam and typed closure
  result while the canonical downstream perimeter is still unsolved.  The
  pressure-outflow condition is intentionally the only supported condition:
  this mock must not be mistaken for a free-boundary or slip-wall solver.
  """

  streamwise_length_m: float = 0.02
  transverse_length_m: float = 0.01
  radial_divisions: int = 2
  condition_kind: MocMixedRegimeDownstreamConditionKind = (
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION
  )
  model: str = 'prescribed-pressure-outflow-mixed-regime-closure-mock'

  def __post_init__(self) -> None:
    for name, value in (
      ('streamwise_length_m', self.streamwise_length_m),
      ('transverse_length_m', self.transverse_length_m),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if (
      isinstance(self.radial_divisions, bool)
      or not isinstance(self.radial_divisions, int)
      or self.radial_divisions < 1
    ):
      raise ValueError('radial_divisions must be a positive integer')
    if not isinstance(
      self.condition_kind,
      MocMixedRegimeDownstreamConditionKind,
    ):
      raise TypeError(
        'condition_kind must be a MocMixedRegimeDownstreamConditionKind'
      )
    if self.condition_kind is not MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION:
      raise ValueError(
        'MocPrescribedMixedRegimeClosureMock only supports the '
        'PRESSURE_OUTFLOW_SECTION condition'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'streamwise_length_m', float(self.streamwise_length_m))
    object.__setattr__(self, 'transverse_length_m', float(self.transverse_length_m))
    object.__setattr__(self, 'model', model)

  @property
  def production_claim_allowed(self) -> bool:
    """Whether this synthetic fixture may support a product claim."""

    return False

  def as_report(self) -> dict[str, Any]:
    """Return the fixture configuration and its hard fidelity ceiling."""

    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'streamwise_length_m': self.streamwise_length_m,
      'transverse_length_m': self.transverse_length_m,
      'radial_divisions': self.radial_divisions,
      'condition_kind': self.condition_kind.value,
      'claim_status': (
        'prescribed-mixed-regime-pressure-outflow-closure-mock; '
        'canonical-downstream-perimeter-and-free-boundary-solve-pending'
      ),
    }

  @staticmethod
  def _validate_request(request: MocMixedRegimePerimeterRequest) -> None:
    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError(
        'request must be a MocMixedRegimePerimeterRequest'
      )

  def perimeter_points(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> tuple[tuple[float, float], ...]:
    """Return the explicit closed rectangle anchored at the terminal seam."""

    self._validate_request(request)
    x_m, y_m = request.terminal_point_m
    return (
      (x_m, y_m),
      (x_m + self.streamwise_length_m, y_m),
      (x_m + self.streamwise_length_m, y_m + self.transverse_length_m),
      (x_m, y_m + self.transverse_length_m),
      (x_m, y_m),
    )

  def specification(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> MocMixedRegimeDownstreamPerimeterSpec:
    """Build the explicit pressure-outflow specification for one request."""

    self._validate_request(request)
    return MocMixedRegimeDownstreamPerimeterSpec(
      perimeter_points_m=self.perimeter_points(request),
      condition_kind=self.condition_kind,
      ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
      model=self.model,
    )

  def sample_at(
    self,
    request: MocMixedRegimePerimeterRequest,
    index: int,
    point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    """Return the constant scalar state at one exact prescribed point."""

    self._validate_request(request)
    points = self.perimeter_points(request)
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(points):
      raise ValueError('sample index is outside the prescribed perimeter')
    expected_point = points[index]
    try:
      received_point = (float(point[0]), float(point[1]))
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError('sample point must contain two numeric coordinates') from error
    if any(
      abs(received - expected) > 1.0e-10
      for received, expected in zip(received_point, expected_point, strict=True)
    ):
      raise ValueError('sample point does not match the prescribed perimeter')
    upstream_state = request.terminal.upstream_state
    if upstream_state is None:
      raise ValueError('terminal request does not expose its upstream state')
    return MocMixedRegimeFieldSample(
      point_m=expected_point,
      mach=request.terminal_downstream_mach,
      flow_angle_rad=request.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=request.terminal_downstream_pressure_Pa,
      total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
      gamma=upstream_state.gamma,
    )

  def solve(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> MocMixedRegimeClosureResult:
    """Solve the explicit fixture through the real downstream adapter."""

    self._validate_request(request)
    specification = self.specification(request)
    return solve_mixed_regime_downstream_perimeter(
      request,
      specification,
      self.sample_at,
      radial_divisions=self.radial_divisions,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocSolverGeneratedMixedRegimeClosureReference:
  """Planner fixture for the solver-owned downstream free-boundary lane.

  Unlike :class:`MocPrescribedMixedRegimeClosureMock`, this reference does
  not prescribe a rectangle or a constant state.  It shoots an effective
  outlet height from the terminal subsonic total state and an explicit
  ambient-pressure target, then submits the generated perimeter through the
  real mixed-boundary and scalar-field gates.  The effective inlet height is
  intentionally an input because a terminal point has no area information.
  """

  effective_inlet_height_m: float = 0.01
  downstream_length_m: float = 0.05
  ambient_pressure_Pa: float | None = None
  ambient_pressure_ratio: float = 0.8
  free_boundary_sample_count: int = 7
  radial_divisions: int = 2
  terminal_regularization_fraction: float = 0.05
  maximum_iterations: int = 40
  model: str = 'solver-owned-quasi-1d-ambient-free-boundary-reference'

  def __post_init__(self) -> None:
    for name, value in (
      ('effective_inlet_height_m', self.effective_inlet_height_m),
      ('downstream_length_m', self.downstream_length_m),
      ('ambient_pressure_ratio', self.ambient_pressure_ratio),
      ('terminal_regularization_fraction', self.terminal_regularization_fraction),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if self.ambient_pressure_ratio >= 1.0:
      raise ValueError('ambient_pressure_ratio must be less than one')
    if self.ambient_pressure_Pa is not None and (
      not isfinite(float(self.ambient_pressure_Pa))
      or self.ambient_pressure_Pa <= 0.0
    ):
      raise ValueError('ambient_pressure_Pa must be finite and positive when supplied')
    for name, value, minimum in (
      ('free_boundary_sample_count', self.free_boundary_sample_count, 3),
      ('radial_divisions', self.radial_divisions, 1),
      ('maximum_iterations', self.maximum_iterations, 1),
    ):
      if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(
          f'{name} must be an integer greater than or equal to {minimum}'
        )
    if not 0.0 < self.terminal_regularization_fraction < 1.0:
      raise ValueError(
        'terminal_regularization_fraction must lie strictly between zero and one'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'effective_inlet_height_m', float(self.effective_inlet_height_m))
    object.__setattr__(self, 'downstream_length_m', float(self.downstream_length_m))
    object.__setattr__(self, 'ambient_pressure_Pa', (
      None
      if self.ambient_pressure_Pa is None
      else float(self.ambient_pressure_Pa)
    ))
    object.__setattr__(self, 'ambient_pressure_ratio', float(self.ambient_pressure_ratio))
    object.__setattr__(self, 'terminal_regularization_fraction', float(self.terminal_regularization_fraction))
    object.__setattr__(self, 'model', model)

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def _ambient_pressure(self, request: MocMixedRegimePerimeterRequest) -> float:
    if self.ambient_pressure_Pa is not None:
      return self.ambient_pressure_Pa
    return self.ambient_pressure_ratio * request.terminal_downstream_pressure_Pa

  def solve(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> MocMixedRegimeFreeBoundaryResult:
    """Run the solver-owned reference against one exact terminal seam."""

    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest')
    return solve_mixed_regime_downstream_free_boundary(
      request,
      ambient_pressure_Pa=self._ambient_pressure(request),
      effective_inlet_height_m=self.effective_inlet_height_m,
      downstream_length_m=self.downstream_length_m,
      free_boundary_sample_count=self.free_boundary_sample_count,
      radial_divisions=self.radial_divisions,
      terminal_regularization_fraction=self.terminal_regularization_fraction,
      maximum_iterations=self.maximum_iterations,
    )

  def solve_from_control_section(
    self,
    request: MocMixedRegimePerimeterRequest,
    control_section: MocMixedRegimeControlSection,
  ) -> MocMixedRegimeFreeBoundaryResult:
    """Run the reference using an explicit solver-supplied control section."""

    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest')
    if not isinstance(control_section, MocMixedRegimeControlSection):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection'
      )
    return solve_mixed_regime_downstream_free_boundary_from_control_section(
      request,
      control_section,
      ambient_pressure_Pa=self._ambient_pressure(request),
      downstream_length_m=self.downstream_length_m,
      free_boundary_sample_count=self.free_boundary_sample_count,
      radial_divisions=self.radial_divisions,
      terminal_regularization_fraction=self.terminal_regularization_fraction,
      maximum_iterations=self.maximum_iterations,
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'effective_inlet_height_m': self.effective_inlet_height_m,
      'downstream_length_m': self.downstream_length_m,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'ambient_pressure_ratio': self.ambient_pressure_ratio,
      'free_boundary_sample_count': self.free_boundary_sample_count,
      'radial_divisions': self.radial_divisions,
      'terminal_regularization_fraction': self.terminal_regularization_fraction,
      'maximum_iterations': self.maximum_iterations,
      'claim_status': (
        'solver-owned-quasi-1d-free-boundary-reference; '
        'canonical-reflected-moc-and-external-validation-pending'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocFirstCellTerminalClosurePlannerResult:
  """Planner/audit result for one first-cell terminal closure attempt.

  This result deliberately is not a ``MocChainPlannerResult``: a terminal
  mixed-regime region is a chain stop, not a supersonic cell that can seed the
  next shock.  The optional closure is retained beside the terminal result so
  reports can distinguish an open physical boundary from a prescribed fixture
  that passed the local scalar/reference gates.
  """

  terminal: MocFirstCellTerminalClosureResult
  mixed_regime_closure: MocMixedRegimeClosureResult | None
  termination: MocChainTerminationDecision | None
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})
  mixed_regime_planar_handoff: MocMixedRegimePlanarSolveResult | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.terminal, MocFirstCellTerminalClosureResult):
      raise TypeError(
        'terminal must be a MocFirstCellTerminalClosureResult'
      )
    if self.mixed_regime_closure is not None and not isinstance(
      self.mixed_regime_closure,
      MocMixedRegimeClosureResult,
    ):
      raise TypeError(
        'mixed_regime_closure must be a MocMixedRegimeClosureResult or None'
      )
    if self.termination is not None and not isinstance(
      self.termination,
      MocChainTerminationDecision,
    ):
      raise TypeError(
        'termination must be a MocChainTerminationDecision or None'
      )
    if self.mixed_regime_planar_handoff is not None and not isinstance(
      self.mixed_regime_planar_handoff,
      MocMixedRegimePlanarSolveResult,
    ):
      raise TypeError(
        'mixed_regime_planar_handoff must be a '
        'MocMixedRegimePlanarSolveResult or None'
      )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def resolved(self) -> bool:
    """Whether the supersonic terminal region itself converged."""

    return self.terminal.converged

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the terminal and its attached mixed-regime field passed."""

    return self.terminal.physical_closure_verified

  @property
  def physical_termination(self) -> bool:
    """Whether the retained decision is a verified physical chain stop."""

    return bool(
      self.termination is not None
      and self.termination.physical_termination
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal mixed-regime result never becomes a supersonic next cell."""

    return self.terminal.chain_promotion_blocked

  @property
  def production_claim_allowed(self) -> bool:
    """Planner and prescribed-fixture results cannot support product claims."""

    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination': self.physical_termination,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'termination': (
        None if self.termination is None else self.termination.as_report()
      ),
      'terminal': self.terminal.as_report(),
      'mixed_regime_closure': (
        None
        if self.mixed_regime_closure is None
        else self.mixed_regime_closure.as_report()
      ),
      'mixed_regime_planar_handoff': (
        None
        if self.mixed_regime_planar_handoff is None
        else self.mixed_regime_planar_handoff.as_report()
      ),
      'diagnostics': dict(self.diagnostics),
    }
  ####


def plan_first_cell_terminal_closure(
  terminal: MocFirstCellTerminalClosureResult,
  *,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
  control_section: MocMixedRegimeControlSection | None = None,
  solve_field: Callable[
    [MocMixedRegimePerimeterRequest],
    MocMixedRegimeFieldResult | None,
  ] | None = None,
  claim_status: str | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Audit a first-cell terminal and optionally submit its exact scalar seam.

  ``mock`` is the reusable rectangular pressure-outflow fixture.  ``solver``
  is the separate solver-owned quasi-one-dimensional free-boundary reference;
  a future higher-fidelity downstream solver can instead be supplied as
  ``solve_field``.  In every case the terminal object owns the request and the
  real mixed-regime adapter owns seam acceptance.  Omitting all three only
  audits the already-solved supersonic terminal and preserves its open/
  physical decision.  ``control_section`` is accepted only with ``solver``;
  the section-aware path refuses to collapse a varying scalar section into a
  one-dimensional height.
  """

  if not isinstance(terminal, MocFirstCellTerminalClosureResult):
    raise TypeError(
      'terminal must be a MocFirstCellTerminalClosureResult'
    )
  if mock is not None and not isinstance(
    mock,
    MocPrescribedMixedRegimeClosureMock,
  ):
    raise TypeError(
      'mock must be a MocPrescribedMixedRegimeClosureMock or None'
    )
  if solver is not None and not isinstance(
    solver,
    MocSolverGeneratedMixedRegimeClosureReference,
  ):
    raise TypeError(
      'solver must be a MocSolverGeneratedMixedRegimeClosureReference or None'
    )
  if control_section is not None and not isinstance(
    control_section,
    MocMixedRegimeControlSection,
  ):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection or None'
    )
  if control_section is not None and solver is None:
    raise ValueError('control_section requires the solver-generated reference')
  supplied_solvers = sum(
    value is not None for value in (mock, solver, solve_field)
  )
  if supplied_solvers > 1:
    raise ValueError('supply only one of mock, solver, or solve_field')
  if solve_field is not None and not callable(solve_field):
    raise TypeError('solve_field must be callable when supplied')

  planner_kind = (
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
    if mock is not None
    else MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  )
  diagnostics: dict[str, Any] = {
    'planner_model': 'first-cell-terminal-closure-planner',
    'mixed_regime_solver_supplied': supplied_solvers == 1,
    'mixed_regime_closure_attached': False,
    'chain_promotion_blocked': terminal.chain_promotion_blocked,
    'terminal_physical_closure_verified': terminal.physical_closure_verified,
  }
  if mock is not None:
    diagnostics['prescribed_mixed_regime_closure_mock'] = mock.as_report()
  elif solver is not None:
    diagnostics['downstream_solver_model'] = solver.model
    diagnostics['solver_generated_mixed_regime_reference'] = solver.as_report()
    diagnostics['control_section_supplied'] = control_section is not None
    if control_section is not None:
      diagnostics['control_section'] = control_section.as_report()
  elif solve_field is not None:
    diagnostics['downstream_solver_model'] = 'caller-supplied-mixed-regime-solver'

  mixed_regime_closure: MocMixedRegimeClosureResult | None = None
  attached_terminal = terminal
  if supplied_solvers == 1:
    if terminal.terminal_field is None or not terminal.converged:
      diagnostics['mixed_regime_solver_skipped'] = (
        'terminal does not expose a converged supersonic field and exact seam'
      )
    else:
      try:
        if mock is not None:
          mixed_regime_closure = mock.solve(
            terminal.mixed_regime_perimeter_request()
          )
        elif solver is not None:
          request = terminal.mixed_regime_perimeter_request()
          free_boundary = (
            solver.solve_from_control_section(request, control_section)
            if control_section is not None
            else solver.solve(request)
          )
          diagnostics['solver_generated_mixed_regime_result'] = (
            free_boundary.as_report()
          )
          mixed_regime_closure = free_boundary.closure
          if mixed_regime_closure is None:
            diagnostics['mixed_regime_closure_message'] = free_boundary.message
        else:
          assert solve_field is not None
          mixed_regime_closure = terminal.solve_mixed_regime_closure(solve_field)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        diagnostics['mixed_regime_solver_error'] = str(error)
      else:
        diagnostics['mixed_regime_closure_status'] = (
          mixed_regime_closure.status.value
          if mixed_regime_closure is not None
          else 'solver-owned-free-boundary-no-closure'
        )
        if mixed_regime_closure is not None and mixed_regime_closure.converged:
          try:
            attached_terminal = terminal.attach_mixed_regime_closure(
              mixed_regime_closure
            )
          except (TypeError, ValueError) as error:
            diagnostics['mixed_regime_closure_attachment_error'] = str(error)
          else:
            diagnostics['mixed_regime_closure_attached'] = True
        elif mixed_regime_closure is not None:
          diagnostics['mixed_regime_closure_message'] = (
            mixed_regime_closure.message
          )

  try:
    termination = attached_terminal.as_chain_termination_decision()
  except ValueError as error:
    termination = None
    diagnostics['termination_decision_error'] = str(error)

  diagnostics.update({
    'terminal_physical_closure_verified': attached_terminal.physical_closure_verified,
    'physical_termination': bool(
      termination is not None and termination.physical_termination
    ),
  })
  return MocFirstCellTerminalClosurePlannerResult(
    terminal=attached_terminal,
    mixed_regime_closure=mixed_regime_closure,
    termination=termination,
    planner_kind=planner_kind,
    claim_status=(
      (
        'prescribed-mixed-regime-terminal-planner-mock; '
        'canonical-downstream-free-boundary-pending'
      )
      if mock is not None
      else (
        'solver-generated-mixed-regime-free-boundary-reference; '
        'canonical-reflected-moc-and-external-validation-pending'
      )
      if solver is not None
      else (
        'first-cell-terminal-closure-planner; '
        'canonical-downstream-free-boundary-and-external-validation-pending'
      )
      if claim_status is None
      else claim_status
    ),
    diagnostics=diagnostics,
  )


def plan_prescribed_first_cell_terminal_closure_mock(
  terminal: MocFirstCellTerminalClosureResult,
  *,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Run the explicit prescribed mixed-regime terminal planner fixture."""

  fixture = (
    MocPrescribedMixedRegimeClosureMock() if mock is None else mock
  )
  return plan_first_cell_terminal_closure(terminal, mock=fixture)
  ####


def plan_solver_generated_first_cell_terminal_closure_reference(
  terminal: MocFirstCellTerminalClosureResult,
  *,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Run the solver-owned finite free-boundary planner reference."""

  reference = (
    MocSolverGeneratedMixedRegimeClosureReference()
    if solver is None
    else solver
  )
  return plan_first_cell_terminal_closure(terminal, solver=reference)
  ####


def plan_solver_generated_first_cell_terminal_closure_reference_from_control_section(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  *,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Plan a first-cell closure from an explicit scalar control section."""

  reference = (
    MocSolverGeneratedMixedRegimeClosureReference()
    if solver is None
    else solver
  )
  return plan_first_cell_terminal_closure(
    terminal,
    solver=reference,
    control_section=control_section,
  )
  ####


def plan_first_cell_terminal_closure_with_planar_handoff(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  solve_field: MocMixedRegimePlanarFieldSolver,
  *,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver',
) -> MocFirstCellTerminalClosurePlannerResult:
  """Audit a first cell against an explicit downstream planar handoff.

  This wrapper records a successful callback-owned planar handoff beside the
  first-cell result, but deliberately does not attach it to the terminal or
  issue a physical termination decision.  The current planar field value can
  represent a scalar reference mesh, so promotion must wait for a solver that
  proves the canonical reflected-MOC downstream field and free boundary.
  """

  if not isinstance(terminal, MocFirstCellTerminalClosureResult):
    raise TypeError(
      'terminal must be a MocFirstCellTerminalClosureResult'
    )
  request = terminal.mixed_regime_perimeter_request()
  handoff = run_mixed_regime_planar_field_solver(
    request,
    control_section,
    perimeter_spec,
    solve_field,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
    solver_model=solver_model,
  )
  base = plan_first_cell_terminal_closure(terminal)
  diagnostics = dict(base.diagnostics)
  diagnostics.update({
    'mixed_regime_planar_handoff_verified': handoff.handoff_verified,
    'mixed_regime_planar_handoff': handoff.as_report(),
    'mixed_regime_planar_handoff_attached': False,
    'mixed_regime_planar_handoff_chain_promotion_blocked': (
      handoff.chain_promotion_blocked
    ),
    'mixed_regime_planar_handoff_physical_closure_verified': (
      handoff.physical_closure_verified
    ),
  })
  return replace(
    base,
    claim_status=(
      'explicit-planar-downstream-handoff-only; canonical-reflected-moc-'
      'free-boundary-and-external-validation-pending'
    ),
    diagnostics=diagnostics,
    mixed_regime_planar_handoff=handoff,
  )
  ####


@dataclass(frozen=True, slots=True)
class MocPrescribedPostShockChainMock:
  """Deterministic continued-cell fixture for planner and report validation.

  This fixture supplies a prescribed next-shock curve and therefore is not a
  free-boundary MOC solver.  It exists so the state-carrying planner contract
  can be exercised over more than one cell without making synthetic geometry
  eligible for a production plume claim.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.50
  shock_start_offset_m: float = 0.20
  shock_sample_spacing_m: float = 0.02
  shock_geometry_scale_per_cell: float = 0.0
  # The default line is tangent to a weak attached shock for M=2, gamma=1.4.
  # It is deliberately still prescribed geometry, but the local fit below now
  # proves that it is compatible with the requested attached-shock branch
  # before the field is assembled.  The varying downstream angles keep the
  # characteristic mesh nondegenerate.
  shock_ordinates_m: tuple[float, ...] = (
    0.08237108456402913,
    0.06177831342302184,
    0.04118554228201456,
    0.020592771141007285,
    0.0,
  )
  downstream_flow_angles_rad: tuple[float, ...] = (-0.16, -0.12, -0.08, -0.04, 0.0)
  upstream_flow_angle_start_rad: float = -0.22316537247754467
  upstream_flow_angle_step_rad: float = 0.01953284223794056
  upstream_flow_angles_rad: tuple[float, ...] = (
    -0.22316537247754467,
    -0.204175961115758,
    -0.18482733549527713,
    -0.16511536988179235,
    -0.14503421352578244,
  )
  mach: float = 2.0
  gamma: float = 1.4
  pressure_loss_ratio: float | None = None
  # Optional schedules apply to continued cells 2..total_cell_count.  They
  # are explicit geometry controls for planner/visualization scenarios; they
  # do not turn this prescribed-boundary fixture into a free-boundary solver.
  cell_axial_lengths_m: tuple[float, ...] | None = None
  shock_start_offsets_m: tuple[float, ...] | None = None
  shock_geometry_scales_per_cell: tuple[float, ...] | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_sample_spacing_m', self.shock_sample_spacing_m),
    ):
      if not isfinite(float(value)) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if not isfinite(float(self.shock_geometry_scale_per_cell)):
      raise ValueError('shock_geometry_scale_per_cell must be finite')
    for name, value, lower_bound in (
      ('mach', self.mach, 1.0),
      ('gamma', self.gamma, 1.0),
    ):
      if not isfinite(float(value)) or value <= lower_bound:
        raise ValueError(f'{name} must be finite and greater than {lower_bound}')
    if self.pressure_loss_ratio is not None and (
      not isfinite(float(self.pressure_loss_ratio))
      or not 0.0 < self.pressure_loss_ratio < 1.0
    ):
      raise ValueError(
        'pressure_loss_ratio must be finite and strictly between zero and one '
        'when supplied'
      )
    try:
      ordinates = tuple(float(value) for value in self.shock_ordinates_m)
      downstream_angles = tuple(float(value) for value in self.downstream_flow_angles_rad)
    except (TypeError, ValueError) as error:
      raise ValueError('shock ordinates and downstream angles must be numeric sequences') from error
    if len(ordinates) < 3 or len(ordinates) != len(downstream_angles):
      raise ValueError(
        'shock ordinates and downstream angles must have equal lengths of at least three'
      )
    if any(not isfinite(value) or value < 0.0 for value in ordinates):
      raise ValueError('shock ordinates must be finite and nonnegative')
    if any(next_value > value for value, next_value in zip(ordinates, ordinates[1:])):
      raise ValueError('shock ordinates must be nonincreasing toward the centerline')
    if abs(ordinates[-1]) > 1.0e-12:
      raise ValueError('the final prescribed shock ordinate must be the centerline')
    if any(not isfinite(value) for value in downstream_angles):
      raise ValueError('downstream flow angles must be finite')
    if abs(downstream_angles[-1]) > 1.0e-12:
      raise ValueError('the final prescribed downstream flow angle must be zero')
    for name, value in (
      ('upstream_flow_angle_start_rad', self.upstream_flow_angle_start_rad),
      ('upstream_flow_angle_step_rad', self.upstream_flow_angle_step_rad),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    try:
      configured_upstream_angles = (
        tuple(float(value) for value in self.upstream_flow_angles_rad)
        if self.upstream_flow_angles_rad is not None
        else tuple(
          float(self.upstream_flow_angle_start_rad)
          + float(self.upstream_flow_angle_step_rad) * index
          for index in range(len(downstream_angles))
        )
      )
    except (TypeError, ValueError) as error:
      raise ValueError('upstream_flow_angles_rad must be a numeric sequence') from error
    if len(configured_upstream_angles) != len(downstream_angles):
      raise ValueError(
        'upstream_flow_angles_rad must match the downstream angle sample count'
      )
    if any(not isfinite(value) for value in configured_upstream_angles):
      raise ValueError('upstream flow angles must be finite')
    if self.shock_geometry_scales_per_cell is None:
      for cell_index in range(2, self.total_cell_count + 1):
        scale = 1.0 + float(self.shock_geometry_scale_per_cell) * (cell_index - 2)
        if scale <= 0.0:
          raise ValueError(
            'shock_geometry_scale_per_cell produces a non-positive scale '
            f'at cell {cell_index}'
          )

    def normalize_schedule(
      values: tuple[float, ...] | None,
      name: str,
      *,
      positive: bool = True,
    ) -> tuple[float, ...] | None:
      if values is None:
        return None
      try:
        normalized = tuple(float(value) for value in values)
      except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be a numeric sequence') from error
      expected_count = self.total_cell_count - 1
      if len(normalized) != expected_count:
        raise ValueError(
          f'{name} must contain one value for each continued cell '
          f'(expected {expected_count}, got {len(normalized)})'
        )
      if any(
        not isfinite(value) or (value <= 0.0 if positive else False)
        for value in normalized
      ):
        qualifier = 'finite and positive' if positive else 'finite'
        raise ValueError(f'{name} must contain {qualifier} values')
      return normalized

    normalized_lengths = normalize_schedule(
      self.cell_axial_lengths_m,
      'cell_axial_lengths_m',
    )
    normalized_offsets = normalize_schedule(
      self.shock_start_offsets_m,
      'shock_start_offsets_m',
    )
    normalized_scales = normalize_schedule(
      self.shock_geometry_scales_per_cell,
      'shock_geometry_scales_per_cell',
    )
    for cell_index in range(2, self.total_cell_count + 1):
      schedule_index = cell_index - 2
      axial_length = (
        float(self.cell_axial_length_m)
        if normalized_lengths is None
        else normalized_lengths[schedule_index]
      )
      start_offset = (
        float(self.shock_start_offset_m)
        if normalized_offsets is None
        else normalized_offsets[schedule_index]
      )
      scale = self._scheduled_scale_for_index(
        schedule_index,
        normalized_scales,
        float(self.shock_geometry_scale_per_cell),
      )
      shock_end_offset = (
        start_offset
        + float(self.shock_sample_spacing_m) * scale * (len(ordinates) - 1)
      )
      if shock_end_offset >= axial_length:
        raise ValueError(
          'continued-cell shock geometry must fit before the cell end: '
          f'cell {cell_index} ends at {axial_length} m but reaches '
          f'{shock_end_offset} m from its start'
        )
    object.__setattr__(self, 'shock_ordinates_m', ordinates)
    object.__setattr__(self, 'downstream_flow_angles_rad', downstream_angles)
    object.__setattr__(self, 'upstream_flow_angles_rad', configured_upstream_angles)
    object.__setattr__(self, 'cell_axial_lengths_m', normalized_lengths)
    object.__setattr__(self, 'shock_start_offsets_m', normalized_offsets)
    object.__setattr__(self, 'shock_geometry_scales_per_cell', normalized_scales)

  @property
  def sample_count(self) -> int:
    """Number of prescribed samples on each mock shock boundary."""

    return len(self.shock_ordinates_m)

  @staticmethod
  def _scheduled_scale_for_index(
    schedule_index: int,
    explicit_schedule: tuple[float, ...] | None,
    linear_step: float,
  ) -> float:
    """Resolve one scale during immutable configuration validation."""

    if explicit_schedule is not None:
      return explicit_schedule[schedule_index]
    return 1.0 + linear_step * schedule_index

  def _validate_continued_cell_index(self, cell_index: int) -> int:
    if (
      isinstance(cell_index, bool)
      or not isinstance(cell_index, int)
      or not 2 <= cell_index <= self.total_cell_count
    ):
      raise ValueError(
        'cell_index must identify a configured continued cell '
        f'(2 through {self.total_cell_count})'
      )
    return cell_index - 2

  def cell_axial_length_for_cell(self, cell_index: int) -> float:
    """Return the configured axial length for one continued cell."""

    schedule_index = self._validate_continued_cell_index(cell_index)
    if self.cell_axial_lengths_m is not None:
      return self.cell_axial_lengths_m[schedule_index]
    return float(self.cell_axial_length_m)

  def shock_start_offset_for_cell(self, cell_index: int) -> float:
    """Return the configured shock-start offset for one continued cell."""

    schedule_index = self._validate_continued_cell_index(cell_index)
    if self.shock_start_offsets_m is not None:
      return self.shock_start_offsets_m[schedule_index]
    return float(self.shock_start_offset_m)

  def shock_geometry_scale_for_cell(self, cell_index: int) -> float:
    """Return the deterministic geometry multiplier for one continued cell.

    The multiplier is a fixture control, not a solved shock-placement law.
    Keeping it behind a named method makes the scenario visible to report and
    visualization consumers while keeping the fidelity boundary explicit.
    """

    schedule_index = self._validate_continued_cell_index(cell_index)
    if self.shock_geometry_scales_per_cell is not None:
      scale = self.shock_geometry_scales_per_cell[schedule_index]
    else:
      scale = 1.0 + float(self.shock_geometry_scale_per_cell) * schedule_index
    if scale <= 0.0:
      raise ValueError(
        'shock_geometry_scale_per_cell produces a non-positive scale '
        f'at cell {cell_index}'
      )
    return scale

  def _resample_incoming_total_pressure(
    self,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> tuple[float, ...]:
    """Resample the prior pressure trace at the mock shock samples.

    The normalized-index interpolation is intentionally a named fixture
    policy. It preserves pressure variation for contract tests without
    pretending that the prescribed shock has a physically derived mapping to
    the prior perimeter.
    """

    pressures = tuple(sample.total_pressure_Pa for sample in incoming_handoff)
    if len(pressures) == self.sample_count:
      return pressures
    last_incoming_index = len(pressures) - 1
    last_shock_index = self.sample_count - 1
    return tuple(
      (
        pressures[lower_index]
        if lower_index == upper_index
        else pressures[lower_index]
        + (pressures[upper_index] - pressures[lower_index]) * fraction
      )
      for index in range(self.sample_count)
      for position in (index * last_incoming_index / last_shock_index,)
      for lower_index in (int(position),)
      for upper_index in (min(lower_index + 1, last_incoming_index),)
      for fraction in (position - lower_index,)
    )

  def as_report(self) -> dict[str, Any]:
    """Return explicit provenance and configuration for the fixture."""

    return {
      'model': 'prescribed-post-shock-chain-planner-mock',
      'planning_only': True,
      'production_claim_allowed': False,
      'claim_fidelity_ceiling': (
        MocChainGeometryFidelity.PRESCRIBED_BOUNDARY_DIAGNOSTIC.value
      ),
      'boundary_provenance': (
        'prescribed-shock-ordinates-and-downstream-flow-angle-samples'
      ),
      'local_field_assembly': (
        'solver-backed-attached-shock-fit-and-post-shock-characteristic-field'
      ),
      'free_boundary_verified': False,
      'physical_chain_promotion_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_sample_spacing_m': self.shock_sample_spacing_m,
      'shock_geometry_scale_per_cell': self.shock_geometry_scale_per_cell,
      'shock_geometry_scale_schedule': [
        {
          'cell_index': cell_index,
          'scale': self.shock_geometry_scale_for_cell(cell_index),
        }
        for cell_index in range(2, self.total_cell_count + 1)
      ],
      'cell_axial_lengths_m': self.cell_axial_lengths_m,
      'shock_start_offsets_m': self.shock_start_offsets_m,
      'shock_geometry_scales_per_cell': self.shock_geometry_scales_per_cell,
      'per_cell_geometry_schedule': [
        {
          'cell_index': cell_index,
          'axial_length_m': self.cell_axial_length_for_cell(cell_index),
          'shock_start_offset_m': self.shock_start_offset_for_cell(cell_index),
          'shock_geometry_scale': self.shock_geometry_scale_for_cell(cell_index),
        }
        for cell_index in range(2, self.total_cell_count + 1)
      ],
      'geometry_schedule_model': (
        'explicit-per-cell-schedule'
        if any(
          value is not None
          for value in (
            self.cell_axial_lengths_m,
            self.shock_start_offsets_m,
            self.shock_geometry_scales_per_cell,
          )
        )
        else 'global-values-with-linear-scale'
      ),
      'shock_ordinates_m': self.shock_ordinates_m,
      'downstream_flow_angles_rad': self.downstream_flow_angles_rad,
      'upstream_flow_angle_start_rad': self.upstream_flow_angle_start_rad,
      'upstream_flow_angle_step_rad': self.upstream_flow_angle_step_rad,
      'upstream_flow_angles_rad': self.upstream_flow_angles_rad,
      'mach': self.mach,
      'gamma': self.gamma,
      'pressure_loss_ratio': self.pressure_loss_ratio,
      'pressure_loss_ratio_role': (
        'optional expected total-pressure ratio; never used to fabricate '
        'post-shock states'
      ),
      'upstream_pressure_model': (
        'normalized-index-resampling-of-exact-incoming-handoff'
      ),
      'claim_status': (
        'prescribed-next-shock-geometry-fixture; '
        'not-free-boundary-chain-evidence'
      ),
    }

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Return one deterministic mock cell or an explicit fixture stop."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if isinstance(next_cell_index, bool) or next_cell_index != current.cell_index + 1:
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    handoff = tuple(incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    if len(handoff) < 3:
      raise ValueError('incoming_handoff requires at least three state samples')
    if handoff != current.continuation_boundary:
      raise ValueError('incoming_handoff must exactly match current.continuation_boundary')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'prescribed post-shock chain planner mock exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )
    upstream_total_pressures = self._resample_incoming_total_pressure(handoff)
    shock_geometry_scale = self.shock_geometry_scale_for_cell(next_cell_index)
    shock_start_x_m = current.end_x_m + self.shock_start_offset_for_cell(next_cell_index)
    shock_points = tuple(
      (
        shock_start_x_m
        + self.shock_sample_spacing_m * shock_geometry_scale * index,
        ordinate * shock_geometry_scale,
      )
      for index, ordinate in enumerate(self.shock_ordinates_m)
    )
    upstream_angles = self.upstream_flow_angles_rad
    if upstream_angles is None:
      raise ValueError('upstream_flow_angles_rad was not normalized by the fixture')
    upstream_states = tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=upstream_angles[index],
        mach=self.mach,
        gamma=self.gamma,
      )
      for index, point in enumerate(shock_points)
    )
    isentropic_factor = (
      1.0 + 0.5 * (self.gamma - 1.0) * self.mach**2
    ) ** (self.gamma / (self.gamma - 1.0))
    upstream_static_pressures = tuple(
      pressure / isentropic_factor
      for pressure in upstream_total_pressures
    )
    fit = fit_attached_shock_boundary(
      upstream_states,
      upstream_static_pressures,
      shock_points,
      self.downstream_flow_angles_rad,
      branch=ShockBranch.WEAK,
    )
    if not fit.converged:
      raise ValueError(
        'prescribed post-shock chain planner mock rejected its shock geometry '
        f'with the local attached-shock fit: {fit.message}'
      )
    # Use the solver-backed fit as the source of truth for the characteristic
    # field.  This prevents the mock from silently fabricating zero residuals
    # or a total-pressure loss across a cell.
    if any(
      abs(angle - fitted.state.theta_rad) > 1.0e-12
      for angle, fitted in zip(
        self.downstream_flow_angles_rad,
        fit.boundary_states,
        strict=True,
      )
    ):
      raise ValueError(
        'prescribed post-shock chain planner mock fit changed its requested '
        'downstream flow angles'
      )
    if self.pressure_loss_ratio is not None:
      fitted_pressure_ratios = tuple(
        sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
        for sample in fit.boundary_states
      )
      if any(
        abs(ratio - self.pressure_loss_ratio) > 1.0e-8
        for ratio in fitted_pressure_ratios
      ):
        raise ValueError(
          'prescribed pressure_loss_ratio disagrees with the attached-shock '
          'fit; omit it to accept solver-computed pressure loss'
        )
    field = assemble_post_shock_characteristic_field(
      fit,
      incoming_handoff=handoff,
    )
    if not field.converged:
      raise ValueError(
        'prescribed post-shock chain planner mock produced a non-converged '
        f'field: {field.message}'
      )
    return MocPostShockChainCellSolve(
      field=field,
      end_x_m=current.end_x_m + self.cell_axial_length_for_cell(next_cell_index),
    )


@dataclass(frozen=True, slots=True)
class MocSolverGeneratedPostShockChainReference:
  """Deterministic solver-generated reference for a continued MOC chain.

  Each step uses the real marched attached-shock solver and the real closed
  post-shock characteristic-field assembler.  The upstream state and the
  downstream turn law are deliberately simple, explicit reference inputs;
  they are not a reflected-plume free-boundary solution.  Keeping this
  reference beside the prescribed mock makes the distinction executable:
  both can exercise the chain handoff, but neither may raise a production
  provider claim.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.80
  shock_start_offset_m: float = 0.20
  shock_start_y_m: float = 0.50
  sample_count: int = 9
  mach: float = 2.0
  gamma: float = 1.4
  upstream_flow_angle_rad: float = -0.20
  downstream_flow_angle_scale_rad_per_m: float = 0.10
  target_centerline_y_m: float = 0.0
  branch: ShockBranch = ShockBranch.WEAK

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_start_y_m', self.shock_start_y_m),
      ('mach', self.mach),
      ('gamma', self.gamma),
      ('upstream_flow_angle_rad', self.upstream_flow_angle_rad),
      (
        'downstream_flow_angle_scale_rad_per_m',
        self.downstream_flow_angle_scale_rad_per_m,
      ),
      ('target_centerline_y_m', self.target_centerline_y_m),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    if self.cell_axial_length_m <= 0.0:
      raise ValueError('cell_axial_length_m must be finite and positive')
    if self.shock_start_offset_m <= 0.0:
      raise ValueError('shock_start_offset_m must be finite and positive')
    if self.shock_start_y_m <= 0.0:
      raise ValueError('shock_start_y_m must be finite and positive')
    if self.shock_start_y_m <= self.target_centerline_y_m:
      raise ValueError(
        'shock_start_y_m must be strictly above target_centerline_y_m'
      )
    if self.mach <= 1.0:
      raise ValueError('mach must be finite and greater than one')
    if self.gamma <= 1.0:
      raise ValueError('gamma must be finite and greater than one')
    if not isinstance(self.branch, ShockBranch):
      raise ValueError('branch must be a ShockBranch')

  def as_report(self) -> dict[str, Any]:
    """Return configuration and the explicit research-only claim ceiling."""

    return {
      'model': 'solver-generated-post-shock-chain-reference',
      'planning_only': True,
      'production_claim_allowed': False,
      'claim_fidelity_ceiling': (
        MocChainGeometryFidelity.RESOLVED_PLANAR_MOC.value
      ),
      'free_boundary_verified': False,
      'physical_chain_promotion_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_start_y_m': self.shock_start_y_m,
      'target_centerline_y_m': self.target_centerline_y_m,
      'sample_count': self.sample_count,
      'mach': self.mach,
      'gamma': self.gamma,
      'upstream_flow_angle_rad': self.upstream_flow_angle_rad,
      'downstream_flow_angle_scale_rad_per_m': (
        self.downstream_flow_angle_scale_rad_per_m
      ),
      'branch': self.branch.value,
      'upstream_state_model': 'uniform-explicit-reference-state',
      'upstream_pressure_model': (
        'normalized-shock-height-resampling-of-exact-incoming-handoff'
      ),
      'downstream_condition_model': 'linear-explicit-reference-turn-law',
      'claim_status': (
        'solver-generated-shock-and-closed-post-shock-field-reference; '
        'reflected-upstream-coupling-and-physical-boundary-pending'
      ),
    }

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Solve one reference cell from the exact prior state/pressure handoff."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if (
      isinstance(next_cell_index, bool)
      or next_cell_index != current.cell_index + 1
    ):
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    handoff = tuple(incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    if len(handoff) < 3:
      raise ValueError('incoming_handoff requires at least three state samples')
    if handoff != current.continuation_boundary:
      raise ValueError('incoming_handoff must exactly match current.continuation_boundary')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'solver-generated post-shock reference exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )

    incoming_total_pressure_trace = self._resample_incoming_total_pressure(handoff)
    isentropic_factor = (
      1.0 + 0.5 * (self.gamma - 1.0) * self.mach * self.mach
    ) ** (self.gamma / (self.gamma - 1.0))
    shock_start = (
      current.end_x_m + self.shock_start_offset_m,
      self.shock_start_y_m,
    )
    result = solve_marched_attached_shock_chain_cell(
      current,
      next_cell_index,
      handoff,
      start_point_m=shock_start,
      end_x_m=current.end_x_m + self.cell_axial_length_m,
      upstream_state_at=lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=self.upstream_flow_angle_rad,
        mach=self.mach,
        gamma=self.gamma,
      ),
      upstream_pressure_at=lambda point: (
        self._upstream_pressure_at(
          point,
          incoming_total_pressure_trace,
        ) / isentropic_factor
      ),
      target_centerline_y_m=self.target_centerline_y_m,
      downstream_flow_angle_at=(
        lambda _index, point: (
          self.downstream_flow_angle_scale_rad_per_m * point[1]
        )
      ),
      sample_count=self.sample_count,
      branch=self.branch,
    )
    return result

  def _resample_incoming_total_pressure(
    self,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> tuple[float, ...]:
    """Resample the complete prior pressure trace for this reference solve.

    The reference has no physical mapping from the prior perimeter to the
    next shock.  Normalized-index interpolation is therefore retained as an
    explicit fixture policy, but it preserves pressure variation instead of
    collapsing the handoff to its maximum value.
    """

    pressures = tuple(sample.total_pressure_Pa for sample in incoming_handoff)
    if len(pressures) == self.sample_count:
      return pressures
    last_incoming_index = len(pressures) - 1
    last_shock_index = self.sample_count - 1
    return tuple(
      (
        pressures[lower_index]
        if lower_index == upper_index
        else pressures[lower_index]
        + (pressures[upper_index] - pressures[lower_index]) * fraction
      )
      for index in range(self.sample_count)
      for position in (index * last_incoming_index / last_shock_index,)
      for lower_index in (int(position),)
      for upper_index in (min(lower_index + 1, last_incoming_index),)
      for fraction in (position - lower_index,)
    )

  def _upstream_pressure_at(
    self,
    point: tuple[float, float],
    incoming_total_pressure_trace: tuple[float, ...],
  ) -> float:
    """Return a height-interpolated pressure from the preserved handoff."""

    span = self.shock_start_y_m - self.target_centerline_y_m
    normalized_height = (
      self.shock_start_y_m - float(point[1])
    ) / span
    normalized_height = min(1.0, max(0.0, normalized_height))
    position = normalized_height * (len(incoming_total_pressure_trace) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(incoming_total_pressure_trace) - 1)
    fraction = position - lower_index
    return (
      incoming_total_pressure_trace[lower_index]
      + (
        incoming_total_pressure_trace[upper_index]
        - incoming_total_pressure_trace[lower_index]
      ) * fraction
    )


@dataclass(frozen=True, slots=True)
class MocFieldCoupledPostShockChainReference:
  """Deterministic reference for continuation fed by the prior solved field.

  This reference deliberately differs from
  :class:`MocSolverGeneratedPostShockChainReference`: its upstream state and
  pressure are sampled from the currently accepted bounded
  ``MocPostShockCharacteristicFieldResult``.  The start point, axial step,
  and downstream turn law remain explicit reference conditions.  A finite
  field boundary therefore becomes a typed stop instead of an opportunity to
  fall back to a uniform state.

  The class is a research/planner fixture.  It does not claim that the
  supplied field is the canonical reflected upstream plume domain.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.40
  shock_start_offset_m: float = 0.02
  shock_start_y_m: float = 0.05
  target_centerline_y_m: float = 0.0
  sample_count: int = 9
  downstream_flow_angle_scale_rad_per_m: float = 2.40
  branch: ShockBranch = ShockBranch.WEAK

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_start_y_m', self.shock_start_y_m),
      ('target_centerline_y_m', self.target_centerline_y_m),
      (
        'downstream_flow_angle_scale_rad_per_m',
        self.downstream_flow_angle_scale_rad_per_m,
      ),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    if self.cell_axial_length_m <= 0.0:
      raise ValueError('cell_axial_length_m must be finite and positive')
    if self.shock_start_offset_m <= 0.0:
      raise ValueError('shock_start_offset_m must be finite and positive')
    if self.shock_start_y_m <= self.target_centerline_y_m:
      raise ValueError(
        'shock_start_y_m must be strictly above target_centerline_y_m'
      )
    if self.downstream_flow_angle_scale_rad_per_m <= 0.0:
      raise ValueError(
        'downstream_flow_angle_scale_rad_per_m must be finite and positive'
      )
    if not isinstance(self.branch, ShockBranch):
      raise ValueError('branch must be a ShockBranch')

  def as_report(self) -> dict[str, Any]:
    """Return the explicit bounded-field reference configuration."""

    return {
      'model': 'field-coupled-post-shock-chain-reference',
      'planning_only': True,
      'production_claim_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_start_y_m': self.shock_start_y_m,
      'target_centerline_y_m': self.target_centerline_y_m,
      'sample_count': self.sample_count,
      'downstream_flow_angle_scale_rad_per_m': (
        self.downstream_flow_angle_scale_rad_per_m
      ),
      'branch': self.branch.value,
      'upstream_state_model': 'bounded-previous-post-shock-field',
      'upstream_pressure_model': 'bounded-previous-post-shock-field',
      'downstream_condition_model': 'linear-explicit-reference-turn-law',
      'claim_status': (
        'field-coupled-research-reference; canonical-reflected-domain-and-'
        'physical-downstream-boundary-pending'
      ),
    }

  def start_point_at(
    self,
    _field: MocPostShockCharacteristicFieldResult,
    current: MocChainCell,
    _next_cell_index: int,
  ) -> tuple[float, float]:
    """Choose the next reference shock start downstream of the current cell."""

    return (
      current.end_x_m + self.shock_start_offset_m,
      self.shock_start_y_m,
    )

  def end_x_at(
    self,
    _field: MocPostShockCharacteristicFieldResult,
    current: MocChainCell,
    _next_cell_index: int,
  ) -> float:
    """Return the deterministic axial endpoint for one reference cell."""

    return current.end_x_m + self.cell_axial_length_m

  def downstream_flow_angle_at(
    self,
    _index: int,
    point_m: tuple[float, float],
  ) -> float:
    """Return the explicit linear turn law, zero at the target centerline."""

    return self.downstream_flow_angle_scale_rad_per_m * (
      point_m[1] - self.target_centerline_y_m
    )

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
    upstream_field: MocPostShockCharacteristicFieldResult,
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Solve one cell from the exact bounded prior field, or return a stop."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if (
      isinstance(next_cell_index, bool)
      or not isinstance(next_cell_index, int)
      or next_cell_index != current.cell_index + 1
    ):
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'field-coupled post-shock reference exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )
    return solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      upstream_field,
      start_point_m=self.start_point_at(
        upstream_field,
        current,
        next_cell_index,
      ),
      end_x_m=self.end_x_at(upstream_field, current, next_cell_index),
      target_centerline_y_m=self.target_centerline_y_m,
      downstream_flow_angle_at=self.downstream_flow_angle_at,
      sample_count=self.sample_count,
      branch=self.branch,
    )


def plan_prescribed_post_shock_chain_mock(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  mock: MocPrescribedPostShockChainMock | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the reusable planning-only prescribed post-shock chain fixture."""

  fixture = MocPrescribedPostShockChainMock() if mock is None else mock
  if not isinstance(fixture, MocPrescribedPostShockChainMock):
    raise TypeError('mock must be a MocPrescribedPostShockChainMock')
  planner = plan_post_shock_characteristic_chain(
    seed,
    fixture.solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    planner_kind=MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK,
  )
  return replace(
    planner,
    diagnostics={
      'prescribed_chain_mock': fixture.as_report(),
    },
  )


def plan_solver_generated_post_shock_chain_reference(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocSolverGeneratedPostShockChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the reusable solver-generated, research-only chain reference."""

  fixture = (
    MocSolverGeneratedPostShockChainReference()
    if reference is None
    else reference
  )
  if not isinstance(fixture, MocSolverGeneratedPostShockChainReference):
    raise TypeError(
      'reference must be a MocSolverGeneratedPostShockChainReference'
    )
  planner = plan_post_shock_characteristic_chain(
    seed,
    fixture.solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  )
  return replace(
    planner,
    diagnostics={
      'solver_generated_chain_reference': fixture.as_report(),
    },
  )


def plan_field_coupled_post_shock_chain_reference(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocFieldCoupledPostShockChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the bounded prior-field-fed, research-only chain reference."""

  fixture = (
    MocFieldCoupledPostShockChainReference()
    if reference is None
    else reference
  )
  if not isinstance(fixture, MocFieldCoupledPostShockChainReference):
    raise TypeError(
      'reference must be a MocFieldCoupledPostShockChainReference'
    )
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    solved = fixture.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-field-coupled-shock-chain-reference; '
      'canonical-reflected-domain-and-physical-downstream-boundary-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'field_coupled_chain_reference': fixture.as_report(),
      'upstream_field_replacement_policy': (
        'replace-only-after-complete-field-coupled-solve'
      ),
    },
  )
####


def _default_claim_status(kind: MocChainPlannerKind) -> str:
  return {
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK: (
      'deterministic-prescribed-next-shock-planner-mock; not-free-boundary-chain-evidence'
    ),
    MocChainPlannerKind.SOLVER_GENERATED_REFERENCE: (
      'solver-generated-chain-reference; physical-free-boundary-validation-pending'
    ),
    MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH: (
      'upstream-coupled-research-chain; external-validation-and-product-promotion-pending'
    ),
  }[kind]
####


def plan_moc_chain(
  seed: MocChainCell,
  solve_next: MocCellContinuationSolver,
  *,
  policy: MocChainContinuationPolicy | None = None,
  planner_kind: MocChainPlannerKind = MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Run the generic chain contract while recording every planned handoff."""

  steps: list[MocChainPlannerStep] = []

  def wrapped(current: MocChainCell, next_cell_index: int):
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      current.continuation_boundary,
      previous_result_handoff_fingerprint=(
        steps[-1].result_handoff_fingerprint if steps else None
      ),
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

  chain = continue_moc_cell_chain(seed, wrapped, policy)
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=planner_kind,
    steps=tuple(steps),
    claim_status=(
      _default_claim_status(planner_kind)
      if claim_status is None
      else claim_status
    ),
  )
####


def plan_terminal_reflection_patch_chain(
  seed: MocChainCell,
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 2.0e-4,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one terminal-reflection handoff through the generic chain audit.

  A terminal reflection patch is a finite upstream domain for one next-shock
  solve, not a reusable downstream field for an arbitrary number of later
  cells.  This wrapper therefore allows the adapter to be invoked once and
  records any returned cell or typed termination through ``plan_moc_chain``.
  A second callback invocation receives an explicit non-physical solver stop
  rather than reusing the terminal patch outside its solved domain.
  """

  if not isinstance(patch, MocTerminalReflectionPatchResult):
    raise TypeError('patch must be a MocTerminalReflectionPatchResult')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'terminal reflection patch planner completed its one-step domain; '
          'a later cell requires a new upstream field and solver adapter'
        ),
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      patch,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  return plan_moc_chain(
    seed,
    solve_next,
    policy=policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'terminal-reflection-patch-planner-handoff; '
      'one-step-domain; mixed-regime-or-new-field-continuation-pending'
    ),
  )


def plan_post_shock_zone_chain(
  seed: MocChainCell,
  post_shock_zone: MocPostShockCharacteristicZoneResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one next shock against a bounded open post-shock zone.

  The open zone is a finite solver interface, not a resolved chain cell.  It
  can therefore be consumed for one next-shock attempt only.  A completely
  covered shock plus closed downstream field is returned as a resolved
  research cell; a zone boundary, subsonic terminal, or solver failure is
  retained as the typed planner stop.  The planner never reuses the original
  open zone for a later cell and never changes its research-only claim.
  """

  if not isinstance(post_shock_zone, MocPostShockCharacteristicZoneResult):
    raise TypeError(
      'post_shock_zone must be a MocPostShockCharacteristicZoneResult'
    )
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'open post-shock zone planner completed its one-step upstream '
          'domain; a later cell requires a newly solved bounded field'
        ),
        diagnostics={
          'termination_model': 'open-post-shock-zone-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      post_shock_zone,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-open-post-shock-zone-next-shock-planner; '
      'one-step-domain-and-physical-downstream-closure-pending'
    ),
  )


def plan_caustic_family_band_chain(
  seed: MocChainCell,
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one caustic-band-to-shock handoff through the chain audit.

  The caustic band is a finite upstream field for one next-shock solve.  Its
  current solver result ends at an open mixed-regime boundary, so a successful
  attempt produces an explicit non-physical ``OPEN_PHYSICAL_CLOSURE`` stop.
  The planner never reuses that band for a second cell and never promotes the
  open terminal field as a resolved chain cell.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic-family band planner completed its one-step upstream '
          'domain; a later cell requires a new family or post-shock field'
        ),
        diagnostics={
          'termination_model': 'caustic-family-band-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      band,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-family-band-next-shock-planner; '
      'open-mixed-regime-closure-and-external-validation-pending'
    ),
  )
####


def plan_caustic_origin_envelope_chain(
  seed: MocChainCell,
  band: MocCausticFamilyBandResult,
  *,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  position_tolerance_m: float = 1.0e-10,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Audit a caustic-origin reachability attempt at a chain boundary.

  The weak attached forward envelope is a pre-shock remeshing diagnostic.  It
  can return a typed ``CHARACTERISTIC_CAUSTIC`` stop when the finite family
  band ends before the centerline, but it can never append an envelope as a
  resolved chain cell.  The planner permits one finite-domain attempt and
  records the exact prior handoff before invoking the probe.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic-origin envelope planner completed its one-step remesh '
          'diagnostic; a later cell requires a physically solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-origin-envelope-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    envelope = trace_caustic_family_band_forward_envelope(
      band,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      position_tolerance_m=position_tolerance_m,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if (
      envelope.status
      is MocCausticFamilyBandEnvelopeStatus.CENTERLINE_UNREACHABLE
    ):
      return envelope.as_chain_termination_decision()
    if envelope.status is MocCausticFamilyBandEnvelopeStatus.INVALID_INPUT:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message=envelope.message,
        diagnostics={
          'termination_model': 'caustic-origin-envelope-invalid-input',
          'envelope_status': envelope.status.value,
        },
      )
    if envelope.converged:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'caustic-origin forward envelope reached the centerline, but no '
          'shock curve, downstream field, or mixed-regime closure was solved'
        ),
        diagnostics={
          'termination_model': 'caustic-origin-envelope-reachability-only',
          'envelope_status': envelope.status.value,
          'envelope_sample_count': envelope.sample_count,
        },
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=envelope.message,
      diagnostics={
        'termination_model': 'caustic-origin-envelope-probe-failure',
        'envelope_status': envelope.status.value,
      },
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-origin-forward-envelope-planner; physical-remesh-and-'
      'shock-closure-pending'
    ),
  )
####


def plan_caustic_family_band_invariant_chain(
  seed: MocChainCell,
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float],
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan an invariant-conditioned caustic shock-chain continuation.

  The planner records the exact prior handoff and permits at most the finite
  family-band domain to be consumed.  Its provenance is always
  ``UPSTREAM_COUPLED_RESEARCH`` and its production claim remains disabled,
  even if a future remeshed band allows the local field to converge.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'invariant-conditioned caustic-band planner consumed its one-step '
          'upstream domain; a later cell requires a new upstream field'
        ),
        diagnostics={
          'termination_model': 'invariant-caustic-band-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      band,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_at=downstream_invariant_at,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'invariant-conditioned-caustic-band-shock-planner; '
      'one-sided-upstream-domain-and-physical-remesh-pending'
    ),
  )


def plan_caustic_upstream_bridge_chain(
  seed: MocChainCell,
  bridge: MocCausticUpstreamBridge,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a one-step shock attempt across an explicit caustic bridge.

  The bridge is a finite upstream sampling domain, not a reusable chain
  field.  This planner records the exact incoming handoff, maps a bounded
  domain gap or ambiguous overlap to a typed non-physical stop, and never
  promotes the bridge's open physical seam into a resolved cell.
  """

  if not isinstance(bridge, MocCausticUpstreamBridge):
    raise TypeError('bridge must be a MocCausticUpstreamBridge')
  try:
    requested_end_x = float(end_x_m)
  except (TypeError, ValueError) as error:
    raise ValueError('end_x_m must be finite and numeric') from error
  if not isfinite(requested_end_x):
    raise ValueError('end_x_m must be finite')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic upstream bridge planner consumed its one-step bounded '
          'domain; a later cell requires a new solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-upstream-bridge-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_from_caustic_upstream_bridge(
      bridge,
      start_point_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      incoming_handoff=current.continuation_boundary,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    diagnostics = {
      'termination_model': 'caustic-upstream-bridge',
      'upstream_field_model': 'bounded-old-family-restarted-family-bridge',
      'next_cell_index': next_cell_index,
      'requested_end_x_m': requested_end_x,
      'bridge_status': solved.coupling.status.value,
      'bridge_sampled_count': solved.coupling.sampled_count,
      'bridge_first_missing_sample_index': solved.coupling.first_missing_sample_index,
      'bridge_first_missing_point_m': solved.coupling.first_missing_point_m,
      'bridge_first_ambiguous_sample_index': solved.coupling.first_ambiguous_sample_index,
      'upstream_coupling_verified': solved.upstream_coupling_verified,
      'physical_closure_verified': solved.physical_closure_verified,
      'bridge_report': solved.coupling.as_report(),
      'shock_status': solved.shock.status.value,
    }
    if solved.coupling.status is MocCausticBridgeStatus.AMBIGUOUS_OVERLAP:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.CHARACTERISTIC_CAUSTIC,
        message=(
          'caustic bridge encountered overlapping one-sided fields without '
          'an explicit branch selection; no state was averaged'
        ),
        diagnostics=diagnostics,
      )
    if solved.coupling.status in (
      MocCausticBridgeStatus.DOMAIN_GAP,
      MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP,
      MocCausticBridgeStatus.FIELD_INPUT_FAILURE,
    ):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'caustic upstream bridge did not cover the next-shock path; no '
          'extrapolation or physical endpoint was inferred'
        ),
        diagnostics=diagnostics,
      )
    if not solved.upstream_coupling_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=(
          'caustic bridge shock solve did not retain a complete bounded '
          'upstream handoff; no next cell was promoted'
        ),
        diagnostics=diagnostics,
      )
    if solved.shock.field is not None:
      expected_states = tuple(sample.state for sample in current.continuation_boundary)
      expected_pressures = tuple(
        sample.total_pressure_Pa for sample in current.continuation_boundary
      )
      if (
        solved.shock.field.incoming_handoff_states != expected_states
        or solved.shock.field.incoming_handoff_total_pressure_Pa != expected_pressures
      ):
        diagnostics['upstream_coupling_verified'] = False
        return MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.STATE_NOT_CARRIED,
          message=(
            'caustic bridge shock field did not retain the exact incoming '
            'chain handoff'
          ),
          diagnostics=diagnostics,
        )
    if solved.shock.converged or solved.shock.terminal_model_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'caustic bridge supplied a bounded shock attempt, but the physical '
          'old-family/new-family seam and downstream cell closure remain '
          'unresolved; no cell was promoted'
        ),
        diagnostics=diagnostics,
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'caustic bridge shock solve did not produce a complete next cell; no '
        'physical endpoint was inferred'
      ),
      diagnostics=diagnostics,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-upstream-bridge-planner; physical-remesh-and-downstream-'
      'closure-pending'
    ),
  )


def plan_caustic_upstream_bridge_invariant_chain(
  seed: MocChainCell,
  bridge: MocCausticUpstreamBridge,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float],
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan an invariant-conditioned one-step caustic bridge shock attempt."""

  if not isinstance(bridge, MocCausticUpstreamBridge):
    raise TypeError('bridge must be a MocCausticUpstreamBridge')
  try:
    requested_end_x = float(end_x_m)
  except (TypeError, ValueError) as error:
    raise ValueError('end_x_m must be finite and numeric') from error
  if not isfinite(requested_end_x):
    raise ValueError('end_x_m must be finite')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'invariant caustic bridge planner consumed its one-step bounded '
          'domain; a later cell requires a new solved upstream field'
        ),
        diagnostics={
          'termination_model': 'invariant-caustic-upstream-bridge-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary(
      bridge,
      start_point_m,
      downstream_invariant_family,
      downstream_invariant_at,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=current.continuation_boundary,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
    diagnostics = {
      'termination_model': 'invariant-caustic-upstream-bridge',
      'upstream_field_model': 'bounded-old-family-restarted-family-bridge',
      'next_cell_index': next_cell_index,
      'requested_end_x_m': requested_end_x,
      'invariant_family': downstream_invariant_family.value,
      'bridge_status': solved.coupling.status.value,
      'bridge_sampled_count': solved.coupling.sampled_count,
      'bridge_first_missing_sample_index': solved.coupling.first_missing_sample_index,
      'bridge_first_missing_point_m': solved.coupling.first_missing_point_m,
      'bridge_first_ambiguous_sample_index': solved.coupling.first_ambiguous_sample_index,
      'upstream_coupling_verified': solved.upstream_coupling_verified,
      'physical_closure_verified': solved.physical_closure_verified,
      'bridge_report': solved.coupling.as_report(),
      'shock_status': solved.shock.status.value,
    }
    if solved.coupling.status is MocCausticBridgeStatus.AMBIGUOUS_OVERLAP:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.CHARACTERISTIC_CAUSTIC,
        message=(
          'invariant caustic bridge encountered overlapping one-sided fields '
          'without explicit branch selection; no state was averaged'
        ),
        diagnostics=diagnostics,
      )
    if solved.coupling.status in (
      MocCausticBridgeStatus.DOMAIN_GAP,
      MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP,
      MocCausticBridgeStatus.FIELD_INPUT_FAILURE,
    ):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'invariant caustic bridge did not cover the next-shock path; no '
          'extrapolation or physical endpoint was inferred'
        ),
        diagnostics=diagnostics,
      )
    if solved.coupling.status is MocCausticBridgeStatus.PATH_GEOMETRY_FAILURE:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message='invariant caustic bridge rejected the shock-path geometry',
        diagnostics=diagnostics,
      )
    if not solved.upstream_coupling_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=(
          'invariant caustic bridge shock solve did not retain a complete '
          'upstream handoff; no next cell was promoted'
        ),
        diagnostics=diagnostics,
      )
    if solved.shock.field is not None:
      expected_states = tuple(sample.state for sample in current.continuation_boundary)
      expected_pressures = tuple(
        sample.total_pressure_Pa for sample in current.continuation_boundary
      )
      if (
        solved.shock.field.incoming_handoff_states != expected_states
        or solved.shock.field.incoming_handoff_total_pressure_Pa != expected_pressures
      ):
        diagnostics['upstream_coupling_verified'] = False
        return MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.STATE_NOT_CARRIED,
          message='invariant caustic bridge shock field did not retain the exact incoming handoff',
          diagnostics=diagnostics,
        )
    if solved.shock.converged or solved.shock.terminal_model_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'invariant caustic bridge supplied a bounded shock attempt, but the '
          'physical branch seam and downstream cell closure remain unresolved'
        ),
        diagnostics=diagnostics,
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'invariant caustic bridge shock solve did not produce a complete next '
        'cell; no physical endpoint was inferred'
      ),
      diagnostics=diagnostics,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'invariant-caustic-upstream-bridge-planner; physical-remesh-and-'
      'downstream-closure-pending'
    ),
  )


def plan_caustic_shock_remesh_chain(
  seed: MocChainCell,
  request: MocCausticShockRemeshRequest,
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  *,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
  _upstream_bridge: MocCausticUpstreamBridge | None = None,
) -> MocChainPlannerResult:
  """Plan one solver-backed caustic shock/new-family remesh attempt.

  The request identifies the exact one-sided caustic event and local shock
  compatibility state.  The current chain cell supplies the exact carried
  perimeter to the remesher.  A converged remesh is intentionally returned as
  an ``OPEN_PHYSICAL_CLOSURE`` stop: it produces a bounded shock and new
  characteristic field, but ambient/terminal closure for the new physical
  cell remains a separate first-cell gate.  The planner therefore never
  appends a remesh result as a chain cell.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    raise TypeError('request must be a MocCausticShockRemeshRequest')
  if not callable(upstream_state_at):
    raise TypeError('upstream_state_at must be callable')
  if not callable(upstream_pressure_at):
    raise TypeError('upstream_pressure_at must be callable')
  if downstream_invariant_at is not None and not callable(downstream_invariant_at):
    raise TypeError('downstream_invariant_at must be callable when supplied')
  if _upstream_bridge is not None and not isinstance(
    _upstream_bridge,
    MocCausticUpstreamBridge,
  ):
    raise TypeError('_upstream_bridge must be a MocCausticUpstreamBridge when supplied')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')

  attempted = False

  def remesh_decision(
    result: MocCausticShockRemeshResult,
    next_cell_index: int,
  ) -> MocChainTerminationDecision:
    decision = result.as_chain_termination_decision()
    diagnostics = dict(decision.diagnostics)
    diagnostics.update({
      'planner_model': 'caustic-shock-remesh-one-step-domain',
      'next_cell_index': next_cell_index,
      'remesh_report': result.as_report(),
    })
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=decision.reason,
      message=decision.message,
      diagnostics=diagnostics,
    )

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic shock remesh planner completed its one-step domain; a '
          'later cell requires a newly closed physical upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-shock-remesh-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    event_x = request.event_point_m[0]
    if event_x < current.end_x_m - float(position_tolerance_m):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'caustic remesh event lies upstream of the current chain cell '
          'boundary; the planner will not back-extrapolate the handoff'
        ),
        diagnostics={
          'termination_model': 'caustic-shock-remesh-one-step-domain',
          'event_point_m': request.event_point_m,
          'current_end_x_m': current.end_x_m,
          'next_cell_index': next_cell_index,
        },
      )
    if _upstream_bridge is None:
      result = solve_caustic_shock_remesh(
        request,
        upstream_state_at,
        upstream_pressure_at,
        current.continuation_boundary,
        downstream_invariant_at=downstream_invariant_at,
        target_centerline_y_m=target_centerline_y_m,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_downstream_angle_rad=maximum_downstream_angle_rad,
        maximum_invariant_scan_samples=maximum_invariant_scan_samples,
        maximum_invariant_iterations=maximum_invariant_iterations,
      )
    else:
      result = solve_caustic_shock_remesh_from_upstream_bridge(
        request,
        _upstream_bridge,
        current.continuation_boundary,
        downstream_invariant_at=downstream_invariant_at,
        target_centerline_y_m=target_centerline_y_m,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_downstream_angle_rad=maximum_downstream_angle_rad,
        maximum_invariant_scan_samples=maximum_invariant_scan_samples,
        maximum_invariant_iterations=maximum_invariant_iterations,
      )
    return remesh_decision(result, next_cell_index)

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  planner = plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-shock-remesh-planner; solver-backed shock/new-family field '
      'with physical-first-cell-closure-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'caustic_shock_remesh_request': request.as_report(),
      'one_step_domain': True,
      'physical_closure_pending': True,
      'upstream_field_model': (
        'bounded-old-family-restarted-family-bridge'
        if _upstream_bridge is not None
        else 'callback-owned-upstream-field'
      ),
    },
  )


def plan_caustic_simple_wave_terminal_chain(
  seed: MocChainCell,
  request: MocCausticShockRemeshRequest,
  *,
  upstream_invariant_family: CharacteristicFamily = CharacteristicFamily.MINUS,
  target_centerline_y_m: float = 0.0,
  upstream_centerline_flow_angle_rad: float = 0.0,
  downstream_centerline_flow_angle_rad: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  maximum_x_m: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one solver-owned simple-wave caustic terminal attempt.

  The simple-wave lane is intentionally one-step.  It gives the planner a
  real attached-shock prefix, open post-shock characteristic zone, and typed
  normal-shock terminal to audit, but it never appends the open result as a
  resolved chain cell.  A later supersonic cell needs a physically closed
  mixed-regime handoff and a newly solved upstream field.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    raise TypeError('request must be a MocCausticShockRemeshRequest')
  if downstream_flow_angle_at is not None and not callable(downstream_flow_angle_at):
    raise TypeError('downstream_flow_angle_at must be callable when supplied')
  if not isinstance(branch, ShockBranch):
    raise TypeError('branch must be a ShockBranch')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 5:
    raise ValueError('sample_count must be an integer of at least five')

  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'simple-wave caustic terminal planner completed its one-step '
          'domain; a later cell requires a new solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-simple-wave-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    event_x = request.event_point_m[0]
    if event_x < current.end_x_m - float(position_tolerance_m):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'simple-wave caustic event lies upstream of the current chain cell '
          'boundary; the planner will not back-extrapolate the handoff'
        ),
        diagnostics={
          'termination_model': 'caustic-simple-wave-one-step-domain',
          'event_point_m': request.event_point_m,
          'current_end_x_m': current.end_x_m,
          'next_cell_index': next_cell_index,
        },
      )
    result = solve_caustic_simple_wave_terminal_remesh(
      request,
      current.continuation_boundary,
      upstream_invariant_family=upstream_invariant_family,
      target_centerline_y_m=target_centerline_y_m,
      upstream_centerline_flow_angle_rad=upstream_centerline_flow_angle_rad,
      downstream_centerline_flow_angle_rad=downstream_centerline_flow_angle_rad,
      downstream_flow_angle_at=downstream_flow_angle_at,
      maximum_x_m=maximum_x_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    decision = result.as_chain_termination_decision()
    diagnostics = dict(decision.diagnostics)
    diagnostics.update({
      'planner_model': 'caustic-simple-wave-terminal-one-step-domain',
      'next_cell_index': next_cell_index,
      'simple_wave_terminal_report': result.as_report(),
      'upstream_field_model': 'solver-owned-constant-invariant-simple-wave-trace',
      'physical_closure_pending': True,
    })
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=decision.reason,
      message=decision.message,
      diagnostics=diagnostics,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  planner = plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-simple-wave-terminal planner; solver-owned simple-wave trace '
      'with open mixed-regime closure and physical-remesh validation pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'caustic_shock_remesh_request': request.as_report(),
      'one_step_domain': True,
      'physical_closure_pending': True,
      'upstream_field_model': 'solver-owned-constant-invariant-simple-wave-trace',
      'simple_wave_invariant_family': upstream_invariant_family.value,
      'simple_wave_target_centerline_y_m': target_centerline_y_m,
    },
  )


def plan_caustic_shock_remesh_chain_from_upstream_bridge(
  seed: MocChainCell,
  request: MocCausticShockRemeshRequest,
  bridge: MocCausticUpstreamBridge,
  *,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a caustic remesh using the strict bounded upstream bridge."""

  if not isinstance(bridge, MocCausticUpstreamBridge):
    raise TypeError('bridge must be a MocCausticUpstreamBridge')
  planner = plan_caustic_shock_remesh_chain(
    seed,
    request,
    bridge.state_at,
    bridge.static_pressure_at,
    downstream_invariant_at=downstream_invariant_at,
    target_centerline_y_m=target_centerline_y_m,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    maximum_invariant_iterations=maximum_invariant_iterations,
    policy=policy,
    _upstream_bridge=bridge,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'upstream_field_model': 'bounded-old-family-restarted-family-bridge',
    'strict_bridge_required': True,
  })
  return replace(
    planner,
    claim_status=(
      'caustic-shock-remesh strict bridge planner; physical-first-cell-'
      'closure-pending'
    ),
    diagnostics=diagnostics,
  )


def plan_caustic_remesh_downstream_field_chain(
  remesh: MocCausticShockRemeshResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
  allow_research_continuation: bool = False,
) -> MocChainPlannerResult:
  """Continue a converged caustic remesh field in an explicit research lane.

  A coupled caustic remesh produces a bounded post-shock field, but the
  remesh result itself is not a physically closed chain cell: the
  old-family/new-family and downstream physical-boundary claim remains open.
  This wrapper makes the next numerical experiment available without
  weakening that gate.  The caller must explicitly opt into the research
  continuation, and the returned planner remains
  ``UPSTREAM_COUPLED_RESEARCH`` with production claims disabled.

  The remesh field is accepted only after its event, upstream, shock, and
  downstream characteristic-field seam checks pass.  Subsequent cells use
  the existing bounded field-coupled solver; the accepted field is replaced
  only after a complete next-cell solve returns.
  """

  if not isinstance(remesh, MocCausticShockRemeshResult):
    raise TypeError('remesh must be a MocCausticShockRemeshResult')
  if not isinstance(allow_research_continuation, bool):
    raise TypeError('allow_research_continuation must be a bool')
  if not allow_research_continuation:
    raise ValueError(
      'caustic remesh field continuation requires explicit '
      'allow_research_continuation=True; production promotion remains blocked'
    )
  field = remesh.as_bounded_downstream_field()
  planner = plan_post_shock_field_chain(
    field,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    start_point_at=start_point_at,
    end_x_at=end_x_at,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'caustic_remesh_continuation': remesh.as_report(),
    'seed_field_model': 'bounded-caustic-remesh-post-shock-field',
    'research_continuation_opt_in': allow_research_continuation,
    'remesh_physical_closure_verified': remesh.physical_closure_verified,
    'remesh_chain_promotion_blocked': remesh.chain_promotion_blocked,
    'upstream_field_replacement_policy': (
      'replace-only-after-complete-field-coupled-solve'
    ),
  })
  return replace(
    planner,
    claim_status=(
      'caustic-remesh-downstream-field research chain; '
      'old-family-seam-and-physical-boundary-pending'
    ),
    diagnostics=diagnostics,
  )


def plan_caustic_remesh_downstream_field_invariant_chain(
  remesh: MocCausticShockRemeshResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[
    [MocPostShockCharacteristicFieldResult, int, tuple[float, float]],
    float,
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
  allow_research_continuation: bool = False,
) -> MocChainPlannerResult:
  """Continue a remeshed field with an explicit invariant boundary law.

  This is the invariant-conditioned counterpart to
  :func:`plan_caustic_remesh_downstream_field_chain`.  The invariant callback
  receives the currently accepted bounded field, so each continued shock is
  still re-solved from carried state/pressure data.  The selected invariant
  is a research boundary condition; it does not supply the missing physical
  caustic seam or mixed-regime closure.
  """

  if not isinstance(remesh, MocCausticShockRemeshResult):
    raise TypeError('remesh must be a MocCausticShockRemeshResult')
  if not isinstance(allow_research_continuation, bool):
    raise TypeError('allow_research_continuation must be a bool')
  if not allow_research_continuation:
    raise ValueError(
      'caustic remesh invariant continuation requires explicit '
      'allow_research_continuation=True; production promotion remains blocked'
    )
  field = remesh.as_bounded_downstream_field()
  planner = plan_post_shock_field_invariant_chain(
    field,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    start_point_at=start_point_at,
    downstream_invariant_family=downstream_invariant_family,
    downstream_invariant_at=downstream_invariant_at,
    end_x_at=end_x_at,
    target_centerline_y_m=target_centerline_y_m,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    maximum_invariant_iterations=maximum_invariant_iterations,
    policy=policy,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'caustic_remesh_continuation': remesh.as_report(),
    'seed_field_model': 'bounded-caustic-remesh-post-shock-field',
    'research_continuation_opt_in': allow_research_continuation,
    'downstream_invariant_family': downstream_invariant_family.value,
    'remesh_physical_closure_verified': remesh.physical_closure_verified,
    'remesh_chain_promotion_blocked': remesh.chain_promotion_blocked,
    'upstream_field_replacement_policy': (
      'replace-only-after-complete-field-coupled-solve'
    ),
  })
  return replace(
    planner,
    claim_status=(
      'caustic-remesh-downstream-field invariant research chain; '
      'old-family-seam-and-physical-boundary-pending'
    ),
    diagnostics=diagnostics,
  )


def plan_post_shock_characteristic_chain(
  seed: MocPostShockCharacteristicFieldResult,
  solve_next: MocPostShockFieldContinuationSolver,
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
  require_upstream_shock_coupling: bool = False,
  planner_kind: MocChainPlannerKind = MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Plan a state-carrying post-shock chain with exact handoff audit steps."""

  if planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH and not require_upstream_shock_coupling:
    raise ValueError(
      'upstream-coupled research planning requires '
      'require_upstream_shock_coupling=True'
    )
  steps: list[MocChainPlannerStep] = []

  def wrapped(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision | None:
    if incoming_handoff != current.continuation_boundary:
      raise ValueError('planner callback received a handoff different from the current cell')
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      incoming_handoff,
      previous_result_handoff_fingerprint=(
        steps[-1].result_handoff_fingerprint if steps else None
      ),
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index, incoming_handoff)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

  chain = continue_post_shock_characteristic_chain(
    seed,
    wrapped,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=require_upstream_shock_coupling,
  )
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=planner_kind,
    steps=tuple(steps),
    claim_status=(
      _default_claim_status(planner_kind)
      if claim_status is None
      else claim_status
    ),
  )
####


def plan_post_shock_field_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a chain whose next shock consumes the prior solved field.

  ``start_point_at`` chooses each new shock start from the current field and
  cell.  The default endpoint advances by the initial seed-cell axial length;
  ``end_x_at`` may supply a different solver-owned endpoint.  The prior field
  is replaced only after a complete field-coupled next-cell solve returns, so
  an upstream-domain miss or typed terminal cannot be converted into a
  prescribed planner cell.

  This is an upstream-coupled research planner.  It is not the prescribed
  boundary mock and remains below the production claim ceiling until the
  downstream boundary and external validation gates are complete.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      start_point_m=start_point,
      end_x_m=next_end_x,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-post-shock-field-coupled-planner; '
      'production-shock-boundary-and-external-validation-pending'
    ),
  )
####


def plan_source_strip_shock_chain(
  seed: MocPostShockCharacteristicFieldResult,
  source_continuation: MocSourceStripContinuationResult,
  *,
  start_point_m: tuple[float, float],
  start_x_m: float,
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one shock-cell step from a bounded source-strip continuation.

  A source strip supplies upstream state and pressure samples for one new
  shock attempt.  It is not reused as though it were a downstream chain
  field: a successful first attempt may produce one new field, after which
  the planner returns an explicit non-physical one-step-domain stop.  A
  source-strip caustic is preserved as a typed characteristic stop before
  the shock solver is called.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(source_continuation, MocSourceStripContinuationResult):
    raise TypeError(
      'source_continuation must be a MocSourceStripContinuationResult'
    )
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)

  source_strip = source_continuation.strip
  if source_continuation.converged and source_strip is not None and source_strip.converged:
    initial_decision: MocChainTerminationDecision | None = None
  elif (
    source_continuation.remesh is not None
    and source_continuation.remesh.chain_termination_available
  ):
    source_strip = None
    initial_decision = source_continuation.remesh.as_chain_termination_decision()
  else:
    source_strip = None
    initial_decision = MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=(
        'source-strip continuation did not provide a converged bounded '
        'upstream field for a next shock-cell attempt'
      ),
      diagnostics={
        'termination_model': 'source-strip-continuation-boundary',
        'upstream_field_model': 'bounded-source-characteristic-strip-continuation',
        'source_continuation_status': source_continuation.status.value,
        'source_continuation_message': source_continuation.message,
        'last_converged_strip': (
          None
          if source_continuation.last_converged_strip is None
          else source_continuation.last_converged_strip.as_report()
        ),
      },
    )

  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'source-strip shock planner completed its one-step upstream '
          'domain; a later cell requires a newly solved bounded upstream field'
        ),
        diagnostics={
          'termination_model': 'bounded-source-strip-one-step-domain',
          'upstream_field_model': 'bounded-source-characteristic-strip',
          'source_strip_reuse_policy': 'never-reuse-after-one-next-cell-attempt',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    if initial_decision is not None:
      return initial_decision
    assert source_strip is not None
    solved = solve_marched_attached_shock_chain_cell_from_source_strip_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      source_strip,
      start_point_m=start_point_m,
      end_x_m=current.end_x_m + cell_axial_length_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-generated-source-strip-shock-chain-planner; '
      'one-step-domain; caustic-or-downstream-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'source_strip_continuation': source_continuation.as_report(),
    'source_strip_chain_model': 'bounded-source-strip-one-step',
    'one_step_domain': True,
    'source_strip_reuse_policy': 'never-reuse-after-one-next-cell-attempt',
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_source_strip_shock_chain_sequence(
  seed: MocPostShockCharacteristicFieldResult,
  source_continuation: MocSourceStripContinuationResult,
  source_continuation_at: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocSourceStripContinuationResult | MocChainTerminationDecision | None,
  ],
  *,
  start_point_at: Callable[
    [MocChainCell, int, MocSourceStripContinuationResult],
    tuple[float, float],
  ],
  start_x_m: float,
  end_x_m: float,
  end_x_at: Callable[
    [MocChainCell, int, MocSourceStripContinuationResult],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a chain with a newly solved bounded source field per cell.

  ``source_continuation`` supplies the first next-shock attempt.  After a
  successful cell, ``source_continuation_at`` must return a distinct,
  converged source-strip continuation for the next attempt.  The planner
  rejects reuse of either the continuation result or its strip object, and a
  missing/nonconverged source domain becomes a typed upstream-field boundary.
  This keeps a finite source strip from being mistaken for a downstream chain
  field or silently reused outside its solved domain.

  The sequence remains a solver-generated research planner.  It does not
  provide the physical reflected-field or mixed-regime downstream closure
  required for product promotion.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(source_continuation, MocSourceStripContinuationResult):
    raise TypeError(
      'source_continuation must be a MocSourceStripContinuationResult'
    )
  if not callable(source_continuation_at):
    raise TypeError('source_continuation_at must be callable')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)

  source_history: list[MocSourceStripContinuationResult] = [
    source_continuation,
  ]
  used_continuation_ids = {id(source_continuation)}
  used_strip_ids = (
    {id(source_continuation.strip)}
    if source_continuation.strip is not None
    else set()
  )
  initial_strip_fingerprint = _source_strip_fingerprint(source_continuation)
  used_strip_fingerprints = (
    {initial_strip_fingerprint}
    if initial_strip_fingerprint is not None
    else set()
  )
  source_attempts: list[dict[str, Any]] = [{
    'current_cell_index': 1,
    'next_cell_index': 2,
    'role': 'initial-source-continuation',
    'continuation': source_continuation.as_report(),
    'fresh_continuation': True,
    'fresh_strip': source_continuation.strip is not None,
    'source_strip_fingerprint': initial_strip_fingerprint,
  }]

  def continuation_stop(
    continuation: MocSourceStripContinuationResult,
    next_cell_index: int,
    *,
    message: str | None = None,
    policy_label: str = 'fresh-bounded-source-strip-required-per-cell',
    allow_remesh_decision: bool = True,
  ) -> MocChainTerminationDecision:
    if (
      allow_remesh_decision
      and
      continuation.remesh is not None
      and continuation.remesh.chain_termination_available
    ):
      remesh_decision = continuation.remesh.as_chain_termination_decision()
      diagnostics = dict(remesh_decision.diagnostics)
      diagnostics.update({
        'source_continuation_status': continuation.status.value,
        'source_continuation_message': continuation.message,
        'next_cell_index': next_cell_index,
        'source_strip_reuse_policy': policy_label,
      })
      return replace(remesh_decision, diagnostics=diagnostics)
    stop_message = message if message is not None else continuation.message
    if not stop_message:
      stop_message = (
        'source-strip continuation did not provide a converged bounded '
        'upstream field for the next shock-cell attempt'
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=stop_message,
      diagnostics={
        'termination_model': 'bounded-source-characteristic-strip-sequence',
        'upstream_field_model': 'bounded-source-characteristic-strip',
        'source_continuation_status': continuation.status.value,
        'source_continuation_message': continuation.message,
        'last_converged_strip': (
          None
          if continuation.last_converged_strip is None
          else continuation.last_converged_strip.as_report()
        ),
        'next_cell_index': next_cell_index,
        'source_strip_reuse_policy': policy_label,
      },
    )

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    if next_cell_index == 2:
      next_source: (
        MocSourceStripContinuationResult
        | MocChainTerminationDecision
        | None
      ) = source_continuation
    else:
      next_source = source_continuation_at(
        current,
        next_cell_index,
        incoming_handoff,
      )
      if next_source is None:
        source_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'source-continuation-provider',
          'provider_result': None,
          'fresh_continuation': False,
          'fresh_strip': False,
        })
        return MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
          message=(
            'source-continuation provider returned no bounded upstream field '
            'for the next shock-cell attempt'
          ),
          diagnostics={
            'termination_model': 'bounded-source-characteristic-strip-sequence',
            'upstream_field_model': 'bounded-source-characteristic-strip',
            'next_cell_index': next_cell_index,
            'source_strip_reuse_policy': (
              'fresh-bounded-source-strip-required-per-cell'
            ),
          },
        )
      if isinstance(next_source, MocChainTerminationDecision):
        source_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'source-continuation-provider',
          'provider_decision': next_source.as_report(),
          'fresh_continuation': False,
          'fresh_strip': False,
        })
        if next_source.physical_termination:
          return MocChainTerminationDecision(
            physical_termination=False,
            reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
            message=(
              'source-continuation provider cannot declare physical plume '
              'termination from an upstream domain boundary'
            ),
            diagnostics={
              'termination_model': 'source-provider-physical-stop-rejected',
              'upstream_field_model': 'bounded-source-characteristic-strip',
              'next_cell_index': next_cell_index,
              'source_provider_decision': next_source.as_report(),
            },
          )
        return next_source
      if not isinstance(next_source, MocSourceStripContinuationResult):
        raise TypeError(
          'source_continuation_at must return a '
          'MocSourceStripContinuationResult, MocChainTerminationDecision, or None'
      )
      fresh_continuation = id(next_source) not in used_continuation_ids
      next_strip_fingerprint = _source_strip_fingerprint(next_source)
      source_strip_reused = (
        next_source.strip is not None
        and (
          id(next_source.strip) in used_strip_ids
          or next_strip_fingerprint is None
          or next_strip_fingerprint in used_strip_fingerprints
        )
      )
      strip_is_fresh = next_source.strip is not None and not source_strip_reused
      fresh_strip = strip_is_fresh
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'source-continuation-provider',
        'continuation': next_source.as_report(),
        'fresh_continuation': fresh_continuation,
        'fresh_strip': fresh_strip,
        'source_strip_fingerprint': next_strip_fingerprint,
      })
      if not fresh_continuation or (
        next_source.strip is not None and source_strip_reused
      ):
        return continuation_stop(
          next_source,
          next_cell_index,
          message=(
            'source-continuation provider reused a prior continuation or '
            'source strip; a new bounded upstream field is required for each '
            'continued shock cell'
          ),
          policy_label='reject-reused-source-continuation-or-strip',
          allow_remesh_decision=False,
        )
      source_history.append(next_source)
      used_continuation_ids.add(id(next_source))
      if next_source.strip is not None:
        used_strip_ids.add(id(next_source.strip))
        if next_strip_fingerprint is not None:
          used_strip_fingerprints.add(next_strip_fingerprint)

    if not isinstance(next_source, MocSourceStripContinuationResult):
      raise TypeError('source-continuation sequence selected an invalid source result')
    if (
      not next_source.converged
      or next_source.strip is None
      or not next_source.strip.converged
    ):
      return continuation_stop(next_source, next_cell_index)
    source_strip = next_source.strip
    start_point = start_point_at(current, next_cell_index, next_source)
    next_end_x = (
      end_x_at(current, next_cell_index, next_source)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    return solve_marched_attached_shock_chain_cell_from_source_strip_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      source_strip,
      start_point_m=start_point,
      end_x_m=next_end_x,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-generated-source-strip-shock-chain-sequence; '
      'fresh-bounded-upstream-domain-per-cell; physical-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'source_strip_chain_model': 'bounded-source-strip-fresh-domain-sequence',
    'one_step_domain': False,
    'source_strip_reuse_policy': (
      'fresh-bounded-source-strip-required-per-cell'
    ),
    'source_domain_count': len(source_history),
    'source_domain_attempt_count': len(source_attempts),
    'source_domain_attempts': source_attempts,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_post_shock_field_invariant_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[
    [MocPostShockCharacteristicFieldResult, int, tuple[float, float]],
    float,
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan field-coupled cells with an explicit downstream invariant law.

  The invariant callback receives the currently accepted bounded field, so a
  caller can derive a target from the local upstream state and pressure before
  the continuation solver inverts it through attached compression.  The
  planner replaces the upstream field only after a complete cell is returned;
  typed physical and numerical stops remain visible in the step audit.

  This is a research planner.  A selected invariant is an explicit downstream
  condition, not a canonical mixed-regime closure or a production shock
  placement model.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if not isinstance(downstream_invariant_family, CharacteristicFamily):
    raise TypeError(
      'downstream_invariant_family must be a CharacteristicFamily'
    )
  if not callable(downstream_invariant_at):
    raise TypeError('downstream_invariant_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_field_with_invariant_boundary_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      start_point_m=start_point,
      end_x_m=next_end_x,
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_at=(
        lambda index, point: downstream_invariant_at(
          current_field,
          index,
          point,
        )
      ),
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-post-shock-field-invariant-coupled-planner; '
      'selected-invariant-and-external-validation-pending'
    ),
  )
####


def plan_ambient_pressure_field_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  closure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan repeated ambient-pressure-conditioned field re-solves.

  Each candidate next shock samples only the currently accepted post-shock
  field.  The field is replaced after, and only after, the ambient perimeter,
  shock fit, exact incoming handoff, and upstream coupling gates pass.  A
  bracket or bounded-domain failure becomes a typed planner stop; the planner
  remains a research lane and never changes the fast or reduced-order
  provider claims.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      lambda point: current_field.state_at(
        point,
        position_tolerance_m=position_tolerance_m,
      ),
      lambda point: current_field.static_pressure_at(
        point,
        position_tolerance_m=position_tolerance_m,
      ),
      start_point,
      next_end_x,
      ambient_pressure_Pa,
      outer_downstream_flow_angle_lower_rad,
      outer_downstream_flow_angle_upper_rad,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      closure_tolerance=closure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'ambient-pressure-field-coupled-planner; exact-handoff-and-'
      'external-validation-pending'
    ),
  )
####


def plan_ambient_closed_post_shock_chain(
  seed: MocPhysicalPostShockFieldResult,
  solve_next: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocPhysicalPostShockFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
  require_upstream_shock_coupling: bool = True,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Audit continuation of solver-owned ambient-closed physical cells.

  This planner is the physical-field counterpart to the prescribed chain
  mock.  Every callback receives the prior closed cell's centerline trace and
  must return a newly assembled ambient-closed field that records the exact
  incoming handoff.  It remains a research planner until the canonical
  reflected upstream domain and independent validation gates pass.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not callable(solve_next):
    raise TypeError('solve_next must be callable')
  steps: list[MocChainPlannerStep] = []

  def wrapped(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision | None:
    if incoming_handoff != current.continuation_boundary:
      raise ValueError(
        'planner callback received a handoff different from the current physical cell'
      )
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      incoming_handoff,
      previous_result_handoff_fingerprint=(
        steps[-1].result_handoff_fingerprint if steps else None
      ),
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index, incoming_handoff)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

  chain = continue_ambient_closed_post_shock_chain(
    seed,
    wrapped,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=require_upstream_shock_coupling,
  )
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    steps=tuple(steps),
    claim_status=(
      'ambient-closed-physical-field-chain; canonical-reflected-domain-and-'
      'external-validation-pending'
      if claim_status is None
      else claim_status
    ),
  )
####
