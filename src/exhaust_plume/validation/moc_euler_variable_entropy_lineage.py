"""Independent variable-entropy lineage audit for an exact physical field.

The legacy ambient physical-field audit has a deliberately narrow uniform-
total-pressure diagnostic.  A fitted shock, however, may produce a different
downstream total pressure at every station.  This operator audits that
variable profile without comparing it to the first shock sample: the exact
post-shock boundary, the solver-produced ambient perimeter, and every
interior ``C-`` source must retain the matching pressure lineage.

This is a source-lineage and state-sampling gate.  It does not claim that the
reflected free boundary, the coupled mixed-regime field, or a production
shock-cell chain is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, log, sin, sqrt

from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)

__all__ = (
  'MOC_EULER_VARIABLE_ENTROPY_LINEAGE_AUDIT_OPERATOR_ID',
  'MocEulerVariableEntropyLineageAuditStatus',
  'MocEulerVariableEntropyLineageAudit',
  'measure_moc_euler_variable_entropy_lineage',
)


MOC_EULER_VARIABLE_ENTROPY_LINEAGE_AUDIT_OPERATOR_ID = (
  'op.moc.euler-variable-entropy-lineage-audit'
)


class MocEulerVariableEntropyLineageAuditStatus(str, Enum):
  """Typed outcomes for the variable-entropy lineage audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_variable_entropy_lineage_audit'
  INVALID_INPUT = 'invalid_input'
  SHOCK_LINEAGE_FAILURE = 'euler_variable_entropy_shock_lineage_failure'
  AMBIENT_LINEAGE_FAILURE = 'euler_variable_entropy_ambient_lineage_failure'
  INTERIOR_LINEAGE_FAILURE = 'euler_variable_entropy_interior_lineage_failure'
  FLAG_FAILURE = 'euler_variable_entropy_lineage_flag_failure'


def _log_pressure_residual(actual: float, expected: float) -> float:
  if actual <= 0.0 or expected <= 0.0:
    return float('inf')
  return abs(log(float(actual) / float(expected)))


