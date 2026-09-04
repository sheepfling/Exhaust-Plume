"""Globally coupled reflected-field closure and gated shock-cell fitting.

The reflected-domain module already contains the numerical pieces needed to
build one global Euler field.  This module supplies the missing contract seam
around those pieces:

``alternating source band -> global shock remesh -> exact Euler field ->
independent field audit -> typed frontier-only shock-cell fit``.

The closure result distinguishes variable-entropy transport from the older
constant-total-pressure diagnostic.  The fitter consumes only a typed
state/total-pressure frontier and the geometry retained by the solver-owned
closure.  It has no caller-supplied shock-point list, downstream-angle
schedule, or compression template.  The current repository still lacks the
canonical reflected free-boundary and indexed external-validation evidence,
so the returned cell is a research candidate and production promotion remains
blocked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from math import hypot, isfinite, log
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainCell,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  fit_euler_consistent_shock_boundary_from_geometry,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceResult,
  MocReflectedDomainGlobalEulerShockBoundaryResult,
  MocReflectedDomainGlobalShockRemeshResult,
  solve_reflected_domain_global_euler_shock_boundary,
  solve_reflected_domain_global_shock_remesh,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocReflectedDomainGlobalPhysicalClosureStatus',
  'MocReflectedDomainPromotionEvidence',
  'MocReflectedDomainDownstreamBoundaryStatus',
  'MocReflectedDomainDownstreamBoundaryResult',
  'MocReflectedDomainGlobalPhysicalClosureResult',
  'moc_reflected_domain_global_physical_closure_fingerprint',
  'solve_reflected_domain_global_physical_closure',
  'MocProductionShockCellFitStatus',
  'MocProductionShockCellFitResult',
  'fit_reflected_domain_production_shock_cell',
  'fit_production_shock_cell_from_frontier',
)


class MocReflectedDomainGlobalPhysicalClosureStatus(str, Enum):
  """Outcome of the globally coupled reflected-field closure."""

  CONVERGED_GLOBAL_PHYSICAL_CLOSURE = (
    'converged_global_reflected_physical_closure'
  )
  INVALID_INPUT = 'invalid_input'
  GLOBAL_REMESH_FAILURE = 'global_physical_closure_remesh_failure'
  GLOBAL_EULER_FAILURE = 'global_physical_closure_euler_failure'
  INDEPENDENT_AUDIT_FAILURE = 'global_physical_closure_independent_audit_failure'
  ENTROPY_TRANSPORT_FAILURE = 'global_physical_closure_entropy_transport_failure'
####


def _pressure_log_residual(actual: float, expected: float) -> float:
  """Return a symmetric, scale-free total-pressure residual."""

  if actual <= 0.0 or expected <= 0.0:
    return float('inf')
  ####
  return abs(log(float(actual) / float(expected)))
####


def _state_residual(
  actual: Any,
  expected: Any,
) -> float:
  """Compare the state components carried across a solver-owned seam."""

  try:
    return max(
      hypot(actual.x_m - expected.x_m, actual.y_m - expected.y_m),
      abs(actual.theta_rad - expected.theta_rad),
      abs(actual.mach - expected.mach),
      abs(actual.gamma - expected.gamma),
    )
  except (AttributeError, TypeError, ValueError):
    return float('inf')
  ####
####


def _variable_entropy_transport_audit(
  source_band: MocReflectedDomainAlternatingSourceResult,
  global_result: MocReflectedDomainGlobalEulerShockBoundaryResult,
  *,
  position_tolerance_m: float,
  pressure_tolerance: float,
) -> tuple[bool, float | None, str]:
  """Verify per-shock-sample entropy lineage through the closed field.

  Total pressure is allowed to vary along a fitted shock.  The old ambient
  field audit intentionally reports a failure when it is asked to compare all
  downstream samples with the first sample; that is useful for a uniform-p0
  diagnostic, but it is not the correct criterion for an entropy-producing
  shock cell.  Here each downstream sample is compared with the matching
  shock sample and then with the retained ambient perimeter.
  """

  curve = global_result.shock_boundary
  physical = global_result.physical_field
  field = None if physical is None else physical.field
  if curve is None or field is None or physical is None:
    return False, None, 'global closure retained no exact shock and physical field'
  ####
  points = tuple(global_result.remeshed_shock_points_m)
  if len(points) < 3 or len(curve.shock_points_m) != len(points):
    return False, None, 'global closure shock geometry and curve samples are misaligned'
  ####
  if any(
    hypot(curve_point[0] - point[0], curve_point[1] - point[1])
    > position_tolerance_m
    for curve_point, point in zip(curve.shock_points_m, points, strict=True)
  ):
    return False, None, 'global shock curve geometry is not aligned with the retained path'
  ####
  if not (
    len(curve.upstream_states)
    == len(curve.upstream_total_pressure_Pa)
    == len(curve.downstream_states)
    == len(curve.downstream_total_pressure_Pa)
    == len(points)
  ):
    return False, None, 'global closure shock curve lacks complete state/pressure lineage'
  ####
  if not (
    len(field.shock_boundary_points_m)
    == len(field.post_shock_boundary_states)
    == len(field.post_shock_boundary_total_pressure_Pa)
    == len(points)
  ):
    return False, None, 'closed field lacks one post-shock state and pressure per shock sample'
  ####
  if any(
    hypot(field_point[0] - point[0], field_point[1] - point[1])
    > position_tolerance_m
    for field_point, point in zip(
      field.shock_boundary_points_m,
      points,
      strict=True,
    )
  ):
    return False, None, 'closed field shock geometry is not aligned with the global curve'
  ####

  residuals: list[float] = []
  for index, point in enumerate(points):
    source_state = source_band.state_at(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    source_pressure = source_band.total_pressure_at(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    if source_state is None or source_pressure is None:
      return False, None, f'source band could not reproduce shock sample {index}'
    ####
    upstream_state = curve.upstream_states[index]
    upstream_pressure = curve.upstream_total_pressure_Pa[index]
    downstream_state = curve.downstream_states[index]
    field_state = field.post_shock_boundary_states[index]
    field_pressure = field.post_shock_boundary_total_pressure_Pa[index]
    if (
      _state_residual(source_state, upstream_state) > position_tolerance_m
      or _pressure_log_residual(source_pressure, upstream_pressure)
      > pressure_tolerance
      or _state_residual(field_state, downstream_state) > position_tolerance_m
      or _pressure_log_residual(
        field_pressure,
        curve.downstream_total_pressure_Pa[index],
      )
      > pressure_tolerance
    ):
      return False, None, f'shock entropy lineage changed at sample {index}'
    ####
    residuals.extend((
      _pressure_log_residual(source_pressure, upstream_pressure),
      _pressure_log_residual(
        field_pressure,
        curve.downstream_total_pressure_Pa[index],
      ),
    ))
  ####

  march = physical.ambient_march
  if march is None or len(march.boundary_samples) != len(points):
    return False, None, 'closed field retained no aligned ambient pressure march'
  ####
  if len(field.ambient_boundary.total_pressure_Pa) != len(points):
    return False, None, 'closed field retained no aligned ambient pressure perimeter'
  ####
  for index, (march_sample, field_pressure) in enumerate(
    zip(march.boundary_samples, field.ambient_boundary.total_pressure_Pa, strict=True)
  ):
    residual = _pressure_log_residual(
      march_sample.total_pressure_Pa,
      field_pressure,
    )
    residuals.append(residual)
    if residual > pressure_tolerance:
      return False, None, f'ambient entropy lineage changed at sample {index}'
    ####
  ####

  cell_samples = field.cell_state_samples(
    position_tolerance_m=position_tolerance_m,
  )
  if len(cell_samples) != field.cell_count:
    return False, None, 'closed field does not expose complete cell pressure lineage'
  ####
  if any(
    pressure is None or not isfinite(float(pressure)) or float(pressure) <= 0.0
    for _vertices, _states, pressures in cell_samples
    for pressure in pressures
  ):
    return False, None, 'closed field contains a non-finite or non-positive cell pressure'
  ####
  maximum_residual = max(residuals, default=0.0)
  return (
    maximum_residual <= pressure_tolerance,
    maximum_residual,
    (
      'per-sample shock entropy loss and ambient pressure lineage are carried '
      'through the closed field'
      if maximum_residual <= pressure_tolerance
      else 'per-sample shock entropy lineage exceeded tolerance'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainPromotionEvidence:
  """References to independently verified gates for one exact closure.

  The evidence IDs identify owner-produced canonical, refinement, or external
  validation records.  This value does not manufacture those records or
  inspect their contents; it binds their accepted gate decisions to the
  deterministic closure fingerprint so a result cannot silently carry gates
  from a different solver run.
  """

  closure_fingerprint: str
  canonical_free_boundary_evidence_id: str | None = None
  canonical_euler_evidence_id: str | None = None
  refinement_evidence_id: str | None = None
  external_validation_evidence_id: str | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.closure_fingerprint, str):
      raise TypeError('closure_fingerprint must be a string')
    ####
    fingerprint = self.closure_fingerprint
    if len(fingerprint) != 64 or any(
      character not in '0123456789abcdef'
      for character in fingerprint
    ):
      raise ValueError(
        'closure_fingerprint must be a 64-character lowercase SHA-256 digest'
      )
    ####
    object.__setattr__(self, 'closure_fingerprint', fingerprint)
    for name in (
      'canonical_free_boundary_evidence_id',
      'canonical_euler_evidence_id',
      'refinement_evidence_id',
      'external_validation_evidence_id',
    ):
      value = getattr(self, name)
      if value is not None:
        if not isinstance(value, str):
          raise TypeError(f'{name} must be a string when supplied')
        ####
        if not value:
          raise ValueError(f'{name} must be non-empty when supplied')
        ####
      ####
    ####
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    return self.canonical_free_boundary_evidence_id is not None
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    return self.canonical_euler_evidence_id is not None
  ####

  @property
  def refinement_verified(self) -> bool:
    return self.refinement_evidence_id is not None
  ####

  @property
  def external_validation_verified(self) -> bool:
    return self.external_validation_evidence_id is not None
  ####

  @property
  def has_verified_gate(self) -> bool:
    return bool(
      self.canonical_free_boundary_verified
      or self.canonical_euler_verified
      or self.refinement_verified
      or self.external_validation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'closure_fingerprint': self.closure_fingerprint,
      'canonical_free_boundary_evidence_id': (
        self.canonical_free_boundary_evidence_id
      ),
      'canonical_euler_evidence_id': self.canonical_euler_evidence_id,
      'refinement_evidence_id': self.refinement_evidence_id,
      'external_validation_evidence_id': (
        self.external_validation_evidence_id
      ),
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'refinement_verified': self.refinement_verified,
      'external_validation_verified': self.external_validation_verified,
      'has_verified_gate': self.has_verified_gate,
    }
  ####
####


class MocReflectedDomainDownstreamBoundaryStatus(str, Enum):
  """Outcome of the solver-owned downstream-boundary seam."""

  RESEARCH_COMPRESSION_ENVELOPE = 'research_compression_envelope'
  SOLVER_OWNED_MIXED_REGIME_PENDING = (
    'solver_owned_mixed_regime_boundary_pending'
  )
  CONVERGED_SOLVER_OWNED_MIXED_REGIME = (
    'converged_solver_owned_mixed_regime_boundary'
  )
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainDownstreamBoundaryResult:
  """Typed evidence at the downstream continuation boundary.

  The current global solver populates this value with the boundary samples
  carried by its research compression-envelope field.  Those samples are
  useful for inspection and for the next solver seam, but they are not a
  mixed-regime boundary condition and therefore cannot pass
  ``closure_verified``.  A future canonical solver must provide a different
  model, its own boundary-condition and mixed-regime-field checks, and the
  residual evidence before this result can satisfy the global gate.
  """

  status: MocReflectedDomainDownstreamBoundaryStatus
  model: str
  boundary_points_m: tuple[tuple[float, float], ...] = ()
  boundary_states: tuple[CharacteristicState, ...] = ()
  boundary_total_pressure_Pa: tuple[float, ...] = ()
  boundary_static_pressure_Pa: tuple[float, ...] = ()
  pressure_residuals: tuple[float, ...] = ()
  tangent_residuals: tuple[float, ...] = ()
  coordinate_residuals_m: tuple[float, ...] = ()
  solver_owned: bool = False
  boundary_condition_verified: bool = False
  mixed_regime_field_verified: bool = False
  position_tolerance_m: float = 1.0e-9
  residual_tolerance: float = 1.0e-8
  message: str = ''
  ambient_pressure_Pa: float | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainDownstreamBoundaryStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainDownstreamBoundaryStatus'
      )
    ####
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    ####
    try:
      points = tuple(
        (float(point[0]), float(point[1]))
        for point in self.boundary_points_m
      )
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError(
        'boundary_points_m must contain two-coordinate numeric points'
      ) from error
    ####
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('boundary_points_m must contain finite coordinates')
    ####
    states = tuple(self.boundary_states)
    if any(not isinstance(state, CharacteristicState) for state in states):
      raise TypeError(
        'boundary_states must contain CharacteristicState values'
      )
    ####
    total_pressure = tuple(
      float(value) for value in self.boundary_total_pressure_Pa
    )
    if any(not isfinite(value) or value <= 0.0 for value in total_pressure):
      raise ValueError(
        'boundary_total_pressure_Pa must contain finite positive values'
      )
    ####
    sample_count = len(points)
    if len(states) != sample_count or len(total_pressure) != sample_count:
      raise ValueError(
        'downstream boundary points, states, and total-pressure samples '
        'must have equal lengths'
      )
    ####
    static_pressure = tuple(
      float(value) for value in self.boundary_static_pressure_Pa
    )
    pressure_residuals = tuple(float(value) for value in self.pressure_residuals)
    tangent_residuals = tuple(float(value) for value in self.tangent_residuals)
    coordinate_residuals = tuple(
      float(value) for value in self.coordinate_residuals_m
    )
    if static_pressure and len(static_pressure) != sample_count:
      raise ValueError(
        'boundary_static_pressure_Pa must match the boundary sample count'
      )
    ####
    for name, values in (
      ('boundary_static_pressure_Pa', static_pressure),
      ('pressure_residuals', pressure_residuals),
      ('coordinate_residuals_m', coordinate_residuals),
    ):
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      if values and len(values) != sample_count:
        raise ValueError(f'{name} must match the boundary sample count')
      ####
    ####
    if tangent_residuals and len(tangent_residuals) != max(0, sample_count - 1):
      raise ValueError(
        'tangent_residuals must match the boundary segment count'
      )
    ####
    if not coordinate_residuals and states:
      coordinate_residuals = tuple(
        hypot(state.x_m - point[0], state.y_m - point[1])
        for point, state in zip(points, states, strict=True)
      )
    ####
    for name in (
      'solver_owned',
      'boundary_condition_verified',
      'mixed_regime_field_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('position_tolerance_m', 'residual_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'boundary_points_m', points)
    object.__setattr__(self, 'boundary_states', states)
    object.__setattr__(self, 'boundary_total_pressure_Pa', total_pressure)
    object.__setattr__(self, 'boundary_static_pressure_Pa', static_pressure)
    object.__setattr__(self, 'pressure_residuals', pressure_residuals)
    object.__setattr__(self, 'tangent_residuals', tangent_residuals)
    object.__setattr__(self, 'coordinate_residuals_m', coordinate_residuals)
    if self.ambient_pressure_Pa is not None:
      ambient_pressure = float(self.ambient_pressure_Pa)
      if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
        raise ValueError(
          'ambient_pressure_Pa must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def sample_count(self) -> int:
    return len(self.boundary_points_m)
  ####

  @property
  def samples_available(self) -> bool:
    return bool(
      self.sample_count >= 2
      and len(self.boundary_states) == self.sample_count
      and len(self.boundary_total_pressure_Pa) == self.sample_count
      and len(self.coordinate_residuals_m) == self.sample_count
      and all(
        residual <= self.position_tolerance_m
        for residual in self.coordinate_residuals_m
      )
    )
  ####

  @property
  def geometry_verified(self) -> bool:
    return bool(
      self.samples_available
      and all(
        hypot(second[0] - first[0], second[1] - first[1])
        > self.position_tolerance_m
        for first, second in zip(
          self.boundary_points_m,
          self.boundary_points_m[1:],
        )
      )
    )
  ####

  @property
  def maximum_coordinate_residual_m(self) -> float | None:
    return max(self.coordinate_residuals_m, default=None)
  ####

  @property
  def maximum_pressure_residual(self) -> float | None:
    return max(self.pressure_residuals, default=None)
  ####

  @property
  def maximum_tangent_residual(self) -> float | None:
    return max(self.tangent_residuals, default=None)
  ####

  @property
  def residuals_verified(self) -> bool:
    return bool(
      self.geometry_verified
      and self.pressure_residuals
      and self.tangent_residuals
      and self.maximum_pressure_residual is not None
      and self.maximum_tangent_residual is not None
      and self.maximum_pressure_residual <= self.residual_tolerance
      and self.maximum_tangent_residual <= self.residual_tolerance
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainDownstreamBoundaryStatus.CONVERGED_SOLVER_OWNED_MIXED_REGIME
      and self.closure_verified
    )
  ####

  @property
  def closure_verified(self) -> bool:
    """Whether the boundary is a non-envelope mixed-regime closure."""

    return bool(
      self.status
      is MocReflectedDomainDownstreamBoundaryStatus.CONVERGED_SOLVER_OWNED_MIXED_REGIME
      and 'compression-envelope' not in self.model
      and self.solver_owned
      and self.boundary_condition_verified
      and self.mixed_regime_field_verified
      and self.residuals_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """A downstream boundary alone is not a promoted shock-cell chain."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'model': self.model,
      'converged': self.converged,
      'closure_verified': self.closure_verified,
      'solver_owned': self.solver_owned,
      'boundary_condition_verified': self.boundary_condition_verified,
      'mixed_regime_field_verified': self.mixed_regime_field_verified,
      'samples_available': self.samples_available,
      'geometry_verified': self.geometry_verified,
      'residuals_verified': self.residuals_verified,
      'sample_count': self.sample_count,
      'boundary_points_m': [list(point) for point in self.boundary_points_m],
      'boundary_states': [
        {
          'x_m': state.x_m,
          'y_m': state.y_m,
          'theta_rad': state.theta_rad,
          'mach': state.mach,
          'gamma': state.gamma,
        }
        for state in self.boundary_states
      ],
      'boundary_total_pressure_Pa': list(self.boundary_total_pressure_Pa),
      'boundary_static_pressure_Pa': list(self.boundary_static_pressure_Pa),
      'pressure_residuals': list(self.pressure_residuals),
      'tangent_residuals': list(self.tangent_residuals),
      'coordinate_residuals_m': list(self.coordinate_residuals_m),
      'maximum_coordinate_residual_m': self.maximum_coordinate_residual_m,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'maximum_tangent_residual': self.maximum_tangent_residual,
      'position_tolerance_m': self.position_tolerance_m,
      'residual_tolerance': self.residual_tolerance,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####
