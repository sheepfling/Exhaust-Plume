"""Independent normalized Euler residuals for the planar MOC research lane.

The characteristic solvers already retain the state and total-pressure data
needed to reconstruct a calorically-perfect-gas Euler state.  This module
uses that retained data to measure two different pieces of evidence:

* Rankine--Hugoniot mass, momentum, and energy flux jumps on every fitted
  shock sample; and
* a conservative flux residual around every assembled characteristic cell.

The audit is intentionally independent of the MOC solver's closure flags.  A
finite/local Euler audit does not by itself solve the global reflected
free-boundary problem, and this module never authorizes a chain or product
promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerCompanionFieldResult,
)
from exhaust_plume.models.moc.topology import validate_moc_mesh

__all__ = (
  'MOC_PHYSICAL_FIELD_EULER_AUDIT_OPERATOR_ID',
  'MocPhysicalFieldEulerAuditStatus',
  'MocPhysicalFieldEulerAudit',
  'measure_moc_physical_field_euler_audit',
  'MOC_EULER_COMPANION_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerCompanionFieldAuditStatus',
  'MocEulerCompanionFieldAudit',
  'measure_moc_euler_companion_field',
)


MOC_PHYSICAL_FIELD_EULER_AUDIT_OPERATOR_ID = (
  'op.moc.physical-field-euler-audit'
)
MOC_EULER_COMPANION_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler-companion-field-audit'
)


class MocPhysicalFieldEulerAuditStatus(str, Enum):
  """Outcome of the independent local Euler audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_local_euler_audit'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'euler_audit_field_failure'
  SHOCK_JUMP_FAILURE = 'euler_audit_shock_jump_failure'
  CELL_RESIDUAL_FAILURE = 'euler_audit_cell_residual_failure'


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerAudit:
  """Independent shock-jump and cell-flux evidence for one physical field.

  ``converged`` means that the audit reconstructed finite data for every
  retained shock sample and cell and that the shock flux-jump gate passed.
  ``cell_euler_residuals_verified`` is kept separate because a characteristic
  mesh's cell residual is a discretization diagnostic whose tolerance must be
  selected independently of the local shock jump.  Neither flag is the
  canonical reflected 2-D Euler/free-boundary gate.
  """

  status: MocPhysicalFieldEulerAuditStatus
  field_status: str | None
  shock_sample_count: int
  cell_count: int
  shock_jump_mass_residuals: tuple[float, ...]
  shock_jump_momentum_residuals: tuple[float, ...]
  shock_jump_energy_residuals: tuple[float, ...]
  cell_euler_residuals: tuple[float, ...]
  maximum_shock_jump_mass_residual: float | None
  maximum_shock_jump_momentum_residual: float | None
  maximum_shock_jump_energy_residual: float | None
  maximum_cell_euler_residual: float | None
  shock_jump_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  field_topology_verified: bool
  residual_tolerance: float
  canonical_euler_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_PHYSICAL_FIELD_EULER_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocPhysicalFieldEulerAuditStatus):
      raise TypeError(
        'status must be a MocPhysicalFieldEulerAuditStatus'
      )
    if self.field_status is not None:
      object.__setattr__(self, 'field_status', str(self.field_status))
    for name in ('shock_sample_count', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    residual_tolerance = float(self.residual_tolerance)
    if not isfinite(residual_tolerance) or residual_tolerance <= 0.0:
      raise ValueError('residual_tolerance must be finite and positive')
    object.__setattr__(self, 'residual_tolerance', residual_tolerance)
    for name in (
      'shock_jump_mass_residuals',
      'shock_jump_momentum_residuals',
      'shock_jump_energy_residuals',
      'cell_euler_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        object.__setattr__(self, name, numeric)
    for name in (
      'shock_jump_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'field_topology_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether finite local evidence and all shock jump gates passed."""

    return self.status is MocPhysicalFieldEulerAuditStatus.CONVERGED_LOCAL_AUDIT

  @property
  def local_euler_consistency_verified(self) -> bool:
    """Whether both shock jumps and the requested cell residual bound passed."""

    return bool(
      self.converged
      and self.shock_jump_verified
      and self.cell_euler_residuals_verified
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Keep local Euler evidence below the physical-closure claim ceiling."""

    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'field_status': self.field_status,
      'shock_sample_count': self.shock_sample_count,
      'cell_count': self.cell_count,
      'shock_jump_mass_residuals': list(self.shock_jump_mass_residuals),
      'shock_jump_momentum_residuals': list(
        self.shock_jump_momentum_residuals
      ),
      'shock_jump_energy_residuals': list(self.shock_jump_energy_residuals),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_shock_jump_mass_residual': (
        self.maximum_shock_jump_mass_residual
      ),
      'maximum_shock_jump_momentum_residual': (
        self.maximum_shock_jump_momentum_residual
      ),
      'maximum_shock_jump_energy_residual': (
        self.maximum_shock_jump_energy_residual
      ),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'shock_jump_verified': self.shock_jump_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'local_euler_consistency_verified': (
          self.local_euler_consistency_verified
        ),
        'field_topology_verified': self.field_topology_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'residual_tolerance': self.residual_tolerance,
      'canonical_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-local-euler-shock-and-cell audit; canonical reflected '
        'free-boundary/euler and external validation remain pending'
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class _EulerPrimitive:
  density: float
  pressure: float
  velocity_x: float
  velocity_y: float
  total_energy: float


def _primitive(
  state: Any,
  total_pressure_Pa: float,
) -> _EulerPrimitive:
  gamma = float(state.gamma)
  mach = float(state.mach)
  total_pressure = float(total_pressure_Pa)
  temperature_ratio = 1.0 / (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  )
  pressure = total_pressure * temperature_ratio ** (gamma / (gamma - 1.0))
  density = pressure / temperature_ratio
  sound_speed = sqrt(gamma * temperature_ratio)
  speed = mach * sound_speed
  velocity_x = speed * cos(float(state.theta_rad))
  velocity_y = speed * sin(float(state.theta_rad))
  total_energy = pressure / (gamma - 1.0) + 0.5 * density * speed * speed
  values = (density, pressure, velocity_x, velocity_y, total_energy)
  if not all(isfinite(value) for value in values):
    raise ValueError('reconstructed Euler primitive contains a non-finite value')
  return _EulerPrimitive(*values)


def _flux_dot_normal(
  primitive: _EulerPrimitive,
  normal_x: float,
  normal_y: float,
) -> tuple[float, float, float, float]:
  normal_speed = (
    primitive.velocity_x * normal_x
    + primitive.velocity_y * normal_y
  )
  return (
    primitive.density * normal_speed,
    primitive.density * primitive.velocity_x * normal_speed
    + primitive.pressure * normal_x,
    primitive.density * primitive.velocity_y * normal_speed
    + primitive.pressure * normal_y,
    (primitive.total_energy + primitive.pressure) * normal_speed,
  )


def _relative_residual(actual: float, scale: float) -> float:
  return abs(float(actual)) / max(1.0, abs(float(scale)))


def _shock_tangent(
  points: tuple[tuple[float, float], ...],
  index: int,
) -> tuple[float, float]:
  if index == 0:
    first, second = points[0], points[1]
  elif index == len(points) - 1:
    first, second = points[-2], points[-1]
  else:
    first, second = points[index - 1], points[index + 1]
  dx = second[0] - first[0]
  dy = second[1] - first[1]
  length = hypot(dx, dy)
  if not isfinite(length) or length <= 0.0:
    raise ValueError('shock boundary contains a zero-length tangent')
  return dx / length, dy / length


def _shock_jump_residuals(
  upstream_state: Any,
  upstream_pressure: float,
  downstream_state: Any,
  downstream_pressure: float,
  tangent: tuple[float, float],
) -> tuple[float, float, float]:
  tangent_x, tangent_y = tangent
  normal_x = -tangent_y
  normal_y = tangent_x
  upstream_flux = _flux_dot_normal(
    _primitive(upstream_state, upstream_pressure),
    normal_x,
    normal_y,
  )
  downstream_flux = _flux_dot_normal(
    _primitive(downstream_state, downstream_pressure),
    normal_x,
    normal_y,
  )
  mass_scale = max(abs(upstream_flux[0]), abs(downstream_flux[0]))
  momentum_scale = max(
    hypot(upstream_flux[1], upstream_flux[2]),
    hypot(downstream_flux[1], downstream_flux[2]),
  )
  energy_scale = max(abs(upstream_flux[3]), abs(downstream_flux[3]))
  return (
    _relative_residual(upstream_flux[0] - downstream_flux[0], mass_scale),
    _relative_residual(
      hypot(
        upstream_flux[1] - downstream_flux[1],
        upstream_flux[2] - downstream_flux[2],
      ),
      momentum_scale,
    ),
    _relative_residual(upstream_flux[3] - downstream_flux[3], energy_scale),
  )


def _cell_flux_residual(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[Any, ...],
  pressures: tuple[float, ...],
) -> float:
  if len(vertices) != len(states) or len(vertices) != len(pressures):
    raise ValueError('cell vertices and Euler samples must have equal lengths')
  if len(vertices) < 3:
    raise ValueError('Euler cell residual requires at least three vertices')
  signed_area = 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(vertices, (*vertices[1:], vertices[0]))
  )
  if not isfinite(signed_area) or abs(signed_area) <= 1.0e-24:
    raise ValueError('Euler cell residual requires a non-degenerate polygon')
  orientation = 1.0 if signed_area > 0.0 else -1.0
  primitives = tuple(
    _primitive(state, pressure)
    for state, pressure in zip(states, pressures, strict=True)
  )
  residual = [0.0, 0.0, 0.0, 0.0]
  scale = 0.0
  for index, (first, second) in enumerate(
    zip(vertices, (*vertices[1:], vertices[0]))
  ):
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    length = hypot(dx, dy)
    if not isfinite(length) or length <= 0.0:
      raise ValueError(f'Euler cell edge {index} has zero length')
    normal_x = orientation * dy / length
    normal_y = -orientation * dx / length
    first_flux = _flux_dot_normal(
      primitives[index],
      normal_x,
      normal_y,
    )
    second_flux = _flux_dot_normal(
      primitives[(index + 1) % len(primitives)],
      normal_x,
      normal_y,
    )
    for component in range(4):
      residual[component] += 0.5 * length * (
        first_flux[component] + second_flux[component]
      )
    scale += length * max(
      1.0,
      max(abs(value) for value in first_flux),
      max(abs(value) for value in second_flux),
    )
  return _relative_residual(
    sqrt(sum(value * value for value in residual)),
    scale,
  )


def _failure(
  status: MocPhysicalFieldEulerAuditStatus,
  message: str,
  *,
  field_status: str | None = None,
  shock_sample_count: int = 0,
  cell_count: int = 0,
  shock_jump_mass_residuals: tuple[float, ...] = (),
  shock_jump_momentum_residuals: tuple[float, ...] = (),
  shock_jump_energy_residuals: tuple[float, ...] = (),
  cell_euler_residuals: tuple[float, ...] = (),
  shock_jump_verified: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  field_topology_verified: bool = False,
  residual_tolerance: float = 1.0e-8,
) -> MocPhysicalFieldEulerAudit:
  maxima = tuple(
    max(values) if values else None
    for values in (
      shock_jump_mass_residuals,
      shock_jump_momentum_residuals,
      shock_jump_energy_residuals,
      cell_euler_residuals,
    )
  )
  return MocPhysicalFieldEulerAudit(
    status=status,
    field_status=field_status,
    shock_sample_count=shock_sample_count,
    cell_count=cell_count,
    shock_jump_mass_residuals=shock_jump_mass_residuals,
    shock_jump_momentum_residuals=shock_jump_momentum_residuals,
    shock_jump_energy_residuals=shock_jump_energy_residuals,
    cell_euler_residuals=cell_euler_residuals,
    maximum_shock_jump_mass_residual=maxima[0],
    maximum_shock_jump_momentum_residual=maxima[1],
    maximum_shock_jump_energy_residual=maxima[2],
    maximum_cell_euler_residual=maxima[3],
    shock_jump_verified=shock_jump_verified,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    field_topology_verified=field_topology_verified,
    residual_tolerance=residual_tolerance,
    message=message,
  )


class MocEulerCompanionFieldAuditStatus(str, Enum):
  """Outcome of independently auditing an open companion strip."""

  CONVERGED_LOCAL_AUDIT = 'converged_companion_field_audit'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'companion_field_audit_field_failure'
  SHOCK_JUMP_FAILURE = 'companion_field_audit_shock_jump_failure'
  BOUNDARY_FAILURE = 'companion_field_audit_boundary_failure'
  TOPOLOGY_FAILURE = 'companion_field_audit_topology_failure'
  CELL_RESIDUAL_FAILURE = 'companion_field_audit_cell_residual_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldAudit:
  """Independent evidence for the open Euler shock/companion strip."""

  status: MocEulerCompanionFieldAuditStatus
  field_status: str | None
  shock_sample_count: int
  cell_count: int
  shock_jump_mass_residuals: tuple[float, ...]
  shock_jump_momentum_residuals: tuple[float, ...]
  shock_jump_energy_residuals: tuple[float, ...]
  cell_euler_residuals: tuple[float, ...]
  maximum_shock_jump_mass_residual: float | None
  maximum_shock_jump_momentum_residual: float | None
  maximum_shock_jump_energy_residual: float | None
  maximum_cell_euler_residual: float | None
  shock_jump_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  field_topology_verified: bool
  boundary_geometry_verified: bool
  pressure_lineage_verified: bool
  promotion_flags_verified: bool
  shock_residual_tolerance: float
  cell_residual_tolerance: float
  canonical_euler_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_COMPANION_FIELD_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerCompanionFieldAuditStatus):
      raise TypeError('status must be a MocEulerCompanionFieldAuditStatus')
    for name in ('shock_sample_count', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in ('shock_residual_tolerance', 'cell_residual_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    for name in (
      'shock_jump_mass_residuals',
      'shock_jump_momentum_residuals',
      'shock_jump_energy_residuals',
      'cell_euler_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    for name in (
      'shock_jump_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'field_topology_verified',
      'boundary_geometry_verified',
      'pressure_lineage_verified',
      'promotion_flags_verified',
      'canonical_euler_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.field_status is not None:
      object.__setattr__(self, 'field_status', str(self.field_status))
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is MocEulerCompanionFieldAuditStatus.CONVERGED_LOCAL_AUDIT

  @property
  def local_euler_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock_jump_verified
      and self.cell_euler_residuals_verified
      and self.field_topology_verified
      and self.boundary_geometry_verified
      and self.pressure_lineage_verified
      and self.promotion_flags_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'field_status': self.field_status,
      'shock_sample_count': self.shock_sample_count,
      'cell_count': self.cell_count,
      'shock_jump_mass_residuals': list(self.shock_jump_mass_residuals),
      'shock_jump_momentum_residuals': list(self.shock_jump_momentum_residuals),
      'shock_jump_energy_residuals': list(self.shock_jump_energy_residuals),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_shock_jump_mass_residual': self.maximum_shock_jump_mass_residual,
      'maximum_shock_jump_momentum_residual': self.maximum_shock_jump_momentum_residual,
      'maximum_shock_jump_energy_residual': self.maximum_shock_jump_energy_residual,
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'shock_jump_verified': self.shock_jump_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'field_topology_verified': self.field_topology_verified,
        'boundary_geometry_verified': self.boundary_geometry_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'promotion_flags_verified': self.promotion_flags_verified,
        'local_euler_consistency_verified': self.local_euler_consistency_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'shock_residual_tolerance': self.shock_residual_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'canonical_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-open-companion-strip audit; ambient/reflected free-boundary '
        'closure and external validation remain pending'
      ),
      'message': self.message,
    }