@dataclass(frozen=True, slots=True)
class MocEulerVariableEntropyLineageAudit:
  """Independent variable-total-pressure source-lineage evidence."""

  status: MocEulerVariableEntropyLineageAuditStatus
  result_status: str | None
  sample_count: int
  shock_geometry_verified: bool
  shock_state_lineage_verified: bool
  shock_pressure_lineage_verified: bool
  ambient_geometry_verified: bool
  ambient_pressure_lineage_verified: bool
  interior_source_lineage_verified: bool
  interior_pressure_samples_verified: bool
  variable_entropy_lineage_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  entropy_advection_residuals: tuple[float, ...] = ()
  entropy_advection_verified: bool = False
  entropy_advection_tolerance: float = 1.0e-3
  maximum_entropy_advection_residual: float | None = None
  maximum_shock_coordinate_residual_m: float | None = None
  maximum_shock_state_residual: float | None = None
  maximum_shock_pressure_log_residual: float | None = None
  maximum_ambient_coordinate_residual_m: float | None = None
  maximum_ambient_pressure_log_residual: float | None = None
  maximum_interior_pressure_log_residual: float | None = None
  message: str = ''
  operator_id: str = MOC_EULER_VARIABLE_ENTROPY_LINEAGE_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerVariableEntropyLineageAuditStatus):
      raise TypeError(
        'status must be a MocEulerVariableEntropyLineageAuditStatus'
      )
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 0
    ):
      raise ValueError('sample_count must be a nonnegative integer')
    ####
    for name in (
      'shock_geometry_verified',
      'shock_state_lineage_verified',
      'shock_pressure_lineage_verified',
      'ambient_geometry_verified',
      'ambient_pressure_lineage_verified',
      'interior_source_lineage_verified',
      'interior_pressure_samples_verified',
      'variable_entropy_lineage_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'entropy_advection_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'maximum_shock_coordinate_residual_m',
      'maximum_shock_state_residual',
      'maximum_shock_pressure_log_residual',
      'maximum_ambient_coordinate_residual_m',
      'maximum_ambient_pressure_log_residual',
      'maximum_interior_pressure_log_residual',
      'maximum_entropy_advection_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    ####
    entropy_advection_residuals = tuple(
      float(value) for value in self.entropy_advection_residuals
    )
    if any(
      not isfinite(value) or value < 0.0
      for value in entropy_advection_residuals
    ):
      raise ValueError(
        'entropy_advection_residuals must contain finite nonnegative values'
      )
    ####
    entropy_advection_tolerance = float(self.entropy_advection_tolerance)
    if not isfinite(entropy_advection_tolerance) or entropy_advection_tolerance <= 0.0:
      raise ValueError('entropy_advection_tolerance must be finite and positive')
    ####
    object.__setattr__(
      self,
      'entropy_advection_residuals',
      entropy_advection_residuals,
    )
    object.__setattr__(
      self,
      'entropy_advection_tolerance',
      entropy_advection_tolerance,
    )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerVariableEntropyLineageAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock_geometry_verified
      and self.shock_state_lineage_verified
      and self.shock_pressure_lineage_verified
      and self.ambient_geometry_verified
      and self.ambient_pressure_lineage_verified
      and self.interior_source_lineage_verified
      and self.interior_pressure_samples_verified
      and self.variable_entropy_lineage_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'sample_count': self.sample_count,
      'shock_geometry_verified': self.shock_geometry_verified,
      'shock_state_lineage_verified': self.shock_state_lineage_verified,
      'shock_pressure_lineage_verified': self.shock_pressure_lineage_verified,
      'ambient_geometry_verified': self.ambient_geometry_verified,
      'ambient_pressure_lineage_verified': self.ambient_pressure_lineage_verified,
      'interior_source_lineage_verified': self.interior_source_lineage_verified,
      'interior_pressure_samples_verified': self.interior_pressure_samples_verified,
      'variable_entropy_lineage_verified': self.variable_entropy_lineage_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'entropy_advection_residuals': list(self.entropy_advection_residuals),
      'entropy_advection_verified': self.entropy_advection_verified,
      'entropy_advection_tolerance': self.entropy_advection_tolerance,
      'maximum_entropy_advection_residual': self.maximum_entropy_advection_residual,
      'maximum_shock_coordinate_residual_m': self.maximum_shock_coordinate_residual_m,
      'maximum_shock_state_residual': self.maximum_shock_state_residual,
      'maximum_shock_pressure_log_residual': self.maximum_shock_pressure_log_residual,
      'maximum_ambient_coordinate_residual_m': self.maximum_ambient_coordinate_residual_m,
      'maximum_ambient_pressure_log_residual': self.maximum_ambient_pressure_log_residual,
      'maximum_interior_pressure_log_residual': self.maximum_interior_pressure_log_residual,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerVariableEntropyLineageAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  sample_count: int = 0,
  shock_geometry_verified: bool = False,
  shock_state_lineage_verified: bool = False,
  shock_pressure_lineage_verified: bool = False,
  ambient_geometry_verified: bool = False,
  ambient_pressure_lineage_verified: bool = False,
  interior_source_lineage_verified: bool = False,
  interior_pressure_samples_verified: bool = False,
  variable_entropy_lineage_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  entropy_advection_residuals: tuple[float, ...] = (),
  entropy_advection_verified: bool = False,
  entropy_advection_tolerance: float = 1.0e-3,
  maximum_entropy_advection_residual: float | None = None,
  maximum_shock_coordinate_residual_m: float | None = None,
  maximum_shock_state_residual: float | None = None,
  maximum_shock_pressure_log_residual: float | None = None,
  maximum_ambient_coordinate_residual_m: float | None = None,
  maximum_ambient_pressure_log_residual: float | None = None,
  maximum_interior_pressure_log_residual: float | None = None,
) -> MocEulerVariableEntropyLineageAudit:
  return MocEulerVariableEntropyLineageAudit(
    status=status,
    result_status=result_status,
    sample_count=sample_count,
    shock_geometry_verified=shock_geometry_verified,
    shock_state_lineage_verified=shock_state_lineage_verified,
    shock_pressure_lineage_verified=shock_pressure_lineage_verified,
    ambient_geometry_verified=ambient_geometry_verified,
    ambient_pressure_lineage_verified=ambient_pressure_lineage_verified,
    interior_source_lineage_verified=interior_source_lineage_verified,
    interior_pressure_samples_verified=interior_pressure_samples_verified,
    variable_entropy_lineage_verified=variable_entropy_lineage_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    entropy_advection_residuals=entropy_advection_residuals,
    entropy_advection_verified=entropy_advection_verified,
    entropy_advection_tolerance=entropy_advection_tolerance,
    maximum_entropy_advection_residual=maximum_entropy_advection_residual,
    maximum_shock_coordinate_residual_m=maximum_shock_coordinate_residual_m,
    maximum_shock_state_residual=maximum_shock_state_residual,
    maximum_shock_pressure_log_residual=maximum_shock_pressure_log_residual,
    maximum_ambient_coordinate_residual_m=maximum_ambient_coordinate_residual_m,
    maximum_ambient_pressure_log_residual=maximum_ambient_pressure_log_residual,
    maximum_interior_pressure_log_residual=maximum_interior_pressure_log_residual,
    message=message,
  )


