"""Typed scalar handoff for the subsonic side of a planar MOC terminal.

The supersonic MOC lane cannot represent a subsonic downstream state as a
``CharacteristicState``.  This module therefore defines the next, narrower
contract: a caller may provide scalar subsonic samples and an explicitly
closed perimeter after a verified terminal shock.  The validator checks the
shock seam, the open supersonic patch, scalar state validity, pressure
lineage, and perimeter geometry.  It also contains a separately named
compressible isentropic potential-flow reference for that explicit perimeter.

This remains a boundary handoff, not a subsonic characteristic solver.  A
passing scalar handoff still reports ``physical_closure_verified=False`` and
cannot seed a continued shock-cell chain.  The harmonic and compressible
potential reference solvers can inspect the declared scalar field, but
terminal attachment additionally requires the exact validated downstream
condition without changing the supersonic ``CharacteristicState`` type or
inferring a free boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import atan2, cos, exp, hypot, isfinite, log, pi, sin, sqrt
from typing import Callable, Sequence

import numpy as np

from exhaust_plume.models.moc.compression import (
  MocNormalShockTerminalResult,
  MocSubsonicShockBoundaryResult,
)
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocMixedRegimeBoundaryStatus',
  'MocMixedRegimeFieldSample',
  'MocMixedRegimePerimeterRequest',
  'MocMixedRegimeControlSection',
  'MocMixedRegimeControlSectionStatus',
  'MocMixedRegimeControlSectionResult',
  'MocMixedRegimeDownstreamPerimeterSpec',
  'MocMixedRegimeDownstreamConditionKind',
  'MocMixedRegimeDownstreamConditionStatus',
  'MocMixedRegimeDownstreamConditionResult',
  'MocMixedRegimeFreeBoundaryStatus',
  'MocMixedRegimeFreeBoundaryResult',
  'MocMixedRegimeClosureStatus',
  'MocMixedRegimeClosureResult',
  'MocMixedRegimeBoundaryResult',
  'MocMixedRegimeFieldStatus',
  'MocMixedRegimeFieldResult',
  'validate_mixed_regime_boundary',
  'validate_mixed_regime_downstream_condition',
  'solve_mixed_regime_downstream_condition',
  'run_mixed_regime_closure_solver',
  'solve_mixed_regime_subsonic_field',
  'solve_mixed_regime_compressible_potential_field',
  'solve_mixed_regime_downstream_perimeter',
  'validate_mixed_regime_control_section',
  'solve_mixed_regime_downstream_free_boundary',
  'solve_mixed_regime_downstream_free_boundary_from_control_section',
)


class MocMixedRegimeBoundaryStatus(str, Enum):
  """Structured outcome for the scalar mixed-regime boundary handoff."""

  CONVERGED_BOUNDARY_HANDOFF = 'converged_subsonic_boundary_handoff'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'mixed_regime_terminal_failure'
  SUPERSONIC_PATCH_FAILURE = 'supersonic_patch_failure'
  SUBSONIC_FIELD_FAILURE = 'subsonic_field_failure'
  GEOMETRY_FAILURE = 'mixed_regime_geometry_failure'
  PRESSURE_FAILURE = 'mixed_regime_pressure_failure'


class MocMixedRegimeFieldStatus(str, Enum):
  """Outcome for the separate elliptic subsonic field solvers."""

  CONVERGED_ELLIPTIC_FIELD = 'converged_elliptic_subsonic_field'
  CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD = (
    'converged_compressible_potential_subsonic_field'
  )
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FAILURE = 'mixed_regime_boundary_failure'
  GEOMETRY_FAILURE = 'mixed_regime_mesh_geometry_failure'
  TOPOLOGY_FAILURE = 'mixed_regime_mesh_topology_failure'
  THERMODYNAMIC_FAILURE = 'mixed_regime_thermodynamic_failure'
  RESIDUAL_FAILURE = 'mixed_regime_elliptic_residual_failure'
  POTENTIAL_FLOW_FAILURE = 'mixed_regime_potential_flow_failure'


class MocMixedRegimeDownstreamConditionKind(str, Enum):
  """Physical condition that a subsonic downstream perimeter claims."""

  SLIP_WALL = 'slip-wall'
  AMBIENT_PRESSURE_FREE_BOUNDARY = 'ambient-pressure-free-boundary'
  PRESSURE_OUTFLOW_SECTION = 'prescribed-pressure-outflow-section'
####


class MocMixedRegimeDownstreamConditionStatus(str, Enum):
  """Outcome of the physical downstream-condition seam."""

  CONVERGED = 'converged-downstream-condition'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FAILURE = 'downstream-boundary-failure'
  TANGENCY_FAILURE = 'downstream-tangency-failure'
  PRESSURE_FAILURE = 'downstream-pressure-condition-failure'
  SOLVER_FAILURE = 'downstream-condition-solver-failure'
####


class MocMixedRegimeFreeBoundaryStatus(str, Enum):
  """Outcome for a solver-owned downstream free-boundary reference."""

  CONVERGED_REFERENCE = 'converged-solver-owned-free-boundary-reference'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'free-boundary-terminal-failure'
  CONTROL_SECTION_FAILURE = 'free-boundary-control-section-failure'
  PRESSURE_UNREACHABLE = 'free-boundary-pressure-unreachable'
  BRACKET_FAILURE = 'free-boundary-height-bracket-failure'
  GEOMETRY_FAILURE = 'free-boundary-geometry-failure'
  CONDITION_FAILURE = 'free-boundary-condition-failure'
  FIELD_FAILURE = 'free-boundary-field-failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFieldSample:
  """One scalar state sample on a proposed subsonic perimeter.

  This deliberately contains no ``CharacteristicState``.  The scalar fields
  are sufficient for seam and thermodynamic checks, but not for entering the
  supersonic compatibility network.
  """

  point_m: tuple[float, float]
  mach: float
  flow_angle_rad: float
  static_pressure_Pa: float
  total_pressure_Pa: float
  gamma: float

  def __post_init__(self) -> None:
    try:
      point = (float(self.point_m[0]), float(self.point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('mixed-regime sample point must contain two finite coordinates') from None
    if not all(isfinite(value) for value in point):
      raise ValueError('mixed-regime sample point must contain two finite coordinates')
    values = (
      ('mach', self.mach, 0.0, 1.0),
      ('flow_angle_rad', self.flow_angle_rad, None, None),
      ('static_pressure_Pa', self.static_pressure_Pa, 0.0, None),
      ('total_pressure_Pa', self.total_pressure_Pa, 0.0, None),
      ('gamma', self.gamma, 1.0, None),
    )
    for name, raw_value, lower, upper in values:
      value = float(raw_value)
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      if lower is not None and value <= lower:
        raise ValueError(f'{name} must be greater than {lower}')
      if upper is not None and value >= upper:
        raise ValueError(f'{name} must be less than {upper}')
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'mach', float(self.mach))
    object.__setattr__(self, 'flow_angle_rad', float(self.flow_angle_rad))
    object.__setattr__(self, 'static_pressure_Pa', float(self.static_pressure_Pa))
    object.__setattr__(self, 'total_pressure_Pa', float(self.total_pressure_Pa))
    object.__setattr__(self, 'gamma', float(self.gamma))


MocMixedRegimeTerminal = MocNormalShockTerminalResult | MocSubsonicShockBoundaryResult


class MocMixedRegimeClosureStatus(str, Enum):
  """Outcome of a solver callback submitted for terminal closure."""

  CONVERGED = 'converged_mixed_regime_closure'
  INVALID_INPUT = 'invalid_input'
  SOLVER_FAILURE = 'mixed_regime_closure_solver_failure'
  SEAM_FAILURE = 'mixed_regime_closure_seam_failure'
  FIELD_FAILURE = 'mixed_regime_closure_field_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimePerimeterRequest:
  """Solver-owned data required to close a subsonic terminal region.

  The terminal shock and the open supersonic patch provide the downstream
  scalar seam, but they do not determine the remaining subsonic perimeter.
  This request exposes the data a mixed-regime solver must consume while
  deliberately carrying no guessed perimeter points.  In particular, the
  open supersonic zone is evidence for the upstream seam, never a substitute
  for the downstream boundary condition.
  """

  terminal: MocMixedRegimeTerminal
  terminal_point_m: tuple[float, float]
  terminal_downstream_mach: float
  terminal_downstream_flow_angle_rad: float
  terminal_downstream_pressure_Pa: float
  terminal_downstream_total_pressure_Pa: float
  terminal_total_pressure_ratio: float
  supersonic_patch: tuple[MocPostShockBoundaryState, ...]
  required_boundary_conditions: tuple[str, ...] = (
    'explicitly closed downstream perimeter',
    'terminal scalar seam continuity',
    'no total-pressure gain over the terminal shock',
  )
  source: str = 'solver-owned-terminal-shock-mixed-regime-handoff'

  def __post_init__(self) -> None:
    if not isinstance(
        self.terminal,
        (MocNormalShockTerminalResult, MocSubsonicShockBoundaryResult),
    ):
      raise TypeError('terminal must be a normal-shock or subsonic boundary result')
    if not self.terminal.converged or not self.terminal.subsonic:
      raise ValueError('terminal must be a converged subsonic boundary result')
    terminal_values = (
      self.terminal.shock_point_m,
      self.terminal.downstream_mach,
      self.terminal.downstream_flow_angle_rad,
      self.terminal.downstream_pressure_Pa,
      self.terminal.downstream_total_pressure_Pa,
      self.terminal.total_pressure_ratio,
    )
    if any(value is None for value in terminal_values):
      raise ValueError(
        'terminal must expose complete scalar seam values for the perimeter request'
      )
    expected_point, expected_mach, expected_angle, expected_pressure, expected_total_pressure, expected_ratio = terminal_values
    try:
      point = (float(self.terminal_point_m[0]), float(self.terminal_point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('terminal_point_m must contain two finite coordinates') from None
    if not all(isfinite(value) for value in point):
      raise ValueError('terminal_point_m must contain two finite coordinates')
    assert expected_point is not None
    assert expected_mach is not None
    assert expected_angle is not None
    assert expected_pressure is not None
    assert expected_total_pressure is not None
    assert expected_ratio is not None
    if (
      abs(point[0] - expected_point[0]) > 1.0e-10
      or abs(point[1] - expected_point[1]) > 1.0e-10
    ):
      raise ValueError('terminal_point_m does not match the terminal shock point')
    for name, value, lower in (
      ('terminal_downstream_mach', self.terminal_downstream_mach, 0.0),
      ('terminal_downstream_pressure_Pa', self.terminal_downstream_pressure_Pa, 0.0),
      ('terminal_downstream_total_pressure_Pa', self.terminal_downstream_total_pressure_Pa, 0.0),
      ('terminal_total_pressure_ratio', self.terminal_total_pressure_ratio, 0.0),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= lower:
        raise ValueError(f'{name} must be finite and greater than {lower}')
    if self.terminal_downstream_mach >= 1.0:
      raise ValueError('terminal_downstream_mach must be subsonic')
    if self.terminal_total_pressure_ratio >= 1.0:
      raise ValueError('terminal_total_pressure_ratio must show strict total-pressure loss')
    angle = float(self.terminal_downstream_flow_angle_rad)
    if not isfinite(angle):
      raise ValueError('terminal_downstream_flow_angle_rad must be finite')
    scalar_pairs = (
      ('terminal_downstream_mach', self.terminal_downstream_mach, expected_mach),
      ('terminal_downstream_flow_angle_rad', angle, expected_angle),
      ('terminal_downstream_pressure_Pa', self.terminal_downstream_pressure_Pa, expected_pressure),
      ('terminal_downstream_total_pressure_Pa', self.terminal_downstream_total_pressure_Pa, expected_total_pressure),
      ('terminal_total_pressure_ratio', self.terminal_total_pressure_ratio, expected_ratio),
    )
    for name, supplied, expected in scalar_pairs:
      supplied_value = float(supplied)
      expected_value = float(expected)
      if abs(supplied_value - expected_value) > 1.0e-10 * max(
        1.0,
        abs(supplied_value),
        abs(expected_value),
      ):
        raise ValueError(f'{name} does not match the terminal shock result')
    patch = tuple(self.supersonic_patch)
    if not patch:
      raise ValueError('supersonic_patch must contain at least one boundary state')
    if any(not isinstance(sample, MocPostShockBoundaryState) for sample in patch):
      raise TypeError('supersonic_patch must contain MocPostShockBoundaryState values')
    if any(sample.state.mach <= 1.0 for sample in patch):
      raise ValueError('supersonic_patch must contain only supersonic states')
    conditions = tuple(str(condition) for condition in self.required_boundary_conditions)
    if not conditions:
      raise ValueError('required_boundary_conditions must not be empty')
    object.__setattr__(self, 'terminal_point_m', point)
    object.__setattr__(self, 'terminal_downstream_mach', float(self.terminal_downstream_mach))
    object.__setattr__(self, 'terminal_downstream_flow_angle_rad', angle)
    object.__setattr__(self, 'terminal_downstream_pressure_Pa', float(self.terminal_downstream_pressure_Pa))
    object.__setattr__(self, 'terminal_downstream_total_pressure_Pa', float(self.terminal_downstream_total_pressure_Pa))
    object.__setattr__(self, 'terminal_total_pressure_ratio', float(self.terminal_total_pressure_ratio))
    object.__setattr__(self, 'supersonic_patch', patch)
    object.__setattr__(self, 'required_boundary_conditions', conditions)
  ####

  @property
  def perimeter_supplied(self) -> bool:
    """Whether a downstream geometry was supplied to this request."""

    return False
  ####

  @property
  def open_supersonic_zone_is_a_perimeter(self) -> bool:
    """The open supersonic patch cannot close the subsonic region."""

    return False
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': 'mixed-regime-perimeter-required',
      'source': self.source,
      'terminal': self.terminal.as_report(),
      'perimeter_supplied': self.perimeter_supplied,
      'open_supersonic_zone_is_a_perimeter': self.open_supersonic_zone_is_a_perimeter,
      'terminal_point_m': self.terminal_point_m,
      'terminal_downstream_mach': self.terminal_downstream_mach,
      'terminal_downstream_flow_angle_rad': self.terminal_downstream_flow_angle_rad,
      'terminal_downstream_pressure_Pa': self.terminal_downstream_pressure_Pa,
      'terminal_downstream_total_pressure_Pa': self.terminal_downstream_total_pressure_Pa,
      'terminal_total_pressure_ratio': self.terminal_total_pressure_ratio,
      'supersonic_patch_sample_count': len(self.supersonic_patch),
      'supersonic_patch_points_m': tuple(sample.point_m for sample in self.supersonic_patch),
      'supersonic_patch_mach': tuple(sample.state.mach for sample in self.supersonic_patch),
      'supersonic_patch_downstream_total_pressure_Pa': tuple(
        sample.downstream_total_pressure_Pa for sample in self.supersonic_patch
      ),
      'required_boundary_conditions': self.required_boundary_conditions,
      'message': (
        'the mixed-regime solver must provide the closed downstream perimeter; '
        'no geometry was inferred from the open supersonic zone'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeControlSection:
  """An explicit transverse section carrying scalar subsonic flux data.

  A terminal shock point does not contain an area or a mass-flow handoff.  A
  downstream solver must therefore provide a finite section before a
  quasi-one-dimensional reference can use an area relation.  The section is
  deliberately scalar: it is not a ``CharacteristicState`` boundary and it
  cannot be used to continue the supersonic MOC chain.

  Points are ordered along the section tangent.  ``normal_angle_rad`` points
  in the positive-flow direction through the section, so the section may be
  checked for positive normal flux without assuming that it is vertical.
  """

  points_m: tuple[tuple[float, float], ...]
  samples: tuple[MocMixedRegimeFieldSample, ...]
  normal_angle_rad: float
  source: str = 'solver-owned-mixed-regime-control-section'

  def __post_init__(self) -> None:
    try:
      points = tuple(
        (float(point[0]), float(point[1]))
        for point in self.points_m
      )
      samples = tuple(self.samples)
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError(
        'control-section points and samples must be finite iterables'
      ) from error
    if len(points) < 2:
      raise ValueError('control section requires at least two points')
    if len(points) != len(samples):
      raise ValueError('control-section points and samples must have equal lengths')
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('control-section points must be finite')
    if any(
      not isinstance(sample, MocMixedRegimeFieldSample)
      for sample in samples
    ):
      raise TypeError(
        'control-section samples must contain MocMixedRegimeFieldSample values'
      )
    if any(
      hypot(sample.point_m[0] - point[0], sample.point_m[1] - point[1])
      > 1.0e-10
      for sample, point in zip(samples, points, strict=True)
    ):
      raise ValueError('control-section sample points must match its geometry')
    normal_angle = float(self.normal_angle_rad)
    if not isfinite(normal_angle):
      raise ValueError('normal_angle_rad must be finite')
    tangent = (-sin(normal_angle), cos(normal_angle))
    normal = (cos(normal_angle), sin(normal_angle))
    normal_coordinates = tuple(
      point[0] * normal[0] + point[1] * normal[1]
      for point in points
    )
    tangent_coordinates = tuple(
      point[0] * tangent[0] + point[1] * tangent[1]
      for point in points
    )
    if max(normal_coordinates) - min(normal_coordinates) > 1.0e-10:
      raise ValueError('control-section points must lie on one straight section')
    if any(
      second <= first + 1.0e-10
      for first, second in zip(tangent_coordinates, tangent_coordinates[1:])
    ):
      raise ValueError(
        'control-section points must be strictly ordered along the section tangent'
      )
    if any(
      hypot(second[0] - first[0], second[1] - first[1]) <= 1.0e-10
      for first, second in zip(points, points[1:])
    ):
      raise ValueError('control-section points must not contain zero-length segments')
    source = str(self.source)
    if not source:
      raise ValueError('control-section source must be non-empty')
    object.__setattr__(self, 'points_m', points)
    object.__setattr__(self, 'samples', samples)
    object.__setattr__(self, 'normal_angle_rad', normal_angle)
    object.__setattr__(self, 'source', source)
  ####

  @property
  def section_measure_m(self) -> float:
    """Return the planar section measure used by the area reference."""

    return sum(
      hypot(second[0] - first[0], second[1] - first[1])
      for first, second in zip(self.points_m, self.points_m[1:])
    )
  ####

  @property
  def normal_flux_factors(self) -> tuple[float, ...]:
    """Return the positive-flow projection for every scalar sample."""

    return tuple(
      cos(sample.flow_angle_rad - self.normal_angle_rad)
      for sample in self.samples
    )
  ####

  @property
  def mass_flux_proxy(self) -> float:
    """Return a total-state-scaled planar mass-flux integral.

    The common gas constant/total-temperature factor is intentionally omitted;
    the value is suitable for continuity and refinement comparisons inside a
    single declared reference case, not for an absolute mass-flow claim.
    """

    densities = tuple(
      sample.total_pressure_Pa
      * _subsonic_mass_flux_factor(sample.mach, sample.gamma)
      * projection
      for sample, projection in zip(self.samples, self.normal_flux_factors, strict=True)
    )
    return sum(
      0.5 * (first + second) * length
      for first, second, length in zip(
        densities,
        densities[1:],
        (
          hypot(second[0] - first[0], second[1] - first[1])
          for first, second in zip(self.points_m, self.points_m[1:])
        ),
      )
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'source': self.source,
      'points_m': self.points_m,
      'sample_count': len(self.samples),
      'normal_angle_rad': self.normal_angle_rad,
      'section_measure_m': self.section_measure_m,
      'normal_flux_factors': self.normal_flux_factors,
      'mass_flux_proxy': self.mass_flux_proxy,
      'mach': tuple(sample.mach for sample in self.samples),
      'flow_angle_rad': tuple(sample.flow_angle_rad for sample in self.samples),
      'static_pressure_Pa': tuple(
        sample.static_pressure_Pa for sample in self.samples
      ),
      'total_pressure_Pa': tuple(
        sample.total_pressure_Pa for sample in self.samples
      ),
      'claim_status': (
        'explicit-scalar-mixed-regime-control-section; '
        'not-a-characteristic-chain-boundary'
      ),
    }
  ####


class MocMixedRegimeControlSectionStatus(str, Enum):
  """Outcome of validating a scalar downstream control section."""

  CONVERGED = 'converged-subsonic-control-section'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'control-section-terminal-failure'
  GEOMETRY_FAILURE = 'control-section-geometry-failure'
  STATE_FAILURE = 'control-section-state-failure'
  FLUX_FAILURE = 'control-section-flux-failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeControlSectionResult:
  """Independent acceptance evidence for one explicit flux section.

  This result is a boundary-input audit only.  Even a converged section has
  ``physical_closure_verified=False`` and cannot promote a terminal or seed a
  continued supersonic cell.
  """

  status: MocMixedRegimeControlSectionStatus
  request: MocMixedRegimePerimeterRequest | None
  section: MocMixedRegimeControlSection | None
  section_measure_m: float | None
  mass_flux_proxy: float | None
  minimum_normal_flux_factor: float | None
  maximum_total_pressure_gain_Pa: float | None
  maximum_isentropic_residual: float | None
  minimum_downstream_terminal_margin_m: float | None
  maximum_terminal_state_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedRegimeControlSectionStatus):
      raise TypeError('status must be a MocMixedRegimeControlSectionStatus')
    if self.request is not None and not isinstance(
      self.request,
      MocMixedRegimePerimeterRequest,
    ):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest or None')
    if self.section is not None and not isinstance(
      self.section,
      MocMixedRegimeControlSection,
    ):
      raise TypeError('section must be a MocMixedRegimeControlSection or None')
    for name in (
      'section_measure_m',
      'mass_flux_proxy',
      'minimum_normal_flux_factor',
      'maximum_total_pressure_gain_Pa',
      'maximum_isentropic_residual',
      'minimum_downstream_terminal_margin_m',
      'maximum_terminal_state_residual',
    ):
      value = getattr(self, name)
      if value is not None and not isfinite(float(value)):
        raise ValueError(f'{name} must be finite when supplied')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeControlSectionStatus.CONVERGED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'request_terminal_point_m': (
        None if self.request is None else self.request.terminal_point_m
      ),
      'section': None if self.section is None else self.section.as_report(),
      'section_measure_m': self.section_measure_m,
      'mass_flux_proxy': self.mass_flux_proxy,
      'minimum_normal_flux_factor': self.minimum_normal_flux_factor,
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'maximum_isentropic_residual': self.maximum_isentropic_residual,
      'minimum_downstream_terminal_margin_m': self.minimum_downstream_terminal_margin_m,
      'maximum_terminal_state_residual': self.maximum_terminal_state_residual,
      'claim_status': (
        'control-section-input-audit-only; downstream-2d-mixed-regime-solve-pending'
      ),
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeDownstreamPerimeterSpec:
  """An explicit scalar perimeter and its declared downstream condition.

  The terminal solver owns the shock seam, but it does not own the remaining
  subsonic geometry.  This value object lets a downstream solver make that
  geometry and condition reproducible without putting it back into
  :class:`MocMixedRegimePerimeterRequest` or inferring it from an open
  supersonic patch.  The resulting field is still the separately named
  elliptic/isentrope reference model; this specification is not a canonical
  free-boundary closure.
  """

  perimeter_points_m: tuple[tuple[float, float], ...]
  condition_kind: MocMixedRegimeDownstreamConditionKind
  ambient_pressure_Pa: float | None = None
  model: str = 'explicit-downstream-perimeter-reference'
  condition_edge_indices: tuple[int, ...] = ()
  condition_sample_indices: tuple[int, ...] = ()

  def __post_init__(self) -> None:
    try:
      points = tuple(
        (float(point[0]), float(point[1]))
        for point in self.perimeter_points_m
      )
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError(
        'perimeter_points_m must contain two-coordinate numeric points'
      ) from error
    if len(points) < 4:
      raise ValueError('perimeter_points_m must contain at least four points')
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('perimeter_points_m must contain finite points')
    if hypot(
      points[-1][0] - points[0][0],
      points[-1][1] - points[0][1],
    ) > 1.0e-10:
      raise ValueError('perimeter_points_m must be explicitly closed')
    if any(
      hypot(second[0] - first[0], second[1] - first[1]) <= 1.0e-10
      for first, second in zip(points[:-1], points[1:], strict=True)
    ):
      raise ValueError('perimeter_points_m must not contain zero-length segments')
    if not isinstance(
      self.condition_kind,
      MocMixedRegimeDownstreamConditionKind,
    ):
      raise TypeError(
        'condition_kind must be a MocMixedRegimeDownstreamConditionKind'
      )
    ambient_pressure = self.ambient_pressure_Pa
    if ambient_pressure is not None:
      ambient_pressure = float(ambient_pressure)
      if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
        raise ValueError(
          'ambient_pressure_Pa must be finite and positive when supplied'
        )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    try:
      condition_edges = tuple(self.condition_edge_indices)
      condition_samples = tuple(self.condition_sample_indices)
    except TypeError as error:
      raise ValueError(
        'condition_edge_indices and condition_sample_indices must be iterable'
      ) from error
    for name, indices, upper in (
      ('condition_edge_indices', condition_edges, len(points) - 2),
      ('condition_sample_indices', condition_samples, len(points) - 1),
    ):
      if any(
        isinstance(index, bool)
        or not isinstance(index, int)
        or index < 0
        or index > upper
        for index in indices
      ):
        raise ValueError(
          f'{name} must contain integer indices in the explicit perimeter range'
        )
      if len(set(indices)) != len(indices):
        raise ValueError(f'{name} must not contain duplicate indices')
    object.__setattr__(self, 'perimeter_points_m', points)
    object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'condition_edge_indices', condition_edges)
    object.__setattr__(self, 'condition_sample_indices', condition_samples)
  ####

  @property
  def sample_count(self) -> int:
    """Number of scalar boundary samples requested from the solver."""

    return len(self.perimeter_points_m)
  ####

  def as_report(self) -> dict[str, object]:
    """Return geometry, condition, and reference-model provenance."""

    return {
      'model': self.model,
      'perimeter_points_m': self.perimeter_points_m,
      'sample_count': self.sample_count,
      'condition_kind': self.condition_kind.value,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'condition_edge_indices': self.condition_edge_indices,
      'condition_sample_indices': self.condition_sample_indices,
      'claim_status': (
        'explicit-downstream-perimeter-reference; canonical-free-boundary-'
        'perimeter-not-inferred'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeClosureResult:
  """Acceptance result for a callback-supplied subsonic terminal field."""

  status: MocMixedRegimeClosureStatus
  request: MocMixedRegimePerimeterRequest
  field: 'MocMixedRegimeFieldResult | None' = None
  message: str = ''
  downstream_condition: 'MocMixedRegimeDownstreamConditionResult | None' = None
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeClosureStatus.CONVERGED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return bool(self.converged and self.field is not None and self.field.physical_closure_verified)
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """A mixed-regime closure is a terminal stop, not a supersonic seed."""

    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'field': None if self.field is None else self.field.as_report(),
      'request': self.request.as_report(),
      'downstream_condition': (
        None
        if self.downstream_condition is None
        else self.downstream_condition.as_report()
      ),
      'perimeter_spec': (
        None
        if self.perimeter_spec is None
        else self.perimeter_spec.as_report()
      ),
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeBoundaryResult:
  """Validation result for a scalar subsonic perimeter handoff.

  ``converged`` means that the handoff itself passed.  It intentionally does
  not mean that a subsonic field was solved: ``physical_closure_verified`` and
  ``mixed_regime_field_complete`` remain false until a future solver supplies
  and validates a real subsonic mesh.
  """

  status: MocMixedRegimeBoundaryStatus
  terminal: MocMixedRegimeTerminal | None
  supersonic_patch_sample_count: int
  subsonic_samples: tuple[MocMixedRegimeFieldSample, ...]
  perimeter_points_m: tuple[tuple[float, float], ...]
  supersonic_patch_verified: bool
  subsonic_state_samples_verified: bool
  terminal_continuity_verified: bool
  perimeter_geometry_verified: bool
  total_pressure_lineage_verified: bool
  maximum_terminal_mach_residual: float | None
  maximum_terminal_flow_angle_residual_rad: float | None
  maximum_terminal_static_pressure_residual_Pa: float | None
  maximum_terminal_total_pressure_residual_Pa: float | None
  maximum_total_pressure_gain_Pa: float | None
  message: str = ''
  supersonic_patch: tuple[MocPostShockBoundaryState, ...] = ()

  def __post_init__(self) -> None:
    patch = tuple(self.supersonic_patch)
    if any(not isinstance(sample, MocPostShockBoundaryState) for sample in patch):
      raise TypeError(
        'supersonic_patch must contain MocPostShockBoundaryState values'
      )
    object.__setattr__(self, 'supersonic_patch', patch)

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF

  @property
  def mixed_regime_field_complete(self) -> bool:
    """Whether a subsonic characteristic/finite-volume field was supplied."""

    return False

  @property
  def physical_closure_verified(self) -> bool:
    """A scalar perimeter handoff is not physical cell closure."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  def as_report(self) -> dict[str, object]:
    terminal_report = None if self.terminal is None else self.terminal.as_report()
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'supersonic_patch_sample_count': self.supersonic_patch_sample_count,
      'subsonic_sample_count': len(self.subsonic_samples),
      'perimeter_sample_count': len(self.perimeter_points_m),
      'supersonic_patch_verified': self.supersonic_patch_verified,
      'subsonic_state_samples_verified': self.subsonic_state_samples_verified,
      'terminal_continuity_verified': self.terminal_continuity_verified,
      'perimeter_geometry_verified': self.perimeter_geometry_verified,
      'total_pressure_lineage_verified': self.total_pressure_lineage_verified,
      'maximum_terminal_mach_residual': self.maximum_terminal_mach_residual,
      'maximum_terminal_flow_angle_residual_rad': self.maximum_terminal_flow_angle_residual_rad,
      'maximum_terminal_static_pressure_residual_Pa': self.maximum_terminal_static_pressure_residual_Pa,
      'maximum_terminal_total_pressure_residual_Pa': self.maximum_terminal_total_pressure_residual_Pa,
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'supersonic_patch_points_m': [
        list(sample.point_m) for sample in self.supersonic_patch
      ],
      'terminal': terminal_report,
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocMixedRegimeDownstreamConditionResult:
  """Acceptance result for a scalar perimeter's physical boundary condition.

  The scalar perimeter validator checks the shock seam and pressure lineage.
  This narrower result adds the downstream kinematic/pressure condition that
  the perimeter itself must satisfy before a mixed-regime field can be called
  physically bounded.  A prescribed-pressure outflow section intentionally
  checks pressure without claiming a slip-wall/free-boundary tangency.  The
  result remains separate from the harmonic reference-field solve and never
  creates a subsonic ``CharacteristicState``.
  """

  status: MocMixedRegimeDownstreamConditionStatus
  condition_kind: MocMixedRegimeDownstreamConditionKind | None
  boundary: MocMixedRegimeBoundaryResult | None
  tangent_residuals_rad: tuple[float, ...]
  pressure_residuals_Pa: tuple[float, ...]
  maximum_tangent_residual_rad: float | None
  maximum_pressure_residual_Pa: float | None
  tangency_condition_verified: bool
  pressure_condition_verified: bool
  message: str = ''
  condition_edge_indices: tuple[int, ...] = ()
  condition_sample_indices: tuple[int, ...] = ()

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeDownstreamConditionStatus.CONVERGED

  @property
  def physical_condition_verified(self) -> bool:
    return self.converged

  @property
  def tangency_condition_applicable(self) -> bool:
    """Whether the declared condition requires flow tangency."""

    return self.condition_kind in (
      MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
      MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A boundary condition is not a resolved supersonic chain handoff."""

    return True

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_condition_verified': self.physical_condition_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'condition_kind': (
        None if self.condition_kind is None else self.condition_kind.value
      ),
      'tangent_sample_count': len(self.tangent_residuals_rad),
      'pressure_sample_count': len(self.pressure_residuals_Pa),
      'maximum_tangent_residual_rad': self.maximum_tangent_residual_rad,
      'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      'tangency_condition_applicable': self.tangency_condition_applicable,
      'tangency_condition_verified': self.tangency_condition_verified,
      'pressure_condition_verified': self.pressure_condition_verified,
      'condition_edge_indices': self.condition_edge_indices,
      'condition_sample_indices': self.condition_sample_indices,
      'boundary': None if self.boundary is None else self.boundary.as_report(),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFieldResult:
  """A mesh-backed elliptic continuation of a scalar subsonic perimeter.

  The harmonic reference and the separately named compressible potential
  reference use a conservative scalar model for the subsonic side.  The
  former harmonically extends primitive fields, while the latter solves a
  nonlinear isentropic potential equation on the same explicit radial mesh.
  Both remain in a separate elliptic lane, not a supersonic MOC field; their
  model name and residuals remain in every report.

  ``model_closure_verified`` means that this explicitly declared
  elliptic/isentrope model closed its supplied boundary and passed its local
  conservation and thermodynamic gates.  ``physical_closure_verified`` is
  stricter: the model must also carry the exact downstream condition result
  that passed the perimeter's physical tangency/pressure gate.  Neither is
  external validation of the plume or permission to expose a public product
  provider.
  """

  status: MocMixedRegimeFieldStatus
  boundary: MocMixedRegimeBoundaryResult
  nodes: tuple[MocMixedRegimeFieldSample, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  interior_point_m: tuple[float, float] | None
  maximum_thermodynamic_residual: float | None
  maximum_harmonic_residual: float | None
  maximum_velocity_divergence_residual: float | None
  minimum_mach: float | None
  maximum_mach: float | None
  model: str = 'elliptic-isentropic-subsonic-reference'
  radial_divisions: int = 1
  message: str = ''
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None = None
  maximum_mass_conservation_residual: float | None = None
  maximum_boundary_velocity_residual: float | None = None
  potential_circulation_residual: float | None = None
  nonlinear_iteration_count: int = 0
  nonlinear_update_residual: float | None = None
  velocity_potential: tuple[float, ...] = ()
  free_boundary_pressure_residual_Pa: float | None = None
  free_boundary_tangent_residual_rad: float | None = None
  centerline_tangent_residual_rad: float | None = None
  outlet_pressure_residual_Pa: float | None = None
  free_boundary_geometry_residual_m: float | None = None
  control_section: MocMixedRegimeControlSection | None = None
  maximum_boundary_normal_velocity_residual: float | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.radial_divisions, bool)
      or not isinstance(self.radial_divisions, int)
      or self.radial_divisions < 1
    ):
      raise ValueError('radial_divisions must be a positive integer')
    if (
      isinstance(self.nonlinear_iteration_count, bool)
      or not isinstance(self.nonlinear_iteration_count, int)
      or self.nonlinear_iteration_count < 0
    ):
      raise ValueError('nonlinear_iteration_count must be a nonnegative integer')
    potential = tuple(float(value) for value in self.velocity_potential)
    if any(not isfinite(value) for value in potential):
      raise ValueError('velocity_potential must contain finite values')
    object.__setattr__(self, 'velocity_potential', potential)
    if self.downstream_condition is not None:
      if not isinstance(
        self.downstream_condition,
        MocMixedRegimeDownstreamConditionResult,
      ):
        raise TypeError(
          'downstream_condition must be a '
          'MocMixedRegimeDownstreamConditionResult or None'
        )
      if self.downstream_condition.boundary != self.boundary:
        raise ValueError(
          'downstream_condition must retain the exact scalar boundary'
        )
    if self.control_section is not None and not isinstance(
      self.control_section,
      MocMixedRegimeControlSection,
    ):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection or None'
      )
    if self.maximum_boundary_normal_velocity_residual is not None:
      residual = float(self.maximum_boundary_normal_velocity_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'maximum_boundary_normal_velocity_residual must be finite and '
          'nonnegative when supplied'
        )
      object.__setattr__(
        self,
        'maximum_boundary_normal_velocity_residual',
        residual,
      )

  @property
  def converged(self) -> bool:
    return self.status in (
      MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD,
      MocMixedRegimeFieldStatus.CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD,
    )

  @property
  def node_count(self) -> int:
    return len(self.nodes)

  @property
  def cell_count(self) -> int:
    return len(self.cells)

  @property
  def mixed_regime_field_complete(self) -> bool:
    return self.converged and self.physical_closure_verified

  @property
  def model_closure_verified(self) -> bool:
    """Whether the declared mesh/reference model passed its local gates."""

    mesh_gates = (
      self.converged
      and self.boundary.converged
      and self.topology.connected
      and self.topology.forms_closed_zone
      and not self.topology.nonmanifold_edge_count
      and self.maximum_thermodynamic_residual is not None
      and self.maximum_thermodynamic_residual <= 1.0e-8
    )
    if self.model == 'solver-owned-subsonic-free-boundary-reference':
      pressure_scale = max(
        1.0,
        max(
          (abs(sample.static_pressure_Pa) for sample in self.boundary.subsonic_samples),
          default=1.0,
        ),
      )
      return bool(
        mesh_gates
        and self.free_boundary_pressure_residual_Pa is not None
        and self.free_boundary_tangent_residual_rad is not None
        and self.centerline_tangent_residual_rad is not None
        and self.outlet_pressure_residual_Pa is not None
        and self.free_boundary_geometry_residual_m is not None
        and self.maximum_mass_conservation_residual is not None
        and self.free_boundary_pressure_residual_Pa <= 1.0e-8 * pressure_scale
        and self.outlet_pressure_residual_Pa <= 1.0e-8 * pressure_scale
        and self.free_boundary_tangent_residual_rad <= 1.0e-8
        and self.centerline_tangent_residual_rad <= 1.0e-8
        and self.free_boundary_geometry_residual_m <= 1.0e-8
        and self.maximum_mass_conservation_residual <= 1.0e-8
      )
    if self.model == 'compressible-isentropic-potential-reference':
      tangency_condition_required = bool(
        self.downstream_condition is not None
        and self.downstream_condition.tangency_condition_applicable
      )
      return bool(
        mesh_gates
        and self.maximum_mass_conservation_residual is not None
        and self.maximum_boundary_velocity_residual is not None
        and self.potential_circulation_residual is not None
        and self.nonlinear_update_residual is not None
        and len(self.velocity_potential) == self.node_count
        and self.maximum_mass_conservation_residual <= 1.0e-8
        and self.maximum_boundary_velocity_residual <= 1.0e-8
        and self.potential_circulation_residual <= 1.0e-8
        and self.nonlinear_update_residual <= 1.0e-8
        and (
          not tangency_condition_required
          or (
            self.maximum_boundary_normal_velocity_residual is not None
            and self.maximum_boundary_normal_velocity_residual <= 1.0e-8
          )
        )
      )
    return bool(
      mesh_gates
      and self.maximum_harmonic_residual is not None
      and self.maximum_velocity_divergence_residual is not None
      and self.maximum_harmonic_residual <= 1.0e-12
      and self.maximum_velocity_divergence_residual <= 1.0e-12
    )

  @property
  def downstream_condition_verified(self) -> bool:
    """Whether the exact supplied perimeter passed its physical condition."""

    return bool(
      self.downstream_condition is not None
      and self.downstream_condition.converged
      and self.downstream_condition.boundary == self.boundary
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the model and its downstream physical condition both passed."""

    return self.model_closure_verified and self.downstream_condition_verified

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal subsonic field is a closure/stop, not a supersonic handoff."""

    return True

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'model_closure_verified': self.model_closure_verified,
      'downstream_condition_verified': self.downstream_condition_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'model': self.model,
      'radial_divisions': self.radial_divisions,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'interior_point_m': self.interior_point_m,
      'maximum_thermodynamic_residual': self.maximum_thermodynamic_residual,
      'maximum_harmonic_residual': self.maximum_harmonic_residual,
      'maximum_velocity_divergence_residual': self.maximum_velocity_divergence_residual,
      'minimum_mach': self.minimum_mach,
      'maximum_mach': self.maximum_mach,
      'maximum_mass_conservation_residual': self.maximum_mass_conservation_residual,
      'maximum_boundary_velocity_residual': self.maximum_boundary_velocity_residual,
      'maximum_boundary_normal_velocity_residual': (
        self.maximum_boundary_normal_velocity_residual
      ),
      'potential_circulation_residual': self.potential_circulation_residual,
      'nonlinear_iteration_count': self.nonlinear_iteration_count,
      'nonlinear_update_residual': self.nonlinear_update_residual,
      'velocity_potential_sample_count': len(self.velocity_potential),
      'free_boundary_pressure_residual_Pa': self.free_boundary_pressure_residual_Pa,
      'free_boundary_tangent_residual_rad': self.free_boundary_tangent_residual_rad,
      'centerline_tangent_residual_rad': self.centerline_tangent_residual_rad,
      'outlet_pressure_residual_Pa': self.outlet_pressure_residual_Pa,
      'free_boundary_geometry_residual_m': self.free_boundary_geometry_residual_m,
      'control_section': (
        None if self.control_section is None else self.control_section.as_report()
      ),
      'boundary': self.boundary.as_report(),
      'downstream_condition': (
        None
        if self.downstream_condition is None
        else self.downstream_condition.as_report()
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFreeBoundaryResult:
  """Result of the solver-owned finite downstream free-boundary reference.

  This result is intentionally not a new supersonic chain cell.  It records a
  parameterized subsonic closure around the normal-shock seam, the scalar
  residual used to determine its outlet height, and the exact field/condition
  objects that passed the mixed-boundary gates.  The model is a planar,
  quasi-one-dimensional free-boundary reference embedded in a scalar radial
  mesh; it is useful for planner and visualization development, but remains
  below the canonical reflected-MOC and production-provider claim ceiling.
  """

  status: MocMixedRegimeFreeBoundaryStatus
  request: MocMixedRegimePerimeterRequest
  ambient_pressure_Pa: float
  effective_inlet_height_m: float
  downstream_length_m: float
  target_outlet_height_m: float | None
  outlet_height_m: float | None
  ambient_mach: float | None
  outlet_mach: float | None
  pressure_residual_Pa: float | None
  mass_flow_residual: float | None
  iteration_count: int
  height_bracket_m: tuple[float, float] | None
  boundary: MocMixedRegimeBoundaryResult | None = None
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None = None
  field: MocMixedRegimeFieldResult | None = None
  closure: MocMixedRegimeClosureResult | None = None
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec | None = None
  model: str = 'solver-owned-subsonic-free-boundary-reference'
  message: str = ''
  control_section: MocMixedRegimeControlSection | None = None
  control_section_validation: MocMixedRegimeControlSectionResult | None = None
  control_section_projection_verified: bool = False

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedRegimeFreeBoundaryStatus):
      raise TypeError('status must be a MocMixedRegimeFreeBoundaryStatus')
    if not isinstance(self.request, MocMixedRegimePerimeterRequest):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest')
    for name, value in (
      ('ambient_pressure_Pa', self.ambient_pressure_Pa),
      ('effective_inlet_height_m', self.effective_inlet_height_m),
      ('downstream_length_m', self.downstream_length_m),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if (
      isinstance(self.iteration_count, bool)
      or not isinstance(self.iteration_count, int)
      or self.iteration_count < 0
    ):
      raise ValueError('iteration_count must be a nonnegative integer')
    if self.height_bracket_m is not None:
      if len(self.height_bracket_m) != 2:
        raise ValueError('height_bracket_m must contain two values')
      lower, upper = (float(value) for value in self.height_bracket_m)
      if (
        not isfinite(lower)
        or not isfinite(upper)
        or lower <= 0.0
        or upper < lower
      ):
        raise ValueError('height_bracket_m must contain an ordered positive bracket')
      object.__setattr__(self, 'height_bracket_m', (lower, upper))
    for name in (
      'target_outlet_height_m',
      'outlet_height_m',
      'ambient_mach',
      'outlet_mach',
      'pressure_residual_Pa',
      'mass_flow_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric):
          raise ValueError(f'{name} must be finite when supplied')
        object.__setattr__(self, name, numeric)
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'message', str(self.message))
    if self.control_section is not None and not isinstance(
      self.control_section,
      MocMixedRegimeControlSection,
    ):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection or None'
      )
    if self.control_section_validation is not None and not isinstance(
      self.control_section_validation,
      MocMixedRegimeControlSectionResult,
    ):
      raise TypeError(
        'control_section_validation must be a '
        'MocMixedRegimeControlSectionResult or None'
      )
    if not isinstance(self.control_section_projection_verified, bool):
      raise TypeError('control_section_projection_verified must be a bool')
    if (
      self.control_section_validation is not None
      and self.control_section_validation.section is not None
      and self.control_section is not None
      and self.control_section_validation.section != self.control_section
    ):
      raise ValueError(
        'control_section_validation must retain the exact control_section'
      )

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocMixedRegimeFreeBoundaryStatus.CONVERGED_REFERENCE
      and self.closure is not None
      and self.closure.converged
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return bool(
      self.converged
      and self.field is not None
      and self.field.physical_closure_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_closure(self) -> MocMixedRegimeClosureResult:
    """Return the exact closure result when the reference converged."""

    if self.closure is None:
      raise ValueError('free-boundary reference did not produce a closure result')
    return self.closure
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'model': self.model,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'effective_inlet_height_m': self.effective_inlet_height_m,
      'downstream_length_m': self.downstream_length_m,
      'target_outlet_height_m': self.target_outlet_height_m,
      'outlet_height_m': self.outlet_height_m,
      'ambient_mach': self.ambient_mach,
      'outlet_mach': self.outlet_mach,
      'pressure_residual_Pa': self.pressure_residual_Pa,
      'mass_flow_residual': self.mass_flow_residual,
      'iteration_count': self.iteration_count,
      'height_bracket_m': self.height_bracket_m,
      'request': self.request.as_report(),
      'perimeter_spec': (
        None if self.perimeter_spec is None else self.perimeter_spec.as_report()
      ),
      'control_section': (
        None if self.control_section is None else self.control_section.as_report()
      ),
      'control_section_validation': (
        None
        if self.control_section_validation is None
        else self.control_section_validation.as_report()
      ),
      'control_section_projection_verified': self.control_section_projection_verified,
      'boundary': None if self.boundary is None else self.boundary.as_report(),
      'downstream_condition': (
        None
        if self.downstream_condition is None
        else self.downstream_condition.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'closure': None if self.closure is None else self.closure.as_report(),
      'claim_status': (
        'solver-owned-control-section-quasi-1d-reference; '
        'varying-section-2d-coupling-and-external-validation-pending'
        if self.control_section is not None
        else (
          'solver-owned-quasi-1d-free-boundary-reference; '
          'canonical-reflected-moc-and-external-validation-pending'
        )
      ),
      'message': self.message,
    }
  ####


def _empty_mixed_regime_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _field_failure(
  status: MocMixedRegimeFieldStatus,
  boundary: MocMixedRegimeBoundaryResult,
  *,
  nodes: Sequence[MocMixedRegimeFieldSample] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  interior_point_m: tuple[float, float] | None = None,
  maximum_thermodynamic_residual: float | None = None,
  maximum_harmonic_residual: float | None = None,
  maximum_velocity_divergence_residual: float | None = None,
  model: str = 'elliptic-isentropic-subsonic-reference',
  radial_divisions: int = 1,
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None = None,
  maximum_mass_conservation_residual: float | None = None,
  maximum_boundary_velocity_residual: float | None = None,
  potential_circulation_residual: float | None = None,
  nonlinear_iteration_count: int = 0,
  nonlinear_update_residual: float | None = None,
  velocity_potential: Sequence[float] = (),
  free_boundary_pressure_residual_Pa: float | None = None,
  free_boundary_tangent_residual_rad: float | None = None,
  centerline_tangent_residual_rad: float | None = None,
  outlet_pressure_residual_Pa: float | None = None,
  free_boundary_geometry_residual_m: float | None = None,
  maximum_boundary_normal_velocity_residual: float | None = None,
  message: str,
) -> MocMixedRegimeFieldResult:
  return MocMixedRegimeFieldResult(
    status=status,
    boundary=boundary,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=_empty_mixed_regime_topology() if topology is None else topology,
    interior_point_m=interior_point_m,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    minimum_mach=min((sample.mach for sample in nodes), default=None),
    maximum_mach=max((sample.mach for sample in nodes), default=None),
    model=model,
    radial_divisions=radial_divisions,
    downstream_condition=downstream_condition,
    maximum_mass_conservation_residual=maximum_mass_conservation_residual,
    maximum_boundary_velocity_residual=maximum_boundary_velocity_residual,
    potential_circulation_residual=potential_circulation_residual,
    nonlinear_iteration_count=nonlinear_iteration_count,
    nonlinear_update_residual=nonlinear_update_residual,
    velocity_potential=tuple(velocity_potential),
    free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
    free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
    centerline_tangent_residual_rad=centerline_tangent_residual_rad,
    outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
    free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
    maximum_boundary_normal_velocity_residual=(
      maximum_boundary_normal_velocity_residual
    ),
    message=message,
  )


def _isentropic_total_pressure(sample: MocMixedRegimeFieldSample) -> float:
  factor = 1.0 + 0.5 * (sample.gamma - 1.0) * sample.mach * sample.mach
  return sample.static_pressure_Pa * factor ** (sample.gamma / (sample.gamma - 1.0))


def _polygon_signed_area(points: Sequence[tuple[float, float]]) -> float:
  return 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(points, (*points[1:], points[0]), strict=True)
  )


def _potential_boundary_normal_velocity_residual(
  unique_points: Sequence[tuple[float, float]],
  connectivity: Sequence[tuple[int, int, int]],
  triangle_velocities: Sequence[tuple[float, float]],
  *,
  outer_start: int,
  condition_edge_indices: Sequence[int],
  position_tolerance_m: float,
) -> float | None:
  """Measure no-penetration on selected outer finite-element edges.

  The scalar potential reference prescribes boundary potential values, so a
  tangency check on the input samples is not enough to establish that the
  solved field has zero normal velocity.  This diagnostic uses the adjacent
  triangle gradient for each explicitly selected tangency edge.  It is kept
  separate from the pressure-outflow path, whose normal flux is intentionally
  not constrained here.
  """

  if not condition_edge_indices:
    return None
  area = _polygon_signed_area(unique_points)
  if abs(area) <= position_tolerance_m * position_tolerance_m:
    raise ValueError('potential perimeter has zero signed area for normal-flow measurement')
  perimeter_count = len(unique_points)
  edge_to_triangles: dict[tuple[int, int], list[int]] = {}
  for triangle_index, triangle in enumerate(connectivity):
    if len(triangle) != 3:
      raise ValueError('potential normal-flow measurement requires triangular cells')
    for first, second in zip(triangle, (*triangle[1:], triangle[0])):
      edge = (first, second) if first <= second else (second, first)
      edge_to_triangles.setdefault(edge, []).append(triangle_index)
  if len(connectivity) != len(triangle_velocities):
    raise ValueError(
      'potential normal-flow measurement has mismatched cell gradients'
    )
  orientation = 1.0 if area > 0.0 else -1.0
  residuals: list[float] = []
  for edge_index in condition_edge_indices:
    if (
      isinstance(edge_index, bool)
      or not isinstance(edge_index, int)
      or edge_index < 0
      or edge_index >= perimeter_count
    ):
      raise ValueError('potential normal-flow measurement received an invalid edge index')
    next_index = (edge_index + 1) % perimeter_count
    first_node = outer_start + edge_index
    second_node = outer_start + next_index
    edge = (
      (first_node, second_node)
      if first_node <= second_node
      else (second_node, first_node)
    )
    adjacent = edge_to_triangles.get(edge, ())
    if len(adjacent) != 1:
      raise ValueError(
        'potential normal-flow measurement requires exactly one adjacent '
        f'triangle for outer edge {edge_index}'
      )
    displacement = (
      unique_points[next_index][0] - unique_points[edge_index][0],
      unique_points[next_index][1] - unique_points[edge_index][1],
    )
    segment_length = hypot(*displacement)
    if segment_length <= position_tolerance_m:
      raise ValueError(
        'potential normal-flow measurement encountered a zero-length outer edge'
      )
    outward_normal = (
      orientation * displacement[1] / segment_length,
      -orientation * displacement[0] / segment_length,
    )
    velocity = triangle_velocities[adjacent[0]]
    if not all(isfinite(float(value)) for value in velocity):
      raise ValueError(
        'potential normal-flow measurement encountered a non-finite triangle velocity'
      )
    residuals.append(abs(
      velocity[0] * outward_normal[0]
      + velocity[1] * outward_normal[1]
    ))
  return max(residuals, default=None)


def _convex_polygon(points: Sequence[tuple[float, float]], tolerance_m: float) -> bool:
  signs: list[float] = []
  for first, second, third in zip(
    points,
    (*points[1:], points[0]),
    (*points[2:], points[0], points[1]),
    strict=True,
  ):
    first_edge = (second[0] - first[0], second[1] - first[1])
    second_edge = (third[0] - second[0], third[1] - second[1])
    cross = (
      first_edge[0] * second_edge[1]
      - first_edge[1] * second_edge[0]
    )
    # ``cross`` has units of m².  Comparing it to tolerance² alone makes a
    # mathematically collinear, long edge fail after coordinate construction
    # leaves round-off on the order of ``edge_length * tolerance``.  Use the
    # positional tolerance projected onto the local edge scale instead.  A
    # genuine turn whose transverse displacement exceeds the requested
    # tolerance still contributes a sign; only numerically collinear turns
    # are ignored.
    cross_tolerance = tolerance_m * max(
      tolerance_m,
      hypot(*first_edge),
      hypot(*second_edge),
    )
    if abs(cross) > cross_tolerance:
      signs.append(cross)
  return bool(signs) and (
    all(value > 0.0 for value in signs)
    or all(value < 0.0 for value in signs)
  )


def _relative_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(1.0, abs(actual), abs(expected))


def _triangle_velocity_divergence(
  vertices: Sequence[MocMixedRegimeFieldSample],
) -> float:
  if len(vertices) != 3:
    return float('inf')
  first, second, third = vertices
  x1, y1 = first.point_m
  x2, y2 = second.point_m
  x3, y3 = third.point_m
  area_twice = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
  if abs(area_twice) <= 1.0e-20:
    return float('inf')
  velocities = tuple(
    (
      sample.mach * cos(sample.flow_angle_rad),
      sample.mach * sin(sample.flow_angle_rad),
    )
    for sample in vertices
  )
  dudy = (
    (velocities[0][0] * (y2 - y3)
     + velocities[1][0] * (y3 - y1)
     + velocities[2][0] * (y1 - y2))
    / area_twice
  )
  dvdy = (
    (velocities[0][1] * (x3 - x2)
     + velocities[1][1] * (x1 - x3)
     + velocities[2][1] * (x2 - x1))
    / area_twice
  )
  return abs(dudy + dvdy)


def _harmonic_radial_levels(
  boundary_values: Sequence[float],
  radial_divisions: int,
  *,
  logarithmic: bool = False,
) -> tuple[tuple[tuple[float, ...], ...], float]:
  """Solve a small structured Dirichlet Laplace reference problem.

  The perimeter vertices are connected by concentric polygon rings.  The
  outer ring is fixed to the supplied boundary values; the center and all
  inner rings satisfy a five-point graph-Laplacian equation.  This is a
  deliberately small, deterministic reference discretization: it provides
  mesh/refinement evidence for the scalar mixed-regime lane, but it is not a
  compressible potential-flow solve.

  ``logarithmic`` is used for total pressure so positive values and the
  terminal shock's no-gain lineage are preserved by the interpolation.
  The returned residual is the largest linear-system residual in the solved
  variable (log space when requested).
  """

  values = tuple(float(value) for value in boundary_values)
  if len(values) < 3:
    raise ValueError('harmonic radial levels require at least three boundary values')
  if any(not isfinite(value) for value in values):
    raise ValueError('harmonic radial levels require finite boundary values')
  if logarithmic and any(value <= 0.0 for value in values):
    raise ValueError('logarithmic harmonic radial levels require positive values')
  transformed = tuple(log(value) for value in values) if logarithmic else values
  sample_count = len(values)

  if radial_divisions == 1:
    center = (sum(transformed) / sample_count,)
    levels = (center, transformed)
    return (
      tuple(
        tuple(exp(value) for value in level) if logarithmic else level
        for level in levels
      ),
      0.0,
    )

  unknown_count = 1 + (radial_divisions - 1) * sample_count
  matrix = np.zeros((unknown_count, unknown_count), dtype=float)
  right_hand_side = np.zeros(unknown_count, dtype=float)

  def ring_index(level: int, index: int) -> int:
    if level < 1 or level >= radial_divisions:
      raise ValueError('ring level must be an interior radial level')
    return 1 + (level - 1) * sample_count + index % sample_count

  # The center node is coupled to the first interior ring.  This keeps the
  # polygonal mesh single-valued instead of duplicating a center vertex once
  # per angular sample.
  matrix[0, 0] = float(sample_count)
  for index in range(sample_count):
    matrix[0, ring_index(1, index)] = -1.0

  for level in range(1, radial_divisions):
    for index in range(sample_count):
      row = ring_index(level, index)
      matrix[row, row] = 4.0
      if level == 1:
        matrix[row, 0] -= 1.0
      else:
        matrix[row, ring_index(level - 1, index)] -= 1.0
      if level + 1 == radial_divisions:
        right_hand_side[row] += transformed[index]
      else:
        matrix[row, ring_index(level + 1, index)] -= 1.0
      matrix[row, ring_index(level, index - 1)] -= 1.0
      matrix[row, ring_index(level, index + 1)] -= 1.0

  try:
    solution = np.linalg.solve(matrix, right_hand_side)
  except np.linalg.LinAlgError as error:
    raise ValueError('harmonic radial reference system is singular') from error
  if not np.isfinite(solution).all():
    raise ValueError('harmonic radial reference system returned non-finite values')

  residual = float(np.max(np.abs(matrix @ solution - right_hand_side)))
  transformed_levels: list[tuple[float, ...]] = [
    (float(solution[0]),),
  ]
  for level in range(1, radial_divisions):
    transformed_levels.append(
      tuple(float(solution[ring_index(level, index)]) for index in range(sample_count))
    )
  transformed_levels.append(transformed)
  if logarithmic:
    return (
      tuple(
        tuple(exp(value) for value in level)
        for level in transformed_levels
      ),
      residual,
    )
  return tuple(transformed_levels), residual


def _radial_mesh_points(
  perimeter_points: Sequence[tuple[float, float]],
  center_point: tuple[float, float],
  radial_divisions: int,
) -> tuple[tuple[tuple[float, float], ...], ...]:
  """Return center plus concentric polygon rings for a convex perimeter."""

  rings: list[tuple[tuple[float, float], ...]] = [(center_point,)]
  for level in range(1, radial_divisions + 1):
    scale = level / radial_divisions
    rings.append(
      tuple(
        (
          center_point[0] + scale * (point[0] - center_point[0]),
          center_point[1] + scale * (point[1] - center_point[1]),
        )
        for point in perimeter_points
      )
    )
  return tuple(rings)


def _radial_mesh_connectivity(
  rings: Sequence[Sequence[tuple[float, float]]],
  perimeter_count: int,
) -> tuple[tuple[MocCharacteristicCell, ...], tuple[tuple[int, int, int], ...]]:
  """Build the shared connectivity used by the scalar radial meshes."""

  if len(rings) < 2 or len(rings[0]) != 1:
    raise ValueError('radial mesh must contain a center and an outer ring')
  if perimeter_count < 3:
    raise ValueError('radial mesh requires at least three perimeter vertices')

  def ring_node_index(level: int, index: int) -> int:
    if level < 1 or level >= len(rings):
      raise ValueError('radial mesh ring level is outside the mesh')
    return 1 + (level - 1) * perimeter_count + index % perimeter_count

  cells: list[MocCharacteristicCell] = []
  connectivity: list[tuple[int, int, int]] = []
  first_ring = rings[1]
  for index in range(perimeter_count):
    next_index = (index + 1) % perimeter_count
    connectivity.append((0, ring_node_index(1, index), ring_node_index(1, next_index)))
    cells.append(
      MocCharacteristicCell(
        cell_index=len(cells),
        cell_kind='mixed-regime-elliptic-radial-center',
        vertices_xr_m=(rings[0][0], first_ring[index], first_ring[next_index]),
        centerline_indices=(),
        boundary_indices=(index, next_index),
      )
    )
  for level in range(1, len(rings) - 1):
    inner_ring = rings[level]
    outer_ring = rings[level + 1]
    for index in range(perimeter_count):
      next_index = (index + 1) % perimeter_count
      inner_first = ring_node_index(level, index)
      inner_second = ring_node_index(level, next_index)
      outer_first = ring_node_index(level + 1, index)
      outer_second = ring_node_index(level + 1, next_index)
      connectivity.extend((
        (inner_first, inner_second, outer_second),
        (inner_first, outer_second, outer_first),
      ))
      cells.extend((
        MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind='mixed-regime-elliptic-radial-annulus',
          vertices_xr_m=(inner_ring[index], inner_ring[next_index], outer_ring[next_index]),
          centerline_indices=(),
          boundary_indices=(index, next_index),
        ),
        MocCharacteristicCell(
          cell_index=len(cells) + 1,
          cell_kind='mixed-regime-elliptic-radial-annulus',
          vertices_xr_m=(inner_ring[index], outer_ring[next_index], outer_ring[index]),
          centerline_indices=(),
          boundary_indices=(index, next_index),
        ),
      ))
  return tuple(cells), tuple(connectivity)


def _potential_primitive(
  q_x: float,
  q_y: float,
  gamma: float,
) -> tuple[float, float]:
  """Return Mach number and normalized density for an isentropic potential."""

  if not isfinite(q_x) or not isfinite(q_y) or not isfinite(gamma) or gamma <= 1.0:
    raise ValueError('potential primitive inputs must be finite with gamma greater than one')
  speed_squared = q_x * q_x + q_y * q_y
  sonic_factor = 0.5 * (gamma - 1.0)
  enthalpy_factor = 1.0 - sonic_factor * speed_squared
  if enthalpy_factor <= 0.0:
    raise ValueError('potential velocity reached a nonphysical enthalpy factor')
  mach = sqrt(speed_squared / enthalpy_factor)
  density = enthalpy_factor ** (1.0 / (gamma - 1.0))
  if not isfinite(mach) or not isfinite(density):
    raise ValueError('potential primitive returned a non-finite state')
  return mach, density


def _potential_flux_and_jacobian(
  q_x: float,
  q_y: float,
  gamma: float,
) -> tuple[float, float, float, float, float, float, float]:
  """Return Mach, mass flux, and the compressible potential-flow Jacobian."""

  mach, density = _potential_primitive(q_x, q_y, gamma)
  sonic_factor = 0.5 * (gamma - 1.0)
  enthalpy_factor = 1.0 - sonic_factor * (q_x * q_x + q_y * q_y)
  flux_x = density * q_x
  flux_y = density * q_y
  jacobian_scale = density / enthalpy_factor
  return (
    mach,
    flux_x,
    flux_y,
    density - jacobian_scale * q_x * q_x,
    -jacobian_scale * q_x * q_y,
    -jacobian_scale * q_y * q_x,
    density - jacobian_scale * q_y * q_y,
  )


def _triangle_basis_gradients(
  vertices: Sequence[tuple[float, float]],
) -> tuple[float, tuple[tuple[float, float], ...]]:
  """Return positive area and constant linear basis gradients for a triangle."""

  if len(vertices) != 3:
    raise ValueError('potential-flow finite elements require triangular cells')
  first, second, third = vertices
  x1, y1 = first
  x2, y2 = second
  x3, y3 = third
  area_twice = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
  if not isfinite(area_twice) or abs(area_twice) <= 1.0e-20:
    raise ValueError('potential-flow finite element has zero area')
  gradients = (
    ((y2 - y3) / area_twice, (x3 - x2) / area_twice),
    ((y3 - y1) / area_twice, (x1 - x3) / area_twice),
    ((y1 - y2) / area_twice, (x2 - x1) / area_twice),
  )
  return abs(area_twice) * 0.5, gradients


def _solve_mixed_regime_radial_reference_field(
  boundary: MocMixedRegimeBoundaryResult,
  unique_samples: tuple[MocMixedRegimeFieldSample, ...],
  unique_points: tuple[tuple[float, float], ...],
  center_point: tuple[float, float],
  *,
  radial_divisions: int,
  position_tolerance_m: float,
  thermodynamic_tolerance: float,
  residual_tolerance: float,
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None,
) -> MocMixedRegimeFieldResult:
  """Build the explicit higher-resolution scalar mixed-regime reference."""

  model = 'elliptic-isentropic-radial-reference'
  try:
    mach_levels, mach_residual = _harmonic_radial_levels(
      tuple(sample.mach for sample in unique_samples),
      radial_divisions,
    )
    angle_levels, angle_residual = _harmonic_radial_levels(
      tuple(sample.flow_angle_rad for sample in unique_samples),
      radial_divisions,
    )
    pressure_levels, pressure_residual = _harmonic_radial_levels(
      tuple(sample.total_pressure_Pa for sample in unique_samples),
      radial_divisions,
      logarithmic=True,
    )
    gamma_levels, gamma_residual = _harmonic_radial_levels(
      tuple(sample.gamma for sample in unique_samples),
      radial_divisions,
    )
    rings = _radial_mesh_points(unique_points, center_point, radial_divisions)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=unique_samples,
      interior_point_m=center_point,
      model=model,
      radial_divisions=radial_divisions,
      message=f'mixed-regime radial reference solve failed: {error}',
    )

  levels: list[tuple[MocMixedRegimeFieldSample, ...]] = []
  for level, points in enumerate(rings):
    if level == radial_divisions:
      levels.append(unique_samples)
      continue
    level_samples: list[MocMixedRegimeFieldSample] = []
    for index, point in enumerate(points):
      mach = mach_levels[level][index]
      flow_angle = angle_levels[level][index]
      total_pressure = pressure_levels[level][index]
      gamma = gamma_levels[level][index]
      pressure_factor = (
        1.0 + 0.5 * (gamma - 1.0) * mach * mach
      ) ** (gamma / (gamma - 1.0))
      try:
        level_samples.append(
          MocMixedRegimeFieldSample(
            point_m=point,
            mach=mach,
            flow_angle_rad=flow_angle,
            static_pressure_Pa=total_pressure / pressure_factor,
            total_pressure_Pa=total_pressure,
            gamma=gamma,
          )
        )
      except (TypeError, ValueError) as error:
        return _field_failure(
          MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
          boundary,
          nodes=tuple(sample for level_samples in levels for sample in level_samples),
          interior_point_m=center_point,
          model=model,
          radial_divisions=radial_divisions,
          message=f'mixed-regime radial scalar state failed at level {level}: {error}',
        )
    levels.append(tuple(level_samples))

  nodes = tuple(sample for level_samples in levels for sample in level_samples)
  thermodynamic_residual = max(
    _relative_residual(_isentropic_total_pressure(sample), sample.total_pressure_Pa)
    for sample in nodes
  )
  harmonic_residual = max(
    mach_residual,
    angle_residual,
    pressure_residual,
    gamma_residual,
  )
  if thermodynamic_residual > thermodynamic_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
      boundary,
      nodes=nodes,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'mixed-regime radial reference scalar states do not satisfy the '
        f'isentrope relation: residual={thermodynamic_residual}'
      ),
    )

  cells: list[MocCharacteristicCell] = []
  try:
    first_ring = rings[1]
    for index, next_index in enumerate(
      (index + 1) % len(unique_points) for index in range(len(unique_points))
    ):
      cells.append(
        MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind='mixed-regime-elliptic-radial-center',
          vertices_xr_m=(rings[0][0], first_ring[index], first_ring[next_index]),
          centerline_indices=(),
          boundary_indices=(index, next_index),
        )
      )
    for level in range(1, radial_divisions):
      inner_ring = rings[level]
      outer_ring = rings[level + 1]
      for index, next_index in enumerate(
        (index + 1) % len(unique_points) for index in range(len(unique_points))
      ):
        inner_first = inner_ring[index]
        inner_second = inner_ring[next_index]
        outer_first = outer_ring[index]
        outer_second = outer_ring[next_index]
        cells.extend((
          MocCharacteristicCell(
            cell_index=len(cells),
            cell_kind='mixed-regime-elliptic-radial-annulus',
            vertices_xr_m=(inner_first, inner_second, outer_second),
            centerline_indices=(),
            boundary_indices=(index, next_index),
          ),
          MocCharacteristicCell(
            cell_index=len(cells) + 1,
            cell_kind='mixed-regime-elliptic-radial-annulus',
            vertices_xr_m=(inner_first, outer_second, outer_first),
            centerline_indices=(),
            boundary_indices=(index, next_index),
          ),
        ))
  except (TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=f'mixed-regime radial mesh geometry failed: {error}',
    )

  topology = validate_moc_mesh(tuple(cells))
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _field_failure(
      MocMixedRegimeFieldStatus.TOPOLOGY_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=f'mixed-regime radial mesh topology failed: {topology.message}',
    )

  node_lookup: dict[tuple[float, float], MocMixedRegimeFieldSample] = {
    sample.point_m: sample
    for level_samples in levels
    for sample in level_samples
  }
  divergence_residual = max(
    _triangle_velocity_divergence(tuple(
      node_lookup[point]
      for point in cell.vertices_xr_m
    ))
    for cell in cells
    if len(cell.vertices_xr_m) == 3
  )
  if harmonic_residual > residual_tolerance or divergence_residual > residual_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.RESIDUAL_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      maximum_velocity_divergence_residual=divergence_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'mixed-regime radial reference residual gate failed: '
        f'harmonic={harmonic_residual}, divergence={divergence_residual}'
      ),
    )
  return MocMixedRegimeFieldResult(
    status=MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD,
    boundary=boundary,
    nodes=nodes,
    cells=tuple(cells),
    topology=topology,
    interior_point_m=center_point,
    maximum_thermodynamic_residual=thermodynamic_residual,
    maximum_harmonic_residual=harmonic_residual,
    maximum_velocity_divergence_residual=divergence_residual,
    minimum_mach=min(sample.mach for sample in nodes),
    maximum_mach=max(sample.mach for sample in nodes),
    model=model,
    radial_divisions=radial_divisions,
    downstream_condition=downstream_condition,
    message=(
      'harmonic radial elliptic/isentrope reference field converged on the '
      'supplied closed perimeter; this model remains separate from the '
      'supersonic MOC lane'
    ),
  )


def solve_mixed_regime_subsonic_field(
  boundary: MocMixedRegimeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
  radial_divisions: int = 1,
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None = None,
) -> MocMixedRegimeFieldResult:
  """Solve the declared elliptic/isentrope subsonic reference field.

  The input perimeter is the physical boundary condition.  By default the
  solver creates a convex fan mesh with one interior control point and sets
  each interior primitive to the arithmetic harmonic extension of the
  boundary values.  ``radial_divisions`` greater than one selects the
  higher-resolution concentric-ring reference mesh and solves a small
  discrete Dirichlet Laplace problem for the interior scalar fields.  Both
  paths check the isentropic total-pressure relation and the piecewise-linear
  dimensionless-velocity divergence on every triangle.

  This intentionally does not accept an open perimeter, infer missing points,
  or extrapolate a subsonic state from the supersonic MOC field.  The optional
  ``downstream_condition`` must be the exact validated condition for the same
  scalar boundary before the returned field can be attached to a terminal.
  Omitting it leaves a converged model mesh that is explicitly incomplete for
  physical closure.  The one-cell fan is a separate reference model with an
  explicit model label; a future higher-order elliptic solver can replace it
  behind this result contract.
  """

  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    raise TypeError('boundary must be a MocMixedRegimeBoundaryResult')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    isinstance(radial_divisions, bool)
    or not isinstance(radial_divisions, int)
    or radial_divisions < 1
  ):
    raise ValueError('radial_divisions must be a positive integer')
  if downstream_condition is not None:
    if not isinstance(
      downstream_condition,
      MocMixedRegimeDownstreamConditionResult,
    ):
      raise TypeError(
        'downstream_condition must be a '
        'MocMixedRegimeDownstreamConditionResult or None'
      )
    if downstream_condition.boundary != boundary:
      return _field_failure(
        MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
        boundary,
        message=(
          'mixed-regime downstream condition must retain the exact scalar '
          'boundary supplied to the field solver'
        ),
      )
    if not downstream_condition.converged:
      return _field_failure(
        MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
        boundary,
        downstream_condition=downstream_condition,
        message=(
          'mixed-regime field requires a converged downstream physical '
          f'condition: {downstream_condition.message}'
        ),
      )
  if not boundary.converged:
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      message=f'mixed-regime field requires a converged boundary handoff: {boundary.message}',
    )
  samples = boundary.subsonic_samples
  points = boundary.perimeter_points_m
  if len(samples) < 4 or len(points) != len(samples):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime field requires a closed perimeter with matching scalar samples',
    )
  if any(
    hypot(sample.point_m[0] - point[0], sample.point_m[1] - point[1])
    > position_tolerance_m
    for sample, point in zip(samples, points, strict=True)
  ):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime scalar sample coordinates do not match the perimeter geometry',
    )
  unique_samples = samples[:-1]
  unique_points = points[:-1]
  if len(unique_samples) < 3:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime field requires at least three unique perimeter vertices',
    )
  area = _polygon_signed_area(unique_points)
  if abs(area) <= position_tolerance_m * position_tolerance_m:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime perimeter has zero signed area',
    )
  if not _convex_polygon(unique_points, position_tolerance_m):
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime reference field requires a convex perimeter fan',
    )
  center_point = (
    sum(point[0] for point in unique_points) / len(unique_points),
    sum(point[1] for point in unique_points) / len(unique_points),
  )
  if radial_divisions > 1:
    return _solve_mixed_regime_radial_reference_field(
      boundary,
      tuple(unique_samples),
      tuple(unique_points),
      center_point,
      radial_divisions=radial_divisions,
      position_tolerance_m=position_tolerance_m,
      thermodynamic_tolerance=thermodynamic_tolerance,
      residual_tolerance=residual_tolerance,
      downstream_condition=downstream_condition,
    )
  center_sample = MocMixedRegimeFieldSample(
    point_m=center_point,
    mach=sum(sample.mach for sample in unique_samples) / len(unique_samples),
    flow_angle_rad=sum(sample.flow_angle_rad for sample in unique_samples) / len(unique_samples),
    static_pressure_Pa=sum(sample.static_pressure_Pa for sample in unique_samples) / len(unique_samples),
    total_pressure_Pa=sum(sample.total_pressure_Pa for sample in unique_samples) / len(unique_samples),
    gamma=sum(sample.gamma for sample in unique_samples) / len(unique_samples),
  )
  nodes = (*unique_samples, center_sample)
  thermodynamic_residual = max(
    _relative_residual(_isentropic_total_pressure(sample), sample.total_pressure_Pa)
    for sample in nodes
  )
  if thermodynamic_residual > thermodynamic_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
      boundary,
      nodes=nodes,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      message=(
        'mixed-regime scalar samples do not satisfy the isentropic '
        f'total-pressure relation: residual={thermodynamic_residual}'
      ),
    )
  harmonic_residual = max(
    value
    for value in (
      abs(center_sample.mach - sum(sample.mach for sample in unique_samples) / len(unique_samples)),
      abs(center_sample.flow_angle_rad - sum(sample.flow_angle_rad for sample in unique_samples) / len(unique_samples)),
      abs(center_sample.static_pressure_Pa - sum(sample.static_pressure_Pa for sample in unique_samples) / len(unique_samples)),
      abs(center_sample.total_pressure_Pa - sum(sample.total_pressure_Pa for sample in unique_samples) / len(unique_samples)),
    )
  )
  cells: list[MocCharacteristicCell] = []
  try:
    for index, (first, second) in enumerate(
      zip(unique_points, (*unique_points[1:], unique_points[0]), strict=True)
    ):
      cells.append(
        MocCharacteristicCell(
          cell_index=index,
          cell_kind='mixed-regime-elliptic-reference',
          vertices_xr_m=(center_point, first, second),
          centerline_indices=(),
          boundary_indices=(index, (index + 1) % len(unique_points)),
        )
      )
  except ValueError as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=nodes,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      message=f'mixed-regime fan-cell geometry failed: {error}',
    )
  topology = validate_moc_mesh(tuple(cells))
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _field_failure(
      MocMixedRegimeFieldStatus.TOPOLOGY_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      message=f'mixed-regime fan topology failed: {topology.message}',
    )
  node_by_index = {index: sample for index, sample in enumerate(unique_samples)}
  node_by_index[len(unique_samples)] = center_sample
  divergence_residual = max(
    _triangle_velocity_divergence((
      center_sample,
      node_by_index[index],
      node_by_index[(index + 1) % len(unique_samples)],
    ))
    for index in range(len(unique_samples))
  )
  if harmonic_residual > residual_tolerance or divergence_residual > residual_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.RESIDUAL_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      maximum_velocity_divergence_residual=divergence_residual,
      message=(
        'mixed-regime elliptic reference residual gate failed: '
        f'harmonic={harmonic_residual}, divergence={divergence_residual}'
      ),
    )
  return MocMixedRegimeFieldResult(
    status=MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD,
    boundary=boundary,
    nodes=nodes,
    cells=tuple(cells),
    topology=topology,
    interior_point_m=center_point,
    maximum_thermodynamic_residual=thermodynamic_residual,
    maximum_harmonic_residual=harmonic_residual,
    maximum_velocity_divergence_residual=divergence_residual,
    minimum_mach=min(sample.mach for sample in nodes),
    maximum_mach=max(sample.mach for sample in nodes),
    downstream_condition=downstream_condition,
    message=(
      'elliptic/isentrope subsonic reference field converged on the supplied '
      'closed perimeter; '
      + (
        'the exact downstream physical condition is attached; '
        if downstream_condition is not None
        else 'the downstream physical condition is still pending; '
      )
      + 'this model remains separate from the supersonic MOC lane'
    ),
  )


def solve_mixed_regime_compressible_potential_field(
  boundary: MocMixedRegimeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  thermodynamic_tolerance: float = 1.0e-8,
  potential_tolerance: float = 1.0e-10,
  residual_tolerance: float = 1.0e-10,
  velocity_tolerance: float = 1.0e-8,
  subsonic_margin: float = 1.0e-6,
  radial_divisions: int = 1,
  maximum_iterations: int = 80,
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None = None,
) -> MocMixedRegimeFieldResult:
  """Solve a compressible isentropic potential field on an explicit perimeter.

  This is a deliberately separate research reference model for the subsonic
  side of a terminal shock.  It solves the conservative nonlinear potential
  equation ``div(rho(grad(phi)) grad(phi)) = 0`` with linear triangular
  finite elements and Dirichlet potential values obtained by integrating the
  supplied boundary velocity tangentially around the declared perimeter.
  The input perimeter remains caller-owned: this function neither discovers
  a free boundary from the open supersonic patch nor infers a canonical plume
  shape.

  The boundary total pressure and gamma must be uniform, because a single
  isentropic potential region cannot represent an imposed total-pressure
  jump.  The result records mass-conservation, boundary-potential,
  circulation, subsonic, and nonlinear iteration diagnostics.  It remains a
  scalar mixed-regime field and ``chain_promotion_blocked`` stays true; it is
  not a ``CharacteristicState`` field and cannot continue a supersonic MOC
  chain.
  """

  model = 'compressible-isentropic-potential-reference'
  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    raise TypeError('boundary must be a MocMixedRegimeBoundaryResult')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
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

  if downstream_condition is not None:
    if not isinstance(
      downstream_condition,
      MocMixedRegimeDownstreamConditionResult,
    ):
      raise TypeError(
        'downstream_condition must be a '
        'MocMixedRegimeDownstreamConditionResult or None'
      )
    if downstream_condition.boundary != boundary:
      return _field_failure(
        MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
        boundary,
        model=model,
        radial_divisions=radial_divisions,
        message=(
          'compressible potential field requires the exact scalar boundary '
          'retained by the downstream condition'
        ),
      )
    if not downstream_condition.converged:
      return _field_failure(
        MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
        boundary,
        model=model,
        radial_divisions=radial_divisions,
        downstream_condition=downstream_condition,
        message=(
          'compressible potential field requires a converged downstream '
          f'physical condition: {downstream_condition.message}'
        ),
      )
  if not boundary.converged:
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'compressible potential field requires a converged scalar boundary '
        f'handoff: {boundary.message}'
      ),
    )

  samples = boundary.subsonic_samples
  points = boundary.perimeter_points_m
  if len(samples) < 4 or len(points) != len(samples):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'compressible potential field requires a closed perimeter with '
        'matching scalar samples'
      ),
    )
  if any(not isinstance(sample, MocMixedRegimeFieldSample) for sample in samples):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      model=model,
      radial_divisions=radial_divisions,
      message='compressible potential field requires scalar mixed-regime samples',
    )
  if any(
    hypot(sample.point_m[0] - point[0], sample.point_m[1] - point[1])
    > position_tolerance_m
    for sample, point in zip(samples, points, strict=True)
  ):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      message='compressible potential field scalar coordinates do not match the perimeter',
    )

  unique_samples = tuple(samples[:-1])
  unique_points = tuple(points[:-1])
  if len(unique_samples) < 3:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      message='compressible potential field requires at least three unique perimeter vertices',
    )
  area = _polygon_signed_area(unique_points)
  if abs(area) <= position_tolerance_m * position_tolerance_m:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      message='compressible potential perimeter has zero signed area',
    )
  if not _convex_polygon(unique_points, position_tolerance_m):
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      message='compressible potential reference field requires a convex perimeter',
    )

  center_point = (
    sum(point[0] for point in unique_points) / len(unique_points),
    sum(point[1] for point in unique_points) / len(unique_points),
  )
  total_pressure_reference = unique_samples[0].total_pressure_Pa
  gamma_reference = unique_samples[0].gamma
  maximum_total_pressure_residual = max(
    _relative_residual(sample.total_pressure_Pa, total_pressure_reference)
    for sample in unique_samples
  )
  maximum_gamma_residual = max(
    _relative_residual(sample.gamma, gamma_reference)
    for sample in unique_samples
  )
  if (
    maximum_total_pressure_residual > thermodynamic_tolerance
    or maximum_gamma_residual > thermodynamic_tolerance
  ):
    return _field_failure(
      MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      maximum_thermodynamic_residual=max(
        maximum_total_pressure_residual,
        maximum_gamma_residual,
      ),
      message=(
        'compressible isentropic potential flow requires uniform boundary '
        'total pressure and gamma: '
        f'total_pressure={maximum_total_pressure_residual}, '
        f'gamma={maximum_gamma_residual}'
      ),
    )

  boundary_velocities: list[tuple[float, float]] = []
  try:
    for index, sample in enumerate(unique_samples):
      if sample.mach >= 1.0 - subsonic_margin:
        raise ValueError(
          f'boundary sample {index} is too close to sonic for the declared '
          f'subsonic margin: mach={sample.mach}'
        )
      sonic_factor = 0.5 * (gamma_reference - 1.0)
      speed = sample.mach / sqrt(1.0 + sonic_factor * sample.mach * sample.mach)
      boundary_velocities.append(
        (
          speed * cos(sample.flow_angle_rad),
          speed * sin(sample.flow_angle_rad),
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      maximum_thermodynamic_residual=max(
        maximum_total_pressure_residual,
        maximum_gamma_residual,
      ),
      message=f'compressible potential boundary velocity conversion failed: {error}',
    )

  perimeter_length = sum(
    hypot(
      unique_points[(index + 1) % len(unique_points)][0] - point[0],
      unique_points[(index + 1) % len(unique_points)][1] - point[1],
    )
    for index, point in enumerate(unique_points)
  )
  boundary_potential = [0.0]
  for index in range(1, len(unique_points)):
    previous = index - 1
    displacement = (
      unique_points[index][0] - unique_points[previous][0],
      unique_points[index][1] - unique_points[previous][1],
    )
    boundary_potential.append(
      boundary_potential[-1]
      + 0.5 * (
        (boundary_velocities[previous][0] + boundary_velocities[index][0]) * displacement[0]
        + (boundary_velocities[previous][1] + boundary_velocities[index][1]) * displacement[1]
      )
    )
  closing_displacement = (
    unique_points[0][0] - unique_points[-1][0],
    unique_points[0][1] - unique_points[-1][1],
  )
  closing_increment = 0.5 * (
    (boundary_velocities[-1][0] + boundary_velocities[0][0]) * closing_displacement[0]
    + (boundary_velocities[-1][1] + boundary_velocities[0][1]) * closing_displacement[1]
  )
  circulation_residual = abs(boundary_potential[-1] + closing_increment)
  circulation_scale = max(
    1.0,
    perimeter_length * max(
      1.0,
      max(hypot(*velocity) for velocity in boundary_velocities),
    ),
  )
  if circulation_residual > potential_tolerance * circulation_scale:
    return _field_failure(
      MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
      boundary,
      nodes=samples,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=max(
        maximum_total_pressure_residual,
        maximum_gamma_residual,
      ),
      potential_circulation_residual=circulation_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'compressible potential boundary velocities are not single-valued '
        f'around the explicit perimeter: circulation={circulation_residual}, '
        f'tolerance={potential_tolerance * circulation_scale}'
      ),
    )

  try:
    rings = _radial_mesh_points(
      unique_points,
      center_point,
      radial_divisions,
    )
    cells, connectivity = _radial_mesh_connectivity(
      rings,
      len(unique_points),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      interior_point_m=center_point,
      potential_circulation_residual=circulation_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=f'compressible potential radial mesh geometry failed: {error}',
    )
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _field_failure(
      MocMixedRegimeFieldStatus.TOPOLOGY_FAILURE,
      boundary,
      nodes=samples,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      potential_circulation_residual=circulation_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=f'compressible potential radial mesh topology failed: {topology.message}',
    )

  node_points = tuple(point for ring in rings for point in ring)
  perimeter_count = len(unique_points)
  unknown_count = 1 + (radial_divisions - 1) * perimeter_count
  outer_start = unknown_count
  total_node_count = len(node_points)
  fixed_boundary_potential = np.asarray(boundary_potential, dtype=float)

  try:
    initial_matrix = np.zeros((unknown_count, unknown_count), dtype=float)
    initial_right_hand_side = np.zeros(unknown_count, dtype=float)
    for triangle in connectivity:
      vertices = tuple(node_points[index] for index in triangle)
      triangle_area, gradients = _triangle_basis_gradients(vertices)
      for local, row_index in enumerate(triangle):
        if row_index >= unknown_count:
          continue
        row_gradient_x, row_gradient_y = gradients[local]
        for column_local, column_index in enumerate(triangle):
          column_gradient_x, column_gradient_y = gradients[column_local]
          coefficient = triangle_area * (
            row_gradient_x * column_gradient_x
            + row_gradient_y * column_gradient_y
          )
          if column_index < unknown_count:
            initial_matrix[row_index, column_index] += coefficient
          else:
            initial_right_hand_side[row_index] -= coefficient * (
              fixed_boundary_potential[column_index - outer_start]
            )
    current_unknown = np.linalg.solve(
      initial_matrix,
      initial_right_hand_side,
    )
    if not np.isfinite(current_unknown).all():
      raise ValueError('compressible potential initial Laplace solve returned non-finite values')
    initial_harmonic_residual = float(
      np.max(np.abs(initial_matrix @ current_unknown - initial_right_hand_side))
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError, np.linalg.LinAlgError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
      boundary,
      nodes=samples,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      potential_circulation_residual=circulation_residual,
      model=model,
      radial_divisions=radial_divisions,
      message=f'compressible potential initial Dirichlet solve failed: {error}',
    )

  def full_potential(unknown: np.ndarray) -> np.ndarray:
    if unknown.shape != (unknown_count,):
      raise ValueError('potential unknown vector has an invalid shape')
    values = np.empty(total_node_count, dtype=float)
    values[:unknown_count] = unknown
    values[outer_start:] = fixed_boundary_potential
    return values

  def assemble(
    unknown: np.ndarray,
    *,
    with_jacobian: bool,
  ):
    values = full_potential(unknown)
    residual = np.zeros(unknown_count, dtype=float)
    jacobian = (
      np.zeros((unknown_count, unknown_count), dtype=float)
      if with_jacobian
      else None
    )
    triangle_velocities: list[tuple[float, float]] = []
    for triangle in connectivity:
      vertices = tuple(node_points[index] for index in triangle)
      area, gradients = _triangle_basis_gradients(vertices)
      q_x = sum(values[index] * gradients[local][0] for local, index in enumerate(triangle))
      q_y = sum(values[index] * gradients[local][1] for local, index in enumerate(triangle))
      primitive = _potential_flux_and_jacobian(q_x, q_y, gamma_reference)
      mach, flux_x, flux_y, jacobian_xx, jacobian_xy, jacobian_yx, jacobian_yy = primitive
      if mach >= 1.0 - subsonic_margin:
        raise ValueError(
          f'interior potential state reached the sonic limit: mach={mach}'
        )
      triangle_velocities.append((q_x, q_y))
      for local, row_index in enumerate(triangle):
        if row_index >= unknown_count:
          continue
        gradient_x, gradient_y = gradients[local]
        residual[row_index] += area * (gradient_x * flux_x + gradient_y * flux_y)
        if jacobian is None:
          continue
        for column_local, column_index in enumerate(triangle):
          if column_index >= unknown_count:
            continue
          column_gradient_x, column_gradient_y = gradients[column_local]
          jacobian[row_index, column_index] += area * (
            gradient_x * (
              jacobian_xx * column_gradient_x
              + jacobian_xy * column_gradient_y
            )
            + gradient_y * (
              jacobian_yx * column_gradient_x
              + jacobian_yy * column_gradient_y
            )
          )
    if not np.isfinite(residual).all():
      raise ValueError('compressible potential residual contains non-finite values')
    if jacobian is not None and not np.isfinite(jacobian).all():
      raise ValueError('compressible potential Jacobian contains non-finite values')
    return residual, jacobian, tuple(triangle_velocities)

  iteration_count = 0
  nonlinear_update_residual = 0.0
  converged = False
  current_residual_norm = float('inf')
  for iteration_index in range(maximum_iterations + 1):
    try:
      current_residual, current_jacobian, _ = assemble(
        current_unknown,
        with_jacobian=True,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _field_failure(
        MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
        boundary,
        nodes=samples,
        cells=cells,
        topology=topology,
        interior_point_m=center_point,
        maximum_harmonic_residual=initial_harmonic_residual,
        potential_circulation_residual=circulation_residual,
        nonlinear_iteration_count=iteration_count,
        nonlinear_update_residual=nonlinear_update_residual,
        velocity_potential=tuple(full_potential(current_unknown)),
        model=model,
        radial_divisions=radial_divisions,
        message=f'compressible potential residual assembly failed: {error}',
      )
    current_residual_norm = float(np.max(np.abs(current_residual)))
    if current_residual_norm <= residual_tolerance:
      converged = True
      nonlinear_update_residual = 0.0
      break
    if iteration_index >= maximum_iterations:
      break
    if current_jacobian is None:
      raise AssertionError('potential Newton assembly omitted its Jacobian')
    try:
      delta = np.linalg.solve(current_jacobian, -current_residual)
    except (np.linalg.LinAlgError, TypeError, ValueError) as error:
      return _field_failure(
        MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
        boundary,
        nodes=samples,
        cells=cells,
        topology=topology,
        interior_point_m=center_point,
        maximum_harmonic_residual=initial_harmonic_residual,
        maximum_velocity_divergence_residual=current_residual_norm,
        potential_circulation_residual=circulation_residual,
        nonlinear_iteration_count=iteration_count,
        nonlinear_update_residual=nonlinear_update_residual,
        velocity_potential=tuple(full_potential(current_unknown)),
        model=model,
        radial_divisions=radial_divisions,
        message=f'compressible potential Newton system failed: {error}',
      )
    if not np.isfinite(delta).all():
      return _field_failure(
        MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
        boundary,
        nodes=samples,
        cells=cells,
        topology=topology,
        interior_point_m=center_point,
        maximum_harmonic_residual=initial_harmonic_residual,
        maximum_velocity_divergence_residual=current_residual_norm,
        potential_circulation_residual=circulation_residual,
        nonlinear_iteration_count=iteration_count,
        nonlinear_update_residual=nonlinear_update_residual,
        velocity_potential=tuple(full_potential(current_unknown)),
        model=model,
        radial_divisions=radial_divisions,
        message='compressible potential Newton system returned a non-finite update',
      )
    delta_norm = float(np.max(np.abs(delta)))
    if delta_norm <= np.finfo(float).eps * max(
      1.0,
      float(np.max(np.abs(current_unknown))),
    ):
      break
    accepted_unknown: np.ndarray | None = None
    accepted_residual_norm = float('inf')
    step_scale = 1.0
    for _ in range(20):
      candidate = current_unknown + step_scale * delta
      try:
        candidate_residual, _, _ = assemble(candidate, with_jacobian=False)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        candidate_residual = None
      if candidate_residual is not None:
        candidate_norm = float(np.max(np.abs(candidate_residual)))
        if (
          candidate_norm < current_residual_norm
          or candidate_norm <= residual_tolerance
        ):
          accepted_unknown = candidate
          accepted_residual_norm = candidate_norm
          break
      step_scale *= 0.5
    if accepted_unknown is None:
      break
    nonlinear_update_residual = float(
      np.max(np.abs(accepted_unknown - current_unknown))
    )
    current_unknown = accepted_unknown
    current_residual_norm = accepted_residual_norm
    iteration_count = iteration_index + 1
  if not converged:
    return _field_failure(
      MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
      boundary,
      nodes=samples,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_harmonic_residual=initial_harmonic_residual,
      maximum_velocity_divergence_residual=current_residual_norm,
      potential_circulation_residual=circulation_residual,
      nonlinear_iteration_count=iteration_count,
      nonlinear_update_residual=nonlinear_update_residual,
      velocity_potential=tuple(full_potential(current_unknown)),
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'compressible potential Newton solve did not converge: '
        f'residual={current_residual_norm}, iterations={iteration_count}'
      ),
    )

  try:
    final_residual, _, triangle_velocities = assemble(
      current_unknown,
      with_jacobian=False,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.POTENTIAL_FLOW_FAILURE,
      boundary,
      nodes=samples,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_harmonic_residual=initial_harmonic_residual,
      potential_circulation_residual=circulation_residual,
      nonlinear_iteration_count=iteration_count,
      nonlinear_update_residual=nonlinear_update_residual,
      velocity_potential=tuple(full_potential(current_unknown)),
      model=model,
      radial_divisions=radial_divisions,
      message=f'compressible potential final assembly failed: {error}',
    )
  mass_residual = float(np.max(np.abs(final_residual)))
  potential_values = full_potential(current_unknown)
  velocity_sums = [[0.0, 0.0] for _ in range(total_node_count)]
  velocity_counts = [0 for _ in range(total_node_count)]
  for triangle, velocity in zip(connectivity, triangle_velocities, strict=True):
    for node_index in triangle:
      velocity_sums[node_index][0] += velocity[0]
      velocity_sums[node_index][1] += velocity[1]
      velocity_counts[node_index] += 1

  nodes: list[MocMixedRegimeFieldSample] = []
  try:
    for node_index, point in enumerate(node_points):
      if node_index >= outer_start:
        nodes.append(unique_samples[node_index - outer_start])
        continue
      if velocity_counts[node_index] == 0:
        raise ValueError(f'potential mesh node {node_index} has no adjacent cells')
      q_x = velocity_sums[node_index][0] / velocity_counts[node_index]
      q_y = velocity_sums[node_index][1] / velocity_counts[node_index]
      mach, _ = _potential_primitive(q_x, q_y, gamma_reference)
      if mach <= 0.0 or mach >= 1.0 - subsonic_margin:
        raise ValueError(
          f'potential mesh node {node_index} is outside the strict subsonic '
          f'range: mach={mach}'
        )
      sonic_factor = 0.5 * (gamma_reference - 1.0)
      enthalpy_factor = 1.0 - sonic_factor * (q_x * q_x + q_y * q_y)
      nodes.append(
        MocMixedRegimeFieldSample(
          point_m=point,
          mach=mach,
          flow_angle_rad=atan2(q_y, q_x),
          static_pressure_Pa=(
            total_pressure_reference
            * enthalpy_factor ** (gamma_reference / (gamma_reference - 1.0))
          ),
          total_pressure_Pa=total_pressure_reference,
          gamma=gamma_reference,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_velocity_divergence_residual=mass_residual,
      potential_circulation_residual=circulation_residual,
      nonlinear_iteration_count=iteration_count,
      nonlinear_update_residual=nonlinear_update_residual,
      velocity_potential=tuple(potential_values),
      downstream_condition=downstream_condition,
      model=model,
      radial_divisions=radial_divisions,
      message=f'compressible potential field state construction failed: {error}',
    )

  boundary_velocity_residual = 0.0
  for index in range(perimeter_count):
    next_index = (index + 1) % perimeter_count
    first_point = unique_points[index]
    second_point = unique_points[next_index]
    displacement = (
      second_point[0] - first_point[0],
      second_point[1] - first_point[1],
    )
    segment_length = hypot(*displacement)
    if segment_length <= position_tolerance_m:
      return _field_failure(
        MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
        boundary,
        nodes=nodes,
        cells=cells,
        topology=topology,
        interior_point_m=center_point,
        maximum_velocity_divergence_residual=mass_residual,
        potential_circulation_residual=circulation_residual,
        nonlinear_iteration_count=iteration_count,
        nonlinear_update_residual=nonlinear_update_residual,
        velocity_potential=tuple(potential_values),
        model=model,
        radial_divisions=radial_divisions,
        message='compressible potential field encountered a zero-length perimeter segment',
      )
    tangent = (
      displacement[0] / segment_length,
      displacement[1] / segment_length,
    )
    computed_tangent_velocity = (
      potential_values[outer_start + next_index]
      - potential_values[outer_start + index]
    ) / segment_length
    prescribed_tangent_velocity = 0.5 * (
      (boundary_velocities[index][0] + boundary_velocities[next_index][0]) * tangent[0]
      + (boundary_velocities[index][1] + boundary_velocities[next_index][1]) * tangent[1]
    )
    boundary_velocity_residual = max(
      boundary_velocity_residual,
      abs(computed_tangent_velocity - prescribed_tangent_velocity),
    )

  boundary_normal_velocity_residual: float | None = None
  if (
    downstream_condition is not None
    and downstream_condition.tangency_condition_applicable
  ):
    try:
      boundary_normal_velocity_residual = (
        _potential_boundary_normal_velocity_residual(
          unique_points,
          connectivity,
          triangle_velocities,
          outer_start=outer_start,
          condition_edge_indices=downstream_condition.condition_edge_indices,
          position_tolerance_m=position_tolerance_m,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _field_failure(
        MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
        boundary,
        nodes=nodes,
        cells=cells,
        topology=topology,
        interior_point_m=center_point,
        maximum_velocity_divergence_residual=mass_residual,
        maximum_boundary_velocity_residual=boundary_velocity_residual,
        potential_circulation_residual=circulation_residual,
        nonlinear_iteration_count=iteration_count,
        nonlinear_update_residual=nonlinear_update_residual,
        velocity_potential=tuple(potential_values),
        maximum_boundary_normal_velocity_residual=(
          boundary_normal_velocity_residual
        ),
        downstream_condition=downstream_condition,
        model=model,
        radial_divisions=radial_divisions,
        message=f'compressible potential normal-flow measurement failed: {error}',
      )

  thermodynamic_residual = max(
    max(
      _relative_residual(_isentropic_total_pressure(sample), sample.total_pressure_Pa)
      for sample in nodes
    ),
    maximum_total_pressure_residual,
    maximum_gamma_residual,
  )
  maximum_mach = max(sample.mach for sample in nodes)
  if (
    mass_residual > residual_tolerance
    or boundary_velocity_residual > velocity_tolerance
    or (
      downstream_condition is not None
      and downstream_condition.tangency_condition_applicable
      and (
        boundary_normal_velocity_residual is None
        or boundary_normal_velocity_residual > velocity_tolerance
      )
    )
    or thermodynamic_residual > thermodynamic_tolerance
    or maximum_mach >= 1.0 - subsonic_margin
  ):
    return _field_failure(
      MocMixedRegimeFieldStatus.RESIDUAL_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_velocity_divergence_residual=mass_residual,
      maximum_mass_conservation_residual=mass_residual,
      maximum_boundary_velocity_residual=boundary_velocity_residual,
      maximum_boundary_normal_velocity_residual=(
        boundary_normal_velocity_residual
      ),
      potential_circulation_residual=circulation_residual,
      nonlinear_iteration_count=iteration_count,
      nonlinear_update_residual=nonlinear_update_residual,
      velocity_potential=tuple(potential_values),
      downstream_condition=downstream_condition,
      model=model,
      radial_divisions=radial_divisions,
      message=(
        'compressible potential field residual gate failed: '
        f'mass={mass_residual}, boundary_velocity={boundary_velocity_residual}, '
        'boundary_normal_velocity='
        f'{boundary_normal_velocity_residual}, '
        f'thermodynamic={thermodynamic_residual}, maximum_mach={maximum_mach}'
      ),
    )
  return MocMixedRegimeFieldResult(
    status=MocMixedRegimeFieldStatus.CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD,
    boundary=boundary,
    nodes=tuple(nodes),
    cells=cells,
    topology=topology,
    interior_point_m=center_point,
    maximum_thermodynamic_residual=thermodynamic_residual,
    maximum_harmonic_residual=initial_harmonic_residual,
    maximum_velocity_divergence_residual=mass_residual,
    minimum_mach=min(sample.mach for sample in nodes),
    maximum_mach=maximum_mach,
    model=model,
    radial_divisions=radial_divisions,
    downstream_condition=downstream_condition,
    maximum_mass_conservation_residual=mass_residual,
    maximum_boundary_velocity_residual=boundary_velocity_residual,
    maximum_boundary_normal_velocity_residual=(
      boundary_normal_velocity_residual
    ),
    potential_circulation_residual=circulation_residual,
    nonlinear_iteration_count=iteration_count,
    nonlinear_update_residual=nonlinear_update_residual,
    velocity_potential=tuple(potential_values),
    message=(
      'compressible isentropic potential field converged on the supplied '
      'closed perimeter with nonlinear mass, circulation, boundary-potential, '
      'strict-subsonic, and applicable no-penetration gates; this research '
      'reference remains separate from the supersonic MOC chain and does not '
      'infer a free boundary'
    ),
  )


def run_mixed_regime_closure_solver(
  request: MocMixedRegimePerimeterRequest,
  solve_field: Callable[
    [MocMixedRegimePerimeterRequest],
    MocMixedRegimeFieldResult | None,
  ],
) -> MocMixedRegimeClosureResult:
  """Run and gate a callback-owned mixed-regime perimeter solve.

  The callback receives the terminal seam and must return a field whose
  boundary carries the same terminal object and an explicitly closed
  perimeter.  A missing or mismatched field is returned as a typed failure;
  no scalar samples or geometry are synthesized here.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  if not callable(solve_field):
    raise TypeError('solve_field must be callable')
  try:
    field = solve_field(request)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.SOLVER_FAILURE,
      request=request,
      message=f'mixed-regime closure callback failed: {error}',
    )
  if field is None:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.SOLVER_FAILURE,
      request=request,
      message='mixed-regime closure callback returned no field',
    )
  if not isinstance(field, MocMixedRegimeFieldResult):
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.INVALID_INPUT,
      request=request,
      message='mixed-regime closure callback must return MocMixedRegimeFieldResult or None',
    )
  if field.boundary.terminal != request.terminal:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.SEAM_FAILURE,
      request=request,
      field=field,
      message='mixed-regime field terminal does not match the requested shock seam',
    )
  if field.boundary.supersonic_patch_sample_count != len(request.supersonic_patch):
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.SEAM_FAILURE,
      request=request,
      field=field,
      message=(
        'mixed-regime field does not retain the complete supersonic patch '
        'sample count from the requested seam'
      ),
    )
  if field.boundary.supersonic_patch != request.supersonic_patch:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.SEAM_FAILURE,
      request=request,
      field=field,
      message=(
        'mixed-regime field does not retain the exact supersonic patch '
        'states and pressure-loss samples from the requested seam'
      ),
    )
  if not field.converged or not field.boundary.converged:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.FIELD_FAILURE,
      request=request,
      field=field,
      message=(
        'mixed-regime closure callback returned a field without a converged '
        'boundary and field acceptance'
      ),
    )
  if not field.physical_closure_verified:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.FIELD_FAILURE,
      request=request,
      field=field,
      message=(
        'mixed-regime field model, topology, residual, or downstream physical '
        'condition gates are not complete'
      ),
    )
  return MocMixedRegimeClosureResult(
    status=MocMixedRegimeClosureStatus.CONVERGED,
    request=request,
    field=field,
    message=(
      'callback-supplied mixed-regime field matches the terminal seam and '
      'passed its explicit perimeter, topology, and residual gates'
    ),
  )
