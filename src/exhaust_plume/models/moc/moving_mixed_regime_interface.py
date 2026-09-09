"""Solver-owned conservative seam for a moving mixed-regime interface.

The retained terminal normal shock is a scalar state bound to one point.  A
downstream subsonic solve needs more: an explicit moving-interface geometry
and conservative boundary states on the requested section.  This module
defines that seam without borrowing the variable-entropy, quasi-one-
dimensional, or potential references.  It admits exact supplied data and
reports the remaining field requirement; it does not synthesize missing
ordinates, move an interface by endpoint hold, or claim a closed field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, sin
from typing import Any

from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryResult,
  measure_moc_transonic_shock_geometry,
)

__all__ = (
  'MOC_MOVING_MIXED_REGIME_INTERFACE_OPERATOR_ID',
  'MOC_MOVING_MIXED_REGIME_INTERFACE_AUDIT_OPERATOR_ID',
  'MocMovingMixedRegimeInterfaceStatus',
  'MocMovingMixedRegimeInterfaceAuditStatus',
  'MocMovingMixedRegimeConservativeBoundarySample',
  'build_moc_terminal_conservative_boundary_sample',
  'MocMovingMixedRegimeInterfaceRequest',
  'MocMovingMixedRegimeInterfaceResult',
  'MocMovingMixedRegimeInterfaceAudit',
  'prepare_moc_moving_mixed_regime_interface',
  'measure_moc_moving_mixed_regime_interface',
)


MOC_MOVING_MIXED_REGIME_INTERFACE_OPERATOR_ID = (
  'op.moc.moving-mixed-regime-interface-conservative-boundary-seam'
)
MOC_MOVING_MIXED_REGIME_INTERFACE_AUDIT_OPERATOR_ID = (
  'op.moc.moving-mixed-regime-interface-conservative-boundary-seam-audit'
)
DEFAULT_POSITION_TOLERANCE_M = 1.0e-9
DEFAULT_STATE_TOLERANCE = 1.0e-8
DEFAULT_NORMAL_TOLERANCE = 1.0e-8
DEFAULT_GAS_CONSTANT_J_KGK = 287.05


class MocMovingMixedRegimeInterfaceStatus(str, Enum):
  """Typed outcome of the solver-owned moving-interface boundary seam."""

  CONVERGED_BOUNDARY_SEAM = (
    'converged-moving-mixed-regime-conservative-boundary-seam'
  )
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_AUDIT_REQUIRED = (
    'moving-mixed-regime-interface-geometry-audit-required'
  )
  INTERFACE_GEOMETRY_REQUIRED = (
    'moving-mixed-regime-interface-geometry-required'
  )
  CONSERVATIVE_BOUNDARY_REQUIRED = (
    'moving-mixed-regime-interface-conservative-boundary-required'
  )
  CONSERVATIVE_STATE_FAILURE = (
    'moving-mixed-regime-interface-conservative-state-failure'
  )
  SUBSONIC_FIELD_REQUIRED = (
    'moving-mixed-regime-subsonic-field-required'
  )


class MocMovingMixedRegimeInterfaceAuditStatus(str, Enum):
  """Typed outcome of independently remeasuring the boundary seam."""

  VERIFIED = 'verified-moving-mixed-regime-conservative-boundary-seam'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'moving-mixed-regime-interface-geometry-audit-failure'
  INTERFACE_LINEAGE_FAILURE = (
    'moving-mixed-regime-interface-geometry-lineage-failure'
  )
  CONSERVATIVE_BOUNDARY_FAILURE = (
    'moving-mixed-regime-interface-conservative-boundary-lineage-failure'
  )
  COVERAGE_FAILURE = 'moving-mixed-regime-interface-coverage-failure'
  CLAIM_FLAG_FAILURE = 'moving-mixed-regime-interface-claim-flag-failure'


def _finite_point(value: object, name: str) -> tuple[float, float]:
  try:
    point = (float(value[0]), float(value[1]))  # type: ignore[index]
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(f'{name} must contain two coordinates') from error
  ####
  if not all(isfinite(component) for component in point):
    raise ValueError(f'{name} must contain finite coordinates')
  ####
  return point


def _finite_positive(name: str, value: object) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric


def _state_residual(
  actual: tuple[float, float, float, float],
  expected: tuple[float, float, float, float],
) -> float:
  return max(
    abs(left - right) / max(1.0, abs(left), abs(right))
    for left, right in zip(actual, expected, strict=True)
  )


def _primitive_from_conservative(
  state: tuple[float, float, float, float],
  gamma: float,
) -> tuple[float, float, float, float]:
  density, momentum_u, momentum_v, energy = state
  if not isfinite(density) or density <= 0.0:
    raise ValueError('conservative boundary density must be finite and positive')
  ####
  velocity_u = momentum_u / density
  velocity_v = momentum_v / density
  pressure = (gamma - 1.0) * (
    energy - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError(
      'conservative boundary state must retain positive thermodynamic pressure'
    )
  ####
  return density, velocity_u, velocity_v, pressure


def _terminal_downstream_conservative_state(
  geometry: MocTransonicShockGeometryResult,
) -> tuple[float, float, float, float]:
  state = geometry.request.shock_state
  angle = state.upstream_flow_angle_rad
  density = state.downstream_density_kg_m3
  speed = state.downstream_speed_m_s
  pressure = state.downstream_static_pressure_Pa
  return (
    density,
    density * speed * cos(angle),
    density * speed * sin(angle),
    pressure / (state.gamma - 1.0) + 0.5 * density * speed * speed,
  )


@dataclass(frozen=True, slots=True)
class MocMovingMixedRegimeConservativeBoundarySample:
  """One explicitly supplied conservative state on the moving-field seam."""

  index: int
  point_m: tuple[float, float]
  conservative_state: tuple[float, float, float, float]
  normal_m: tuple[float, float] = (1.0, 0.0)
  source: str = 'solver-owned-moving-mixed-regime-boundary-state-v1'

  def __post_init__(self) -> None:
    if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
      raise ValueError('index must be a nonnegative integer')
    ####
    object.__setattr__(self, 'point_m', _finite_point(self.point_m, 'point_m'))
    state = tuple(float(value) for value in self.conservative_state)
    if len(state) != 4 or any(not isfinite(value) for value in state):
      raise ValueError(
        'conservative_state must contain four finite conservative values'
      )
    ####
    object.__setattr__(self, 'conservative_state', state)
    normal = _finite_point(self.normal_m, 'normal_m')
    if hypot(*normal) <= 0.0:
      raise ValueError('normal_m must have nonzero length')
    ####
    object.__setattr__(self, 'normal_m', normal)
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'index': self.index,
      'point_m': list(self.point_m),
      'conservative_state': list(self.conservative_state),
      'normal_m': list(self.normal_m),
      'source': self.source,
    }
  ####


def build_moc_terminal_conservative_boundary_sample(
  geometry: MocTransonicShockGeometryResult,
  *,
  index: int = 0,
  source: str = 'solver-owned-terminal-rankine-hugoniot-boundary-state-v1',
) -> MocMovingMixedRegimeConservativeBoundarySample:
  """Convert only the audited scalar downstream state into one boundary sample.

  This helper deliberately creates one exact terminal sample.  It does not
  extend the state to another ordinate or create a moving-interface trace.
  """

  if not isinstance(geometry, MocTransonicShockGeometryResult):
    raise TypeError('geometry must be a MocTransonicShockGeometryResult')
  ####
  if not geometry.geometry_verified:
    raise ValueError('geometry must be verified before its terminal state is consumed')
  ####
  return MocMovingMixedRegimeConservativeBoundarySample(
    index=index,
    point_m=geometry.shock_point_m,
    conservative_state=_terminal_downstream_conservative_state(geometry),
    source=source,
  )


@dataclass(frozen=True, slots=True)
class MocMovingMixedRegimeInterfaceRequest:
  """Inputs for one explicit moving-interface boundary admission attempt."""

  terminal_geometry: MocTransonicShockGeometryResult
  interface_points_m: tuple[tuple[float, float], ...]
  boundary_samples: tuple[MocMovingMixedRegimeConservativeBoundarySample, ...]
  cross_section_x_m: float
  lower_y_m: float
  upper_y_m: float
  sample_count: int = 9
  gas_constant_J_kgK: float = DEFAULT_GAS_CONSTANT_J_KGK
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M
  state_tolerance: float = DEFAULT_STATE_TOLERANCE
  normal_tolerance: float = DEFAULT_NORMAL_TOLERANCE
  source: str = 'solver-owned-moving-mixed-regime-interface-request-v1'

  def __post_init__(self) -> None:
    if not isinstance(
      self.terminal_geometry,
      MocTransonicShockGeometryResult,
    ):
      raise TypeError(
        'terminal_geometry must be a MocTransonicShockGeometryResult'
      )
    ####
    interface_points = tuple(
      _finite_point(point, 'interface_points_m')
      for point in self.interface_points_m
    )
    samples = tuple(self.boundary_samples)
    if any(
      not isinstance(sample, MocMovingMixedRegimeConservativeBoundarySample)
      for sample in samples
    ):
      raise TypeError(
        'boundary_samples must contain typed conservative boundary samples'
      )
    ####
    if len({sample.index for sample in samples}) != len(samples):
      raise ValueError('boundary_samples indices must be unique')
    ####
    object.__setattr__(self, 'interface_points_m', interface_points)
    object.__setattr__(self, 'boundary_samples', samples)
    for name in (
      'cross_section_x_m',
      'lower_y_m',
      'upper_y_m',
      'gas_constant_J_kgK',
      'position_tolerance_m',
      'state_tolerance',
      'normal_tolerance',
    ):
      numeric = float(getattr(self, name))
      if not isfinite(numeric):
        raise ValueError(f'{name} must be finite')
      ####
      if name in (
        'gas_constant_J_kgK',
        'position_tolerance_m',
        'state_tolerance',
        'normal_tolerance',
      ) and numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.upper_y_m <= self.lower_y_m:
      raise ValueError('upper_y_m must be strictly greater than lower_y_m')
    ####
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    ####
    gamma = self.terminal_geometry.request.shock_state.gamma
    if gamma <= 1.0:
      raise ValueError('terminal geometry must retain gamma greater than one')
    ####
    for sample in samples:
      if sample.index >= self.sample_count:
        raise ValueError('boundary sample index must be inside sample_count')
      ####
      if abs(sample.point_m[0] - self.cross_section_x_m) > self.position_tolerance_m:
        raise ValueError(
          'boundary samples must lie on the declared cross-section without '
          'x extrapolation'
        )
      ####
      if not (
        self.lower_y_m - self.position_tolerance_m
        <= sample.point_m[1]
        <= self.upper_y_m + self.position_tolerance_m
      ):
        raise ValueError(
          'boundary samples must lie inside the declared section interval'
        )
      ####
      expected_y = self.lower_y_m + (
        self.upper_y_m - self.lower_y_m
      ) * sample.index / (self.sample_count - 1)
      if abs(sample.point_m[1] - expected_y) > self.position_tolerance_m:
        raise ValueError(
          'boundary samples must retain the declared ordinate grid; '
          'interpolation or remapping is not accepted'
        )
      ####
      normal_length = hypot(*sample.normal_m)
      if abs(normal_length - 1.0) > self.normal_tolerance:
        raise ValueError('boundary sample normals must be unit vectors')
      ####
    ####
    object.__setattr__(self, 'source', str(self.source))
    if not self.source:
      raise ValueError('source must be non-empty')
  ####

  @property
  def gamma(self) -> float:
    return float(self.terminal_geometry.request.shock_state.gamma)
  ####

  @property
  def expected_sample_points_m(self) -> tuple[tuple[float, float], ...]:
    denominator = self.sample_count - 1
    return tuple(
      (
        self.cross_section_x_m,
        self.lower_y_m
        + (self.upper_y_m - self.lower_y_m) * index / denominator,
      )
      for index in range(self.sample_count)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_MOVING_MIXED_REGIME_INTERFACE_OPERATOR_ID,
      'terminal_geometry': self.terminal_geometry.as_report(),
      'interface_points_m': [list(point) for point in self.interface_points_m],
      'boundary_samples': [sample.as_report() for sample in self.boundary_samples],
      'cross_section_x_m': self.cross_section_x_m,
      'lower_y_m': self.lower_y_m,
      'upper_y_m': self.upper_y_m,
      'sample_count': self.sample_count,
      'expected_sample_points_m': [
        list(point) for point in self.expected_sample_points_m
      ],
      'gamma': self.gamma,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'normal_tolerance': self.normal_tolerance,
      'source': self.source,
      'no_extrapolation': True,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMovingMixedRegimeInterfaceResult:
  """Result of admitting a boundary seam, never a solved subsonic field."""

  status: MocMovingMixedRegimeInterfaceStatus
  request: MocMovingMixedRegimeInterfaceRequest
  terminal_geometry_audit: MocTransonicShockGeometryAudit
  interface_points_m: tuple[tuple[float, float], ...] = ()
  boundary_samples: tuple[MocMovingMixedRegimeConservativeBoundarySample, ...] = ()
  missing_sample_indices: tuple[int, ...] = ()
  terminal_conservative_state_residual: float | None = None
  terminal_conservative_state_verified: bool = False
  interface_geometry_verified: bool = False
  conservative_boundary_verified: bool = False
  complete_cross_section_coverage: bool = False
  moving_interface_solve_attempted: bool = False
  subsonic_field_required: bool = True
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMovingMixedRegimeInterfaceStatus):
      raise TypeError('status must be a moving mixed-regime interface status')
    ####
    if not isinstance(self.request, MocMovingMixedRegimeInterfaceRequest):
      raise TypeError('request must be a moving mixed-regime interface request')
    ####
    if not isinstance(self.terminal_geometry_audit, MocTransonicShockGeometryAudit):
      raise TypeError('terminal_geometry_audit must be a typed geometry audit')
    ####
    points = tuple(
      _finite_point(point, 'interface_points_m')
      for point in self.interface_points_m
    )
    if points != self.request.interface_points_m:
      raise ValueError('result must retain the exact requested interface geometry')
    ####
    samples = tuple(self.boundary_samples)
    if samples != self.request.boundary_samples:
      raise ValueError('result must retain the exact conservative boundary samples')
    ####
    missing = tuple(int(index) for index in self.missing_sample_indices)
    if any(
      isinstance(index, bool)
      or index < 0
      or index >= self.request.sample_count
      for index in missing
    ):
      raise ValueError('missing_sample_indices must be valid sample indices')
    if len(set(missing)) != len(missing):
      raise ValueError('missing_sample_indices must be unique')
    ####
    object.__setattr__(self, 'interface_points_m', points)
    object.__setattr__(self, 'boundary_samples', samples)
    object.__setattr__(self, 'missing_sample_indices', missing)
    if self.terminal_conservative_state_residual is not None:
      residual = float(self.terminal_conservative_state_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'terminal_conservative_state_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'terminal_conservative_state_residual', residual)
    ####
    for name in (
      'terminal_conservative_state_verified',
      'interface_geometry_verified',
      'conservative_boundary_verified',
      'complete_cross_section_coverage',
      'moving_interface_solve_attempted',
      'subsonic_field_required',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if not self.subsonic_field_required:
      raise ValueError('moving-interface seam must require a subsonic field')
    if self.moving_interface_solve_attempted:
      raise ValueError(
        'boundary seam cannot claim that the moving-interface field was solved'
      )
    if self.physical_closure_verified or not self.chain_promotion_blocked:
      raise ValueError('moving-interface seam cannot close or promote a field')
    if self.production_claim_allowed:
      raise ValueError('moving-interface seam cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def boundary_seam_verified(self) -> bool:
    return bool(
      self.status is MocMovingMixedRegimeInterfaceStatus.CONVERGED_BOUNDARY_SEAM
      and self.terminal_geometry_audit.converged
      and self.terminal_conservative_state_verified
      and self.interface_geometry_verified
      and self.conservative_boundary_verified
      and self.complete_cross_section_coverage
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_MOVING_MIXED_REGIME_INTERFACE_OPERATOR_ID,
      'status': self.status.value,
      'boundary_seam_verified': self.boundary_seam_verified,
      'interface_points_m': [list(point) for point in self.interface_points_m],
      'boundary_samples': [sample.as_report() for sample in self.boundary_samples],
      'missing_sample_indices': list(self.missing_sample_indices),
      'terminal_conservative_state_residual': (
        self.terminal_conservative_state_residual
      ),
      'terminal_conservative_state_verified': (
        self.terminal_conservative_state_verified
      ),
      'interface_geometry_verified': self.interface_geometry_verified,
      'conservative_boundary_verified': self.conservative_boundary_verified,
      'complete_cross_section_coverage': self.complete_cross_section_coverage,
      'moving_interface_solve_attempted': self.moving_interface_solve_attempted,
      'subsonic_field_required': self.subsonic_field_required,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'terminal_geometry_audit': self.terminal_geometry_audit.as_report(),
      'request': self.request.as_report(),
      'message': self.message,
      'claim_status': (
        'solver-owned-conservative-boundary-seam-only; moving mixed-regime '
        'subsonic field, independent Euler/entropy closure, refinement, and '
        'external validation remain open'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMovingMixedRegimeInterfaceAudit:
  """Independent remeasurement of the retained moving-interface seam."""

  status: MocMovingMixedRegimeInterfaceAuditStatus
  candidate: MocMovingMixedRegimeInterfaceResult | None
  operator_id: str = MOC_MOVING_MIXED_REGIME_INTERFACE_AUDIT_OPERATOR_ID
  terminal_geometry_rederived: bool = False
  interface_geometry_rederived: bool = False
  conservative_boundary_rederived: bool = False
  coverage_rederived: bool = False
  claim_flags_verified: bool = False
  terminal_conservative_state_residual: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMovingMixedRegimeInterfaceAuditStatus):
      raise TypeError('status must be a moving mixed-regime interface audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocMovingMixedRegimeInterfaceResult,
    ):
      raise TypeError('candidate must be a typed moving-interface result or None')
    ####
    for name in (
      'terminal_geometry_rederived',
      'interface_geometry_rederived',
      'conservative_boundary_rederived',
      'coverage_rederived',
      'claim_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.terminal_conservative_state_residual is not None:
      residual = float(self.terminal_conservative_state_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'terminal_conservative_state_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'terminal_conservative_state_residual', residual)
    ####
    if not str(self.operator_id):
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocMovingMixedRegimeInterfaceAuditStatus.VERIFIED
      and self.terminal_geometry_rederived
      and self.interface_geometry_rederived
      and self.conservative_boundary_rederived
      and self.coverage_rederived
      and self.claim_flags_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'terminal_geometry_rederived': self.terminal_geometry_rederived,
      'interface_geometry_rederived': self.interface_geometry_rederived,
      'conservative_boundary_rederived': self.conservative_boundary_rederived,
      'coverage_rederived': self.coverage_rederived,
      'claim_flags_verified': self.claim_flags_verified,
      'terminal_conservative_state_residual': (
        self.terminal_conservative_state_residual
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'message': self.message,
    }
  ####


def _result(
  status: MocMovingMixedRegimeInterfaceStatus,
  request: MocMovingMixedRegimeInterfaceRequest,
  geometry_audit: MocTransonicShockGeometryAudit,
  *,
  interface_points_m: tuple[tuple[float, float], ...] = (),
  boundary_samples: tuple[MocMovingMixedRegimeConservativeBoundarySample, ...] = (),
  missing_sample_indices: tuple[int, ...] = (),
  terminal_conservative_state_residual: float | None = None,
  terminal_conservative_state_verified: bool = False,
  interface_geometry_verified: bool = False,
  conservative_boundary_verified: bool = False,
  complete_cross_section_coverage: bool = False,
  message: str,
) -> MocMovingMixedRegimeInterfaceResult:
  return MocMovingMixedRegimeInterfaceResult(
    status=status,
    request=request,
    terminal_geometry_audit=geometry_audit,
    interface_points_m=request.interface_points_m
    if not interface_points_m
    else interface_points_m,
    boundary_samples=request.boundary_samples
    if not boundary_samples
    else boundary_samples,
    missing_sample_indices=missing_sample_indices,
    terminal_conservative_state_residual=terminal_conservative_state_residual,
    terminal_conservative_state_verified=terminal_conservative_state_verified,
    interface_geometry_verified=interface_geometry_verified,
    conservative_boundary_verified=conservative_boundary_verified,
    complete_cross_section_coverage=complete_cross_section_coverage,
    message=message,
  )


def _interface_geometry_check(
  request: MocMovingMixedRegimeInterfaceRequest,
) -> tuple[bool, str]:
  points = request.interface_points_m
  if len(points) < 2:
    return False, 'a moving interface requires at least two explicit geometry points'
  ####
  terminal = request.terminal_geometry.shock_point_m
  first = points[0]
  if max(abs(first[index] - terminal[index]) for index in range(2)) > (
    request.position_tolerance_m
  ):
    return False, 'the first interface point must equal the audited terminal point'
  ####
  for previous, current in zip(points, points[1:]):
    if current[0] <= previous[0] + request.position_tolerance_m:
      return False, 'moving interface points must be strictly downstream ordered'
  ####
  return True, 'explicit interface geometry retains the audited terminal point'


def _boundary_state_check(
  request: MocMovingMixedRegimeInterfaceRequest,
) -> tuple[bool, float | None, str]:
  gamma = request.gamma
  for sample in request.boundary_samples:
    try:
      _primitive_from_conservative(sample.conservative_state, gamma)
    except ValueError as error:
      return False, None, str(error)
    ####
  ####
  expected = _terminal_downstream_conservative_state(request.terminal_geometry)
  terminal_candidates = tuple(
    sample
    for sample in request.boundary_samples
    if max(
      abs(sample.point_m[index] - request.terminal_geometry.shock_point_m[index])
      for index in range(2)
    ) <= request.position_tolerance_m
  )
  if not terminal_candidates:
    return (
      False,
      None,
      'conservative boundary samples do not retain the exact audited terminal point',
    )
  ####
  residual = min(
    _state_residual(sample.conservative_state, expected)
    for sample in terminal_candidates
  )
  if residual > request.state_tolerance:
    return (
      False,
      residual,
      'terminal conservative state does not reproduce the audited downstream '
      'Rankine-Hugoniot state',
    )
  ####
  return True, residual, 'explicit conservative boundary states are physical'


def prepare_moc_moving_mixed_regime_interface(
  request: MocMovingMixedRegimeInterfaceRequest,
) -> MocMovingMixedRegimeInterfaceResult:
  """Admit explicit seam data without solving or extending the subsonic field."""

  if not isinstance(request, MocMovingMixedRegimeInterfaceRequest):
    raise TypeError('request must be a moving mixed-regime interface request')
  ####
  geometry_audit = measure_moc_transonic_shock_geometry(request.terminal_geometry)
  if not request.terminal_geometry.geometry_verified or not geometry_audit.converged:
    return _result(
      MocMovingMixedRegimeInterfaceStatus.GEOMETRY_AUDIT_REQUIRED,
      request,
      geometry_audit,
      message=(
        'moving-interface admission requires the independently audited scalar '
        'terminal Rankine-Hugoniot geometry'
      ),
    )
  ####
  interface_verified, interface_message = _interface_geometry_check(request)
  if not interface_verified:
    status = (
      MocMovingMixedRegimeInterfaceStatus.INTERFACE_GEOMETRY_REQUIRED
    )
    return _result(
      status,
      request,
      geometry_audit,
      message=interface_message,
    )
  ####
  conservative_verified, terminal_residual, state_message = _boundary_state_check(
    request
  )
  if not conservative_verified:
    status = (
      MocMovingMixedRegimeInterfaceStatus.CONSERVATIVE_STATE_FAILURE
      if terminal_residual is not None
      else MocMovingMixedRegimeInterfaceStatus.CONSERVATIVE_BOUNDARY_REQUIRED
    )
    return _result(
      status,
      request,
      geometry_audit,
      interface_points_m=request.interface_points_m,
      terminal_conservative_state_residual=terminal_residual,
      message=state_message,
    )
  ####
  supplied_indices = {sample.index for sample in request.boundary_samples}
  missing_indices = tuple(
    index
    for index in range(request.sample_count)
    if index not in supplied_indices
  )
  complete = not missing_indices
  if not complete:
    return _result(
      MocMovingMixedRegimeInterfaceStatus.SUBSONIC_FIELD_REQUIRED,
      request,
      geometry_audit,
      interface_points_m=request.interface_points_m,
      terminal_conservative_state_residual=terminal_residual,
      terminal_conservative_state_verified=True,
      interface_geometry_verified=True,
      conservative_boundary_verified=True,
      missing_sample_indices=missing_indices,
      message=(
        'the audited terminal conservative state and explicit moving-interface '
        'seed are retained, but the requested cross-section is incomplete; '
        f'missing sample indices={missing_indices}; no extrapolation was used'
      ),
    )
  ####
  return _result(
    MocMovingMixedRegimeInterfaceStatus.CONVERGED_BOUNDARY_SEAM,
    request,
    geometry_audit,
    interface_points_m=request.interface_points_m,
    terminal_conservative_state_residual=terminal_residual,
    terminal_conservative_state_verified=True,
    interface_geometry_verified=True,
    conservative_boundary_verified=True,
    complete_cross_section_coverage=True,
    message=(
      'explicit conservative boundary coverage and moving-interface geometry '
      'are admitted; the separate subsonic field solve and physical closure '
      'remain required'
    ),
  )


def _audit_failure(
  status: MocMovingMixedRegimeInterfaceAuditStatus,
  candidate: MocMovingMixedRegimeInterfaceResult | None,
  message: str,
  **kwargs: object,
) -> MocMovingMixedRegimeInterfaceAudit:
  return MocMovingMixedRegimeInterfaceAudit(
    status=status,
    candidate=candidate,
    message=message,
    **kwargs,
  )


def measure_moc_moving_mixed_regime_interface(
  candidate: MocMovingMixedRegimeInterfaceResult,
) -> MocMovingMixedRegimeInterfaceAudit:
  """Independently rederive seam geometry, state, and coverage lineage."""

  if not isinstance(candidate, MocMovingMixedRegimeInterfaceResult):
    return _audit_failure(
      MocMovingMixedRegimeInterfaceAuditStatus.INVALID_INPUT,
      None,
      'candidate must be a typed moving mixed-regime interface result',
    )
  ####
  expected = prepare_moc_moving_mixed_regime_interface(candidate.request)
  geometry_rederived = bool(
    expected.terminal_geometry_audit.converged
    and candidate.terminal_geometry_audit == expected.terminal_geometry_audit
  )
  if not geometry_rederived:
    return _audit_failure(
      MocMovingMixedRegimeInterfaceAuditStatus.GEOMETRY_FAILURE,
      candidate,
      'independent terminal geometry rederivation did not match the candidate',
      terminal_geometry_rederived=False,
    )
  ####
  interface_rederived = bool(
    candidate.interface_points_m == expected.interface_points_m
    and candidate.interface_geometry_verified == expected.interface_geometry_verified
  )
  if not interface_rederived:
    return _audit_failure(
      MocMovingMixedRegimeInterfaceAuditStatus.INTERFACE_LINEAGE_FAILURE,
      candidate,
      'candidate did not retain the exact explicit moving-interface geometry',
      terminal_geometry_rederived=True,
    )
  ####
  boundary_rederived = bool(
    candidate.boundary_samples == expected.boundary_samples
    and candidate.terminal_conservative_state_residual
    == expected.terminal_conservative_state_residual
    and candidate.terminal_conservative_state_verified
    == expected.terminal_conservative_state_verified
    and candidate.conservative_boundary_verified
    == expected.conservative_boundary_verified
  )
  if not boundary_rederived:
    return _audit_failure(
      MocMovingMixedRegimeInterfaceAuditStatus.CONSERVATIVE_BOUNDARY_FAILURE,
      candidate,
      'candidate did not retain the independently rederived conservative '
      'boundary state lineage',
      terminal_geometry_rederived=True,
      interface_geometry_rederived=True,
    )
  ####
  coverage_rederived = bool(
    candidate.status is expected.status
    and candidate.missing_sample_indices == expected.missing_sample_indices
    and candidate.complete_cross_section_coverage
    == expected.complete_cross_section_coverage
  )
  if not coverage_rederived:
    return _audit_failure(
      MocMovingMixedRegimeInterfaceAuditStatus.COVERAGE_FAILURE,
      candidate,
      'candidate cross-section coverage differs from independent remeasurement',
      terminal_geometry_rederived=True,
      interface_geometry_rederived=True,
      conservative_boundary_rederived=True,
    )
  ####
  flags_verified = bool(
    candidate.subsonic_field_required
    and not candidate.moving_interface_solve_attempted
    and not candidate.physical_closure_verified
    and candidate.chain_promotion_blocked
    and not candidate.production_claim_allowed
  )
  if not flags_verified:
    return _audit_failure(
      MocMovingMixedRegimeInterfaceAuditStatus.CLAIM_FLAG_FAILURE,
      candidate,
      'moving-interface result weakened its field-required or non-promotion flags',
      terminal_geometry_rederived=True,
      interface_geometry_rederived=True,
      conservative_boundary_rederived=True,
      coverage_rederived=True,
    )
  ####
  return MocMovingMixedRegimeInterfaceAudit(
    status=MocMovingMixedRegimeInterfaceAuditStatus.VERIFIED,
    candidate=candidate,
    terminal_geometry_rederived=True,
    interface_geometry_rederived=True,
    conservative_boundary_rederived=True,
    coverage_rederived=True,
    claim_flags_verified=True,
    terminal_conservative_state_residual=(
      expected.terminal_conservative_state_residual
    ),
    message=(
      'independent remeasurement reproduces the explicit conservative '
      'boundary seam and preserves the subsonic-field/non-promotion boundary'
    ),
  )