####


def _selected_downstream_continuation_law(
  global_remesh: MocReflectedDomainGlobalShockRemeshResult | None,
) -> str:
  """Return the exact continuation law selected by a global remesh."""

  if global_remesh is None or global_remesh.selected_attempt is None:
    return 'unavailable'
  ####
  physical_field = (
    global_remesh.selected_attempt.first_cell_result.selected_physical_field
  )
  if physical_field is None:
    return 'unavailable'
  ####
  return physical_field.continuation_law
####


def _build_downstream_boundary_result(
  global_remesh: MocReflectedDomainGlobalShockRemeshResult,
  global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult,
) -> MocReflectedDomainDownstreamBoundaryResult:
  """Expose retained downstream samples without promoting the envelope."""

  model = _selected_downstream_continuation_law(global_remesh)
  status = (
    MocReflectedDomainDownstreamBoundaryStatus.RESEARCH_COMPRESSION_ENVELOPE
    if 'compression-envelope' in model
    else MocReflectedDomainDownstreamBoundaryStatus.SOLVER_OWNED_MIXED_REGIME_PENDING
  )
  physical = global_euler.physical_field
  field = None if physical is None else physical.field
  if field is None:
    return MocReflectedDomainDownstreamBoundaryResult(
      status=status,
      model=model,
      solver_owned=model != 'unavailable',
      message=(
        'global Euler closure retained no downstream boundary samples; '
        'a solver-owned mixed-regime boundary is still required'
      ),
    )
  ####
  boundary = field.ambient_boundary
  points = tuple(boundary.points_m)
  states = tuple(boundary.states)
  total_pressure = tuple(boundary.total_pressure_Pa)
  static_pressure = tuple(boundary.static_pressure_Pa)
  pressure_residuals = tuple(
    abs(float(value)) for value in boundary.pressure_residuals
  )
  tangent_residuals = tuple(
    abs(float(value)) for value in boundary.tangent_residuals
  )
  coordinate_residuals = tuple(
    hypot(state.x_m - point[0], state.y_m - point[1])
    for point, state in zip(points, states, strict=True)
  )
  return MocReflectedDomainDownstreamBoundaryResult(
    status=status,
    model=model,
    boundary_points_m=points,
    boundary_states=states,
    boundary_total_pressure_Pa=total_pressure,
    boundary_static_pressure_Pa=static_pressure,
    pressure_residuals=pressure_residuals,
    tangent_residuals=tangent_residuals,
    coordinate_residuals_m=coordinate_residuals,
    ambient_pressure_Pa=boundary.ambient_pressure_Pa,
    solver_owned=True,
    boundary_condition_verified=False,
    mixed_regime_field_verified=False,
    message=(
      'solver-carried ambient boundary samples are retained for the '
      f'{model} research law; the coupled mixed-regime downstream condition '
      'is not solved'
    ),
  )
