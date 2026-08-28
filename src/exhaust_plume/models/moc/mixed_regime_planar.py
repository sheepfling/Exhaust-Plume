"""Explicit planar downstream handoff for the mixed-regime MOC lane.

The terminal shock provides a scalar subsonic point and an open supersonic
patch.  It does not provide the downstream control section or the remaining
perimeter.  This module defines the callback boundary for a future planar
mixed-regime solver: callers must provide both pieces of geometry, and the
callback must return a field that retains the exact terminal seam and named
perimeter condition.

The callback seam remains available for a future canonical solver.  This
module also contains a separately named affine control-section projection
reference that drives the existing nonlinear isentropic potential solver.  A
successful reference handoff is useful evidence for planner and visualization
work, but remains non-promotable until a real downstream 2-D field and
canonical free-boundary validation exist.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import atan2, cos, hypot, isfinite, sin, sqrt
from typing import Callable

from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeClosureStatus,
  MocMixedRegimeControlSection,
  MocMixedRegimeControlSectionResult,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFieldSample,
  MocMixedRegimeFieldResult,
  MocMixedRegimePerimeterRequest,
  solve_mixed_regime_compressible_potential_field,
  validate_mixed_regime_boundary,
  validate_mixed_regime_downstream_condition,
  validate_mixed_regime_control_section,
)

__all__ = (
  'MocMixedRegimePlanarFieldSolver',
  'MocMixedRegimePlanarSolveStatus',
  'MocMixedRegimePlanarSolveResult',
  'MocMixedRegimePlanarPotentialReference',
  'solve_mixed_regime_planar_potential_reference',
  'run_mixed_regime_planar_field_solver',
)


MocMixedRegimePlanarFieldSolver = Callable[
  [
    MocMixedRegimePerimeterRequest,
    MocMixedRegimeControlSection,
    MocMixedRegimeDownstreamPerimeterSpec,
  ],
  MocMixedRegimeFieldResult | None,
]


class MocMixedRegimePlanarSolveStatus(str, Enum):
  """Outcome of the explicit planar mixed-regime callback seam."""

  CONVERGED_HANDOFF = 'converged-planar-downstream-handoff'
  INVALID_INPUT = 'invalid_input'
  CONTROL_SECTION_FAILURE = 'planar-control-section-failure'
  SOLVER_FAILURE = 'planar-solver-failure'
  SEAM_FAILURE = 'planar-seam-failure'
  PERIMETER_FAILURE = 'planar-perimeter-failure'
  FIELD_FAILURE = 'planar-field-failure'


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarSolveResult:
  """Auditable result for a callback-owned planar downstream handoff.

  ``converged`` means only that the callback field retained the requested
  control section/perimeter seam and passed its own field gates.  The adapter
  deliberately keeps ``physical_closure_verified`` false: the current field
  value object also represents scalar reference meshes, and this seam cannot
  promote one of those models into canonical planar-MOC closure by naming it
  differently.
  """

  status: MocMixedRegimePlanarSolveStatus
  request: MocMixedRegimePerimeterRequest
  control_section: MocMixedRegimeControlSection | None
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec | None
  control_section_validation: MocMixedRegimeControlSectionResult | None
  field: MocMixedRegimeFieldResult | None = None
  closure: MocMixedRegimeClosureResult | None = None
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver'
  message: str = ''
  control_section_projection_verified: bool = False
  maximum_control_section_projection_residual: float | None = None
  projection_model: str = 'none'

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedRegimePlanarSolveStatus):
      raise TypeError(
        'status must be a MocMixedRegimePlanarSolveStatus'
      )
    if not isinstance(self.request, MocMixedRegimePerimeterRequest):
      raise TypeError(
        'request must be a MocMixedRegimePerimeterRequest'
      )
    if self.control_section is not None and not isinstance(
      self.control_section,
      MocMixedRegimeControlSection,
    ):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection or None'
      )
    if self.perimeter_spec is not None and not isinstance(
      self.perimeter_spec,
      MocMixedRegimeDownstreamPerimeterSpec,
    ):
      raise TypeError(
        'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec or None'
      )
    if self.control_section_validation is not None and not isinstance(
      self.control_section_validation,
      MocMixedRegimeControlSectionResult,
    ):
      raise TypeError(
        'control_section_validation must be a '
        'MocMixedRegimeControlSectionResult or None'
      )
    if self.field is not None and not isinstance(
      self.field,
      MocMixedRegimeFieldResult,
    ):
      raise TypeError('field must be a MocMixedRegimeFieldResult or None')
    if self.closure is not None and not isinstance(
      self.closure,
      MocMixedRegimeClosureResult,
    ):
      raise TypeError(
        'closure must be a MocMixedRegimeClosureResult or None'
      )
    if self.closure is not None:
      if self.closure.request != self.request:
        raise ValueError('closure must retain the exact planar request')
      if self.field is not None and self.closure.field != self.field:
        raise ValueError('closure must retain the exact returned field')
    if (
      self.control_section_validation is not None
      and self.control_section_validation.section is not None
      and self.control_section is not None
      and self.control_section_validation.section != self.control_section
    ):
      raise ValueError(
        'control_section_validation must retain the exact control_section'
      )
    solver_model = str(self.solver_model)
    if not solver_model:
      raise ValueError('solver_model must be a non-empty string')
    object.__setattr__(self, 'solver_model', solver_model)
    if not isinstance(self.control_section_projection_verified, bool):
      raise TypeError('control_section_projection_verified must be a bool')
    if self.maximum_control_section_projection_residual is not None:
      residual = float(self.maximum_control_section_projection_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'maximum_control_section_projection_residual must be finite and '
          'nonnegative when supplied'
        )
      object.__setattr__(
        self,
        'maximum_control_section_projection_residual',
        residual,
      )
    projection_model = str(self.projection_model)
    if not projection_model:
      raise ValueError('projection_model must be a non-empty string')
    object.__setattr__(self, 'projection_model', projection_model)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether the explicit callback handoff passed all adapter gates."""

    return self.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF

  @property
  def handoff_verified(self) -> bool:
    """Whether the field, section, perimeter, and physical condition agree."""

    return self.converged

  @property
  def field_physical_closure_verified(self) -> bool:
    """Expose the callback field's own local closure claim for diagnostics."""

    return bool(self.field is not None and self.field.physical_closure_verified)

  @property
  def section_is_varying(self) -> bool:
    """Whether the section carries a non-terminal-equivalent scalar state."""

    residual = (
      None
      if self.control_section_validation is None
      else self.control_section_validation.maximum_terminal_state_residual
    )
    return bool(residual is not None and residual > 1.0e-8)

  @property
  def physical_closure_verified(self) -> bool:
    """A callback handoff is not canonical physical mixed-regime closure."""

    return False

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The canonical reflected-MOC downstream free boundary is still open."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    """A subsonic handoff cannot seed a continued supersonic cell."""

    return True

  @property
  def production_claim_allowed(self) -> bool:
    """Keep this research/planner seam below every product claim ceiling."""

    return False

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'handoff_verified': self.handoff_verified,
      'field_physical_closure_verified': self.field_physical_closure_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'solver_model': self.solver_model,
      'control_section_projection_verified': (
        self.control_section_projection_verified
      ),
      'maximum_control_section_projection_residual': (
        self.maximum_control_section_projection_residual
      ),
      'projection_model': self.projection_model,
      'section_is_varying': self.section_is_varying,
      'control_section': (
        None
        if self.control_section is None
        else self.control_section.as_report()
      ),
      'control_section_validation': (
        None
        if self.control_section_validation is None
        else self.control_section_validation.as_report()
      ),
      'perimeter_spec': (
        None
        if self.perimeter_spec is None
        else self.perimeter_spec.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'closure': None if self.closure is None else self.closure.as_report(),
      'claim_status': (
        'explicit-planar-downstream-handoff-only; canonical-reflected-moc-'
        'free-boundary-and-external-validation-pending'
      ),
      'message': self.message,
  }


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarPotentialReference:
  """Built-in research reference for a planar downstream handoff.

  The reference fits the supplied control-section velocity samples to an
  affine potential-flow profile, extends that profile over the explicitly
  supplied perimeter, and solves the resulting nonlinear isentropic
  potential field.  This replaces a callback-only field seam with a
  reproducible numerical reference while keeping the canonical reflected-MOC
  free-boundary claim boundary intact.

  The control-section fit is intentionally a declared model assumption.  It
  is not a free-boundary solve, does not infer perimeter geometry, and cannot
  promote a scalar mixed-regime field into a supersonic chain cell.
  """

  radial_divisions: int = 2
  profile_tolerance: float = 1.0e-8
  position_tolerance_m: float = 1.0e-10
  state_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance_rad: float = 1.0e-8
  normal_flux_tolerance: float = 1.0e-8
  thermodynamic_tolerance: float = 1.0e-8
  potential_tolerance: float = 1.0e-10
  residual_tolerance: float = 1.0e-10
  velocity_tolerance: float = 1.0e-8
  subsonic_margin: float = 1.0e-6
  maximum_iterations: int = 80
  model: str = 'control-section-projected-compressible-potential-reference'

  def __post_init__(self) -> None:
    if (
      isinstance(self.radial_divisions, bool)
      or not isinstance(self.radial_divisions, int)
      or self.radial_divisions < 1
    ):
      raise ValueError('radial_divisions must be a positive integer')
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
    for name, value in (
      ('profile_tolerance', self.profile_tolerance),
      ('position_tolerance_m', self.position_tolerance_m),
      ('state_tolerance', self.state_tolerance),
      ('pressure_tolerance', self.pressure_tolerance),
      ('tangent_tolerance_rad', self.tangent_tolerance_rad),
      ('normal_flux_tolerance', self.normal_flux_tolerance),
      ('thermodynamic_tolerance', self.thermodynamic_tolerance),
      ('potential_tolerance', self.potential_tolerance),
      ('residual_tolerance', self.residual_tolerance),
      ('velocity_tolerance', self.velocity_tolerance),
      ('subsonic_margin', self.subsonic_margin),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if self.subsonic_margin >= 1.0:
      raise ValueError('subsonic_margin must be less than one')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'model', model)

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def solve(
    self,
    request: MocMixedRegimePerimeterRequest,
    control_section: MocMixedRegimeControlSection,
    perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  ) -> MocMixedRegimePlanarSolveResult:
    """Solve one exact request through the built-in reference lane."""

    return solve_mixed_regime_planar_potential_reference(
      request,
      control_section,
      perimeter_spec,
      radial_divisions=self.radial_divisions,
      profile_tolerance=self.profile_tolerance,
      position_tolerance_m=self.position_tolerance_m,
      state_tolerance=self.state_tolerance,
      pressure_tolerance=self.pressure_tolerance,
      tangent_tolerance_rad=self.tangent_tolerance_rad,
      normal_flux_tolerance=self.normal_flux_tolerance,
      thermodynamic_tolerance=self.thermodynamic_tolerance,
      potential_tolerance=self.potential_tolerance,
      residual_tolerance=self.residual_tolerance,
      velocity_tolerance=self.velocity_tolerance,
      subsonic_margin=self.subsonic_margin,
      maximum_iterations=self.maximum_iterations,
      solver_model=self.model,
    )

  def as_report(self) -> dict[str, object]:
    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'radial_divisions': self.radial_divisions,
      'profile_tolerance': self.profile_tolerance,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance_rad': self.tangent_tolerance_rad,
      'normal_flux_tolerance': self.normal_flux_tolerance,
      'thermodynamic_tolerance': self.thermodynamic_tolerance,
      'potential_tolerance': self.potential_tolerance,
      'residual_tolerance': self.residual_tolerance,
      'velocity_tolerance': self.velocity_tolerance,
      'subsonic_margin': self.subsonic_margin,
      'maximum_iterations': self.maximum_iterations,
      'projection_model': 'affine-control-section-potential-extension',
      'claim_status': (
        'control-section-projected-compressible-potential-reference; '
        'canonical-reflected-moc-free-boundary-and-external-validation-pending'
      ),
    }


def _same_points(
  first: tuple[tuple[float, float], ...],
  second: tuple[tuple[float, float], ...],
  tolerance_m: float,
) -> bool:
  return len(first) == len(second) and all(
    hypot(left[0] - right[0], left[1] - right[1]) <= tolerance_m
    for left, right in zip(first, second)
  )


def _failure(
  status: MocMixedRegimePlanarSolveStatus,
  request: MocMixedRegimePerimeterRequest,
  *,
  control_section: MocMixedRegimeControlSection | None = None,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec | None = None,
  control_section_validation: MocMixedRegimeControlSectionResult | None = None,
  field: MocMixedRegimeFieldResult | None = None,
  closure: MocMixedRegimeClosureResult | None = None,
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver',
  control_section_projection_verified: bool = False,
  maximum_control_section_projection_residual: float | None = None,
  projection_model: str = 'none',
  message: str,
) -> MocMixedRegimePlanarSolveResult:
  return MocMixedRegimePlanarSolveResult(
    status=status,
    request=request,
    control_section=control_section,
    perimeter_spec=perimeter_spec,
    control_section_validation=control_section_validation,
    field=field,
    closure=closure,
    solver_model=solver_model,
    control_section_projection_verified=control_section_projection_verified,
    maximum_control_section_projection_residual=(
      maximum_control_section_projection_residual
    ),
    projection_model=projection_model,
    message=message,
  )


def _fit_affine_profile(
  coordinates: tuple[float, ...],
  values: tuple[float, ...],
) -> tuple[float, float, float]:
  """Fit ``value = intercept + slope * coordinate`` and return its residual."""

  if len(coordinates) != len(values) or len(coordinates) < 2:
    raise ValueError('an affine profile requires at least two paired samples')
  coordinate_mean = sum(coordinates) / len(coordinates)
  value_mean = sum(values) / len(values)
  denominator = sum(
    (coordinate - coordinate_mean) ** 2
    for coordinate in coordinates
  )
  if denominator <= 0.0:
    raise ValueError('control-section profile coordinates have zero span')
  slope = sum(
    (coordinate - coordinate_mean) * (value - value_mean)
    for coordinate, value in zip(coordinates, values, strict=True)
  ) / denominator
  intercept = value_mean - slope * coordinate_mean
  residual = max(
    abs(value - (intercept + slope * coordinate))
    for coordinate, value in zip(coordinates, values, strict=True)
  )
  return intercept, slope, residual


def _project_control_section_to_perimeter(
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  *,
  profile_tolerance: float,
  thermodynamic_tolerance: float,
) -> tuple[tuple[MocMixedRegimeFieldSample, ...], float]:
  """Extend a control-section profile with a declared affine potential law."""

  terminal_upstream_state = request.terminal.upstream_state
  if terminal_upstream_state is None:
    raise ValueError('terminal request does not expose its upstream state')
  tangent = (
    -sin(control_section.normal_angle_rad),
    cos(control_section.normal_angle_rad),
  )
  normal = (
    cos(control_section.normal_angle_rad),
    sin(control_section.normal_angle_rad),
  )
  origin = control_section.points_m[0]
  section_coordinates = tuple(
    (point[0] - origin[0]) * tangent[0]
    + (point[1] - origin[1]) * tangent[1]
    for point in control_section.points_m
  )
  gamma = terminal_upstream_state.gamma
  sonic_factor = 0.5 * (gamma - 1.0)
  tangential_velocities: list[float] = []
  normal_velocities: list[float] = []
  for sample in control_section.samples:
    speed = sample.mach / sqrt(
      1.0 + sonic_factor * sample.mach * sample.mach
    )
    velocity = (
      speed * cos(sample.flow_angle_rad),
      speed * sin(sample.flow_angle_rad),
    )
    tangential_velocities.append(
      velocity[0] * tangent[0] + velocity[1] * tangent[1]
    )
    normal_velocities.append(
      velocity[0] * normal[0] + velocity[1] * normal[1]
    )
  tangential_intercept, tangential_slope, tangential_residual = (
    _fit_affine_profile(section_coordinates, tuple(tangential_velocities))
  )
  normal_intercept, normal_slope, normal_residual = _fit_affine_profile(
    section_coordinates,
    tuple(normal_velocities),
  )
  projection_residual = max(tangential_residual, normal_residual)
  if projection_residual > profile_tolerance:
    raise ValueError(
      'control-section velocity profile is not affine within the declared '
      f'projection tolerance: residual={projection_residual}'
    )
  reference_total_pressure = control_section.samples[0].total_pressure_Pa
  total_pressure_residual = max(
    abs(sample.total_pressure_Pa - reference_total_pressure)
    / max(1.0, abs(sample.total_pressure_Pa), abs(reference_total_pressure))
    for sample in control_section.samples
  )
  gamma_residual = max(
    abs(sample.gamma - gamma) / max(1.0, abs(sample.gamma), abs(gamma))
    for sample in control_section.samples
  )
  if max(total_pressure_residual, gamma_residual) > thermodynamic_tolerance:
    raise ValueError(
      'control-section projected potential reference requires uniform total '
      'pressure and gamma: '
      f'total_pressure_residual={total_pressure_residual}, '
      f'gamma_residual={gamma_residual}'
    )

  samples: list[MocMixedRegimeFieldSample] = []
  for point in perimeter_spec.perimeter_points_m:
    displacement = (point[0] - origin[0], point[1] - origin[1])
    coordinate = displacement[0] * tangent[0] + displacement[1] * tangent[1]
    normal_offset = displacement[0] * normal[0] + displacement[1] * normal[1]
    tangential_velocity = (
      tangential_intercept
      + tangential_slope * coordinate
      + normal_slope * normal_offset
    )
    normal_velocity = normal_intercept + normal_slope * coordinate
    velocity = (
      tangential_velocity * tangent[0] + normal_velocity * normal[0],
      tangential_velocity * tangent[1] + normal_velocity * normal[1],
    )
    speed_squared = velocity[0] * velocity[0] + velocity[1] * velocity[1]
    enthalpy_factor = 1.0 - sonic_factor * speed_squared
    if enthalpy_factor <= 0.0:
      raise ValueError(
        'control-section affine potential extension crossed its finite '
        'enthalpy limit at the declared perimeter'
      )
    mach = sqrt(speed_squared / enthalpy_factor)
    if mach <= 0.0 or mach >= 1.0:
      raise ValueError(
        'control-section affine potential extension is not strictly '
        f'subsonic at perimeter point {point}: mach={mach}'
      )
    static_pressure = request.terminal_downstream_total_pressure_Pa / (
      1.0 + sonic_factor * mach * mach
    ) ** (gamma / (gamma - 1.0))
    samples.append(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=mach,
        flow_angle_rad=atan2(velocity[1], velocity[0]),
        static_pressure_Pa=static_pressure,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
    )
  return tuple(samples), projection_residual


def solve_mixed_regime_planar_potential_reference(
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  *,
  radial_divisions: int = 2,
  profile_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  potential_tolerance: float = 1.0e-10,
  residual_tolerance: float = 1.0e-10,
  velocity_tolerance: float = 1.0e-8,
  subsonic_margin: float = 1.0e-6,
  maximum_iterations: int = 80,
  solver_model: str = 'control-section-projected-compressible-potential-reference',
) -> MocMixedRegimePlanarSolveResult:
  """Solve a planar mixed-regime reference from an explicit section profile.

  The perimeter and downstream condition remain caller-owned.  Only the
  scalar boundary samples are generated here, through the explicitly named
  affine potential projection of the control section.  The nonlinear field
  solve and the exact terminal/perimeter seam are then routed through the
  existing planar handoff adapter.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError('control_section must be a MocMixedRegimeControlSection')
  if not isinstance(
    perimeter_spec,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  for name, value in (
    ('profile_tolerance', profile_tolerance),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('normal_flux_tolerance', normal_flux_tolerance),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('potential_tolerance', potential_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('velocity_tolerance', velocity_tolerance),
    ('subsonic_margin', subsonic_margin),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if subsonic_margin >= 1.0:
    raise ValueError('subsonic_margin must be less than one')
  if (
    isinstance(radial_divisions, bool)
    or not isinstance(radial_divisions, int)
    or radial_divisions < 1
  ):
    raise ValueError('radial_divisions must be a positive integer')
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  solver_model = str(solver_model)
  if not solver_model:
    raise ValueError('solver_model must be a non-empty string')
  section_validation = validate_mixed_regime_control_section(
    request,
    control_section,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
  )
  if not section_validation.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.CONTROL_SECTION_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      message=(
        'control-section projected potential reference requires a valid '
        f'control section: {section_validation.message}'
      ),
    )
  try:
    samples, projection_residual = _project_control_section_to_perimeter(
      request,
      control_section,
      perimeter_spec,
      profile_tolerance=profile_tolerance,
      thermodynamic_tolerance=thermodynamic_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocMixedRegimePlanarSolveStatus.CONTROL_SECTION_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      projection_model='affine-control-section-potential-extension',
      message=f'control-section perimeter projection failed: {error}',
    )
  boundary = validate_mixed_regime_boundary(
    request.terminal,
    request.supersonic_patch,
    supersonic_patch_converged=True,
    subsonic_samples=samples,
    perimeter_points_m=perimeter_spec.perimeter_points_m,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
  )
  if not boundary.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      control_section_projection_verified=True,
      maximum_control_section_projection_residual=projection_residual,
      projection_model='affine-control-section-potential-extension',
      message=(
        'projected perimeter failed the exact terminal/patch scalar seam: '
        f'{boundary.message}'
      ),
    )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    perimeter_spec.condition_kind,
    ambient_pressure_Pa=perimeter_spec.ambient_pressure_Pa,
    condition_edge_indices=(
      None
      if not perimeter_spec.condition_edge_indices
      else perimeter_spec.condition_edge_indices
    ),
    condition_sample_indices=(
      None
      if not perimeter_spec.condition_sample_indices
      else perimeter_spec.condition_sample_indices
    ),
    position_tolerance_m=position_tolerance_m,
    tangent_tolerance_rad=tangent_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
  )
  if not condition.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.FIELD_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      control_section_projection_verified=True,
      maximum_control_section_projection_residual=projection_residual,
      projection_model='affine-control-section-potential-extension',
      message=(
        'projected perimeter failed its declared downstream condition: '
        f'{condition.message}'
      ),
    )
  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    position_tolerance_m=position_tolerance_m,
    thermodynamic_tolerance=thermodynamic_tolerance,
    potential_tolerance=potential_tolerance,
    residual_tolerance=residual_tolerance,
    velocity_tolerance=velocity_tolerance,
    subsonic_margin=subsonic_margin,
    radial_divisions=radial_divisions,
    maximum_iterations=maximum_iterations,
    downstream_condition=condition,
  )
  if not field.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.FIELD_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      control_section_projection_verified=True,
      maximum_control_section_projection_residual=projection_residual,
      projection_model='affine-control-section-potential-extension',
      message=f'projected planar potential field failed its gates: {field.message}',
    )
  field = replace(
    field,
    control_section=control_section,
    message=(
      'control-section affine potential projection and nonlinear isentropic '
      'field converged on the explicitly supplied perimeter'
    ),
  )
  result = run_mixed_regime_planar_field_solver(
    request,
    control_section,
    perimeter_spec,
    lambda _request, _section, _specification: field,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
    solver_model=solver_model,
  )
  return replace(
    result,
    control_section_projection_verified=True,
    maximum_control_section_projection_residual=projection_residual,
    projection_model='affine-control-section-potential-extension',
  )