def _companion_audit_failure(
  status: MocEulerCompanionFieldAuditStatus,
  message: str,
  *,
  field_status: str | None = None,
  shock_sample_count: int = 0,
  cell_count: int = 0,
  shock_jump_mass_residuals: tuple[float, ...] = (),
  shock_jump_momentum_residuals: tuple[float, ...] = (),
  shock_jump_energy_residuals: tuple[float, ...] = (),
  cell_euler_residuals: tuple[float, ...] = (),
  shock_jump_verified: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  field_topology_verified: bool = False,
  boundary_geometry_verified: bool = False,
  pressure_lineage_verified: bool = False,
  promotion_flags_verified: bool = False,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerCompanionFieldAudit:
  maxima = tuple(
    max(values) if values else None
    for values in (
      shock_jump_mass_residuals,
      shock_jump_momentum_residuals,
      shock_jump_energy_residuals,
      cell_euler_residuals,
    )
  )
  return MocEulerCompanionFieldAudit(
    status=status,
    field_status=field_status,
    shock_sample_count=shock_sample_count,
    cell_count=cell_count,
    shock_jump_mass_residuals=shock_jump_mass_residuals,
    shock_jump_momentum_residuals=shock_jump_momentum_residuals,
    shock_jump_energy_residuals=shock_jump_energy_residuals,
    cell_euler_residuals=cell_euler_residuals,
    maximum_shock_jump_mass_residual=maxima[0],
    maximum_shock_jump_momentum_residual=maxima[1],
    maximum_shock_jump_energy_residual=maxima[2],
    maximum_cell_euler_residual=maxima[3],
    shock_jump_verified=shock_jump_verified,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    field_topology_verified=field_topology_verified,
    boundary_geometry_verified=boundary_geometry_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    promotion_flags_verified=promotion_flags_verified,
    shock_residual_tolerance=shock_residual_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )


def measure_moc_euler_companion_field(
  field: MocEulerCompanionFieldResult,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
) -> MocEulerCompanionFieldAudit:
  """Rebuild local shock, strip, topology, and pressure evidence independently."""

  if not isinstance(field, MocEulerCompanionFieldResult):
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.INVALID_INPUT,
      'field must be a MocEulerCompanionFieldResult',
    )
  try:
    shock_tolerance = float(shock_residual_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.INVALID_INPUT,
      'companion-field audit tolerances must be numeric',
      field_status=field.status.value,
    )
  tolerances = (
    shock_tolerance,
    cell_tolerance,
    position_tolerance,
    invariant_tolerance_value,
    pressure_tolerance_value,
  )
  if any(not isfinite(value) or value <= 0.0 for value in tolerances):
    raise ValueError('companion-field audit tolerances must be finite and positive')
  if not field.converged:
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.FIELD_FAILURE,
      'companion-field audit requires a converged open strip',
      field_status=field.status.value,
      shock_sample_count=len(field.shock_boundary_points_m),
      cell_count=len(field.cells),
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  curve = field.shock_boundary
  if curve is None or not curve.converged:
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.SHOCK_JUMP_FAILURE,
      'companion-field audit requires the retained converged shock curve',
      field_status=field.status.value,
      shock_sample_count=len(field.shock_boundary_points_m),
      cell_count=len(field.cells),
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  shock_points = tuple(field.shock_boundary_points_m)
  boundary_geometry_verified = bool(
    len(shock_points) >= 2
    and len(shock_points) == len(field.shock_boundary_states)
    and len(shock_points) == len(field.shock_boundary_total_pressure_Pa)
    and len(shock_points) == len(field.companion_boundary_points_m)
    and len(shock_points) == len(field.companion_boundary_states)
    and len(shock_points) == len(field.companion_boundary_total_pressure_Pa)
    and len(shock_points) == len(field.interior_points_m)
    and len(shock_points) == len(field.nodes)
    and all(
      len(point) == 2 and all(isfinite(float(value)) for value in point)
      for point in shock_points
    )
  )
  if not boundary_geometry_verified:
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.BOUNDARY_FAILURE,
      'companion-field boundary evidence has inconsistent sample counts or geometry',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  boundary_geometry_verified = boundary_geometry_verified and all(
    abs(state.x_m - point[0]) <= position_tolerance
    and abs(state.y_m - point[1]) <= position_tolerance
    for state, point in zip(field.shock_boundary_states, shock_points, strict=True)
  ) and all(
    abs(state.x_m - point[0]) <= position_tolerance
    and abs(state.y_m - point[1]) <= position_tolerance
    for state, point in zip(
      field.companion_boundary_states,
      field.companion_boundary_points_m,
      strict=True,
    )
  )
  curve_geometry_matches = (
    curve.shock_points_m == shock_points
    and curve.downstream_states == field.shock_boundary_states
    and curve.downstream_total_pressure_Pa
    == field.shock_boundary_total_pressure_Pa
  )
  boundary_geometry_verified = boundary_geometry_verified and curve_geometry_matches
  pressure_lineage_verified = bool(
    len(field.shock_boundary_total_pressure_Pa) == len(shock_points)
    and len(field.companion_boundary_total_pressure_Pa) == len(shock_points)
    and all(
      abs(companion - shock) <= pressure_tolerance_value * max(1.0, abs(shock))
      for companion, shock in zip(
        field.companion_boundary_total_pressure_Pa,
        field.shock_boundary_total_pressure_Pa,
        strict=True,
      )
    )
    and all(
      abs(interior - shock) <= pressure_tolerance_value * max(1.0, abs(shock))
      for interior, shock in zip(
        field.interior_total_pressure_Pa,
        field.shock_boundary_total_pressure_Pa,
        strict=True,
      )
    )
  )
  jump_mass: list[float] = []
  jump_momentum: list[float] = []
  jump_energy: list[float] = []
  try:
    if not (
      len(curve.upstream_states)
      == len(curve.upstream_total_pressure_Pa)
      == len(curve.downstream_states)
      == len(curve.downstream_total_pressure_Pa)
      == len(shock_points)
    ):
      raise ValueError('retained shock curve evidence sequences have unequal lengths')
    for index in range(len(shock_points)):
      mass, momentum, energy = _shock_jump_residuals(
        curve.upstream_states[index],
        curve.upstream_total_pressure_Pa[index],
        curve.downstream_states[index],
        curve.downstream_total_pressure_Pa[index],
        _shock_tangent(shock_points, index),
      )
      jump_mass.append(mass)
      jump_momentum.append(momentum)
      jump_energy.append(energy)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.SHOCK_JUMP_FAILURE,
      f'companion shock Euler flux reconstruction failed: {error}',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
      boundary_geometry_verified=boundary_geometry_verified,
      pressure_lineage_verified=pressure_lineage_verified,
    )
  maximum_shock_residual = max(
    (*jump_mass, *jump_momentum, *jump_energy),
    default=float('inf'),
  )
  shock_verified = maximum_shock_residual <= shock_tolerance
  cells: list[float] = []
  cell_geometry_verified = len(field.cells) == len(shock_points) - 1
  try:
    for index, cell in enumerate(field.cells):
      expected_vertices = (
        shock_points[index],
        shock_points[index + 1],
        field.interior_points_m[index + 1],
        field.interior_points_m[index],
      )
      vertices = tuple(
        (float(point[0]), float(point[1]))
        for point in cell.vertices_xr_m
      )
      if len(vertices) != len(expected_vertices) or any(
        abs(actual[axis] - expected[axis]) > position_tolerance
        for actual, expected in zip(vertices, expected_vertices, strict=True)
        for axis in (0, 1)
      ):
        cell_geometry_verified = False
      states = (
        field.shock_boundary_states[index],
        field.shock_boundary_states[index + 1],
        field.interior_states[index + 1],
        field.interior_states[index],
      )
      pressures = (
        field.shock_boundary_total_pressure_Pa[index],
        field.shock_boundary_total_pressure_Pa[index + 1],
        field.interior_total_pressure_Pa[index + 1],
        field.interior_total_pressure_Pa[index],
      )
      cells.append(_cell_flux_residual(vertices, states, pressures))
  except (ArithmeticError, FloatingPointError, IndexError, TypeError, ValueError) as error:
    return _companion_audit_failure(
      MocEulerCompanionFieldAuditStatus.CELL_RESIDUAL_FAILURE,
      f'companion cell Euler flux reconstruction failed: {error}',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      shock_jump_mass_residuals=tuple(jump_mass),
      shock_jump_momentum_residuals=tuple(jump_momentum),
      shock_jump_energy_residuals=tuple(jump_energy),
      shock_jump_verified=shock_verified,
      boundary_geometry_verified=boundary_geometry_verified and cell_geometry_verified,
      pressure_lineage_verified=pressure_lineage_verified,
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  cells_finite = all(isfinite(value) for value in cells)
  maximum_cell_residual = max(cells, default=0.0)
  cells_verified = cells_finite and maximum_cell_residual <= cell_tolerance
  independent_topology = validate_moc_mesh(field.cells)
  field_topology_verified = bool(
    independent_topology.status is field.topology.status
    and independent_topology.cell_count == field.topology.cell_count
    and independent_topology.edge_count == field.topology.edge_count
    and independent_topology.boundary_edge_count == field.topology.boundary_edge_count
    and independent_topology.boundary_component_count == field.topology.boundary_component_count
    and independent_topology.boundary_is_closed_cycle == field.topology.boundary_is_closed_cycle
    and independent_topology.nonmanifold_edge_count == field.topology.nonmanifold_edge_count
    and independent_topology.connected == field.topology.connected
    and independent_topology.forms_closed_zone
  )
  node_compatibility_verified = bool(
    all(
      result.converged
      and result.state is not None
      and result.point_m is not None
      and abs(result.state.x_m - point[0]) <= position_tolerance
      and abs(result.state.y_m - point[1]) <= position_tolerance
      and max(
        abs(result.invariant_residual_plus or 0.0),
        abs(result.invariant_residual_minus or 0.0),
      ) <= invariant_tolerance_value
      for result, point in zip(field.point_results, field.interior_points_m, strict=True)
    )
    and len(field.point_results) == len(field.nodes)
  )
  boundary_geometry_verified = boundary_geometry_verified and cell_geometry_verified and node_compatibility_verified
  promotion_flags_verified = bool(
    field.shock_boundary_local_euler_verified
    and field.physical_closure_verified is False
    and field.chain_promotion_blocked
    and field.production_claim_allowed is False
  )
  if not shock_verified:
    status = MocEulerCompanionFieldAuditStatus.SHOCK_JUMP_FAILURE
    message = 'companion shock Rankine--Hugoniot residual exceeded tolerance'
  elif not boundary_geometry_verified:
    status = MocEulerCompanionFieldAuditStatus.BOUNDARY_FAILURE
    message = 'companion strip boundary or compatibility evidence failed independent checks'
  elif not pressure_lineage_verified:
    status = MocEulerCompanionFieldAuditStatus.BOUNDARY_FAILURE
    message = 'companion strip pressure lineage failed independent checks'
  elif not field_topology_verified:
    status = MocEulerCompanionFieldAuditStatus.TOPOLOGY_FAILURE
    message = 'companion strip topology failed independent checks'
  elif not cells_verified:
    status = MocEulerCompanionFieldAuditStatus.CELL_RESIDUAL_FAILURE
    message = 'companion strip conservative cell residual exceeded tolerance'
  elif not promotion_flags_verified:
    status = MocEulerCompanionFieldAuditStatus.FIELD_FAILURE
    message = 'companion strip promotion flags do not preserve the fidelity boundary'
  else:
    status = MocEulerCompanionFieldAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent companion-strip audit verified local shock jumps, finite '
      'cell residuals, topology, compatibility, and pressure lineage; '
      'physical closure remains pending'
    )
  return MocEulerCompanionFieldAudit(
    status=status,
    field_status=field.status.value,
    shock_sample_count=len(shock_points),
    cell_count=len(field.cells),
    shock_jump_mass_residuals=tuple(jump_mass),
    shock_jump_momentum_residuals=tuple(jump_momentum),
    shock_jump_energy_residuals=tuple(jump_energy),
    cell_euler_residuals=tuple(cells),
    maximum_shock_jump_mass_residual=max(jump_mass, default=None),
    maximum_shock_jump_momentum_residual=max(jump_momentum, default=None),
    maximum_shock_jump_energy_residual=max(jump_energy, default=None),
    maximum_cell_euler_residual=maximum_cell_residual,
    shock_jump_verified=shock_verified,
    cell_euler_residuals_finite=cells_finite,
    cell_euler_residuals_verified=cells_verified,
    field_topology_verified=field_topology_verified,
    boundary_geometry_verified=boundary_geometry_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    promotion_flags_verified=promotion_flags_verified,
    shock_residual_tolerance=shock_tolerance,
    cell_residual_tolerance=cell_tolerance,
    message=message,
  )


