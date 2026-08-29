"""Companion-boundary characteristic strip for the Euler shock lane.

The conservative shock curve is a mixed characteristic boundary: one
characteristic family enters the downstream domain from the shock while the
other must come from a second boundary.  This module assembles that explicit
one-layer strip without treating a prescribed companion boundary as a closed
shock cell or as a production-quality Euler field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, tan
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  MocEulerShockBoundaryOrientation,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  interior_characteristic_point,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocEulerAmbientCompanionBoundaryStatus',
  'MocEulerAmbientCompanionBoundaryResult',
  'solve_euler_ambient_companion_boundary_reference',
  'MocEulerCompanionFieldStatus',
  'MocEulerCompanionFieldResult',
  'assemble_euler_consistent_companion_characteristic_strip',
)


class MocEulerCompanionFieldStatus(str, Enum):
  """Outcome of an explicit companion-boundary characteristic strip."""

  CONVERGED_OPEN_COMPANION_FIELD = 'converged_open_companion_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'shock_boundary_required'
  COMPANION_BOUNDARY_REQUIRED = 'companion_boundary_required'
  CHARACTERISTIC_ORIENTATION_FAILURE = 'characteristic_orientation_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


class MocEulerAmbientCompanionBoundaryStatus(str, Enum):
  """Outcome of deriving an ambient-conditioned companion trace."""

  CONVERGED_AMBIENT_COMPANION_BOUNDARY = (
    'converged_ambient_companion_boundary'
  )
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'shock_boundary_required'
  AMBIENT_PRESSURE_FAILURE = 'ambient_pressure_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientCompanionBoundaryResult:
  """A solver-derived ambient/isobaric companion boundary reference.

  The trace uses the shock's downstream total-pressure samples to invert the
  ambient static pressure and carries one seeded ``C-`` invariant along the
  resulting streamline-like boundary.  The seed separation and invariant
  are explicit research inputs; this result is not a globally coupled
  reflected free-boundary solution and cannot promote a chain cell.
  """

  status: MocEulerAmbientCompanionBoundaryStatus
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None
  ambient_pressure_Pa: float | None = None
  samples: tuple[MocChainBoundarySample, ...] = ()
  static_pressure_residuals: tuple[float, ...] = ()
  companion_invariant_residuals: tuple[float, ...] = ()
  geometry_residuals_m: tuple[float, ...] = ()
  seed_k_minus_rad: float | None = None
  seed_flow_angle_rad: float | None = None
  separation_m: float | None = None
  minimum_shock_clearance_m: float | None = None
  maximum_static_pressure_residual: float | None = None
  maximum_companion_invariant_residual: float | None = None
  maximum_geometry_residual_m: float | None = None
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientCompanionBoundaryStatus):
      raise TypeError(
        'status must be a MocEulerAmbientCompanionBoundaryStatus'
      )
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    if self.ambient_pressure_Pa is not None:
      pressure = float(self.ambient_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      object.__setattr__(self, 'ambient_pressure_Pa', pressure)
    samples = tuple(self.samples)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in samples):
      raise TypeError('samples must contain MocChainBoundarySample values')
    object.__setattr__(self, 'samples', samples)
    expected = len(samples)
    for name in (
      'static_pressure_residuals',
      'companion_invariant_residuals',
      'geometry_residuals_m',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != expected:
        raise ValueError(f'{name} must match the companion sample count')
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'seed_k_minus_rad',
      'seed_flow_angle_rad',
      'separation_m',
      'minimum_shock_clearance_m',
      'maximum_static_pressure_residual',
      'maximum_companion_invariant_residual',
      'maximum_geometry_residual_m',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or (
        numeric < 0.0 and name not in ('seed_k_minus_rad', 'seed_flow_angle_rad')
      ):
        raise ValueError(f'{name} must be finite and valid when supplied')
      object.__setattr__(self, name, numeric)
    for name in (
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))
    ####

  @property
  def converged(self) -> bool:
    """Whether every derived ambient companion sample passed its checks."""

    return self.status is MocEulerAmbientCompanionBoundaryStatus.CONVERGED_AMBIENT_COMPANION_BOUNDARY
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(self.converged and self.samples)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'shock_boundary_status': (
        None if self.shock_boundary is None else self.shock_boundary.status.value
      ),
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'sample_count': len(self.samples),
      'points_m': [list(sample.point_m) for sample in self.samples],
      'mach': [sample.state.mach for sample in self.samples],
      'flow_angles_rad': [sample.state.theta_rad for sample in self.samples],
      'total_pressure_Pa': [
        sample.total_pressure_Pa for sample in self.samples
      ],
      'static_pressure_residuals': list(self.static_pressure_residuals),
      'companion_invariant_residuals': list(self.companion_invariant_residuals),
      'geometry_residuals_m': list(self.geometry_residuals_m),
      'seed_k_minus_rad': self.seed_k_minus_rad,
      'seed_flow_angle_rad': self.seed_flow_angle_rad,
      'separation_m': self.separation_m,
      'minimum_shock_clearance_m': self.minimum_shock_clearance_m,
      'maximum_static_pressure_residual': self.maximum_static_pressure_residual,
      'maximum_companion_invariant_residual': (
        self.maximum_companion_invariant_residual
      ),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldResult:
  """A bounded shock/companion characteristic strip.

  The strip is deliberately open in the physical sense.  Its cells form a
  polygonal patch, but the companion boundary is caller-supplied and no
  ambient, reflected free-boundary, or downstream chain closure is inferred.
  """

  status: MocEulerCompanionFieldStatus
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None
  shock_boundary_points_m: tuple[tuple[float, float], ...] = ()
  companion_boundary_points_m: tuple[tuple[float, float], ...] = ()
  interior_points_m: tuple[tuple[float, float], ...] = ()
  shock_boundary_states: tuple[CharacteristicState, ...] = ()
  shock_boundary_total_pressure_Pa: tuple[float, ...] = ()
  companion_boundary_states: tuple[CharacteristicState, ...] = ()
  companion_boundary_total_pressure_Pa: tuple[float, ...] = ()
  interior_states: tuple[CharacteristicState, ...] = ()
  interior_total_pressure_Pa: tuple[float, ...] = ()
  point_results: tuple[CharacteristicPointResult, ...] = ()
  shock_boundary_orientation: MocEulerShockBoundaryOrientation | None = None
  shock_boundary_local_euler_verified: bool = False
  companion_boundary_contract_verified: bool = False
  pressure_lineage_verified: bool = False
  maximum_geometry_residual_m: float | None = None
  maximum_absolute_invariant_residual: float | None = None
  minimum_forward_margin_m: float | None = None
  maximum_companion_pressure_residual: float | None = None
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerCompanionFieldStatus):
      raise TypeError('status must be a MocEulerCompanionFieldStatus')
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    if len(self.nodes) != len(self.point_results):
      raise ValueError('nodes and point_results must have equal lengths')
    if len(self.nodes) != len(self.interior_states):
      raise ValueError('nodes and interior states must have equal lengths')
    if len(self.nodes) != len(self.interior_total_pressure_Pa):
      raise ValueError('nodes and interior pressures must have equal lengths')
    if len(self.shock_boundary_points_m) != len(self.shock_boundary_states):
      raise ValueError('shock boundary points and states must have equal lengths')
    if self.shock_boundary_total_pressure_Pa and len(
      self.shock_boundary_total_pressure_Pa
    ) != len(self.shock_boundary_points_m):
      raise ValueError(
        'shock boundary points and pressures must have equal lengths'
      )
    if len(self.companion_boundary_points_m) != len(self.companion_boundary_states):
      raise ValueError('companion boundary points and states must have equal lengths')
    if self.companion_boundary_total_pressure_Pa and len(
      self.companion_boundary_total_pressure_Pa
    ) != len(self.companion_boundary_points_m):
      raise ValueError(
        'companion boundary points and pressures must have equal lengths'
      )
    if len(self.interior_points_m) != len(self.nodes):
      raise ValueError('interior points and nodes must have equal lengths')
    for name, states in (
      ('shock_boundary_states', self.shock_boundary_states),
      ('companion_boundary_states', self.companion_boundary_states),
      ('interior_states', self.interior_states),
    ):
      if any(not isinstance(state, CharacteristicState) for state in states):
        raise TypeError(f'{name} must contain CharacteristicState values')
    for name, points in (
      ('shock_boundary_points_m', self.shock_boundary_points_m),
      ('companion_boundary_points_m', self.companion_boundary_points_m),
      ('interior_points_m', self.interior_points_m),
    ):
      if any(
        len(point) != 2 or not all(isfinite(float(value)) for value in point)
        for point in points
      ):
        raise ValueError(f'{name} must contain finite coordinate pairs')
    if any(
      not isfinite(float(value)) or value <= 0.0
      for value in self.interior_total_pressure_Pa
    ):
      raise ValueError('interior total pressures must be finite and positive')
    for name, pressures in (
      ('shock_boundary_total_pressure_Pa', self.shock_boundary_total_pressure_Pa),
      (
        'companion_boundary_total_pressure_Pa',
        self.companion_boundary_total_pressure_Pa,
      ),
    ):
      if any(not isfinite(float(value)) or value <= 0.0 for value in pressures):
        raise ValueError(f'{name} must contain finite positive values')
    for name in (
      'maximum_geometry_residual_m',
      'maximum_absolute_invariant_residual',
      'minimum_forward_margin_m',
      'maximum_companion_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or (name != 'minimum_forward_margin_m' and numeric < 0.0):
        raise ValueError(f'{name} must be finite and valid when supplied')
      object.__setattr__(self, name, numeric)
    if self.shock_boundary_orientation is not None and not isinstance(
      self.shock_boundary_orientation,
      MocEulerShockBoundaryOrientation,
    ):
      raise TypeError(
        'shock_boundary_orientation must be a MocEulerShockBoundaryOrientation'
      )
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult when supplied'
      )
    for name in (
      'shock_boundary_local_euler_verified',
      'companion_boundary_contract_verified',
      'pressure_lineage_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the bounded strip assembled numerically."""

    return self.status is MocEulerCompanionFieldStatus.CONVERGED_OPEN_COMPANION_FIELD
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether every interior node carries a bounded state and pressure."""

    return bool(
      self.converged
      and self.nodes
      and len(self.interior_states) == len(self.nodes)
      and len(self.interior_total_pressure_Pa) == len(self.nodes)
    )
  ####

  @property
  def downstream_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the carried open-field frontier for a future solver.

    The interior intersections form the downstream frontier of this
    one-layer strip.  They are state-carrying samples, but they are not a
    physical chain-cell perimeter: the companion/free-boundary and entropy
    closure are still unsolved.  Returning an empty tuple for an incomplete
    field makes that boundary explicit to planners without allowing them to
    manufacture a handoff from geometry alone.
    """

    if not self.state_sampling_available:
      return ()
    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.interior_states,
        self.interior_total_pressure_Pa,
        strict=True,
      )
    )
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit chain boundary represented by this field.

    A companion strip has a topologically bounded patch, but its second
    characteristic boundary is an input to the strip rather than a solved
    ambient/free-boundary closure.  Consequently a converged strip must
    enter a continued-chain planner as a non-physical stop.  Keeping this
    conversion on the typed result prevents a caller from treating
    ``converged`` or ``forms_closed_zone`` as permission to relabel the strip
    as a resolved chain cell.
    """

    if self.converged:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'Euler companion characteristic strip is locally assembled but its '
        'companion/ambient downstream closure is open; no continued cell may '
        'be promoted from this field'
      )
    elif self.status is MocEulerCompanionFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = 'Euler companion characteristic strip rejected its inputs'
    elif self.status is MocEulerCompanionFieldStatus.SHOCK_BOUNDARY_REQUIRED:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = (
        'Euler companion characteristic strip has no locally verified shock '
        'boundary to seed the downstream field'
      )
    elif self.status is MocEulerCompanionFieldStatus.COMPANION_BOUNDARY_REQUIRED:
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
      message = (
        'Euler companion characteristic strip is missing its second '
        'characteristic boundary; no state-carrying cell handoff exists'
      )
    elif self.status is MocEulerCompanionFieldStatus.CHARACTERISTIC_ORIENTATION_FAILURE:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = (
        'Euler companion characteristic strip received a boundary whose '
        'characteristic orientation is not supported by this stencil'
      )
    elif self.status is MocEulerCompanionFieldStatus.TOPOLOGY_FAILURE:
      reason = MocChainTerminationReason.TOPOLOGY_INVALID
      message = (
        'Euler companion characteristic strip did not produce a valid '
        'connected bounded mesh'
      )
    elif self.status in (
      MocEulerCompanionFieldStatus.PRESSURE_FAILURE,
      MocEulerCompanionFieldStatus.INVARIANT_FAILURE,
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
      message = (
        'Euler companion characteristic strip did not preserve a usable '
        'state/pressure handoff'
      )
    else:
      reason = MocChainTerminationReason.SOLVER_ERROR
      message = (
        'Euler companion characteristic strip failed before a continued '
        'cell handoff was available'
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'euler_companion_field_status': self.status.value,
        'node_count': self.node_count,
        'cell_count': self.cell_count,
        'shock_boundary_orientation': (
          None
          if self.shock_boundary_orientation is None
          else self.shock_boundary_orientation.value
        ),
        'shock_boundary_local_euler_verified': (
          self.shock_boundary_local_euler_verified
        ),
        'companion_boundary_contract_verified': (
          self.companion_boundary_contract_verified
        ),
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'topology_forms_closed_zone': self.topology.forms_closed_zone,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'required_next_boundary': (
          'ambient/free-boundary plus downstream entropy-coupled closure'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'shock_boundary_status': (
        None if self.shock_boundary is None else self.shock_boundary.status.value
      ),
      'shock_boundary_sample_count': len(self.shock_boundary_points_m),
      'companion_boundary_sample_count': len(self.companion_boundary_points_m),
      'interior_sample_count': len(self.interior_points_m),
      'shock_boundary_points_m': [list(point) for point in self.shock_boundary_points_m],
      'companion_boundary_points_m': [
        list(point) for point in self.companion_boundary_points_m
      ],
      'interior_points_m': [list(point) for point in self.interior_points_m],
      'shock_boundary_orientation': (
        None
        if self.shock_boundary_orientation is None
        else self.shock_boundary_orientation.value
      ),
      'shock_boundary_local_euler_verified': self.shock_boundary_local_euler_verified,
      'shock_boundary_maximum_jump_residual': (
        None
        if self.shock_boundary is None
        else self.shock_boundary.maximum_shock_jump_residual
      ),
      'companion_boundary_contract_verified': self.companion_boundary_contract_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_companion_pressure_residual': self.maximum_companion_pressure_residual,
      'downstream_handoff_sample_count': len(self.downstream_handoff),
      'downstream_handoff_available': bool(self.downstream_handoff),
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####


def solve_euler_ambient_companion_boundary_reference(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  ambient_pressure_Pa: float,
  *,
  separation_m: float = 0.5,
  seed_flow_angle_rad: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
) -> MocEulerAmbientCompanionBoundaryResult:
  """Derive an ambient-conditioned companion trace from shock data.

  The shock downstream total-pressure lineage determines the supersonic Mach
  number at the requested ambient pressure.  A single seeded ``C-``
  invariant then determines the boundary flow angle, and the boundary is
  advanced as a streamline-like curve using that angle.  This is a bounded
  solver-owned reference for the missing second boundary; the separation and
  seed angle remain explicit parameters, and the result is intentionally not
  a globally coupled physical closure.
  """

  defaults = {
    'position_tolerance_m': 1.0e-10,
    'invariant_tolerance': 1.0e-10,
    'pressure_tolerance': 1.0e-10,
  }
  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.INVALID_INPUT,
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
      **defaults,
    )
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    separation = float(separation_m)
    seed_angle = float(seed_flow_angle_rad)
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      message=(
        'ambient companion pressure, separation, seed angle, and tolerances '
        'must be numeric'
      ),
      **defaults,
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('invariant_tolerance', invariant_tolerance_value),
    ('pressure_tolerance', pressure_tolerance_value),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='ambient_pressure_Pa must be finite and positive',
    )
  if not isfinite(separation) or separation <= position_tolerance:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='separation_m must be finite and greater than position tolerance',
    )
  if not isfinite(seed_angle):
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='seed_flow_angle_rad must be finite',
    )
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='ambient companion boundary requires a locally Euler-verified shock curve',
    )
  if shock_boundary.orientation is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message=(
        'ambient companion boundary reference requires the mixed-'
        'characteristic shock orientation'
      ),
    )
  points = tuple(shock_boundary.shock_points_m)
  pressures = tuple(shock_boundary.downstream_total_pressure_Pa)
  states = tuple(shock_boundary.downstream_states)
  if len(points) < 2 or len(points) != len(pressures) or len(points) != len(states):
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='shock curve must contain at least two aligned points and states',
    )
  if any(
    points[index + 1][0] <= points[index][0] + position_tolerance
    for index in range(len(points) - 1)
  ):
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='shock curve must advance strictly downstream in x',
    )
  gamma = states[0].gamma
  if any(abs(state.gamma - gamma) > invariant_tolerance_value for state in states):
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.INVARIANT_FAILURE,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='shock downstream states must use one gamma',
    )
  first_ratio = pressures[0] / ambient_pressure
  if not isfinite(first_ratio) or first_ratio <= 1.0:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message='ambient pressure must be below every shock downstream total pressure',
    )
  try:
    first_inverse = supersonic_mach_from_stagnation_pressure_ratio(
      first_ratio,
      gamma,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message=f'ambient Mach inversion failed: {error}',
    )
  if not first_inverse.converged or first_inverse.value is None:
    return MocEulerAmbientCompanionBoundaryResult(
      status=MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE,
      shock_boundary=shock_boundary,
      ambient_pressure_Pa=ambient_pressure,
      separation_m=separation,
      seed_flow_angle_rad=seed_angle,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      message=first_inverse.message,
    )
  first_nu = prandtl_meyer_angle_rad(first_inverse.value, gamma)
  seed_k_minus = seed_angle + first_nu
  samples: list[MocChainBoundarySample] = []
  static_pressure_residuals: list[float] = []
  invariant_residuals: list[float] = []
  geometry_residuals: list[float] = []
  clearances: list[float] = []
  previous_theta: float | None = None
  previous_y: float | None = None
  for index, (point, total_pressure, _downstream_state) in enumerate(
    zip(points, pressures, states, strict=True)
  ):
    ratio = total_pressure / ambient_pressure
    if not isfinite(ratio) or ratio <= 1.0:
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'shock sample {index} cannot support an ambient supersonic state',
      )
    try:
      inverse = supersonic_mach_from_stagnation_pressure_ratio(ratio, gamma)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'ambient Mach inversion failed at sample {index}: {error}',
      )
    if not inverse.converged or inverse.value is None:
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'ambient Mach inversion failed at sample {index}: {inverse.message}',
      )
    mach = inverse.value
    nu = prandtl_meyer_angle_rad(mach, gamma)
    theta = seed_k_minus - nu
    try:
      tangent = tan(theta)
    except (ArithmeticError, FloatingPointError, ValueError) as error:
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'ambient companion tangent failed at sample {index}: {error}',
      )
    if not isfinite(tangent):
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'ambient companion tangent is non-finite at sample {index}',
      )
    companion_y = (
      point[1] + separation
      if index == 0
      else previous_y
      + 0.5 * (previous_theta + theta) * (point[0] - points[index - 1][0])
    )
    if not isfinite(companion_y):
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'ambient companion point is non-finite at sample {index}',
      )
    clearance = companion_y - point[1]
    if clearance <= position_tolerance:
      return MocEulerAmbientCompanionBoundaryResult(
        status=MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        ambient_pressure_Pa=ambient_pressure,
        samples=tuple(samples),
        static_pressure_residuals=tuple(static_pressure_residuals),
        companion_invariant_residuals=tuple(invariant_residuals),
        geometry_residuals_m=tuple(geometry_residuals),
        seed_k_minus_rad=seed_k_minus,
        seed_flow_angle_rad=seed_angle,
        separation_m=separation,
        minimum_shock_clearance_m=min(clearances, default=None),
        maximum_static_pressure_residual=max(static_pressure_residuals, default=None),
        maximum_companion_invariant_residual=max(invariant_residuals, default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        message=f'ambient companion boundary crosses the shock at sample {index}',
      )
    static_pressure = total_pressure / (
      1.0 + 0.5 * (gamma - 1.0) * mach * mach
    ) ** (gamma / (gamma - 1.0))
    pressure_residual = abs(static_pressure - ambient_pressure) / ambient_pressure
    invariant_residual = abs(theta + nu - seed_k_minus)
    geometry_residual = (
      0.0
      if index == 0
      else abs(
        (companion_y - previous_y)
        - 0.5 * (previous_theta + theta) * (point[0] - points[index - 1][0])
      )
    )
    sample = MocChainBoundarySample(
      state=CharacteristicState(
        x_m=point[0],
        y_m=companion_y,
        theta_rad=theta,
        mach=mach,
        gamma=gamma,
      ),
      total_pressure_Pa=total_pressure,
    )
    samples.append(sample)
    static_pressure_residuals.append(pressure_residual)
    invariant_residuals.append(invariant_residual)
    geometry_residuals.append(geometry_residual)
    clearances.append(clearance)
    previous_theta = theta
    previous_y = companion_y
  maximum_pressure_residual = max(static_pressure_residuals, default=0.0)
  maximum_invariant_residual = max(invariant_residuals, default=0.0)
  maximum_geometry_residual = max(geometry_residuals, default=0.0)
  if maximum_pressure_residual > pressure_tolerance_value:
    status = MocEulerAmbientCompanionBoundaryStatus.AMBIENT_PRESSURE_FAILURE
    message = 'ambient companion static-pressure residual exceeded tolerance'
  elif maximum_invariant_residual > invariant_tolerance_value:
    status = MocEulerAmbientCompanionBoundaryStatus.INVARIANT_FAILURE
    message = 'ambient companion C- invariant residual exceeded tolerance'
  elif maximum_geometry_residual > position_tolerance:
    status = MocEulerAmbientCompanionBoundaryStatus.GEOMETRY_FAILURE
    message = 'ambient companion streamline geometry residual exceeded tolerance'
  else:
    status = MocEulerAmbientCompanionBoundaryStatus.CONVERGED_AMBIENT_COMPANION_BOUNDARY
    message = (
      'ambient-conditioned companion boundary derived from shock total-pressure '
      'lineage; global reflected free-boundary closure remains pending'
    )
  return MocEulerAmbientCompanionBoundaryResult(
    status=status,
    shock_boundary=shock_boundary,
    ambient_pressure_Pa=ambient_pressure,
    samples=tuple(samples),
    static_pressure_residuals=tuple(static_pressure_residuals),
    companion_invariant_residuals=tuple(invariant_residuals),
    geometry_residuals_m=tuple(geometry_residuals),
    seed_k_minus_rad=seed_k_minus,
    seed_flow_angle_rad=seed_angle,
    separation_m=separation,
    minimum_shock_clearance_m=min(clearances, default=None),
    maximum_static_pressure_residual=maximum_pressure_residual,
    maximum_companion_invariant_residual=maximum_invariant_residual,
    maximum_geometry_residual_m=maximum_geometry_residual,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
    message=message,
  )
####


def _failure(
  status: MocEulerCompanionFieldStatus,
  message: str,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  **values: Any,
) -> MocEulerCompanionFieldResult:
  return MocEulerCompanionFieldResult(
    status=status,
    nodes=tuple(values.pop('nodes', ())),
    cells=tuple(values.pop('cells', ())),
    topology=values.pop('topology', validate_moc_mesh(())),
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    message=message,
    **values,
  )


def assemble_euler_consistent_companion_characteristic_strip(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  companion_boundary: Sequence[MocChainBoundarySample],
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
) -> MocEulerCompanionFieldResult:
  """Assemble a one-layer ``C+``/``C-`` strip from explicit boundaries.

  The locally conservative shock supplies the ``C+`` source at each sample.
  The companion boundary supplies the ``C-`` source at the matching sample.
  Matching total pressure is required so this narrow strip has one explicit
  isentropic pressure lineage; variable-entropy companion fields belong to a
  separate solver.  The returned patch remains open to physical closure and
  cannot seed a continued shock-cell chain.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'strip tolerances must be numeric',
    )
  if not isfinite(position_tolerance) or position_tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(invariant_tolerance_value) or invariant_tolerance_value <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not isfinite(pressure_tolerance_value) or pressure_tolerance_value <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return _failure(
      MocEulerCompanionFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      'companion strip requires a locally Euler-verified shock boundary',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
    )
  if shock_boundary.orientation is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY:
    return _failure(
      MocEulerCompanionFieldStatus.CHARACTERISTIC_ORIENTATION_FAILURE,
      'companion strip requires a mixed-characteristic shock boundary; the shock-only two-family stencil is not valid here',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  try:
    companion = tuple(companion_boundary)
  except TypeError:
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'companion_boundary must be an iterable of MocChainBoundarySample values',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  if len(companion) != len(shock_boundary.shock_points_m) or len(companion) < 2:
    return _failure(
      MocEulerCompanionFieldStatus.COMPANION_BOUNDARY_REQUIRED,
      'companion boundary must contain one state/pressure sample for every shock sample',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in companion):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'companion_boundary must contain MocChainBoundarySample values',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  gamma = shock_boundary.downstream_states[0].gamma
  if any(abs(sample.state.gamma - gamma) > invariant_tolerance_value for sample in companion):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'shock and companion boundaries must use the same gamma',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  companion_pressure_residuals = tuple(
    sample.total_pressure_Pa - expected
    for sample, expected in zip(
      companion,
      shock_boundary.downstream_total_pressure_Pa,
      strict=True,
    )
  )
  maximum_pressure_residual = max(
    (abs(value) for value in companion_pressure_residuals),
    default=None,
  )
  if any(
    abs(residual) > pressure_tolerance_value * max(1.0, abs(expected))
    for residual, expected in zip(
      companion_pressure_residuals,
      shock_boundary.downstream_total_pressure_Pa,
      strict=True,
    )
  ):
    return _failure(
      MocEulerCompanionFieldStatus.PRESSURE_FAILURE,
      'companion boundary total pressure does not match the shock downstream pressure lineage',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_points_m=shock_boundary.shock_points_m,
      companion_boundary_points_m=tuple(sample.point_m for sample in companion),
      shock_boundary_states=shock_boundary.downstream_states,
      companion_boundary_states=tuple(sample.state for sample in companion),
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
      maximum_companion_pressure_residual=maximum_pressure_residual,
    )
  ####

  nodes: list[MocCharacteristicNode] = []
  point_results: list[CharacteristicPointResult] = []
  interior_states: list[CharacteristicState] = []
  interior_points: list[tuple[float, float]] = []
  interior_pressures: list[float] = []
  forward_margins: list[float] = []
  for index, (shock_state, companion_sample) in enumerate(
    zip(shock_boundary.downstream_states, companion, strict=True)
  ):
    point_result = interior_characteristic_point(
      shock_state,
      companion_sample.state,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
    )
    point_results.append(point_result)
    if not point_result.converged or point_result.point_m is None or point_result.state is None:
      status = (
        MocEulerCompanionFieldStatus.INVARIANT_FAILURE
        if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
        else MocEulerCompanionFieldStatus.GEOMETRY_FAILURE
      )
      return _failure(
        status,
        f'companion characteristic intersection {index} failed: {point_result.message}',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        point_results=tuple(point_results[:-1]),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_geometry_residual_m=max(
          (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
          default=None,
        ),
        maximum_absolute_invariant_residual=max(
          (
            abs(value)
            for result in point_results
            for value in (
              result.invariant_residual_plus,
              result.invariant_residual_minus,
            )
            if value is not None
          ),
          default=None,
        ),
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
    point = (float(point_result.point_m[0]), float(point_result.point_m[1]))
    minimum_y = min(shock_state.y_m, companion_sample.state.y_m)
    maximum_y = max(shock_state.y_m, companion_sample.state.y_m)
    if point[1] < minimum_y - position_tolerance or point[1] > maximum_y + position_tolerance:
      return _failure(
        MocEulerCompanionFieldStatus.GEOMETRY_FAILURE,
        f'companion characteristic intersection {index} lies outside its two boundary samples',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        point_results=tuple(point_results[:-1]),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
    forward_margin = point[0] - max(shock_state.x_m, companion_sample.state.x_m)
    if forward_margin <= position_tolerance:
      return _failure(
        MocEulerCompanionFieldStatus.GEOMETRY_FAILURE,
        f'companion characteristic intersection {index} has no forward margin from its boundaries',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        point_results=tuple(point_results[:-1]),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
    forward_margins.append(forward_margin)
    interior_states.append(point_result.state)
    interior_points.append(point)
    pressure = shock_boundary.downstream_total_pressure_Pa[index]
    interior_pressures.append(pressure)
    nodes.append(
      MocCharacteristicNode(
        centerline_index=1,
        boundary_index=index,
        point_m=point,
        state=point_result.state,
        point_result=point_result,
        total_pressure_Pa=pressure,
      )
    )
  ####

  cells: list[MocCharacteristicCell] = []
  for index in range(len(nodes) - 1):
    try:
      cells.append(
        MocCharacteristicCell(
          cell_index=index,
          cell_kind='euler-shock-companion-characteristic-strip',
          vertices_xr_m=(
            shock_boundary.shock_points_m[index],
            shock_boundary.shock_points_m[index + 1],
            nodes[index + 1].point_m,
            nodes[index].point_m,
          ),
          centerline_indices=(1,),
          boundary_indices=(index, index + 1),
        )
      )
    except ValueError as error:
      return _failure(
        MocEulerCompanionFieldStatus.GEOMETRY_FAILURE,
        f'companion characteristic cell {index} geometry failed: {error}',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        cells=tuple(cells),
        point_results=tuple(point_results),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_geometry_residual_m=max(
          (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
          default=None,
        ),
        maximum_absolute_invariant_residual=max(
          (
            abs(value)
            for result in point_results
            for value in (
              result.invariant_residual_plus,
              result.invariant_residual_minus,
            )
            if value is not None
          ),
          default=None,
        ),
        minimum_forward_margin_m=min(forward_margins, default=None),
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
  cell_tuple = tuple(cells)
  topology = validate_moc_mesh(cell_tuple)
  if not topology.connected or topology.nonmanifold_edge_count or not topology.forms_closed_zone:
    return _failure(
      MocEulerCompanionFieldStatus.TOPOLOGY_FAILURE,
      f'companion characteristic strip topology failed: {topology.message}',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      nodes=tuple(nodes),
      cells=cell_tuple,
      topology=topology,
      point_results=tuple(point_results),
      interior_states=tuple(interior_states),
      interior_points_m=tuple(interior_points),
      interior_total_pressure_Pa=tuple(interior_pressures),
      shock_boundary_points_m=shock_boundary.shock_points_m,
      companion_boundary_points_m=tuple(sample.point_m for sample in companion),
      shock_boundary_states=shock_boundary.downstream_states,
      companion_boundary_states=tuple(sample.state for sample in companion),
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
      companion_boundary_contract_verified=True,
      pressure_lineage_verified=True,
      maximum_geometry_residual_m=max(
        (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
        default=None,
      ),
      maximum_absolute_invariant_residual=max(
        (
          abs(value)
          for result in point_results
          for value in (
            result.invariant_residual_plus,
            result.invariant_residual_minus,
          )
          if value is not None
        ),
        default=None,
      ),
      minimum_forward_margin_m=min(forward_margins, default=None),
      maximum_companion_pressure_residual=maximum_pressure_residual,
    )
  return MocEulerCompanionFieldResult(
    status=MocEulerCompanionFieldStatus.CONVERGED_OPEN_COMPANION_FIELD,
    nodes=tuple(nodes),
    cells=cell_tuple,
    topology=topology,
    shock_boundary=shock_boundary,
    shock_boundary_points_m=shock_boundary.shock_points_m,
    companion_boundary_points_m=tuple(sample.point_m for sample in companion),
    interior_points_m=tuple(interior_points),
    shock_boundary_states=shock_boundary.downstream_states,
    shock_boundary_total_pressure_Pa=shock_boundary.downstream_total_pressure_Pa,
    companion_boundary_states=tuple(sample.state for sample in companion),
    companion_boundary_total_pressure_Pa=tuple(
      sample.total_pressure_Pa for sample in companion
    ),
    interior_states=tuple(interior_states),
    interior_total_pressure_Pa=tuple(interior_pressures),
    point_results=tuple(point_results),
    shock_boundary_orientation=shock_boundary.orientation,
    shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    companion_boundary_contract_verified=True,
    pressure_lineage_verified=True,
    maximum_geometry_residual_m=max(
      (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (
        abs(value)
        for result in point_results
        for value in (
          result.invariant_residual_plus,
          result.invariant_residual_minus,
        )
        if value is not None
      ),
      default=None,
    ),
    minimum_forward_margin_m=min(forward_margins, default=None),
    maximum_companion_pressure_residual=maximum_pressure_residual,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
    message=(
      'Euler-consistent shock and explicit companion boundary formed an open '
      'one-layer characteristic strip; ambient/free-boundary closure and '
      'continued-cell promotion remain blocked'
    ),
  )