####


def _failure(
  status: MocMixedRegimeBoundaryStatus,
  *,
  terminal: MocMixedRegimeTerminal | None = None,
  supersonic_patch_sample_count: int = 0,
  supersonic_patch: Sequence[MocPostShockBoundaryState] = (),
  subsonic_samples: Sequence[MocMixedRegimeFieldSample] = (),
  perimeter_points_m: Sequence[tuple[float, float]] = (),
  supersonic_patch_verified: bool = False,
  subsonic_state_samples_verified: bool = False,
  terminal_continuity_verified: bool = False,
  perimeter_geometry_verified: bool = False,
  total_pressure_lineage_verified: bool = False,
  maximum_terminal_mach_residual: float | None = None,
  maximum_terminal_flow_angle_residual_rad: float | None = None,
  maximum_terminal_static_pressure_residual_Pa: float | None = None,
  maximum_terminal_total_pressure_residual_Pa: float | None = None,
  maximum_total_pressure_gain_Pa: float | None = None,
  message: str,
) -> MocMixedRegimeBoundaryResult:
  return MocMixedRegimeBoundaryResult(
    status=status,
    terminal=terminal,
    supersonic_patch_sample_count=supersonic_patch_sample_count,
    supersonic_patch=tuple(supersonic_patch),
    subsonic_samples=tuple(subsonic_samples),
    perimeter_points_m=tuple(perimeter_points_m),
    supersonic_patch_verified=supersonic_patch_verified,
    subsonic_state_samples_verified=subsonic_state_samples_verified,
    terminal_continuity_verified=terminal_continuity_verified,
    perimeter_geometry_verified=perimeter_geometry_verified,
    total_pressure_lineage_verified=total_pressure_lineage_verified,
    maximum_terminal_mach_residual=maximum_terminal_mach_residual,
    maximum_terminal_flow_angle_residual_rad=maximum_terminal_flow_angle_residual_rad,
    maximum_terminal_static_pressure_residual_Pa=maximum_terminal_static_pressure_residual_Pa,
    maximum_terminal_total_pressure_residual_Pa=maximum_terminal_total_pressure_residual_Pa,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain_Pa,
    message=message,
  )