####


def moc_reflected_domain_global_physical_closure_fingerprint(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> str:
  """Return the stable identity of a closure before promotion evidence.

  Promotion metadata and the human-readable message are intentionally not
  part of this identity.  The retained solver outputs, independent audits,
  local gate inputs, and entropy residual are included so binding evidence to
  a different field or altered local result fails closed.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  payload = {
    'status': closure.status.value,
    'source_band': (
      None if closure.source_band is None else closure.source_band.as_report()
    ),
    'global_remesh': (
      None if closure.global_remesh is None else closure.global_remesh.as_report()
    ),
    'global_euler': (
      None if closure.global_euler is None else closure.global_euler.as_report()
    ),
    'downstream_boundary': (
      None
      if closure.downstream_boundary is None
      else closure.downstream_boundary.as_report()
    ),
    'downstream_boundary_audit': (
      None
      if closure.downstream_boundary_audit is None
      else closure.downstream_boundary_audit.as_report()
    ),
    'global_audit': (
      None if closure.global_audit is None else closure.global_audit.as_report()
    ),
    'field_audit': (
      None if closure.field_audit is None else closure.field_audit.as_report()
    ),
    'local_gates': {
      'source_frontier_verified': closure.source_frontier_verified,
      'incoming_handoff_verified': closure.incoming_handoff_verified,
      'downstream_boundary_closure_verified': (
        closure.downstream_boundary_closure_verified
      ),
      'variable_entropy_transport_verified': (
        closure.variable_entropy_transport_verified
      ),
      'maximum_entropy_lineage_residual': (
        closure.maximum_entropy_lineage_residual
      ),
      'cell_euler_residuals_verified': closure.cell_euler_residuals_verified,
    },
  }
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalPhysicalClosureResult:
  """A globally coupled local physical closure with explicit claim gates."""

  status: MocReflectedDomainGlobalPhysicalClosureStatus
  source_band: MocReflectedDomainAlternatingSourceResult | None
  global_remesh: MocReflectedDomainGlobalShockRemeshResult | None
  global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult | None
  global_audit: Any | None = None
  field_audit: Any | None = None
  source_frontier_verified: bool = False
  incoming_handoff_verified: bool = False
  variable_entropy_transport_verified: bool = False
  maximum_entropy_lineage_residual: float | None = None
  cell_euler_residuals_verified: bool = False
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  refinement_verified: bool = False
  external_validation_verified: bool = False
  message: str = ''
  promotion_evidence: MocReflectedDomainPromotionEvidence | None = None
  downstream_boundary: MocReflectedDomainDownstreamBoundaryResult | None = None
  downstream_boundary_audit: Any | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalPhysicalClosureStatus):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalPhysicalClosureStatus'
      )
    ####
    if self.source_band is not None and not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError('source_band must be a MocReflectedDomainAlternatingSourceResult or None')
    ####
    if self.global_remesh is not None and not isinstance(
      self.global_remesh,
      MocReflectedDomainGlobalShockRemeshResult,
    ):
      raise TypeError('global_remesh must be a MocReflectedDomainGlobalShockRemeshResult or None')
    ####
    if self.global_euler is not None and not isinstance(
      self.global_euler,
      MocReflectedDomainGlobalEulerShockBoundaryResult,
    ):
      raise TypeError(
        'global_euler must be a MocReflectedDomainGlobalEulerShockBoundaryResult or None'
      )
    ####
    if self.downstream_boundary is not None and not isinstance(
      self.downstream_boundary,
      MocReflectedDomainDownstreamBoundaryResult,
    ):
      raise TypeError(
        'downstream_boundary must be a '
        'MocReflectedDomainDownstreamBoundaryResult or None'
      )
    ####
    selected_model = _selected_downstream_continuation_law(self.global_remesh)
    if (
      self.downstream_boundary is not None
      and selected_model != 'unavailable'
      and self.downstream_boundary.model != selected_model
    ):
      raise ValueError(
        'downstream_boundary model must match the selected continuation law'
      )
    ####
    for name in (
      'source_frontier_verified',
      'incoming_handoff_verified',
      'variable_entropy_transport_verified',
      'cell_euler_residuals_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'refinement_verified',
      'external_validation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.promotion_evidence is not None and not isinstance(
      self.promotion_evidence,
      MocReflectedDomainPromotionEvidence,
    ):
      raise TypeError(
        'promotion_evidence must be a MocReflectedDomainPromotionEvidence or None'
      )
    ####
    for gate_name, evidence_name in (
      (
        'canonical_free_boundary_verified',
        'canonical_free_boundary_verified',
      ),
      ('canonical_euler_verified', 'canonical_euler_verified'),
      ('refinement_verified', 'refinement_verified'),
      ('external_validation_verified', 'external_validation_verified'),
    ):
      if (
        getattr(self, gate_name)
        and (
          self.promotion_evidence is None
          or not getattr(self.promotion_evidence, evidence_name)
        )
      ):
        raise ValueError(
          f'{gate_name} requires matching promotion evidence'
        )
      ####
    ####
    if self.maximum_entropy_lineage_residual is not None:
      residual = float(self.maximum_entropy_lineage_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'maximum_entropy_lineage_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'maximum_entropy_lineage_residual', residual)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainGlobalPhysicalClosureStatus.CONVERGED_GLOBAL_PHYSICAL_CLOSURE
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether all local shock, boundary, entropy, and cell gates passed."""

    global_audit = self.global_audit
    field_audit = self.field_audit
    return bool(
      self.converged
      and self.source_band is not None
      and self.source_band.source_field_verified
      and self.global_euler is not None
      and self.global_euler.converged
      and self.global_euler.physical_closure_verified
      and global_audit is not None
      and global_audit.converged
      and global_audit.local_euler_consistency_verified
      and global_audit.source_frontier_verified
      and global_audit.incoming_handoff_verified
      and global_audit.physical_closure_verified
      and field_audit is not None
      and field_audit.shock_jump_verified
      and field_audit.physical_field_verified
      and field_audit.physical_closure_verified
      and field_audit.cell_euler_residuals_verified
      and self.source_frontier_verified
      and self.incoming_handoff_verified
      and self.variable_entropy_transport_verified
      and self.cell_euler_residuals_verified
    )
  ####

  @property
  def downstream_boundary_model(self) -> str:
    """Return the downstream turn law retained by the selected remesh.

    The current global remesh intentionally carries a bounded compression
    envelope.  Naming that law at the closure boundary prevents a locally
    closed field from being mistaken for a solver-owned reflected/mixed-regime
    downstream condition.
    """

    if self.downstream_boundary is not None:
      return self.downstream_boundary.model
    ####
    return _selected_downstream_continuation_law(self.global_remesh)
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """Whether a canonical solver-owned downstream boundary was verified.

    The present global closure retains a research compression-envelope law and
    therefore cannot satisfy this gate.  The property is deliberately
    explicit so a future canonical reflected/mixed-regime implementation must
    add a typed solver-owned boundary result rather than merely renaming the
    existing envelope.
    """

    boundary = self.downstream_boundary
    return bool(boundary is not None and boundary.closure_verified)
  ####

  @property
  def promotion_blockers(self) -> tuple[str, ...]:
    """Return the concrete gates that still block production promotion."""

    blockers: list[str] = []
    if not self.physical_closure_verified:
      blockers.append('local physical closure gates are not all verified')
    ####
    if not self.downstream_boundary_closure_verified:
      blockers.append(
        'solver-owned downstream boundary closure is not verified; '
        f'current law is {self.downstream_boundary_model}'
      )
    ####
    if not self.canonical_free_boundary_verified:
      blockers.append('canonical reflected free-boundary evidence is not bound')
    ####
    if not self.canonical_euler_verified:
      blockers.append('canonical Euler evidence is not bound')
    ####
    if not self.refinement_verified:
      blockers.append('independent refinement evidence is not bound')
    ####
    if not self.external_validation_verified:
      blockers.append('external validation evidence is not bound')
    ####
    return tuple(blockers)
  ####

  @property
  def production_promotion_gates(self) -> Mapping[str, bool]:
    """Return the gates still required before a product claim."""

    evidence = self.promotion_evidence
    evidence_bound = bool(
      evidence is not None
      and evidence.has_verified_gate
      and evidence.closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(self)
    )
    return MappingProxyType({
      'physical_closure_verified': self.physical_closure_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': bool(
        evidence_bound
        and self.canonical_free_boundary_verified
        and evidence.canonical_free_boundary_verified
      ),
      'canonical_euler_verified': bool(
        evidence_bound
        and self.canonical_euler_verified
        and evidence.canonical_euler_verified
      ),
      'refinement_verified': bool(
        evidence_bound
        and self.refinement_verified
        and evidence.refinement_verified
      ),
      'external_validation_verified': bool(
        evidence_bound
        and self.external_validation_verified
        and evidence.external_validation_verified
      ),
    })
  ####

  @property
  def promotion_evidence_bound(self) -> bool:
    evidence = self.promotion_evidence
    return bool(
      evidence is not None
      and evidence.has_verified_gate
      and evidence.closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(self)
    )
  ####

  def bind_promotion_evidence(
    self,
    evidence: MocReflectedDomainPromotionEvidence,
  ) -> MocReflectedDomainGlobalPhysicalClosureResult:
    """Bind independently produced gate records to this exact closure.

    The local closure must already be physically verified.  A partial evidence
    bundle is allowed so canonical, refinement, and provider validation can be
    completed in separate work packets; all four records are still required
    by ``production_claim_allowed``.
    """

    if not isinstance(evidence, MocReflectedDomainPromotionEvidence):
      raise TypeError(
        'evidence must be a MocReflectedDomainPromotionEvidence'
      )
    ####
    if not self.physical_closure_verified:
      raise ValueError(
        'promotion evidence requires a locally physically verified closure'
      )
    ####
    fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(self)
    if evidence.closure_fingerprint != fingerprint:
      raise ValueError(
        'promotion evidence closure_fingerprint does not match this closure'
      )
    ####
    if not evidence.has_verified_gate:
      raise ValueError(
        'promotion evidence must contain at least one verified gate record'
      )
    ####
    return replace(
      self,
      canonical_free_boundary_verified=evidence.canonical_free_boundary_verified,
      canonical_euler_verified=evidence.canonical_euler_verified,
      refinement_verified=evidence.refinement_verified,
      external_validation_verified=evidence.external_validation_verified,
      promotion_evidence=evidence,
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return not all(self.production_promotion_gates.values())
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return all(self.production_promotion_gates.values())
  ####

  @property
  def incoming_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    if self.global_euler is None:
      return ()
    ####
    return self.global_euler.incoming_handoff
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is MocReflectedDomainGlobalPhysicalClosureStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.physical_closure_verified:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'termination_model': 'globally-coupled-reflected-physical-closure',
        'status': self.status.value,
        'physical_closure_verified': self.physical_closure_verified,
        'source_frontier_verified': self.source_frontier_verified,
        'incoming_handoff_verified': self.incoming_handoff_verified,
        'variable_entropy_transport_verified': self.variable_entropy_transport_verified,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'downstream_boundary': (
          None
          if self.downstream_boundary is None
          else self.downstream_boundary.as_report()
        ),
        'downstream_boundary_audit': (
          None
          if self.downstream_boundary_audit is None
          else self.downstream_boundary_audit.as_report()
        ),
        'downstream_boundary_model': self.downstream_boundary_model,
        'promotion_blockers': list(self.promotion_blockers),
        'promotion_evidence_bound': self.promotion_evidence_bound,
        'production_promotion_gates': dict(self.production_promotion_gates),
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'source_frontier_verified': self.source_frontier_verified,
      'incoming_handoff_verified': self.incoming_handoff_verified,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'variable_entropy_transport_verified': self.variable_entropy_transport_verified,
      'maximum_entropy_lineage_residual': self.maximum_entropy_lineage_residual,
      'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'downstream_boundary': (
        None
        if self.downstream_boundary is None
        else self.downstream_boundary.as_report()
      ),
      'downstream_boundary_audit': (
        None
        if self.downstream_boundary_audit is None
        else self.downstream_boundary_audit.as_report()
      ),
      'downstream_boundary_model': self.downstream_boundary_model,
      'promotion_blockers': list(self.promotion_blockers),
      'closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(self)
      ),
      'promotion_evidence_bound': self.promotion_evidence_bound,
      'promotion_evidence': (
        None
        if self.promotion_evidence is None
        else self.promotion_evidence.as_report()
      ),
      'production_promotion_gates': dict(self.production_promotion_gates),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'global_remesh': None if self.global_remesh is None else self.global_remesh.as_report(),
      'global_euler': None if self.global_euler is None else self.global_euler.as_report(),
      'global_audit': None if self.global_audit is None else self.global_audit.as_report(),
      'field_audit': None if self.field_audit is None else self.field_audit.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _closure_result(
  status: MocReflectedDomainGlobalPhysicalClosureStatus,
  source_band: MocReflectedDomainAlternatingSourceResult | None,
  global_remesh: MocReflectedDomainGlobalShockRemeshResult | None,
  global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult | None,
  *,
  global_audit: Any | None = None,
  field_audit: Any | None = None,
  source_frontier_verified: bool = False,
  incoming_handoff_verified: bool = False,
  variable_entropy_transport_verified: bool = False,
  maximum_entropy_lineage_residual: float | None = None,
  cell_euler_residuals_verified: bool = False,
  downstream_boundary: MocReflectedDomainDownstreamBoundaryResult | None = None,
  downstream_boundary_audit: Any | None = None,
  message: str,
) -> MocReflectedDomainGlobalPhysicalClosureResult:
  return MocReflectedDomainGlobalPhysicalClosureResult(
    status=status,
    source_band=source_band,
    global_remesh=global_remesh,
    global_euler=global_euler,
    global_audit=global_audit,
    field_audit=field_audit,
    source_frontier_verified=source_frontier_verified,
    incoming_handoff_verified=incoming_handoff_verified,
    variable_entropy_transport_verified=variable_entropy_transport_verified,
    maximum_entropy_lineage_residual=maximum_entropy_lineage_residual,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    downstream_boundary=downstream_boundary,
    downstream_boundary_audit=downstream_boundary_audit,
    message=message,
  )
