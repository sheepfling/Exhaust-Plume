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

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from math import atan2, cos, hypot, isfinite, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerAmbientCompanionBoundaryResult,
  MocEulerCompanionFieldResult,
)
from exhaust_plume.models.moc.euler_ambient_field import (
  MocEulerAmbientBoundaryMarchResult,
  MocEulerAmbientShockFieldResult,
)
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)
from exhaust_plume.models.moc.euler_post_shock import (
  MocEulerPostShockFieldResult,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryOrientation,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import validate_moc_mesh

__all__ = (
  'MOC_PHYSICAL_FIELD_EULER_AUDIT_OPERATOR_ID',
  'MocPhysicalFieldEulerAuditStatus',
  'MocPhysicalFieldEulerAudit',
  'measure_moc_physical_field_euler_audit',
  'MOC_EULER_AMBIENT_PHYSICAL_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerAmbientPhysicalFieldAuditStatus',
  'MocEulerAmbientPhysicalFieldAudit',
  'measure_moc_euler_ambient_physical_field',
  'MOC_EULER_COMPANION_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerCompanionFieldAuditStatus',
  'MocEulerCompanionFieldAudit',
  'measure_moc_euler_companion_field',
  'MOC_EULER_AMBIENT_COMPANION_BOUNDARY_AUDIT_OPERATOR_ID',
  'MocEulerAmbientCompanionBoundaryAuditStatus',
  'MocEulerAmbientCompanionBoundaryAudit',
  'measure_moc_ambient_companion_boundary',
  'MOC_EULER_COMPANION_FIELD_CHAIN_AUDIT_OPERATOR_ID',
  'MocEulerCompanionFieldChainAuditStatus',
  'MocEulerCompanionFieldChainAudit',
  'measure_moc_euler_companion_field_chain',
  'MOC_EULER_COMPANION_FIELD_CHAIN_REFINEMENT_OPERATOR_ID',
  'MocEulerCompanionFieldChainRefinementCase',
  'MocEulerCompanionFieldChainRefinementMeasurementStatus',
  'MocEulerCompanionFieldChainRefinementMeasurement',
  'measure_moc_euler_companion_field_chain_refinement',
  'MOC_EULER_AMBIENT_SHOCK_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerAmbientShockFieldAuditStatus',
  'MocEulerAmbientShockFieldAudit',
  'measure_moc_euler_ambient_shock_field',
  'MOC_EULER_AMBIENT_SHOCK_FIELD_CHAIN_AUDIT_OPERATOR_ID',
  'MocEulerAmbientShockFieldChainAuditStatus',
  'MocEulerAmbientShockFieldChainAudit',
  'measure_moc_euler_ambient_shock_field_chain',
  'MOC_EULER_POST_SHOCK_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerPostShockFieldAuditStatus',
  'MocEulerPostShockFieldAudit',
  'measure_moc_euler_post_shock_field',
  'MOC_EULER_POST_SHOCK_FIELD_CHAIN_AUDIT_OPERATOR_ID',
  'MocEulerPostShockFieldChainAuditStatus',
  'MocEulerPostShockFieldChainAudit',
  'measure_moc_euler_post_shock_field_chain',
)


MOC_PHYSICAL_FIELD_EULER_AUDIT_OPERATOR_ID = (
  'op.moc.physical-field-euler-audit'
)
MOC_EULER_COMPANION_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler-companion-field-audit'
)
MOC_EULER_AMBIENT_COMPANION_BOUNDARY_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-companion-boundary-audit'
)
MOC_EULER_AMBIENT_SHOCK_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-shock-field-audit'
)
MOC_EULER_AMBIENT_SHOCK_FIELD_CHAIN_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-shock-field-chain-audit'
)
MOC_EULER_AMBIENT_PHYSICAL_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-physical-field-audit'
)


class MocPhysicalFieldEulerAuditStatus(str, Enum):
  """Outcome of the independent local Euler audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_local_euler_audit'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'euler_audit_field_failure'
  SHOCK_JUMP_FAILURE = 'euler_audit_shock_jump_failure'
  CELL_RESIDUAL_FAILURE = 'euler_audit_cell_residual_failure'
####


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
    ####
    if self.field_status is not None:
      object.__setattr__(self, 'field_status', str(self.field_status))
    ####
    for name in ('shock_sample_count', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    residual_tolerance = float(self.residual_tolerance)
    if not isfinite(residual_tolerance) or residual_tolerance <= 0.0:
      raise ValueError('residual_tolerance must be finite and positive')
    ####
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
      ####
      object.__setattr__(self, name, values)
    ####
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
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
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
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether finite local evidence and all shock jump gates passed."""

    return self.status is MocPhysicalFieldEulerAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_euler_consistency_verified(self) -> bool:
    """Whether both shock jumps and the requested cell residual bound passed."""

    return bool(
      self.converged
      and self.shock_jump_verified
      and self.cell_euler_residuals_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Keep local Euler evidence below the physical-closure claim ceiling."""

    return False
  ####

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
  ####
####


@dataclass(frozen=True, slots=True)
class _EulerPrimitive:
  density: float
  pressure: float
  velocity_x: float
  velocity_y: float
  total_energy: float
####


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
  ####
  return _EulerPrimitive(*values)
####


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
####


def _relative_residual(actual: float, scale: float) -> float:
  return abs(float(actual)) / max(1.0, abs(float(scale)))
####


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
  ####
  dx = second[0] - first[0]
  dy = second[1] - first[1]
  length = hypot(dx, dy)
  if not isfinite(length) or length <= 0.0:
    raise ValueError('shock boundary contains a zero-length tangent')
  ####
  return dx / length, dy / length
####


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
####


def _cell_flux_residual(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[Any, ...],
  pressures: tuple[float, ...],
) -> float:
  if len(vertices) != len(states) or len(vertices) != len(pressures):
    raise ValueError('cell vertices and Euler samples must have equal lengths')
  ####
  if len(vertices) < 3:
    raise ValueError('Euler cell residual requires at least three vertices')
  ####
  signed_area = 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(vertices, (*vertices[1:], vertices[0]))
  )
  if not isfinite(signed_area) or abs(signed_area) <= 1.0e-24:
    raise ValueError('Euler cell residual requires a non-degenerate polygon')
  ####
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
    ####
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
    ####
    scale += length * max(
      1.0,
      max(abs(value) for value in first_flux),
      max(abs(value) for value in second_flux),
    )
  ####
  return _relative_residual(
    sqrt(sum(value * value for value in residual)),
    scale,
  )
####


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
####


class MocEulerAmbientCompanionBoundaryAuditStatus(str, Enum):
  """Outcome of independently auditing an ambient companion trace."""

  CONVERGED_LOCAL_AUDIT = 'converged_ambient_companion_boundary_audit'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FAILURE = 'ambient_companion_boundary_audit_boundary_failure'
  PRESSURE_FAILURE = 'ambient_companion_boundary_audit_pressure_failure'
  INVARIANT_FAILURE = 'ambient_companion_boundary_audit_invariant_failure'
  GEOMETRY_FAILURE = 'ambient_companion_boundary_audit_geometry_failure'
  FLAG_FAILURE = 'ambient_companion_boundary_audit_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientCompanionBoundaryAudit:
  """Independent evidence for the solver-owned ambient companion trace.

  This audit rebuilds pressure, invariant, and streamline-like geometry from
  the returned samples.  It intentionally does not call the boundary solver
  again, and a passing result still describes an open research boundary
  rather than a globally coupled reflected free-boundary solution.
  """

  status: MocEulerAmbientCompanionBoundaryAuditStatus
  boundary_status: str | None
  sample_count: int
  static_pressure_residuals: tuple[float, ...]
  companion_invariant_residuals: tuple[float, ...]
  geometry_residuals_m: tuple[float, ...]
  maximum_static_pressure_residual: float | None
  maximum_companion_invariant_residual: float | None
  maximum_geometry_residual_m: float | None
  minimum_shock_clearance_m: float | None
  sampling_verified: bool
  pressure_verified: bool
  invariant_verified: bool
  geometry_verified: bool
  fidelity_flags_verified: bool
  ambient_pressure_Pa: float | None = None
  separation_m: float | None = None
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_COMPANION_BOUNDARY_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientCompanionBoundaryAuditStatus):
      raise TypeError(
        'status must be a MocEulerAmbientCompanionBoundaryAuditStatus'
      )
    ####
    if self.boundary_status is not None:
      object.__setattr__(self, 'boundary_status', str(self.boundary_status))
    ####
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 0
    ):
      raise ValueError('sample_count must be a nonnegative integer')
    ####
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.ambient_pressure_Pa is not None:
      pressure = float(self.ambient_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', pressure)
    ####
    if self.separation_m is not None:
      separation = float(self.separation_m)
      if not isfinite(separation):
        raise ValueError('separation_m must be finite when supplied')
      ####
      object.__setattr__(self, 'separation_m', separation)
    ####
    for name in (
      'static_pressure_residuals',
      'companion_invariant_residuals',
      'geometry_residuals_m',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != self.sample_count:
        raise ValueError(f'{name} must match sample_count')
      ####
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'maximum_static_pressure_residual',
      'maximum_companion_invariant_residual',
      'maximum_geometry_residual_m',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.minimum_shock_clearance_m is not None:
      clearance = float(self.minimum_shock_clearance_m)
      if not isfinite(clearance):
        raise ValueError('minimum_shock_clearance_m must be finite when supplied')
      ####
      object.__setattr__(self, 'minimum_shock_clearance_m', clearance)
    ####
    for name in (
      'sampling_verified',
      'pressure_verified',
      'invariant_verified',
      'geometry_verified',
      'fidelity_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerAmbientCompanionBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_boundary_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.sampling_verified
      and self.pressure_verified
      and self.invariant_verified
      and self.geometry_verified
      and self.fidelity_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'boundary_status': self.boundary_status,
      'sample_count': self.sample_count,
      'static_pressure_residuals': list(self.static_pressure_residuals),
      'companion_invariant_residuals': list(self.companion_invariant_residuals),
      'geometry_residuals_m': list(self.geometry_residuals_m),
      'maximum_static_pressure_residual': self.maximum_static_pressure_residual,
      'maximum_companion_invariant_residual': (
        self.maximum_companion_invariant_residual
      ),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'minimum_shock_clearance_m': self.minimum_shock_clearance_m,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'separation_m': self.separation_m,
      'checks': {
        'sampling_verified': self.sampling_verified,
        'pressure_verified': self.pressure_verified,
        'invariant_verified': self.invariant_verified,
        'geometry_verified': self.geometry_verified,
        'fidelity_flags_verified': self.fidelity_flags_verified,
        'local_boundary_consistency_verified': (
          self.local_boundary_consistency_verified
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'independent-ambient-companion-boundary-audit; global-reflected-'
        'free-boundary closure and external validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _ambient_companion_boundary_audit_failure(
  status: MocEulerAmbientCompanionBoundaryAuditStatus,
  message: str,
  *,
  boundary_status: str | None = None,
  sample_count: int = 0,
  static_pressure_residuals: tuple[float, ...] = (),
  companion_invariant_residuals: tuple[float, ...] = (),
  geometry_residuals_m: tuple[float, ...] = (),
  ambient_pressure_Pa: float | None = None,
  separation_m: float | None = None,
  minimum_shock_clearance_m: float | None = None,
  sampling_verified: bool = False,
  pressure_verified: bool = False,
  invariant_verified: bool = False,
  geometry_verified: bool = False,
  fidelity_flags_verified: bool = False,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
) -> MocEulerAmbientCompanionBoundaryAudit:
  return MocEulerAmbientCompanionBoundaryAudit(
    status=status,
    boundary_status=boundary_status,
    sample_count=sample_count,
    static_pressure_residuals=static_pressure_residuals,
    companion_invariant_residuals=companion_invariant_residuals,
    geometry_residuals_m=geometry_residuals_m,
    maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
    maximum_companion_invariant_residual=max(
      companion_invariant_residuals,
      default=None,
    ),
    maximum_geometry_residual_m=max(geometry_residuals_m, default=None),
    minimum_shock_clearance_m=minimum_shock_clearance_m,
    sampling_verified=sampling_verified,
    pressure_verified=pressure_verified,
    invariant_verified=invariant_verified,
    geometry_verified=geometry_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    ambient_pressure_Pa=ambient_pressure_Pa,
    separation_m=separation_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    message=message,
  )
####


def measure_moc_ambient_companion_boundary(
  boundary: MocEulerAmbientCompanionBoundaryResult,
  *,
  position_tolerance_m: float | None = None,
  invariant_tolerance: float | None = None,
  pressure_tolerance: float | None = None,
) -> MocEulerAmbientCompanionBoundaryAudit:
  """Rebuild an ambient companion boundary's local evidence independently."""

  if not isinstance(boundary, MocEulerAmbientCompanionBoundaryResult):
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.INVALID_INPUT,
      'boundary must be a MocEulerAmbientCompanionBoundaryResult',
    )
  ####
  try:
    position_tolerance = float(
      boundary.position_tolerance_m
      if position_tolerance_m is None
      else position_tolerance_m
    )
    invariant_tolerance_value = float(
      boundary.invariant_tolerance
      if invariant_tolerance is None
      else invariant_tolerance
    )
    pressure_tolerance_value = float(
      boundary.pressure_tolerance
      if pressure_tolerance is None
      else pressure_tolerance
    )
  except (TypeError, ValueError):
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.INVALID_INPUT,
      'ambient companion boundary audit tolerances must be numeric',
      boundary_status=boundary.status.value,
      sample_count=len(boundary.samples),
    )
  ####
  tolerances = (
    position_tolerance,
    invariant_tolerance_value,
    pressure_tolerance_value,
  )
  if any(not isfinite(value) or value <= 0.0 for value in tolerances):
    raise ValueError(
      'ambient companion boundary audit tolerances must be finite and positive'
    )
  ####
  common = {
    'boundary_status': boundary.status.value,
    'sample_count': len(boundary.samples),
    'ambient_pressure_Pa': boundary.ambient_pressure_Pa,
    'separation_m': boundary.separation_m,
    'position_tolerance_m': position_tolerance,
    'invariant_tolerance': invariant_tolerance_value,
    'pressure_tolerance': pressure_tolerance_value,
  }
  if not boundary.converged:
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.BOUNDARY_FAILURE,
      'ambient companion boundary audit requires a converged solver result',
      **common,
    )
  ####
  shock = boundary.shock_boundary
  if (
    shock is None
    or not shock.converged
    or not shock.local_euler_verified
    or shock.orientation is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
  ):
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.BOUNDARY_FAILURE,
      'ambient companion boundary audit requires a converged mixed-characteristic shock curve',
      **common,
    )
  ####
  ambient_pressure = boundary.ambient_pressure_Pa
  separation = boundary.separation_m
  seed_k_minus = boundary.seed_k_minus_rad
  if (
    ambient_pressure is None
    or separation is None
    or seed_k_minus is None
  ):
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.BOUNDARY_FAILURE,
      'ambient companion boundary audit requires ambient pressure, separation, and seeded invariant',
      **common,
    )
  ####
  shock_points = tuple(shock.shock_points_m)
  shock_states = tuple(shock.downstream_states)
  shock_pressures = tuple(shock.downstream_total_pressure_Pa)
  samples = tuple(boundary.samples)
  sampling_verified = bool(
    len(samples) >= 2
    and len(samples) == len(shock_points)
    and len(samples) == len(shock_states)
    and len(samples) == len(shock_pressures)
    and all(
      abs(sample.state.x_m - point[0]) <= position_tolerance
      and abs(sample.total_pressure_Pa - pressure)
      <= pressure_tolerance_value * max(1.0, abs(pressure))
      for sample, point, pressure in zip(
        samples,
        shock_points,
        shock_pressures,
        strict=True,
      )
    )
    and all(
      abs(sample.state.gamma - state.gamma) <= invariant_tolerance_value
      for sample, state in zip(samples, shock_states, strict=True)
    )
    and all(
      shock_points[index + 1][0]
      > shock_points[index][0] + position_tolerance
      for index in range(len(shock_points) - 1)
    )
  )
  if not sampling_verified:
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.BOUNDARY_FAILURE,
      'ambient companion boundary sample alignment or downstream ordering failed',
      sampling_verified=False,
      **common,
    )
  ####
  gamma = shock_states[0].gamma
  pressure_residuals: list[float] = []
  invariant_residuals: list[float] = []
  geometry_residuals: list[float] = []
  clearances: list[float] = []
  try:
    for index, (sample, point, total_pressure) in enumerate(
      zip(samples, shock_points, shock_pressures, strict=True)
    ):
      state = sample.state
      static_pressure = total_pressure / (
        1.0 + 0.5 * (gamma - 1.0) * state.mach * state.mach
      ) ** (gamma / (gamma - 1.0))
      pressure_residuals.append(
        abs(static_pressure - ambient_pressure) / ambient_pressure
      )
      invariant_residuals.append(
        abs(
          state.theta_rad
          + prandtl_meyer_angle_rad(state.mach, gamma)
          - seed_k_minus
        )
      )
      clearances.append(state.y_m - point[1])
      if index == 0:
        geometry_residuals.append(
          abs((state.y_m - point[1]) - separation)
        )
      else:
        previous = samples[index - 1].state
        geometry_residuals.append(
          abs(
            (state.y_m - previous.y_m)
            - 0.5 * (previous.theta_rad + state.theta_rad)
            * (point[0] - shock_points[index - 1][0])
          )
        )
      ####
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _ambient_companion_boundary_audit_failure(
      MocEulerAmbientCompanionBoundaryAuditStatus.INVARIANT_FAILURE,
      f'ambient companion boundary reconstruction failed: {error}',
      sampling_verified=True,
      **common,
    )
  ####
  maximum_pressure = max(pressure_residuals, default=float('inf'))
  maximum_invariant = max(invariant_residuals, default=float('inf'))
  maximum_geometry = max(geometry_residuals, default=float('inf'))
  minimum_clearance = min(clearances, default=None)
  pressure_verified = maximum_pressure <= pressure_tolerance_value
  invariant_verified = maximum_invariant <= invariant_tolerance_value
  geometry_verified = bool(
    maximum_geometry <= position_tolerance
    and minimum_clearance is not None
    and minimum_clearance > position_tolerance
  )
  fidelity_flags_verified = bool(
    boundary.physical_closure_verified is False
    and boundary.chain_promotion_blocked
    and boundary.production_claim_allowed is False
  )
  if not pressure_verified:
    status = MocEulerAmbientCompanionBoundaryAuditStatus.PRESSURE_FAILURE
    message = 'ambient companion boundary static-pressure residual exceeded tolerance'
  elif not invariant_verified:
    status = MocEulerAmbientCompanionBoundaryAuditStatus.INVARIANT_FAILURE
    message = 'ambient companion boundary C- invariant residual exceeded tolerance'
  elif not geometry_verified:
    status = MocEulerAmbientCompanionBoundaryAuditStatus.GEOMETRY_FAILURE
    message = 'ambient companion boundary geometry or shock clearance failed'
  elif not fidelity_flags_verified:
    status = MocEulerAmbientCompanionBoundaryAuditStatus.FLAG_FAILURE
    message = 'ambient companion boundary promotion flags weakened the fidelity boundary'
  else:
    status = MocEulerAmbientCompanionBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent ambient companion boundary audit verified sample alignment, '
      'ambient pressure, C- invariant, geometry, and non-promotion flags; '
      'global reflected free-boundary closure remains pending'
    )
  ####
  return MocEulerAmbientCompanionBoundaryAudit(
    status=status,
    boundary_status=boundary.status.value,
    sample_count=len(samples),
    static_pressure_residuals=tuple(pressure_residuals),
    companion_invariant_residuals=tuple(invariant_residuals),
    geometry_residuals_m=tuple(geometry_residuals),
    maximum_static_pressure_residual=maximum_pressure,
    maximum_companion_invariant_residual=maximum_invariant,
    maximum_geometry_residual_m=maximum_geometry,
    minimum_shock_clearance_m=minimum_clearance,
    sampling_verified=sampling_verified,
    pressure_verified=pressure_verified,
    invariant_verified=invariant_verified,
    geometry_verified=geometry_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    ambient_pressure_Pa=ambient_pressure,
    separation_m=separation,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
    physical_closure_verified=boundary.physical_closure_verified,
    chain_promotion_blocked=boundary.chain_promotion_blocked,
    production_claim_allowed=boundary.production_claim_allowed,
    message=message,
  )