def _terminal_scalars(
  terminal: MocMixedRegimeTerminal,
) -> tuple[tuple[float, float], float, float, float, float, float] | None:
  point = terminal.shock_point_m
  mach = terminal.downstream_mach
  flow_angle = terminal.downstream_flow_angle_rad
  static_pressure = terminal.downstream_pressure_Pa
  total_pressure = terminal.downstream_total_pressure_Pa
  upstream_total_pressure = terminal.upstream_total_pressure_Pa
  if (
    point is None
    or mach is None
    or flow_angle is None
    or static_pressure is None
    or total_pressure is None
    or upstream_total_pressure is None
  ):
    return None
  values = (*point, mach, flow_angle, static_pressure, total_pressure, upstream_total_pressure)
  if not all(isfinite(float(value)) for value in values):
    return None
  if mach <= 0.0 or mach >= 1.0:
    return None
  if static_pressure <= 0.0 or total_pressure <= 0.0 or upstream_total_pressure <= 0.0:
    return None
  if total_pressure > upstream_total_pressure:
    return None
  return (
    (float(point[0]), float(point[1])),
    float(mach),
    float(flow_angle),
    float(static_pressure),
    float(total_pressure),
    float(upstream_total_pressure),
  )


def validate_mixed_regime_boundary(
  terminal: MocMixedRegimeTerminal,
  supersonic_patch: Sequence[MocPostShockBoundaryState],
  *,
  supersonic_patch_converged: bool,
  subsonic_samples: Sequence[MocMixedRegimeFieldSample],
  perimeter_points_m: Sequence[tuple[float, float]] | None = None,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeBoundaryResult:
  """Validate a scalar subsonic perimeter without fabricating MOC states.

  The perimeter is an ordered, explicitly closed path.  Its first and last
  samples must reproduce the terminal shock scalar state.  All points must
  lie downstream of that terminal point.  The open supersonic patch is
  validated independently so a passing scalar perimeter cannot hide a gap in
  the preceding shock-side field.
  """

  if not isinstance(terminal, (MocNormalShockTerminalResult, MocSubsonicShockBoundaryResult)):
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      message='terminal must be a normal-shock or attached subsonic boundary result',
    )
  if not isinstance(supersonic_patch_converged, bool):
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      terminal=terminal,
      message='supersonic_patch_converged must be a bool',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    patch = tuple(supersonic_patch)
    samples = tuple(subsonic_samples)
  except TypeError:
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      terminal=terminal,
      message='supersonic_patch and subsonic_samples must be iterable',
    )
  if not terminal.converged or not terminal.subsonic:
    return _failure(
      MocMixedRegimeBoundaryStatus.TERMINAL_FAILURE,
      terminal=terminal,
      message='terminal must be a converged subsonic shock boundary',
    )
  scalars = _terminal_scalars(terminal)
  if scalars is None:
    return _failure(
      MocMixedRegimeBoundaryStatus.TERMINAL_FAILURE,
      terminal=terminal,
      message='terminal does not expose a complete finite scalar downstream state',
    )
  terminal_point, terminal_mach, terminal_angle, terminal_pressure, terminal_total_pressure, upstream_total_pressure = scalars

  if not supersonic_patch_converged or not patch:
    return _failure(
      MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      message='a converged open supersonic patch is required before subsonic closure',
    )
  for index, boundary_state in enumerate(patch):
    if not isinstance(boundary_state, MocPostShockBoundaryState):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} is not a MocPostShockBoundaryState',
      )
    state = boundary_state.state
    if state.mach <= 1.0:
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} is not supersonic',
      )
    if (
      abs(state.x_m - boundary_state.point_m[0]) > position_tolerance_m
      or abs(state.y_m - boundary_state.point_m[1]) > position_tolerance_m
    ):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} state coordinates do not match its point',
      )
    if (
      not isfinite(boundary_state.upstream_total_pressure_Pa)
      or not isfinite(boundary_state.downstream_total_pressure_Pa)
      or boundary_state.upstream_total_pressure_Pa <= 0.0
      or boundary_state.downstream_total_pressure_Pa <= 0.0
      or boundary_state.downstream_total_pressure_Pa >= boundary_state.upstream_total_pressure_Pa
    ):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} does not carry a strict total-pressure loss',
      )
  patch_verified = True

  if len(samples) < 4:
    return _failure(
      MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=samples,
      message='subsonic perimeter requires at least four scalar samples',
    )
  if any(not isinstance(sample, MocMixedRegimeFieldSample) for sample in samples):
    return _failure(
      MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=tuple(sample for sample in samples if isinstance(sample, MocMixedRegimeFieldSample)),
      message='subsonic_samples must contain MocMixedRegimeFieldSample values',
    )
  points = tuple(samples[index].point_m for index in range(len(samples)))
  if perimeter_points_m is not None:
    try:
      points = tuple((float(point[0]), float(point[1])) for point in perimeter_points_m)
    except (IndexError, TypeError, ValueError):
      return _failure(
        MocMixedRegimeBoundaryStatus.INVALID_INPUT,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        supersonic_patch_verified=patch_verified,
        subsonic_samples=samples,
        message='perimeter_points_m must contain finite two-coordinate points',
      )
    if len(points) != len(samples) or any(not all(isfinite(value) for value in point) for point in points):
      return _failure(
        MocMixedRegimeBoundaryStatus.INVALID_INPUT,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        supersonic_patch_verified=patch_verified,
        subsonic_samples=samples,
        perimeter_points_m=points,
        message='perimeter_points_m must match the scalar sample count and be finite',
      )
  if len(points) < 4:
    return _failure(
      MocMixedRegimeBoundaryStatus.GEOMETRY_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=samples,
      perimeter_points_m=points,
      message='subsonic perimeter requires at least four geometry points',
    )

  closed = hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1]) <= position_tolerance_m
  downstream = all(point[0] >= terminal_point[0] - position_tolerance_m for point in points)
  distinct_segments = all(
    hypot(second[0] - first[0], second[1] - first[1]) > position_tolerance_m
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  terminal_geometry_residual = max(
    hypot(points[0][0] - terminal_point[0], points[0][1] - terminal_point[1]),
    hypot(points[-1][0] - terminal_point[0], points[-1][1] - terminal_point[1]),
  )
  geometry_verified = closed and downstream and distinct_segments and terminal_geometry_residual <= position_tolerance_m
  if not geometry_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.GEOMETRY_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      perimeter_geometry_verified=False,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=None,
      maximum_terminal_flow_angle_residual_rad=None,
      maximum_terminal_static_pressure_residual_Pa=None,
      maximum_terminal_total_pressure_residual_Pa=None,
      maximum_total_pressure_gain_Pa=None,
      message=(
        'subsonic perimeter must be a distinct explicitly closed downstream '
        f'path anchored at the terminal point; closed={closed}, downstream={downstream}, '
        f'distinct_segments={distinct_segments}, terminal_residual_m={terminal_geometry_residual}'
      ),
    )

  seam_samples = (samples[0], samples[-1])
  mach_residual = max(abs(sample.mach - terminal_mach) for sample in seam_samples)
  angle_residual = max(abs(sample.flow_angle_rad - terminal_angle) for sample in seam_samples)
  static_residual = max(abs(sample.static_pressure_Pa - terminal_pressure) for sample in seam_samples)
  total_residual = max(abs(sample.total_pressure_Pa - terminal_total_pressure) for sample in seam_samples)
  seam_verified = (
    mach_residual <= state_tolerance
    and angle_residual <= state_tolerance
    and static_residual <= pressure_tolerance * max(1.0, abs(terminal_pressure))
    and total_residual <= pressure_tolerance * max(1.0, abs(terminal_total_pressure))
  )
  if not seam_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      terminal_continuity_verified=False,
      perimeter_geometry_verified=True,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=mach_residual,
      maximum_terminal_flow_angle_residual_rad=angle_residual,
      maximum_terminal_static_pressure_residual_Pa=static_residual,
      maximum_terminal_total_pressure_residual_Pa=total_residual,
      message='subsonic perimeter endpoints do not reproduce the scalar terminal shock state',
    )

  maximum_total_pressure_gain = max(
    sample.total_pressure_Pa - terminal_total_pressure
    for sample in samples
  )
  lineage_verified = maximum_total_pressure_gain <= pressure_tolerance * max(
    1.0,
    abs(terminal_total_pressure),
    abs(upstream_total_pressure),
  )
  if not lineage_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      terminal_continuity_verified=True,
      perimeter_geometry_verified=True,
      total_pressure_lineage_verified=False,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=mach_residual,
      maximum_terminal_flow_angle_residual_rad=angle_residual,
      maximum_terminal_static_pressure_residual_Pa=static_residual,
      maximum_terminal_total_pressure_residual_Pa=total_residual,
      maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
      message='subsonic perimeter contains a total-pressure gain over the terminal shock state',
    )

  return MocMixedRegimeBoundaryResult(
    status=MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF,
    terminal=terminal,
    supersonic_patch_sample_count=len(patch),
    supersonic_patch=patch,
    subsonic_samples=samples,
    perimeter_points_m=points,
    supersonic_patch_verified=patch_verified,
    subsonic_state_samples_verified=True,
    terminal_continuity_verified=True,
    perimeter_geometry_verified=True,
    total_pressure_lineage_verified=True,
    maximum_terminal_mach_residual=mach_residual,
    maximum_terminal_flow_angle_residual_rad=angle_residual,
    maximum_terminal_static_pressure_residual_Pa=static_residual,
    maximum_terminal_total_pressure_residual_Pa=total_residual,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
    message=(
      'scalar subsonic perimeter handoff passed shock-seam, open-supersonic-patch, '
      'geometry, and total-pressure lineage checks; a subsonic field mesh is still pending'
    ),
  )