def run_mixed_regime_planar_field_solver(
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  solve_field: MocMixedRegimePlanarFieldSolver,
  *,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver',
) -> MocMixedRegimePlanarSolveResult:
  """Run a future planar downstream solver through an exact seam audit.

  The callback receives the terminal request, an explicit transverse control
  section, and an explicit closed perimeter specification.  It must return a
  complete ``MocMixedRegimeFieldResult`` with the exact request terminal and
  supersonic patch, the exact perimeter geometry, and a converged downstream
  condition matching the specification.  The adapter does not call the
  quasi-1-D reference, infer geometry, fill samples, or promote the result.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection'
    )
  if not isinstance(
    perimeter_spec,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  if not callable(solve_field):
    raise TypeError('solve_field must be callable')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  solver_model = str(solver_model)
  if not solver_model:
    raise ValueError('solver_model must be a non-empty string')

  section_validation = validate_mixed_regime_control_section(
    request,
    control_section,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
  )
  if not section_validation.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.CONTROL_SECTION_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      message=(
        'planar mixed-regime solve requires a valid explicit control section: '
        f'{section_validation.message}'
      ),
    )

  try:
    field = solve_field(request, control_section, perimeter_spec)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SOLVER_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      message=f'planar mixed-regime callback failed: {error}',
    )
  if field is None:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SOLVER_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      message='planar mixed-regime callback returned no field',
    )
  if not isinstance(field, MocMixedRegimeFieldResult):
    return _failure(
      MocMixedRegimePlanarSolveStatus.INVALID_INPUT,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      solver_model=solver_model,
      message=(
        'planar mixed-regime callback must return '
        'MocMixedRegimeFieldResult or None'
      ),
    )

  if field.control_section != control_section:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback did not retain the exact supplied control section; '
        'the downstream field must attest which section it consumed'
      ),
    )

  boundary = field.boundary
  if boundary.terminal != request.terminal:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message='planar field changed the requested terminal shock seam',
    )
  if boundary.supersonic_patch != request.supersonic_patch:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar field did not retain the exact requested supersonic patch '
        'and pressure-loss samples'
      ),
    )
  if not _same_points(
    boundary.perimeter_points_m,
    perimeter_spec.perimeter_points_m,
    position_tolerance_m,
  ):
    return _failure(
      MocMixedRegimePlanarSolveStatus.PERIMETER_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar field did not retain the exact explicitly supplied '
        'downstream perimeter geometry'
      ),
    )
  if not field.converged or not boundary.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.FIELD_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback returned a field without converged field and '
        f'boundary acceptance: {field.message}'
      ),
    )
  condition = field.downstream_condition
  if condition is None:
    return _failure(
      MocMixedRegimePlanarSolveStatus.FIELD_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback must return a field with the validated downstream '
        'condition attached'
      ),
    )
  if condition.boundary != boundary:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback returned a downstream condition for a different '
        'scalar boundary'
      ),
    )
  if condition.condition_kind is not perimeter_spec.condition_kind:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback returned a downstream condition different from the '
        'declared perimeter condition'
      ),
    )
  expected_condition_edges = (
    tuple(range(len(perimeter_spec.perimeter_points_m) - 1))
    if not perimeter_spec.condition_edge_indices
    else perimeter_spec.condition_edge_indices
  )
  expected_condition_samples = (
    tuple(sorted({
      endpoint
      for edge_index in expected_condition_edges
      for endpoint in (edge_index, edge_index + 1)
    }))
    if not perimeter_spec.condition_sample_indices
    else perimeter_spec.condition_sample_indices
  )
  if condition.condition_edge_indices != expected_condition_edges:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback changed the declared downstream condition edge '
        'selection'
      ),
    )
  if condition.condition_sample_indices != expected_condition_samples:
    return _failure(
      MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback changed the declared downstream condition sample '
        'selection'
      ),
    )
  if perimeter_spec.condition_kind in (
    MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
  ):
    ambient_pressure = perimeter_spec.ambient_pressure_Pa
    if ambient_pressure is None:
      return _failure(
        MocMixedRegimePlanarSolveStatus.PERIMETER_FAILURE,
        request,
        control_section=control_section,
        perimeter_spec=perimeter_spec,
        control_section_validation=section_validation,
        field=field,
        solver_model=solver_model,
        message=(
          'the declared pressure-conditioned planar perimeter must provide '
          'ambient_pressure_Pa'
        ),
      )
    selected_pressure_residual = max(
      (
        abs(
          boundary.subsonic_samples[index].static_pressure_Pa
          - ambient_pressure
        )
        for index in expected_condition_samples
      ),
      default=None,
    )
    if selected_pressure_residual is None or selected_pressure_residual > (
      pressure_tolerance * max(1.0, abs(ambient_pressure))
    ):
      return _failure(
        MocMixedRegimePlanarSolveStatus.SEAM_FAILURE,
        request,
        control_section=control_section,
        perimeter_spec=perimeter_spec,
        control_section_validation=section_validation,
        field=field,
        solver_model=solver_model,
        message=(
          'planar field pressure samples do not match the declared '
          f'downstream pressure condition: residual={selected_pressure_residual}'
        ),
      )
  if not condition.converged:
    return _failure(
      MocMixedRegimePlanarSolveStatus.FIELD_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback downstream condition did not converge: '
        f'{condition.message}'
      ),
    )
  if not field.physical_closure_verified:
    return _failure(
      MocMixedRegimePlanarSolveStatus.FIELD_FAILURE,
      request,
      control_section=control_section,
      perimeter_spec=perimeter_spec,
      control_section_validation=section_validation,
      field=field,
      solver_model=solver_model,
      message=(
        'planar callback field did not pass its declared model and physical '
        'condition gates'
      ),
    )

  closure = MocMixedRegimeClosureResult(
    status=MocMixedRegimeClosureStatus.CONVERGED,
    request=request,
    field=field,
    downstream_condition=condition,
    perimeter_spec=perimeter_spec,
    message=(
      'callback-supplied planar field retained the exact terminal, patch, '
      'perimeter, and downstream-condition seams; promotion remains blocked'
    ),
  )
  return MocMixedRegimePlanarSolveResult(
    status=MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF,
    request=request,
    control_section=control_section,
    perimeter_spec=perimeter_spec,
    control_section_validation=section_validation,
    field=field,
    closure=closure,
    solver_model=solver_model,
    message=(
      'explicit control section and perimeter reached the callback-owned '
      'planar handoff; canonical reflected-MOC free-boundary closure and '
      'external validation remain pending'
    ),
  )