def measure_moc_physical_field_euler_audit(
  field: MocPhysicalPostShockFieldResult,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
) -> MocPhysicalFieldEulerAudit:
  """Reconstruct normalized Euler fluxes from a retained physical field.

  The normalized reconstruction uses ``R*T0 = 1``.  Since the field carries
  Mach number, flow angle, gamma, and total pressure but not a dimensional
  total temperature, this removes an arbitrary scale while preserving all
  local Rankine--Hugoniot ratios and conservative flux residuals.  The
  caller-selected ``cell_residual_tolerance`` is a diagnostic threshold, not
  a canonical product gate.
  """

  if not isinstance(field, MocPhysicalPostShockFieldResult):
    return _failure(
      MocPhysicalFieldEulerAuditStatus.INVALID_INPUT,
      'field must be a MocPhysicalPostShockFieldResult',
    )
  try:
    shock_tolerance = float(shock_residual_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    position_tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    return _failure(
      MocPhysicalFieldEulerAuditStatus.INVALID_INPUT,
      'Euler audit tolerances must be numeric',
      field_status=field.status.value,
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (shock_tolerance, cell_tolerance, position_tolerance)
  ):
    raise ValueError('Euler audit tolerances must be finite and positive')
  if not field.converged or not field.physical_closure_verified:
    return _failure(
      MocPhysicalFieldEulerAuditStatus.FIELD_FAILURE,
      'Euler audit requires a converged physically closed field',
      field_status=field.status.value,
      shock_sample_count=len(field.shock_boundary_points_m),
      cell_count=len(field.cells),
      residual_tolerance=cell_tolerance,
    )
  if not field.state_sampling_available:
    return _failure(
      MocPhysicalFieldEulerAuditStatus.FIELD_FAILURE,
      'Euler audit requires complete bounded field state sampling',
      field_status=field.status.value,
      shock_sample_count=len(field.shock_boundary_points_m),
      cell_count=len(field.cells),
      field_topology_verified=bool(
        field.topology.connected
        and field.topology.forms_closed_zone
        and field.topology.nonmanifold_edge_count == 0
      ),
      residual_tolerance=cell_tolerance,
    )
  shock_points = tuple(field.shock_boundary_points_m)
  upstream_states = tuple(field.upstream_shock_boundary_states)
  upstream_pressures = tuple(field.upstream_shock_boundary_total_pressure_Pa)
  downstream_states = tuple(field.post_shock_boundary_states)
  downstream_pressures = tuple(field.post_shock_boundary_total_pressure_Pa)
  if len(shock_points) < 3 or not (
    len(shock_points)
    == len(upstream_states)
    == len(upstream_pressures)
    == len(downstream_states)
    == len(downstream_pressures)
  ):
    return _failure(
      MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE,
      'field does not retain complete upstream and downstream shock samples',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      residual_tolerance=cell_tolerance,
    )
  if any(
    len(point) != 2
    or not all(isfinite(float(value)) for value in point)
    for point in shock_points
  ):
    return _failure(
      MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE,
      'shock samples contain non-finite geometry',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      residual_tolerance=cell_tolerance,
    )
  jump_mass: list[float] = []
  jump_momentum: list[float] = []
  jump_energy: list[float] = []
  try:
    for index in range(len(shock_points)):
      mass, momentum, energy = _shock_jump_residuals(
        upstream_states[index],
        upstream_pressures[index],
        downstream_states[index],
        downstream_pressures[index],
        _shock_tangent(shock_points, index),
      )
      jump_mass.append(mass)
      jump_momentum.append(momentum)
      jump_energy.append(energy)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE,
      f'shock Euler flux reconstruction failed: {error}',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      residual_tolerance=cell_tolerance,
    )
  maximum_shock_residual = max(
    (*jump_mass, *jump_momentum, *jump_energy),
    default=float('inf'),
  )
  shock_verified = maximum_shock_residual <= shock_tolerance
  try:
    cell_samples = field.cell_state_samples(
      position_tolerance_m=position_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerAuditStatus.FIELD_FAILURE,
      f'cell Euler samples could not be reconstructed: {error}',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      shock_jump_mass_residuals=tuple(jump_mass),
      shock_jump_momentum_residuals=tuple(jump_momentum),
      shock_jump_energy_residuals=tuple(jump_energy),
      shock_jump_verified=shock_verified,
      residual_tolerance=cell_tolerance,
    )
  if len(cell_samples) != len(field.cells):
    return _failure(
      MocPhysicalFieldEulerAuditStatus.FIELD_FAILURE,
      'bounded cell sampling did not return one Euler sample set per cell',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      shock_jump_mass_residuals=tuple(jump_mass),
      shock_jump_momentum_residuals=tuple(jump_momentum),
      shock_jump_energy_residuals=tuple(jump_energy),
      shock_jump_verified=shock_verified,
      residual_tolerance=cell_tolerance,
    )
  cell_residuals: list[float] = []
  try:
    for (vertices, states, pressures) in cell_samples:
      if any(value is None for value in pressures):
        raise ValueError(
          'bounded cell sampling returned a missing total pressure'
        )
      cell_residuals.append(
        _cell_flux_residual(
          tuple((float(point[0]), float(point[1])) for point in vertices),
          tuple(states),
          tuple(float(value) for value in pressures),
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      (
        MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE
        if not shock_verified
        else MocPhysicalFieldEulerAuditStatus.CELL_RESIDUAL_FAILURE
      ),
      f'cell Euler flux reconstruction failed: {error}',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      shock_jump_mass_residuals=tuple(jump_mass),
      shock_jump_momentum_residuals=tuple(jump_momentum),
      shock_jump_energy_residuals=tuple(jump_energy),
      shock_jump_verified=shock_verified,
      residual_tolerance=cell_tolerance,
    )
  maximum_cell_residual = max(cell_residuals, default=0.0)
  cells_finite = all(isfinite(value) for value in cell_residuals)
  cells_verified = cells_finite and maximum_cell_residual <= cell_tolerance
  topology_verified = bool(
    field.topology.connected
    and field.topology.forms_closed_zone
    and field.topology.nonmanifold_edge_count == 0
  )
  if not shock_verified:
    status = MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE
    message = (
      'local shock Rankine--Hugoniot Euler flux jump exceeded tolerance; '
      'cell residuals were retained as diagnostic evidence'
    )
  elif not cells_verified:
    status = MocPhysicalFieldEulerAuditStatus.CELL_RESIDUAL_FAILURE
    message = 'local conservative cell Euler residual exceeded tolerance'
  else:
    status = MocPhysicalFieldEulerAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent normalized Euler audit reconstructed shock mass/momentum/'
      'energy jumps and finite conservative cell residuals; canonical reflected '
      'free-boundary/Euler closure remains pending'
    )
  return MocPhysicalFieldEulerAudit(
    status=status,
    field_status=field.status.value,
    shock_sample_count=len(shock_points),
    cell_count=len(field.cells),
    shock_jump_mass_residuals=tuple(jump_mass),
    shock_jump_momentum_residuals=tuple(jump_momentum),
    shock_jump_energy_residuals=tuple(jump_energy),
    cell_euler_residuals=tuple(cell_residuals),
    maximum_shock_jump_mass_residual=max(jump_mass),
    maximum_shock_jump_momentum_residual=max(jump_momentum),
    maximum_shock_jump_energy_residual=max(jump_energy),
    maximum_cell_euler_residual=maximum_cell_residual,
    shock_jump_verified=shock_verified,
    cell_euler_residuals_finite=cells_finite,
    cell_euler_residuals_verified=cells_verified,
    field_topology_verified=topology_verified,
    residual_tolerance=cell_tolerance,
    message=message,
  )