def _control_section_failure(
  status: MocMixedRegimeControlSectionStatus,
  *,
  request: MocMixedRegimePerimeterRequest | None = None,
  section: MocMixedRegimeControlSection | None = None,
  section_measure_m: float | None = None,
  mass_flux_proxy: float | None = None,
  minimum_normal_flux_factor: float | None = None,
  maximum_total_pressure_gain_Pa: float | None = None,
  maximum_isentropic_residual: float | None = None,
  minimum_downstream_terminal_margin_m: float | None = None,
  maximum_terminal_state_residual: float | None = None,
  message: str,
) -> MocMixedRegimeControlSectionResult:
  return MocMixedRegimeControlSectionResult(
    status=status,
    request=request,
    section=section,
    section_measure_m=section_measure_m,
    mass_flux_proxy=mass_flux_proxy,
    minimum_normal_flux_factor=minimum_normal_flux_factor,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain_Pa,
    maximum_isentropic_residual=maximum_isentropic_residual,
    minimum_downstream_terminal_margin_m=minimum_downstream_terminal_margin_m,
    maximum_terminal_state_residual=maximum_terminal_state_residual,
    message=message,
  )


def validate_mixed_regime_control_section(
  request: MocMixedRegimePerimeterRequest,
  section: MocMixedRegimeControlSection | None,
  *,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
) -> MocMixedRegimeControlSectionResult:
  """Validate an explicit scalar section supplied to a downstream solver.

  The section is a missing boundary-value input for the canonical terminal:
  the normal shock supplies one subsonic point, not a finite area or a mass
  flux.  This validator therefore accepts only solver-supplied section data.
  It checks straight-section geometry, downstream placement, strict
  subsonic states, isentropic state consistency, no total-pressure gain over
  the terminal shock, and positive oriented flux.  It never samples or
  extends the open supersonic patch.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if section is None:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.INVALID_INPUT,
      request=request,
      message=(
        'a solver-supplied downstream control section is required; the open '
        'supersonic patch and terminal point do not provide area or mass flux'
      ),
    )
  if not isinstance(section, MocMixedRegimeControlSection):
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.INVALID_INPUT,
      request=request,
      message='section must be a MocMixedRegimeControlSection or None',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  terminal = request.terminal
  terminal_point = request.terminal_point_m
  terminal_mach = request.terminal_downstream_mach
  terminal_angle = request.terminal_downstream_flow_angle_rad
  terminal_total_pressure = request.terminal_downstream_total_pressure_Pa
  upstream_state = terminal.upstream_state
  if upstream_state is None:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.TERMINAL_FAILURE,
      request=request,
      section=section,
      section_measure_m=section.section_measure_m,
      message='terminal does not expose an upstream state for section validation',
    )

  measure = section.section_measure_m
  flux_factors = section.normal_flux_factors
  minimum_flux_factor = min(flux_factors, default=None)
  margins = tuple(
    (point[0] - terminal_point[0]) * cos(terminal_angle)
    + (point[1] - terminal_point[1]) * sin(terminal_angle)
    for point in section.points_m
  )
  minimum_margin = min(margins, default=None)
  maximum_isentropic_residual = max(
    (
      _relative_residual(
        _isentropic_total_pressure(sample),
        sample.total_pressure_Pa,
      )
      for sample in section.samples
    ),
    default=None,
  )
  maximum_total_pressure_gain = max(
    (
      max(0.0, sample.total_pressure_Pa - terminal_total_pressure)
      for sample in section.samples
    ),
    default=None,
  )
  maximum_terminal_state_residual = max(
    (
      max(
        abs(sample.mach - terminal_mach),
        abs(sample.flow_angle_rad - terminal_angle),
        _relative_residual(sample.total_pressure_Pa, terminal_total_pressure),
      )
      for sample in section.samples
    ),
    default=None,
  )
  try:
    mass_flux = section.mass_flux_proxy
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.FLUX_FAILURE,
      request=request,
      section=section,
      section_measure_m=measure,
      minimum_normal_flux_factor=minimum_flux_factor,
      maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
      maximum_isentropic_residual=maximum_isentropic_residual,
      minimum_downstream_terminal_margin_m=minimum_margin,
      maximum_terminal_state_residual=maximum_terminal_state_residual,
      message=f'control-section mass-flux evaluation failed: {error}',
    )

  common = {
    'request': request,
    'section': section,
    'section_measure_m': measure,
    'mass_flux_proxy': mass_flux,
    'minimum_normal_flux_factor': minimum_flux_factor,
    'maximum_total_pressure_gain_Pa': maximum_total_pressure_gain,
    'maximum_isentropic_residual': maximum_isentropic_residual,
    'minimum_downstream_terminal_margin_m': minimum_margin,
    'maximum_terminal_state_residual': maximum_terminal_state_residual,
  }
  if not isfinite(measure) or measure <= position_tolerance_m:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.GEOMETRY_FAILURE,
      **common,
      message='control section has no finite positive transverse measure',
    )
  if minimum_margin is None or minimum_margin <= position_tolerance_m:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.GEOMETRY_FAILURE,
      **common,
      message=(
        'every control-section point must lie strictly downstream of the '
        'terminal shock in the terminal flow direction'
      ),
    )
  if minimum_flux_factor is None or minimum_flux_factor <= normal_flux_tolerance:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.FLUX_FAILURE,
      **common,
      message='control-section samples must carry positive oriented normal flux',
    )
  if not isfinite(mass_flux) or mass_flux <= 0.0:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.FLUX_FAILURE,
      **common,
      message='control section must carry a finite positive mass-flux proxy',
    )
  if maximum_isentropic_residual is None or maximum_isentropic_residual > state_tolerance:
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.STATE_FAILURE,
      **common,
      message=(
        'control-section scalar states do not satisfy their local '
        f'isentropic total-pressure relation: residual={maximum_isentropic_residual}'
      ),
    )
  if maximum_total_pressure_gain is None or maximum_total_pressure_gain > (
    pressure_tolerance * max(1.0, abs(terminal_total_pressure))
  ):
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.STATE_FAILURE,
      **common,
      message=(
        'control section contains a total-pressure gain over the terminal '
        f'shock: gain={maximum_total_pressure_gain}'
      ),
    )
  if any(
    sample.gamma <= 1.0
    or abs(sample.gamma - upstream_state.gamma) > state_tolerance
    or sample.mach <= 0.0
    or sample.mach >= 1.0
    for sample in section.samples
  ):
    return _control_section_failure(
      MocMixedRegimeControlSectionStatus.STATE_FAILURE,
      **common,
      message=(
        'control-section samples must remain strictly subsonic and use the '
        'terminal gamma'
      ),
    )
  return MocMixedRegimeControlSectionResult(
    status=MocMixedRegimeControlSectionStatus.CONVERGED,
    request=request,
    section=section,
    section_measure_m=measure,
    mass_flux_proxy=mass_flux,
    minimum_normal_flux_factor=minimum_flux_factor,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
    maximum_isentropic_residual=maximum_isentropic_residual,
    minimum_downstream_terminal_margin_m=minimum_margin,
    maximum_terminal_state_residual=maximum_terminal_state_residual,
    message=(
      'explicit scalar subsonic control section passed geometry, terminal '
      'placement, state, pressure-lineage, and positive-flux checks; it is '
      'ready as input to a declared downstream reference solver'
    ),
  )


def _downstream_condition_failure(
  status: MocMixedRegimeDownstreamConditionStatus,
  *,
  condition_kind: MocMixedRegimeDownstreamConditionKind | None,
  boundary: MocMixedRegimeBoundaryResult | None = None,
  tangent_residuals_rad: Sequence[float] = (),
  pressure_residuals_Pa: Sequence[float] = (),
  tangency_condition_verified: bool = False,
  pressure_condition_verified: bool = False,
  condition_edge_indices: Sequence[int] = (),
  condition_sample_indices: Sequence[int] = (),
  message: str,
) -> MocMixedRegimeDownstreamConditionResult:
  tangent_residuals = tuple(float(value) for value in tangent_residuals_rad)
  pressure_residuals = tuple(float(value) for value in pressure_residuals_Pa)
  return MocMixedRegimeDownstreamConditionResult(
    status=status,
    condition_kind=condition_kind,
    boundary=boundary,
    tangent_residuals_rad=tangent_residuals,
    pressure_residuals_Pa=pressure_residuals,
    maximum_tangent_residual_rad=max(tangent_residuals, default=None),
    maximum_pressure_residual_Pa=max(
      (abs(value) for value in pressure_residuals),
      default=None,
    ),
    tangency_condition_verified=tangency_condition_verified,
    pressure_condition_verified=pressure_condition_verified,
    condition_edge_indices=tuple(condition_edge_indices),
    condition_sample_indices=tuple(condition_sample_indices),
    message=message,
  )


def _segment_flow_angle(
  first_angle_rad: float,
  second_angle_rad: float,
) -> float:
  """Interpolate directed flow angles across a polygon segment."""

  delta = (second_angle_rad - first_angle_rad + pi) % (2.0 * pi) - pi
  return first_angle_rad + 0.5 * delta


def _line_angle_residual(
  flow_angle_rad: float,
  tangent_angle_rad: float,
) -> float:
  """Return the acute residual between a flow direction and a line."""

  residual = (
    flow_angle_rad - tangent_angle_rad + 0.5 * pi
  ) % pi - 0.5 * pi
  return abs(residual)


def validate_mixed_regime_downstream_condition(
  boundary: MocMixedRegimeBoundaryResult,
  condition_kind: MocMixedRegimeDownstreamConditionKind,
  *,
  ambient_pressure_Pa: float | None = None,
  condition_edge_indices: Sequence[int] | None = None,
  condition_sample_indices: Sequence[int] | None = None,
  position_tolerance_m: float = 1.0e-10,
  tangent_tolerance_rad: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeDownstreamConditionResult:
  """Validate the physical condition carried by a scalar perimeter.

  The perimeter and scalar seam are validated first by
  :func:`validate_mixed_regime_boundary`.  This function then checks the
  condition that makes the perimeter physical: a slip wall requires the
  subsonic flow to be tangent to every boundary segment, an ambient free
  boundary requires both tangency and static-pressure matching, and a
  prescribed-pressure outflow section requires its declared static pressure.
  The open supersonic patch is never used as a replacement for this path.
  """

  if not isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind):
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=None,
      message='condition_kind must be a MocMixedRegimeDownstreamConditionKind',
    )
  try:
    for name, value in (
      ('position_tolerance_m', position_tolerance_m),
      ('tangent_tolerance_rad', tangent_tolerance_rad),
      ('pressure_tolerance', pressure_tolerance),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
  except (TypeError, ValueError) as error:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=condition_kind,
      boundary=boundary if isinstance(boundary, MocMixedRegimeBoundaryResult) else None,
      message=f'downstream condition inputs are invalid: {error}',
    )
  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=condition_kind,
      message='boundary must be a MocMixedRegimeBoundaryResult',
    )
  tangency_required = condition_kind in (
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
    MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
  )
  if condition_kind is MocMixedRegimeDownstreamConditionKind.SLIP_WALL:
    if ambient_pressure_Pa is not None:
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
        condition_kind=condition_kind,
        boundary=boundary,
        message='ambient_pressure_Pa is only valid for an ambient free boundary',
      )
    pressure_verified = True
  else:
    if ambient_pressure_Pa is None:
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
        condition_kind=condition_kind,
        boundary=boundary,
        message=(
          'ambient_pressure_Pa is required for an ambient free boundary or '
          'prescribed-pressure outflow section'
        ),
      )
    try:
      ambient_pressure = float(ambient_pressure_Pa)
    except (TypeError, ValueError):
      ambient_pressure = float('nan')
    if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
        condition_kind=condition_kind,
        boundary=boundary,
        message=(
          'ambient_pressure_Pa must be finite and positive for the declared '
          'pressure condition'
        ),
      )
    pressure_verified = False

  if not boundary.converged:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.BOUNDARY_FAILURE,
      condition_kind=condition_kind,
      boundary=boundary,
      pressure_condition_verified=pressure_verified,
      message=(
        'downstream physical condition requires a converged scalar perimeter: '
        f'{boundary.message}'
      ),
    )
  points = boundary.perimeter_points_m
  samples = boundary.subsonic_samples
  if len(points) != len(samples) or len(points) < 4:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.BOUNDARY_FAILURE,
      condition_kind=condition_kind,
      boundary=boundary,
      pressure_condition_verified=pressure_verified,
      message='downstream physical condition requires a closed perimeter with matching samples',
    )

  edge_count = len(points) - 1
  try:
    selected_edges = (
      tuple(range(edge_count))
      if condition_edge_indices is None
      else tuple(condition_edge_indices)
    )
    if condition_sample_indices is None:
      selected_samples = tuple(sorted({
        endpoint
        for edge_index in selected_edges
        for endpoint in (edge_index, edge_index + 1)
      }))
    else:
      selected_samples = tuple(condition_sample_indices)
  except TypeError:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=condition_kind,
      boundary=boundary,
      message=(
        'condition_edge_indices and condition_sample_indices must be iterable '
        'integer selections'
      ),
    )
  for name, indices, upper in (
    ('condition_edge_indices', selected_edges, edge_count - 1),
    ('condition_sample_indices', selected_samples, len(samples) - 1),
  ):
    if any(
      isinstance(index, bool)
      or not isinstance(index, int)
      or index < 0
      or index > upper
      for index in indices
    ):
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
        condition_kind=condition_kind,
        boundary=boundary,
        condition_edge_indices=selected_edges,
        condition_sample_indices=selected_samples,
        message=f'{name} contains an index outside the explicit perimeter range',
      )
    if len(set(indices)) != len(indices):
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
        condition_kind=condition_kind,
        boundary=boundary,
        condition_edge_indices=selected_edges,
        condition_sample_indices=selected_samples,
        message=f'{name} must not contain duplicate indices',
      )
  if tangency_required and not selected_edges:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=condition_kind,
      boundary=boundary,
      condition_edge_indices=selected_edges,
      condition_sample_indices=selected_samples,
      message='a tangency condition requires at least one selected perimeter edge',
    )
  if (
    condition_kind in (
      MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
      MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    )
    and not selected_samples
  ):
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=condition_kind,
      boundary=boundary,
      condition_edge_indices=selected_edges,
      condition_sample_indices=selected_samples,
      message='a pressure condition requires at least one selected perimeter sample',
    )

  tangent_residuals: list[float] = []
  if tangency_required:
    for edge_index in selected_edges:
      first_point = points[edge_index]
      second_point = points[edge_index + 1]
      first_sample = samples[edge_index]
      second_sample = samples[edge_index + 1]
      displacement = (
        second_point[0] - first_point[0],
        second_point[1] - first_point[1],
      )
      if hypot(*displacement) <= float(position_tolerance_m):
        return _downstream_condition_failure(
          MocMixedRegimeDownstreamConditionStatus.BOUNDARY_FAILURE,
          condition_kind=condition_kind,
          boundary=boundary,
          tangent_residuals_rad=tangent_residuals,
          pressure_condition_verified=pressure_verified,
          condition_edge_indices=selected_edges,
          condition_sample_indices=selected_samples,
          message='downstream physical condition encountered a zero-length perimeter segment',
        )
      tangent_angle = atan2(displacement[1], displacement[0])
      flow_angle = _segment_flow_angle(
        first_sample.flow_angle_rad,
        second_sample.flow_angle_rad,
      )
      tangent_residuals.append(
        _line_angle_residual(flow_angle, tangent_angle)
      )
    maximum_tangent_residual = max(tangent_residuals, default=float('inf'))
    tangency_verified = maximum_tangent_residual <= float(tangent_tolerance_rad)
    if not tangency_verified:
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.TANGENCY_FAILURE,
        condition_kind=condition_kind,
        boundary=boundary,
        tangent_residuals_rad=tangent_residuals,
        pressure_condition_verified=pressure_verified,
        condition_edge_indices=selected_edges,
        condition_sample_indices=selected_samples,
        message=(
          'subsonic flow is not tangent to the proposed downstream perimeter: '
          f'maximum residual={maximum_tangent_residual}'
        ),
      )
  else:
    maximum_tangent_residual = None
    tangency_verified = True

  pressure_residuals: tuple[float, ...] = ()
  if condition_kind in (
    MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
  ):
    assert ambient_pressure_Pa is not None
    ambient_pressure = float(ambient_pressure_Pa)
    pressure_residuals = tuple(
      samples[index].static_pressure_Pa - ambient_pressure
      for index in selected_samples
    )
    maximum_pressure_residual = max(
      (abs(value) for value in pressure_residuals),
      default=float('inf'),
    )
    pressure_verified = maximum_pressure_residual <= float(pressure_tolerance) * max(
      1.0,
      abs(ambient_pressure),
    )
    if not pressure_verified:
      return _downstream_condition_failure(
        MocMixedRegimeDownstreamConditionStatus.PRESSURE_FAILURE,
        condition_kind=condition_kind,
        boundary=boundary,
        tangent_residuals_rad=tangent_residuals,
        pressure_residuals_Pa=pressure_residuals,
        tangency_condition_verified=tangency_verified,
        pressure_condition_verified=False,
        condition_edge_indices=selected_edges,
        condition_sample_indices=selected_samples,
        message=(
          'subsonic perimeter does not match the requested ambient pressure: '
          f'maximum residual={maximum_pressure_residual}'
        ),
      )

  return MocMixedRegimeDownstreamConditionResult(
    status=MocMixedRegimeDownstreamConditionStatus.CONVERGED,
    condition_kind=condition_kind,
    boundary=boundary,
    tangent_residuals_rad=tuple(tangent_residuals),
    pressure_residuals_Pa=pressure_residuals,
    maximum_tangent_residual_rad=maximum_tangent_residual,
    maximum_pressure_residual_Pa=(
      None
      if not pressure_residuals
      else max(abs(value) for value in pressure_residuals)
    ),
    tangency_condition_verified=True,
    pressure_condition_verified=pressure_verified,
    condition_edge_indices=selected_edges,
    condition_sample_indices=selected_samples,
    message=(
      'subsonic downstream perimeter passed scalar seam and its declared '
      + (
        'kinematic tangency and physical pressure condition'
        if tangency_required
        else 'pressure-outflow condition without a tangency claim'
      )
    ),
  )


def solve_mixed_regime_downstream_condition(
  request: MocMixedRegimePerimeterRequest,
  solve_boundary: Callable[
    [MocMixedRegimePerimeterRequest],
    MocMixedRegimeBoundaryResult | None,
  ],
  *,
  condition_kind: MocMixedRegimeDownstreamConditionKind,
  ambient_pressure_Pa: float | None = None,
  position_tolerance_m: float = 1.0e-10,
  tangent_tolerance_rad: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeDownstreamConditionResult:
  """Run a solver-owned downstream-boundary callback and apply its gates.

  The callback owns the boundary construction.  This adapter only checks
  that it used the exact terminal shock seam and then applies the physical
  downstream-condition validator.  A missing or mismatched callback result
  cannot be turned into a guessed perimeter.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if not callable(solve_boundary):
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      message='solve_boundary must be callable',
    )
  try:
    boundary = solve_boundary(request)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.SOLVER_FAILURE,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      message=f'downstream boundary callback failed: {error}',
    )
  if boundary is None:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.SOLVER_FAILURE,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      message='downstream boundary callback returned no perimeter',
    )
  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.INVALID_INPUT,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      message='downstream boundary callback must return MocMixedRegimeBoundaryResult or None',
    )
  if boundary.terminal != request.terminal:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.BOUNDARY_FAILURE,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      boundary=boundary,
      message='downstream boundary callback changed the requested terminal seam',
    )
  if boundary.supersonic_patch != request.supersonic_patch:
    return _downstream_condition_failure(
      MocMixedRegimeDownstreamConditionStatus.BOUNDARY_FAILURE,
      condition_kind=(
        condition_kind
        if isinstance(condition_kind, MocMixedRegimeDownstreamConditionKind)
        else None
      ),
      boundary=boundary,
      message='downstream boundary callback changed the requested supersonic patch',
    )
  return validate_mixed_regime_downstream_condition(
    boundary,
    condition_kind,
    ambient_pressure_Pa=ambient_pressure_Pa,
    position_tolerance_m=position_tolerance_m,
    tangent_tolerance_rad=tangent_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
  )


