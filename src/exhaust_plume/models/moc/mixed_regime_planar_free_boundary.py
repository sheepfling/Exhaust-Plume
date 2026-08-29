"""Research-only planar free-boundary continuation for the mixed-regime lane.

The terminal shock and an explicit scalar control section do not determine a
downstream perimeter by themselves.  This module adds a bounded numerical
candidate: a discrete convex envelope is iterated against the signed normal
velocity residual of the existing nonlinear compressible-potential field.

The candidate is deliberately kept below the canonical claim ceiling.  It is
not a characteristic-state field, does not continue a supersonic shock-cell
chain, and does not replace the fast visualization providers.  Its purpose is
to make the remaining 2-D free-boundary seam concrete, reproducible, and
independently measurable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from itertools import accumulate
from math import atan2, cos, exp, hypot, isfinite, log, sin, sqrt
from typing import Sequence

from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeBoundaryResult,
  MocMixedRegimeClosureResult,
  MocMixedRegimeControlSection,
  MocMixedRegimeControlSectionResult,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionResult,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  MocMixedRegimeFieldStatus,
  MocMixedRegimePerimeterRequest,
  validate_mixed_regime_boundary,
  validate_mixed_regime_control_section,
  validate_mixed_regime_downstream_condition,
  solve_mixed_regime_compressible_potential_field,
)
from exhaust_plume.models.moc.mixed_regime_planar import (
  MocMixedRegimePlanarSolveResult,
  run_mixed_regime_planar_field_solver,
)

__all__ = (
  'MocMixedRegimePlanarFreeBoundaryStatus',
  'MocMixedRegimePlanarFreeBoundaryResult',
  'MocMixedRegimePlanarFreeBoundaryReference',
  'solve_mixed_regime_planar_free_boundary_reference',
)


class MocMixedRegimePlanarFreeBoundaryStatus(str, Enum):
  """Outcome of the parameterized planar free-boundary reference."""

  CONVERGED_REFERENCE = 'converged-parameterized-planar-free-boundary-reference'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'planar-free-boundary-terminal-failure'
  CONTROL_SECTION_FAILURE = 'planar-free-boundary-control-section-failure'
  PRESSURE_UNREACHABLE = 'planar-free-boundary-pressure-unreachable'
  GEOMETRY_FAILURE = 'planar-free-boundary-geometry-failure'
  CONDITION_FAILURE = 'planar-free-boundary-condition-failure'
  FIELD_FAILURE = 'planar-free-boundary-field-failure'
  ITERATION_FAILURE = 'planar-free-boundary-iteration-failure'


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarFreeBoundaryResult:
  """Auditable result for one parameterized planar envelope solve.

  A converged result means that the explicit terminal/control-section seam,
  the parameterized perimeter, the ambient-pressure/tangency condition, and
  the nonlinear potential field all passed their local gates.  It does not
  establish the canonical reflected-MOC free boundary or external plume
  validation; those claims remain explicitly disabled.
  """

  status: MocMixedRegimePlanarFreeBoundaryStatus
  request: MocMixedRegimePerimeterRequest
  control_section: MocMixedRegimeControlSection
  control_section_validation: MocMixedRegimeControlSectionResult
  ambient_pressure_Pa: float
  downstream_length_m: float
  outlet_height_m: float
  free_boundary_sample_count: int
  centerline_sample_count: int
  radial_divisions: int
  iteration_count: int
  shape_heights_m: tuple[float, ...] = ()
  initial_shape_heights_m: tuple[float, ...] = ()
  residual_history: tuple[float, ...] = ()
  signed_free_boundary_residuals: tuple[float, ...] = ()
  maximum_boundary_normal_velocity_residual: float | None = None
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec | None = None
  boundary: MocMixedRegimeBoundaryResult | None = None
  downstream_condition: MocMixedRegimeDownstreamConditionResult | None = None
  field: MocMixedRegimeFieldResult | None = None
  handoff: MocMixedRegimePlanarSolveResult | None = None
  closure: MocMixedRegimeClosureResult | None = None
  centerline_speed_m_s_normalized: float | None = None
  control_section_mean_normal_speed_m_s_normalized: float | None = None
  model: str = (
    'parameterized-2d-compressible-potential-free-boundary-reference'
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocMixedRegimePlanarFreeBoundaryStatus,
    ):
      raise TypeError(
        'status must be a MocMixedRegimePlanarFreeBoundaryStatus'
      )
    if not isinstance(self.request, MocMixedRegimePerimeterRequest):
      raise TypeError(
        'request must be a MocMixedRegimePerimeterRequest'
      )
    if not isinstance(self.control_section, MocMixedRegimeControlSection):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection'
      )
    if not isinstance(
      self.control_section_validation,
      MocMixedRegimeControlSectionResult,
    ):
      raise TypeError(
        'control_section_validation must be a '
        'MocMixedRegimeControlSectionResult'
      )
    if self.control_section_validation.section not in (
      None,
      self.control_section,
    ):
      raise ValueError(
        'control_section_validation must retain the exact control section'
      )
    for name, value in (
      ('ambient_pressure_Pa', self.ambient_pressure_Pa),
      ('downstream_length_m', self.downstream_length_m),
      ('outlet_height_m', self.outlet_height_m),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, numeric)
    for name, value, minimum in (
      ('free_boundary_sample_count', self.free_boundary_sample_count, 4),
      ('centerline_sample_count', self.centerline_sample_count, 2),
      ('radial_divisions', self.radial_divisions, 1),
      ('iteration_count', self.iteration_count, 0),
    ):
      if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
      ):
        raise ValueError(
          f'{name} must be an integer greater than or equal to {minimum}'
        )
    for name in (
      'shape_heights_m',
      'initial_shape_heights_m',
      'residual_history',
      'signed_free_boundary_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) for value in values):
        raise ValueError(f'{name} must contain finite values')
      object.__setattr__(self, name, values)
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
    for name in (
      'centerline_speed_m_s_normalized',
      'control_section_mean_normal_speed_m_s_normalized',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric):
          raise ValueError(f'{name} must be finite when supplied')
        object.__setattr__(self, name, numeric)
    if self.perimeter_spec is not None and not isinstance(
      self.perimeter_spec,
      MocMixedRegimeDownstreamPerimeterSpec,
    ):
      raise TypeError(
        'perimeter_spec must be a '
        'MocMixedRegimeDownstreamPerimeterSpec or None'
      )
    if self.boundary is not None and not isinstance(
      self.boundary,
      MocMixedRegimeBoundaryResult,
    ):
      raise TypeError('boundary must be a MocMixedRegimeBoundaryResult or None')
    if self.downstream_condition is not None and not isinstance(
      self.downstream_condition,
      MocMixedRegimeDownstreamConditionResult,
    ):
      raise TypeError(
        'downstream_condition must be a '
        'MocMixedRegimeDownstreamConditionResult or None'
      )
    if self.field is not None and not isinstance(
      self.field,
      MocMixedRegimeFieldResult,
    ):
      raise TypeError('field must be a MocMixedRegimeFieldResult or None')
    if self.handoff is not None and not isinstance(
      self.handoff,
      MocMixedRegimePlanarSolveResult,
    ):
      raise TypeError(
        'handoff must be a MocMixedRegimePlanarSolveResult or None'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether the local parameterized free-boundary reference converged."""

    return bool(
      self.status is MocMixedRegimePlanarFreeBoundaryStatus.CONVERGED_REFERENCE
      and self.handoff is not None
      and self.handoff.converged
      and self.field is not None
      and self.field.converged
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Expose local potential-field closure, not canonical plume closure."""

    return bool(self.converged and self.field is not None and self.field.physical_closure_verified)

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The canonical reflected-MOC free boundary remains unresolved."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    """A subsonic potential field cannot seed another supersonic cell."""

    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, object]:
    """Return geometry, iteration, field, and claim-boundary evidence."""

    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'model': self.model,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'downstream_length_m': self.downstream_length_m,
      'outlet_height_m': self.outlet_height_m,
      'free_boundary_sample_count': self.free_boundary_sample_count,
      'centerline_sample_count': self.centerline_sample_count,
      'radial_divisions': self.radial_divisions,
      'iteration_count': self.iteration_count,
      'shape_heights_m': self.shape_heights_m,
      'initial_shape_heights_m': self.initial_shape_heights_m,
      'residual_history': self.residual_history,
      'signed_free_boundary_residuals': self.signed_free_boundary_residuals,
      'maximum_boundary_normal_velocity_residual': (
        self.maximum_boundary_normal_velocity_residual
      ),
      'centerline_speed_m_s_normalized': self.centerline_speed_m_s_normalized,
      'control_section_mean_normal_speed_m_s_normalized': (
        self.control_section_mean_normal_speed_m_s_normalized
      ),
      'control_section': self.control_section.as_report(),
      'control_section_validation': self.control_section_validation.as_report(),
      'perimeter_spec': (
        None if self.perimeter_spec is None else self.perimeter_spec.as_report()
      ),
      'boundary': None if self.boundary is None else self.boundary.as_report(),
      'downstream_condition': (
        None
        if self.downstream_condition is None
        else self.downstream_condition.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'handoff': None if self.handoff is None else self.handoff.as_report(),
      'closure': (
        None
        if self.closure is None
        else self.closure.as_report()
      ),
      'claim_status': (
        'parameterized-2d-compressible-potential-free-boundary-reference; '
        'canonical-reflected-moc-free-boundary-and-external-validation-pending'
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarFreeBoundaryReference:
  """Convenience configuration for the parameterized 2-D reference."""

  free_boundary_sample_count: int = 8
  centerline_sample_count: int = 3
  radial_divisions: int = 2
  maximum_iterations: int = 40
  potential_maximum_iterations: int = 80
  position_tolerance_m: float = 1.0e-10
  state_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance_rad: float = 2.0e-2
  normal_flux_tolerance: float = 1.0e-8
  thermodynamic_tolerance: float = 1.0e-8
  potential_tolerance: float = 1.0e-10
  residual_tolerance: float = 1.0e-10
  velocity_tolerance: float = 1.0e-8
  subsonic_margin: float = 1.0e-6
  initial_free_boundary_fraction: float = 0.8
  model: str = (
    'parameterized-2d-compressible-potential-free-boundary-reference'
  )

  def __post_init__(self) -> None:
    for name, value, minimum in (
      ('free_boundary_sample_count', self.free_boundary_sample_count, 4),
      ('centerline_sample_count', self.centerline_sample_count, 2),
      ('radial_divisions', self.radial_divisions, 1),
      ('maximum_iterations', self.maximum_iterations, 1),
      ('potential_maximum_iterations', self.potential_maximum_iterations, 1),
    ):
      if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
      ):
        raise ValueError(
          f'{name} must be an integer greater than or equal to {minimum}'
        )
    for name, value in (
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
    if not 0.0 < self.initial_free_boundary_fraction < 1.0:
      raise ValueError('initial_free_boundary_fraction must lie between zero and one')
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
    *,
    ambient_pressure_Pa: float,
    downstream_length_m: float,
    outlet_height_m: float,
    initial_free_boundary_heights_m: Sequence[float] | None = None,
  ) -> MocMixedRegimePlanarFreeBoundaryResult:
    """Solve one explicit terminal/control-section case."""

    return solve_mixed_regime_planar_free_boundary_reference(
      request,
      control_section,
      ambient_pressure_Pa=ambient_pressure_Pa,
      downstream_length_m=downstream_length_m,
      outlet_height_m=outlet_height_m,
      free_boundary_sample_count=self.free_boundary_sample_count,
      centerline_sample_count=self.centerline_sample_count,
      radial_divisions=self.radial_divisions,
      maximum_iterations=self.maximum_iterations,
      potential_maximum_iterations=self.potential_maximum_iterations,
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
      initial_free_boundary_fraction=self.initial_free_boundary_fraction,
      initial_free_boundary_heights_m=initial_free_boundary_heights_m,
      solver_model=self.model,
    )

  def as_report(self) -> dict[str, object]:
    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'free_boundary_sample_count': self.free_boundary_sample_count,
      'centerline_sample_count': self.centerline_sample_count,
      'radial_divisions': self.radial_divisions,
      'maximum_iterations': self.maximum_iterations,
      'potential_maximum_iterations': self.potential_maximum_iterations,
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
      'initial_free_boundary_fraction': self.initial_free_boundary_fraction,
      'shape_parameterization': 'concave-discrete-free-boundary-heights',
      'claim_status': (
        'parameterized-2d-compressible-potential-free-boundary-reference; '
        'canonical-reflected-moc-free-boundary-and-external-validation-pending'
      ),
    }


@dataclass(frozen=True, slots=True)
class _PlanarFreeBoundaryCandidate:
  shape_heights_m: tuple[float, ...]
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec
  boundary: MocMixedRegimeBoundaryResult
  downstream_condition: MocMixedRegimeDownstreamConditionResult
  field: MocMixedRegimeFieldResult
  signed_residuals: tuple[float, ...]
  centerline_speed: float
  control_section_mean_speed: float


def _result(
  status: MocMixedRegimePlanarFreeBoundaryStatus,
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  control_section_validation: MocMixedRegimeControlSectionResult,
  *,
  ambient_pressure_Pa: float,
  downstream_length_m: float,
  outlet_height_m: float,
  free_boundary_sample_count: int,
  centerline_sample_count: int,
  radial_divisions: int,
  iteration_count: int,
  message: str,
  **kwargs: object,
) -> MocMixedRegimePlanarFreeBoundaryResult:
  return MocMixedRegimePlanarFreeBoundaryResult(
    status=status,
    request=request,
    control_section=control_section,
    control_section_validation=control_section_validation,
    ambient_pressure_Pa=ambient_pressure_Pa,
    downstream_length_m=downstream_length_m,
    outlet_height_m=outlet_height_m,
    free_boundary_sample_count=free_boundary_sample_count,
    centerline_sample_count=centerline_sample_count,
    radial_divisions=radial_divisions,
    iteration_count=iteration_count,
    message=message,
    **kwargs,
  )


def _sigmoid(value: float) -> float:
  bounded = max(-40.0, min(40.0, float(value)))
  return 1.0 / (1.0 + exp(-bounded))


def _logit(value: float) -> float:
  bounded = max(1.0e-12, min(1.0 - 1.0e-12, float(value)))
  return log(bounded / (1.0 - bounded))


def _shape_heights_from_parameters(
  parameters: Sequence[float],
  *,
  outlet_height_m: float,
  downstream_length_m: float,
  free_boundary_sample_count: int,
  minimum_height_m: float,
) -> tuple[float, ...]:
  edge_count = free_boundary_sample_count - 1
  if len(parameters) != edge_count + 1:
    raise ValueError('free-boundary shape parameter vector has an invalid length')
  if float(parameters[0]) >= 19.0:
    return tuple(
      float(outlet_height_m)
      for _ in range(free_boundary_sample_count)
    )
  first_fraction = _sigmoid(float(parameters[0]))
  first_height = minimum_height_m + (
    outlet_height_m - minimum_height_m
  ) * first_fraction
  raw_weights = tuple(
    exp(max(-30.0, min(30.0, float(value))))
    for value in parameters[1:]
  )
  total_weight = sum(raw_weights)
  if not isfinite(total_weight) or total_weight <= 0.0:
    raise ValueError('free-boundary shape weights are not finite and positive')
  weights = tuple(value / total_weight for value in raw_weights)
  tails_reversed = tuple(accumulate(reversed(weights)))
  tail_weights = tuple(reversed(tails_reversed))
  segment_length = downstream_length_m / free_boundary_sample_count
  denominator = segment_length * sum(tail_weights)
  rise = outlet_height_m - first_height
  if denominator <= 0.0 or rise < 0.0:
    raise ValueError('free-boundary shape height normalization failed')
  slopes = tuple(rise * tail / denominator for tail in tail_weights)
  heights = [first_height]
  for slope in slopes:
    heights.append(heights[-1] + segment_length * slope)
  heights[-1] = outlet_height_m
  return tuple(float(value) for value in heights)


def _parameters_from_shape_heights(
  heights: Sequence[float],
  *,
  outlet_height_m: float,
  downstream_length_m: float,
  free_boundary_sample_count: int,
  minimum_height_m: float,
) -> tuple[float, ...]:
  expected = free_boundary_sample_count - 1
  edge_count = expected
  if len(heights) != expected:
    raise ValueError(
      'initial_free_boundary_heights_m must contain one height for each '
      'non-outlet free-boundary sample'
    )
  full_heights = tuple(float(value) for value in heights) + (outlet_height_m,)
  if any(
    not isfinite(value)
    or value < minimum_height_m
    or value > outlet_height_m
    for value in full_heights
  ):
    raise ValueError(
      'initial free-boundary heights must be finite and lie between the '
      'minimum and outlet heights'
    )
  segment_length = downstream_length_m / free_boundary_sample_count
  slopes = tuple(
    (second - first) / segment_length
    for first, second in zip(full_heights[:-1], full_heights[1:], strict=True)
  )
  if any(first < -1.0e-12 for first in slopes):
    raise ValueError('initial free-boundary heights must be nondecreasing')
  if any(
    second > first + 1.0e-10 * max(1.0, abs(first), abs(second))
    for first, second in zip(slopes[:-1], slopes[1:], strict=True)
  ):
    raise ValueError(
      'initial free-boundary heights must form a concave discrete envelope'
    )
  first_fraction = (
    (full_heights[0] - minimum_height_m)
    / (outlet_height_m - minimum_height_m)
  )
  if abs(first_fraction - 1.0) <= 1.0e-12 and all(
    abs(slope) <= 1.0e-12 for slope in slopes
  ):
    return (20.0, *(0.0 for _ in range(edge_count)))
  parameters = [_logit(first_fraction)]
  weights = [
    max(1.0e-12, slopes[index] - slopes[index + 1])
    for index in range(len(slopes) - 1)
  ]
  weights.append(max(1.0e-12, slopes[-1]))
  parameters.extend(log(weight) for weight in weights)
  return tuple(parameters)


def _normalized_velocity(sample: MocMixedRegimeFieldSample) -> tuple[float, float]:
  sonic_factor = 0.5 * (sample.gamma - 1.0)
  speed = sample.mach / sqrt(1.0 + sonic_factor * sample.mach * sample.mach)
  return (
    speed * cos(sample.flow_angle_rad),
    speed * sin(sample.flow_angle_rad),
  )


def _mean_control_section_normal_speed(
  section: MocMixedRegimeControlSection,
) -> float:
  normal = (cos(section.normal_angle_rad), sin(section.normal_angle_rad))
  values = tuple(
    _normalized_velocity(sample)[0] * normal[0]
    + _normalized_velocity(sample)[1] * normal[1]
    for sample in section.samples
  )
  lengths = tuple(
    hypot(second[0] - first[0], second[1] - first[1])
    for first, second in zip(
      section.points_m[:-1],
      section.points_m[1:],
      strict=True,
    )
  )
  measure = sum(lengths)
  if measure <= 0.0:
    raise ValueError('control section has no positive measure')
  integral = sum(
    0.5 * (first + second) * length
    for first, second, length in zip(
      values[:-1],
      values[1:],
      lengths,
      strict=True,
    )
  )
  result = integral / measure
  if not isfinite(result) or result <= 0.0:
    raise ValueError('control section mean normal speed is not positive')
  return result


def _signed_boundary_normal_velocity_residuals(
  field: MocMixedRegimeFieldResult,
  condition_edge_indices: Sequence[int],
  *,
  position_tolerance_m: float,
) -> tuple[float, ...]:
  """Recover signed finite-element normal velocity on selected outer edges."""

  if len(field.nodes) != len(field.velocity_potential):
    raise ValueError('potential field node/potential layouts do not match')
  points = tuple(field.boundary.perimeter_points_m[:-1])
  if len(points) < 3:
    raise ValueError('potential field perimeter has too few unique points')
  area = 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(points, (*points[1:], points[0]), strict=True)
  )
  if abs(area) <= position_tolerance_m * position_tolerance_m:
    raise ValueError('potential field perimeter has zero signed area')
  orientation = 1.0 if area > 0.0 else -1.0
  potential_by_point = {
    sample.point_m: field.velocity_potential[index]
    for index, sample in enumerate(field.nodes)
  }
  residuals: list[float] = []
  for edge_index in condition_edge_indices:
    if edge_index < 0 or edge_index >= len(points):
      raise ValueError('selected normal-flow edge lies outside the perimeter')
    next_index = (edge_index + 1) % len(points)
    first_point = points[edge_index]
    second_point = points[next_index]
    displacement = (
      second_point[0] - first_point[0],
      second_point[1] - first_point[1],
    )
    segment_length = hypot(*displacement)
    if segment_length <= position_tolerance_m:
      raise ValueError('selected normal-flow edge has zero length')
    adjacent = [
      cell
      for cell in field.cells
      if len(cell.vertices_xr_m) == 3
      and {first_point, second_point}.issubset(cell.vertices_xr_m)
    ]
    if len(adjacent) != 1:
      raise ValueError(
        'selected normal-flow edge does not have exactly one adjacent triangle'
      )
    triangle = adjacent[0].vertices_xr_m
    try:
      potentials = tuple(potential_by_point[point] for point in triangle)
    except KeyError as error:
      raise ValueError('potential field triangle is missing a nodal potential') from error
    (x1, y1), (x2, y2), (x3, y3) = triangle
    denominator = (
      x1 * (y2 - y3)
      + x2 * (y3 - y1)
      + x3 * (y1 - y2)
    )
    if abs(denominator) <= position_tolerance_m * position_tolerance_m:
      raise ValueError('potential field triangle has zero area')
    velocity = (
      (
        potentials[0] * (y2 - y3)
        + potentials[1] * (y3 - y1)
        + potentials[2] * (y1 - y2)
      ) / denominator,
      (
        potentials[0] * (x3 - x2)
        + potentials[1] * (x1 - x3)
        + potentials[2] * (x2 - x1)
      ) / denominator,
    )
    outward_normal = (
      orientation * displacement[1] / segment_length,
      -orientation * displacement[0] / segment_length,
    )
    residuals.append(
      velocity[0] * outward_normal[0]
      + velocity[1] * outward_normal[1]
    )
  return tuple(residuals)


def _build_candidate(
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  *,
  ambient_pressure_Pa: float,
  downstream_length_m: float,
  outlet_height_m: float,
  free_boundary_sample_count: int,
  centerline_sample_count: int,
  radial_divisions: int,
  shape_parameters: Sequence[float],
  minimum_height_m: float,
  position_tolerance_m: float,
  state_tolerance: float,
  pressure_tolerance: float,
  tangent_tolerance_rad: float,
  thermodynamic_tolerance: float,
  potential_tolerance: float,
  residual_tolerance: float,
  trial_velocity_tolerance: float,
  subsonic_margin: float,
  potential_maximum_iterations: int,
  solver_model: str,
) -> _PlanarFreeBoundaryCandidate:
  upstream_state = request.terminal.upstream_state
  if upstream_state is None:
    raise ValueError('terminal request does not expose an upstream state')
  gamma = upstream_state.gamma
  total_pressure = request.terminal_downstream_total_pressure_Pa
  ambient_mach_squared = 2.0 / (gamma - 1.0) * (
    (total_pressure / ambient_pressure_Pa) ** ((gamma - 1.0) / gamma) - 1.0
  )
  if (
    not isfinite(ambient_mach_squared)
    or ambient_mach_squared <= 0.0
  ):
    raise ValueError(
      'ambient pressure does not map to a positive subsonic boundary speed'
    )
  ambient_mach = sqrt(ambient_mach_squared)
  if ambient_mach >= 1.0 - subsonic_margin:
    raise ValueError(
      'ambient pressure maps to a Mach number outside the strict-subsonic '
      f'range: mach={ambient_mach}'
    )
  sonic_factor = 0.5 * (gamma - 1.0)
  ambient_speed = ambient_mach / sqrt(
    1.0 + sonic_factor * ambient_mach * ambient_mach
  )
  terminal_speed = request.terminal_downstream_mach / sqrt(
    1.0 + sonic_factor * request.terminal_downstream_mach ** 2
  )
  shape_heights = _shape_heights_from_parameters(
    shape_parameters,
    outlet_height_m=outlet_height_m,
    downstream_length_m=downstream_length_m,
    free_boundary_sample_count=free_boundary_sample_count,
    minimum_height_m=minimum_height_m,
  )
  x0, y0 = request.terminal_point_m
  segment_length = downstream_length_m / free_boundary_sample_count
  free_ascending = tuple(
    (
      x0 + segment_length * index,
      y0 + shape_heights[index - 1],
    )
    for index in range(1, free_boundary_sample_count + 1)
  )
  free_slopes = tuple(
    (second[1] - first[1]) / (second[0] - first[0])
    for first, second in zip(
      free_ascending[:-1],
      free_ascending[1:],
      strict=True,
    )
  )
  free_angles_ascending = (
    (atan2(free_slopes[0], 1.0),)
    + tuple(
      atan2(0.5 * (first + second), 1.0)
      for first, second in zip(
        free_slopes[:-1],
        free_slopes[1:],
        strict=True,
      )
    )
    + (atan2(free_slopes[-1], 1.0),)
  )
  free_velocity_ascending = tuple(
    (
      ambient_speed * cos(angle),
      ambient_speed * sin(angle),
    )
    for angle in free_angles_ascending
  )
  points = (
    (x0, y0),
    *tuple(
      (x0 + downstream_length_m * index / centerline_sample_count, y0)
      for index in range(1, centerline_sample_count + 1)
    ),
    *tuple(reversed(free_ascending)),
    (x0, y0),
  )
  free_velocities = tuple(reversed(free_velocity_ascending))
  control_section_mean_speed = _mean_control_section_normal_speed(control_section)
  terminal_velocity = (terminal_speed, 0.0)

  def velocities(centerline_speed: float) -> tuple[tuple[float, float], ...]:
    return (
      terminal_velocity,
      *tuple(
        (centerline_speed, 0.0)
        for _ in range(centerline_sample_count)
      ),
      *free_velocities,
      terminal_velocity,
    )

  def circulation(centerline_speed: float) -> float:
    values = velocities(centerline_speed)
    return sum(
      0.5 * (
        (first_velocity[0] + second_velocity[0])
        * (second_point[0] - first_point[0])
        + (first_velocity[1] + second_velocity[1])
        * (second_point[1] - first_point[1])
      )
      for first_point, second_point, first_velocity, second_velocity in zip(
        points[:-1],
        points[1:],
        values[:-1],
        values[1:],
        strict=True,
      )
    )

  circulation_at_zero = circulation(0.0)
  circulation_at_one = circulation(1.0)
  coefficient = circulation_at_one - circulation_at_zero
  if abs(coefficient) <= 1.0e-14:
    raise ValueError('boundary-potential circulation cannot determine the centerline speed')
  centerline_speed = -circulation_at_zero / coefficient
  if not isfinite(centerline_speed) or centerline_speed <= 0.0:
    raise ValueError(
      'single-valued potential circulation requires a nonpositive or nonfinite '
      f'centerline speed: {centerline_speed}'
    )
  centerline_mach = centerline_speed / sqrt(
    1.0 - sonic_factor * centerline_speed * centerline_speed
  ) if 1.0 - sonic_factor * centerline_speed * centerline_speed > 0.0 else float('inf')
  if not isfinite(centerline_mach) or centerline_mach >= 1.0 - subsonic_margin:
    raise ValueError(
      'circulation-balanced centerline speed is not strictly subsonic: '
      f'mach={centerline_mach}'
    )
  velocity_values = velocities(centerline_speed)

  def make_sample(
    index: int,
    point: tuple[float, float],
    velocity: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    if index in (0, len(points) - 1):
      return MocMixedRegimeFieldSample(
        point_m=point,
        mach=request.terminal_downstream_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=request.terminal_downstream_pressure_Pa,
        total_pressure_Pa=total_pressure,
        gamma=gamma,
      )
    speed_squared = velocity[0] * velocity[0] + velocity[1] * velocity[1]
    enthalpy_factor = 1.0 - sonic_factor * speed_squared
    if enthalpy_factor <= 0.0:
      raise ValueError('boundary velocity crossed its finite enthalpy limit')
    mach = sqrt(speed_squared / enthalpy_factor)
    if mach <= 0.0 or mach >= 1.0 - subsonic_margin:
      raise ValueError(f'boundary velocity is not strictly subsonic: mach={mach}')
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=mach,
      flow_angle_rad=atan2(velocity[1], velocity[0]),
      static_pressure_Pa=(
        total_pressure
        * enthalpy_factor ** (gamma / (gamma - 1.0))
      ),
      total_pressure_Pa=total_pressure,
      gamma=gamma,
    )

  samples = tuple(
    make_sample(index, point, velocity)
    for index, (point, velocity) in enumerate(zip(points, velocity_values, strict=True))
  )
  boundary = validate_mixed_regime_boundary(
    request.terminal,
    request.supersonic_patch,
    supersonic_patch_converged=True,
    subsonic_samples=samples,
    perimeter_points_m=points,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
  )
  if not boundary.converged:
    raise ValueError(f'parameterized perimeter failed scalar seam: {boundary.message}')
  free_start_index = 1 + centerline_sample_count
  condition_edges = tuple(
    range(free_start_index, free_start_index + free_boundary_sample_count - 1)
  )
  condition_samples = tuple(
    range(free_start_index, free_start_index + free_boundary_sample_count)
  )
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=points,
    condition_kind=(
      MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY
    ),
    ambient_pressure_Pa=ambient_pressure_Pa,
    model=solver_model,
    condition_edge_indices=condition_edges,
    condition_sample_indices=condition_samples,
  )
  condition = validate_mixed_regime_downstream_condition(
    boundary,
    perimeter_spec.condition_kind,
    ambient_pressure_Pa=ambient_pressure_Pa,
    condition_edge_indices=condition_edges,
    condition_sample_indices=condition_samples,
    position_tolerance_m=position_tolerance_m,
    tangent_tolerance_rad=tangent_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
  )
  if not condition.converged:
    raise ValueError(f'parameterized perimeter failed physical condition: {condition.message}')
  field = solve_mixed_regime_compressible_potential_field(
    boundary,
    position_tolerance_m=position_tolerance_m,
    thermodynamic_tolerance=thermodynamic_tolerance,
    potential_tolerance=potential_tolerance,
    residual_tolerance=residual_tolerance,
    velocity_tolerance=trial_velocity_tolerance,
    subsonic_margin=subsonic_margin,
    radial_divisions=radial_divisions,
    maximum_iterations=potential_maximum_iterations,
    downstream_condition=condition,
  )
  if (
    not field.velocity_potential
    or not field.cells
    or len(field.velocity_potential) != len(field.nodes)
    or field.status not in (
      MocMixedRegimeFieldStatus.CONVERGED_COMPRESSIBLE_POTENTIAL_FIELD,
      MocMixedRegimeFieldStatus.RESIDUAL_FAILURE,
    )
  ):
    raise ValueError(f'parameterized potential field did not provide a usable trial: {field.message}')
  signed_residuals = _signed_boundary_normal_velocity_residuals(
    field,
    condition_edges,
    position_tolerance_m=position_tolerance_m,
  )
  return _PlanarFreeBoundaryCandidate(
    shape_heights_m=shape_heights,
    perimeter_spec=perimeter_spec,
    boundary=boundary,
    downstream_condition=condition,
    field=field,
    signed_residuals=signed_residuals,
    centerline_speed=centerline_speed,
    control_section_mean_speed=control_section_mean_speed,
  )


def solve_mixed_regime_planar_free_boundary_reference(
  request: MocMixedRegimePerimeterRequest,
  control_section: MocMixedRegimeControlSection,
  *,
  ambient_pressure_Pa: float,
  downstream_length_m: float,
  outlet_height_m: float,
  free_boundary_sample_count: int = 8,
  centerline_sample_count: int = 3,
  radial_divisions: int = 2,
  maximum_iterations: int = 40,
  potential_maximum_iterations: int = 80,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 2.0e-2,
  normal_flux_tolerance: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  potential_tolerance: float = 1.0e-10,
  residual_tolerance: float = 1.0e-10,
  velocity_tolerance: float = 1.0e-8,
  subsonic_margin: float = 1.0e-6,
  initial_free_boundary_fraction: float = 0.8,
  initial_free_boundary_heights_m: Sequence[float] | None = None,
  solver_model: str = (
    'parameterized-2d-compressible-potential-free-boundary-reference'
  ),
) -> MocMixedRegimePlanarFreeBoundaryResult:
  """Solve the bounded parameterized 2-D free-boundary reference.

  The free boundary is represented by ``free_boundary_sample_count`` points
  whose heights are constrained to form a nondecreasing, concave envelope.
  The nonlinear compressible-potential field is solved on each candidate
  perimeter, and its signed outer normal velocity drives a least-squares
  shape iteration.  The outlet height and downstream length remain explicit
  inputs because the terminal shock does not supply an area scale.

  The result is research-only.  It uses a single uniform isentropic total
  pressure and a radial finite-element mesh, so it is evidence for the missing
  coupling seam rather than canonical reflected-MOC closure.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    raise TypeError('request must be a MocMixedRegimePerimeterRequest')
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError('control_section must be a MocMixedRegimeControlSection')
  for name, value in (
    ('ambient_pressure_Pa', ambient_pressure_Pa),
    ('downstream_length_m', downstream_length_m),
    ('outlet_height_m', outlet_height_m),
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
  for name, value, minimum in (
    ('free_boundary_sample_count', free_boundary_sample_count, 4),
    ('centerline_sample_count', centerline_sample_count, 2),
    ('radial_divisions', radial_divisions, 1),
    ('maximum_iterations', maximum_iterations, 1),
    ('potential_maximum_iterations', potential_maximum_iterations, 1),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
      raise ValueError(
        f'{name} must be an integer greater than or equal to {minimum}'
      )
  if not 0.0 < initial_free_boundary_fraction < 1.0:
    raise ValueError('initial_free_boundary_fraction must lie between zero and one')
  solver_model = str(solver_model)
  if not solver_model:
    raise ValueError('solver_model must be a non-empty string')
  if outlet_height_m <= 100.0 * position_tolerance_m:
    raise ValueError(
      'outlet_height_m must be materially larger than position_tolerance_m'
    )
  if downstream_length_m <= 100.0 * position_tolerance_m:
    raise ValueError(
      'downstream_length_m must be materially larger than position_tolerance_m'
    )
  control_section_validation = validate_mixed_regime_control_section(
    request,
    control_section,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
  )
  common = {
    'ambient_pressure_Pa': float(ambient_pressure_Pa),
    'downstream_length_m': float(downstream_length_m),
    'outlet_height_m': float(outlet_height_m),
    'free_boundary_sample_count': free_boundary_sample_count,
    'centerline_sample_count': centerline_sample_count,
    'radial_divisions': radial_divisions,
    'iteration_count': 0,
  }
  if not control_section_validation.converged:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
      request,
      control_section,
      control_section_validation,
      message=(
        'planar free-boundary reference requires a valid explicit control '
        f'section: {control_section_validation.message}'
      ),
      **common,
    )
  terminal_angle = request.terminal_downstream_flow_angle_rad
  if abs(terminal_angle) > tangent_tolerance_rad:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.INVALID_INPUT,
      request,
      control_section,
      control_section_validation,
      message=(
        'the current parameterized envelope is axis-aligned and requires a '
        f'near-zero terminal flow angle, received {terminal_angle}'
      ),
      **common,
    )
  if abs(control_section.normal_angle_rad) > tangent_tolerance_rad:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.INVALID_INPUT,
      request,
      control_section,
      control_section_validation,
      message=(
        'the current parameterized envelope is axis-aligned and requires a '
        f'near-zero control-section normal angle, received '
        f'{control_section.normal_angle_rad}'
      ),
      **common,
    )
  upstream_state = request.terminal.upstream_state
  if upstream_state is None:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.TERMINAL_FAILURE,
      request,
      control_section,
      control_section_validation,
      message='terminal does not expose an upstream state for gamma',
      **common,
    )
  total_pressure = request.terminal_downstream_total_pressure_Pa
  total_pressure_residual = max(
    abs(sample.total_pressure_Pa - total_pressure)
    / max(1.0, abs(sample.total_pressure_Pa), abs(total_pressure))
    for sample in control_section.samples
  )
  gamma_residual = max(
    abs(sample.gamma - upstream_state.gamma)
    / max(1.0, abs(sample.gamma), abs(upstream_state.gamma))
    for sample in control_section.samples
  )
  if max(total_pressure_residual, gamma_residual) > thermodynamic_tolerance:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
      request,
      control_section,
      control_section_validation,
      message=(
        'the compressible potential reference requires the explicit control '
        'section to carry uniform total pressure and gamma: '
        f'total_pressure_residual={total_pressure_residual}, '
        f'gamma_residual={gamma_residual}'
      ),
      **common,
    )
  ambient_mach_squared = 2.0 / (upstream_state.gamma - 1.0) * (
    (total_pressure / ambient_pressure_Pa)
    ** ((upstream_state.gamma - 1.0) / upstream_state.gamma)
    - 1.0
  )
  ambient_mach = (
    sqrt(ambient_mach_squared)
    if isfinite(ambient_mach_squared) and ambient_mach_squared > 0.0
    else None
  )
  if ambient_mach is None or ambient_mach >= 1.0 - subsonic_margin:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.PRESSURE_UNREACHABLE,
      request,
      control_section,
      control_section_validation,
      message=(
        'ambient pressure does not map to a positive strict-subsonic Mach '
        f'number for the terminal total pressure: mach={ambient_mach}'
      ),
      **common,
    )
  minimum_height_m = max(
    100.0 * position_tolerance_m,
    outlet_height_m * 1.0e-8,
  )
  if minimum_height_m >= outlet_height_m:
    raise ValueError('outlet_height_m leaves no valid free-boundary height interval')
  try:
    if initial_free_boundary_heights_m is None:
      initial_parameters = (
        _logit(initial_free_boundary_fraction),
        *(0.0 for _ in range(free_boundary_sample_count - 1)),
      )
      initial_shape_heights = _shape_heights_from_parameters(
        initial_parameters,
        outlet_height_m=outlet_height_m,
        downstream_length_m=downstream_length_m,
        free_boundary_sample_count=free_boundary_sample_count,
        minimum_height_m=minimum_height_m,
      )
    else:
      initial_parameters = _parameters_from_shape_heights(
        initial_free_boundary_heights_m,
        outlet_height_m=outlet_height_m,
        downstream_length_m=downstream_length_m,
        free_boundary_sample_count=free_boundary_sample_count,
        minimum_height_m=minimum_height_m,
      )
      initial_shape_heights = tuple(
        float(value) for value in initial_free_boundary_heights_m
      ) + (float(outlet_height_m),)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.GEOMETRY_FAILURE,
      request,
      control_section,
      control_section_validation,
      message=f'initial free-boundary envelope is invalid: {error}',
      **common,
    )
  # A deliberately loose trial gate lets the outer iteration inspect signed
  # normal velocity even when the current shape is not yet closed.  The final
  # solve below uses the requested strict velocity tolerance.
  trial_velocity_tolerance = max(1.0, 100.0 * velocity_tolerance)
  evaluation_count = 0
  residual_history: list[float] = []
  best_candidate: _PlanarFreeBoundaryCandidate | None = None
  last_trial_error = ''
  import numpy as np
  from scipy.optimize import least_squares

  def residual(parameters: Sequence[float]) -> np.ndarray:
    nonlocal evaluation_count, best_candidate, last_trial_error
    evaluation_count += 1
    try:
      candidate = _build_candidate(
        request,
        control_section,
        ambient_pressure_Pa=ambient_pressure_Pa,
        downstream_length_m=downstream_length_m,
        outlet_height_m=outlet_height_m,
        free_boundary_sample_count=free_boundary_sample_count,
        centerline_sample_count=centerline_sample_count,
        radial_divisions=radial_divisions,
        shape_parameters=parameters,
        minimum_height_m=minimum_height_m,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance_rad=tangent_tolerance_rad,
        thermodynamic_tolerance=thermodynamic_tolerance,
        potential_tolerance=potential_tolerance,
        residual_tolerance=residual_tolerance,
        trial_velocity_tolerance=trial_velocity_tolerance,
        subsonic_margin=subsonic_margin,
        potential_maximum_iterations=potential_maximum_iterations,
        solver_model=solver_model,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      last_trial_error = str(error)
      residual_history.append(float('inf'))
      return np.full(free_boundary_sample_count - 1, 10.0, dtype=float)
    candidate_residual = max(abs(value) for value in candidate.signed_residuals)
    residual_history.append(candidate_residual)
    if best_candidate is None or candidate_residual < max(
      abs(value) for value in best_candidate.signed_residuals
    ):
      best_candidate = candidate
    return np.asarray(candidate.signed_residuals, dtype=float)

  flat_parameters = (
    20.0,
    *(0.0 for _ in range(free_boundary_sample_count - 1)),
  )
  flat_residual = residual(flat_parameters)
  flat_maximum = max(abs(float(value)) for value in flat_residual)
  if flat_maximum > velocity_tolerance:
    initial_residual = residual(initial_parameters)
    initial_maximum = max(abs(float(value)) for value in initial_residual)
  else:
    initial_maximum = flat_maximum
  if initial_maximum > velocity_tolerance:
    try:
      optimization = least_squares(
        residual,
        np.asarray(initial_parameters, dtype=float),
        bounds=(
          np.full(len(initial_parameters), -20.0, dtype=float),
          np.full(len(initial_parameters), 20.0, dtype=float),
        ),
        max_nfev=maximum_iterations,
        xtol=1.0e-10,
        ftol=1.0e-10,
        gtol=1.0e-10,
      )
      residual(optimization.x)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      last_trial_error = str(error)
  if best_candidate is None:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.FIELD_FAILURE,
      request,
      control_section,
      control_section_validation,
      iteration_count=evaluation_count,
      residual_history=tuple(value for value in residual_history if isfinite(value)),
      initial_shape_heights_m=initial_shape_heights,
      message=(
        'no usable nonlinear potential trial was available for the free-boundary '
        f'iteration: {last_trial_error}'
      ),
      **{
        key: value
        for key, value in common.items()
        if key != 'iteration_count'
      },
    )
  best_residual = max(abs(value) for value in best_candidate.signed_residuals)
  common_solution = {
    'iteration_count': evaluation_count,
    'shape_heights_m': best_candidate.shape_heights_m,
    'initial_shape_heights_m': initial_shape_heights,
    'residual_history': tuple(value for value in residual_history if isfinite(value)),
    'signed_free_boundary_residuals': best_candidate.signed_residuals,
    'maximum_boundary_normal_velocity_residual': best_residual,
    'perimeter_spec': best_candidate.perimeter_spec,
    'boundary': best_candidate.boundary,
    'downstream_condition': best_candidate.downstream_condition,
    'field': best_candidate.field,
    'centerline_speed_m_s_normalized': best_candidate.centerline_speed,
    'control_section_mean_normal_speed_m_s_normalized': (
      best_candidate.control_section_mean_speed
    ),
  }
  if best_residual > velocity_tolerance:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.ITERATION_FAILURE,
      request,
      control_section,
      control_section_validation,
      message=(
        'parameterized free-boundary iteration stopped before the strict '
        f'normal-velocity gate: residual={best_residual}, '
        f'tolerance={velocity_tolerance}; last_trial_error={last_trial_error}'
      ),
      **{
        **common,
        **common_solution,
      },
    )
  try:
    final_field = solve_mixed_regime_compressible_potential_field(
      best_candidate.boundary,
      position_tolerance_m=position_tolerance_m,
      thermodynamic_tolerance=thermodynamic_tolerance,
      potential_tolerance=potential_tolerance,
      residual_tolerance=residual_tolerance,
      velocity_tolerance=velocity_tolerance,
      subsonic_margin=subsonic_margin,
      radial_divisions=radial_divisions,
      maximum_iterations=potential_maximum_iterations,
      downstream_condition=best_candidate.downstream_condition,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.FIELD_FAILURE,
      request,
      control_section,
      control_section_validation,
      message=f'final strict potential solve failed: {error}',
      **{
        **common,
        **common_solution,
      },
    )
  if not final_field.converged:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.FIELD_FAILURE,
      request,
      control_section,
      control_section_validation,
      message=f'final strict potential field failed its gates: {final_field.message}',
      **{
        **common,
        **common_solution,
        'field': final_field,
      },
    )
  final_field = replace(
    final_field,
    control_section=control_section,
    message=(
      'parameterized 2-D free-boundary shape iteration and nonlinear '
      'isentropic potential field converged on the explicit perimeter; '
      'canonical reflected-MOC promotion remains blocked'
    ),
  )
  handoff = run_mixed_regime_planar_field_solver(
    request,
    control_section,
    best_candidate.perimeter_spec,
    lambda _request, _section, _specification: final_field,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
    solver_model=solver_model,
  )
  if not handoff.converged:
    return _result(
      MocMixedRegimePlanarFreeBoundaryStatus.FIELD_FAILURE,
      request,
      control_section,
      control_section_validation,
      handoff=handoff,
      closure=handoff.closure,
      message=f'final planar seam audit failed: {handoff.message}',
      **{
        **common,
        **common_solution,
        'field': final_field,
      },
    )
  return _result(
    MocMixedRegimePlanarFreeBoundaryStatus.CONVERGED_REFERENCE,
    request,
    control_section,
    control_section_validation,
    handoff=handoff,
    closure=handoff.closure,
    message=(
      'parameterized 2-D free-boundary reference converged through the exact '
      'terminal/control-section/perimeter seam and nonlinear potential field; '
      'it remains a non-canonical research lane'
    ),
    **{
      **common,
      **common_solution,
      'field': final_field,
      'maximum_boundary_normal_velocity_residual': (
        final_field.maximum_boundary_normal_velocity_residual
      ),
    },
  )
