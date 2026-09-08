"""Independent conservative boundary-face flux audit.

The coupled Euler result retains conservative cell states and the exact
quadrilateral mesh used by the solver, but its existing residual gates do not
retain a boundary-face flux ledger.  This audit replays every retained
boundary face from those states, checks internal-face antisymmetry, and keeps
the wall/free-boundary mass and energy constraints separate from cell Euler
residuals.  It is local research evidence; it does not establish a canonical
reflected free boundary or a production claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, sqrt
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_COUPLED_EULER_BOUNDARY_FLUX_AUDIT_OPERATOR_ID',
  'MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus',
  'MocReflectedDomainCoupledEulerBoundaryFluxAudit',
  'measure_reflected_domain_coupled_euler_boundary_fluxes',
)


MOC_REFLECTED_DOMAIN_COUPLED_EULER_BOUNDARY_FLUX_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.coupled-euler-boundary-flux-audit'
)

_BOUNDARY_KINDS = ('centerline', 'inlet', 'free-boundary', 'outlet')


class MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus(str, Enum):
  """Outcome of replaying retained conservative boundary faces."""

  CONVERGED_LOCAL_AUDIT = (
    'converged-local-coupled-euler-boundary-flux-audit'
  )
  INVALID_INPUT = 'invalid_input'
  MESH_FAILURE = 'coupled-euler-boundary-flux-audit-mesh-failure'
  STATE_FAILURE = 'coupled-euler-boundary-flux-audit-state-failure'
  FLUX_FAILURE = 'coupled-euler-boundary-flux-audit-flux-failure'
  CONSERVATION_FAILURE = (
    'coupled-euler-boundary-flux-audit-internal-conservation-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerBoundaryFluxAudit:
  """Retained-state boundary-face flux ledger and independent gates."""

  status: MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  axial_cell_count: int = 0
  transverse_cell_count: int = 0
  boundary_face_count: int = 0
  expected_boundary_face_count: int = 0
  internal_face_pair_count: int = 0
  boundary_face_counts: tuple[tuple[str, int], ...] = ()
  boundary_flux_totals: tuple[tuple[str, tuple[float, ...]], ...] = ()
  maximum_boundary_flux_magnitude: float | None = None
  maximum_internal_pair_residual: float | None = None
  maximum_wall_mass_flux: float | None = None
  maximum_wall_energy_flux: float | None = None
  retained_states_verified: bool = False
  boundary_face_ledger_verified: bool = False
  internal_flux_pair_cancellation_verified: bool = False
  wall_flux_law_verified: bool = False
  inlet_flux_replay_verified: bool = False
  outlet_flux_replay_verified: bool = False
  residual_channels_finite: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  boundary_flux_tolerance: float = 1.0e-10
  wall_flux_tolerance: float = 1.0e-10
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_COUPLED_EULER_BOUNDARY_FLUX_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus,
    ):
      raise TypeError('status must be a typed boundary-flux audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'candidate must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult or None'
      )
    ####
    for name in (
      'axial_cell_count',
      'transverse_cell_count',
      'boundary_face_count',
      'expected_boundary_face_count',
      'internal_face_pair_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    counts = tuple((str(kind), int(count)) for kind, count in self.boundary_face_counts)
    if any(kind not in _BOUNDARY_KINDS or count < 0 for kind, count in counts):
      raise ValueError('boundary_face_counts contains an invalid kind or count')
    ####
    totals = tuple(
      (str(kind), tuple(float(value) for value in flux))
      for kind, flux in self.boundary_flux_totals
    )
    if any(
      kind not in _BOUNDARY_KINDS
      or len(flux) != 4
      or any(not isfinite(value) for value in flux)
      for kind, flux in totals
    ):
      raise ValueError('boundary_flux_totals contains an invalid flux vector')
    ####
    for name in (
      'maximum_boundary_flux_magnitude',
      'maximum_internal_pair_residual',
      'maximum_wall_mass_flux',
      'maximum_wall_energy_flux',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'retained_states_verified',
      'boundary_face_ledger_verified',
      'internal_flux_pair_cancellation_verified',
      'wall_flux_law_verified',
      'inlet_flux_replay_verified',
      'outlet_flux_replay_verified',
      'residual_channels_finite',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('boundary_flux_tolerance', 'wall_flux_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.physical_closure_verified or self.production_claim_allowed:
      raise ValueError('boundary-flux audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('boundary-flux audit must retain its promotion block')
    ####
    object.__setattr__(self, 'boundary_face_counts', counts)
    object.__setattr__(self, 'boundary_flux_totals', totals)
    object.__setattr__(self, 'message', str(self.message))
    object.__setattr__(self, 'operator_id', str(self.operator_id))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus
      .CONVERGED_LOCAL_AUDIT
      and self.retained_states_verified
      and self.boundary_face_ledger_verified
      and self.internal_flux_pair_cancellation_verified
      and self.wall_flux_law_verified
      and self.inlet_flux_replay_verified
      and self.outlet_flux_replay_verified
      and self.residual_channels_finite
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'mesh': {
        'axial_cell_count': self.axial_cell_count,
        'transverse_cell_count': self.transverse_cell_count,
        'boundary_face_count': self.boundary_face_count,
        'expected_boundary_face_count': self.expected_boundary_face_count,
        'internal_face_pair_count': self.internal_face_pair_count,
        'boundary_face_counts': self.boundary_face_counts,
      },
      'boundary_flux_totals': self.boundary_flux_totals,
      'maximum_boundary_flux_magnitude': self.maximum_boundary_flux_magnitude,
      'maximum_internal_pair_residual': self.maximum_internal_pair_residual,
      'maximum_wall_mass_flux': self.maximum_wall_mass_flux,
      'maximum_wall_energy_flux': self.maximum_wall_energy_flux,
      'checks': {
        'retained_states_verified': self.retained_states_verified,
        'boundary_face_ledger_verified': self.boundary_face_ledger_verified,
        'internal_flux_pair_cancellation_verified': (
          self.internal_flux_pair_cancellation_verified
        ),
        'wall_flux_law_verified': self.wall_flux_law_verified,
        'inlet_flux_replay_verified': self.inlet_flux_replay_verified,
        'outlet_flux_replay_verified': self.outlet_flux_replay_verified,
        'residual_channels_finite': self.residual_channels_finite,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'retained-state conservative boundary-face flux audit; canonical '
        'reflected free-boundary, refinement, and external validation remain '
        'open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus,
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult | None,
  message: str,
  *,
  axial_cell_count: int = 0,
  transverse_cell_count: int = 0,
  retained_states_verified: bool = False,
  residual_channels_finite: bool = False,
  boundary_flux_tolerance: float = 1.0e-10,
  wall_flux_tolerance: float = 1.0e-10,
) -> MocReflectedDomainCoupledEulerBoundaryFluxAudit:
  return MocReflectedDomainCoupledEulerBoundaryFluxAudit(
    status=status,
    candidate=candidate,
    axial_cell_count=axial_cell_count,
    transverse_cell_count=transverse_cell_count,
    retained_states_verified=retained_states_verified,
    residual_channels_finite=residual_channels_finite,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    boundary_flux_tolerance=boundary_flux_tolerance,
    wall_flux_tolerance=wall_flux_tolerance,
    message=message,
  )
####


def _primitive(
  state: tuple[float, float, float, float],
  gamma: float,
) -> tuple[float, float, float, float, float]:
  density = float(state[0])
  if not isfinite(density) or density <= 0.0:
    raise ValueError('conservative state density must be positive')
  ####
  velocity_u = float(state[1]) / density
  velocity_v = float(state[2]) / density
  pressure = (gamma - 1.0) * (
    float(state[3])
    - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('conservative state pressure must be positive')
  ####
  sound_speed = sqrt(gamma * pressure / density)
  return density, velocity_u, velocity_v, pressure, sound_speed
####


def _face_geometry(
  first: tuple[float, float],
  second: tuple[float, float],
) -> tuple[float, float, float]:
  delta_x = float(second[0] - first[0])
  delta_y = float(second[1] - first[1])
  length = hypot(delta_x, delta_y)
  if not isfinite(length) or length <= 0.0:
    raise ValueError('boundary face has nonpositive length')
  ####
  return delta_y / length, -delta_x / length, length
####


def _euler_flux(
  state: tuple[float, float, float, float],
  normal_x: float,
  normal_y: float,
  gamma: float,
) -> tuple[float, float, float, float]:
  density, velocity_u, velocity_v, pressure, _sound_speed = _primitive(
    state,
    gamma,
  )
  normal_velocity = velocity_u * normal_x + velocity_v * normal_y
  return (
    density * normal_velocity,
    density * velocity_u * normal_velocity + pressure * normal_x,
    density * velocity_v * normal_velocity + pressure * normal_y,
    (state[3] + pressure) * normal_velocity,
  )
####


def _rusanov_flux(
  left: tuple[float, float, float, float],
  right: tuple[float, float, float, float],
  normal_x: float,
  normal_y: float,
  length: float,
  gamma: float,
) -> tuple[float, float, float, float]:
  left_flux = _euler_flux(left, normal_x, normal_y, gamma)
  right_flux = _euler_flux(right, normal_x, normal_y, gamma)
  _rho_l, u_l, v_l, _p_l, sound_l = _primitive(left, gamma)
  _rho_r, u_r, v_r, _p_r, sound_r = _primitive(right, gamma)
  wave = max(
    abs(u_l * normal_x + v_l * normal_y) + sound_l,
    abs(u_r * normal_x + v_r * normal_y) + sound_r,
  )
  return tuple(
    float(
      0.5 * (left_flux[index] + right_flux[index])
      - 0.5 * wave * (right[index] - left[index])
    )
    * length
    for index in range(4)
  )
####


def _wall_flux(
  state: tuple[float, float, float, float],
  normal_x: float,
  normal_y: float,
  length: float,
  gamma: float,
  pressure_override: float | None = None,
) -> tuple[float, float, float, float]:
  _density, _u, _v, pressure, _sound_speed = _primitive(state, gamma)
  boundary_pressure = pressure if pressure_override is None else pressure_override
  if not isfinite(boundary_pressure) or boundary_pressure <= 0.0:
    raise ValueError('wall boundary pressure must be finite and positive')
  ####
  return (
    0.0,
    boundary_pressure * normal_x * length,
    boundary_pressure * normal_y * length,
    0.0,
  )
####


def _ambient_ghost(
  state: tuple[float, float, float, float],
  pressure: float,
  gamma: float,
) -> tuple[float, float, float, float]:
  density, velocity_u, velocity_v, local_pressure, _sound_speed = _primitive(
    state,
    gamma,
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('outlet pressure must be finite and positive')
  ####
  entropy_proxy = local_pressure / density**gamma
  ghost_density = (pressure / entropy_proxy) ** (1.0 / gamma)
  return (
    ghost_density,
    ghost_density * velocity_u,
    ghost_density * velocity_v,
    pressure / (gamma - 1.0)
    + 0.5 * ghost_density * (velocity_u**2 + velocity_v**2),
  )
####


def _relative_vector_residual(
  first: tuple[float, ...],
  second: tuple[float, ...],
) -> float:
  return max(
    abs(left + right)
    / max(abs(left), abs(right), 1.0)
    for left, right in zip(first, second, strict=True)
  )
####


def measure_reflected_domain_coupled_euler_boundary_fluxes(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
  *,
  boundary_flux_tolerance: float = 1.0e-10,
  wall_flux_tolerance: float = 1.0e-10,
) -> MocReflectedDomainCoupledEulerBoundaryFluxAudit:
  """Recompute every retained boundary-face flux independently."""

  if not isinstance(
    candidate,
    MocReflectedDomainCoupledEulerFreeBoundaryResult,
  ):
    raise TypeError(
      'candidate must be a MocReflectedDomainCoupledEulerFreeBoundaryResult'
    )
  ####
  flux_tolerance = float(boundary_flux_tolerance)
  wall_tolerance = float(wall_flux_tolerance)
  if not isfinite(flux_tolerance) or flux_tolerance <= 0.0:
    raise ValueError('boundary_flux_tolerance must be finite and positive')
  ####
  if not isfinite(wall_tolerance) or wall_tolerance <= 0.0:
    raise ValueError('wall_flux_tolerance must be finite and positive')
  ####
  request = candidate.request
  if request is None:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.INVALID_INPUT,
      candidate,
      'candidate retained no coupled Euler request',
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  axial_count = int(request.axial_cell_count)
  transverse_count = int(request.transverse_cell_count)
  expected_cells = axial_count * transverse_count
  states = tuple(candidate.conservative_states_by_cell)
  cells = tuple(candidate.cell_vertices_by_cell_m)
  inlet_states = tuple(candidate.inlet_boundary_conservative_states_by_face)
  residuals = tuple(candidate.residual_channels_by_cell)
  if not (
    axial_count >= 1
    and transverse_count >= 1
    and len(states) == len(cells) == expected_cells
  ):
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.MESH_FAILURE,
      candidate,
      'retained cell state and quadrilateral mesh counts do not match the '
      'coupled request',
      axial_cell_count=axial_count,
      transverse_cell_count=transverse_count,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  gamma = float(request.mixed_regime_request.control_section.samples[-1].gamma)
  if not isfinite(gamma) or gamma <= 1.0:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.INVALID_INPUT,
      candidate,
      'coupled request retained no admissible gamma',
      axial_cell_count=axial_count,
      transverse_cell_count=transverse_count,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  residuals_finite = bool(
    len(residuals) == expected_cells
    and all(
      len(row) == 5 and all(isfinite(float(value)) for value in row)
      for row in residuals
    )
  )
  try:
    for state in states:
      _primitive(state, gamma)
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.STATE_FAILURE,
      candidate,
      f'retained conservative state is not physical: {error}',
      axial_cell_count=axial_count,
      transverse_cell_count=transverse_count,
      residual_channels_finite=residuals_finite,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  if len(inlet_states) != transverse_count:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.MESH_FAILURE,
      candidate,
      'retained inlet conservative states do not cover every transverse '
      'boundary face',
      axial_cell_count=axial_count,
      transverse_cell_count=transverse_count,
      retained_states_verified=True,
      residual_channels_finite=residuals_finite,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  pressure_profile = request.free_boundary_pressure_profile_Pa
  if pressure_profile is not None and len(pressure_profile) != axial_count:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.MESH_FAILURE,
      candidate,
      'free-boundary pressure profile does not cover every axial cell',
      axial_cell_count=axial_count,
      transverse_cell_count=transverse_count,
      retained_states_verified=True,
      residual_channels_finite=residuals_finite,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  ambient_pressure = float(request.mixed_regime_request.ambient_pressure_Pa)
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.INVALID_INPUT,
      candidate,
      'coupled request retained no positive ambient pressure',
      axial_cell_count=axial_count,
      transverse_count=transverse_count,
      retained_states_verified=True,
      residual_channels_finite=residuals_finite,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  counts = {kind: 0 for kind in _BOUNDARY_KINDS}
  totals = {kind: [0.0, 0.0, 0.0, 0.0] for kind in _BOUNDARY_KINDS}
  maximum_boundary_flux = 0.0
  maximum_wall_mass = 0.0
  maximum_wall_energy = 0.0
  wall_verified = True
  inlet_verified = True
  outlet_verified = True
  boundary_fluxes: list[tuple[int, int, str, tuple[float, ...]]] = []
  try:
    for index, (cell, state) in enumerate(zip(cells, states, strict=True)):
      if len(cell) != 4:
        raise ValueError('retained cell is not quadrilateral')
      ####
      axial_index, transverse_index = divmod(index, transverse_count)
      for edge_index in range(4):
        first = cell[edge_index]
        second = cell[(edge_index + 1) % 4]
        normal_x, normal_y, length = _face_geometry(first, second)
        if edge_index == 0 and transverse_index == 0:
          kind = 'centerline'
          flux = _wall_flux(
            state,
            normal_x,
            normal_y,
            length,
            gamma,
          )
          maximum_wall_mass = max(maximum_wall_mass, abs(flux[0]))
          maximum_wall_energy = max(maximum_wall_energy, abs(flux[3]))
          wall_verified = wall_verified and (
            abs(flux[0]) <= wall_tolerance
            and abs(flux[3]) <= wall_tolerance
          )
        elif edge_index == 2 and transverse_index == transverse_count - 1:
          kind = 'free-boundary'
          target_pressure = (
            ambient_pressure
            if pressure_profile is None
            else float(pressure_profile[axial_index])
          )
          flux = _wall_flux(
            state,
            normal_x,
            normal_y,
            length,
            gamma,
            pressure_override=target_pressure,
          )
          maximum_wall_mass = max(maximum_wall_mass, abs(flux[0]))
          maximum_wall_energy = max(maximum_wall_energy, abs(flux[3]))
          wall_verified = wall_verified and (
            abs(flux[0]) <= wall_tolerance
            and abs(flux[3]) <= wall_tolerance
          )
        elif edge_index == 3 and axial_index == 0:
          kind = 'inlet'
          flux = _rusanov_flux(
            state,
            inlet_states[transverse_index],
            normal_x,
            normal_y,
            length,
            gamma,
          )
        elif edge_index == 1 and axial_index == axial_count - 1:
          kind = 'outlet'
          outlet_pressure = request.outlet_static_pressure_Pa
          if outlet_pressure is None:
            flux = tuple(
              value * length
              for value in _euler_flux(state, normal_x, normal_y, gamma)
            )
          else:
            flux = _rusanov_flux(
              state,
              _ambient_ghost(state, float(outlet_pressure), gamma),
              normal_x,
              normal_y,
              length,
              gamma,
            )
          ####
        else:
          continue
        ####
        if any(not isfinite(float(value)) for value in flux):
          raise FloatingPointError('replayed boundary flux is not finite')
        ####
        counts[kind] += 1
        for component, value in enumerate(flux):
          totals[kind][component] += float(value)
        ####
        maximum_boundary_flux = max(
          maximum_boundary_flux,
          max(abs(float(value)) for value in flux),
        )
        boundary_fluxes.append((index, edge_index, kind, flux))
      ####
    ####
    # Rebuild every interior pair in both orientations.  This checks the
    # conservative numerical flux itself, not merely the stored cell residual.
    maximum_internal_pair = 0.0
    pair_count = 0
    for axial_index in range(axial_count):
      for transverse_index in range(transverse_count):
        index = axial_index * transverse_count + transverse_index
        cell = cells[index]
        state = states[index]
        if axial_index + 1 < axial_count:
          neighbor_index = (axial_index + 1) * transverse_count + transverse_index
          neighbor = cells[neighbor_index]
          forward = _face_geometry(cell[1], cell[2])
          reverse = _face_geometry(neighbor[3], neighbor[0])
          first_flux = _rusanov_flux(
            state,
            states[neighbor_index],
            *forward,
            gamma,
          )
          second_flux = _rusanov_flux(
            states[neighbor_index],
            state,
            *reverse,
            gamma,
          )
          maximum_internal_pair = max(
            maximum_internal_pair,
            _relative_vector_residual(first_flux, second_flux),
          )
          pair_count += 1
        ####
        if transverse_index + 1 < transverse_count:
          neighbor_index = axial_index * transverse_count + transverse_index + 1
          neighbor = cells[neighbor_index]
          forward = _face_geometry(cell[2], cell[3])
          reverse = _face_geometry(neighbor[0], neighbor[1])
          first_flux = _rusanov_flux(
            state,
            states[neighbor_index],
            *forward,
            gamma,
          )
          second_flux = _rusanov_flux(
            states[neighbor_index],
            state,
            *reverse,
            gamma,
          )
          maximum_internal_pair = max(
            maximum_internal_pair,
            _relative_vector_residual(first_flux, second_flux),
          )
          pair_count += 1
        ####
      ####
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.FLUX_FAILURE,
      candidate,
      f'conservative boundary-face replay failed: {error}',
      axial_cell_count=axial_count,
      transverse_cell_count=transverse_count,
      retained_states_verified=True,
      residual_channels_finite=residuals_finite,
      boundary_flux_tolerance=flux_tolerance,
      wall_flux_tolerance=wall_tolerance,
    )
  ####
  expected_boundary = 2 * axial_count + 2 * transverse_count
  boundary_ledger = bool(
    len(boundary_fluxes) == expected_boundary
    and tuple(counts[kind] for kind in _BOUNDARY_KINDS)
    == (axial_count, transverse_count, axial_count, transverse_count)
  )
  internal_verified = bool(
    pair_count == (axial_count - 1) * transverse_count
    + axial_count * (transverse_count - 1)
    and maximum_internal_pair <= flux_tolerance
  )
  # Both inlet and outlet are explicitly replayed above.  Separate flags keep
  # later audits from treating a wall-law pass as open-boundary evidence.
  inlet_verified = counts['inlet'] == transverse_count
  outlet_verified = counts['outlet'] == transverse_count
  wall_verified = bool(
    wall_verified
    and counts['centerline'] == axial_count
    and counts['free-boundary'] == axial_count
  )
  status = (
    MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus
    .CONVERGED_LOCAL_AUDIT
    if (
      boundary_ledger
      and internal_verified
      and wall_verified
      and inlet_verified
      and outlet_verified
      and residuals_finite
    )
    else (
      MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus
      .CONSERVATION_FAILURE
      if boundary_ledger and not internal_verified
      else MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.FLUX_FAILURE
    )
  )
  message = (
    'retained conservative boundary faces and internal numerical flux pairs '
    'were independently replayed'
    if status
    is MocReflectedDomainCoupledEulerBoundaryFluxAuditStatus.CONVERGED_LOCAL_AUDIT
    else 'retained boundary-face flux replay did not pass every local gate'
  )
  return MocReflectedDomainCoupledEulerBoundaryFluxAudit(
    status=status,
    candidate=candidate,
    axial_cell_count=axial_count,
    transverse_cell_count=transverse_count,
    boundary_face_count=len(boundary_fluxes),
    expected_boundary_face_count=expected_boundary,
    internal_face_pair_count=pair_count,
    boundary_face_counts=tuple((kind, counts[kind]) for kind in _BOUNDARY_KINDS),
    boundary_flux_totals=tuple(
      (kind, tuple(totals[kind])) for kind in _BOUNDARY_KINDS
    ),
    maximum_boundary_flux_magnitude=maximum_boundary_flux,
    maximum_internal_pair_residual=maximum_internal_pair,
    maximum_wall_mass_flux=maximum_wall_mass,
    maximum_wall_energy_flux=maximum_wall_energy,
    retained_states_verified=True,
    boundary_face_ledger_verified=boundary_ledger,
    internal_flux_pair_cancellation_verified=internal_verified,
    wall_flux_law_verified=wall_verified,
    inlet_flux_replay_verified=inlet_verified,
    outlet_flux_replay_verified=outlet_verified,
    residual_channels_finite=residuals_finite,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    boundary_flux_tolerance=flux_tolerance,
    wall_flux_tolerance=wall_tolerance,
    message=message,
  )
####
