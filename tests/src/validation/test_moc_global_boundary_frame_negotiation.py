"""Tests for the solver-owned global boundary-frame negotiation contract."""

import pytest

from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_global_boundary_frame_negotiation import (
  MocReflectedDomainGlobalBoundaryFrameNegotiationRequest,
  MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
  negotiate_reflected_domain_global_boundary_frame,
)


SOURCE = 'a' * 64
PROPOSAL = 'b' * 64


def _request(
  requested: tuple[float, ...],
  *,
  maximum_extension_m: float = 0.5,
  target_source: str = SOURCE,
  proposal_source: str = PROPOSAL,
):
  target = MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=(0.0, 1.0, 2.0),
    static_pressure_Pa=(100000.0, 99000.0, 98000.0),
    source_id='frame-test-target',
    source_closure_fingerprint=target_source,
    source_proposal_fingerprint=proposal_source,
  )
  return MocReflectedDomainGlobalBoundaryFrameNegotiationRequest(
    source_closure_fingerprint=SOURCE,
    source_proposal_fingerprint=PROPOSAL,
    available_target=target,
    requested_x_stations_m=requested,
    maximum_extension_m=maximum_extension_m,
    consumer_id='frame-test',
  )
####


def test_frame_negotiation_accepts_covered_solver_frame():
  result = negotiate_reflected_domain_global_boundary_frame(
    _request((0.25, 1.25, 1.9))
  )

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.COVERED_SOLVER_FRAME
  )
  assert result.frame_covered
  assert result.converged
  assert result.frame_coverage_verified
  assert result.extension_required is False
  assert result.maximum_required_extension_m == pytest.approx(0.0)
  assert result.extrapolation_blocked
  assert result.endpoint_hold_blocked
  assert result.geometry_injection_blocked
  assert result.physical_closure_verified is False
  assert result.production_claim_allowed is False
####


def test_frame_negotiation_retains_exact_solver_extension_request():
  result = negotiate_reflected_domain_global_boundary_frame(
    _request((0.0, 1.0, 2.25))
  )

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
    .FRAME_EXTENSION_REQUIRED
  )
  assert result.frame_covered is False
  assert result.extension_required
  assert result.lineage_verified
  assert result.frame_request_verified
  assert result.extension_budget_verified
  assert result.solver_owned_extension_required
  assert result.available_x_interval_m == (0.0, 2.0)
  assert result.requested_x_interval_m == (0.0, 2.25)
  assert result.extension_lower_m == pytest.approx(0.0)
  assert result.extension_upper_m == pytest.approx(0.25)
  assert result.maximum_required_extension_m == pytest.approx(0.25)
  assert 'no pressure extrapolation' in result.message
  assert result.as_report()['claim_status'].startswith('research-only-')
####


def test_frame_negotiation_rejects_extension_beyond_budget():
  result = negotiate_reflected_domain_global_boundary_frame(
    _request((0.0, 1.0, 2.25), maximum_extension_m=0.1)
  )

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
    .EXTENSION_BUDGET_FAILURE
  )
  assert result.frame_covered is False
  assert result.extension_required is False
  assert result.lineage_verified
  assert result.frame_request_verified
  assert result.extension_budget_verified is False
  assert result.solver_owned_extension_required
####


def test_frame_negotiation_rejects_mismatched_target_lineage():
  result = negotiate_reflected_domain_global_boundary_frame(
    _request((0.25, 1.25, 1.9), target_source='c' * 64)
  )

  assert result.status is (
    MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.LINEAGE_FAILURE
  )
  assert result.lineage_verified is False
  assert result.frame_request_verified
  assert result.frame_covered is False
####


def test_frame_negotiation_requires_ordered_requested_stations():
  with pytest.raises(ValueError, match='strictly increasing'):
    _request((0.0, 1.0, 0.5))
  ####
####