def solve_mixed_regime_downstream_perimeter(
  request: MocMixedRegimePerimeterRequest,
  specification: MocMixedRegimeDownstreamPerimeterSpec,
  sample_at: Callable[
    [MocMixedRegimePerimeterRequest, int, tuple[float, float]],
    MocMixedRegimeFieldSample | None,
  ],
  *,
  radial_divisions: int = 1,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
) -> MocMixedRegimeClosureResult:
  """Solve a declared downstream perimeter through the reference field lane.

  ``specification`` owns the ordered closed geometry and the named boundary
  condition.  ``sample_at`` owns the scalar subsonic state model; this adapter
  never fills a missing sample from the terminal or the open supersonic patch.
  The returned closure is accepted only after the scalar seam, downstream
  condition, elliptic reference-field, and exact terminal-patch handoff gates
  all pass.  The model remains a finite-domain reference and does not infer a
  canonical plume perimeter or create a supersonic chain cell.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  if not isinstance(
    specification,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'specification must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  if not callable(sample_at):
    raise TypeError('sample_at must be callable')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    isinstance(radial_divisions, bool)
    or not isinstance(radial_divisions, int)
    or radial_divisions < 1
  ):
    raise ValueError('radial_divisions must be a positive integer')

  samples: list[MocMixedRegimeFieldSample] = []
  for index, point in enumerate(specification.perimeter_points_m):
    try:
      sample = sample_at(request, index, point)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocMixedRegimeClosureResult(
        status=MocMixedRegimeClosureStatus.SOLVER_FAILURE,
        request=request,
        perimeter_spec=specification,
        message=(
          f'mixed-regime scalar perimeter sampler failed at sample {index}: '
          f'{error}'
        ),
      )
    if not isinstance(sample, MocMixedRegimeFieldSample):
      return MocMixedRegimeClosureResult(
        status=MocMixedRegimeClosureStatus.INVALID_INPUT,
        request=request,
        perimeter_spec=specification,
        message=(
          'mixed-regime scalar perimeter sampler must return '
          'MocMixedRegimeFieldSample values'
        ),
      )
    if hypot(
      sample.point_m[0] - point[0],
      sample.point_m[1] - point[1],
    ) > float(position_tolerance_m):
      return MocMixedRegimeClosureResult(
        status=MocMixedRegimeClosureStatus.SEAM_FAILURE,
        request=request,
        perimeter_spec=specification,
        message=(
          f'mixed-regime scalar sample {index} changed the explicit perimeter '
          'coordinate'
        ),
      )
    samples.append(sample)

  boundary = validate_mixed_regime_boundary(
    request.terminal,
    request.supersonic_patch,
    supersonic_patch_converged=True,
    subsonic_samples=tuple(samples),
    perimeter_points_m=specification.perimeter_points_m,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
  )
  if not boundary.converged:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.SEAM_FAILURE,
      request=request,
      perimeter_spec=specification,
      message=(
        'explicit downstream perimeter failed the scalar seam/geometry '
        f'gate: {boundary.message}'
      ),
    )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    specification.condition_kind,
    ambient_pressure_Pa=specification.ambient_pressure_Pa,
    condition_edge_indices=(
      None
      if not specification.condition_edge_indices
      else specification.condition_edge_indices
    ),
    condition_sample_indices=(
      None
      if not specification.condition_sample_indices
      else specification.condition_sample_indices
    ),
    position_tolerance_m=position_tolerance_m,
    tangent_tolerance_rad=tangent_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
  )
  if not condition.converged:
    return MocMixedRegimeClosureResult(
      status=MocMixedRegimeClosureStatus.FIELD_FAILURE,
      request=request,
      downstream_condition=condition,
      perimeter_spec=specification,
      message=(
        'explicit downstream perimeter failed its declared physical '
        f'condition: {condition.message}'
      ),
    )
  field = solve_mixed_regime_subsonic_field(
    boundary,
    radial_divisions=radial_divisions,
    thermodynamic_tolerance=thermodynamic_tolerance,
    residual_tolerance=residual_tolerance,
    downstream_condition=condition,
  )
  result = run_mixed_regime_closure_solver(
    request,
    lambda _request: field,
  )
  return replace(
    result,
    downstream_condition=condition,
    perimeter_spec=specification,
    message=(
      result.message
      if result.message
      else 'explicit downstream perimeter reference solve completed'
    ),
  )


def _subsonic_area_ratio(mach: float, gamma: float) -> float:
  """Return the planar isentropic area ratio on the subsonic branch."""

  if (
    not isfinite(float(mach))
    or not isfinite(float(gamma))
    or gamma <= 1.0
    or mach <= 0.0
    or mach >= 1.0
  ):
    raise ValueError('subsonic area-ratio inputs must be finite and strictly subsonic')
  factor = 2.0 / (gamma + 1.0) * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  )
  return factor ** ((gamma + 1.0) / (2.0 * (gamma - 1.0))) / mach


def _subsonic_mach_from_area_ratio(
  area_ratio: float,
  gamma: float,
  *,
  iterations: int = 80,
) -> float:
  """Invert the isentropic area ratio without crossing the sonic branch."""

  if not isfinite(float(area_ratio)) or area_ratio < 1.0:
    raise ValueError('subsonic area ratio must be finite and at least one')
  if (
    isinstance(iterations, bool)
    or not isinstance(iterations, int)
    or iterations < 1
  ):
    raise ValueError('iterations must be a positive integer')
  lower = 1.0e-10
  upper = 1.0 - 1.0e-10
  for _ in range(iterations):
    midpoint = 0.5 * (lower + upper)
    if _subsonic_area_ratio(midpoint, gamma) > area_ratio:
      lower = midpoint
    else:
      upper = midpoint
  return 0.5 * (lower + upper)


def _subsonic_static_pressure_from_total(
  total_pressure_Pa: float,
  mach: float,
  gamma: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  return total_pressure_Pa / factor ** (gamma / (gamma - 1.0))


def _subsonic_mass_flux_factor(mach: float, gamma: float) -> float:
  """Return mass flux per unit area up to a common total-state factor."""

  exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))
  return mach * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (-exponent)


def _solve_free_boundary_reference_field(
  boundary: MocMixedRegimeBoundaryResult,
  downstream_condition: MocMixedRegimeDownstreamConditionResult,
  *,
  radial_divisions: int,
  mass_flow_residual: float,
  free_boundary_pressure_residual_Pa: float,
  free_boundary_tangent_residual_rad: float,
  centerline_tangent_residual_rad: float,
  outlet_pressure_residual_Pa: float,
  free_boundary_geometry_residual_m: float,
  thermodynamic_tolerance: float,
  residual_tolerance: float,
) -> MocMixedRegimeFieldResult:
  """Build the scalar mesh attached to the quasi-one-dimensional envelope."""

  model = 'solver-owned-subsonic-free-boundary-reference'
  samples = boundary.subsonic_samples
  unique_samples = tuple(samples[:-1])
  unique_points = tuple(boundary.perimeter_points_m[:-1])
  if len(unique_samples) < 3 or len(unique_points) != len(unique_samples):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      model=model,
      radial_divisions=radial_divisions,
      downstream_condition=downstream_condition,
      free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
      centerline_tangent_residual_rad=centerline_tangent_residual_rad,
      outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
      free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
      maximum_mass_conservation_residual=mass_flow_residual,
      message='free-boundary reference requires a closed scalar perimeter',
    )
  center_point = (
    sum(point[0] for point in unique_points) / len(unique_points),
    sum(point[1] for point in unique_points) / len(unique_points),
  )
  try:
    mach_levels, mach_residual = _harmonic_radial_levels(
      tuple(sample.mach for sample in unique_samples),
      radial_divisions,
    )
    angle_levels, angle_residual = _harmonic_radial_levels(
      tuple(sample.flow_angle_rad for sample in unique_samples),
      radial_divisions,
    )
    total_pressure_levels, total_pressure_residual = _harmonic_radial_levels(
      tuple(sample.total_pressure_Pa for sample in unique_samples),
      radial_divisions,
      logarithmic=True,
    )
    gamma_levels, gamma_residual = _harmonic_radial_levels(
      tuple(sample.gamma for sample in unique_samples),
      radial_divisions,
    )
    rings = _radial_mesh_points(unique_points, center_point, radial_divisions)
    cells, connectivity = _radial_mesh_connectivity(
      rings,
      len(unique_points),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      interior_point_m=center_point,
      model=model,
      radial_divisions=radial_divisions,
      downstream_condition=downstream_condition,
      free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
      centerline_tangent_residual_rad=centerline_tangent_residual_rad,
      outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
      free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
      maximum_mass_conservation_residual=mass_flow_residual,
      message=f'free-boundary reference mesh construction failed: {error}',
    )

  levels: list[tuple[MocMixedRegimeFieldSample, ...]] = []
  for level, points in enumerate(rings):
    level_samples: list[MocMixedRegimeFieldSample] = []
    for index, point in enumerate(points):
      mach = mach_levels[level][index]
      flow_angle = angle_levels[level][index]
      total_pressure = total_pressure_levels[level][index]
      gamma = gamma_levels[level][index]
      try:
        level_samples.append(
          MocMixedRegimeFieldSample(
            point_m=point,
            mach=mach,
            flow_angle_rad=flow_angle,
            static_pressure_Pa=_subsonic_static_pressure_from_total(
              total_pressure,
              mach,
              gamma,
            ),
            total_pressure_Pa=total_pressure,
            gamma=gamma,
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return _field_failure(
          MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
          boundary,
          nodes=tuple(sample for level_samples in levels for sample in level_samples),
          cells=cells,
          interior_point_m=center_point,
          model=model,
          radial_divisions=radial_divisions,
          downstream_condition=downstream_condition,
          free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
          free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
          centerline_tangent_residual_rad=centerline_tangent_residual_rad,
          outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
          free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
          maximum_mass_conservation_residual=mass_flow_residual,
          message=f'free-boundary scalar state construction failed: {error}',
        )
    levels.append(tuple(level_samples))
  nodes = tuple(sample for level_samples in levels for sample in level_samples)
  topology = validate_moc_mesh(cells)
  maximum_harmonic_residual = max(
    mach_residual,
    angle_residual,
    total_pressure_residual,
    gamma_residual,
  )
  thermodynamic_residual = max(
    _relative_residual(_isentropic_total_pressure(sample), sample.total_pressure_Pa)
    for sample in nodes
  )
  node_by_point = {sample.point_m: sample for sample in nodes}
  try:
    divergence_residual = max(
      _triangle_velocity_divergence(tuple(
        node_by_point[point] for point in cell.vertices_xr_m
      ))
      for cell in cells
      if len(cell.vertices_xr_m) == 3
    )
  except KeyError as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=maximum_harmonic_residual,
      model=model,
      radial_divisions=radial_divisions,
      downstream_condition=downstream_condition,
      free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
      centerline_tangent_residual_rad=centerline_tangent_residual_rad,
      outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
      free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
      maximum_mass_conservation_residual=mass_flow_residual,
      message=f'free-boundary reference cell/node lookup failed: {error}',
    )
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _field_failure(
      MocMixedRegimeFieldStatus.TOPOLOGY_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=maximum_harmonic_residual,
      maximum_velocity_divergence_residual=divergence_residual,
      model=model,
      radial_divisions=radial_divisions,
      downstream_condition=downstream_condition,
      free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
      centerline_tangent_residual_rad=centerline_tangent_residual_rad,
      outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
      free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
      maximum_mass_conservation_residual=mass_flow_residual,
      message=f'free-boundary reference mesh topology failed: {topology.message}',
    )
  if thermodynamic_residual > thermodynamic_tolerance or maximum_harmonic_residual > residual_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.RESIDUAL_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=maximum_harmonic_residual,
      maximum_velocity_divergence_residual=divergence_residual,
      model=model,
      radial_divisions=radial_divisions,
      downstream_condition=downstream_condition,
      free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
      centerline_tangent_residual_rad=centerline_tangent_residual_rad,
      outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
      free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
      maximum_mass_conservation_residual=mass_flow_residual,
      message=(
        'free-boundary reference scalar residual gate failed: '
        f'thermodynamic={thermodynamic_residual}, '
        f'harmonic={maximum_harmonic_residual}'
      ),
    )
  return MocMixedRegimeFieldResult(
    status=MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD,
    boundary=boundary,
    nodes=nodes,
    cells=cells,
    topology=topology,
    interior_point_m=center_point,
    maximum_thermodynamic_residual=thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=divergence_residual,
    minimum_mach=min(sample.mach for sample in nodes),
    maximum_mach=max(sample.mach for sample in nodes),
    model=model,
    radial_divisions=radial_divisions,
    downstream_condition=downstream_condition,
    maximum_mass_conservation_residual=mass_flow_residual,
    maximum_boundary_velocity_residual=free_boundary_tangent_residual_rad,
    free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
    free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
    centerline_tangent_residual_rad=centerline_tangent_residual_rad,
    outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
    free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
    message=(
      'solver-owned quasi-one-dimensional subsonic free-boundary reference '
      'converged on a closed scalar radial mesh; this model remains separate '
      'from the supersonic MOC lane'
    ),
  )


def solve_mixed_regime_downstream_free_boundary(
  request: MocMixedRegimePerimeterRequest,
  *,
  ambient_pressure_Pa: float,
  effective_inlet_height_m: float,
  downstream_length_m: float,
  free_boundary_sample_count: int = 7,
  radial_divisions: int = 2,
  terminal_regularization_fraction: float = 0.05,
  maximum_iterations: int = 40,
  height_tolerance_m: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
  subsonic_margin: float = 1.0e-6,
) -> MocMixedRegimeFreeBoundaryResult:
  """Solve a bounded solver-owned downstream free-boundary reference.

  The normal-shock seam supplies the subsonic total state.  A planar
  quasi-one-dimensional area relation then determines the outlet height that
  matches ``ambient_pressure_Pa``; the resulting centerline/outlet/ambient
  envelope is sampled into the exact mixed-regime perimeter contract and
  checked on a scalar radial mesh.  ``effective_inlet_height_m`` is an
  explicit model parameter because the terminal point alone does not contain
  an area.  The returned result is therefore a reproducible research
  reference, not an inferred canonical plume boundary.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  for name, value in (
    ('ambient_pressure_Pa', ambient_pressure_Pa),
    ('effective_inlet_height_m', effective_inlet_height_m),
    ('downstream_length_m', downstream_length_m),
    ('height_tolerance_m', height_tolerance_m),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('subsonic_margin', subsonic_margin),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if subsonic_margin >= 1.0:
    raise ValueError('subsonic_margin must be less than one')
  for name, value, minimum in (
    ('free_boundary_sample_count', free_boundary_sample_count, 3),
    ('radial_divisions', radial_divisions, 1),
    ('maximum_iterations', maximum_iterations, 1),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
      raise ValueError(f'{name} must be an integer greater than or equal to {minimum}')
  if not 0.0 < terminal_regularization_fraction < 1.0:
    raise ValueError('terminal_regularization_fraction must lie strictly between zero and one')
  if not isfinite(float(request.terminal_downstream_flow_angle_rad)):
    raise ValueError('terminal downstream flow angle must be finite')
  if abs(request.terminal_downstream_flow_angle_rad) > 1.0e-8:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.INVALID_INPUT,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=None,
      outlet_height_m=None,
      ambient_mach=None,
      outlet_mach=None,
      pressure_residual_Pa=None,
      mass_flow_residual=None,
      iteration_count=0,
      height_bracket_m=None,
      message=(
        'the axis-aligned free-boundary reference requires a zero terminal '
        'downstream flow angle'
      ),
    )

  terminal_mach = request.terminal_downstream_mach
  terminal_pressure = request.terminal_downstream_pressure_Pa
  total_pressure = request.terminal_downstream_total_pressure_Pa
  upstream_state = request.terminal.upstream_state
  if upstream_state is None:
    raise ValueError('request terminal must expose an upstream state for gamma')
  gamma = upstream_state.gamma
  pressure_factor = total_pressure / float(ambient_pressure_Pa)
  ambient_mach_squared = (
    2.0 / (gamma - 1.0)
    * (pressure_factor ** ((gamma - 1.0) / gamma) - 1.0)
  )
  if (
    not isfinite(ambient_mach_squared)
    or ambient_mach_squared <= 0.0
    or sqrt(ambient_mach_squared) >= 1.0 - subsonic_margin
  ):
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.PRESSURE_UNREACHABLE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=None,
      outlet_height_m=None,
      ambient_mach=None,
      outlet_mach=None,
      pressure_residual_Pa=None,
      mass_flow_residual=None,
      iteration_count=0,
      height_bracket_m=None,
      message=(
        'ambient pressure does not map to a positive strict-subsonic Mach '
        'number for the terminal total pressure'
      ),
    )
  ambient_mach = sqrt(ambient_mach_squared)
  terminal_area_ratio = _subsonic_area_ratio(terminal_mach, gamma)
  ambient_area_ratio = _subsonic_area_ratio(ambient_mach, gamma)
  target_height = (
    float(effective_inlet_height_m) * ambient_area_ratio / terminal_area_ratio
  )
  sonic_height = float(effective_inlet_height_m) / terminal_area_ratio

  def pressure_at_height(height: float) -> tuple[float, float]:
    area_ratio = terminal_area_ratio * height / float(effective_inlet_height_m)
    outlet_mach = _subsonic_mach_from_area_ratio(area_ratio, gamma)
    return (
      _subsonic_static_pressure_from_total(total_pressure, outlet_mach, gamma)
      - float(ambient_pressure_Pa),
      outlet_mach,
    )

  lower = sonic_height * (1.0 + 1.0e-8)
  upper = max(target_height * 1.5, lower * 2.0)
  try:
    lower_residual, _ = pressure_at_height(lower)
    upper_residual, _ = pressure_at_height(upper)
    for _ in range(24):
      if lower_residual <= 0.0 <= upper_residual:
        break
      upper *= 2.0
      upper_residual, _ = pressure_at_height(upper)
    else:
      raise ValueError(
        f'could not bracket ambient pressure: lower={lower_residual}, '
        f'upper={upper_residual}'
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.BRACKET_FAILURE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=target_height,
      outlet_height_m=None,
      ambient_mach=ambient_mach,
      outlet_mach=None,
      pressure_residual_Pa=None,
      mass_flow_residual=None,
      iteration_count=0,
      height_bracket_m=(lower, upper),
      message=f'free-boundary outlet-height bracket failed: {error}',
    )

  pressure_scale = max(1.0, abs(float(ambient_pressure_Pa)))
  root_height = target_height
  root_residual, root_mach = pressure_at_height(root_height)
  iteration_count = 0
  for iteration_index in range(maximum_iterations):
    midpoint = 0.5 * (lower + upper)
    midpoint_residual, midpoint_mach = pressure_at_height(midpoint)
    iteration_count = iteration_index + 1
    root_height = midpoint
    root_residual = midpoint_residual
    root_mach = midpoint_mach
    if (
      abs(midpoint_residual) <= pressure_tolerance * pressure_scale
      or upper - lower <= height_tolerance_m
    ):
      break
    if midpoint_residual > 0.0:
      upper = midpoint
    else:
      lower = midpoint

  if abs(root_residual) > pressure_tolerance * pressure_scale:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.BRACKET_FAILURE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=target_height,
      outlet_height_m=root_height,
      ambient_mach=ambient_mach,
      outlet_mach=root_mach,
      pressure_residual_Pa=abs(root_residual),
      mass_flow_residual=None,
      iteration_count=iteration_count,
      height_bracket_m=(lower, upper),
      message=(
        'free-boundary outlet-height shoot reached its iteration limit: '
        f'pressure_residual={root_residual}'
      ),
    )

  terminal_point = request.terminal_point_m
  x0, y0 = terminal_point
  outlet_centerline = (x0 + float(downstream_length_m), y0)
  outlet_outer = (x0 + float(downstream_length_m), y0 + root_height)
  free_points: list[tuple[float, float]] = []
  for index in range(free_boundary_sample_count):
    fraction = index / (free_boundary_sample_count - 1)
    radius_fraction = 1.0 - fraction * (1.0 - terminal_regularization_fraction)
    free_points.append((x0 + float(downstream_length_m) * radius_fraction, y0 + root_height * radius_fraction))
  if free_points[0] != outlet_outer:
    raise AssertionError('free-boundary construction did not start at the outlet')
  tangent_angle = atan2(root_height, float(downstream_length_m))
  points = (terminal_point, outlet_centerline, *free_points, terminal_point)
  terminal_sample = MocMixedRegimeFieldSample(
    point_m=terminal_point,
    mach=terminal_mach,
    flow_angle_rad=request.terminal_downstream_flow_angle_rad,
    static_pressure_Pa=terminal_pressure,
    total_pressure_Pa=total_pressure,
    gamma=gamma,
  )
  outlet_sample = MocMixedRegimeFieldSample(
    point_m=outlet_centerline,
    mach=root_mach,
    flow_angle_rad=request.terminal_downstream_flow_angle_rad,
    static_pressure_Pa=float(ambient_pressure_Pa),
    total_pressure_Pa=total_pressure,
    gamma=gamma,
  )
  free_samples = tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=ambient_mach,
      flow_angle_rad=tangent_angle,
      static_pressure_Pa=float(ambient_pressure_Pa),
      total_pressure_Pa=total_pressure,
      gamma=gamma,
    )
    for point in free_points
  )
  samples = (terminal_sample, outlet_sample, *free_samples, terminal_sample)
  boundary = validate_mixed_regime_boundary(
    request.terminal,
    request.supersonic_patch,
    supersonic_patch_converged=True,
    subsonic_samples=samples,
    perimeter_points_m=points,
    pressure_tolerance=pressure_tolerance,
  )
  if not boundary.converged:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.GEOMETRY_FAILURE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=target_height,
      outlet_height_m=root_height,
      ambient_mach=ambient_mach,
      outlet_mach=root_mach,
      pressure_residual_Pa=abs(root_residual),
      mass_flow_residual=None,
      iteration_count=iteration_count,
      height_bracket_m=(lower, upper),
      boundary=boundary,
      message=f'free-boundary perimeter failed its scalar seam: {boundary.message}',
    )

  outer_edge_start = 2
  outer_edge_stop = 2 + free_boundary_sample_count - 1
  specification = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=points,
    condition_kind=MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
    ambient_pressure_Pa=float(ambient_pressure_Pa),
    model='solver-owned-quasi-1d-ambient-free-boundary-reference',
    condition_edge_indices=tuple(range(outer_edge_start, outer_edge_stop)),
    condition_sample_indices=tuple(range(outer_edge_start, outer_edge_stop + 1)),
  )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    specification.condition_kind,
    ambient_pressure_Pa=specification.ambient_pressure_Pa,
    condition_edge_indices=specification.condition_edge_indices,
    condition_sample_indices=specification.condition_sample_indices,
    tangent_tolerance_rad=tangent_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
  )
  if not condition.converged:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.CONDITION_FAILURE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=target_height,
      outlet_height_m=root_height,
      ambient_mach=ambient_mach,
      outlet_mach=root_mach,
      pressure_residual_Pa=abs(root_residual),
      mass_flow_residual=None,
      iteration_count=iteration_count,
      height_bracket_m=(lower, upper),
      boundary=boundary,
      downstream_condition=condition,
      perimeter_spec=specification,
      message=f'free-boundary condition failed: {condition.message}',
    )

  centerline_tangent_residual = _line_angle_residual(
    _segment_flow_angle(
      samples[0].flow_angle_rad,
      samples[1].flow_angle_rad,
    ),
    atan2(
      points[1][1] - points[0][1],
      points[1][0] - points[0][0],
    ),
  )
  outlet_pressure_residual = max(
    abs(samples[index].static_pressure_Pa - float(ambient_pressure_Pa))
    for index in (1, 2)
  )
  mass_terminal = (
    float(effective_inlet_height_m)
    * _subsonic_mass_flux_factor(terminal_mach, gamma)
  )
  mass_outlet = root_height * _subsonic_mass_flux_factor(root_mach, gamma)
  mass_flow_residual = abs(mass_outlet - mass_terminal) / max(1.0, abs(mass_terminal))
  free_boundary_geometry_residual = max(
    abs(
      (point[1] - y0) * float(downstream_length_m)
      - (point[0] - x0) * root_height
    )
    / max(1.0, root_height, float(downstream_length_m))
    for point in free_points
  )
  field = _solve_free_boundary_reference_field(
    boundary,
    condition,
    radial_divisions=radial_divisions,
    mass_flow_residual=mass_flow_residual,
    free_boundary_pressure_residual_Pa=max(
      abs(samples[index].static_pressure_Pa - float(ambient_pressure_Pa))
      for index in specification.condition_sample_indices
    ),
    free_boundary_tangent_residual_rad=condition.maximum_tangent_residual_rad or 0.0,
    centerline_tangent_residual_rad=centerline_tangent_residual,
    outlet_pressure_residual_Pa=outlet_pressure_residual,
    free_boundary_geometry_residual_m=free_boundary_geometry_residual,
    thermodynamic_tolerance=thermodynamic_tolerance,
    residual_tolerance=residual_tolerance,
  )
  if not field.converged or not field.model_closure_verified:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.FIELD_FAILURE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=target_height,
      outlet_height_m=root_height,
      ambient_mach=ambient_mach,
      outlet_mach=root_mach,
      pressure_residual_Pa=abs(root_residual),
      mass_flow_residual=mass_flow_residual,
      iteration_count=iteration_count,
      height_bracket_m=(lower, upper),
      boundary=boundary,
      downstream_condition=condition,
      field=field,
      perimeter_spec=specification,
      message=f'free-boundary scalar field failed its model gates: {field.message}',
    )
  closure = run_mixed_regime_closure_solver(
    request,
    lambda _request: field,
  )
  if not closure.converged:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.FIELD_FAILURE,
      request=request,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      effective_inlet_height_m=float(effective_inlet_height_m),
      downstream_length_m=float(downstream_length_m),
      target_outlet_height_m=target_height,
      outlet_height_m=root_height,
      ambient_mach=ambient_mach,
      outlet_mach=root_mach,
      pressure_residual_Pa=abs(root_residual),
      mass_flow_residual=mass_flow_residual,
      iteration_count=iteration_count,
      height_bracket_m=(lower, upper),
      boundary=boundary,
      downstream_condition=condition,
      field=field,
      closure=closure,
      perimeter_spec=specification,
      message=f'free-boundary closure seam failed: {closure.message}',
    )
  return MocMixedRegimeFreeBoundaryResult(
    status=MocMixedRegimeFreeBoundaryStatus.CONVERGED_REFERENCE,
    request=request,
    ambient_pressure_Pa=float(ambient_pressure_Pa),
    effective_inlet_height_m=float(effective_inlet_height_m),
    downstream_length_m=float(downstream_length_m),
    target_outlet_height_m=target_height,
    outlet_height_m=root_height,
    ambient_mach=ambient_mach,
    outlet_mach=root_mach,
    pressure_residual_Pa=abs(root_residual),
    mass_flow_residual=mass_flow_residual,
    iteration_count=iteration_count,
    height_bracket_m=(lower, upper),
    boundary=boundary,
    downstream_condition=condition,
    field=field,
    closure=closure,
    perimeter_spec=specification,
    message=(
      'solver-owned quasi-one-dimensional outlet-height shoot, ambient free '
      'boundary condition, scalar radial field, and exact terminal seam passed; '
      'canonical reflected-MOC coupling and external validation remain pending'
    ),
  )