####


def solve_reflected_domain_global_physical_closure(
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
  euler_reconciliation_shock_angle_tolerance_rad: float = 1.0e-8,
  euler_reconciliation_residual_tolerance: float = 1.0e-8,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  maximum_attempts: int = 64,
) -> MocReflectedDomainGlobalPhysicalClosureResult:
  """Solve and independently audit one globally coupled physical closure.

  The source band is the only upstream field input.  Shock geometry is
  generated by the solver-owned global remesh and then reconciled against the
  exact Euler shock equations.  The result deliberately stops below the
  canonical free-boundary and external-validation gates.
  """

  status_type = MocReflectedDomainGlobalPhysicalClosureStatus
  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    return _closure_result(
      status_type.INVALID_INPUT,
      None,
      None,
      None,
      message='source_band must be a MocReflectedDomainAlternatingSourceResult',
    )
  ####
  try:
    resolved_handoff = (
      source_band.incoming_handoff
      if incoming_handoff is None
      else tuple(incoming_handoff)
    )
  except TypeError:
    return _closure_result(
      status_type.INVALID_INPUT,
      source_band,
      None,
      None,
      message='incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  ####
  if any(not isinstance(sample, MocChainBoundarySample) for sample in resolved_handoff):
    return _closure_result(
      status_type.INVALID_INPUT,
      source_band,
      None,
      None,
      message='incoming_handoff must contain MocChainBoundarySample values',
    )
  ####
  if resolved_handoff != source_band.incoming_handoff:
    return _closure_result(
      status_type.INVALID_INPUT,
      source_band,
      None,
      None,
      incoming_handoff_verified=False,
      message='incoming_handoff must exactly match the source-band handoff',
    )
  ####
  if not source_band.source_field_verified:
    return _closure_result(
      status_type.GLOBAL_REMESH_FAILURE,
      source_band,
      None,
      None,
      incoming_handoff_verified=True,
      message='global physical closure requires a verified bounded source band',
    )
  ####
  try:
    global_remesh = solve_reflected_domain_global_shock_remesh(
      source_band,
      outer_source_indices=outer_source_indices,
      target_centerline_indices=target_centerline_indices,
      compression_amplitude_lower_rad=compression_amplitude_lower_rad,
      compression_amplitude_upper_rad=compression_amplitude_upper_rad,
      compression_envelope_skews=compression_envelope_skews,
      closure_tolerance_m=closure_tolerance_m,
      incoming_handoff=resolved_handoff,
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
      maximum_attempts=maximum_attempts,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _closure_result(
      status_type.GLOBAL_REMESH_FAILURE,
      source_band,
      None,
      None,
      incoming_handoff_verified=True,
      message=f'global shock remesh raised: {error}',
    )
  ####
  if not global_remesh.attempts or global_remesh.selected_attempt is None:
    return _closure_result(
      status_type.GLOBAL_REMESH_FAILURE,
      source_band,
      global_remesh,
      None,
      incoming_handoff_verified=True,
      message=f'global shock remesh retained no selectable attempt: {global_remesh.message}',
    )
  ####
  try:
    global_euler = solve_reflected_domain_global_euler_shock_boundary(
      global_remesh,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=euler_reconciliation_shock_angle_tolerance_rad,
      residual_tolerance=euler_reconciliation_residual_tolerance,
      maximum_boundary_iterations=maximum_boundary_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _closure_result(
      status_type.GLOBAL_EULER_FAILURE,
      source_band,
      global_remesh,
      None,
      incoming_handoff_verified=True,
      message=f'global Euler closure raised: {error}',
    )
  ####
  downstream_boundary = _build_downstream_boundary_result(
    global_remesh,
    global_euler,
  )
  if not global_euler.converged:
    return _closure_result(
      status_type.GLOBAL_EULER_FAILURE,
      source_band,
      global_remesh,
      global_euler,
      source_frontier_verified=global_euler.source_frontier_verified,
      incoming_handoff_verified=global_euler.incoming_handoff_verified,
      downstream_boundary=downstream_boundary,
      message=f'global Euler closure did not converge: {global_euler.message}',
    )
  ####
  downstream_boundary_audit: Any | None = None
  try:
    from exhaust_plume.validation.moc_euler import measure_moc_euler_ambient_physical_field
    from exhaust_plume.validation.moc_measurements import (
      measure_moc_reflected_domain_downstream_boundary,
      measure_moc_reflected_domain_global_euler_shock_boundary,
    )

    downstream_boundary_audit = measure_moc_reflected_domain_downstream_boundary(
      downstream_boundary,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      residual_tolerance=max(pressure_tolerance, tangent_tolerance),
    )
    global_audit = measure_moc_reflected_domain_global_euler_shock_boundary(
      global_euler,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
    )
    field_audit = (
      None
      if global_euler.physical_field is None
      else measure_moc_euler_ambient_physical_field(
        global_euler.physical_field,
        position_tolerance_m=position_tolerance_m,
        pressure_tolerance=pressure_tolerance,
        invariant_tolerance=invariant_tolerance,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _closure_result(
      status_type.INDEPENDENT_AUDIT_FAILURE,
      source_band,
      global_remesh,
      global_euler,
      source_frontier_verified=global_euler.source_frontier_verified,
      incoming_handoff_verified=global_euler.incoming_handoff_verified,
      downstream_boundary=downstream_boundary,
      downstream_boundary_audit=downstream_boundary_audit,
      message=f'global physical closure independent audit raised: {error}',
    )
  ####
  if downstream_boundary_audit is None or not downstream_boundary_audit.converged:
    return _closure_result(
      status_type.INDEPENDENT_AUDIT_FAILURE,
      source_band,
      global_remesh,
      global_euler,
      source_frontier_verified=global_euler.source_frontier_verified,
      incoming_handoff_verified=global_euler.incoming_handoff_verified,
      downstream_boundary=downstream_boundary,
      downstream_boundary_audit=downstream_boundary_audit,
      message=(
        'global physical closure downstream-boundary audit failed: '
        f'{"audit was not produced" if downstream_boundary_audit is None else downstream_boundary_audit.message}'
      ),
    )
  ####
  entropy_verified, maximum_entropy_residual, entropy_message = (
    _variable_entropy_transport_audit(
      source_band,
      global_euler,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
    )
  )
  cell_residuals_verified = bool(
    field_audit is not None
    and field_audit.cell_euler_residuals_verified
  )
  provisional = _closure_result(
    status_type.CONVERGED_GLOBAL_PHYSICAL_CLOSURE,
    source_band,
    global_remesh,
    global_euler,
    global_audit=global_audit,
    field_audit=field_audit,
    source_frontier_verified=global_euler.source_frontier_verified,
    incoming_handoff_verified=global_euler.incoming_handoff_verified,
    variable_entropy_transport_verified=entropy_verified,
    maximum_entropy_lineage_residual=maximum_entropy_residual,
    cell_euler_residuals_verified=cell_residuals_verified,
    downstream_boundary=downstream_boundary,
    downstream_boundary_audit=downstream_boundary_audit,
    message=(
      'globally coupled exact-Euler shock, ambient, centerline, entropy, and '
      'cell-residual gates passed locally; canonical free-boundary, refinement, '
      'and external validation remain promotion gates'
      if entropy_verified and cell_residuals_verified
      else entropy_message
    ),
  )
  if provisional.physical_closure_verified:
    return provisional
  ####
  failure_status = (
    status_type.ENTROPY_TRANSPORT_FAILURE
    if not entropy_verified
    else status_type.INDEPENDENT_AUDIT_FAILURE
  )
  return _closure_result(
    failure_status,
    source_band,
    global_remesh,
    global_euler,
    global_audit=global_audit,
    field_audit=field_audit,
    source_frontier_verified=global_euler.source_frontier_verified,
    incoming_handoff_verified=global_euler.incoming_handoff_verified,
    variable_entropy_transport_verified=entropy_verified,
    maximum_entropy_lineage_residual=maximum_entropy_residual,
    cell_euler_residuals_verified=cell_residuals_verified,
    downstream_boundary=downstream_boundary,
    downstream_boundary_audit=downstream_boundary_audit,
    message=(
      'global Euler field did not pass the coupled physical closure gates: '
      f'{entropy_message}'
      if not entropy_verified
      else 'global Euler field did not pass the independent physical-field or cell-residual audit'
    ),
  )
####


class MocProductionShockCellFitStatus(str, Enum):
  """Outcome of the frontier-only next shock-cell fitting seam."""

  CONVERGED_LOCAL_FIT = 'converged_local_production_shock_cell_fit'
  INVALID_INPUT = 'invalid_input'
  CLOSURE_REQUIRED = 'production_shock_cell_global_closure_required'
  FRONTIER_FAILURE = 'production_shock_cell_frontier_failure'
  SHOCK_FIT_FAILURE = 'production_shock_cell_fit_failure'
  FIELD_FAILURE = 'production_shock_cell_field_failure'
####


@dataclass(frozen=True, slots=True)
class MocProductionShockCellFitResult:
  """A solver-generated shock-cell candidate with a hard production gate."""

  status: MocProductionShockCellFitStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  incoming_frontier: tuple[MocChainBoundarySample, ...]
  shock_fit: MocEulerShockBoundaryCurveResult | None
  candidate_field: MocPhysicalPostShockFieldResult | None
  candidate_cell: MocChainCell | None
  fitted_shock_points_m: tuple[tuple[float, float], ...] = ()
  frontier_verified: bool = False
  shock_fit_verified: bool = False
  start_x_m: float | None = None
  end_x_m: float | None = None
  cell_index: int = 1
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocProductionShockCellFitStatus):
      raise TypeError('status must be a MocProductionShockCellFitStatus')
    ####
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('closure must be a MocReflectedDomainGlobalPhysicalClosureResult or None')
    ####
    frontier = tuple(self.incoming_frontier)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in frontier):
      raise TypeError('incoming_frontier must contain MocChainBoundarySample values')
    ####
    object.__setattr__(self, 'incoming_frontier', frontier)
    if self.shock_fit is not None and not isinstance(
      self.shock_fit,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError('shock_fit must be a MocEulerShockBoundaryCurveResult or None')
    ####
    if self.candidate_field is not None and not isinstance(
      self.candidate_field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError('candidate_field must be a MocPhysicalPostShockFieldResult or None')
    ####
    if self.candidate_cell is not None and not isinstance(self.candidate_cell, MocChainCell):
      raise TypeError('candidate_cell must be a MocChainCell or None')
    ####
    points = tuple(
      (float(point[0]), float(point[1])) for point in self.fitted_shock_points_m
    )
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('fitted_shock_points_m must contain finite coordinates')
    ####
    object.__setattr__(self, 'fitted_shock_points_m', points)
    for name in ('frontier_verified', 'shock_fit_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('start_x_m', 'end_x_m'):
      value = getattr(self, name)
      if value is not None:
        normalized = float(value)
        if not isfinite(normalized):
          raise ValueError(f'{name} must be finite when supplied')
        ####
        object.__setattr__(self, name, normalized)
      ####
    ####
    if isinstance(self.cell_index, bool) or not isinstance(self.cell_index, int) or self.cell_index < 1:
      raise ValueError('cell_index must be a positive integer')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def local_fit_verified(self) -> bool:
    return bool(
      self.status is MocProductionShockCellFitStatus.CONVERGED_LOCAL_FIT
      and self.closure is not None
      and self.closure.physical_closure_verified
      and self.frontier_verified
      and self.shock_fit_verified
      and self.shock_fit is not None
      and self.shock_fit.local_euler_verified
      and self.candidate_field is not None
      and self.candidate_field.physical_closure_verified
      and self.candidate_field.state_sampling_available
      and self.candidate_cell is not None
    )
  ####

  @property
  def production_promotion_gates(self) -> Mapping[str, bool]:
    closure_gates = (
      MappingProxyType({})
      if self.closure is None
      else self.closure.production_promotion_gates
    )
    return MappingProxyType({
      'local_fit_verified': self.local_fit_verified,
      'frontier_verified': self.frontier_verified,
      'shock_fit_verified': self.shock_fit_verified,
      'downstream_boundary_closure_verified': bool(
        closure_gates.get('downstream_boundary_closure_verified', False)
      ),
      'canonical_free_boundary_verified': bool(
        closure_gates.get('canonical_free_boundary_verified', False)
      ),
      'canonical_euler_verified': bool(
        closure_gates.get('canonical_euler_verified', False)
      ),
      'refinement_verified': bool(closure_gates.get('refinement_verified', False)),
      'external_validation_verified': bool(
        closure_gates.get('external_validation_verified', False)
      ),
    })
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return not all(self.production_promotion_gates.values())
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return all(self.production_promotion_gates.values())
  ####

  def as_production_chain_cell(self) -> MocChainCell:
    """Return a production cell only after every explicit promotion gate."""

    if not self.production_claim_allowed or self.candidate_cell is None:
      raise ValueError(
        'production shock-cell promotion is blocked until canonical closure, '
        'refinement, and external validation pass'
      )
    ####
    return self.candidate_cell
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is MocProductionShockCellFitStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.local_fit_verified:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    elif self.status is MocProductionShockCellFitStatus.FRONTIER_FAILURE:
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'termination_model': 'frontier-only-production-shock-cell-fit',
        'status': self.status.value,
        'local_fit_verified': self.local_fit_verified,
        'frontier_verified': self.frontier_verified,
        'shock_fit_verified': self.shock_fit_verified,
        'production_promotion_gates': dict(self.production_promotion_gates),
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'prescribed_shock_geometry_consumed': False,
        'template_schedule_consumed': False,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'local_fit_verified': self.local_fit_verified,
      'frontier_verified': self.frontier_verified,
      'shock_fit_verified': self.shock_fit_verified,
      'fitted_shock_points_m': [list(point) for point in self.fitted_shock_points_m],
      'start_x_m': self.start_x_m,
      'end_x_m': self.end_x_m,
      'cell_index': self.cell_index,
      'incoming_frontier_sample_count': len(self.incoming_frontier),
      'production_promotion_gates': dict(self.production_promotion_gates),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'prescribed_shock_geometry_consumed': False,
      'template_schedule_consumed': False,
      'shock_fit': None if self.shock_fit is None else self.shock_fit.as_report(),
      'candidate_field': (
        None if self.candidate_field is None else self.candidate_field.as_report()
      ),
      'candidate_cell_available': self.candidate_cell is not None,
      'closure': None if self.closure is None else self.closure.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _fit_result(
  status: MocProductionShockCellFitStatus,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None,
  frontier: Sequence[MocChainBoundarySample],
  *,
  shock_fit: MocEulerShockBoundaryCurveResult | None = None,
  candidate_field: MocPhysicalPostShockFieldResult | None = None,
  candidate_cell: MocChainCell | None = None,
  fitted_shock_points_m: Sequence[tuple[float, float]] = (),
  frontier_verified: bool = False,
  shock_fit_verified: bool = False,
  start_x_m: float | None = None,
  end_x_m: float | None = None,
  cell_index: int = 1,
  message: str,
) -> MocProductionShockCellFitResult:
  return MocProductionShockCellFitResult(
    status=status,
    closure=closure,
    incoming_frontier=tuple(frontier),
    shock_fit=shock_fit,
    candidate_field=candidate_field,
    candidate_cell=candidate_cell,
    fitted_shock_points_m=tuple(fitted_shock_points_m),
    frontier_verified=frontier_verified,
    shock_fit_verified=shock_fit_verified,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    cell_index=cell_index,
    message=message,
  )
####


def fit_reflected_domain_production_shock_cell(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  start_x_m: float,
  end_x_m: float,
  cell_index: int = 1,
  incoming_frontier: Sequence[MocChainBoundarySample] | None = None,
  position_tolerance_m: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  branch: ShockBranch = ShockBranch.WEAK,
) -> MocProductionShockCellFitResult:
  """Fit one next shock cell from a verified typed frontier.

  The accepted closure owns the shock geometry.  This function only
  re-samples and re-fits that solver-generated geometry against the bounded
  source field before producing a research candidate cell.  Callers cannot
  provide shock points, downstream angle schedules, or a scaled template.
  """

  status_type = MocProductionShockCellFitStatus
  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _fit_result(
      status_type.INVALID_INPUT,
      None,
      (),
      message='closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  try:
    start = float(start_x_m)
    end = float(end_x_m)
    position_tolerance = float(position_tolerance_m)
    angle_tolerance = float(shock_angle_tolerance_rad)
    fit_tolerance = float(residual_tolerance)
  except (TypeError, ValueError):
    return _fit_result(
      status_type.INVALID_INPUT,
      closure,
      (),
      start_x_m=None,
      end_x_m=None,
      cell_index=cell_index,
      message='shock-cell fit geometry and tolerances must be numeric',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (position_tolerance, angle_tolerance, fit_tolerance)
  ) or not all(isfinite(value) for value in (start, end)) or end <= start:
    return _fit_result(
      status_type.INVALID_INPUT,
      closure,
      (),
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='shock-cell fit requires finite positive tolerances and end_x_m > start_x_m',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _fit_result(
      status_type.INVALID_INPUT,
      closure,
      (),
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='branch must be a ShockBranch',
    )
  ####
  if (
    isinstance(cell_index, bool)
    or not isinstance(cell_index, int)
    or cell_index < 1
  ):
    return _fit_result(
      status_type.INVALID_INPUT,
      closure,
      (),
      start_x_m=start,
      end_x_m=end,
      cell_index=1,
      message='cell_index must be a positive integer',
    )
  ####
  try:
    frontier = (
      closure.incoming_handoff
      if incoming_frontier is None
      else tuple(incoming_frontier)
    )
  except TypeError:
    return _fit_result(
      status_type.INVALID_INPUT,
      closure,
      (),
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='incoming_frontier must be an iterable of MocChainBoundarySample values',
    )
  ####
  if any(not isinstance(sample, MocChainBoundarySample) for sample in frontier):
    return _fit_result(
      status_type.INVALID_INPUT,
      closure,
      frontier,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='incoming_frontier must contain MocChainBoundarySample values',
    )
  ####
  frontier_verified = bool(frontier and frontier == closure.incoming_handoff)
  if not frontier_verified:
    return _fit_result(
      status_type.FRONTIER_FAILURE,
      closure,
      frontier,
      frontier_verified=False,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='incoming_frontier must exactly match the globally coupled closure handoff',
    )
  ####
  if not closure.physical_closure_verified:
    return _fit_result(
      status_type.CLOSURE_REQUIRED,
      closure,
      frontier,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='production shock-cell fitting requires a verified global physical closure',
    )
  ####
  source_band = closure.source_band
  global_euler = closure.global_euler
  physical_result = None if global_euler is None else global_euler.physical_field
  field = None if physical_result is None else physical_result.field
  if source_band is None or global_euler is None or physical_result is None or field is None:
    return _fit_result(
      status_type.FIELD_FAILURE,
      closure,
      frontier,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='global physical closure retained no state-carrying field for fitting',
    )
  ####
  points = tuple(global_euler.remeshed_shock_points_m)
  if len(points) < 3 or any(
    second[0] <= first[0] + position_tolerance
    or second[1] > first[1] + position_tolerance
    for first, second in zip(points, points[1:])
  ):
    return _fit_result(
      status_type.SHOCK_FIT_FAILURE,
      closure,
      frontier,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='global closure retained no ordered solver-generated shock path',
    )
  ####
  if points[0][0] <= start + position_tolerance:
    return _fit_result(
      status_type.SHOCK_FIT_FAILURE,
      closure,
      frontier,
      fitted_shock_points_m=points,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='solver-generated next shock does not start downstream of start_x_m',
    )
  ####
  if not field.ambient_boundary_points_m:
    return _fit_result(
      status_type.FIELD_FAILURE,
      closure,
      frontier,
      fitted_shock_points_m=points,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='closed physical field retained no ambient boundary path',
    )
  ####
  if end < field.ambient_boundary_points_m[-1][0] - position_tolerance:
    return _fit_result(
      status_type.FIELD_FAILURE,
      closure,
      frontier,
      fitted_shock_points_m=points,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message='end_x_m truncates the retained closed physical field',
    )
  ####

  upstream_states = []
  upstream_pressures = []
  for index, point in enumerate(points):
    state = source_band.state_at(
      point,
      position_tolerance_m=position_tolerance,
    )
    pressure = source_band.static_pressure_at(
      point,
      position_tolerance_m=position_tolerance,
    )
    if state is None or pressure is None or not isfinite(float(pressure)) or pressure <= 0.0:
      return _fit_result(
        status_type.FRONTIER_FAILURE,
        closure,
        frontier,
        fitted_shock_points_m=points,
        frontier_verified=True,
        start_x_m=start,
        end_x_m=end,
        cell_index=cell_index,
        message=f'bounded source frontier cannot reproduce shock sample {index}',
      )
    ####
    upstream_states.append(state)
    upstream_pressures.append(float(pressure))
  ####
  try:
    shock_fit = fit_euler_consistent_shock_boundary_from_geometry(
      tuple(upstream_states),
      tuple(upstream_pressures),
      points,
      branch=branch,
      position_tolerance_m=position_tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
      residual_tolerance=fit_tolerance,
      allow_zero_strength_endpoints=True,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _fit_result(
      status_type.SHOCK_FIT_FAILURE,
      closure,
      frontier,
      fitted_shock_points_m=points,
      frontier_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message=f'frontier-only shock fit raised: {error}',
    )
  ####
  if not shock_fit.converged or not shock_fit.local_euler_verified:
    return _fit_result(
      status_type.SHOCK_FIT_FAILURE,
      closure,
      frontier,
      shock_fit=shock_fit,
      fitted_shock_points_m=points,
      frontier_verified=True,
      shock_fit_verified=False,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message=f'frontier-only shock fit did not pass its Euler gate: {shock_fit.message}',
    )
  ####
  try:
    candidate_cell = field.as_coupled_chain_cell(
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      diagnostics={
        'fitting_model': 'frontier-only-solver-generated-global-euler-shock',
        'production_fit_candidate': True,
        'production_claim_allowed': False,
        'fitted_shock_points_m': [list(point) for point in points],
        'fitted_shock': shock_fit.as_report(),
      },
    )
  except (TypeError, ValueError) as error:
    return _fit_result(
      status_type.FIELD_FAILURE,
      closure,
      frontier,
      shock_fit=shock_fit,
      candidate_field=field,
      fitted_shock_points_m=points,
      frontier_verified=True,
      shock_fit_verified=True,
      start_x_m=start,
      end_x_m=end,
      cell_index=cell_index,
      message=f'closed physical field could not become a fitting candidate: {error}',
    )
  ####
  return _fit_result(
    status_type.CONVERGED_LOCAL_FIT,
    closure,
    frontier,
    shock_fit=shock_fit,
    candidate_field=field,
    candidate_cell=candidate_cell,
    fitted_shock_points_m=points,
    frontier_verified=True,
    shock_fit_verified=True,
    start_x_m=start,
    end_x_m=end,
    cell_index=cell_index,
    message=(
      'solver-generated shock geometry was independently re-fit from the '
      'typed frontier; candidate cell retained, production promotion blocked '
      'by canonical/refinement/external gates'
    ),
  )
####


fit_production_shock_cell_from_frontier = fit_reflected_domain_production_shock_cell