####


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
    ####
    for name in ('shock_sample_count', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in ('shock_residual_tolerance', 'cell_residual_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'shock_jump_mass_residuals',
      'shock_jump_momentum_residuals',
      'shock_jump_energy_residuals',
      'cell_euler_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
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
      ####
    ####
    if self.field_status is not None:
      object.__setattr__(self, 'field_status', str(self.field_status))
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerCompanionFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

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
  ####

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
  ####
####


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
####


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
  ####
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
  ####
  tolerances = (
    shock_tolerance,
    cell_tolerance,
    position_tolerance,
    invariant_tolerance_value,
    pressure_tolerance_value,
  )
  if any(not isfinite(value) or value <= 0.0 for value in tolerances):
    raise ValueError('companion-field audit tolerances must be finite and positive')
  ####
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
  ####
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
  ####
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
  ####
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
    ####
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
    ####
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
  ####
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
      ####
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
    ####
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
  ####
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
  ####
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
####


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
  ####
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
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (shock_tolerance, cell_tolerance, position_tolerance)
  ):
    raise ValueError('Euler audit tolerances must be finite and positive')
  ####
  if not field.converged or not field.physical_closure_verified:
    return _failure(
      MocPhysicalFieldEulerAuditStatus.FIELD_FAILURE,
      'Euler audit requires a converged physically closed field',
      field_status=field.status.value,
      shock_sample_count=len(field.shock_boundary_points_m),
      cell_count=len(field.cells),
      residual_tolerance=cell_tolerance,
    )
  ####
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
  ####
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
  ####
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
  ####
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
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerAuditStatus.SHOCK_JUMP_FAILURE,
      f'shock Euler flux reconstruction failed: {error}',
      field_status=field.status.value,
      shock_sample_count=len(shock_points),
      cell_count=len(field.cells),
      residual_tolerance=cell_tolerance,
    )
  ####
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
  ####
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
  ####
  cell_residuals: list[float] = []
  try:
    for (vertices, states, pressures) in cell_samples:
      if any(value is None for value in pressures):
        raise ValueError(
          'bounded cell sampling returned a missing total pressure'
        )
      ####
      cell_residuals.append(
        _cell_flux_residual(
          tuple((float(point[0]), float(point[1])) for point in vertices),
          tuple(states),
          tuple(float(value) for value in pressures),
        )
      )
    ####
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
  ####
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
  ####
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
####


class MocEulerAmbientPhysicalFieldAuditStatus(str, Enum):
  """Outcome of auditing the exact ambient-closed physical-field bridge."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_ambient_physical_field_audit'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'euler_ambient_physical_field_audit_shock_failure'
  AMBIENT_FAILURE = 'euler_ambient_physical_field_audit_ambient_failure'
  FIELD_FAILURE = 'euler_ambient_physical_field_audit_field_failure'
  ENTROPY_FAILURE = 'euler_ambient_physical_field_audit_entropy_failure'
  CELL_RESIDUAL_FAILURE = (
    'euler_ambient_physical_field_audit_cell_residual_failure'
  )
  FLAG_FAILURE = 'euler_ambient_physical_field_audit_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientPhysicalFieldAudit:
  """Independent gate report for an exact ambient-closed field candidate.

  The audit deliberately keeps geometric field closure separate from the
  conservative-cell residual gate.  This lets the long-running planner
  retain a useful exact field for diagnostics while refusing to promote it
  into a continued shock-cell chain until refinement and cell evidence pass.
  """

  status: MocEulerAmbientPhysicalFieldAuditStatus
  result_status: str | None
  shock_sample_count: int
  field_cell_count: int
  shock_jump_verified: bool
  cell_euler_residuals_verified: bool
  physical_field_verified: bool
  entropy_lineage_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  maximum_shock_jump_mass_residual: float | None = None
  maximum_shock_jump_momentum_residual: float | None = None
  maximum_shock_jump_energy_residual: float | None = None
  maximum_cell_euler_residual: float | None = None
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_PHYSICAL_FIELD_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientPhysicalFieldAuditStatus):
      raise TypeError(
        'status must be a MocEulerAmbientPhysicalFieldAuditStatus'
      )
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    for name in ('shock_sample_count', 'field_cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'shock_jump_verified',
      'cell_euler_residuals_verified',
      'physical_field_verified',
      'entropy_lineage_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether every requested local bridge audit gate passed."""

    return self.status is MocEulerAmbientPhysicalFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the audit passed while preserving the hard claim boundary."""

    return bool(
      self.converged
      and self.shock_jump_verified
      and self.cell_euler_residuals_verified
      and self.physical_field_verified
      and self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'shock_sample_count': self.shock_sample_count,
      'field_cell_count': self.field_cell_count,
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
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'physical_field_verified': self.physical_field_verified,
        'entropy_lineage_verified': self.entropy_lineage_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'exact ambient-closed physical-field audit; independent cell '
        'refinement, canonical reflected free-boundary, and external '
        'validation remain explicit promotion gates'
      ),
      'message': self.message,
    }
  ####
####


def _ambient_physical_field_audit_failure(
  status: MocEulerAmbientPhysicalFieldAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  shock_sample_count: int = 0,
  field_cell_count: int = 0,
  shock_jump_verified: bool = False,
  cell_euler_residuals_verified: bool = False,
  physical_field_verified: bool = False,
  entropy_lineage_verified: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  maximum_shock_jump_mass_residual: float | None = None,
  maximum_shock_jump_momentum_residual: float | None = None,
  maximum_shock_jump_energy_residual: float | None = None,
  maximum_cell_euler_residual: float | None = None,
) -> MocEulerAmbientPhysicalFieldAudit:
  return MocEulerAmbientPhysicalFieldAudit(
    status=status,
    result_status=result_status,
    shock_sample_count=shock_sample_count,
    field_cell_count=field_cell_count,
    shock_jump_verified=shock_jump_verified,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    physical_field_verified=physical_field_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    maximum_shock_jump_mass_residual=maximum_shock_jump_mass_residual,
    maximum_shock_jump_momentum_residual=maximum_shock_jump_momentum_residual,
    maximum_shock_jump_energy_residual=maximum_shock_jump_energy_residual,
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    message=message,
  )
####


def measure_moc_euler_ambient_physical_field(
  result: MocEulerAmbientPhysicalFieldResult,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-8,
) -> MocEulerAmbientPhysicalFieldAudit:
  """Audit the exact shock, ambient march, and retained physical field.

  The nested physical-field audit is intentionally run even when the exact
  bridge has already marked its geometry closed.  Its conservative cell
  residual is the independent promotion gate for a future continued chain.
  """

  if not isinstance(result, MocEulerAmbientPhysicalFieldResult):
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.INVALID_INPUT,
      'result must be a MocEulerAmbientPhysicalFieldResult',
    )
  ####
  try:
    shock_tolerance = float(shock_residual_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    position_tolerance = float(position_tolerance_m)
    pressure_tolerance_value = float(pressure_tolerance)
    invariant_tolerance_value = float(invariant_tolerance)
  except (TypeError, ValueError):
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.INVALID_INPUT,
      'ambient physical-field audit tolerances must be numeric',
      result_status=result.status.value,
    )
  ####
  tolerances = (
    shock_tolerance,
    cell_tolerance,
    position_tolerance,
    pressure_tolerance_value,
    invariant_tolerance_value,
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('ambient physical-field audit tolerances must be finite and positive')
  ####
  shock = result.shock_boundary
  march = result.ambient_march
  field = result.field
  shock_count = 0 if shock is None else len(shock.shock_points_m)
  cell_count = 0 if field is None else len(field.cells)
  if shock is None:
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.SHOCK_FAILURE,
      'exact ambient physical-field result did not retain a shock boundary',
      result_status=result.status.value,
      field_cell_count=cell_count,
    )
  ####
  if not shock.converged or not shock.local_euler_verified:
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.SHOCK_FAILURE,
      'exact shock boundary did not pass its local Euler gate',
      result_status=result.status.value,
      shock_sample_count=shock_count,
      field_cell_count=cell_count,
    )
  ####
  if march is None or not march.converged:
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.AMBIENT_FAILURE,
      'exact ambient physical-field result did not retain a converged ambient march',
      result_status=result.status.value,
      shock_sample_count=shock_count,
      field_cell_count=cell_count,
    )
  ####
  ambient_boundary_verified = bool(
    len(march.boundary_samples) == shock_count
    and len(march.point_results) == shock_count
    and march.ambient_boundary.converged
    and march.maximum_geometry_residual_m is not None
    and march.maximum_geometry_residual_m <= position_tolerance
    and march.maximum_absolute_pressure_residual is not None
    and march.maximum_absolute_pressure_residual <= pressure_tolerance_value
    and march.maximum_absolute_invariant_residual is not None
    and march.maximum_absolute_invariant_residual <= invariant_tolerance_value
    and march.attachment_relative_pressure_residual is not None
    and abs(march.attachment_relative_pressure_residual) <= pressure_tolerance_value
    and all(result_item.converged for result_item in march.point_results)
    and all(
      residual <= invariant_tolerance_value
      for residual in march.incoming_k_plus_residuals
    )
  )
  if not ambient_boundary_verified:
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.AMBIENT_FAILURE,
      'ambient march did not pass independent pressure, geometry, and invariant checks',
      result_status=result.status.value,
      shock_sample_count=shock_count,
      field_cell_count=cell_count,
    )
  ####
  if field is None:
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.FIELD_FAILURE,
      'exact ambient physical-field result did not retain a physical field',
      result_status=result.status.value,
      shock_sample_count=shock_count,
    )
  ####
  try:
    field_audit = measure_moc_physical_field_euler_audit(
      field,
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
      position_tolerance_m=position_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _ambient_physical_field_audit_failure(
      MocEulerAmbientPhysicalFieldAuditStatus.FIELD_FAILURE,
      f'independent physical-field audit raised: {error}',
      result_status=result.status.value,
      shock_sample_count=shock_count,
      field_cell_count=cell_count,
    )
  ####
  physical_field_verified = bool(
    result.converged
    and result.physical_field_verified
    and field.converged
    and field.physical_closure_verified
    and field.state_sampling_available
    and field_audit.field_topology_verified
  )
  shock_jump_verified = bool(
    result.shock_boundary_verified
    and field_audit.shock_jump_verified
  )
  flags_verified = bool(
    result.chain_promotion_blocked
    and not result.production_claim_allowed
    and march.chain_promotion_blocked
    and not march.production_claim_allowed
  )
  physical_closure_verified = bool(
    result.physical_closure_verified and field.physical_closure_verified
  )
  chain_promotion_blocked = bool(
    result.chain_promotion_blocked and march.chain_promotion_blocked
  )
  production_claim_allowed = bool(
    result.production_claim_allowed or march.production_claim_allowed
  )
  common = dict(
    result_status=result.status.value,
    shock_sample_count=shock_count,
    field_cell_count=cell_count,
    shock_jump_verified=shock_jump_verified,
    cell_euler_residuals_verified=field_audit.cell_euler_residuals_verified,
    physical_field_verified=physical_field_verified,
    entropy_lineage_verified=result.entropy_lineage_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    maximum_shock_jump_mass_residual=(
      field_audit.maximum_shock_jump_mass_residual
    ),
    maximum_shock_jump_momentum_residual=(
      field_audit.maximum_shock_jump_momentum_residual
    ),
    maximum_shock_jump_energy_residual=(
      field_audit.maximum_shock_jump_energy_residual
    ),
    maximum_cell_euler_residual=field_audit.maximum_cell_euler_residual,
  )
  if not shock_jump_verified:
    status = MocEulerAmbientPhysicalFieldAuditStatus.SHOCK_FAILURE
    message = 'independent shock Rankine--Hugoniot audit exceeded tolerance'
  elif not physical_field_verified:
    status = MocEulerAmbientPhysicalFieldAuditStatus.FIELD_FAILURE
    message = 'independent physical-field topology or state-sampling audit failed'
  elif not physical_closure_verified:
    status = MocEulerAmbientPhysicalFieldAuditStatus.FIELD_FAILURE
    message = 'exact ambient physical-field closure flag was not verified'
  elif not field_audit.cell_euler_residuals_verified:
    status = MocEulerAmbientPhysicalFieldAuditStatus.CELL_RESIDUAL_FAILURE
    message = (
      'independent conservative cell Euler residual exceeded tolerance; '
      'refinement is required before chain promotion'
    )
  elif not result.entropy_lineage_verified:
    status = MocEulerAmbientPhysicalFieldAuditStatus.ENTROPY_FAILURE
    message = (
      'exact field retained variable downstream entropy/total-pressure '
      'lineage that is not yet admitted by the continued-chain contract'
    )
  elif not flags_verified:
    status = MocEulerAmbientPhysicalFieldAuditStatus.FLAG_FAILURE
    message = 'exact ambient physical-field fidelity flags were weakened'
  else:
    status = MocEulerAmbientPhysicalFieldAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent exact ambient physical-field audit passed shock, ambient, '
      'field, cell, entropy-lineage, and fidelity gates'
    )
  ####
  return _ambient_physical_field_audit_failure(
    status,
    message,
    **common,
  )
####


MOC_EULER_COMPANION_FIELD_CHAIN_AUDIT_OPERATOR_ID = (
  'op.moc.euler-companion-field-chain-audit'
)


class MocEulerCompanionFieldChainAuditStatus(str, Enum):
  """Outcome of independently measuring an open Euler-field sequence."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_companion_field_chain_audit'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'euler_companion_field_chain_field_failure'
  HANDOFF_FAILURE = 'euler_companion_field_chain_handoff_failure'
  DOMAIN_FAILURE = 'euler_companion_field_chain_domain_failure'
  TERMINATION_FAILURE = 'euler_companion_field_chain_termination_failure'
  FLAG_FAILURE = 'euler_companion_field_chain_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldChainAudit:
  """Independent evidence for a repeated open Euler companion-field path."""

  status: MocEulerCompanionFieldChainAuditStatus
  field_count: int
  continued_field_count: int
  step_count: int
  field_statuses: tuple[str, ...]
  field_audits_verified: bool
  fresh_domains_verified: bool
  handoff_links_verified: bool
  termination_verified: bool
  fidelity_flags_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_COMPANION_FIELD_CHAIN_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerCompanionFieldChainAuditStatus,
    ):
      raise TypeError(
        'status must be a MocEulerCompanionFieldChainAuditStatus'
      )
    ####
    for name in (
      'field_count',
      'continued_field_count',
      'step_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    statuses = tuple(str(value) for value in self.field_statuses)
    if len(statuses) != self.field_count:
      raise ValueError('field_statuses must match field_count')
    ####
    object.__setattr__(self, 'field_statuses', statuses)
    for name in (
      'field_audits_verified',
      'fresh_domains_verified',
      'handoff_links_verified',
      'termination_verified',
      'fidelity_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerCompanionFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_sequence_verified(self) -> bool:
    return bool(
      self.converged
      and self.field_audits_verified
      and self.fresh_domains_verified
      and self.handoff_links_verified
      and self.termination_verified
      and self.fidelity_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'step_count': self.step_count,
      'field_statuses': list(self.field_statuses),
      'checks': {
        'field_audits_verified': self.field_audits_verified,
        'fresh_domains_verified': self.fresh_domains_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'termination_verified': self.termination_verified,
        'fidelity_flags_verified': self.fidelity_flags_verified,
        'local_sequence_verified': self.local_sequence_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-open-euler-companion-field-chain-audit; reflected-free-'
        'boundary, entropy closure, and external validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _euler_chain_handoff_fingerprint(samples: Any) -> str | None:
  try:
    handoff = tuple(samples)
  except TypeError:
    return None
  ####
  if not handoff:
    return None
  ####
  payload = '\n'.join(
    '|'.join(
      value.hex()
      for value in (
        sample.state.x_m,
        sample.state.y_m,
        sample.state.theta_rad,
        sample.state.mach,
        sample.state.gamma,
        float(sample.total_pressure_Pa),
      )
    )
    for sample in handoff
  )
  return sha256(payload.encode('ascii')).hexdigest()
####


def _euler_chain_field_fingerprint(field: Any) -> str | None:
  if field is None:
    return None
  ####

  def state_payload(state: Any) -> str:
    return '|'.join(
      float(value).hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )
  ####

  try:
    payload = [f'status:{field.status.value}']
    for label, states, pressures in (
      (
        'shock',
        field.shock_boundary_states,
        field.shock_boundary_total_pressure_Pa,
      ),
      (
        'companion',
        field.companion_boundary_states,
        field.companion_boundary_total_pressure_Pa,
      ),
      ('interior', field.interior_states, field.interior_total_pressure_Pa),
    ):
      payload.append(label)
      payload.extend(
        f'{state_payload(state)}|{float(pressure).hex()}'
        for state, pressure in zip(states, pressures, strict=True)
      )
    ####
  except (AttributeError, TypeError, ValueError):
    return None
  ####
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()
####


def _euler_chain_field_x_extent(field: Any) -> tuple[float, float] | None:
  try:
    points = (
      *field.shock_boundary_points_m,
      *field.companion_boundary_points_m,
      *field.interior_points_m,
    )
    values = tuple(float(point[0]) for point in points)
  except (AttributeError, TypeError, ValueError, IndexError):
    return None
  ####
  if not values or not all(isfinite(value) for value in values):
    return None
  ####
  return min(values), max(values)
####


def _euler_companion_field_chain_audit_failure(
  status: MocEulerCompanionFieldChainAuditStatus,
  message: str,
  *,
  field_count: int = 0,
  continued_field_count: int = 0,
  step_count: int = 0,
  field_statuses: tuple[str, ...] = (),
  field_audits_verified: bool = False,
  fresh_domains_verified: bool = False,
  handoff_links_verified: bool = False,
  termination_verified: bool = False,
  fidelity_flags_verified: bool = False,
) -> MocEulerCompanionFieldChainAudit:
  return MocEulerCompanionFieldChainAudit(
    status=status,
    field_count=field_count,
    continued_field_count=continued_field_count,
    step_count=step_count,
    field_statuses=field_statuses,
    field_audits_verified=field_audits_verified,
    fresh_domains_verified=fresh_domains_verified,
    handoff_links_verified=handoff_links_verified,
    termination_verified=termination_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    message=message,
  )
####


def measure_moc_euler_companion_field_chain(
  chain: Any,
) -> MocEulerCompanionFieldChainAudit:
  """Recompute the open-field sequence and exact frontier links.

  The measurement uses only retained field samples and planner metadata.  It
  never invokes the continuation callback or a solver, and a passing audit is
  still explicitly below physical chain-cell promotion.
  """

  from exhaust_plume.models.moc.euler_characteristic_field import (
    MocEulerCompanionFieldResult,
  )
  from exhaust_plume.models.moc.planner import (
    MocEulerCompanionFieldChainPlannerResult,
  )

  if not isinstance(chain, MocEulerCompanionFieldChainPlannerResult):
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.INVALID_INPUT,
      'chain must be a MocEulerCompanionFieldChainPlannerResult',
    )
  ####
  fields = tuple(chain.fields)
  steps = tuple(chain.steps)
  if not fields or any(
    not isinstance(field, MocEulerCompanionFieldResult)
    for field in fields
  ):
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.INVALID_INPUT,
      'chain must retain one or more Euler companion fields',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=tuple(field.status.value for field in fields),
    )
  ####

  field_audits = tuple(measure_moc_euler_companion_field(field) for field in fields)
  field_audits_verified = all(
    audit.converged and audit.local_euler_consistency_verified
    for audit in field_audits
  )
  if not field_audits_verified:
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.FIELD_FAILURE,
      'one or more open Euler companion fields failed its local audit',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=tuple(field.status.value for field in fields),
      field_audits_verified=False,
    )
  ####

  fresh_domains_verified = True
  extents = tuple(_euler_chain_field_x_extent(field) for field in fields)
  for previous, current in zip(extents, extents[1:]):
    fresh_domains_verified = fresh_domains_verified and bool(
      previous is not None
      and current is not None
      and current[0] > previous[1] + 1.0e-10
    )
  ####
  if not fresh_domains_verified:
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.DOMAIN_FAILURE,
      'open Euler companion fields do not occupy fresh downstream domains',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=tuple(field.status.value for field in fields),
      field_audits_verified=True,
      fresh_domains_verified=False,
    )
  ####

  handoff_links_verified = bool(steps)
  for index, step in enumerate(steps):
    expected_index = index + 2
    handoff = fields[index].downstream_handoff if index < len(fields) else ()
    expected_fingerprint = _euler_chain_handoff_fingerprint(handoff)
    handoff_links_verified = handoff_links_verified and bool(
      step.next_field_index == expected_index
      and step.incoming_handoff_fingerprint == expected_fingerprint
      and step.incoming_handoff_link_verified
    )
    if step.result_kind == 'field-solve-returned':
      if index + 1 >= len(fields):
        handoff_links_verified = False
        continue
      ####
      next_field = fields[index + 1]
      handoff_links_verified = handoff_links_verified and bool(
        step.result_field_status == next_field.status.value
        and step.result_handoff_sample_count == len(next_field.downstream_handoff)
        and step.result_handoff_fingerprint == _euler_chain_handoff_fingerprint(
          next_field.downstream_handoff
        )
        and step.result_field_fingerprint == _euler_chain_field_fingerprint(
          next_field
        )
      )
    ####
  ####
  if not handoff_links_verified:
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.HANDOFF_FAILURE,
      'open Euler companion field frontier links failed independent remeasurement',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=tuple(field.status.value for field in fields),
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=False,
    )
  ####

  termination_verified = bool(
    steps
    and steps[-1].result_termination_reason is chain.termination.reason
    and steps[-1].result_physical_termination
    is chain.termination.physical_termination
  )
  if not termination_verified:
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.TERMINATION_FAILURE,
      'chain termination metadata did not match its final planner step',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=tuple(field.status.value for field in fields),
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=True,
      termination_verified=False,
    )
  ####

  fidelity_flags_verified = bool(
    not chain.physical_closure_verified
    and chain.chain_promotion_blocked
    and not chain.production_claim_allowed
    and all(
      not field.physical_closure_verified
      and field.chain_promotion_blocked
      and not field.production_claim_allowed
      for field in fields
    )
  )
  if not fidelity_flags_verified:
    return _euler_companion_field_chain_audit_failure(
      MocEulerCompanionFieldChainAuditStatus.FLAG_FAILURE,
      'open Euler companion field sequence weakened its fidelity boundary',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=tuple(field.status.value for field in fields),
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=True,
      termination_verified=True,
      fidelity_flags_verified=False,
    )
  ####
  return MocEulerCompanionFieldChainAudit(
    status=MocEulerCompanionFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT,
    field_count=len(fields),
    continued_field_count=max(0, len(fields) - 1),
    step_count=len(steps),
    field_statuses=tuple(field.status.value for field in fields),
    field_audits_verified=True,
    fresh_domains_verified=True,
    handoff_links_verified=True,
    termination_verified=True,
    fidelity_flags_verified=True,
    message=(
      'independent open Euler companion-field sequence audit reproduced '
      'local field evidence, fresh domains, exact frontier links, and the '
      'typed non-physical stop; reflected/free-boundary and entropy closure '
      'remain pending'
    ),
  )