def solve_mixed_regime_downstream_free_boundary_from_control_section(
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  *,
  ambient_pressure_Pa: float,
  downstream_length_m: float,
  free_boundary_sample_count: int = 7,
  radial_divisions: int = 2,
  terminal_regularization_fraction: float = 0.05,
  maximum_iterations: int = 40,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  control_section_projection_tolerance: float = 1.0e-8,
  height_tolerance_m: float = 1.0e-10,
  tangent_tolerance_rad: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
  subsonic_margin: float = 1.0e-6,
) -> MocMixedRegimeFreeBoundaryResult:
  """Run the quasi-one-dimensional reference from an explicit control section.

  The control section is the only source of the effective inlet measure in
  this adapter.  A section whose scalar states vary from the terminal state is
  rejected instead of being collapsed into a one-dimensional height: that
  case requires a genuine downstream two-dimensional mixed-regime solver.
  This preserves a useful planner/reference path while making the fidelity
  boundary executable and visible in the result.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection'
    )
  for name, value in (
    ('ambient_pressure_Pa', ambient_pressure_Pa),
    ('downstream_length_m', downstream_length_m),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
    ('control_section_projection_tolerance', control_section_projection_tolerance),
    ('height_tolerance_m', height_tolerance_m),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('subsonic_margin', subsonic_margin),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if subsonic_margin >= 1.0:
    raise ValueError('subsonic_margin must be less than one')
  for name, value, minimum in (
    ('free_boundary_sample_count', free_boundary_sample_count, 3),
    ('radial_divisions', radial_divisions, 1),
    ('maximum_iterations', maximum_iterations, 1),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
      raise ValueError(f'{name} must be an integer greater than or equal to {minimum}')
  if not 0.0 < terminal_regularization_fraction < 1.0:
    raise ValueError(
      'terminal_regularization_fraction must lie strictly between zero and one'
    )

  validation = validate_mixed_regime_control_section(
    request,
    control_section,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
  )
  effective_inlet_height = control_section.section_measure_m
  common = {
    'request': request,
    'ambient_pressure_Pa': float(ambient_pressure_Pa),
    'effective_inlet_height_m': effective_inlet_height,
    'downstream_length_m': float(downstream_length_m),
    'target_outlet_height_m': None,
    'outlet_height_m': None,
    'ambient_mach': None,
    'outlet_mach': None,
    'pressure_residual_Pa': None,
    'mass_flow_residual': None,
    'iteration_count': 0,
    'height_bracket_m': None,
    'control_section': control_section,
    'control_section_validation': validation,
    'model': 'solver-owned-control-section-quasi-1d-reference',
  }
  if not validation.converged:
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
      message=(
        'explicit downstream control section failed its input gates: '
        f'{validation.message}'
      ),
      **common,
    )
  maximum_terminal_state_residual = validation.maximum_terminal_state_residual
  if (
    maximum_terminal_state_residual is None
    or maximum_terminal_state_residual > control_section_projection_tolerance
  ):
    return MocMixedRegimeFreeBoundaryResult(
      status=MocMixedRegimeFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
      message=(
        'the control section is not terminal-equivalent within the declared '
        'quasi-one-dimensional projection tolerance; a varying section must '
        'be solved by the pending downstream two-dimensional mixed-regime '
        f'coupling, residual={maximum_terminal_state_residual}'
      ),
      **common,
    )

  result = solve_mixed_regime_downstream_free_boundary(
    request,
    ambient_pressure_Pa=ambient_pressure_Pa,
    effective_inlet_height_m=effective_inlet_height,
    downstream_length_m=downstream_length_m,
    free_boundary_sample_count=free_boundary_sample_count,
    radial_divisions=radial_divisions,
    terminal_regularization_fraction=terminal_regularization_fraction,
    maximum_iterations=maximum_iterations,
    height_tolerance_m=height_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance_rad=tangent_tolerance_rad,
    thermodynamic_tolerance=thermodynamic_tolerance,
    residual_tolerance=residual_tolerance,
    subsonic_margin=subsonic_margin,
  )
  return replace(
    result,
    model='solver-owned-control-section-quasi-1d-reference',
    control_section=control_section,
    control_section_validation=validation,
    control_section_projection_verified=True,
    message=(
      f'{result.message} Explicit terminal-equivalent control section '
      'supplied the effective inlet measure; varying-section two-dimensional '
      'coupling and external validation remain pending.'
    ),
  )
