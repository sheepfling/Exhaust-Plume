"""Explicit planar downstream handoff for the mixed-regime MOC lane.

The terminal shock provides a scalar subsonic point and an open supersonic
patch.  It does not provide the downstream control section or the remaining
perimeter.  This module defines the callback boundary for a future planar
mixed-regime solver: callers must provide both pieces of geometry, and the
callback must return a field that retains the exact terminal seam and named
perimeter condition.

This is intentionally an adapter, not a new physical solver.  A successful
handoff is useful evidence for planner and visualization work, but remains
non-promotable until a real downstream 2-D field and canonical free-boundary
validation exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Callable

from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeClosureStatus,
  MocMixedRegimeControlSection,
  MocMixedRegimeControlSectionResult,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFieldResult,
  MocMixedRegimePerimeterRequest,
  validate_mixed_regime_control_section,
)

__all__ = (
  'MocMixedRegimePlanarFieldSolver',
  'MocMixedRegimePlanarSolveStatus',
  'MocMixedRegimePlanarSolveResult',
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
    message=message,
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
