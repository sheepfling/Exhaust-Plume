"""Independent audit for the global physical-field continuation handoff.

The global downstream seam is assembled from three separately audited
operators: mesh-bound interface placement, exact field continuation sampling,
and the shock-front/neighboring-boundary condition.  This module remeasures
those operators and verifies that they still refer to one immutable physical
field and one exact cross-section.  It is research evidence only; it cannot
close the downstream free boundary or authorize production claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
    MocReflectedDomainGlobalPhysicalFieldHandoff,
)
from exhaust_plume.validation.moc_field_continuation import (
    measure_moc_physical_field_continuation_profile,
)
from exhaust_plume.validation.moc_physical_field_shock_front import (
    measure_moc_physical_field_shock_front_condition,
)
from exhaust_plume.validation.moc_transonic_interface import (
    measure_moc_transonic_shock_interface_field_placement,
)

__all__ = (
    "MOC_REFLECTED_DOMAIN_GLOBAL_PHYSICAL_FIELD_HANDOFF_AUDIT_OPERATOR_ID",
    "MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus",
    "MocReflectedDomainGlobalPhysicalFieldHandoffAudit",
    "measure_moc_reflected_domain_global_physical_field_handoff",
)


MOC_REFLECTED_DOMAIN_GLOBAL_PHYSICAL_FIELD_HANDOFF_AUDIT_OPERATOR_ID = "op.moc.reflected-domain.global-physical-field-handoff-audit"


class MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus(str, Enum):
    """Outcome of the shared-field handoff audit."""

    VERIFIED = "verified-global-physical-field-handoff-audit"
    INVALID_INPUT = "invalid_input"
    COMPONENT_AUDIT_FAILURE = "global-physical-field-handoff-component-audit-failure"
    FIELD_LINEAGE_FAILURE = "global-physical-field-handoff-field-lineage-failure"
    CROSS_SECTION_LINEAGE_FAILURE = "global-physical-field-handoff-cross-section-lineage-failure"
    COUPLED_PROFILE_LINEAGE_FAILURE = "global-physical-field-handoff-coupled-profile-lineage-failure"


def _point_residual(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    return hypot(first[0] - second[0], first[1] - second[1])


def _failure(
    status: MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus,
    message: str,
    *,
    handoff: MocReflectedDomainGlobalPhysicalFieldHandoff | None = None,
    placement_audit: Any | None = None,
    continuation_audit: Any | None = None,
    shock_front_audit: Any | None = None,
    source_field_identity_verified: bool = False,
    cross_section_lineage_verified: bool = False,
    coupled_profile_lineage_verified: bool = False,
    maximum_cross_section_point_residual_m: float | None = None,
) -> MocReflectedDomainGlobalPhysicalFieldHandoffAudit:
    return MocReflectedDomainGlobalPhysicalFieldHandoffAudit(
        status=status,
        handoff=handoff,
        placement_audit=placement_audit,
        continuation_audit=continuation_audit,
        shock_front_audit=shock_front_audit,
        source_field_identity_verified=source_field_identity_verified,
        cross_section_lineage_verified=cross_section_lineage_verified,
        coupled_profile_lineage_verified=coupled_profile_lineage_verified,
        maximum_cross_section_point_residual_m=maximum_cross_section_point_residual_m,
        message=message,
    )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalPhysicalFieldHandoffAudit:
    """Second-pass evidence for one exact global physical-field handoff."""

    status: MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus
    handoff: MocReflectedDomainGlobalPhysicalFieldHandoff | None
    placement_audit: Any | None = None
    continuation_audit: Any | None = None
    shock_front_audit: Any | None = None
    source_field_identity_verified: bool = False
    cross_section_lineage_verified: bool = False
    coupled_profile_lineage_verified: bool = False
    maximum_cross_section_point_residual_m: float | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus,
        ):
            raise TypeError("status must be a typed handoff-audit status")
        if self.handoff is not None and not isinstance(
            self.handoff,
            MocReflectedDomainGlobalPhysicalFieldHandoff,
        ):
            raise TypeError("handoff must be a MocReflectedDomainGlobalPhysicalFieldHandoff or None")
        for name in (
            "source_field_identity_verified",
            "cross_section_lineage_verified",
            "coupled_profile_lineage_verified",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.maximum_cross_section_point_residual_m is not None:
            residual = float(self.maximum_cross_section_point_residual_m)
            if not isfinite(residual) or residual < 0.0:
                raise ValueError("maximum_cross_section_point_residual_m must be finite and nonnegative")
            object.__setattr__(self, "maximum_cross_section_point_residual_m", residual)
        object.__setattr__(self, "message", str(self.message))

    @property
    def converged(self) -> bool:
        return self.status is (MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.VERIFIED)

    @property
    def research_evidence_verified(self) -> bool:
        """Whether all component and shared-lineage checks passed."""

        return bool(
            self.converged
            and self.handoff is not None
            and self.placement_audit is not None
            and bool(getattr(self.placement_audit, "converged", False))
            and self.continuation_audit is not None
            and bool(getattr(self.continuation_audit, "converged", False))
            and self.shock_front_audit is not None
            and bool(getattr(self.shock_front_audit, "converged", False))
            and self.source_field_identity_verified
            and self.cross_section_lineage_verified
            and self.coupled_profile_lineage_verified
            and self.handoff.chain_promotion_blocked
            and not self.handoff.production_claim_allowed
        )

    def as_report(self) -> dict[str, Any]:
        return {
            "operator_id": (MOC_REFLECTED_DOMAIN_GLOBAL_PHYSICAL_FIELD_HANDOFF_AUDIT_OPERATOR_ID),
            "status": self.status.value,
            "converged": self.converged,
            "research_evidence_verified": self.research_evidence_verified,
            "source_field_identity_verified": self.source_field_identity_verified,
            "cross_section_lineage_verified": self.cross_section_lineage_verified,
            "coupled_profile_lineage_verified": self.coupled_profile_lineage_verified,
            "maximum_cross_section_point_residual_m": (self.maximum_cross_section_point_residual_m),
            "placement_audit": (None if self.placement_audit is None else self.placement_audit.as_report()),
            "continuation_audit": (None if self.continuation_audit is None else self.continuation_audit.as_report()),
            "shock_front_audit": (None if self.shock_front_audit is None else self.shock_front_audit.as_report()),
            "claim_status": ("research-only-shared-global-physical-field-handoff-audit; downstream free-boundary closure, refinement, external validation, and production claims remain blocked"),
            "message": self.message,
        }


def measure_moc_reflected_domain_global_physical_field_handoff(
    handoff: MocReflectedDomainGlobalPhysicalFieldHandoff,
) -> MocReflectedDomainGlobalPhysicalFieldHandoffAudit:
    """Remeasure components and shared field/section lineage."""

    if not isinstance(
        handoff,
        MocReflectedDomainGlobalPhysicalFieldHandoff,
    ):
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.INVALID_INPUT,
            "handoff must be a MocReflectedDomainGlobalPhysicalFieldHandoff",
        )
    ####
    try:
        placement_audit = measure_moc_transonic_shock_interface_field_placement(handoff.placement)
        continuation_audit = measure_moc_physical_field_continuation_profile(handoff.continuation_profile)
        shock_front_audit = measure_moc_physical_field_shock_front_condition(handoff.shock_front_condition)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.COMPONENT_AUDIT_FAILURE,
            f"global physical-field handoff component audit raised: {error}",
            handoff=handoff,
        )
    ####
    if not (placement_audit.converged and continuation_audit.converged and shock_front_audit.converged):
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.COMPONENT_AUDIT_FAILURE,
            "one or more global physical-field handoff components failed its independent audit",
            handoff=handoff,
            placement_audit=placement_audit,
            continuation_audit=continuation_audit,
            shock_front_audit=shock_front_audit,
        )
    ####
    placement_field = handoff.placement.field
    continuation_field = handoff.continuation_profile.field
    condition_field = handoff.shock_front_condition.field
    request_field = handoff.continuation_profile.request.field
    condition_request = handoff.shock_front_condition.request
    source_field_identity_verified = bool(
        placement_field is not None
        and placement_field is handoff.placement.request.field
        and placement_field is continuation_field
        and placement_field is request_field
        and placement_field is condition_field
        and placement_field is handoff.shock_front_condition.continuation_profile.field
        and handoff.shock_front_condition.continuation_profile is handoff.continuation_profile
        and condition_request.continuation_profile is handoff.continuation_profile
        and placement_field.converged
        and placement_field.physical_closure_verified
        and placement_field.state_sampling_available
    )
    if not source_field_identity_verified:
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.FIELD_LINEAGE_FAILURE,
            "global physical-field handoff components do not retain one exact source field and continuation result",
            handoff=handoff,
            placement_audit=placement_audit,
            continuation_audit=continuation_audit,
            shock_front_audit=shock_front_audit,
        )
    ####
    placement_points = tuple(handoff.placement.sample_points_m)
    continuation = handoff.continuation_profile
    profile = continuation.profile
    if profile is None:
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.CROSS_SECTION_LINEAGE_FAILURE,
            "global physical-field handoff retained no continuation profile",
            handoff=handoff,
            placement_audit=placement_audit,
            continuation_audit=continuation_audit,
            shock_front_audit=shock_front_audit,
            source_field_identity_verified=True,
        )
    ####
    continuation_points = tuple(sample.point_m for sample in profile.samples)
    point_residuals = tuple(
        _point_residual(actual, expected)
        for actual, expected in zip(
            placement_points,
            continuation_points,
            strict=False,
        )
    )
    maximum_point_residual = max(point_residuals, default=0.0)
    position_tolerance = max(
        handoff.placement.request.position_tolerance_m,
        continuation.request.position_tolerance_m,
        handoff.shock_front_condition.request.position_tolerance_m,
    )
    cross_section_lineage_verified = bool(
        len(placement_points) == len(continuation_points) >= 2
        and maximum_point_residual <= position_tolerance
        and continuation.request.sample_points_m == continuation_points
        and abs(handoff.placement.cross_section_x_m - profile.cross_section_x_m) <= position_tolerance
        and handoff.placement.lower_ordinate_m is not None
        and handoff.placement.upper_ordinate_m is not None
        and abs(handoff.placement.lower_ordinate_m - profile.lower_ordinate_m) <= position_tolerance
        and abs(handoff.placement.upper_ordinate_m - profile.upper_ordinate_m) <= position_tolerance
    )
    if not cross_section_lineage_verified:
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.CROSS_SECTION_LINEAGE_FAILURE,
            "placement and continuation do not retain the exact same cross-section points and bounds",
            handoff=handoff,
            placement_audit=placement_audit,
            continuation_audit=continuation_audit,
            shock_front_audit=shock_front_audit,
            source_field_identity_verified=True,
            maximum_cross_section_point_residual_m=maximum_point_residual,
        )
    ####
    coupled_profile = handoff.shock_front_condition.coupled_inlet_profile
    coupled_profile_lineage_verified = bool(
        coupled_profile is not None
        and coupled_profile.cross_section_x_m == profile.cross_section_x_m
        and coupled_profile.gamma == profile.gamma
        and handoff.shock_front_condition.coupled_inlet_profile_verified
    )
    if not coupled_profile_lineage_verified:
        return _failure(
            MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.COUPLED_PROFILE_LINEAGE_FAILURE,
            "shock-front condition does not retain the exact continuation section as its coupled inlet profile",
            handoff=handoff,
            placement_audit=placement_audit,
            continuation_audit=continuation_audit,
            shock_front_audit=shock_front_audit,
            source_field_identity_verified=True,
            cross_section_lineage_verified=True,
            maximum_cross_section_point_residual_m=maximum_point_residual,
        )
    ####
    return MocReflectedDomainGlobalPhysicalFieldHandoffAudit(
        status=MocReflectedDomainGlobalPhysicalFieldHandoffAuditStatus.VERIFIED,
        handoff=handoff,
        placement_audit=placement_audit,
        continuation_audit=continuation_audit,
        shock_front_audit=shock_front_audit,
        source_field_identity_verified=True,
        cross_section_lineage_verified=True,
        coupled_profile_lineage_verified=True,
        maximum_cross_section_point_residual_m=maximum_point_residual,
        message=("placement, continuation, and shock-front components were independently remeasured and retain one exact physical field and cross-section"),
    )
