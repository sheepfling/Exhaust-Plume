"""Independent fixed-point audit for the two-sided moving-interface ladder.

The moving-interface driver proves that a solver-owned response can be
consumed by an exact field re-solve.  That is not, by itself, a fixed point:
the final response may still move the interface, and a single successful
response cannot establish iteration-to-iteration stability.  This validator
adds that missing gate without changing the response law or inventing a
closure.

The audit compares adjacent response packets in their native units, checks
that the exact field object produced by one step is the field consumed by the
next step, and requires the final update to be stationary.  It is research
evidence only; canonical free-boundary and production gates remain closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
    MocEulerTwoSidedInterfaceResponse,
    MocEulerTwoSidedMovingInterfaceRequest,
    MocEulerTwoSidedMovingInterfaceResult,
)

__all__ = (
    "MOC_EULER_TWO_SIDED_MOVING_INTERFACE_FIXED_POINT_AUDIT_OPERATOR_ID",
    "MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus",
    "MocEulerTwoSidedMovingInterfaceFixedPointAudit",
    "measure_moc_euler_two_sided_moving_interface_fixed_point",
)


MOC_EULER_TWO_SIDED_MOVING_INTERFACE_FIXED_POINT_AUDIT_OPERATOR_ID = "op.moc.euler-two-sided-moving-interface-fixed-point-audit"


class MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus(str, Enum):
    """Typed outcomes for the independent fixed-point gate."""

    CONVERGED_RESEARCH_FIXED_POINT = "converged_research_two_sided_moving_interface_fixed_point"
    INVALID_INPUT = "invalid_input"
    RECORD_FAILURE = "two_sided_moving_interface_fixed_point_record_failure"
    LINEAGE_FAILURE = "two_sided_moving_interface_fixed_point_lineage_failure"
    RESIDUAL_FAILURE = "two_sided_moving_interface_fixed_point_residual_failure"
    STABILITY_FAILURE = "two_sided_moving_interface_fixed_point_stability_failure"
    MOTION_FAILURE = "two_sided_moving_interface_fixed_point_motion_failure"
    PROMOTION_FAILURE = "two_sided_moving_interface_fixed_point_promotion_failure"


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedMovingInterfaceFixedPointAudit:
    """Independent evidence for a stationary, iterated interface fixed point."""

    status: MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus
    result_status: str | None
    request_verified: bool
    record_count: int
    record_lineage_verified: bool
    response_lineage_verified: bool
    field_re_solve_verified: bool
    response_residuals_verified: bool
    response_stability_verified: bool
    final_update_zero_verified: bool
    stationary_equilibrium_verified: bool
    fixed_point_verified: bool
    canonical_free_boundary_verified: bool
    canonical_euler_verified: bool
    chain_promotion_blocked: bool
    production_claim_allowed: bool
    maximum_normal_update_change_m: float = 0.0
    maximum_mass_residual_change_kg_m2_s: float = 0.0
    maximum_momentum_residual_change_Pa: float = 0.0
    maximum_energy_residual_change_W_m2: float = 0.0
    maximum_final_normal_update_m: float = 0.0
    update_change_tolerance_m: float = 1.0e-8
    mass_residual_change_tolerance_kg_m2_s: float = 1.0e-3
    momentum_residual_change_tolerance_Pa: float = 1.0e-2
    energy_residual_change_tolerance_W_m2: float = 1.0e-1
    message: str = ""
    operator_id: str = MOC_EULER_TWO_SIDED_MOVING_INTERFACE_FIXED_POINT_AUDIT_OPERATOR_ID

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus,
        ):
            raise TypeError("status must be a fixed-point audit status")
        ####
        if self.result_status is not None:
            object.__setattr__(self, "result_status", str(self.result_status))
        ####
        if isinstance(self.record_count, bool) or not isinstance(self.record_count, int) or self.record_count < 0:
            raise ValueError("record_count must be a nonnegative integer")
        ####
        for name in (
            "request_verified",
            "record_lineage_verified",
            "response_lineage_verified",
            "field_re_solve_verified",
            "response_residuals_verified",
            "response_stability_verified",
            "final_update_zero_verified",
            "stationary_equilibrium_verified",
            "fixed_point_verified",
            "canonical_free_boundary_verified",
            "canonical_euler_verified",
            "chain_promotion_blocked",
            "production_claim_allowed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        ####
        for name in (
            "maximum_normal_update_change_m",
            "maximum_mass_residual_change_kg_m2_s",
            "maximum_momentum_residual_change_Pa",
            "maximum_energy_residual_change_W_m2",
            "maximum_final_normal_update_m",
            "update_change_tolerance_m",
            "mass_residual_change_tolerance_kg_m2_s",
            "momentum_residual_change_tolerance_Pa",
            "energy_residual_change_tolerance_W_m2",
        ):
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
            ####
            object.__setattr__(self, name, value)
        ####
        if self.fixed_point_verified and not (
            self.record_lineage_verified
            and self.response_lineage_verified
            and self.field_re_solve_verified
            and self.response_residuals_verified
            and self.final_update_zero_verified
            and (self.response_stability_verified or self.stationary_equilibrium_verified)
        ):
            raise ValueError("fixed_point_verified requires every independent fixed-point gate")
        ####
        if self.canonical_free_boundary_verified or self.canonical_euler_verified:
            raise ValueError("fixed-point research audit cannot claim canonical closure")
        ####
        if not self.chain_promotion_blocked or self.production_claim_allowed:
            raise ValueError("fixed-point research audit must remain promotion-blocked")
        ####
        operator_id = str(self.operator_id)
        if not operator_id:
            raise ValueError("operator_id must be non-empty")
        ####
        object.__setattr__(self, "operator_id", operator_id)
        object.__setattr__(self, "message", str(self.message))

    ####

    @property
    def converged(self) -> bool:
        return self.status is (MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.CONVERGED_RESEARCH_FIXED_POINT)

    ####

    @property
    def local_consistency_verified(self) -> bool:
        return bool(
            self.converged
            and self.request_verified
            and self.record_lineage_verified
            and self.response_lineage_verified
            and self.field_re_solve_verified
            and self.response_residuals_verified
            and self.final_update_zero_verified
            and (self.response_stability_verified or self.stationary_equilibrium_verified)
            and self.fixed_point_verified
            and not self.canonical_free_boundary_verified
            and not self.canonical_euler_verified
            and self.chain_promotion_blocked
            and not self.production_claim_allowed
        )

    ####

    def as_report(self) -> dict[str, object]:
        return {
            "operator_id": self.operator_id,
            "status": self.status.value,
            "result_status": self.result_status,
            "converged": self.converged,
            "local_consistency_verified": self.local_consistency_verified,
            "request_verified": self.request_verified,
            "record_count": self.record_count,
            "record_lineage_verified": self.record_lineage_verified,
            "response_lineage_verified": self.response_lineage_verified,
            "field_re_solve_verified": self.field_re_solve_verified,
            "response_residuals_verified": self.response_residuals_verified,
            "response_stability_verified": self.response_stability_verified,
            "final_update_zero_verified": self.final_update_zero_verified,
            "stationary_equilibrium_verified": self.stationary_equilibrium_verified,
            "fixed_point_verified": self.fixed_point_verified,
            "canonical_free_boundary_verified": False,
            "canonical_euler_verified": False,
            "chain_promotion_blocked": True,
            "production_claim_allowed": False,
            "maximum_normal_update_change_m": self.maximum_normal_update_change_m,
            "maximum_mass_residual_change_kg_m2_s": (self.maximum_mass_residual_change_kg_m2_s),
            "maximum_momentum_residual_change_Pa": (self.maximum_momentum_residual_change_Pa),
            "maximum_energy_residual_change_W_m2": (self.maximum_energy_residual_change_W_m2),
            "maximum_final_normal_update_m": self.maximum_final_normal_update_m,
            "update_change_tolerance_m": self.update_change_tolerance_m,
            "mass_residual_change_tolerance_kg_m2_s": (self.mass_residual_change_tolerance_kg_m2_s),
            "momentum_residual_change_tolerance_Pa": (self.momentum_residual_change_tolerance_Pa),
            "energy_residual_change_tolerance_W_m2": (self.energy_residual_change_tolerance_W_m2),
            "message": self.message,
        }

    ####


####


def _failure(
    status: MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus,
    message: str,
    *,
    result_status: str | None = None,
    request_verified: bool = False,
    record_count: int = 0,
    record_lineage_verified: bool = False,
    response_lineage_verified: bool = False,
    field_re_solve_verified: bool = False,
    response_residuals_verified: bool = False,
    response_stability_verified: bool = False,
    final_update_zero_verified: bool = False,
    stationary_equilibrium_verified: bool = False,
    fixed_point_verified: bool = False,
    maximum_normal_update_change_m: float = 0.0,
    maximum_mass_residual_change_kg_m2_s: float = 0.0,
    maximum_momentum_residual_change_Pa: float = 0.0,
    maximum_energy_residual_change_W_m2: float = 0.0,
    maximum_final_normal_update_m: float = 0.0,
    update_change_tolerance_m: float = 1.0e-8,
    mass_residual_change_tolerance_kg_m2_s: float = 1.0e-3,
    momentum_residual_change_tolerance_Pa: float = 1.0e-2,
    energy_residual_change_tolerance_W_m2: float = 1.0e-1,
) -> MocEulerTwoSidedMovingInterfaceFixedPointAudit:
    return MocEulerTwoSidedMovingInterfaceFixedPointAudit(
        status=status,
        result_status=result_status,
        request_verified=request_verified,
        record_count=record_count,
        record_lineage_verified=record_lineage_verified,
        response_lineage_verified=response_lineage_verified,
        field_re_solve_verified=field_re_solve_verified,
        response_residuals_verified=response_residuals_verified,
        response_stability_verified=response_stability_verified,
        final_update_zero_verified=final_update_zero_verified,
        stationary_equilibrium_verified=stationary_equilibrium_verified,
        fixed_point_verified=fixed_point_verified,
        canonical_free_boundary_verified=False,
        canonical_euler_verified=False,
        chain_promotion_blocked=True,
        production_claim_allowed=False,
        maximum_normal_update_change_m=maximum_normal_update_change_m,
        maximum_mass_residual_change_kg_m2_s=maximum_mass_residual_change_kg_m2_s,
        maximum_momentum_residual_change_Pa=maximum_momentum_residual_change_Pa,
        maximum_energy_residual_change_W_m2=maximum_energy_residual_change_W_m2,
        maximum_final_normal_update_m=maximum_final_normal_update_m,
        update_change_tolerance_m=update_change_tolerance_m,
        mass_residual_change_tolerance_kg_m2_s=mass_residual_change_tolerance_kg_m2_s,
        momentum_residual_change_tolerance_Pa=momentum_residual_change_tolerance_Pa,
        energy_residual_change_tolerance_W_m2=energy_residual_change_tolerance_W_m2,
        message=message,
    )


def _maximum_absolute_difference(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    if len(first) != len(second):
        raise ValueError("fixed-point response channels must have equal lengths")
    return max(
        (abs(float(left) - float(right)) for left, right in zip(first, second, strict=True)),
        default=0.0,
    )


def _response_is_finite(response: MocEulerTwoSidedInterfaceResponse) -> bool:
    return all(
        isfinite(float(value))
        for values in (
            response.normal_displacements_m,
            response.mass_flux_residuals_kg_m2_s,
            response.normal_momentum_residuals_Pa,
            response.energy_flux_residuals_W_m2,
        )
        for value in values
    )


def measure_moc_euler_two_sided_moving_interface_fixed_point(
    result: MocEulerTwoSidedMovingInterfaceResult,
    *,
    update_change_tolerance_m: float | None = None,
    mass_residual_change_tolerance_kg_m2_s: float | None = None,
    momentum_residual_change_tolerance_Pa: float | None = None,
    energy_residual_change_tolerance_W_m2: float | None = None,
) -> MocEulerTwoSidedMovingInterfaceFixedPointAudit:
    """Audit iteration stability and final zero interface update.

    A moving response with nonzero final normal displacement is intentionally
    not a fixed point, even when its individual flux tolerances pass.  A
    stationary-equilibrium response may pass with one record when the solver
    explicitly allowed that mode; an iterated moving response requires at least
    two exact response/re-solve records.
    """

    if not isinstance(result, MocEulerTwoSidedMovingInterfaceResult):
        return _failure(
            MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.INVALID_INPUT,
            "result must be a MocEulerTwoSidedMovingInterfaceResult",
        )
    ####
    request = result.request
    if not isinstance(request, MocEulerTwoSidedMovingInterfaceRequest):
        return _failure(
            MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.INVALID_INPUT,
            "fixed-point audit requires the typed moving-interface request",
            result_status=result.status.value,
        )
    ####
    tolerances: dict[str, float] = {}
    for name, supplied, fallback in (
        (
            "update_change_tolerance_m",
            update_change_tolerance_m,
            request.position_tolerance_m,
        ),
        (
            "mass_residual_change_tolerance_kg_m2_s",
            mass_residual_change_tolerance_kg_m2_s,
            request.mass_flux_tolerance_kg_m2_s,
        ),
        (
            "momentum_residual_change_tolerance_Pa",
            momentum_residual_change_tolerance_Pa,
            request.normal_momentum_tolerance_Pa,
        ),
        (
            "energy_residual_change_tolerance_W_m2",
            energy_residual_change_tolerance_W_m2,
            request.energy_flux_tolerance_W_m2,
        ),
    ):
        try:
            value = float(fallback if supplied is None else supplied)
        except (TypeError, ValueError):
            return _failure(
                MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.INVALID_INPUT,
                f"{name} must be numeric",
                result_status=result.status.value,
                request_verified=True,
            )
        ####
        if not isfinite(value) or value <= 0.0:
            return _failure(
                MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.INVALID_INPUT,
                f"{name} must be finite and positive",
                result_status=result.status.value,
                request_verified=True,
            )
        ####
        tolerances[name] = value
    ####

    records = tuple(result.records)
    if not records:
        return _failure(
            MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.RECORD_FAILURE,
            "fixed-point audit requires at least one retained response record",
            result_status=result.status.value,
            request_verified=True,
            record_count=0,
            **tolerances,
        )
    ####
    response_values: list[MocEulerTwoSidedInterfaceResponse] = []
    record_lineage_verified = True
    response_lineage_verified = True
    field_re_solve_verified = True
    response_residuals_verified = True
    for index, record in enumerate(records):
        response = record.response
        if response is None or not _response_is_finite(response):
            response_lineage_verified = False
            response_residuals_verified = False
            continue
        ####
        response_values.append(response)
        response_lineage_verified = bool(
            response_lineage_verified
            and record.response_lineage_verified
            and response.prior_shock_boundary is record.field_iteration.shock_boundary
            and record.field_iteration.shock_boundary is not None
        )
        response_residuals_verified = bool(response_residuals_verified and record.response_residuals_verified)
        next_field = record.next_field_iteration
        if next_field is None:
            field_re_solve_verified = False
            continue
        ####
        field_re_solve_verified = bool(
            field_re_solve_verified
            and record.field_re_solve_verified
            and next_field.shock_boundary is response.next_shock_boundary
            and next_field.initial_companion_field is response.next_companion_field
            and next_field.field_iteration_verified
        )
        if index + 1 < len(records):
            next_record = records[index + 1]
            record_lineage_verified = bool(record_lineage_verified and next_field is next_record.field_iteration)
        ####
    ####
    record_lineage_verified = bool(record_lineage_verified and all(record.next_field_iteration is not None for record in records))
    response_lineage_verified = bool(response_lineage_verified and all(record.response is not None for record in records))
    response_residuals_verified = bool(response_residuals_verified and result.response_residuals_verified and all(record.response is not None for record in records))
    ####
    maximum_update_change = 0.0
    maximum_mass_change = 0.0
    maximum_momentum_change = 0.0
    maximum_energy_change = 0.0
    response_stability_verified = False
    if len(response_values) >= 2 and len(response_values) == len(records):
        try:
            for first, second in zip(response_values, response_values[1:], strict=True):
                maximum_update_change = max(
                    maximum_update_change,
                    _maximum_absolute_difference(
                        first.normal_displacements_m,
                        second.normal_displacements_m,
                    ),
                )
                maximum_mass_change = max(
                    maximum_mass_change,
                    _maximum_absolute_difference(
                        first.mass_flux_residuals_kg_m2_s,
                        second.mass_flux_residuals_kg_m2_s,
                    ),
                )
                maximum_momentum_change = max(
                    maximum_momentum_change,
                    _maximum_absolute_difference(
                        first.normal_momentum_residuals_Pa,
                        second.normal_momentum_residuals_Pa,
                    ),
                )
                maximum_energy_change = max(
                    maximum_energy_change,
                    _maximum_absolute_difference(
                        first.energy_flux_residuals_W_m2,
                        second.energy_flux_residuals_W_m2,
                    ),
                )
            ####
            response_stability_verified = bool(
                maximum_update_change <= tolerances["update_change_tolerance_m"]
                and maximum_mass_change <= tolerances["mass_residual_change_tolerance_kg_m2_s"]
                and maximum_momentum_change <= tolerances["momentum_residual_change_tolerance_Pa"]
                and maximum_energy_change <= tolerances["energy_residual_change_tolerance_W_m2"]
            )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError):
            response_stability_verified = False
    ####
    final_response = response_values[-1] if response_values else None
    maximum_final_update = 0.0 if final_response is None else max((abs(value) for value in final_response.normal_displacements_m), default=0.0)
    final_update_zero_verified = bool(final_response is not None and maximum_final_update <= request.position_tolerance_m)
    stationary_equilibrium_verified = bool(
        result.stationary_equilibrium_verified and request.allow_stationary_equilibrium and records[-1].stationary_equilibrium_verified and final_update_zero_verified
    )
    fixed_point_verified = bool(
        result.moving_interface_verified
        and record_lineage_verified
        and response_lineage_verified
        and field_re_solve_verified
        and response_residuals_verified
        and final_update_zero_verified
        and (response_stability_verified or stationary_equilibrium_verified)
    )
    common = dict(
        result_status=result.status.value,
        request_verified=True,
        record_count=len(records),
        record_lineage_verified=record_lineage_verified,
        response_lineage_verified=response_lineage_verified,
        field_re_solve_verified=field_re_solve_verified,
        response_residuals_verified=response_residuals_verified,
        response_stability_verified=response_stability_verified,
        final_update_zero_verified=final_update_zero_verified,
        stationary_equilibrium_verified=stationary_equilibrium_verified,
        fixed_point_verified=fixed_point_verified,
        maximum_normal_update_change_m=maximum_update_change,
        maximum_mass_residual_change_kg_m2_s=maximum_mass_change,
        maximum_momentum_residual_change_Pa=maximum_momentum_change,
        maximum_energy_residual_change_W_m2=maximum_energy_change,
        maximum_final_normal_update_m=maximum_final_update,
        **tolerances,
    )
    if not record_lineage_verified or not response_lineage_verified or not field_re_solve_verified:
        status = MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.LINEAGE_FAILURE
        message = "exact response-to-field lineage did not form a contiguous fixed-point chain"
    elif not response_residuals_verified:
        status = MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.RESIDUAL_FAILURE
        message = "one or more retained response records did not pass the declared flux residual gate"
    elif not final_update_zero_verified:
        status = MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.MOTION_FAILURE
        message = "the final solver-owned interface update remains nonzero; the response is not a fixed point"
    elif not response_stability_verified and not stationary_equilibrium_verified:
        status = MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.STABILITY_FAILURE
        message = "at least two stable response updates or an explicit stationary-equilibrium proof are required"
    elif not result.chain_promotion_blocked or result.production_claim_allowed:
        status = MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.PROMOTION_FAILURE
        message = "moving-interface fixed-point evidence weakened its promotion boundary"
    else:
        status = MocEulerTwoSidedMovingInterfaceFixedPointAuditStatus.CONVERGED_RESEARCH_FIXED_POINT
        message = (
            "the solver-owned moving-interface ladder retained exact contiguous "
            "field lineage, stable response channels, and a zero final update; "
            "canonical closure and production promotion remain open"
        )
    ####
    return _failure(status, message, **common)
