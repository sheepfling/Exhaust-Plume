"""Bounded attachment of a scalar transonic branch to an upstream MOC field.

The scalar normal-shock branch contains a conservative upstream/downstream
state but no placement.  This module lets a solver-owned characteristic field
select a retained node whose Mach number, flow direction, and pressure lineage
match that branch.  The selected node is then bound to the scalar shock
geometry.  The operation is a local attachment probe only: it does not solve
the upstream field, move the free boundary, or promote a shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, cos, isfinite, sin
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryResult,
  MocTransonicShockState,
  measure_moc_transonic_shock_geometry,
  solve_moc_transonic_shock_geometry,
)

__all__ = (
  'MocTransonicShockFieldAttachmentStatus',
  'MocTransonicShockFieldAttachmentRequest',
  'MocTransonicShockFieldAttachmentResult',
  'solve_moc_transonic_shock_field_attachment',
)


class MocTransonicShockFieldAttachmentStatus(str, Enum):
  """Outcome of a bounded scalar-branch attachment probe."""

  CONVERGED_BOUNDED_ATTACHMENT = (
    'converged-bounded-transonic-shock-field-attachment'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_REQUIRED = 'transonic-attachment-field-required'
  NO_ADMISSIBLE_FIELD_MATCH = 'transonic-attachment-no-admissible-field-match'
  GEOMETRY_FAILURE = 'transonic-attachment-geometry-failure'
####


def _wrapped_angle_residual(first_angle_rad: float, second_angle_rad: float) -> float:
  """Return the smallest absolute angular difference in radians."""

  return abs(atan2(
    sin(first_angle_rad - second_angle_rad),
    cos(first_angle_rad - second_angle_rad),
  ))
####


def _relative_residual(actual: float, expected: float) -> float:
  """Return a finite scale-free residual for positive pressure quantities."""

  return abs(actual - expected) / max(1.0, abs(actual), abs(expected))
####


def _static_pressure(
  total_pressure_Pa: float,
  state: CharacteristicState,
) -> float:
  """Recover the isentropic static pressure carried by one MOC node."""

  return total_pressure_Pa / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockFieldAttachmentRequest:
  """Inputs for solver-owned matching of a scalar shock branch to a field."""

  upstream_field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
  shock_state: MocTransonicShockState
  state_tolerance: float = 1.0e-8
  pressure_tolerance_fraction: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(
      self.upstream_field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'upstream_field must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult'
      )
    ####
    if not isinstance(self.shock_state, MocTransonicShockState):
      raise TypeError('shock_state must be a MocTransonicShockState')
    ####
    for name in ('state_tolerance', 'pressure_tolerance_fraction'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'shock_state': self.shock_state.as_report(),
      'upstream_field_status': self.upstream_field.status.value,
      'upstream_field_node_count': self.upstream_field.node_count,
      'upstream_field_cell_count': self.upstream_field.cell_count,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance_fraction': self.pressure_tolerance_fraction,
      'model': 'research-solver-owned-transonic-field-attachment-v1',
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockFieldAttachmentResult:
  """A scalar branch matched to one retained upstream field node."""

  status: MocTransonicShockFieldAttachmentStatus
  request: MocTransonicShockFieldAttachmentRequest
  selected_node_index: int | None
  selected_point_m: tuple[float, float] | None
  sampled_upstream_state: CharacteristicState | None
  sampled_upstream_static_pressure_Pa: float | None
  sampled_upstream_total_pressure_Pa: float | None
  mach_residual: float | None
  flow_angle_residual_rad: float | None
  gamma_residual: float | None
  static_pressure_residual: float | None
  total_pressure_residual: float | None
  geometry: MocTransonicShockGeometryResult | None
  geometry_audit: MocTransonicShockGeometryAudit | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicShockFieldAttachmentStatus):
      raise TypeError(
        'status must be a MocTransonicShockFieldAttachmentStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocTransonicShockFieldAttachmentRequest,
    ):
      raise TypeError(
        'request must be a MocTransonicShockFieldAttachmentRequest'
      )
    ####
    if self.selected_node_index is not None:
      if (
        isinstance(self.selected_node_index, bool)
        or not isinstance(self.selected_node_index, int)
        or self.selected_node_index < 0
      ):
        raise ValueError('selected_node_index must be a nonnegative integer or None')
      ####
    ####
    if self.selected_point_m is not None:
      point = tuple(float(value) for value in self.selected_point_m)
      if len(point) != 2 or any(not isfinite(value) for value in point):
        raise ValueError('selected_point_m must contain two finite coordinates')
      ####
      object.__setattr__(self, 'selected_point_m', point)
    ####
    if self.sampled_upstream_state is not None and not isinstance(
      self.sampled_upstream_state,
      CharacteristicState,
    ):
      raise TypeError(
        'sampled_upstream_state must be a CharacteristicState or None'
      )
    ####
    for name in (
      'sampled_upstream_static_pressure_Pa',
      'sampled_upstream_total_pressure_Pa',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'mach_residual',
      'flow_angle_residual_rad',
      'gamma_residual',
      'static_pressure_residual',
      'total_pressure_residual',
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
    if (self.geometry is None) != (self.geometry_audit is None):
      raise ValueError('geometry and geometry_audit must be supplied together')
    ####
    if self.geometry is not None and not isinstance(
      self.geometry,
      MocTransonicShockGeometryResult,
    ):
      raise TypeError('geometry must be a MocTransonicShockGeometryResult or None')
    ####
    if self.geometry_audit is not None and not isinstance(
      self.geometry_audit,
      MocTransonicShockGeometryAudit,
    ):
      raise TypeError(
        'geometry_audit must be a MocTransonicShockGeometryAudit or None'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def attachment_verified(self) -> bool:
    """Whether the bounded upstream match and scalar geometry both passed."""

    return bool(
      self.status is MocTransonicShockFieldAttachmentStatus
      .CONVERGED_BOUNDED_ATTACHMENT
      and self.selected_node_index is not None
      and self.sampled_upstream_state is not None
      and self.geometry is not None
      and self.geometry.geometry_verified
      and self.geometry_audit is not None
      and self.geometry_audit.geometry_binding_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A local field match is not a globally closed mixed-regime solution."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the attachment probe to an explicitly non-promotable decision."""

    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocTransonicShockFieldAttachmentStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'attachment_status': self.status.value,
        'attachment_verified': self.attachment_verified,
        'selected_node_index': self.selected_node_index,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'solver-owned-mixed-regime-shock-placement-and-independent-'
          'refinement-before-continued-shock-cell-chain'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'attachment_verified': self.attachment_verified,
      'selected_node_index': self.selected_node_index,
      'selected_point_m': (
        None if self.selected_point_m is None else list(self.selected_point_m)
      ),
      'sampled_upstream_state': (
        None
        if self.sampled_upstream_state is None
        else {
          'point_m': [
            self.sampled_upstream_state.x_m,
            self.sampled_upstream_state.y_m,
          ],
          'mach': self.sampled_upstream_state.mach,
          'flow_angle_rad': self.sampled_upstream_state.theta_rad,
          'gamma': self.sampled_upstream_state.gamma,
        }
      ),
      'sampled_upstream_static_pressure_Pa': (
        self.sampled_upstream_static_pressure_Pa
      ),
      'sampled_upstream_total_pressure_Pa': (
        self.sampled_upstream_total_pressure_Pa
      ),
      'mach_residual': self.mach_residual,
      'flow_angle_residual_rad': self.flow_angle_residual_rad,
      'gamma_residual': self.gamma_residual,
      'static_pressure_residual': self.static_pressure_residual,
      'total_pressure_residual': self.total_pressure_residual,
      'geometry': None if self.geometry is None else self.geometry.as_report(),
      'geometry_audit': (
        None if self.geometry_audit is None else self.geometry_audit.as_report()
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-bounded-scalar-shock-field-attachment; global-shock-'
        'placement, mixed-regime closure, chain promotion, and external '
        'validation remain open'
      ),
      'request': self.request.as_report(),
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocTransonicShockFieldAttachmentStatus,
  request: MocTransonicShockFieldAttachmentRequest,
  *,
  selected_node_index: int | None = None,
  selected_point_m: tuple[float, float] | None = None,
  sampled_upstream_state: CharacteristicState | None = None,
  sampled_upstream_static_pressure_Pa: float | None = None,
  sampled_upstream_total_pressure_Pa: float | None = None,
  mach_residual: float | None = None,
  flow_angle_residual_rad: float | None = None,
  gamma_residual: float | None = None,
  static_pressure_residual: float | None = None,
  total_pressure_residual: float | None = None,
  message: str,
) -> MocTransonicShockFieldAttachmentResult:
  return MocTransonicShockFieldAttachmentResult(
    status=status,
    request=request,
    selected_node_index=selected_node_index,
    selected_point_m=selected_point_m,
    sampled_upstream_state=sampled_upstream_state,
    sampled_upstream_static_pressure_Pa=sampled_upstream_static_pressure_Pa,
    sampled_upstream_total_pressure_Pa=sampled_upstream_total_pressure_Pa,
    mach_residual=mach_residual,
    flow_angle_residual_rad=flow_angle_residual_rad,
    gamma_residual=gamma_residual,
    static_pressure_residual=static_pressure_residual,
    total_pressure_residual=total_pressure_residual,
    geometry=None,
    geometry_audit=None,
    message=message,
  )
