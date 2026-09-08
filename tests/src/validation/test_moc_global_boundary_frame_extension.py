from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_global_boundary_frame_extension import (
  MocReflectedDomainGlobalBoundaryFrameExtensionRequest,
  MocReflectedDomainGlobalBoundaryFrameExtensionStatus,
  extend_reflected_domain_global_boundary_frame,
)
from exhaust_plume.validation.moc_global_boundary_frame_negotiation import (
  MocReflectedDomainGlobalBoundaryFrameNegotiationRequest,
  MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
  MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
)


SOURCE_CLOSURE = 'a' * 64
SOURCE_PROPOSAL = 'b' * 64


def _target(*, terminal_pressure: float = 100.0):
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=(1.0, 2.0),
    static_pressure_Pa=(100.0, terminal_pressure),
    source_id='solver-owned-base',
    source_closure_fingerprint=SOURCE_CLOSURE,
    source_proposal_fingerprint=SOURCE_PROPOSAL,
  )
####


def _negotiation(
  *,
  status: MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
  requested: tuple[float, ...],
  upper_extension: float = 0.0,
  lower_extension: float = 0.0,
  covered: bool = False,
):
  available = _target()
  request = MocReflectedDomainGlobalBoundaryFrameNegotiationRequest(
    source_closure_fingerprint=SOURCE_CLOSURE,
    source_proposal_fingerprint=SOURCE_PROPOSAL,
    available_target=available,
    requested_x_stations_m=requested,
    maximum_extension_m=1.0,
    consumer_id='test-frame-extension',
  )
  return MocReflectedDomainGlobalBoundaryFrameNegotiationResult(
    status=status,
    request=request,
    source_closure_fingerprint=SOURCE_CLOSURE,
    source_proposal_fingerprint=SOURCE_PROPOSAL,
    available_x_interval_m=(1.0, 2.0),
    requested_x_interval_m=(requested[0], requested[-1]),
    extension_lower_m=lower_extension,
    extension_upper_m=upper_extension,
    maximum_required_extension_m=max(lower_extension, upper_extension),
    lineage_verified=True,
    frame_request_verified=True,
    frame_coverage_verified=covered,
    extension_budget_verified=True,
    solver_owned_extension_required=not covered,
    configuration={},
  )
####


def _request(
  negotiation: MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
  *,
  target=None,
):
  return MocReflectedDomainGlobalBoundaryFrameExtensionRequest(
    source_closure_fingerprint=SOURCE_CLOSURE,
    source_proposal_fingerprint=SOURCE_PROPOSAL,
    frame_negotiation=negotiation,
    base_target=_target() if target is None else target,
    ambient_pressure_Pa=100.0,
    consumer_id='test-ambient-extension',
  )
####


def test_solver_owned_ambient_law_generates_exact_requested_extension():
  negotiation = _negotiation(
    status=(
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .FRAME_EXTENSION_REQUIRED
    ),
    requested=(1.0, 2.2),
    upper_extension=0.2,
  )
  result = extend_reflected_domain_global_boundary_frame(_request(negotiation))

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameExtensionStatus.EXTENSION_GENERATED
  )
  assert result.converged
  assert result.extension_generated
  assert result.extension_x_stations_m == (2.2,)
  assert result.generated_pressure_Pa == (100.0,)
  assert result.extended_target is not None
  assert result.extended_target.x_stations_m == (1.0, 2.0, 2.2)
  assert result.extended_target.boundary_points_m == ()
  assert result.geometry_injection_blocked
  assert result.extrapolation_blocked
  assert result.endpoint_hold_blocked
####


def test_covered_frame_does_not_generate_an_extension():
  negotiation = _negotiation(
    status=(
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .COVERED_SOLVER_FRAME
    ),
    requested=(1.0, 2.0),
    covered=True,
  )
  result = extend_reflected_domain_global_boundary_frame(_request(negotiation))

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameExtensionStatus.NO_EXTENSION_REQUIRED
  )
  assert result.converged
  assert result.extension_generated is False
  assert result.extended_target == _target()
####


def test_extension_rejects_non_ambient_terminal_pressure():
  negotiation = _negotiation(
    status=(
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .FRAME_EXTENSION_REQUIRED
    ),
    requested=(1.0, 2.2),
    upper_extension=0.2,
  )
  result = extend_reflected_domain_global_boundary_frame(
    _request(negotiation, target=_target(terminal_pressure=102.0))
  )

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE
  )
  assert result.converged is False
  assert result.extended_target is None
####


def test_extension_rejects_lower_frame_request():
  negotiation = _negotiation(
    status=(
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .FRAME_EXTENSION_REQUIRED
    ),
    requested=(0.9, 2.2),
    lower_extension=0.1,
    upper_extension=0.2,
  )
  result = extend_reflected_domain_global_boundary_frame(_request(negotiation))

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE
  )
  assert 'lower-frame' in result.message
####

