"""Shock/ambient characteristic strips for the planar MOC research lane.

The physical outer boundary of an underexpanded or mildly overexpanded plume
is a streamline at the prescribed ambient pressure.  In the downstream
post-shock region, a ``C+`` characteristic enters the field from the shock and
a ``C-`` characteristic enters it from the outer boundary.  This module keeps
that family orientation explicit.

The returned strip is intentionally open at its downstream terminal trace.
That trace must still be coupled to a centerline/axis closure before a field
can become a resolved shock-cell chain seed.  In particular, this module does
not reinterpret the terminal trace as an axis or manufacture a physical end
point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, sqrt, sin
from typing import Sequence

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientBoundaryStatus,
  MocAmbientPressureBoundaryResult,
  validate_ambient_pressure_boundary,
)
from exhaust_plume.models.moc.boundary import (
  MocFreeBoundaryPointResult,
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocCharacteristicTraceResult,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.post_shock import MocShockBoundaryFitResult
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocAmbientShockBoundaryMarchStatus',
  'MocAmbientShockBoundaryMarchResult',
  'MocAmbientAxisClosureStatus',
  'MocAmbientAxisClosureResult',
  'MocAmbientShockStripStatus',
  'MocAmbientShockStripResult',
  'march_post_shock_ambient_boundary',
  'probe_post_shock_ambient_axis_closure',
  'assemble_ambient_shock_characteristic_strip',
)


class MocAmbientShockBoundaryMarchStatus(str, Enum):
  """Outcome for a shock-to-ambient streamline march."""

  CONVERGED = 'converged_post_shock_ambient_boundary'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'shock_boundary_failure'
  SEED_FAILURE = 'ambient_boundary_seed_failure'
  BOUNDARY_FAILURE = 'ambient_boundary_march_failure'
  GEOMETRY_FAILURE = 'ambient_boundary_geometry_failure'
  PRESSURE_FAILURE = 'ambient_boundary_pressure_failure'
####


class MocAmbientAxisClosureStatus(str, Enum):
  """Outcome of extending the marched ambient boundary to the axis."""

  CONVERGED = 'converged_ambient_axis_candidate'
  INVALID_INPUT = 'invalid_input'
  MARCH_FAILURE = 'ambient_boundary_march_failure'
  AXIS_FAILURE = 'centerline_axis_failure'
  PRESSURE_FAILURE = 'ambient_axis_pressure_failure'
####


class MocAmbientShockStripStatus(str, Enum):
  """Outcome for a shock/ambient characteristic strip assembly."""

  CONVERGED_OPEN = 'converged_open_shock_ambient_strip'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'shock_boundary_failure'
  AMBIENT_BOUNDARY_FAILURE = 'ambient_boundary_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocAmbientShockBoundaryMarchResult:
  """A pressure-matched ambient boundary generated from a shock trace."""

  status: MocAmbientShockBoundaryMarchStatus
  boundary_samples: tuple[MocAmbientBoundarySample, ...]
  point_results: tuple[MocFreeBoundaryPointResult, ...]
  ambient_boundary: MocAmbientPressureBoundaryResult
  maximum_geometry_residual_m: float | None
  maximum_absolute_pressure_residual: float | None
  maximum_absolute_invariant_residual: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocAmbientShockBoundaryMarchStatus.CONVERGED
  ####

  @property
  def points_m(self) -> tuple[tuple[float, float], ...]:
    return tuple(sample.point_m for sample in self.boundary_samples)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'sample_count': len(self.boundary_samples),
      'ambient_boundary': self.ambient_boundary.as_report(),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_pressure_residual': self.maximum_absolute_pressure_residual,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocAmbientAxisClosureResult:
  """A bounded centerline candidate and its ambient-pressure residual.

  The last ambient-boundary state is continued along its compatible ``C-``
  characteristic to ``y=0``.  This produces a physically meaningful axis
  candidate, but it is only a local closure gate: a pressure mismatch means
  the upstream shock/boundary solve still has to change.  Even a candidate
  that passes this scalar check is deliberately not a promoted MOC cell.
  """

  status: MocAmbientAxisClosureStatus
  source_boundary_sample: MocAmbientBoundarySample | None
  axis_point_m: tuple[float, float] | None
  axis_state: CharacteristicState | None
  axis_total_pressure_Pa: float | None
  axis_static_pressure_Pa: float | None
  ambient_pressure_Pa: float | None
  pressure_residual_Pa: float | None
  relative_pressure_residual: float | None
  axis_geometry_residual_m: float | None
  axis_invariant_residual: float | None
  axis_candidate_verified: bool
  ambient_pressure_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocAmbientAxisClosureStatus):
      raise TypeError('status must be a MocAmbientAxisClosureStatus')
    if self.source_boundary_sample is not None and not isinstance(
        self.source_boundary_sample,
        MocAmbientBoundarySample,
    ):
      raise TypeError(
        'source_boundary_sample must be a MocAmbientBoundarySample or None'
      )
    if self.axis_state is not None and not isinstance(
        self.axis_state,
        CharacteristicState,
    ):
      raise TypeError('axis_state must be a CharacteristicState or None')
    for name, value in (
      ('axis_total_pressure_Pa', self.axis_total_pressure_Pa),
      ('axis_static_pressure_Pa', self.axis_static_pressure_Pa),
      ('ambient_pressure_Pa', self.ambient_pressure_Pa),
    ):
      if value is not None and (
        not isfinite(float(value)) or float(value) <= 0.0
      ):
        raise ValueError(f'{name} must be finite and positive when supplied')
    for name, value in (
      ('pressure_residual_Pa', self.pressure_residual_Pa),
      ('relative_pressure_residual', self.relative_pressure_residual),
      ('axis_geometry_residual_m', self.axis_geometry_residual_m),
      ('axis_invariant_residual', self.axis_invariant_residual),
    ):
      if value is not None and not isfinite(float(value)):
        raise ValueError(f'{name} must be finite when supplied')
    if self.axis_point_m is not None:
      if len(self.axis_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.axis_point_m
      ):
        raise ValueError('axis_point_m must contain two finite coordinates')
      object.__setattr__(
        self,
        'axis_point_m',
        (float(self.axis_point_m[0]), float(self.axis_point_m[1])),
      )
    if not isinstance(self.axis_candidate_verified, bool):
      raise TypeError('axis_candidate_verified must be a bool')
    if not isinstance(self.ambient_pressure_verified, bool):
      raise TypeError('ambient_pressure_verified must be a bool')
  ####

  @property
  def converged(self) -> bool:
    """Whether both the axis characteristic and pressure gate passed."""

    return self.status is MocAmbientAxisClosureStatus.CONVERGED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether this local axis probe proves a complete physical cell."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Whether the local axis candidate must remain outside chain promotion."""

    return True
  ####

  def as_report(self) -> dict[str, object]:
    """Serialize the axis candidate and both independent closure gates."""

    axis_state = self.axis_state
    return {
      'status': self.status.value,
      'converged': self.converged,
      'axis_candidate_verified': self.axis_candidate_verified,
      'ambient_pressure_verified': self.ambient_pressure_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'source_boundary_point_m': (
        None
        if self.source_boundary_sample is None
        else self.source_boundary_sample.point_m
      ),
      'axis_point_m': self.axis_point_m,
      'axis_state': (
        None
        if axis_state is None
        else {
          'x_m': axis_state.x_m,
          'y_m': axis_state.y_m,
          'theta_rad': axis_state.theta_rad,
          'mach': axis_state.mach,
          'gamma': axis_state.gamma,
        }
      ),
      'axis_total_pressure_Pa': self.axis_total_pressure_Pa,
      'axis_static_pressure_Pa': self.axis_static_pressure_Pa,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'pressure_residual_Pa': self.pressure_residual_Pa,
      'relative_pressure_residual': self.relative_pressure_residual,
      'axis_geometry_residual_m': self.axis_geometry_residual_m,
      'axis_invariant_residual': self.axis_invariant_residual,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocAmbientShockStripResult:
  """A topologically bounded but downstream-open physical-boundary strip.

  ``CONVERGED_OPEN`` means that the supplied shock and ambient boundaries
  couple through a compatible characteristic net.  It does not mean the
  terminal trace has reached the symmetry line, so ``physical_closure_verified``
  is deliberately always false and no chain-cell promotion method is exposed.
  """

  status: MocAmbientShockStripStatus
  characteristic_layer_count: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  terminal_trace_points_m: tuple[tuple[float, float], ...]
  terminal_trace_states: tuple[CharacteristicState, ...]
  terminal_trace_total_pressure_Pa: tuple[float, ...]
  ambient_boundary: MocAmbientPressureBoundaryResult
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_post_shock_total_pressure_ratio: float | None
  maximum_post_shock_total_pressure_ratio: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocAmbientShockStripStatus.CONVERGED_OPEN
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def terminal_trace_samples(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the terminal trace in the chain handoff representation."""

    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.terminal_trace_states,
        self.terminal_trace_total_pressure_Pa,
        strict=True,
      )
    )
  ####

  @property
  def terminal_trace_validation(self) -> MocCharacteristicTraceResult:
    """Validate the open terminal trace as a shock-sourced ``C+`` line."""

    return validate_characteristic_trace(
      self.terminal_trace_samples,
      CharacteristicFamily.PLUS,
    )
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'characteristic_layer_count': self.characteristic_layer_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_status': self.topology.status.value,
      'ambient_boundary': self.ambient_boundary.as_report(),
      'shock_boundary_sample_count': len(self.shock_boundary_points_m),
      'terminal_trace_sample_count': len(self.terminal_trace_points_m),
      'terminal_trace_kind': 'terminal-characteristic-trace',
      'terminal_trace_family': CharacteristicFamily.PLUS.value,
      'terminal_trace_validation': self.terminal_trace_validation.as_report(),
      'source_families': {'shock': 'C+', 'ambient': 'C-'},
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
      'message': self.message,
    }
  ####


def _empty_ambient_boundary(
  ambient_pressure_Pa: float | None,
  *,
  message: str,
) -> MocAmbientPressureBoundaryResult:
  return MocAmbientPressureBoundaryResult(
    status=MocAmbientBoundaryStatus.INVALID_INPUT,
    points_m=(),
    states=(),
    total_pressure_Pa=(),
    static_pressure_Pa=(),
    pressure_residuals=(),
    tangent_residuals=(),
    ambient_pressure_Pa=ambient_pressure_Pa,
    maximum_absolute_pressure_residual=None,
    maximum_absolute_tangent_residual=None,
    message=message,
  )


def _empty_march(
  status: MocAmbientShockBoundaryMarchStatus,
  *,
  ambient_boundary: MocAmbientPressureBoundaryResult,
  samples: Sequence[MocAmbientBoundarySample] = (),
  point_results: Sequence[MocFreeBoundaryPointResult] = (),
  message: str,
) -> MocAmbientShockBoundaryMarchResult:
  return MocAmbientShockBoundaryMarchResult(
    status=status,
    boundary_samples=tuple(samples),
    point_results=tuple(point_results),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=max(
      (
        abs(result.geometry_residual)
        for result in point_results
        if result.geometry_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_pressure_residual=max(
      (
        abs(result.pressure_residual)
        for result in point_results
        if result.pressure_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_invariant_residual=None,
    message=message,
  )


def _static_pressure_from_total(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  return float(total_pressure_Pa) / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))


def _finite_point(point_m: tuple[float, float], name: str) -> tuple[float, float]:
  if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
    raise ValueError(f'{name} must contain two finite coordinates')
  return float(point_m[0]), float(point_m[1])


def march_post_shock_ambient_boundary(
  shock_fit: MocShockBoundaryFitResult,
  ambient_pressure_Pa: float,
  *,
  seed_boundary_state: CharacteristicState | None = None,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  maximum_iterations: int = 16,
) -> MocAmbientShockBoundaryMarchResult:
  """March a physical ambient boundary from an ordered post-shock trace.

  The first sample is an explicit attachment state.  Every later boundary
  sample is solved by preserving the incoming shock ``K+`` invariant while
  imposing ambient static pressure and streamline tangency.  The shock trace
  supplies ``C+`` sources; the generated ambient trace is the ``C-`` source
  for the downstream strip assembler.

  The attachment state must agree with the first downstream shock state.  A
  discontinuous corner can be supported later, but silently selecting one of
  two different states at the shared point would make the characteristic net
  ambiguous.
  """

  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    ambient = _empty_ambient_boundary(None, message='shock_fit has an invalid type')
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
  except (TypeError, ValueError):
    ambient = _empty_ambient_boundary(None, message='ambient pressure and target ordinate must be numeric')
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='ambient_pressure_Pa and target_centerline_y_m must be finite numeric values',
    )
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  if not isfinite(target_y):
    raise ValueError('target_centerline_y_m must be finite')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  if not shock_fit.converged:
    ambient = _empty_ambient_boundary(
      ambient_pressure,
      message='ambient boundary was not marched because the shock fit is not converged',
    )
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.SHOCK_FAILURE,
      ambient_boundary=ambient,
      message=f'shock boundary fit is not converged: {shock_fit.message}',
    )
  shock_samples = tuple(shock_fit.boundary_states)
  if len(shock_samples) < 3:
    ambient = _empty_ambient_boundary(
      ambient_pressure,
      message='ambient boundary march requires at least three shock samples',
    )
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='shock boundary fit requires at least three samples',
    )
  first_shock = shock_samples[0]
  seed = first_shock.state if seed_boundary_state is None else seed_boundary_state
  if not isinstance(seed, CharacteristicState):
    ambient = _empty_ambient_boundary(ambient_pressure, message='ambient seed has an invalid type')
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='seed_boundary_state must be a CharacteristicState when supplied',
    )
  if (
    abs(seed.x_m - first_shock.point_m[0]) > position_tolerance_m
    or abs(seed.y_m - first_shock.point_m[1]) > position_tolerance_m
  ):
    ambient = _empty_ambient_boundary(
      ambient_pressure,
      message='ambient seed must lie at the first shock/ambient attachment point',
    )
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.SEED_FAILURE,
      ambient_boundary=ambient,
      message='ambient seed must lie at the first shock/ambient attachment point',
    )
  if abs(seed.gamma - first_shock.state.gamma) > invariant_tolerance:
    ambient = _empty_ambient_boundary(
      ambient_pressure,
      message='ambient seed and shock trace use different gamma values',
    )
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.SEED_FAILURE,
      ambient_boundary=ambient,
      message='ambient seed and shock trace must use the same gamma',
    )
  if (
    abs(seed.theta_rad - first_shock.state.theta_rad) > invariant_tolerance
    or abs(seed.mach - first_shock.state.mach) > invariant_tolerance
  ):
    ambient = _empty_ambient_boundary(
      ambient_pressure,
      message='ambient seed must match the first post-shock attachment state',
    )
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.SEED_FAILURE,
      ambient_boundary=ambient,
      message='ambient seed must match the first post-shock attachment state',
    )
  first_total_pressure = first_shock.downstream_total_pressure_Pa
  first_static_pressure = _static_pressure_from_total(seed, first_total_pressure)
  first_pressure_residual = (first_static_pressure - ambient_pressure) / ambient_pressure
  if abs(first_pressure_residual) > pressure_tolerance:
    ambient = _empty_ambient_boundary(
      ambient_pressure,
      message='ambient seed static pressure does not match ambient pressure',
    )
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.SEED_FAILURE,
      ambient_boundary=ambient,
      message=(
        'ambient seed static pressure does not match ambient pressure: '
        f'residual={first_pressure_residual}'
      ),
    )
  samples: list[MocAmbientBoundarySample] = [
    MocAmbientBoundarySample(
      point_m=first_shock.point_m,
      state=seed,
      total_pressure_Pa=first_total_pressure,
    )
  ]
  point_results: list[MocFreeBoundaryPointResult] = [
    MocFreeBoundaryPointResult(
      status=MocPrimitiveStatus.CONVERGED,
      family=CharacteristicFamily.PLUS,
      state=seed,
      point_m=first_shock.point_m,
      pressure_residual=first_pressure_residual,
      tangent_residual=None,
      geometry_residual=0.0,
      iterations=0,
      intersection_status='shared-shock-ambient-attachment',
    )
  ]
  previous_boundary = seed
  for index, shock_sample in enumerate(shock_samples[1:], start=1):
    result = solve_ambient_pressure_free_boundary_point(
      shock_sample.state,
      previous_boundary,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=shock_sample.downstream_total_pressure_Pa,
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    point_results.append(result)
    if not result.converged or result.state is None or result.point_m is None:
      ambient = validate_ambient_pressure_boundary(
        samples,
        ambient_pressure,
        position_tolerance_m=position_tolerance_m,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=pressure_tolerance,
      ) if len(samples) >= 2 else _empty_ambient_boundary(
        ambient_pressure,
        message='ambient boundary march stopped before two samples were available',
      )
      return _empty_march(
        MocAmbientShockBoundaryMarchStatus.BOUNDARY_FAILURE,
        ambient_boundary=ambient,
        samples=samples,
        point_results=point_results,
        message=f'ambient boundary sample {index} failed: {result.message}',
      )
    if result.point_m[0] <= previous_boundary.x_m + position_tolerance_m:
      ambient = _empty_ambient_boundary(
        ambient_pressure,
        message='ambient boundary march stopped without downstream progress',
      )
      return _empty_march(
        MocAmbientShockBoundaryMarchStatus.GEOMETRY_FAILURE,
        ambient_boundary=ambient,
        samples=samples,
        point_results=point_results,
        message=f'ambient boundary sample {index} is not strictly downstream',
      )
    if result.point_m[1] < target_y - position_tolerance_m:
      ambient = _empty_ambient_boundary(
        ambient_pressure,
        message='ambient boundary crossed below the target centerline',
      )
      return _empty_march(
        MocAmbientShockBoundaryMarchStatus.GEOMETRY_FAILURE,
        ambient_boundary=ambient,
        samples=samples,
        point_results=point_results,
        message=f'ambient boundary sample {index} crossed below the target centerline',
      )
    if abs(result.state.k_plus - shock_sample.state.k_plus) > invariant_tolerance:
      ambient = _empty_ambient_boundary(
        ambient_pressure,
        message='ambient boundary sample did not preserve the incoming shock K+ invariant',
      )
      return _empty_march(
        MocAmbientShockBoundaryMarchStatus.PRESSURE_FAILURE,
        ambient_boundary=ambient,
        samples=samples,
        point_results=point_results,
        message=f'ambient boundary sample {index} violated shock-to-boundary K+ compatibility',
      )
    sample = MocAmbientBoundarySample(
      point_m=result.point_m,
      state=result.state,
      total_pressure_Pa=shock_sample.downstream_total_pressure_Pa,
    )
    samples.append(sample)
    previous_boundary = result.state
  ambient = validate_ambient_pressure_boundary(
    samples,
    ambient_pressure,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=pressure_tolerance,
  )
  if not ambient.converged:
    return _empty_march(
      MocAmbientShockBoundaryMarchStatus.PRESSURE_FAILURE,
      ambient_boundary=ambient,
      samples=samples,
      point_results=point_results,
      message=f'generated ambient boundary failed acceptance: {ambient.message}',
    )
  return MocAmbientShockBoundaryMarchResult(
    status=MocAmbientShockBoundaryMarchStatus.CONVERGED,
    boundary_samples=tuple(samples),
    point_results=tuple(point_results),
    ambient_boundary=ambient,
    maximum_geometry_residual_m=max(
      (
        abs(result.geometry_residual)
        for result in point_results
        if result.geometry_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_pressure_residual=ambient.maximum_absolute_pressure_residual,
    maximum_absolute_invariant_residual=max(
      (
        abs(shock_sample.state.k_plus - sample.state.k_plus)
        for shock_sample, sample in zip(shock_samples, samples, strict=True)
      ),
      default=None,
    ),
    message=(
      'shock-sourced C+ characteristics generated an ambient-pressure, '
      'streamline-tangent C- boundary; downstream axis closure remains pending'
    ),
  )
####


def _strip_failure(
  status: MocAmbientShockStripStatus,
  *,
  ambient_boundary: MocAmbientPressureBoundaryResult,
  characteristic_layer_count: int = 0,
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  shock_points: Sequence[tuple[float, float]] = (),
  ambient_points: Sequence[tuple[float, float]] = (),
  terminal_points: Sequence[tuple[float, float]] = (),
  terminal_states: Sequence[CharacteristicState] = (),
  terminal_pressures: Sequence[float] = (),
  pressure_ratios: Sequence[float] = (),
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  message: str,
) -> MocAmbientShockStripResult:
  return MocAmbientShockStripResult(
    status=status,
    characteristic_layer_count=characteristic_layer_count,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=validate_moc_mesh(()) if topology is None else topology,
    shock_boundary_points_m=tuple(shock_points),
    ambient_boundary_points_m=tuple(ambient_points),
    terminal_trace_points_m=tuple(terminal_points),
    terminal_trace_states=tuple(terminal_states),
    terminal_trace_total_pressure_Pa=tuple(float(value) for value in terminal_pressures),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios, default=None),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios, default=None),
    message=message,
  )


def _shock_endpoint_characteristic_point(
  plus_source: CharacteristicState,
  minus_endpoint: CharacteristicState,
  endpoint: tuple[float, float],
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> CharacteristicPointResult:
  """Validate a shock ``C+`` ray arriving at an ambient endpoint."""

  if abs(plus_source.gamma - minus_endpoint.gamma) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=None,
      iterations=0,
      message='shock and ambient endpoint states use different gamma',
    )
  plus_residual = minus_endpoint.k_plus - plus_source.k_plus
  displacement = (
    endpoint[0] - plus_source.x_m,
    endpoint[1] - plus_source.y_m,
  )
  if sqrt(displacement[0] ** 2 + displacement[1] ** 2) <= position_tolerance_m:
    if abs(plus_residual) > invariant_tolerance:
      return CharacteristicPointResult(
        status=MocPrimitiveStatus.INVARIANT_FAILURE,
        state=minus_endpoint,
        point_m=endpoint,
        invariant_residual_plus=plus_residual,
        invariant_residual_minus=0.0,
        geometry_residual=0.0,
        iterations=0,
        intersection_status='shared-attachment',
        message='shared shock/ambient attachment does not preserve C+ compatibility',
      )
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.CONVERGED,
      state=minus_endpoint,
      point_m=endpoint,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=0.0,
      iterations=0,
      intersection_status='shared-attachment',
    )
  start_angle = plus_source.theta_rad + plus_source.mu_rad
  end_angle = minus_endpoint.theta_rad + minus_endpoint.mu_rad
  average_angle = 0.5 * (start_angle + end_angle)
  direction = (cos(average_angle), sin(average_angle))
  forward_parameter = displacement[0] * direction[0] + displacement[1] * direction[1]
  geometry_residual = abs(displacement[0] * direction[1] - displacement[1] * direction[0])
  if abs(plus_residual) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      state=minus_endpoint,
      point_m=endpoint,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=geometry_residual,
      iterations=0,
      message='ambient endpoint does not preserve the shock C+ invariant',
    )
  if forward_parameter <= position_tolerance_m or geometry_residual > position_tolerance_m:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      state=None,
      point_m=None,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=geometry_residual,
      iterations=0,
      message='ambient endpoint is not on a forward shock C+ characteristic',
    )
  return CharacteristicPointResult(
    status=MocPrimitiveStatus.CONVERGED,
    state=minus_endpoint,
    point_m=endpoint,
    invariant_residual_plus=plus_residual,
    invariant_residual_minus=0.0,
    geometry_residual=geometry_residual,
    iterations=0,
    intersection_status='ambient-boundary-endpoint',
  )


def probe_post_shock_ambient_axis_closure(
  march: MocAmbientShockBoundaryMarchResult,
  ambient_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocAmbientAxisClosureResult:
  """Probe the final ambient ``C-`` sample against a centerline closure.

  The probe carries the last accepted ambient total pressure to the axis and
  reconstructs the compatible ``theta=0`` state.  It does not alter the
  marched boundary and does not infer a downstream perimeter.  A pressure
  mismatch is therefore a useful residual for a future global shock/boundary
  solve, not a reason to accept this candidate as a physical first cell.
  """

  try:
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    ambient_pressure = None
  if ambient_pressure is None or not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return MocAmbientAxisClosureResult(
      status=MocAmbientAxisClosureStatus.INVALID_INPUT,
      source_boundary_sample=None,
      axis_point_m=None,
      axis_state=None,
      axis_total_pressure_Pa=None,
      axis_static_pressure_Pa=None,
      ambient_pressure_Pa=ambient_pressure,
      pressure_residual_Pa=None,
      relative_pressure_residual=None,
      axis_geometry_residual_m=None,
      axis_invariant_residual=None,
      axis_candidate_verified=False,
      ambient_pressure_verified=False,
      message='ambient_pressure_Pa must be finite and positive',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not isinstance(march, MocAmbientShockBoundaryMarchResult):
    return MocAmbientAxisClosureResult(
      status=MocAmbientAxisClosureStatus.INVALID_INPUT,
      source_boundary_sample=None,
      axis_point_m=None,
      axis_state=None,
      axis_total_pressure_Pa=None,
      axis_static_pressure_Pa=None,
      ambient_pressure_Pa=ambient_pressure,
      pressure_residual_Pa=None,
      relative_pressure_residual=None,
      axis_geometry_residual_m=None,
      axis_invariant_residual=None,
      axis_candidate_verified=False,
      ambient_pressure_verified=False,
      message='march must be a MocAmbientShockBoundaryMarchResult',
    )
  source = march.boundary_samples[-1] if march.boundary_samples else None
  if not march.converged or source is None:
    return MocAmbientAxisClosureResult(
      status=MocAmbientAxisClosureStatus.MARCH_FAILURE,
      source_boundary_sample=source,
      axis_point_m=None,
      axis_state=None,
      axis_total_pressure_Pa=None,
      axis_static_pressure_Pa=None,
      ambient_pressure_Pa=ambient_pressure,
      pressure_residual_Pa=None,
      relative_pressure_residual=None,
      axis_geometry_residual_m=None,
      axis_invariant_residual=None,
      axis_candidate_verified=False,
      ambient_pressure_verified=False,
      message=(
        'ambient axis closure requires a converged marched boundary with a '
        f'final sample: {march.message}'
      ),
    )

  axis = centerline_characteristic_point(
    source.state,
    CharacteristicFamily.MINUS,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  axis_candidate_verified = (
    axis.converged
    and axis.point_m is not None
    and axis.state is not None
    and abs(axis.point_m[1]) <= position_tolerance_m
    and abs(axis.state.theta_rad) <= invariant_tolerance
  )
  if not axis_candidate_verified:
    return MocAmbientAxisClosureResult(
      status=MocAmbientAxisClosureStatus.AXIS_FAILURE,
      source_boundary_sample=source,
      axis_point_m=axis.point_m,
      axis_state=axis.state,
      axis_total_pressure_Pa=source.total_pressure_Pa,
      axis_static_pressure_Pa=None,
      ambient_pressure_Pa=ambient_pressure,
      pressure_residual_Pa=None,
      relative_pressure_residual=None,
      axis_geometry_residual_m=axis.geometry_residual,
      axis_invariant_residual=axis.invariant_residual_minus,
      axis_candidate_verified=False,
      ambient_pressure_verified=False,
      message=f'final ambient C- sample did not produce a valid axis candidate: {axis.message}',
    )

  assert axis.state is not None
  assert axis.point_m is not None
  axis_static_pressure = _static_pressure_from_total(
    axis.state,
    source.total_pressure_Pa,
  )
  pressure_residual = axis_static_pressure - ambient_pressure
  relative_pressure_residual = pressure_residual / ambient_pressure
  ambient_pressure_verified = abs(relative_pressure_residual) <= pressure_tolerance
  if ambient_pressure_verified:
    status = MocAmbientAxisClosureStatus.CONVERGED
    message = (
      'final ambient C- sample reaches a centerline candidate and its '
      'carried static pressure matches ambient within tolerance; full '
      'physical downstream closure remains pending'
    )
  else:
    status = MocAmbientAxisClosureStatus.PRESSURE_FAILURE
    message = (
      'final ambient C- sample reaches a geometric centerline candidate, '
      'but its carried static pressure does not match ambient: '
      f'relative residual={relative_pressure_residual}'
    )
  return MocAmbientAxisClosureResult(
    status=status,
    source_boundary_sample=source,
    axis_point_m=axis.point_m,
    axis_state=axis.state,
    axis_total_pressure_Pa=source.total_pressure_Pa,
    axis_static_pressure_Pa=axis_static_pressure,
    ambient_pressure_Pa=ambient_pressure,
    pressure_residual_Pa=pressure_residual,
    relative_pressure_residual=relative_pressure_residual,
    axis_geometry_residual_m=axis.geometry_residual,
    axis_invariant_residual=axis.invariant_residual_minus,
    axis_candidate_verified=axis_candidate_verified,
    ambient_pressure_verified=ambient_pressure_verified,
    message=message,
  )
####


def _point_key(point: tuple[float, float], tolerance_m: float) -> tuple[int, int]:
  return round(point[0] / tolerance_m), round(point[1] / tolerance_m)


def _edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _point_key(first, tolerance_m)
  second_key = _point_key(second, tolerance_m)
  return (first_key, second_key) if first_key <= second_key else (second_key, first_key)


def _edge_counts(
  cells: Sequence[MocCharacteristicCell],
  tolerance_m: float,
) -> dict[tuple[tuple[int, int], tuple[int, int]], int]:
  counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  for cell in cells:
    vertices = tuple(cell.vertices_xr_m)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      edge = _edge_key(first, second, tolerance_m)
      counts[edge] = counts.get(edge, 0) + 1
  return counts


def _path_is_boundary(
  points: Sequence[tuple[float, float]],
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  tolerance_m: float,
) -> bool:
  return all(
    edge_counts.get(_edge_key(first, second, tolerance_m), 0) == 1
    for first, second in zip(points, points[1:])
  )


def assemble_ambient_shock_characteristic_strip(
  shock_fit: MocShockBoundaryFitResult,
  ambient_boundary: Sequence[MocAmbientBoundarySample],
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocAmbientShockStripResult:
  """Assemble the correctly oriented shock/ambient characteristic strip.

  The supplied ambient boundary must already satisfy pressure and tangent
  acceptance.  The diagonal condition is that shock ``C+`` rays arrive at the
  corresponding ambient samples.  The final polygon edge is retained as a
  typed terminal characteristic trace; it is not relabeled as a centerline.
  """

  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    ambient = _empty_ambient_boundary(None, message='ambient boundary was not assembled')
    return _strip_failure(
      MocAmbientShockStripStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
  except (TypeError, ValueError):
    ambient = _empty_ambient_boundary(None, message='ambient pressure and target ordinate must be numeric')
    return _strip_failure(
      MocAmbientShockStripStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='ambient_pressure_Pa and target_centerline_y_m must be finite numeric values',
    )
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  if not isfinite(target_y):
    raise ValueError('target_centerline_y_m must be finite')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not shock_fit.converged:
    ambient = _empty_ambient_boundary(ambient_pressure, message='shock fit is not converged')
    return _strip_failure(
      MocAmbientShockStripStatus.SHOCK_FAILURE,
      ambient_boundary=ambient,
      message=f'shock boundary fit is not converged: {shock_fit.message}',
    )
  shock_samples = tuple(shock_fit.boundary_states)
  samples = tuple(ambient_boundary)
  if len(shock_samples) < 3 or len(samples) != len(shock_samples):
    ambient = _empty_ambient_boundary(ambient_pressure, message='shock and ambient sample counts are incompatible')
    return _strip_failure(
      MocAmbientShockStripStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='shock and ambient boundaries require the same count of at least three samples',
    )
  if any(not isinstance(sample, MocAmbientBoundarySample) for sample in samples):
    ambient = _empty_ambient_boundary(ambient_pressure, message='ambient boundary sample type is invalid')
    return _strip_failure(
      MocAmbientShockStripStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      message='ambient_boundary must contain MocAmbientBoundarySample values',
    )
  ambient = validate_ambient_pressure_boundary(
    samples,
    ambient_pressure,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
  )
  if not ambient.converged:
    return _strip_failure(
      MocAmbientShockStripStatus.AMBIENT_BOUNDARY_FAILURE,
      ambient_boundary=ambient,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      ambient_points=tuple(sample.point_m for sample in samples),
      message=f'ambient boundary is not accepted: {ambient.message}',
    )
  shock_points = tuple(sample.point_m for sample in shock_samples)
  ambient_points = tuple(sample.point_m for sample in samples)
  if any(
    abs(sample.state.x_m - sample.point_m[0]) > position_tolerance_m
    or abs(sample.state.y_m - sample.point_m[1]) > position_tolerance_m
    for sample in shock_samples
  ):
    return _strip_failure(
      MocAmbientShockStripStatus.INVALID_INPUT,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary state coordinates do not match their fitted points',
    )
  if any(point[1] < target_y - position_tolerance_m for point in (*shock_points, *ambient_points)):
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock/ambient boundary crossed below the target centerline',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    for first, second in zip(shock_points, shock_points[1:])
  ):
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary must be strictly downstream and nonincreasing in y',
    )
  if sqrt(
    (shock_points[0][0] - ambient_points[0][0]) ** 2
    + (shock_points[0][1] - ambient_points[0][1]) ** 2
  ) > position_tolerance_m:
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock and ambient boundaries must share their attachment point',
    )
  if abs(shock_points[-1][1] - target_y) > position_tolerance_m:
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary must terminate on the target centerline',
    )
  if (
    abs(shock_samples[0].state.theta_rad - samples[0].state.theta_rad)
    > invariant_tolerance
    or abs(shock_samples[0].state.mach - samples[0].state.mach)
    > invariant_tolerance
  ):
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock and ambient attachment states must agree at the shared point',
    )
  pressure_ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in shock_samples
  )
  if any(ratio <= 0.0 or ratio >= 1.0 for ratio in pressure_ratios):
    return _strip_failure(
      MocAmbientShockStripStatus.SHOCK_FAILURE,
      ambient_boundary=ambient,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message='shock boundary must carry strict total-pressure loss at every sample',
    )
  ####

  expected_count = len(shock_samples)
  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for plus_index in range(expected_count):
    plus_source = shock_samples[plus_index].state
    for minus_index in range(plus_index + 1):
      minus_source = samples[minus_index].state
      if plus_index == minus_index:
        point_result = _shock_endpoint_characteristic_point(
          plus_source,
          minus_source,
          ambient_points[minus_index],
          position_tolerance_m=position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
      else:
        point_result = interior_characteristic_point(
          plus_source,
          minus_source,
          position_tolerance_m=position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
      if not point_result.converged or point_result.point_m is None or point_result.state is None:
        status = (
          MocAmbientShockStripStatus.INVARIANT_FAILURE
          if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
          else MocAmbientShockStripStatus.GEOMETRY_FAILURE
        )
        return _strip_failure(
          status,
          ambient_boundary=ambient,
          characteristic_layer_count=expected_count - 1,
          nodes=tuple(nodes_by_index.values()),
          shock_points=shock_points,
          ambient_points=ambient_points,
          pressure_ratios=pressure_ratios,
          message=(
            f'shock/ambient characteristic node ({plus_index}, {minus_index}) '
            f'failed: {point_result.message}'
          ),
        )
      point = point_result.point_m
      if point[1] < target_y - position_tolerance_m:
        return _strip_failure(
          MocAmbientShockStripStatus.GEOMETRY_FAILURE,
          ambient_boundary=ambient,
          characteristic_layer_count=expected_count - 1,
          nodes=tuple(nodes_by_index.values()),
          shock_points=shock_points,
          ambient_points=ambient_points,
          pressure_ratios=pressure_ratios,
          message=f'shock/ambient node ({plus_index}, {minus_index}) crossed below the target centerline',
        )
      if plus_index != minus_index and point[0] <= max(
        plus_source.x_m,
        minus_source.x_m,
      ) + position_tolerance_m:
        return _strip_failure(
          MocAmbientShockStripStatus.GEOMETRY_FAILURE,
          ambient_boundary=ambient,
          characteristic_layer_count=expected_count - 1,
          nodes=tuple(nodes_by_index.values()),
          shock_points=shock_points,
          ambient_points=ambient_points,
          pressure_ratios=pressure_ratios,
          message=f'shock/ambient node ({plus_index}, {minus_index}) has no forward margin',
        )
      nodes_by_index[(plus_index, minus_index)] = MocCharacteristicNode(
        centerline_index=plus_index,
        boundary_index=minus_index,
        point_m=(float(point[0]), float(point[1])),
        state=point_result.state,
        point_result=point_result,
        total_pressure_Pa=samples[minus_index].total_pressure_Pa,
      )
  ####

  def node_point(plus_index: int, minus_index: int) -> tuple[float, float]:
    return nodes_by_index[(plus_index, minus_index)].point_m

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(expected_count - 1):
      vertices = (
        (shock_points[index], shock_points[index + 1], node_point(index + 1, 0))
        if index == 0
        else (
          shock_points[index],
          shock_points[index + 1],
          node_point(index + 1, 0),
          node_point(index, 0),
        )
      )
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='shock-ambient-shock-strip',
          vertices_xr_m=vertices,
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    for row in range(1, expected_count - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='shock-ambient-interior',
            vertices_xr_m=(
              node_point(row, column),
              node_point(row + 1, column),
              node_point(row + 1, column + 1),
              node_point(row, column + 1),
            ),
            centerline_indices=(row, row + 1),
            boundary_indices=(column, column + 1),
          )
        )
    for index in range(expected_count - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='shock-ambient-ambient-strip',
          vertices_xr_m=(
            node_point(index, index),
            node_point(index + 1, index),
            ambient_points[index + 1],
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        )
      )
  except (KeyError, ValueError) as error:
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=tuple(cells_list),
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message=f'shock/ambient characteristic cell geometry failed: {error}',
    )
  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _strip_failure(
      MocAmbientShockStripStatus.TOPOLOGY_FAILURE,
      ambient_boundary=ambient,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message=f'shock/ambient characteristic strip topology failed: {topology.message}',
    )
  edge_counts = _edge_counts(cells, position_tolerance_m)
  if not _path_is_boundary(shock_points, edge_counts, position_tolerance_m):
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message='shock/ambient strip is missing an explicit shock boundary edge',
    )
  if not _path_is_boundary(ambient_points, edge_counts, position_tolerance_m):
    return _strip_failure(
      MocAmbientShockStripStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message='shock/ambient strip is missing an explicit ambient boundary edge',
    )
  terminal_points = [shock_points[-1]]
  terminal_states = [shock_samples[-1].state]
  terminal_pressures = [shock_samples[-1].downstream_total_pressure_Pa]
  for boundary_index in range(expected_count - 1):
    terminal_node = nodes_by_index[(expected_count - 1, boundary_index)]
    terminal_points.append(terminal_node.point_m)
    terminal_states.append(terminal_node.state)
    terminal_pressures.append(
      float(terminal_node.total_pressure_Pa)
      if terminal_node.total_pressure_Pa is not None
      else samples[boundary_index].total_pressure_Pa
    )
  terminal_points.append(ambient_points[-1])
  terminal_states.append(samples[-1].state)
  terminal_pressures.append(samples[-1].total_pressure_Pa)
  maximum_geometry_residual = max(
    (
      abs(node.point_result.geometry_residual)
      for node in nodes_by_index.values()
      if node.point_result.geometry_residual is not None
    ),
    default=None,
  )
  maximum_invariant_residual = max(
    (
      abs(value)
      for node in nodes_by_index.values()
      for value in (
        node.point_result.invariant_residual_plus,
        node.point_result.invariant_residual_minus,
      )
      if value is not None
    ),
    default=None,
  )
  return MocAmbientShockStripResult(
    status=MocAmbientShockStripStatus.CONVERGED_OPEN,
    characteristic_layer_count=expected_count - 1,
    nodes=tuple(nodes_by_index.values()),
    cells=cells,
    topology=topology,
    shock_boundary_points_m=shock_points,
    ambient_boundary_points_m=ambient_points,
    terminal_trace_points_m=tuple(terminal_points),
    terminal_trace_states=tuple(terminal_states),
    terminal_trace_total_pressure_Pa=tuple(terminal_pressures),
    ambient_boundary=ambient,
    maximum_geometry_residual_m=maximum_geometry_residual,
    maximum_absolute_invariant_residual=maximum_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios),
    message=(
      'shock-sourced C+ and ambient-sourced C- characteristics formed a '
      'connected physical-boundary strip; terminal centerline closure remains pending'
    ),
  )
####