def _triangle_entropy_advection_residual(
  points: tuple[tuple[float, float], ...],
  states: tuple[object, ...],
  pressures: tuple[float, ...],
) -> float | None:
  """Measure normalized ``u · grad(log(p0))`` on one triangle."""

  if len(points) != 3 or len(states) != 3 or len(pressures) != 3:
    return None
  ####
  if any(
    not all(isfinite(float(value)) for value in point)
    for point in points
  ) or any(
    not isfinite(float(pressure)) or float(pressure) <= 0.0
    for pressure in pressures
  ):
    return None
  ####
  determinant = (
    (points[1][0] - points[0][0]) * (points[2][1] - points[0][1])
    - (points[2][0] - points[0][0]) * (points[1][1] - points[0][1])
  )
  if not isfinite(determinant) or abs(determinant) <= 1.0e-14:
    return None
  ####
  values = tuple(log(float(pressure)) for pressure in pressures)
  gradient_x = (
    (values[1] - values[0]) * (points[2][1] - points[0][1])
    - (values[2] - values[0]) * (points[1][1] - points[0][1])
  ) / determinant
  gradient_y = (
    (points[1][0] - points[0][0]) * (values[2] - values[0])
    - (points[2][0] - points[0][0]) * (values[1] - values[0])
  ) / determinant
  ####
  velocities: list[tuple[float, float]] = []
  for state in states:
    try:
      mach = float(state.mach)
      gamma = float(state.gamma)
      theta = float(state.theta_rad)
    except (AttributeError, TypeError, ValueError):
      return None
    denominator = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
    if (
      not isfinite(mach)
      or not isfinite(gamma)
      or not isfinite(theta)
      or not isfinite(denominator)
      or denominator <= 0.0
    ):
      return None
    speed = mach / sqrt(denominator)
    velocities.append((speed * cos(theta), speed * sin(theta)))
  ####
  center_velocity = (
    sum(value[0] for value in velocities) / 3.0,
    sum(value[1] for value in velocities) / 3.0,
  )
  diameter = max(
    hypot(
      points[first][0] - points[second][0],
      points[first][1] - points[second][1],
    )
    for first in range(3)
    for second in range(first + 1, 3)
  )
  residual = (
    abs(
      center_velocity[0] * gradient_x
      + center_velocity[1] * gradient_y
    )
    * diameter
    / max(1.0e-12, hypot(*center_velocity))
  )
  if not isfinite(residual) or residual < 0.0:
    return None
  return residual
