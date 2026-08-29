"""Bounded entropy transport binding for the mixed-regime research lane.

The shock-interface entropy handoff supplies an ordered total-pressure
profile, while the existing mixed-regime solvers supply scalar reference
fields.  This module binds those two objects only when a caller supplies an
explicit source assignment for every scalar-field node.  The assignment is a
solver-owned Cauchy/streamline seam: it is not inferred from geometry and it
does not claim that the scalar reference has solved the Euler entropy
transport equation.

Keeping the source assignment explicit is important for the continued-cell
boundary.  A downstream field may not silently reset total pressure to the
terminal value, borrow a value outside the solved shock interface, or turn a
scalar subsonic mesh into a characteristic-state field.  This result remains
research-only until the assignment is replaced by a coupled reflected
shock/ambient/free-boundary solve.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, log
from typing import Any, Sequence

from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeFieldResult,
  MocMixedRegimePerimeterRequest,
)
from exhaust_plume.models.moc.mixed_regime_entropy import (
  MocMixedRegimeEntropyHandoffResult,
)

__all__ = (
  'MocMixedRegimeEntropyTransportStatus',
  'MocMixedRegimeEntropyTransportResult',
  'solve_mixed_regime_entropy_transport_boundary',
)


class MocMixedRegimeEntropyTransportStatus(str, Enum):
  """Outcome of binding entropy data to a scalar downstream field."""

  CONVERGED_REFERENCE = (
    'converged-mixed-regime-entropy-transport-boundary-reference'
  )
  INVALID_INPUT = 'invalid_input'
  HANDOFF_FAILURE = 'entropy-transport-handoff-failure'
  FIELD_FAILURE = 'entropy-transport-field-failure'
  MAPPING_FAILURE = 'entropy-transport-mapping-failure'
  RESIDUAL_FAILURE = 'entropy-transport-residual-failure'


@dataclass(frozen=True, slots=True)
class MocMixedRegimeEntropyTransportResult:
  """Auditable entropy assignment for one explicit scalar field.

  ``streamline_source_arc_length_m`` has one value for every retained field
  node.  Nodes sharing a ``streamline_id`` must carry the same source arc
  length, so the assignment represents entropy transported along an explicit
  streamline group rather than an arbitrary node-wise pressure overwrite.

  ``entropy_transport_verified`` therefore means that this bounded source
  assignment reproduces the field's total-pressure samples.  It does not
  mean that a coupled subsonic Euler solve or the canonical reflected free
  boundary has been completed.
  """

  status: MocMixedRegimeEntropyTransportStatus
  request: MocMixedRegimePerimeterRequest | None
  handoff: MocMixedRegimeEntropyHandoffResult | None
  field: MocMixedRegimeFieldResult | None
  streamline_source_arc_length_m: tuple[float, ...] = ()
  streamline_ids: tuple[int, ...] = ()
  transported_total_pressure_Pa: tuple[float, ...] = ()
  terminal_node_index: int | None = None
  maximum_total_pressure_residual_Pa: float | None = None
  maximum_entropy_coordinate_residual: float | None = None
  field_boundary_verified: bool = False
  source_profile_verified: bool = False
  streamline_assignment_verified: bool = False
  terminal_seam_verified: bool = False
  entropy_transport_verified: bool = False
  model: str = 'solver-owned-mixed-regime-entropy-transport-boundary'
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedRegimeEntropyTransportStatus):
      raise TypeError(
        'status must be a MocMixedRegimeEntropyTransportStatus'
      )
    if self.request is not None and not isinstance(
      self.request,
      MocMixedRegimePerimeterRequest,
    ):
      raise TypeError(
        'request must be a MocMixedRegimePerimeterRequest or None'
      )
    if self.handoff is not None and not isinstance(
      self.handoff,
      MocMixedRegimeEntropyHandoffResult,
    ):
      raise TypeError(
        'handoff must be a MocMixedRegimeEntropyHandoffResult or None'
      )
    if self.field is not None and not isinstance(
      self.field,
      MocMixedRegimeFieldResult,
    ):
      raise TypeError(
        'field must be a MocMixedRegimeFieldResult or None'
      )
    try:
      source_arc = tuple(float(value) for value in self.streamline_source_arc_length_m)
      streamline_ids = tuple(self.streamline_ids)
      transported = tuple(
        float(value) for value in self.transported_total_pressure_Pa
      )
    except (TypeError, ValueError) as error:
      raise ValueError(
        'entropy transport samples must contain numeric values'
      ) from error
    if any(not isfinite(value) or value < 0.0 for value in source_arc):
      raise ValueError(
        'streamline_source_arc_length_m must contain finite nonnegative values'
      )
    if any(
      isinstance(identifier, bool)
      or not isinstance(identifier, int)
      or identifier < 0
      for identifier in streamline_ids
    ):
      raise ValueError(
        'streamline_ids must contain nonnegative integer identifiers'
      )
    if any(not isfinite(value) or value <= 0.0 for value in transported):
      raise ValueError(
        'transported_total_pressure_Pa must contain finite positive values'
      )
    if self.field is not None:
      node_count = self.field.node_count
      for name, values in (
        ('streamline_source_arc_length_m', source_arc),
        ('streamline_ids', streamline_ids),
        ('transported_total_pressure_Pa', transported),
      ):
        if values and len(values) != node_count:
          raise ValueError(
            f'{name} must match the mixed-regime field node count'
          )
    if self.terminal_node_index is not None:
      if (
        isinstance(self.terminal_node_index, bool)
        or not isinstance(self.terminal_node_index, int)
        or self.terminal_node_index < 0
        or (
          self.field is not None
          and self.terminal_node_index >= self.field.node_count
        )
      ):
        raise ValueError('terminal_node_index must identify a field node')
    for name in (
      'maximum_total_pressure_residual_Pa',
      'maximum_entropy_coordinate_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        object.__setattr__(self, name, numeric)
    for name in (
      'field_boundary_verified',
      'source_profile_verified',
      'streamline_assignment_verified',
      'terminal_seam_verified',
      'entropy_transport_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'streamline_source_arc_length_m', source_arc)
    object.__setattr__(self, 'streamline_ids', streamline_ids)
    object.__setattr__(self, 'transported_total_pressure_Pa', transported)
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeEntropyTransportStatus.CONVERGED_REFERENCE
  ####

  @property
  def node_count(self) -> int:
    return 0 if self.field is None else self.field.node_count
  ####

  @property
  def streamline_count(self) -> int:
    return len(set(self.streamline_ids))
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """An explicit entropy assignment is not canonical field closure."""

    return False
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
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

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'model': self.model,
      'node_count': self.node_count,
      'streamline_count': self.streamline_count,
      'terminal_node_index': self.terminal_node_index,
      'streamline_source_arc_length_m': self.streamline_source_arc_length_m,
      'streamline_ids': self.streamline_ids,
      'transported_total_pressure_Pa': self.transported_total_pressure_Pa,
      'maximum_total_pressure_residual_Pa': (
        self.maximum_total_pressure_residual_Pa
      ),
      'maximum_entropy_coordinate_residual': (
        self.maximum_entropy_coordinate_residual
      ),
      'field_boundary_verified': self.field_boundary_verified,
      'source_profile_verified': self.source_profile_verified,
      'streamline_assignment_verified': self.streamline_assignment_verified,
      'terminal_seam_verified': self.terminal_seam_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request_terminal_point_m': (
        None if self.request is None else self.request.terminal_point_m
      ),
      'handoff': None if self.handoff is None else self.handoff.as_report(),
      'field': None if self.field is None else self.field.as_report(),
      'message': self.message,
    }
  ####


def _failure(
  status: MocMixedRegimeEntropyTransportStatus,
  *,
  request: MocMixedRegimePerimeterRequest | None = None,
  handoff: MocMixedRegimeEntropyHandoffResult | None = None,
  field: MocMixedRegimeFieldResult | None = None,
  streamline_source_arc_length_m: Sequence[float] = (),
  streamline_ids: Sequence[int] = (),
  transported_total_pressure_Pa: Sequence[float] = (),
  terminal_node_index: int | None = None,
  field_boundary_verified: bool = False,
  source_profile_verified: bool = False,
  streamline_assignment_verified: bool = False,
  terminal_seam_verified: bool = False,
  maximum_total_pressure_residual_Pa: float | None = None,
  maximum_entropy_coordinate_residual: float | None = None,
  message: str,
) -> MocMixedRegimeEntropyTransportResult:
  return MocMixedRegimeEntropyTransportResult(
    status=status,
    request=request,
    handoff=handoff,
    field=field,
    streamline_source_arc_length_m=tuple(streamline_source_arc_length_m),
    streamline_ids=tuple(streamline_ids),
    transported_total_pressure_Pa=tuple(transported_total_pressure_Pa),
    terminal_node_index=terminal_node_index,
    maximum_total_pressure_residual_Pa=maximum_total_pressure_residual_Pa,
    maximum_entropy_coordinate_residual=maximum_entropy_coordinate_residual,
    field_boundary_verified=field_boundary_verified,
    source_profile_verified=source_profile_verified,
    streamline_assignment_verified=streamline_assignment_verified,
    terminal_seam_verified=terminal_seam_verified,
    message=message,
  )


def solve_mixed_regime_entropy_transport_boundary(
  request: MocMixedRegimePerimeterRequest,
  handoff: MocMixedRegimeEntropyHandoffResult,
  field: MocMixedRegimeFieldResult,
  streamline_source_arc_length_m: Sequence[float],
  streamline_ids: Sequence[int],
  *,
  position_tolerance_m: float = 1.0e-10,
  source_arc_length_tolerance_m: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeEntropyTransportResult:
  """Bind a declared entropy source assignment to a scalar field.

  The caller supplies one source arc coordinate and streamline identifier per
  field node.  The solver interpolates only inside the already solved shock
  interface and compares that carried pressure with the field's retained
  total pressure.  No state, streamline, perimeter, or free-boundary point is
  inferred by this function.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _failure(
      MocMixedRegimeEntropyTransportStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if not isinstance(handoff, MocMixedRegimeEntropyHandoffResult):
    return _failure(
      MocMixedRegimeEntropyTransportStatus.INVALID_INPUT,
      request=request,
      message='handoff must be a MocMixedRegimeEntropyHandoffResult',
    )
  if not isinstance(field, MocMixedRegimeFieldResult):
    return _failure(
      MocMixedRegimeEntropyTransportStatus.INVALID_INPUT,
      request=request,
      handoff=handoff,
      message='field must be a MocMixedRegimeFieldResult',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('source_arc_length_tolerance_m', source_arc_length_tolerance_m),
    ('pressure_tolerance', pressure_tolerance),
  ):
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  position_tolerance_m = float(position_tolerance_m)
  source_arc_length_tolerance_m = float(source_arc_length_tolerance_m)
  pressure_tolerance = float(pressure_tolerance)
  if handoff.request != request:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.HANDOFF_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      message='entropy handoff must retain the exact mixed-regime request',
    )
  if not handoff.converged or not handoff.entropy_transport_verified:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.HANDOFF_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      message=(
        'entropy transport requires a converged shock-interface handoff: '
        f'{handoff.message}'
      ),
    )
  if not field.converged:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.FIELD_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      message='entropy transport requires a converged scalar mixed-regime field',
    )
  boundary = field.boundary
  field_boundary_verified = bool(
    boundary.converged
    and boundary.terminal == request.terminal
    and boundary.supersonic_patch == request.supersonic_patch
    and len(field.nodes) > 0
    and all(
      len(sample.point_m) == 2
      and all(isfinite(value) for value in sample.point_m)
      for sample in field.nodes
    )
  )
  if not field_boundary_verified:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.FIELD_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      message=(
        'entropy transport field must retain the exact terminal/patch seam '
        'and finite scalar nodes'
      ),
    )
  try:
    source_arc = tuple(
      float(value) for value in streamline_source_arc_length_m
    )
    identifiers = tuple(streamline_ids)
  except (TypeError, ValueError) as error:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      message=f'entropy transport mapping is not numeric: {error}',
    )
  if len(source_arc) != field.node_count or len(identifiers) != field.node_count:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      streamline_source_arc_length_m=source_arc,
      streamline_ids=identifiers,
      message=(
        'entropy transport requires one source arc coordinate and streamline '
        f'identifier per field node (expected {field.node_count})'
      ),
    )
  if any(
    not isfinite(value) for value in source_arc
  ) or any(
    isinstance(identifier, bool)
    or not isinstance(identifier, int)
    or identifier < 0
    for identifier in identifiers
  ):
    return _failure(
      MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      streamline_source_arc_length_m=source_arc,
      streamline_ids=identifiers,
      message=(
        'entropy transport mapping requires finite arc coordinates and '
        'nonnegative integer streamline identifiers'
      ),
    )
  arc = handoff.cumulative_arc_length_m
  if len(arc) < 2:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.HANDOFF_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      streamline_source_arc_length_m=source_arc,
      streamline_ids=identifiers,
      message='entropy handoff does not expose a usable arc-length interval',
    )
  if any(
    coordinate < arc[0] - source_arc_length_tolerance_m
    or coordinate > arc[-1] + source_arc_length_tolerance_m
    for coordinate in source_arc
  ):
    return _failure(
      MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      streamline_source_arc_length_m=source_arc,
      streamline_ids=identifiers,
      field_boundary_verified=field_boundary_verified,
      message=(
        'entropy source assignment lies outside the solved shock-interface '
        'arc; extrapolation is disabled'
      ),
    )
  group_coordinates: dict[int, list[float]] = {}
  for identifier, coordinate in zip(identifiers, source_arc, strict=True):
    group_coordinates.setdefault(identifier, []).append(coordinate)
  streamline_assignment_verified = bool(
    group_coordinates
    and all(
      len(coordinates) >= 2
      and max(coordinates) - min(coordinates)
      <= source_arc_length_tolerance_m
      for coordinates in group_coordinates.values()
    )
  )
  if not streamline_assignment_verified:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.MAPPING_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      streamline_source_arc_length_m=source_arc,
      streamline_ids=identifiers,
      field_boundary_verified=field_boundary_verified,
      source_profile_verified=True,
      message=(
        'each explicit streamline group must contain at least two nodes with '
        'one common shock-interface source coordinate'
      ),
    )
  transported: list[float] = []
  pressure_residuals: list[float] = []
  entropy_residuals: list[float] = []
  try:
    for coordinate, sample in zip(source_arc, field.nodes, strict=True):
      carried_pressure = handoff.total_pressure_at_arc_length(coordinate)
      transported.append(carried_pressure)
      residual = abs(sample.total_pressure_Pa - carried_pressure)
      pressure_residuals.append(residual)
      entropy_residuals.append(
        abs(log(carried_pressure / sample.total_pressure_Pa))
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocMixedRegimeEntropyTransportStatus.HANDOFF_FAILURE,
      request=request,
      handoff=handoff,
      field=field,
      streamline_source_arc_length_m=source_arc,
      streamline_ids=identifiers,
      field_boundary_verified=field_boundary_verified,
      source_profile_verified=True,
      streamline_assignment_verified=streamline_assignment_verified,
      message=f'could not interpolate the carried entropy profile: {error}',
    )
  terminal_index = next(
    (
      index
      for index, sample in enumerate(field.nodes)
      if abs(sample.point_m[0] - request.terminal_point_m[0])
      <= position_tolerance_m
      and abs(sample.point_m[1] - request.terminal_point_m[1])
      <= position_tolerance_m
    ),
    None,
  )
  terminal_arc = arc[handoff.terminal_sample_index] if handoff.terminal_sample_index is not None else None
  terminal_seam_verified = bool(
    terminal_index is not None
    and terminal_arc is not None
    and abs(source_arc[terminal_index] - terminal_arc)
    <= source_arc_length_tolerance_m
    and abs(
      field.nodes[terminal_index].total_pressure_Pa
      - request.terminal_downstream_total_pressure_Pa
    )
    <= pressure_tolerance
    * max(1.0, abs(request.terminal_downstream_total_pressure_Pa))
  )
  maximum_pressure_residual = max(pressure_residuals, default=None)
  maximum_entropy_residual = max(entropy_residuals, default=None)
  pressure_verified = all(
    residual <= pressure_tolerance * max(1.0, abs(sample.total_pressure_Pa), abs(carried))
    for residual, sample, carried in zip(
      pressure_residuals,
      field.nodes,
      transported,
      strict=True,
    )
  )
  entropy_transport_verified = bool(
    pressure_verified
    and terminal_seam_verified
    and streamline_assignment_verified
  )
  status = (
    MocMixedRegimeEntropyTransportStatus.CONVERGED_REFERENCE
    if entropy_transport_verified
    else MocMixedRegimeEntropyTransportStatus.RESIDUAL_FAILURE
  )
  return MocMixedRegimeEntropyTransportResult(
    status=status,
    request=request,
    handoff=handoff,
    field=field,
    streamline_source_arc_length_m=source_arc,
    streamline_ids=identifiers,
    transported_total_pressure_Pa=tuple(transported),
    terminal_node_index=terminal_index,
    maximum_total_pressure_residual_Pa=maximum_pressure_residual,
    maximum_entropy_coordinate_residual=maximum_entropy_residual,
    field_boundary_verified=field_boundary_verified,
    source_profile_verified=True,
    streamline_assignment_verified=streamline_assignment_verified,
    terminal_seam_verified=terminal_seam_verified,
    entropy_transport_verified=entropy_transport_verified,
    message=(
      'explicit streamline-source entropy assignment reproduced the scalar '
      'field total-pressure samples; canonical Euler/free-boundary closure '
      'remains separate'
      if entropy_transport_verified
      else 'explicit entropy assignment did not reproduce the field pressure '
      'lineage'
    ),
  )