####


MOC_EULER_COMPANION_FIELD_CHAIN_REFINEMENT_OPERATOR_ID = (
  'op.moc.euler-companion-field-chain-refinement'
)
_EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL = 1.0e300


class MocEulerCompanionFieldChainRefinementMeasurementStatus(str, Enum):
  """Outcome of comparing independently measured open-field resolutions."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'resolution_failure'
  CASE_FAILURE = 'case_failure'
  CONSISTENCY_FAILURE = 'consistency_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  SENSITIVITY_FAILURE = 'sensitivity_failure'
  TERMINATION_FAILURE = 'termination_failure'
  FIDELITY_FAILURE = 'fidelity_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldChainRefinementCase:
  """One declared resolution of an open Euler-field chain.

  ``resolution`` is caller-owned metadata, normally the number of retained
  shock/companion samples in every field of the chain.  The independent
  operator checks that the retained arrays actually match this declaration;
  it never infers a resolution from a cell count or repairs a mismatch.
  ``chain`` is typed at the operator boundary to avoid importing the planner
  module while this validation module is imported by the planner.
  """

  resolution: int
  chain: Any

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 2
    ):
      raise ValueError('resolution must be an integer of at least two')
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldChainRefinementMeasurement:
  """Independent topology, geometry, and sensitivity evidence.

  A passing result means that the already-returned open-field sequence is
  locally reproducible over the declared resolutions.  It does not mean that
  the companion boundary is a solved reflected/free boundary, and it never
  authorizes promotion to a physical ``MocChainCell``.
  """

  status: MocEulerCompanionFieldChainRefinementMeasurementStatus
  cases: tuple[MocEulerCompanionFieldChainRefinementCase, ...] = ()
  chain_audits: tuple[MocEulerCompanionFieldChainAudit, ...] = ()
  resolutions: tuple[int, ...] = ()
  expected_resolutions: tuple[int, ...] = ()
  field_count: int | None = None
  continued_field_count: int | None = None
  expected_resolutions_verified: bool = False
  resolution_order_verified: bool = False
  field_count_consistent: bool = False
  continued_field_count_consistent: bool = False
  step_count_consistent: bool = False
  sample_resolution_verified: bool = False
  topology_verified: bool = False
  geometry_shape_verified: bool = False
  field_euler_audits_verified: bool = False
  handoff_links_verified: bool | None = None
  termination_sensitivity_verified: bool | None = None
  fidelity_flags_verified: bool = False
  cell_residual_trend_verified: bool = False
  refinement_convergence_verified: bool = False
  field_node_counts: tuple[tuple[int, ...], ...] = ()
  field_cell_counts: tuple[tuple[int, ...], ...] = ()
  maximum_cell_euler_residuals: tuple[float, ...] = ()
  axial_extent_residuals_m: tuple[float, ...] = ()
  shock_endpoint_residuals_m: tuple[float, ...] = ()
  companion_endpoint_residuals_m: tuple[float, ...] = ()
  interior_endpoint_residuals_m: tuple[float, ...] = ()
  endpoint_tolerance_m: float = 1.0e-10
  cell_residual_tolerance: float = 1.0e-2
  cell_residual_trend_tolerance: float = 1.0e-12
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''
  operator_id: str = MOC_EULER_COMPANION_FIELD_CHAIN_REFINEMENT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerCompanionFieldChainRefinementMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerCompanionFieldChainRefinementMeasurementStatus'
      )
    ####
    cases = tuple(self.cases)
    audits = tuple(self.chain_audits)
    if len(cases) != len(audits):
      raise ValueError('cases and chain_audits must have equal lengths')
    ####
    if any(
      not isinstance(case, MocEulerCompanionFieldChainRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain MocEulerCompanionFieldChainRefinementCase values'
      )
    ####
    if any(
      not isinstance(audit, MocEulerCompanionFieldChainAudit)
      for audit in audits
    ):
      raise TypeError(
        'chain_audits must contain MocEulerCompanionFieldChainAudit values'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'chain_audits', audits)
    resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != resolutions:
      raise ValueError('resolutions must match the declared refinement cases')
    ####
    object.__setattr__(self, 'resolutions', resolutions)
    expected = tuple(int(value) for value in self.expected_resolutions)
    if any(value < 2 for value in expected):
      raise ValueError('expected_resolutions must contain values of at least two')
    ####
    object.__setattr__(self, 'expected_resolutions', expected)
    for name in (
      'field_count',
      'continued_field_count',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer when supplied')
      ####
    ####
    for name in (
      'endpoint_tolerance_m',
      'cell_residual_tolerance',
      'cell_residual_trend_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'maximum_cell_euler_residuals',
      'axial_extent_residuals_m',
      'shock_endpoint_residuals_m',
      'companion_endpoint_residuals_m',
      'interior_endpoint_residuals_m',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'expected_resolutions_verified',
      'resolution_order_verified',
      'field_count_consistent',
      'continued_field_count_consistent',
      'step_count_consistent',
      'sample_resolution_verified',
      'topology_verified',
      'geometry_shape_verified',
      'field_euler_audits_verified',
      'fidelity_flags_verified',
      'cell_residual_trend_verified',
      'refinement_convergence_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'handoff_links_verified',
      'termination_sensitivity_verified',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, bool):
        raise TypeError(f'{name} must be a bool or None')
      ####
    ####
    for name in ('field_node_counts', 'field_cell_counts'):
      rows = tuple(tuple(int(value) for value in row) for row in getattr(self, name))
      if any(
        any(value < 0 for value in row)
        for row in rows
      ):
        raise ValueError(f'{name} must contain nonnegative integer counts')
      ####
      object.__setattr__(self, name, rows)
    ####
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'message', str(self.message))
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerCompanionFieldChainRefinementMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_count': len(self.cases),
      'resolutions': list(self.resolutions),
      'expected_resolutions': list(self.expected_resolutions),
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'field_node_counts': [list(row) for row in self.field_node_counts],
      'field_cell_counts': [list(row) for row in self.field_cell_counts],
      'cases': [
        {
          'resolution': case.resolution,
          'chain_audit': audit.as_report(),
        }
        for case, audit in zip(self.cases, self.chain_audits, strict=True)
      ],
      'checks': {
        'expected_resolutions_verified': self.expected_resolutions_verified,
        'resolution_order_verified': self.resolution_order_verified,
        'field_count_consistent': self.field_count_consistent,
        'continued_field_count_consistent': (
          self.continued_field_count_consistent
        ),
        'step_count_consistent': self.step_count_consistent,
        'sample_resolution_verified': self.sample_resolution_verified,
        'topology_verified': self.topology_verified,
        'geometry_shape_verified': self.geometry_shape_verified,
        'field_euler_audits_verified': self.field_euler_audits_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'termination_sensitivity_verified': (
          self.termination_sensitivity_verified
        ),
        'fidelity_flags_verified': self.fidelity_flags_verified,
        'cell_residual_trend_verified': self.cell_residual_trend_verified,
        'refinement_convergence_verified': self.refinement_convergence_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'residuals': {
        'maximum_cell_euler_residuals': list(
          self.maximum_cell_euler_residuals
        ),
        'axial_extent_residuals_m': list(self.axial_extent_residuals_m),
        'shock_endpoint_residuals_m': list(self.shock_endpoint_residuals_m),
        'companion_endpoint_residuals_m': list(
          self.companion_endpoint_residuals_m
        ),
        'interior_endpoint_residuals_m': list(
          self.interior_endpoint_residuals_m
        ),
      },
      'declared_tolerances': {
        'endpoint_tolerance_m': self.endpoint_tolerance_m,
        'cell_residual_tolerance': self.cell_residual_tolerance,
        'cell_residual_trend_tolerance': self.cell_residual_trend_tolerance,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####
####


def _euler_companion_field_chain_refinement_failure(
  status: MocEulerCompanionFieldChainRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocEulerCompanionFieldChainRefinementCase] = (),
  chain_audits: Sequence[MocEulerCompanionFieldChainAudit] = (),
  expected_resolutions: Sequence[int] = (),
  field_count: int | None = None,
  continued_field_count: int | None = None,
  expected_resolutions_verified: bool = False,
  resolution_order_verified: bool = False,
  field_count_consistent: bool = False,
  continued_field_count_consistent: bool = False,
  step_count_consistent: bool = False,
  sample_resolution_verified: bool = False,
  topology_verified: bool = False,
  geometry_shape_verified: bool = False,
  field_euler_audits_verified: bool = False,
  handoff_links_verified: bool | None = None,
  termination_sensitivity_verified: bool | None = None,
  fidelity_flags_verified: bool = False,
  cell_residual_trend_verified: bool = False,
  refinement_convergence_verified: bool = False,
  field_node_counts: Sequence[Sequence[int]] = (),
  field_cell_counts: Sequence[Sequence[int]] = (),
  maximum_cell_euler_residuals: Sequence[float] = (),
  axial_extent_residuals_m: Sequence[float] = (),
  shock_endpoint_residuals_m: Sequence[float] = (),
  companion_endpoint_residuals_m: Sequence[float] = (),
  interior_endpoint_residuals_m: Sequence[float] = (),
  endpoint_tolerance_m: float = 1.0e-10,
  cell_residual_tolerance: float = 1.0e-2,
  cell_residual_trend_tolerance: float = 1.0e-12,
) -> MocEulerCompanionFieldChainRefinementMeasurement:
  valid_cases = tuple(
    case
    for case in cases
    if isinstance(case, MocEulerCompanionFieldChainRefinementCase)
  )
  valid_audits = tuple(
    audit
    for audit in chain_audits
    if isinstance(audit, MocEulerCompanionFieldChainAudit)
  )
  paired_count = min(len(valid_cases), len(valid_audits))
  return MocEulerCompanionFieldChainRefinementMeasurement(
    status=status,
    cases=valid_cases[:paired_count],
    chain_audits=valid_audits[:paired_count],
    expected_resolutions=tuple(expected_resolutions),
    field_count=field_count,
    continued_field_count=continued_field_count,
    expected_resolutions_verified=expected_resolutions_verified,
    resolution_order_verified=resolution_order_verified,
    field_count_consistent=field_count_consistent,
    continued_field_count_consistent=continued_field_count_consistent,
    step_count_consistent=step_count_consistent,
    sample_resolution_verified=sample_resolution_verified,
    topology_verified=topology_verified,
    geometry_shape_verified=geometry_shape_verified,
    field_euler_audits_verified=field_euler_audits_verified,
    handoff_links_verified=handoff_links_verified,
    termination_sensitivity_verified=termination_sensitivity_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    cell_residual_trend_verified=cell_residual_trend_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    field_node_counts=tuple(tuple(row) for row in field_node_counts),
    field_cell_counts=tuple(tuple(row) for row in field_cell_counts),
    maximum_cell_euler_residuals=tuple(maximum_cell_euler_residuals),
    axial_extent_residuals_m=tuple(axial_extent_residuals_m),
    shock_endpoint_residuals_m=tuple(shock_endpoint_residuals_m),
    companion_endpoint_residuals_m=tuple(companion_endpoint_residuals_m),
    interior_endpoint_residuals_m=tuple(interior_endpoint_residuals_m),
    endpoint_tolerance_m=endpoint_tolerance_m,
    cell_residual_tolerance=cell_residual_tolerance,
    cell_residual_trend_tolerance=cell_residual_trend_tolerance,
    message=message,
  )
####


def _euler_field_endpoint_pair(
  field: Any,
  attribute: str,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
  try:
    points = tuple(getattr(field, attribute))
  except (AttributeError, TypeError):
    return None
  ####
  if len(points) < 2:
    return None
  ####
  try:
    first = (float(points[0][0]), float(points[0][1]))
    last = (float(points[-1][0]), float(points[-1][1]))
  except (IndexError, TypeError, ValueError):
    return None
  ####
  if not all(isfinite(value) for point in (first, last) for value in point):
    return None
  ####
  return first, last
####


def _euler_endpoint_residual(
  previous: tuple[tuple[float, float], tuple[float, float]] | None,
  current: tuple[tuple[float, float], tuple[float, float]] | None,
) -> float:
  if previous is None or current is None:
    return _EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL
  ####
  return max(
    hypot(
      current[index][0] - previous[index][0],
      current[index][1] - previous[index][1],
    )
    for index in (0, 1)
  )
####


def measure_moc_euler_companion_field_chain_refinement(
  cases: Sequence[MocEulerCompanionFieldChainRefinementCase],
  *,
  expected_resolutions: Sequence[int] | None = None,
  endpoint_tolerance_m: float = 1.0e-10,
  cell_residual_tolerance: float = 1.0e-2,
  cell_residual_trend_tolerance: float = 1.0e-12,
  shock_residual_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
) -> MocEulerCompanionFieldChainRefinementMeasurement:
  """Independently compare an open Euler-field chain across resolutions.

  The operator remeasures every retained field and chain trace.  It checks
  that the declared resolution matches all boundary/interior arrays, that
  every field retains an independently verified connected strip topology,
  that corresponding field endpoints remain geometrically stable, that the
  local conservative residual does not worsen, and that exact handoff and
  typed-stop metadata survive refinement.  It never invokes a continuation
  callback or solves a new field.
  """

  tolerance_values = (
    endpoint_tolerance_m,
    cell_residual_tolerance,
    cell_residual_trend_tolerance,
    shock_residual_tolerance,
    position_tolerance_m,
    invariant_tolerance,
    pressure_tolerance,
  )
  if any(
    not isfinite(float(value)) or float(value) <= 0.0
    for value in tolerance_values
  ):
    raise ValueError('Euler chain refinement tolerances must be finite and positive')
  ####
  try:
    items = tuple(cases)
  except TypeError:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  ####
  expected = ()
  if expected_resolutions is not None:
    try:
      expected = tuple(expected_resolutions)
    except TypeError:
      return _euler_companion_field_chain_refinement_failure(
        MocEulerCompanionFieldChainRefinementMeasurementStatus.INVALID_INPUT,
        'expected_resolutions must be iterable',
      )
    ####
    if any(
      isinstance(value, bool)
      or not isinstance(value, int)
      or value < 2
      for value in expected
    ):
      return _euler_companion_field_chain_refinement_failure(
        MocEulerCompanionFieldChainRefinementMeasurementStatus.INVALID_INPUT,
        'expected_resolutions must contain integers of at least two',
        expected_resolutions=expected,
      )
    ####
  ####
  if len(items) < 2:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'at least two Euler companion-field refinement cases are required',
      expected_resolutions=expected,
    )
  ####
  if any(
    not isinstance(case, MocEulerCompanionFieldChainRefinementCase)
    for case in items
  ):
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain '
      'MocEulerCompanionFieldChainRefinementCase values',
      cases=items,
      expected_resolutions=expected,
    )
  ####
  resolutions = tuple(case.resolution for case in items)
  expected_verified = not expected or expected == resolutions
  if not expected_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.RESOLUTION_FAILURE,
      'refinement cases do not match the expected resolution sequence',
      cases=items,
      expected_resolutions=expected,
    )
  ####
  resolution_order_verified = all(
    right > left
    for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing from coarse to fine',
      cases=items,
      expected_resolutions=expected,
      expected_resolutions_verified=True,
    )
  ####

  from exhaust_plume.models.moc.planner import (
    MocEulerCompanionFieldChainPlannerResult,
  )

  if any(
    not isinstance(case.chain, MocEulerCompanionFieldChainPlannerResult)
    for case in items
  ):
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain Euler companion-field chain planner results',
      cases=items,
      expected_resolutions=expected,
      expected_resolutions_verified=True,
      resolution_order_verified=True,
    )
  ####

  chain_audits = tuple(
    measure_moc_euler_companion_field_chain(case.chain)
    for case in items
  )
  if any(
    not audit.converged or not audit.local_sequence_verified
    for audit in chain_audits
  ):
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.CASE_FAILURE,
      'one or more Euler companion-field chains failed independent sequence audit',
      cases=items,
      chain_audits=chain_audits,
      expected_resolutions=expected,
      expected_resolutions_verified=True,
      resolution_order_verified=True,
    )
  ####

  chains = tuple(case.chain for case in items)
  field_counts = tuple(chain.field_count for chain in chains)
  continued_counts = tuple(chain.continued_field_count for chain in chains)
  step_counts = tuple(len(chain.steps) for chain in chains)
  field_count_consistent = len(set(field_counts)) == 1 and field_counts[0] > 0
  continued_field_count_consistent = (
    len(set(continued_counts)) == 1
    and continued_counts[0] >= 0
  )
  step_count_consistent = all(
    step_count == field_count
    for step_count, field_count in zip(step_counts, field_counts, strict=True)
  )
  if not (
    field_count_consistent
    and continued_field_count_consistent
    and step_count_consistent
  ):
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'refinement cases must retain the same field/step sequence shape',
      cases=items,
      chain_audits=chain_audits,
      expected_resolutions=expected,
      field_count=field_counts[0] if field_counts else None,
      continued_field_count=(continued_counts[0] if continued_counts else None),
      expected_resolutions_verified=True,
      resolution_order_verified=True,
      field_count_consistent=field_count_consistent,
      continued_field_count_consistent=continued_field_count_consistent,
      step_count_consistent=step_count_consistent,
    )
  ####

  field_audits = tuple(
    tuple(
      measure_moc_euler_companion_field(
        field,
        shock_residual_tolerance=shock_residual_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
      )
      for field in chain.fields
    )
    for chain in chains
  )
  field_euler_audits_verified = all(
    audit.converged
    and audit.local_euler_consistency_verified
    and audit.field_topology_verified
    for audits in field_audits
    for audit in audits
  )
  field_node_counts = tuple(
    tuple(field.node_count for field in chain.fields)
    for chain in chains
  )
  field_cell_counts = tuple(
    tuple(field.cell_count for field in chain.fields)
    for chain in chains
  )
  sample_resolution_verified = all(
    all(
      len(field.shock_boundary_points_m) == case.resolution
      and len(field.shock_boundary_states) == case.resolution
      and len(field.shock_boundary_total_pressure_Pa) == case.resolution
      and len(field.companion_boundary_points_m) == case.resolution
      and len(field.companion_boundary_states) == case.resolution
      and len(field.companion_boundary_total_pressure_Pa) == case.resolution
      and len(field.interior_points_m) == case.resolution
      and len(field.interior_states) == case.resolution
      and len(field.interior_total_pressure_Pa) == case.resolution
      and len(field.nodes) == case.resolution
      and len(field.cells) == case.resolution - 1
      for field in case.chain.fields
    )
    for case in items
  )
  topology_verified = bool(
    sample_resolution_verified
    and field_euler_audits_verified
    and all(
      field.topology.connected
      and field.topology.forms_closed_zone
      and field.topology.nonmanifold_edge_count == 0
      for chain in chains
      for field in chain.fields
    )
  )

  axial_extent_residuals: list[float] = []
  shock_endpoint_residuals: list[float] = []
  companion_endpoint_residuals: list[float] = []
  interior_endpoint_residuals: list[float] = []
  geometry_shape_verified = True
  for previous, current in zip(chains, chains[1:]):
    if previous.field_count != current.field_count:
      geometry_shape_verified = False
      axial_extent_residuals.append(_EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL)
      shock_endpoint_residuals.append(_EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL)
      companion_endpoint_residuals.append(
        _EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL
      )
      interior_endpoint_residuals.append(
        _EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL
      )
      continue
    ####
    extent_residual = 0.0
    shock_residual = 0.0
    companion_residual = 0.0
    interior_residual = 0.0
    for previous_field, current_field in zip(
      previous.fields,
      current.fields,
      strict=True,
    ):
      previous_extent = _euler_chain_field_x_extent(previous_field)
      current_extent = _euler_chain_field_x_extent(current_field)
      if previous_extent is None or current_extent is None:
        extent_residual = _EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL
      else:
        extent_residual = max(
          extent_residual,
          abs(current_extent[0] - previous_extent[0]),
          abs(current_extent[1] - previous_extent[1]),
        )
      ####
      shock_residual = max(
        shock_residual,
        _euler_endpoint_residual(
          _euler_field_endpoint_pair(
            previous_field,
            'shock_boundary_points_m',
          ),
          _euler_field_endpoint_pair(current_field, 'shock_boundary_points_m'),
        ),
      )
      companion_residual = max(
        companion_residual,
        _euler_endpoint_residual(
          _euler_field_endpoint_pair(
            previous_field,
            'companion_boundary_points_m',
          ),
          _euler_field_endpoint_pair(
            current_field,
            'companion_boundary_points_m',
          ),
        ),
      )
      interior_residual = max(
        interior_residual,
        _euler_endpoint_residual(
          _euler_field_endpoint_pair(previous_field, 'interior_points_m'),
          _euler_field_endpoint_pair(current_field, 'interior_points_m'),
        ),
      )
    ####
    axial_extent_residuals.append(extent_residual)
    shock_endpoint_residuals.append(shock_residual)
    companion_endpoint_residuals.append(companion_residual)
    interior_endpoint_residuals.append(interior_residual)
  ####
  geometry_shape_verified = bool(
    geometry_shape_verified
    and all(
      residual <= float(endpoint_tolerance_m)
      for residual in (
        *axial_extent_residuals,
        *shock_endpoint_residuals,
        *companion_endpoint_residuals,
        *interior_endpoint_residuals,
      )
    )
  )

  maximum_cell_euler_residuals = tuple(
    max(
      (
        audit.maximum_cell_euler_residual or 0.0
        for audit in audits_for_case
      ),
      default=_EULER_CHAIN_REFINEMENT_FAILURE_RESIDUAL,
    )
    for audits_for_case in field_audits
  )
  cell_residual_trend_verified = bool(
    all(
      current <= previous + float(cell_residual_trend_tolerance)
      for previous, current in zip(
        maximum_cell_euler_residuals,
        maximum_cell_euler_residuals[1:],
      )
    )
    and all(
      residual <= float(cell_residual_tolerance)
      for residual in maximum_cell_euler_residuals
    )
  )
  handoff_links_verified = all(
    audit.handoff_links_verified is True
    for audit in chain_audits
  )
  termination_values = tuple(
    (
      chain.termination.reason.value,
      chain.termination.physical_termination,
    )
    for chain in chains
  )
  termination_sensitivity_verified = bool(
    len(set(termination_values)) == 1
    and all(not physical for _, physical in termination_values)
  )
  fidelity_flags_verified = all(
    not chain.physical_closure_verified
    and chain.chain_promotion_blocked
    and not chain.production_claim_allowed
    and audit.fidelity_flags_verified
    and all(
      not field.physical_closure_verified
      and field.chain_promotion_blocked
      and not field.production_claim_allowed
      for field in chain.fields
    )
    for chain, audit in zip(chains, chain_audits, strict=True)
  )
  refinement_convergence_verified = bool(
    expected_verified
    and resolution_order_verified
    and field_count_consistent
    and continued_field_count_consistent
    and step_count_consistent
    and sample_resolution_verified
    and topology_verified
    and geometry_shape_verified
    and field_euler_audits_verified
    and handoff_links_verified
    and termination_sensitivity_verified
    and fidelity_flags_verified
    and cell_residual_trend_verified
  )

  common = {
    'cases': items,
    'chain_audits': chain_audits,
    'expected_resolutions': expected,
    'field_count': field_counts[0],
    'continued_field_count': continued_counts[0],
    'expected_resolutions_verified': True,
    'resolution_order_verified': True,
    'field_count_consistent': field_count_consistent,
    'continued_field_count_consistent': continued_field_count_consistent,
    'step_count_consistent': step_count_consistent,
    'sample_resolution_verified': sample_resolution_verified,
    'topology_verified': topology_verified,
    'geometry_shape_verified': geometry_shape_verified,
    'field_euler_audits_verified': field_euler_audits_verified,
    'handoff_links_verified': handoff_links_verified,
    'termination_sensitivity_verified': termination_sensitivity_verified,
    'fidelity_flags_verified': fidelity_flags_verified,
    'cell_residual_trend_verified': cell_residual_trend_verified,
    'refinement_convergence_verified': refinement_convergence_verified,
    'field_node_counts': field_node_counts,
    'field_cell_counts': field_cell_counts,
    'maximum_cell_euler_residuals': maximum_cell_euler_residuals,
    'axial_extent_residuals_m': axial_extent_residuals,
    'shock_endpoint_residuals_m': shock_endpoint_residuals,
    'companion_endpoint_residuals_m': companion_endpoint_residuals,
    'interior_endpoint_residuals_m': interior_endpoint_residuals,
    'endpoint_tolerance_m': endpoint_tolerance_m,
    'cell_residual_tolerance': cell_residual_tolerance,
    'cell_residual_trend_tolerance': cell_residual_trend_tolerance,
  }
  if not field_euler_audits_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.CASE_FAILURE,
      'one or more retained fields failed independent Euler remeasurement',
      **common,
    )
  ####
  if not sample_resolution_verified or not topology_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.TOPOLOGY_FAILURE,
      'refinement cases failed independent resolution or topology checks',
      **common,
    )
  ####
  if not geometry_shape_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.GEOMETRY_FAILURE,
      'corresponding open-field boundary endpoints changed beyond tolerance',
      **common,
    )
  ####
  if not cell_residual_trend_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.SENSITIVITY_FAILURE,
      'open-field conservative residuals did not remain bounded or non-increasing',
      **common,
    )
  ####
  if not handoff_links_verified or not termination_sensitivity_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.TERMINATION_FAILURE,
      'handoff or typed termination metadata changed across refinement',
      **common,
    )
  ####
  if not fidelity_flags_verified:
    return _euler_companion_field_chain_refinement_failure(
      MocEulerCompanionFieldChainRefinementMeasurementStatus.FIDELITY_FAILURE,
      'refinement sequence weakened its open-field fidelity boundary',
      **common,
    )
  ####
  return MocEulerCompanionFieldChainRefinementMeasurement(
    status=MocEulerCompanionFieldChainRefinementMeasurementStatus.CONVERGED,
    **common,
    claim_status=(
      'independent-open-euler-companion-field-chain-refinement; '
      'reflected-free-boundary, entropy closure, and external validation remain pending'
    ),
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent Euler companion-field chain refinement verified retained '
      'resolution/topology shape, stable endpoints, bounded decreasing cell '
      'residuals, exact frontier links, and a typed non-physical stop; '
      'physical reflected closure remains pending'
    ),
  )
####


class MocEulerAmbientShockFieldAuditStatus(str, Enum):
  """Outcome of independently auditing the exact ambient shock-field lane."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_ambient_shock_field_audit'
  INVALID_INPUT = 'invalid_input'
  SHOCK_JUMP_FAILURE = 'euler_ambient_shock_field_audit_shock_failure'
  AMBIENT_BOUNDARY_FAILURE = 'euler_ambient_shock_field_audit_ambient_failure'
  ENTROPY_FAILURE = 'euler_ambient_shock_field_audit_entropy_failure'
  FIELD_FAILURE = 'euler_ambient_shock_field_audit_field_failure'
  FLAG_FAILURE = 'euler_ambient_shock_field_audit_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldAudit:
  """Independent evidence for an exact shock-to-ambient field candidate.

  The audit deliberately distinguishes the converged ambient boundary from
  the downstream characteristic strip.  A solver result may therefore carry
  a passing shock and ambient march while this audit still reports
  ``FIELD_FAILURE`` because the shared attachment has not been remeshed into
  a valid first interior wedge.
  """

  status: MocEulerAmbientShockFieldAuditStatus
  field_status: str | None
  shock_sample_count: int
  ambient_sample_count: int
  cell_count: int
  shock_jump_mass_residuals: tuple[float, ...]
  shock_jump_momentum_residuals: tuple[float, ...]
  shock_jump_energy_residuals: tuple[float, ...]
  ambient_pressure_residuals: tuple[float, ...]
  ambient_tangent_residuals: tuple[float, ...]
  incoming_k_plus_residuals: tuple[float, ...]
  entropy_residuals: tuple[float, ...]
  maximum_shock_jump_mass_residual: float | None
  maximum_shock_jump_momentum_residual: float | None
  maximum_shock_jump_energy_residual: float | None
  maximum_ambient_pressure_residual: float | None
  maximum_ambient_tangent_residual: float | None
  maximum_incoming_k_plus_residual: float | None
  maximum_entropy_residual: float | None
  attachment_relative_pressure_residual: float | None
  shock_geometry_verified: bool
  shock_jump_verified: bool
  ambient_sample_alignment_verified: bool
  ambient_direction_verified: bool
  ambient_boundary_verified: bool
  entropy_lineage_verified: bool
  companion_field_verified: bool
  promotion_flags_verified: bool
  shock_residual_tolerance: float
  cell_residual_tolerance: float
  position_tolerance_m: float
  invariant_tolerance: float
  pressure_tolerance: float
  tangent_tolerance: float
  ambient_boundary_kind: str = 'shock-sourced-march'
  ambient_companion_invariant_residuals: tuple[float, ...] = ()
  maximum_ambient_companion_invariant_residual: float | None = None
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_SHOCK_FIELD_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientShockFieldAuditStatus):
      raise TypeError(
        'status must be a MocEulerAmbientShockFieldAuditStatus'
      )
    ####
    for name in ('shock_sample_count', 'ambient_sample_count', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'shock_residual_tolerance',
      'cell_residual_tolerance',
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'shock_jump_mass_residuals',
      'shock_jump_momentum_residuals',
      'shock_jump_energy_residuals',
      'ambient_pressure_residuals',
      'ambient_tangent_residuals',
      'incoming_k_plus_residuals',
      'entropy_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_ambient_pressure_residual',
      'maximum_ambient_tangent_residual',
      'maximum_incoming_k_plus_residual',
      'maximum_entropy_residual',
      'attachment_relative_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    companion_residuals = tuple(
      float(value) for value in self.ambient_companion_invariant_residuals
    )
    if any(
      not isfinite(value) or value < 0.0 for value in companion_residuals
    ):
      raise ValueError(
        'ambient_companion_invariant_residuals must contain finite '
        'nonnegative values'
      )
    ####
    object.__setattr__(
      self,
      'ambient_companion_invariant_residuals',
      companion_residuals,
    )
    if self.maximum_ambient_companion_invariant_residual is not None:
      companion_maximum = float(self.maximum_ambient_companion_invariant_residual)
      if not isfinite(companion_maximum) or companion_maximum < 0.0:
        raise ValueError(
          'maximum_ambient_companion_invariant_residual must be finite and '
          'nonnegative when supplied'
        )
      ####
      object.__setattr__(
        self,
        'maximum_ambient_companion_invariant_residual',
        companion_maximum,
      )
    ####
    for name in (
      'shock_geometry_verified',
      'shock_jump_verified',
      'ambient_sample_alignment_verified',
      'ambient_direction_verified',
      'ambient_boundary_verified',
      'entropy_lineage_verified',
      'companion_field_verified',
      'promotion_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.field_status is not None:
      object.__setattr__(self, 'field_status', str(self.field_status))
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    boundary_kind = str(self.ambient_boundary_kind)
    if not boundary_kind:
      raise ValueError('ambient_boundary_kind must be a non-empty string')
    ####
    object.__setattr__(self, 'ambient_boundary_kind', boundary_kind)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerAmbientShockFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock_geometry_verified
      and self.shock_jump_verified
      and self.ambient_sample_alignment_verified
      and self.ambient_direction_verified
      and self.ambient_boundary_verified
      and self.entropy_lineage_verified
      and self.companion_field_verified
      and self.promotion_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'field_status': self.field_status,
      'shock_sample_count': self.shock_sample_count,
      'ambient_sample_count': self.ambient_sample_count,
      'cell_count': self.cell_count,
      'shock_jump_mass_residuals': list(self.shock_jump_mass_residuals),
      'shock_jump_momentum_residuals': list(self.shock_jump_momentum_residuals),
      'shock_jump_energy_residuals': list(self.shock_jump_energy_residuals),
      'ambient_pressure_residuals': list(self.ambient_pressure_residuals),
      'ambient_tangent_residuals': list(self.ambient_tangent_residuals),
      'ambient_boundary_kind': self.ambient_boundary_kind,
      'ambient_companion_invariant_residuals': list(
        self.ambient_companion_invariant_residuals
      ),
      'incoming_k_plus_residuals': list(self.incoming_k_plus_residuals),
      'entropy_residuals': list(self.entropy_residuals),
      'maximum_shock_jump_mass_residual': (
        self.maximum_shock_jump_mass_residual
      ),
      'maximum_shock_jump_momentum_residual': (
        self.maximum_shock_jump_momentum_residual
      ),
      'maximum_shock_jump_energy_residual': (
        self.maximum_shock_jump_energy_residual
      ),
      'maximum_ambient_pressure_residual': (
        self.maximum_ambient_pressure_residual
      ),
      'maximum_ambient_tangent_residual': (
        self.maximum_ambient_tangent_residual
      ),
      'maximum_incoming_k_plus_residual': (
        self.maximum_incoming_k_plus_residual
      ),
      'maximum_ambient_companion_invariant_residual': (
        self.maximum_ambient_companion_invariant_residual
      ),
      'maximum_entropy_residual': self.maximum_entropy_residual,
      'attachment_relative_pressure_residual': (
        self.attachment_relative_pressure_residual
      ),
      'checks': {
        'shock_geometry_verified': self.shock_geometry_verified,
        'shock_jump_verified': self.shock_jump_verified,
        'ambient_sample_alignment_verified': (
          self.ambient_sample_alignment_verified
        ),
        'ambient_direction_verified': self.ambient_direction_verified,
        'ambient_boundary_verified': self.ambient_boundary_verified,
        'entropy_lineage_verified': self.entropy_lineage_verified,
        'companion_field_verified': self.companion_field_verified,
        'promotion_flags_verified': self.promotion_flags_verified,
        'local_consistency_verified': self.local_consistency_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'tolerances': {
        'shock_residual_tolerance': self.shock_residual_tolerance,
        'cell_residual_tolerance': self.cell_residual_tolerance,
        'position_tolerance_m': self.position_tolerance_m,
        'invariant_tolerance': self.invariant_tolerance,
        'pressure_tolerance': self.pressure_tolerance,
        'tangent_tolerance': self.tangent_tolerance,
      },
      'canonical_euler_verified': False,
      'canonical_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-exact-euler-ambient-shock-field-audit; attachment-aware '
        'remesh, reflected closure, chain continuation, and external validation '
        'remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _ambient_shock_field_audit_failure(
  status: MocEulerAmbientShockFieldAuditStatus,
  message: str,
  *,
  field_status: str | None = None,
  shock_sample_count: int = 0,
  ambient_sample_count: int = 0,
  cell_count: int = 0,
  shock_jump_mass_residuals: Sequence[float] = (),
  shock_jump_momentum_residuals: Sequence[float] = (),
  shock_jump_energy_residuals: Sequence[float] = (),
  ambient_pressure_residuals: Sequence[float] = (),
  ambient_tangent_residuals: Sequence[float] = (),
  incoming_k_plus_residuals: Sequence[float] = (),
  entropy_residuals: Sequence[float] = (),
  attachment_relative_pressure_residual: float | None = None,
  shock_geometry_verified: bool = False,
  shock_jump_verified: bool = False,
  ambient_sample_alignment_verified: bool = False,
  ambient_direction_verified: bool = False,
  ambient_boundary_verified: bool = False,
  entropy_lineage_verified: bool = False,
  companion_field_verified: bool = False,
  promotion_flags_verified: bool = False,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  ambient_boundary_kind: str = 'shock-sourced-march',
  ambient_companion_invariant_residuals: Sequence[float] = (),
  maximum_ambient_companion_invariant_residual: float | None = None,
) -> MocEulerAmbientShockFieldAudit:
  values = (
    tuple(float(value) for value in shock_jump_mass_residuals),
    tuple(float(value) for value in shock_jump_momentum_residuals),
    tuple(float(value) for value in shock_jump_energy_residuals),
    tuple(float(value) for value in ambient_pressure_residuals),
    tuple(float(value) for value in ambient_tangent_residuals),
    tuple(float(value) for value in incoming_k_plus_residuals),
    tuple(float(value) for value in entropy_residuals),
  )
  maxima = tuple(max(item, default=None) for item in values)
  return MocEulerAmbientShockFieldAudit(
    status=status,
    field_status=field_status,
    shock_sample_count=shock_sample_count,
    ambient_sample_count=ambient_sample_count,
    cell_count=cell_count,
    shock_jump_mass_residuals=values[0],
    shock_jump_momentum_residuals=values[1],
    shock_jump_energy_residuals=values[2],
    ambient_pressure_residuals=values[3],
    ambient_tangent_residuals=values[4],
    incoming_k_plus_residuals=values[5],
    entropy_residuals=values[6],
    maximum_shock_jump_mass_residual=maxima[0],
    maximum_shock_jump_momentum_residual=maxima[1],
    maximum_shock_jump_energy_residual=maxima[2],
    maximum_ambient_pressure_residual=maxima[3],
    maximum_ambient_tangent_residual=maxima[4],
    maximum_incoming_k_plus_residual=maxima[5],
    maximum_entropy_residual=maxima[6],
    ambient_boundary_kind=ambient_boundary_kind,
    ambient_companion_invariant_residuals=(
      tuple(float(value) for value in ambient_companion_invariant_residuals)
    ),
    maximum_ambient_companion_invariant_residual=(
      maximum_ambient_companion_invariant_residual
    ),
    attachment_relative_pressure_residual=attachment_relative_pressure_residual,
    shock_geometry_verified=shock_geometry_verified,
    shock_jump_verified=shock_jump_verified,
    ambient_sample_alignment_verified=ambient_sample_alignment_verified,
    ambient_direction_verified=ambient_direction_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    companion_field_verified=companion_field_verified,
    promotion_flags_verified=promotion_flags_verified,
    shock_residual_tolerance=shock_residual_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    message=message,
  )
####


def measure_moc_euler_ambient_shock_field(
  field: MocEulerAmbientShockFieldResult,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocEulerAmbientShockFieldAudit:
  """Reconstruct exact shock, ambient, entropy, and field evidence.

  This operator only measures retained states and geometry.  It does not
  rerun the shock or ambient solver.  The nested companion-strip audit is
  likewise a measurement of the retained open field, not a continuation call.
  """

  if not isinstance(field, MocEulerAmbientShockFieldResult):
    return _ambient_shock_field_audit_failure(
      MocEulerAmbientShockFieldAuditStatus.INVALID_INPUT,
      'field must be a MocEulerAmbientShockFieldResult',
    )
  ####
  try:
    shock_tolerance = float(shock_residual_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
    tangent_tolerance_value = float(tangent_tolerance)
  except (TypeError, ValueError):
    return _ambient_shock_field_audit_failure(
      MocEulerAmbientShockFieldAuditStatus.INVALID_INPUT,
      'ambient shock-field audit tolerances must be numeric',
      field_status=field.status.value,
    )
  ####
  tolerances = (
    shock_tolerance,
    cell_tolerance,
    position_tolerance,
    invariant_tolerance_value,
    pressure_tolerance_value,
    tangent_tolerance_value,
  )
  if any(not isfinite(value) or value <= 0.0 for value in tolerances):
    raise ValueError(
      'ambient shock-field audit tolerances must be finite and positive'
    )
  ####

  shock = field.shock_boundary
  march = field.ambient_march
  shock_status = field.status.value
  if shock is None or not shock.converged or not shock.local_euler_verified:
    return _ambient_shock_field_audit_failure(
      MocEulerAmbientShockFieldAuditStatus.SHOCK_JUMP_FAILURE,
      'ambient shock-field audit requires a converged locally Euler-verified shock curve',
      field_status=shock_status,
      shock_sample_count=0 if shock is None else len(shock.shock_points_m),
      cell_count=0 if field.field is None else field.field.cell_count,
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      tangent_tolerance=tangent_tolerance_value,
    )
  ####

  shock_points = tuple(shock.shock_points_m)
  shock_count = len(shock_points)
  shock_geometry_verified = bool(
    shock_count >= 2
    and len(shock.upstream_states) == shock_count
    and len(shock.upstream_total_pressure_Pa) == shock_count
    and len(shock.downstream_states) == shock_count
    and len(shock.downstream_total_pressure_Pa) == shock_count
    and all(
      len(point) == 2 and all(isfinite(float(value)) for value in point)
      for point in shock_points
    )
    and all(
      abs(state.x_m - point[0]) <= position_tolerance
      and abs(state.y_m - point[1]) <= position_tolerance
      for state, point in zip(shock.downstream_states, shock_points, strict=True)
    )
    and all(
      shock_points[index + 1][0] > shock_points[index][0] + position_tolerance
      for index in range(shock_count - 1)
    )
    and shock.orientation is MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
  )
  jump_mass: list[float] = []
  jump_momentum: list[float] = []
  jump_energy: list[float] = []
  if shock_geometry_verified:
    try:
      for index in range(shock_count):
        mass, momentum, energy = _shock_jump_residuals(
          shock.upstream_states[index],
          shock.upstream_total_pressure_Pa[index],
          shock.downstream_states[index],
          shock.downstream_total_pressure_Pa[index],
          _shock_tangent(shock_points, index),
        )
        jump_mass.append(mass)
        jump_momentum.append(momentum)
        jump_energy.append(energy)
      ####
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      shock_geometry_verified = False
    ####
  ####
  maximum_shock_residual = max(
    (*jump_mass, *jump_momentum, *jump_energy),
    default=None,
  )
  shock_jump_verified = bool(
    shock_geometry_verified
    and maximum_shock_residual is not None
    and maximum_shock_residual <= shock_tolerance
  )

  ambient_pressure_residuals: list[float] = []
  ambient_tangent_residuals: list[float] = []
  incoming_k_plus_residuals: list[float] = []
  ambient_companion_invariant_residuals: list[float] = []
  attachment_residual: float | None = None
  ambient_sample_alignment_verified = False
  ambient_direction_verified = False
  ambient_boundary_verified = False
  ambient_count = 0
  ambient_pressure = field.ambient_pressure_Pa
  ambient_boundary_kind = 'shock-sourced-march'
  companion_invariant_maximum: float | None = None
  if isinstance(march, MocEulerAmbientBoundaryMarchResult):
    samples = tuple(march.boundary_samples)
    ambient_count = len(samples)
    sample_states = tuple(sample.state for sample in samples)
    ambient_sample_alignment_verified = bool(
      march.converged
      and ambient_pressure is not None
      and march.ambient_pressure_Pa is not None
      and abs(march.ambient_pressure_Pa - ambient_pressure)
      <= pressure_tolerance_value * max(1.0, abs(ambient_pressure))
      and ambient_count == shock_count
      and len(march.point_results) == ambient_count
      and len(march.incoming_k_plus_residuals) == ambient_count
      and len(march.ambient_boundary.points_m) == ambient_count
      and len(march.ambient_boundary.states) == ambient_count
      and all(
        abs(state.x_m - point[0]) <= position_tolerance
        and abs(state.y_m - point[1]) <= position_tolerance
        for state, point in zip(sample_states, march.points_m, strict=True)
      )
      and all(
        abs(point[axis] - reference[axis]) <= position_tolerance
        for point, reference in zip(
          march.ambient_boundary.points_m,
          march.points_m,
          strict=True,
        )
        for axis in (0, 1)
      )
      and all(
        abs(state.x_m - point[0]) <= position_tolerance
        and abs(state.y_m - point[1]) <= position_tolerance
        for state, point in zip(
          march.ambient_boundary.states,
          march.points_m,
          strict=True,
        )
      )
      and abs(samples[0].point_m[0] - shock_points[0][0])
      <= position_tolerance
      and abs(samples[0].point_m[1] - shock_points[0][1])
      <= position_tolerance
    ) if ambient_count and shock_count else False
    if ambient_count == shock_count and shock_count:
      try:
        for index, sample in enumerate(samples):
          state = sample.state
          pressure_ratio = (
            1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
          ) ** (state.gamma / (state.gamma - 1.0))
          static_pressure = sample.total_pressure_Pa / pressure_ratio
          if ambient_pressure is None or ambient_pressure <= 0.0:
            raise ValueError('ambient pressure is missing or non-positive')
          ####
          ambient_pressure_residuals.append(
            abs(static_pressure - ambient_pressure) / ambient_pressure
          )
          incoming_k_plus_residuals.append(
            abs(state.k_plus - shock.downstream_states[index].k_plus)
          )
        ####
        for first, second in zip(samples, samples[1:]):
          dx = second.point_m[0] - first.point_m[0]
          dy = second.point_m[1] - first.point_m[1]
          length = hypot(dx, dy)
          if not isfinite(length) or length <= 0.0:
            raise ValueError('ambient boundary contains a zero-length segment')
          ####
          segment_angle = atan2(dy, dx)
          flow_angle = 0.5 * (
            first.state.theta_rad + second.state.theta_rad
          )
          ambient_tangent_residuals.append(
            abs(sin(segment_angle - flow_angle))
          )
        ####
        attachment_residual = ambient_pressure_residuals[0]
        ambient_direction_verified = bool(
          all(
            second.point_m[0] > first.point_m[0] + position_tolerance
            for first, second in zip(samples, samples[1:])
          )
          and all(
            (second.point_m[0] - first.point_m[0])
            * cos(0.5 * (first.state.theta_rad + second.state.theta_rad))
            + (second.point_m[1] - first.point_m[1])
            * sin(0.5 * (first.state.theta_rad + second.state.theta_rad))
            > 0.0
            for first, second in zip(samples, samples[1:])
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        ambient_sample_alignment_verified = False
      ####
    ####
    ambient_pressure_maximum = max(ambient_pressure_residuals, default=None)
    ambient_tangent_maximum = max(ambient_tangent_residuals, default=None)
    incoming_k_plus_maximum = max(incoming_k_plus_residuals, default=None)
    march_invariant_evidence = bool(
      len(march.incoming_k_plus_residuals) == len(incoming_k_plus_residuals)
      and all(
        abs(declared - reconstructed) <= invariant_tolerance_value
        for declared, reconstructed in zip(
          march.incoming_k_plus_residuals,
          incoming_k_plus_residuals,
          strict=True,
        )
      )
    )
    ambient_boundary_verified = bool(
      ambient_sample_alignment_verified
      and ambient_pressure_maximum is not None
      and ambient_pressure_maximum <= pressure_tolerance_value
      and (
        not ambient_tangent_residuals
        or (
          ambient_tangent_maximum is not None
          and ambient_tangent_maximum <= tangent_tolerance_value
        )
      )
      and incoming_k_plus_maximum is not None
      and incoming_k_plus_maximum <= invariant_tolerance_value
      and march.ambient_boundary.converged
      and march_invariant_evidence
    )
  elif isinstance(
    field.ambient_companion_boundary,
    MocEulerAmbientCompanionBoundaryResult,
  ):
    ambient_boundary_kind = 'explicit-separated-companion'
    companion = field.ambient_companion_boundary
    samples = tuple(companion.samples)
    ambient_count = len(samples)
    ambient_sample_alignment_verified = bool(
      companion.converged
      and companion.state_sampling_available
      and companion.shock_boundary is shock
      and ambient_pressure is not None
      and companion.ambient_pressure_Pa is not None
      and abs(companion.ambient_pressure_Pa - ambient_pressure)
      <= pressure_tolerance_value * max(1.0, abs(ambient_pressure))
      and ambient_count == shock_count
      and len(companion.static_pressure_residuals) == ambient_count
      and len(companion.companion_invariant_residuals) == ambient_count
      and len(companion.geometry_residuals_m) == ambient_count
      and all(
        abs(sample.point_m[0] - shock_points[index][0]) <= position_tolerance
        and sample.point_m[1] > shock_points[index][1] + position_tolerance
        for index, sample in enumerate(samples)
      )
    ) if ambient_count and shock_count else False
    if ambient_count == shock_count and shock_count:
      try:
        seed_k_minus = companion.seed_k_minus_rad
        if seed_k_minus is None:
          raise ValueError('explicit companion boundary is missing seed K-')
        ####
        for sample in samples:
          state = sample.state
          pressure_ratio = (
            1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
          ) ** (state.gamma / (state.gamma - 1.0))
          static_pressure = sample.total_pressure_Pa / pressure_ratio
          if ambient_pressure is None or ambient_pressure <= 0.0:
            raise ValueError('ambient pressure is missing or non-positive')
          ####
          ambient_pressure_residuals.append(
            abs(static_pressure - ambient_pressure) / ambient_pressure
          )
          ambient_companion_invariant_residuals.append(
            abs(state.k_minus - seed_k_minus)
          )
        ####
        for first, second in zip(samples, samples[1:]):
          dx = second.point_m[0] - first.point_m[0]
          dy = second.point_m[1] - first.point_m[1]
          length = hypot(dx, dy)
          if not isfinite(length) or length <= 0.0:
            raise ValueError('explicit companion boundary contains a zero-length segment')
          ####
          segment_angle = atan2(dy, dx)
          flow_angle = 0.5 * (
            first.state.theta_rad + second.state.theta_rad
          )
          ambient_tangent_residuals.append(
            abs(sin(segment_angle - flow_angle))
          )
        ####
        ambient_direction_verified = bool(
          all(
            second.point_m[0] > first.point_m[0] + position_tolerance
            for first, second in zip(samples, samples[1:])
          )
          and all(
            (second.point_m[0] - first.point_m[0])
            * cos(0.5 * (first.state.theta_rad + second.state.theta_rad))
            + (second.point_m[1] - first.point_m[1])
            * sin(0.5 * (first.state.theta_rad + second.state.theta_rad))
            > 0.0
            for first, second in zip(samples, samples[1:])
          )
          and all(
            sample.point_m[1] > shock_points[index][1] + position_tolerance
            for index, sample in enumerate(samples)
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        ambient_sample_alignment_verified = False
      ####
    ####
    ambient_pressure_maximum = max(ambient_pressure_residuals, default=None)
    ambient_tangent_maximum = max(ambient_tangent_residuals, default=None)
    incoming_k_plus_maximum = None
    companion_invariant_maximum = max(
      ambient_companion_invariant_residuals,
      default=None,
    )
    companion_invariant_evidence = bool(
      len(companion.companion_invariant_residuals)
      == len(ambient_companion_invariant_residuals)
      and all(
        abs(declared - reconstructed) <= invariant_tolerance_value
        for declared, reconstructed in zip(
          companion.companion_invariant_residuals,
          ambient_companion_invariant_residuals,
          strict=True,
        )
      )
    )
    ambient_boundary_verified = bool(
      ambient_sample_alignment_verified
      and ambient_pressure_maximum is not None
      and ambient_pressure_maximum <= pressure_tolerance_value
      and (
        not ambient_tangent_residuals
        or (
          ambient_tangent_maximum is not None
          and ambient_tangent_maximum <= tangent_tolerance_value
        )
      )
      and companion_invariant_maximum is not None
      and companion_invariant_maximum <= invariant_tolerance_value
      and companion_invariant_evidence
    )
  else:
    ambient_pressure_maximum = None
    ambient_tangent_maximum = None
    incoming_k_plus_maximum = None
    companion_invariant_maximum = None
  ####

  entropy_residuals: list[float] = []
  entropy_lineage_verified = False
  if shock_geometry_verified and shock_count:
    baseline_pressure = shock.downstream_total_pressure_Pa[0]
    if isfinite(baseline_pressure) and baseline_pressure > 0.0:
      entropy_residuals = [
        abs(pressure - baseline_pressure) / baseline_pressure
        for pressure in shock.downstream_total_pressure_Pa
      ]
      retained_entropy = tuple(field.entropy_residuals)
      entropy_lineage_verified = bool(
        max(entropy_residuals, default=float('inf'))
        <= pressure_tolerance_value
        and len(retained_entropy) == shock_count
        and all(
          abs(declared - reconstructed)
          <= pressure_tolerance_value * max(1.0, reconstructed)
          for declared, reconstructed in zip(
            retained_entropy,
            entropy_residuals,
            strict=True,
          )
        )
        and field.entropy_lineage_verified
      )
    ####
  ####

  companion_field_verified = False
  if field.field is not None:
    companion_audit = measure_moc_euler_companion_field(
      field.field,
      shock_residual_tolerance=shock_tolerance,
      cell_residual_tolerance=cell_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
    )
    companion_field_verified = bool(
      companion_audit.converged
      and companion_audit.local_euler_consistency_verified
    )
  ####
  promotion_flags_verified = bool(
    shock.physical_closure_verified is False
    and shock.chain_promotion_blocked
    and shock.production_claim_allowed is False
    and (
      march is None
      or (
        march.physical_closure_verified is False
        and march.chain_promotion_blocked
        and march.production_claim_allowed is False
      )
    )
    and (
      field.ambient_companion_boundary is None
      or (
        field.ambient_companion_boundary.physical_closure_verified is False
        and field.ambient_companion_boundary.chain_promotion_blocked
        and field.ambient_companion_boundary.production_claim_allowed is False
      )
    )
    and field.physical_closure_verified is False
    and field.chain_promotion_blocked
    and field.production_claim_allowed is False
    and (
      field.field is None
      or (
        field.field.physical_closure_verified is False
        and field.field.chain_promotion_blocked
        and field.field.production_claim_allowed is False
      )
    )
  )

  if not shock_geometry_verified or not shock_jump_verified:
    status = MocEulerAmbientShockFieldAuditStatus.SHOCK_JUMP_FAILURE
    message = 'exact shock geometry or Rankine--Hugoniot residual failed independent audit'
  elif not ambient_boundary_verified:
    status = MocEulerAmbientShockFieldAuditStatus.AMBIENT_BOUNDARY_FAILURE
    message = (
      'solver-owned ambient boundary failed independent pressure, tangent, '
      'direction, or shock-sourced C+ checks'
    )
  elif not entropy_lineage_verified:
    status = MocEulerAmbientShockFieldAuditStatus.ENTROPY_FAILURE
    message = (
      'downstream total-pressure lineage is variable or not retained; '
      'entropy transport is required before field continuation'
    )
  elif not field.converged or not companion_field_verified:
    status = MocEulerAmbientShockFieldAuditStatus.FIELD_FAILURE
    message = (
      'shock and ambient boundary evidence passed, but the downstream '
      'attachment-aware characteristic field is not locally closed'
    )
  elif not promotion_flags_verified:
    status = MocEulerAmbientShockFieldAuditStatus.FLAG_FAILURE
    message = 'ambient shock-field result weakened its non-promotion fidelity flags'
  else:
    status = MocEulerAmbientShockFieldAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent exact-Euler ambient shock-field audit verified shock jumps, '
      'ambient pressure/tangency, C+ lineage, entropy consistency, and the '
      'open-field local strip; reflected closure remains pending'
    )
  ####
  return MocEulerAmbientShockFieldAudit(
    status=status,
    field_status=field.status.value,
    shock_sample_count=shock_count,
    ambient_sample_count=ambient_count,
    cell_count=0 if field.field is None else field.field.cell_count,
    shock_jump_mass_residuals=tuple(jump_mass),
    shock_jump_momentum_residuals=tuple(jump_momentum),
    shock_jump_energy_residuals=tuple(jump_energy),
    ambient_pressure_residuals=tuple(ambient_pressure_residuals),
    ambient_tangent_residuals=tuple(ambient_tangent_residuals),
    incoming_k_plus_residuals=tuple(incoming_k_plus_residuals),
    entropy_residuals=tuple(entropy_residuals),
    maximum_shock_jump_mass_residual=max(jump_mass, default=None),
    maximum_shock_jump_momentum_residual=max(jump_momentum, default=None),
    maximum_shock_jump_energy_residual=max(jump_energy, default=None),
    maximum_ambient_pressure_residual=ambient_pressure_maximum,
    maximum_ambient_tangent_residual=ambient_tangent_maximum,
    maximum_incoming_k_plus_residual=incoming_k_plus_maximum,
    maximum_entropy_residual=max(entropy_residuals, default=None),
    attachment_relative_pressure_residual=attachment_residual,
    shock_geometry_verified=shock_geometry_verified,
    shock_jump_verified=shock_jump_verified,
    ambient_sample_alignment_verified=ambient_sample_alignment_verified,
    ambient_direction_verified=ambient_direction_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    companion_field_verified=companion_field_verified,
    promotion_flags_verified=promotion_flags_verified,
    shock_residual_tolerance=shock_tolerance,
    cell_residual_tolerance=cell_tolerance,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
    tangent_tolerance=tangent_tolerance_value,
    ambient_boundary_kind=ambient_boundary_kind,
    ambient_companion_invariant_residuals=(
      tuple(ambient_companion_invariant_residuals)
    ),
    maximum_ambient_companion_invariant_residual=(
      companion_invariant_maximum
    ),
    message=message,
  )
####


class MocEulerAmbientShockFieldChainAuditStatus(str, Enum):
  """Outcome of independently measuring an exact open-field sequence."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_ambient_shock_field_chain_audit'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'euler_ambient_shock_field_chain_field_failure'
  HANDOFF_FAILURE = 'euler_ambient_shock_field_chain_handoff_failure'
  DOMAIN_FAILURE = 'euler_ambient_shock_field_chain_domain_failure'
  TERMINATION_FAILURE = 'euler_ambient_shock_field_chain_termination_failure'
  FLAG_FAILURE = 'euler_ambient_shock_field_chain_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldChainAudit:
  """Independent evidence for a repeated exact open ambient-field path."""

  status: MocEulerAmbientShockFieldChainAuditStatus
  field_count: int
  continued_field_count: int
  step_count: int
  field_statuses: tuple[str, ...]
  field_audits_verified: bool
  fresh_domains_verified: bool
  handoff_links_verified: bool
  termination_verified: bool
  fidelity_flags_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_SHOCK_FIELD_CHAIN_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientShockFieldChainAuditStatus,
    ):
      raise TypeError(
        'status must be a MocEulerAmbientShockFieldChainAuditStatus'
      )
    ####
    for name in (
      'field_count',
      'continued_field_count',
      'step_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    statuses = tuple(str(value) for value in self.field_statuses)
    if len(statuses) != self.field_count:
      raise ValueError('field_statuses must match field_count')
    ####
    object.__setattr__(self, 'field_statuses', statuses)
    for name in (
      'field_audits_verified',
      'fresh_domains_verified',
      'handoff_links_verified',
      'termination_verified',
      'fidelity_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerAmbientShockFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_sequence_verified(self) -> bool:
    return bool(
      self.converged
      and self.field_audits_verified
      and self.fresh_domains_verified
      and self.handoff_links_verified
      and self.termination_verified
      and self.fidelity_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'step_count': self.step_count,
      'field_statuses': list(self.field_statuses),
      'checks': {
        'field_audits_verified': self.field_audits_verified,
        'fresh_domains_verified': self.fresh_domains_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'termination_verified': self.termination_verified,
        'fidelity_flags_verified': self.fidelity_flags_verified,
        'local_sequence_verified': self.local_sequence_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-exact-euler-ambient-shock-field-chain-audit; '
        'attachment-aware remesh, reflected closure, and external validation '
        'remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _ambient_shock_field_chain_audit_failure(
  status: MocEulerAmbientShockFieldChainAuditStatus,
  message: str,
  *,
  field_count: int = 0,
  continued_field_count: int = 0,
  step_count: int = 0,
  field_statuses: tuple[str, ...] = (),
  field_audits_verified: bool = False,
  fresh_domains_verified: bool = False,
  handoff_links_verified: bool = False,
  termination_verified: bool = False,
  fidelity_flags_verified: bool = False,
) -> MocEulerAmbientShockFieldChainAudit:
  return MocEulerAmbientShockFieldChainAudit(
    status=status,
    field_count=field_count,
    continued_field_count=continued_field_count,
    step_count=step_count,
    field_statuses=field_statuses,
    field_audits_verified=field_audits_verified,
    fresh_domains_verified=fresh_domains_verified,
    handoff_links_verified=handoff_links_verified,
    termination_verified=termination_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    message=message,
  )
####


def _ambient_shock_field_chain_fingerprint(field: Any) -> str | None:
  if not isinstance(field, MocEulerAmbientShockFieldResult):
    return None
  ####

  def state_payload(state: Any) -> str:
    return '|'.join(
      float(value).hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )
  ####

  payload = [
    f'status:{field.status.value}',
    f'ambient-pressure:{field.ambient_pressure_Pa!r}',
  ]
  if field.shock_boundary is not None:
    payload.append('shock')
    payload.extend(
      f'{state_payload(state)}|{float(point[0]).hex()}|'
      f'{float(point[1]).hex()}'
      for state, point in zip(
        field.shock_boundary.downstream_states,
        field.shock_boundary.shock_points_m,
        strict=True,
      )
    )
  ####
  if field.ambient_march is not None:
    payload.append('ambient')
    payload.extend(
      f'{state_payload(sample.state)}|{float(sample.point_m[0]).hex()}|'
      f'{float(sample.point_m[1]).hex()}|{float(sample.total_pressure_Pa).hex()}'
      for sample in field.ambient_march.boundary_samples
    )
  ####
  if field.ambient_companion_boundary is not None:
    payload.append('explicit-companion')
    payload.extend(
      f'{state_payload(sample.state)}|{float(sample.point_m[0]).hex()}|'
      f'{float(sample.point_m[1]).hex()}|{float(sample.total_pressure_Pa).hex()}'
      for sample in field.ambient_companion_boundary.samples
    )
  ####
  if field.attachment_wedge is not None:
    payload.append('attachment-wedge:' + field.attachment_wedge.status.value)
    payload.extend(
      f'{trial.plus_source_index}|{trial.minus_source_index}|'
      f'{trial.accepted}|{trial.forward_margin_m!r}'
      for trial in field.attachment_wedge.trials
    )
  ####
  if field.field is not None:
    nested = _euler_chain_field_fingerprint(field.field)
    if nested is None:
      return None
    ####
    payload.append('companion:' + nested)
  ####
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()
####


def _ambient_shock_field_chain_x_extent(
  field: Any,
) -> tuple[float, float] | None:
  if not isinstance(field, MocEulerAmbientShockFieldResult):
    return None
  ####
  points: list[tuple[float, float]] = []
  if field.shock_boundary is not None:
    points.extend(field.shock_boundary.shock_points_m)
  ####
  if field.ambient_march is not None:
    points.extend(field.ambient_march.points_m)
  ####
  if field.ambient_companion_boundary is not None:
    points.extend(
      sample.point_m for sample in field.ambient_companion_boundary.samples
    )
  ####
  if field.field is not None:
    points.extend(field.field.shock_boundary_points_m)
    points.extend(field.field.companion_boundary_points_m)
    points.extend(field.field.interior_points_m)
  ####
  if not points:
    return None
  ####
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  ####
  return min(values), max(values)
####


def measure_moc_euler_ambient_shock_field_chain(
  chain: Any,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocEulerAmbientShockFieldChainAudit:
  """Remeasure an exact ambient-field sequence without invoking callbacks."""

  from exhaust_plume.models.moc.planner import (
    MocEulerAmbientShockFieldChainPlannerResult,
  )

  if not isinstance(chain, MocEulerAmbientShockFieldChainPlannerResult):
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.INVALID_INPUT,
      'chain must be a MocEulerAmbientShockFieldChainPlannerResult',
    )
  ####
  fields = tuple(chain.fields)
  steps = tuple(chain.steps)
  field_statuses = tuple(field.status.value for field in fields)
  if not fields or any(
    not isinstance(field, MocEulerAmbientShockFieldResult)
    for field in fields
  ):
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.INVALID_INPUT,
      'chain must retain one or more exact ambient shock fields',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=field_statuses,
    )
  ####

  field_audits = tuple(
    measure_moc_euler_ambient_shock_field(
      field,
      shock_residual_tolerance=shock_residual_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
    )
    for field in fields
  )
  field_audits_verified = all(
    audit.converged and audit.local_consistency_verified
    for audit in field_audits
  )
  if not field_audits_verified:
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.FIELD_FAILURE,
      'one or more exact ambient shock fields failed its local audit',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=field_statuses,
    )
  ####

  extents = tuple(_ambient_shock_field_chain_x_extent(field) for field in fields)
  fresh_domains_verified = all(
    previous is not None
    and current is not None
    and current[0] > previous[1] + position_tolerance_m
    for previous, current in zip(extents, extents[1:])
  )
  if not fresh_domains_verified:
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.DOMAIN_FAILURE,
      'exact ambient shock fields do not occupy fresh downstream domains',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=field_statuses,
      field_audits_verified=True,
    )
  ####

  handoff_links_verified = bool(steps)
  for index, step in enumerate(steps):
    expected_index = index + 2
    if index >= len(fields):
      handoff_links_verified = False
      continue
    ####
    incoming = fields[index].downstream_handoff
    handoff_links_verified = handoff_links_verified and bool(
      step.next_field_index == expected_index
      and step.incoming_handoff_sample_count == len(incoming)
      and step.incoming_handoff_fingerprint == _euler_chain_handoff_fingerprint(incoming)
      and step.incoming_handoff_link_verified
    )
    if step.result_kind == 'field-solve-returned':
      if index + 1 >= len(fields):
        handoff_links_verified = False
        continue
      ####
      next_field = fields[index + 1]
      handoff_links_verified = handoff_links_verified and bool(
        step.result_field_status == next_field.status.value
        and step.result_field_fingerprint
        == _ambient_shock_field_chain_fingerprint(next_field)
        and step.result_handoff_sample_count == len(next_field.downstream_handoff)
        and step.result_handoff_fingerprint
        == _euler_chain_handoff_fingerprint(next_field.downstream_handoff)
      )
    ####
  ####
  if not handoff_links_verified:
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.HANDOFF_FAILURE,
      'exact ambient shock field frontier links failed independent remeasurement',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=field_statuses,
      field_audits_verified=True,
      fresh_domains_verified=True,
    )
  ####

  termination_verified = bool(
    steps
    and steps[-1].result_termination_reason is chain.termination.reason
    and steps[-1].result_physical_termination
    is chain.termination.physical_termination
  )
  if not termination_verified:
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.TERMINATION_FAILURE,
      'chain termination metadata did not match its final planner step',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=field_statuses,
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=True,
    )
  ####

  fidelity_flags_verified = bool(
    not chain.physical_closure_verified
    and chain.chain_promotion_blocked
    and not chain.production_claim_allowed
    and all(
      not field.physical_closure_verified
      and field.chain_promotion_blocked
      and not field.production_claim_allowed
      and field.ambient_boundary_verified
      and field.entropy_lineage_verified
      and field.local_field_verified
      for field in fields
    )
  )
  if not fidelity_flags_verified:
    return _ambient_shock_field_chain_audit_failure(
      MocEulerAmbientShockFieldChainAuditStatus.FLAG_FAILURE,
      'exact ambient shock field sequence weakened its fidelity boundary',
      field_count=len(fields),
      continued_field_count=max(0, len(fields) - 1),
      step_count=len(steps),
      field_statuses=field_statuses,
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=True,
      termination_verified=True,
    )
  ####
  return MocEulerAmbientShockFieldChainAudit(
    status=MocEulerAmbientShockFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT,
    field_count=len(fields),
    continued_field_count=max(0, len(fields) - 1),
    step_count=len(steps),
    field_statuses=field_statuses,
    field_audits_verified=True,
    fresh_domains_verified=True,
    handoff_links_verified=True,
    termination_verified=True,
    fidelity_flags_verified=True,
    message=(
      'independent exact-Euler ambient shock-field sequence audit reproduced '
      'local field evidence, fresh domains, exact frontier links, and the '
      'typed non-physical stop; attachment-aware remesh and reflected closure '
      'remain pending'
    ),
  )
####


MOC_EULER_POST_SHOCK_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler.post-shock-field-audit'
)
MOC_EULER_POST_SHOCK_FIELD_CHAIN_AUDIT_OPERATOR_ID = (
  'op.moc.euler.post-shock-field-chain-audit'
)


class MocEulerPostShockFieldAuditStatus(str, Enum):
  """Outcome of independently auditing a local post-shock field."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_post_shock_field_audit'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'euler_post_shock_field_audit_shock_failure'
  INVARIANT_FAILURE = 'euler_post_shock_field_audit_invariant_failure'
  GEOMETRY_FAILURE = 'euler_post_shock_field_audit_geometry_failure'
  TOPOLOGY_FAILURE = 'euler_post_shock_field_audit_topology_failure'
  CELL_RESIDUAL_FAILURE = 'euler_post_shock_field_audit_cell_residual_failure'
  FLAG_FAILURE = 'euler_post_shock_field_audit_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldAudit:
  """Independent geometry, shock-jump, and cell-residual evidence."""

  status: MocEulerPostShockFieldAuditStatus
  field_status: str | None
  shock_sample_count: int
  node_count: int
  cell_count: int
  shock_jump_mass_residuals: tuple[float, ...] = ()
  shock_jump_momentum_residuals: tuple[float, ...] = ()
  shock_jump_energy_residuals: tuple[float, ...] = ()
  centerline_invariant_residuals: tuple[float, ...] = ()
  node_invariant_residuals: tuple[float, ...] = ()
  cell_euler_residuals: tuple[float, ...] = ()
  maximum_shock_jump_mass_residual: float | None = None
  maximum_shock_jump_momentum_residual: float | None = None
  maximum_shock_jump_energy_residual: float | None = None
  maximum_centerline_invariant_residual: float | None = None
  maximum_node_invariant_residual: float | None = None
  maximum_cell_euler_residual: float | None = None
  shock_geometry_verified: bool = False
  shock_jump_verified: bool = False
  uniform_state_verified: bool = False
  centerline_geometry_verified: bool = False
  interior_geometry_verified: bool = False
  topology_verified: bool = False
  cell_euler_residuals_finite: bool = False
  cell_euler_residuals_verified: bool = False
  fidelity_flags_verified: bool = False
  shock_residual_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-8
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  state_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-8
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_POST_SHOCK_FIELD_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerPostShockFieldAuditStatus):
      raise TypeError(
        'status must be a MocEulerPostShockFieldAuditStatus'
      )
    ####
    if self.field_status is not None:
      object.__setattr__(self, 'field_status', str(self.field_status))
    ####
    for name in ('shock_sample_count', 'node_count', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'shock_jump_mass_residuals',
      'shock_jump_momentum_residuals',
      'shock_jump_energy_residuals',
      'centerline_invariant_residuals',
      'node_invariant_residuals',
      'cell_euler_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_centerline_invariant_residual',
      'maximum_node_invariant_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'shock_residual_tolerance',
      'cell_residual_tolerance',
      'position_tolerance_m',
      'invariant_tolerance',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'shock_geometry_verified',
      'shock_jump_verified',
      'uniform_state_verified',
      'centerline_geometry_verified',
      'interior_geometry_verified',
      'topology_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'fidelity_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerPostShockFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock_geometry_verified
      and self.shock_jump_verified
      and self.uniform_state_verified
      and self.centerline_geometry_verified
      and self.interior_geometry_verified
      and self.topology_verified
      and self.cell_euler_residuals_verified
      and self.fidelity_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'field_status': self.field_status,
      'shock_sample_count': self.shock_sample_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'shock_jump_mass_residuals': list(self.shock_jump_mass_residuals),
      'shock_jump_momentum_residuals': list(self.shock_jump_momentum_residuals),
      'shock_jump_energy_residuals': list(self.shock_jump_energy_residuals),
      'centerline_invariant_residuals': list(self.centerline_invariant_residuals),
      'node_invariant_residuals': list(self.node_invariant_residuals),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_shock_jump_mass_residual': self.maximum_shock_jump_mass_residual,
      'maximum_shock_jump_momentum_residual': self.maximum_shock_jump_momentum_residual,
      'maximum_shock_jump_energy_residual': self.maximum_shock_jump_energy_residual,
      'maximum_centerline_invariant_residual': self.maximum_centerline_invariant_residual,
      'maximum_node_invariant_residual': self.maximum_node_invariant_residual,
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'shock_geometry_verified': self.shock_geometry_verified,
        'shock_jump_verified': self.shock_jump_verified,
        'uniform_state_verified': self.uniform_state_verified,
        'centerline_geometry_verified': self.centerline_geometry_verified,
        'interior_geometry_verified': self.interior_geometry_verified,
        'topology_verified': self.topology_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'fidelity_flags_verified': self.fidelity_flags_verified,
        'local_consistency_verified': self.local_consistency_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'tolerances': {
        'shock_residual_tolerance': self.shock_residual_tolerance,
        'cell_residual_tolerance': self.cell_residual_tolerance,
        'position_tolerance_m': self.position_tolerance_m,
        'invariant_tolerance': self.invariant_tolerance,
        'state_tolerance': self.state_tolerance,
        'pressure_tolerance': self.pressure_tolerance,
      },
      'canonical_euler_verified': False,
      'canonical_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-local-euler-post-shock-field-audit; ambient/free-boundary '
        'closure, physical chain promotion, and external validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _post_shock_field_audit_failure(
  status: MocEulerPostShockFieldAuditStatus,
  message: str,
  *,
  field_status: str | None = None,
  shock_sample_count: int = 0,
  node_count: int = 0,
  cell_count: int = 0,
  shock_jump_mass_residuals: Sequence[float] = (),
  shock_jump_momentum_residuals: Sequence[float] = (),
  shock_jump_energy_residuals: Sequence[float] = (),
  centerline_invariant_residuals: Sequence[float] = (),
  node_invariant_residuals: Sequence[float] = (),
  cell_euler_residuals: Sequence[float] = (),
  shock_geometry_verified: bool = False,
  shock_jump_verified: bool = False,
  uniform_state_verified: bool = False,
  centerline_geometry_verified: bool = False,
  interior_geometry_verified: bool = False,
  topology_verified: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  fidelity_flags_verified: bool = False,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocEulerPostShockFieldAudit:
  values = tuple(
    tuple(float(value) for value in sequence)
    for sequence in (
      shock_jump_mass_residuals,
      shock_jump_momentum_residuals,
      shock_jump_energy_residuals,
      centerline_invariant_residuals,
      node_invariant_residuals,
      cell_euler_residuals,
    )
  )
  maxima = tuple(max(sequence, default=None) for sequence in values)
  return MocEulerPostShockFieldAudit(
    status=status,
    field_status=field_status,
    shock_sample_count=shock_sample_count,
    node_count=node_count,
    cell_count=cell_count,
    shock_jump_mass_residuals=values[0],
    shock_jump_momentum_residuals=values[1],
    shock_jump_energy_residuals=values[2],
    centerline_invariant_residuals=values[3],
    node_invariant_residuals=values[4],
    cell_euler_residuals=values[5],
    maximum_shock_jump_mass_residual=maxima[0],
    maximum_shock_jump_momentum_residual=maxima[1],
    maximum_shock_jump_energy_residual=maxima[2],
    maximum_centerline_invariant_residual=maxima[3],
    maximum_node_invariant_residual=maxima[4],
    maximum_cell_euler_residual=maxima[5],
    shock_geometry_verified=shock_geometry_verified,
    shock_jump_verified=shock_jump_verified,
    uniform_state_verified=uniform_state_verified,
    centerline_geometry_verified=centerline_geometry_verified,
    interior_geometry_verified=interior_geometry_verified,
    topology_verified=topology_verified,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    shock_residual_tolerance=shock_residual_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    message=message,
  )
####


def _post_shock_characteristic_geometry(
  source: CharacteristicState,
  target: CharacteristicState,
  family: Any,
) -> tuple[float, float] | None:
  first_direction = source.direction(family)
  second_direction = target.direction(family)
  averaged = (
    0.5 * (first_direction[0] + second_direction[0]),
    0.5 * (first_direction[1] + second_direction[1]),
  )
  norm = hypot(*averaged)
  if norm <= 0.0 or not isfinite(norm):
    return None
  ####
  displacement = (target.x_m - source.x_m, target.y_m - source.y_m)
  unit = (averaged[0] / norm, averaged[1] / norm)
  return (
    displacement[0] * unit[0] + displacement[1] * unit[1],
    abs(displacement[0] * unit[1] - displacement[1] * unit[0]),
  )
####


def measure_moc_euler_post_shock_field(
  field: MocEulerPostShockFieldResult,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocEulerPostShockFieldAudit:
  """Remeasure the local field without invoking its assembler or planner."""

  if not isinstance(field, MocEulerPostShockFieldResult):
    return _post_shock_field_audit_failure(
      MocEulerPostShockFieldAuditStatus.INVALID_INPUT,
      'field must be a MocEulerPostShockFieldResult',
    )
  ####
  try:
    shock_tolerance = float(shock_residual_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    state_tolerance_value = float(state_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _post_shock_field_audit_failure(
      MocEulerPostShockFieldAuditStatus.INVALID_INPUT,
      'post-shock field audit tolerances must be numeric',
      field_status=field.status.value,
    )
  ####
  if any(
    not isfinite(value) or value <= 0.0
    for value in (
      shock_tolerance,
      cell_tolerance,
      position_tolerance,
      invariant_tolerance_value,
      state_tolerance_value,
      pressure_tolerance_value,
    )
  ):
    raise ValueError('post-shock field audit tolerances must be finite and positive')
  ####

  shock = field.shock_boundary
  points = tuple(field.shock_boundary_points_m)
  states = tuple(field.shock_boundary_states)
  pressures = tuple(field.shock_boundary_total_pressure_Pa)
  common = {
    'field_status': field.status.value,
    'shock_sample_count': len(points),
    'node_count': field.node_count,
    'cell_count': field.cell_count,
    'shock_residual_tolerance': shock_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'position_tolerance_m': position_tolerance,
    'invariant_tolerance': invariant_tolerance_value,
    'state_tolerance': state_tolerance_value,
    'pressure_tolerance': pressure_tolerance_value,
  }
  if shock is None or len(points) < 3:
    return _post_shock_field_audit_failure(
      MocEulerPostShockFieldAuditStatus.SHOCK_FAILURE,
      'local post-shock audit requires a retained shock boundary with at least three samples',
      **common,
    )
  ####
  if len(states) != len(points) or len(pressures) != len(points):
    return _post_shock_field_audit_failure(
      MocEulerPostShockFieldAuditStatus.SHOCK_FAILURE,
      'retained post-shock shock arrays are not aligned',
      **common,
    )
  ####
  if (
    len(shock.upstream_states) != len(points)
    or len(shock.upstream_total_pressure_Pa) != len(points)
    or len(shock.downstream_total_pressure_Pa) != len(points)
    or not shock.converged
  ):
    return _post_shock_field_audit_failure(
      MocEulerPostShockFieldAuditStatus.SHOCK_FAILURE,
      'retained exact shock data is incomplete for an independent jump audit',
      **common,
    )
  ####

  shock_geometry_verified = bool(
    shock.orientation is MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
    and all(
      hypot(state.x_m - point[0], state.y_m - point[1])
      <= 10.0 * position_tolerance
      for point, state in zip(points, states, strict=True)
    )
    and all(
      current[0] > previous[0] + position_tolerance
      and current[1] <= previous[1] + position_tolerance
      for previous, current in zip(points[:-1], points[1:], strict=True)
    )
    and points[0][1] > position_tolerance
    and abs(points[-1][1]) <= 10.0 * position_tolerance
  )
  jump_residuals = tuple(
    _shock_jump_residuals(
      upstream_state,
      upstream_pressure,
      downstream_state,
      downstream_pressure,
      _shock_tangent(points, index),
    )
    for index, (
      upstream_state,
      upstream_pressure,
      downstream_state,
      downstream_pressure,
    ) in enumerate(zip(
      shock.upstream_states,
      shock.upstream_total_pressure_Pa,
      states,
      shock.downstream_total_pressure_Pa,
      strict=True,
    ))
  )
  shock_jump_mass = tuple(value[0] for value in jump_residuals)
  shock_jump_momentum = tuple(value[1] for value in jump_residuals)
  shock_jump_energy = tuple(value[2] for value in jump_residuals)
  shock_jump_verified = bool(
    shock_geometry_verified
    and max((*shock_jump_mass, *shock_jump_momentum, *shock_jump_energy), default=float('inf'))
    <= shock_tolerance
  )

  reference_state = states[0]
  uniform_state_verified = bool(
    all(
      max(
        abs(state.theta_rad - reference_state.theta_rad),
        abs(state.mach - reference_state.mach),
        abs(state.gamma - reference_state.gamma),
      ) <= state_tolerance_value
      for state in states
    )
    and abs(reference_state.theta_rad) <= state_tolerance_value
    and all(
      abs(value - pressures[0])
      <= pressure_tolerance_value * max(1.0, abs(pressures[0]))
      for value in pressures
    )
  )
  centerline_points = tuple(field.centerline_boundary_points_m)
  centerline_states = tuple(field.centerline_boundary_states)
  centerline_invariants = tuple(
    abs(state.k_minus - shock_state.k_minus)
    for state, shock_state in zip(centerline_states, states, strict=False)
  )
  centerline_geometry_verified = bool(
    len(centerline_points) == len(points)
    and len(centerline_states) == len(points)
    and len(field.centerline_boundary_total_pressure_Pa) == len(points)
    and all(
      abs(point[1]) <= 10.0 * position_tolerance
      and hypot(state.x_m - point[0], state.y_m - point[1])
      <= 10.0 * position_tolerance
      for point, state in zip(centerline_points, centerline_states, strict=True)
    )
    and all(
      current[0] > previous[0] + position_tolerance
      for previous, current in zip(
        centerline_points[:-1],
        centerline_points[1:],
        strict=True,
      )
    )
    and centerline_points
    and hypot(
      centerline_points[-1][0] - points[-1][0],
      centerline_points[-1][1] - points[-1][1],
    ) <= 10.0 * position_tolerance
    and max(centerline_invariants, default=float('inf'))
    <= invariant_tolerance_value
  )

  node_invariants: list[float] = []
  interior_geometry_verified = True
  for node in field.nodes:
    if (
      hypot(node.state.x_m - node.point_m[0], node.state.y_m - node.point_m[1])
      > 10.0 * position_tolerance
      or not node.point_result.converged
    ):
      interior_geometry_verified = False
    ####
    if node.point_result.intersection_status == (
      'synthetic-uniform-state-terminal-center'
    ):
      node_invariants.append(0.0)
      continue
    ####
    centerline_index = node.centerline_index
    boundary_index = node.boundary_index
    if (
      centerline_index < 0
      or boundary_index < 0
      or centerline_index >= len(centerline_states)
      or boundary_index >= len(states)
    ):
      interior_geometry_verified = False
      continue
    ####
    if centerline_index == boundary_index:
      node_invariants.append(
        abs(node.state.k_minus - states[boundary_index].k_minus)
      )
      geometry = _post_shock_characteristic_geometry(
        states[boundary_index],
        node.state,
        CharacteristicFamily.MINUS,
      )
      if geometry is None or geometry[0] <= position_tolerance:
        interior_geometry_verified = False
      ####
    elif centerline_index < boundary_index:
      plus_residual = abs(
        node.state.k_plus - centerline_states[centerline_index].k_plus
      )
      minus_residual = abs(
        node.state.k_minus - states[boundary_index].k_minus
      )
      node_invariants.append(max(plus_residual, minus_residual))
      plus_geometry = _post_shock_characteristic_geometry(
        centerline_states[centerline_index],
        node.state,
        CharacteristicFamily.PLUS,
      )
      minus_geometry = _post_shock_characteristic_geometry(
        states[boundary_index],
        node.state,
        CharacteristicFamily.MINUS,
      )
      if (
        plus_geometry is None
        or minus_geometry is None
        or plus_geometry[0] <= position_tolerance
        or minus_geometry[0] <= position_tolerance
        or plus_geometry[1] > position_tolerance
        or minus_geometry[1] > position_tolerance
      ):
        interior_geometry_verified = False
      ####
    else:
      interior_geometry_verified = False
    ####
  ####
  if max(node_invariants, default=float('inf')) > invariant_tolerance_value:
    interior_geometry_verified = False
  ####

  topology = validate_moc_mesh(field.cells)
  topology_verified = bool(
    topology == field.topology
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  cell_residuals: list[float] = []
  cell_residuals_finite = True
  try:
    for cell in field.cells:
      cell_states = tuple(
        replace(reference_state, x_m=point[0], y_m=point[1])
        for point in cell.vertices_xr_m
      )
      cell_residuals.append(
        _cell_flux_residual(
          tuple(cell.vertices_xr_m),
          cell_states,
          (pressures[0],) * len(cell.vertices_xr_m),
        )
      )
    ####
  except (ArithmeticError, TypeError, ValueError):
    cell_residuals_finite = False
  ####
  cell_euler_residuals_verified = bool(
    cell_residuals_finite
    and len(cell_residuals) == len(field.cells)
    and all(isfinite(value) for value in cell_residuals)
    and max(cell_residuals, default=float('inf')) <= cell_tolerance
  )
  fidelity_flags_verified = bool(
    not field.physical_closure_verified
    and field.chain_promotion_blocked
    and not field.production_claim_allowed
    and field.terminal_mesh_completion_synthetic
  )

  if not shock_jump_verified:
    status = MocEulerPostShockFieldAuditStatus.SHOCK_FAILURE
    message = 'independent Rankine--Hugoniot or shock geometry checks failed'
  elif not uniform_state_verified or max(
    centerline_invariants,
    default=float('inf'),
  ) > invariant_tolerance_value:
    status = MocEulerPostShockFieldAuditStatus.INVARIANT_FAILURE
    message = 'uniform-state or centerline characteristic invariants failed'
  elif not centerline_geometry_verified or not interior_geometry_verified:
    status = MocEulerPostShockFieldAuditStatus.GEOMETRY_FAILURE
    message = 'independent post-shock characteristic geometry checks failed'
  elif not topology_verified:
    status = MocEulerPostShockFieldAuditStatus.TOPOLOGY_FAILURE
    message = 'independent post-shock mesh topology check failed'
  elif not cell_euler_residuals_verified:
    status = MocEulerPostShockFieldAuditStatus.CELL_RESIDUAL_FAILURE
    message = 'independent constant-state Euler cell residual check failed'
  elif not fidelity_flags_verified:
    status = MocEulerPostShockFieldAuditStatus.FLAG_FAILURE
    message = 'local post-shock field weakened its explicit fidelity boundary'
  else:
    status = MocEulerPostShockFieldAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent local exact-Euler post-shock audit verified shock jumps, '
      'uniform state, centerline/interior characteristic geometry, closed '
      'topology, bounded cell residuals, and the non-physical fidelity stop'
    )
  ####
  return _post_shock_field_audit_failure(
    status,
    message,
    **common,
    shock_jump_mass_residuals=shock_jump_mass,
    shock_jump_momentum_residuals=shock_jump_momentum,
    shock_jump_energy_residuals=shock_jump_energy,
    centerline_invariant_residuals=centerline_invariants,
    node_invariant_residuals=node_invariants,
    cell_euler_residuals=cell_residuals,
    shock_geometry_verified=shock_geometry_verified,
    shock_jump_verified=shock_jump_verified,
    uniform_state_verified=uniform_state_verified,
    centerline_geometry_verified=centerline_geometry_verified,
    interior_geometry_verified=interior_geometry_verified,
    topology_verified=topology_verified,
    cell_euler_residuals_finite=cell_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    fidelity_flags_verified=fidelity_flags_verified,
  )
####


class MocEulerPostShockFieldChainAuditStatus(str, Enum):
  """Outcome of independently auditing a local post-shock field chain."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_post_shock_field_chain_audit'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'euler_post_shock_field_chain_audit_field_failure'
  DOMAIN_FAILURE = 'euler_post_shock_field_chain_audit_domain_failure'
  HANDOFF_FAILURE = 'euler_post_shock_field_chain_audit_handoff_failure'
  TERMINATION_FAILURE = 'euler_post_shock_field_chain_audit_termination_failure'
  FLAG_FAILURE = 'euler_post_shock_field_chain_audit_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldChainAudit:
  """Independent sequence, domain, handoff, and fidelity evidence."""

  status: MocEulerPostShockFieldChainAuditStatus
  field_count: int
  continued_field_count: int
  step_count: int
  field_statuses: tuple[str, ...]
  field_audits_verified: bool = False
  fresh_domains_verified: bool = False
  handoff_links_verified: bool = False
  termination_verified: bool = False
  fidelity_flags_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = MOC_EULER_POST_SHOCK_FIELD_CHAIN_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerPostShockFieldChainAuditStatus):
      raise TypeError(
        'status must be a MocEulerPostShockFieldChainAuditStatus'
      )
    ####
    for name in ('field_count', 'continued_field_count', 'step_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    statuses = tuple(str(value) for value in self.field_statuses)
    object.__setattr__(self, 'field_statuses', statuses)
    for name in (
      'field_audits_verified',
      'fresh_domains_verified',
      'handoff_links_verified',
      'termination_verified',
      'fidelity_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerPostShockFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.field_audits_verified
      and self.fresh_domains_verified
      and self.handoff_links_verified
      and self.termination_verified
      and self.fidelity_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'step_count': self.step_count,
      'field_statuses': list(self.field_statuses),
      'checks': {
        'field_audits_verified': self.field_audits_verified,
        'fresh_domains_verified': self.fresh_domains_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'termination_verified': self.termination_verified,
        'fidelity_flags_verified': self.fidelity_flags_verified,
        'local_consistency_verified': self.local_consistency_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'canonical_euler_verified': False,
      'canonical_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-local-euler-post-shock-field-chain-audit; ambient/free-'
        'boundary closure and physical shock-cell promotion remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _post_shock_field_chain_audit_failure(
  status: MocEulerPostShockFieldChainAuditStatus,
  message: str,
  *,
  field_count: int = 0,
  continued_field_count: int = 0,
  step_count: int = 0,
  field_statuses: Sequence[str] = (),
  field_audits_verified: bool = False,
  fresh_domains_verified: bool = False,
  handoff_links_verified: bool = False,
  termination_verified: bool = False,
  fidelity_flags_verified: bool = False,
) -> MocEulerPostShockFieldChainAudit:
  return MocEulerPostShockFieldChainAudit(
    status=status,
    field_count=field_count,
    continued_field_count=continued_field_count,
    step_count=step_count,
    field_statuses=tuple(field_statuses),
    field_audits_verified=field_audits_verified,
    fresh_domains_verified=fresh_domains_verified,
    handoff_links_verified=handoff_links_verified,
    termination_verified=termination_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    message=message,
  )
####


def _post_shock_field_chain_handoff_fingerprint(boundary: Sequence[Any]) -> str | None:
  if not boundary:
    return None
  ####
  payload = '\n'.join(
    '|'.join(
      value.hex()
      for value in (
        sample.state.x_m,
        sample.state.y_m,
        sample.state.theta_rad,
        sample.state.mach,
        sample.state.gamma,
        sample.total_pressure_Pa,
      )
    )
    for sample in boundary
  )
  return sha256(payload.encode('ascii')).hexdigest()
####


def _post_shock_field_chain_fingerprint(field: MocEulerPostShockFieldResult) -> str:
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
  ####

  payload = [f'status:{field.status.value}']
  for label, points, states, pressures in (
    (
      'shock',
      field.shock_boundary_points_m,
      field.shock_boundary_states,
      field.shock_boundary_total_pressure_Pa,
    ),
    (
      'centerline',
      field.centerline_boundary_points_m,
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
    ),
  ):
    payload.append(label)
    payload.extend(
      f'{point[0].hex()}|{point[1].hex()}|{state_payload(state)}|{pressure.hex()}'
      for point, state, pressure in zip(points, states, pressures, strict=True)
    )
  ####
  payload.append('nodes')
  payload.extend(
    f'{node.point_m[0].hex()}|{node.point_m[1].hex()}|'
    f'{state_payload(node.state)}|{node.total_pressure_Pa!r}'
    for node in field.nodes
  )
  payload.append('cells')
  payload.extend(
    '|'.join(value.hex() for point in cell.vertices_xr_m for value in point)
    for cell in field.cells
  )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()
####


def _post_shock_field_chain_x_extent(
  field: MocEulerPostShockFieldResult,
) -> tuple[float, float] | None:
  points = (
    *(point for cell in field.cells for point in cell.vertices_xr_m),
    *field.shock_boundary_points_m,
    *field.centerline_boundary_points_m,
  )
  if not points:
    return None
  ####
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  ####
  return min(values), max(values)
####


def measure_moc_euler_post_shock_field_chain(
  chain: Any,
  *,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocEulerPostShockFieldChainAudit:
  """Remeasure a continued local-field sequence without callbacks."""

  from exhaust_plume.models.moc.planner import (
    MocEulerPostShockFieldChainPlannerResult,
  )

  if not isinstance(chain, MocEulerPostShockFieldChainPlannerResult):
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.INVALID_INPUT,
      'chain must be a MocEulerPostShockFieldChainPlannerResult',
    )
  ####
  fields = tuple(chain.fields)
  steps = tuple(chain.steps)
  statuses = tuple(field.status.value for field in fields)
  common = {
    'field_count': len(fields),
    'continued_field_count': max(0, len(fields) - 1),
    'step_count': len(steps),
    'field_statuses': statuses,
  }
  if not fields or any(
    not isinstance(field, MocEulerPostShockFieldResult)
    for field in fields
  ):
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.INVALID_INPUT,
      'chain must retain one or more local post-shock fields',
      **common,
    )
  ####
  field_audits = tuple(
    measure_moc_euler_post_shock_field(
      field,
      shock_residual_tolerance=shock_residual_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
    for field in fields
  )
  field_audits_verified = all(
    audit.converged and audit.local_consistency_verified
    for audit in field_audits
  )
  if not field_audits_verified:
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.FIELD_FAILURE,
      'one or more local post-shock fields failed its independent audit',
      **common,
    )
  ####
  extents = tuple(_post_shock_field_chain_x_extent(field) for field in fields)
  fresh_domains_verified = all(
    previous is not None
    and current is not None
    and current[0] > previous[1] + position_tolerance_m
    for previous, current in zip(extents[:-1], extents[1:], strict=True)
  )
  if not fresh_domains_verified:
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.DOMAIN_FAILURE,
      'local post-shock fields do not occupy fresh downstream domains',
      **common,
      field_audits_verified=True,
    )
  ####
  handoff_links_verified = bool(steps)
  for index, step in enumerate(steps):
    if index >= len(fields):
      handoff_links_verified = False
      continue
    ####
    incoming = fields[index].downstream_handoff
    handoff_links_verified = handoff_links_verified and bool(
      step.next_field_index == index + 2
      and step.incoming_handoff_sample_count == len(incoming)
      and step.incoming_handoff_fingerprint
      == _post_shock_field_chain_handoff_fingerprint(incoming)
      and step.incoming_handoff_link_verified
    )
    if step.result_kind == 'field-solve-returned':
      if index + 1 >= len(fields):
        handoff_links_verified = False
        continue
      ####
      next_field = fields[index + 1]
      handoff_links_verified = handoff_links_verified and bool(
        step.result_field_status == next_field.status.value
        and step.result_field_fingerprint
        == _post_shock_field_chain_fingerprint(next_field)
        and step.result_handoff_sample_count == len(next_field.downstream_handoff)
        and step.result_handoff_fingerprint
        == _post_shock_field_chain_handoff_fingerprint(
          next_field.downstream_handoff
        )
      )
    ####
  ####
  if not handoff_links_verified:
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.HANDOFF_FAILURE,
      'local post-shock field frontier links failed independent remeasurement',
      **common,
      field_audits_verified=True,
      fresh_domains_verified=True,
    )
  ####
  termination_verified = bool(
    steps
    and steps[-1].result_termination_reason is chain.termination.reason
    and steps[-1].result_physical_termination
    is chain.termination.physical_termination
  )
  if not termination_verified:
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.TERMINATION_FAILURE,
      'chain termination metadata did not match its final planner step',
      **common,
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=True,
    )
  ####
  fidelity_flags_verified = bool(
    not chain.physical_closure_verified
    and chain.chain_promotion_blocked
    and not chain.production_claim_allowed
    and all(
      not field.physical_closure_verified
      and field.chain_promotion_blocked
      and not field.production_claim_allowed
      for field in fields
    )
  )
  if not fidelity_flags_verified:
    return _post_shock_field_chain_audit_failure(
      MocEulerPostShockFieldChainAuditStatus.FLAG_FAILURE,
      'local post-shock field sequence weakened its fidelity boundary',
      **common,
      field_audits_verified=True,
      fresh_domains_verified=True,
      handoff_links_verified=True,
      termination_verified=True,
    )
  ####
  return MocEulerPostShockFieldChainAudit(
    status=MocEulerPostShockFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT,
    **common,
    field_audits_verified=True,
    fresh_domains_verified=True,
    handoff_links_verified=True,
    termination_verified=True,
    fidelity_flags_verified=True,
    message=(
      'independent local exact-Euler post-shock chain audit verified every '
      'field, fresh domains, exact centerline frontier links, and the typed '
      'non-physical stop; ambient/free-boundary closure remains pending'
    ),
  )
####