####


def _entropy_advection_residuals(
  field: object,
  *,
  position_tolerance_m: float,
) -> tuple[float, ...]:
  """Resolve normalized entropy-advection residuals over retained cells."""

  try:
    samples = field.cell_state_samples(
      position_tolerance_m=position_tolerance_m,
    )
  except (AttributeError, TypeError, ValueError):
    return ()
  ####
  residuals: list[float] = []
  for vertices, states, pressures in samples:
    if len(vertices) == 3:
      triangles = ((0, 1, 2),)
    elif len(vertices) == 4:
      triangles = ((0, 1, 2), (0, 2, 3))
    else:
      return ()
    ####
    for indices in triangles:
      triangle_residual = _triangle_entropy_advection_residual(
        tuple(vertices[index] for index in indices),
        tuple(states[index] for index in indices),
        tuple(
          float(pressures[index])
          if pressures[index] is not None
          else float('nan')
          for index in indices
        ),
      )
      if triangle_residual is None:
        return ()
      residuals.append(triangle_residual)
    ####
  ####
  return tuple(residuals)
####


def measure_moc_euler_variable_entropy_lineage(
  result: MocEulerAmbientPhysicalFieldResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  entropy_advection_tolerance: float = 1.0e-3,
) -> MocEulerVariableEntropyLineageAudit:
  """Recompute variable shock-entropy lineage without a uniform-p0 assumption."""

  if not isinstance(result, MocEulerAmbientPhysicalFieldResult):
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.INVALID_INPUT,
      'result must be a MocEulerAmbientPhysicalFieldResult',
    )
  ####
  tolerances = (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('entropy_advection_tolerance', entropy_advection_tolerance),
  )
  try:
    resolved_tolerances = tuple(float(value) for _name, value in tolerances)
  except (TypeError, ValueError):
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.INVALID_INPUT,
      'lineage tolerances must be numeric',
      result_status=result.status.value,
    )
  ####
  if any(not isfinite(value) or value <= 0.0 for value in resolved_tolerances):
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.INVALID_INPUT,
      'lineage tolerances must be finite and positive',
      result_status=result.status.value,
    )
  ####
  (
    position_bound,
    state_bound,
    pressure_bound,
    entropy_advection_bound,
  ) = resolved_tolerances
  shock = result.shock_boundary
  physical = result.field
  march = result.ambient_march
  if not result.converged or shock is None or physical is None or march is None:
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.INVALID_INPUT,
      'variable-entropy lineage requires a converged shock, ambient march, and physical field',
      result_status=result.status.value,
      chain_promotion_blocked=result.chain_promotion_blocked,
      production_claim_allowed=result.production_claim_allowed,
    )
  ####
  shock_points = tuple(shock.shock_points_m)
  shock_states = tuple(shock.downstream_states)
  shock_pressures = tuple(shock.downstream_total_pressure_Pa)
  field_points = tuple(physical.shock_boundary_points_m)
  field_states = tuple(physical.post_shock_boundary_states)
  field_pressures = tuple(physical.post_shock_boundary_total_pressure_Pa)
  sample_count = len(shock_points)
  aligned_shock = bool(
    sample_count >= 3
    and len(shock_states) == sample_count
    and len(shock_pressures) == sample_count
    and len(field_points) == sample_count
    and len(field_states) == sample_count
    and len(field_pressures) == sample_count
  )
  if not aligned_shock:
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.SHOCK_LINEAGE_FAILURE,
      'shock and physical-field post-shock samples are not aligned',
      result_status=result.status.value,
      sample_count=sample_count,
      chain_promotion_blocked=result.chain_promotion_blocked,
      production_claim_allowed=result.production_claim_allowed,
    )
  ####
  shock_coordinate_residuals = tuple(
    hypot(field_point[0] - shock_point[0], field_point[1] - shock_point[1])
    for field_point, shock_point in zip(field_points, shock_points, strict=True)
  )
  shock_state_residuals = tuple(
    max(
      abs(field_state.theta_rad - shock_state.theta_rad),
      abs(field_state.mach - shock_state.mach),
      abs(field_state.gamma - shock_state.gamma),
    )
    for field_state, shock_state in zip(field_states, shock_states, strict=True)
  )
  shock_pressure_residuals = tuple(
    _log_pressure_residual(field_pressure, shock_pressure)
    for field_pressure, shock_pressure in zip(
      field_pressures,
      shock_pressures,
      strict=True,
    )
  )
  shock_geometry_verified = bool(
    all(value <= position_bound for value in shock_coordinate_residuals)
  )
  shock_state_lineage_verified = bool(
    all(
      coordinate <= position_bound and state <= state_bound
      for coordinate, state in zip(
        shock_coordinate_residuals,
        shock_state_residuals,
        strict=True,
      )
    )
  )
  shock_pressure_lineage_verified = bool(
    all(value <= pressure_bound for value in shock_pressure_residuals)
  )
  if not shock_geometry_verified or not shock_state_lineage_verified or not shock_pressure_lineage_verified:
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.SHOCK_LINEAGE_FAILURE,
      'variable shock entropy source was not retained at every physical-field sample',
      result_status=result.status.value,
      sample_count=sample_count,
      shock_geometry_verified=shock_geometry_verified,
      shock_state_lineage_verified=shock_state_lineage_verified,
      shock_pressure_lineage_verified=shock_pressure_lineage_verified,
      chain_promotion_blocked=result.chain_promotion_blocked,
      production_claim_allowed=result.production_claim_allowed,
      maximum_shock_coordinate_residual_m=max(shock_coordinate_residuals, default=None),
      maximum_shock_state_residual=max(shock_state_residuals, default=None),
      maximum_shock_pressure_log_residual=max(shock_pressure_residuals, default=None),
    )
  ####
  march_samples = tuple(march.boundary_samples)
  ambient_points = tuple(physical.ambient_boundary.points_m)
  ambient_pressures = tuple(physical.ambient_boundary.total_pressure_Pa)
  ambient_count = len(march_samples)
  aligned_ambient = bool(
    ambient_count >= 3
    and len(ambient_points) == ambient_count
    and len(ambient_pressures) == ambient_count
  )
  if not aligned_ambient:
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.AMBIENT_LINEAGE_FAILURE,
      'ambient march and physical-field perimeter samples are not aligned',
      result_status=result.status.value,
      sample_count=sample_count,
      shock_geometry_verified=True,
      shock_state_lineage_verified=True,
      shock_pressure_lineage_verified=True,
      chain_promotion_blocked=result.chain_promotion_blocked,
      production_claim_allowed=result.production_claim_allowed,
      maximum_shock_coordinate_residual_m=max(shock_coordinate_residuals, default=None),
      maximum_shock_state_residual=max(shock_state_residuals, default=None),
      maximum_shock_pressure_log_residual=max(shock_pressure_residuals, default=None),
    )
  ####
  ambient_coordinate_residuals = tuple(
    hypot(point[0] - sample.point_m[0], point[1] - sample.point_m[1])
    for point, sample in zip(ambient_points, march_samples, strict=True)
  )
  ambient_pressure_residuals = tuple(
    _log_pressure_residual(field_pressure, sample.total_pressure_Pa)
    for field_pressure, sample in zip(
      ambient_pressures,
      march_samples,
      strict=True,
    )
  )
  ambient_geometry_verified = bool(
    all(value <= position_bound for value in ambient_coordinate_residuals)
  )
  ambient_pressure_lineage_verified = bool(
    all(value <= pressure_bound for value in ambient_pressure_residuals)
  )
  if not ambient_geometry_verified or not ambient_pressure_lineage_verified:
    return _failure(
      MocEulerVariableEntropyLineageAuditStatus.AMBIENT_LINEAGE_FAILURE,
      'variable shock entropy source was not retained on the physical ambient perimeter',
      result_status=result.status.value,
      sample_count=sample_count,
      shock_geometry_verified=True,
      shock_state_lineage_verified=True,
      shock_pressure_lineage_verified=True,
      ambient_geometry_verified=ambient_geometry_verified,
      ambient_pressure_lineage_verified=ambient_pressure_lineage_verified,
      chain_promotion_blocked=result.chain_promotion_blocked,
      production_claim_allowed=result.production_claim_allowed,
      maximum_shock_coordinate_residual_m=max(shock_coordinate_residuals, default=None),
      maximum_shock_state_residual=max(shock_state_residuals, default=None),
      maximum_shock_pressure_log_residual=max(shock_pressure_residuals, default=None),
      maximum_ambient_coordinate_residual_m=max(ambient_coordinate_residuals, default=None),
      maximum_ambient_pressure_log_residual=max(ambient_pressure_residuals, default=None),
    )
  ####
  interior_source_residuals: list[float] = []
  for node in physical.nodes:
    boundary_index = node.boundary_index
    if boundary_index < 0 or boundary_index >= len(ambient_pressures):
      return _failure(
        MocEulerVariableEntropyLineageAuditStatus.INTERIOR_LINEAGE_FAILURE,
        'physical-field characteristic node references an ambient source outside the retained perimeter',
        result_status=result.status.value,
        sample_count=sample_count,
        shock_geometry_verified=True,
        shock_state_lineage_verified=True,
        shock_pressure_lineage_verified=True,
        ambient_geometry_verified=True,
        ambient_pressure_lineage_verified=True,
        chain_promotion_blocked=result.chain_promotion_blocked,
        production_claim_allowed=result.production_claim_allowed,
        maximum_shock_coordinate_residual_m=max(shock_coordinate_residuals, default=None),
        maximum_shock_state_residual=max(shock_state_residuals, default=None),
        maximum_shock_pressure_log_residual=max(shock_pressure_residuals, default=None),
        maximum_ambient_coordinate_residual_m=max(ambient_coordinate_residuals, default=None),
        maximum_ambient_pressure_log_residual=max(ambient_pressure_residuals, default=None),
      )
    ####
    pressure = node.total_pressure_Pa
    source_pressure = ambient_pressures[boundary_index]
    if pressure is None or not isfinite(float(pressure)) or float(pressure) <= 0.0:
      return _failure(
        MocEulerVariableEntropyLineageAuditStatus.INTERIOR_LINEAGE_FAILURE,
        'physical-field characteristic node has no finite positive entropy sample',
        result_status=result.status.value,
        sample_count=sample_count,
        shock_geometry_verified=True,
        shock_state_lineage_verified=True,
        shock_pressure_lineage_verified=True,
        ambient_geometry_verified=True,
        ambient_pressure_lineage_verified=True,
        chain_promotion_blocked=result.chain_promotion_blocked,
        production_claim_allowed=result.production_claim_allowed,
        maximum_shock_coordinate_residual_m=max(shock_coordinate_residuals, default=None),
        maximum_shock_state_residual=max(shock_state_residuals, default=None),
        maximum_shock_pressure_log_residual=max(shock_pressure_residuals, default=None),
        maximum_ambient_coordinate_residual_m=max(ambient_coordinate_residuals, default=None),
        maximum_ambient_pressure_log_residual=max(ambient_pressure_residuals, default=None),
      )
    ####
    interior_source_residuals.append(
      _log_pressure_residual(float(pressure), source_pressure)
    )
  ####
  interior_source_lineage_verified = bool(
    interior_source_residuals
    and all(value <= pressure_bound for value in interior_source_residuals)
  )
  try:
    cell_samples = physical.cell_state_samples(
      position_tolerance_m=position_bound,
    )
  except (TypeError, ValueError):
    cell_samples = ()
  ####
  interior_pressure_samples_verified = bool(
    len(cell_samples) == physical.cell_count
    and all(
      pressure is not None
      and isfinite(float(pressure))
      and float(pressure) > 0.0
      for _vertices, _states, pressures in cell_samples
      for pressure in pressures
    )
  )
  entropy_advection_residuals = _entropy_advection_residuals(
    physical,
    position_tolerance_m=position_bound,
  )
  maximum_entropy_advection_residual = max(
    entropy_advection_residuals,
    default=None,
  )
  entropy_advection_verified = bool(
    entropy_advection_residuals
    and maximum_entropy_advection_residual is not None
    and maximum_entropy_advection_residual <= entropy_advection_bound
  )
  variable_entropy_lineage_verified = bool(
    shock_geometry_verified
    and shock_state_lineage_verified
    and shock_pressure_lineage_verified
    and ambient_geometry_verified
    and ambient_pressure_lineage_verified
    and interior_source_lineage_verified
    and interior_pressure_samples_verified
  )
  flags_verified = bool(
    result.chain_promotion_blocked and not result.production_claim_allowed
  )
  if not interior_source_lineage_verified or not interior_pressure_samples_verified:
    status = MocEulerVariableEntropyLineageAuditStatus.INTERIOR_LINEAGE_FAILURE
    message = 'interior characteristic entropy source lineage did not pass independent checks'
  elif not flags_verified:
    status = MocEulerVariableEntropyLineageAuditStatus.FLAG_FAILURE
    message = 'physical-field entropy lineage result weakened promotion flags'
  else:
    status = MocEulerVariableEntropyLineageAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'variable shock total-pressure/entropy lineage was independently retained '
      'at the shock, ambient perimeter, and interior characteristic sources; '
      + (
        'the normalized entropy-advection residual is within its research '
        'tolerance; '
        if entropy_advection_verified
        else 'the normalized entropy-advection residual remains a separate '
        'research gate; '
      )
      + 'canonical free-boundary and production gates remain separate'
    )
  ####
  return _failure(
    status,
    message,
    result_status=result.status.value,
    sample_count=sample_count,
    shock_geometry_verified=shock_geometry_verified,
    shock_state_lineage_verified=shock_state_lineage_verified,
    shock_pressure_lineage_verified=shock_pressure_lineage_verified,
    ambient_geometry_verified=ambient_geometry_verified,
    ambient_pressure_lineage_verified=ambient_pressure_lineage_verified,
    interior_source_lineage_verified=interior_source_lineage_verified,
    interior_pressure_samples_verified=interior_pressure_samples_verified,
    variable_entropy_lineage_verified=variable_entropy_lineage_verified,
    chain_promotion_blocked=result.chain_promotion_blocked,
    production_claim_allowed=result.production_claim_allowed,
    entropy_advection_residuals=entropy_advection_residuals,
    entropy_advection_verified=entropy_advection_verified,
    entropy_advection_tolerance=entropy_advection_bound,
    maximum_entropy_advection_residual=maximum_entropy_advection_residual,
    maximum_shock_coordinate_residual_m=max(shock_coordinate_residuals, default=None),
    maximum_shock_state_residual=max(shock_state_residuals, default=None),
    maximum_shock_pressure_log_residual=max(shock_pressure_residuals, default=None),
    maximum_ambient_coordinate_residual_m=max(ambient_coordinate_residuals, default=None),
    maximum_ambient_pressure_log_residual=max(ambient_pressure_residuals, default=None),
    maximum_interior_pressure_log_residual=max(interior_source_residuals, default=None),
  )