####


def solve_moc_transonic_shock_field_attachment(
  request: MocTransonicShockFieldAttachmentRequest,
) -> MocTransonicShockFieldAttachmentResult:
  """Select and bind the best matching retained upstream field node.

  The selection is solver-owned and deterministic: the normalized maximum of
  Mach, flow-angle, gamma, static-pressure, and total-pressure residuals is
  minimized over retained field nodes.  No state is extrapolated or inferred
  outside the field.
  """

  if not isinstance(request, MocTransonicShockFieldAttachmentRequest):
    raise TypeError('request must be a MocTransonicShockFieldAttachmentRequest')
  ####
  field = request.upstream_field
  if not field.state_sampling_available:
    return _failure(
      MocTransonicShockFieldAttachmentStatus.FIELD_REQUIRED,
      request,
      message=(
        'transonic attachment requires a locally consistent upstream field '
        'with bounded state sampling'
      ),
    )
  ####
  shock_state = request.shock_state
  best: tuple[
    float,
    int,
    CharacteristicState,
    float,
    float,
    float,
    float,
    float,
    float,
  ] | None = None
  for node in field.nodes:
    state = node.state
    sampled_static_pressure = _static_pressure(node.total_pressure_Pa, state)
    mach_residual = _relative_residual(state.mach, shock_state.upstream_mach)
    flow_angle_residual = _wrapped_angle_residual(
      state.theta_rad,
      shock_state.upstream_flow_angle_rad,
    )
    gamma_residual = _relative_residual(state.gamma, shock_state.gamma)
    static_pressure_residual = _relative_residual(
      sampled_static_pressure,
      shock_state.upstream_static_pressure_Pa,
    )
    total_pressure_residual = _relative_residual(
      node.total_pressure_Pa,
      shock_state.upstream_total_pressure_Pa,
    )
    score = max(
      mach_residual,
      flow_angle_residual,
      gamma_residual,
      static_pressure_residual,
      total_pressure_residual,
    )
    candidate = (
      score,
      node.node_index,
      state,
      sampled_static_pressure,
      mach_residual,
      flow_angle_residual,
      gamma_residual,
      static_pressure_residual,
      total_pressure_residual,
    )
    if best is None or candidate[:2] < best[:2]:
      best = candidate
    ####
  ####
  if best is None:
    return _failure(
      MocTransonicShockFieldAttachmentStatus.NO_ADMISSIBLE_FIELD_MATCH,
      request,
      message='upstream field retained no candidate nodes for attachment',
    )
  ####
  (
    _score,
    node_index,
    state,
    sampled_static_pressure,
    mach_residual,
    flow_angle_residual,
    gamma_residual,
    static_pressure_residual,
    total_pressure_residual,
  ) = best
  if (
    mach_residual > request.state_tolerance
    or flow_angle_residual > request.state_tolerance
    or gamma_residual > request.state_tolerance
    or static_pressure_residual > request.pressure_tolerance_fraction
    or total_pressure_residual > request.pressure_tolerance_fraction
  ):
    return _failure(
      MocTransonicShockFieldAttachmentStatus.NO_ADMISSIBLE_FIELD_MATCH,
      request,
      selected_node_index=node_index,
      selected_point_m=(state.x_m, state.y_m),
      sampled_upstream_state=state,
      sampled_upstream_static_pressure_Pa=sampled_static_pressure,
      sampled_upstream_total_pressure_Pa=field.nodes[node_index].total_pressure_Pa,
      mach_residual=mach_residual,
      flow_angle_residual_rad=flow_angle_residual,
      gamma_residual=gamma_residual,
      static_pressure_residual=static_pressure_residual,
      total_pressure_residual=total_pressure_residual,
      message=(
        'no retained upstream characteristic node matches the audited scalar '
        'shock branch within the declared state and pressure tolerances'
      ),
    )
  ####
  geometry_request = MocTransonicShockGeometryRequest(
    shock_state=shock_state,
    shock_point_m=(state.x_m, state.y_m),
    shock_normal_angle_rad=shock_state.upstream_flow_angle_rad,
    normal_alignment_tolerance_rad=request.state_tolerance,
    flux_tolerance=max(request.state_tolerance, 1.0e-8),
  )
  geometry = solve_moc_transonic_shock_geometry(geometry_request)
  geometry_audit = measure_moc_transonic_shock_geometry(geometry)
  if not geometry_audit.geometry_binding_verified:
    return MocTransonicShockFieldAttachmentResult(
      status=MocTransonicShockFieldAttachmentStatus.GEOMETRY_FAILURE,
      request=request,
      selected_node_index=node_index,
      selected_point_m=(state.x_m, state.y_m),
      sampled_upstream_state=state,
      sampled_upstream_static_pressure_Pa=sampled_static_pressure,
      sampled_upstream_total_pressure_Pa=field.nodes[node_index].total_pressure_Pa,
      mach_residual=mach_residual,
      flow_angle_residual_rad=flow_angle_residual,
      gamma_residual=gamma_residual,
      static_pressure_residual=static_pressure_residual,
      total_pressure_residual=total_pressure_residual,
      geometry=geometry,
      geometry_audit=geometry_audit,
      message=(
        'solver-owned field match was found, but the scalar geometry audit '
        'did not verify'
      ),
    )
  ####
  return MocTransonicShockFieldAttachmentResult(
    status=MocTransonicShockFieldAttachmentStatus.CONVERGED_BOUNDED_ATTACHMENT,
    request=request,
    selected_node_index=node_index,
    selected_point_m=(state.x_m, state.y_m),
    sampled_upstream_state=state,
    sampled_upstream_static_pressure_Pa=sampled_static_pressure,
    sampled_upstream_total_pressure_Pa=field.nodes[node_index].total_pressure_Pa,
    mach_residual=mach_residual,
    flow_angle_residual_rad=flow_angle_residual,
    gamma_residual=gamma_residual,
    static_pressure_residual=static_pressure_residual,
    total_pressure_residual=total_pressure_residual,
    geometry=geometry,
    geometry_audit=geometry_audit,
    message=(
      'solver-owned upstream characteristic node matched the audited scalar '
      'shock branch; global shock placement and mixed-regime closure remain open'
    ),
  )
####
