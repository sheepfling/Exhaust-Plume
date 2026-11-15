"""Consume conservative overlap states in a fresh downstream Euler solve.

The source mesh is remapped conservatively onto the downstream finite-volume
cells. This module binds the source cell averages adjacent to each retained
free-boundary face, solves a fresh downstream PDE with an entropy-compatible
state-trace flux, and independently replays the state binding and Euler
residual audit. The downstream equation can reject the transferred trace; a
verified transfer is not a verified global coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite, sqrt
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
    MocReflectedDomainCoupledEulerFreeBoundaryFluxMode,
    MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    MocReflectedDomainCoupledEulerFreeBoundaryResult,
    solve_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
    MocReflectedDomainCoupledEulerFreeBoundaryAudit,
    measure_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.validation.moc_global_mixed_regime_conservative_mesh_overlap import (
    MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit,
    MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
    audit_reflected_domain_global_mixed_regime_conservative_mesh_overlap,
)

__all__ = (
    "MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID",
    "MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode",
    "MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus",
    "MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveRequest",
    "MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult",
    "MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAuditStatus",
    "MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAudit",
    "solve_reflected_domain_global_mixed_regime_overlap_boundary",
    "audit_reflected_domain_global_mixed_regime_overlap_boundary",
)


MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID = (
    "op.moc.reflected-domain.global-mixed-regime.overlap-boundary-solve-v1"
)
_SOURCE = "research-global-source-overlap-cell-average-v1"
_FLUX_SOURCE = "research-global-overlap-euler-normal-flux-v1"
_GEOMETRY_SOURCE = "research-overlap-boundary-geometry-v1"


class MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode(
    str,
    Enum,
):
    """Select the distinct one-way overlap handoff law under investigation."""

    ENTROPY_COMPATIBLE_STATE_TRACE = "entropy-compatible-state-trace"
    REMAPPED_EULER_NORMAL_FLUX = "remapped-euler-normal-flux"


class MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus(
    str,
    Enum,
):
    """Outcome of binding and consuming the remapped boundary states."""

    VERIFIED_RESEARCH_CONSUMPTION = (
        "verified-research-overlap-boundary-state-consumption"
    )
    INVALID_INPUT = "invalid_input"
    LINEAGE_FAILURE = "overlap-boundary-solve-lineage-failure"
    SOLVER_FAILURE = "overlap-boundary-solve-failure"
    INDEPENDENT_AUDIT_FAILURE = "overlap-boundary-solve-audit-failure"


class MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAuditStatus(
    str,
    Enum,
):
    """Outcome of independent state-transfer and residual replay."""

    VERIFIED_RESEARCH_REPLAY = (
        "verified-research-overlap-boundary-solve-replay"
    )
    INVALID_INPUT = "invalid_input"
    REPLAY_FAILURE = "overlap-boundary-solve-replay-failure"


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveRequest:
    """A verified overlap packet and explicit downstream boundary law."""

    overlap: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult
    boundary_condition_mode: (
        MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode
    ) = (
        MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode
        .ENTROPY_COMPATIBLE_STATE_TRACE
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.overlap,
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
        ):
            raise TypeError("overlap must be a typed conservative mesh-overlap result")
        if not isinstance(
            self.boundary_condition_mode,
            MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode,
        ):
            raise TypeError("boundary_condition_mode must be a typed overlap boundary mode")

    def as_report(self) -> dict[str, Any]:
        return {
            "operator_id": MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID,
            "overlap_source_closure_fingerprint": self.overlap.source_closure_fingerprint,
            "overlap_verified": self.overlap.local_overlap_verified,
            "boundary_condition_mode": self.boundary_condition_mode.value,
            "research_only": True,
            "global_coupling_verified": False,
            "production_claim_allowed": False,
        }


def _point_matches(
    first: tuple[float, float],
    second: tuple[float, float],
    tolerance_m: float,
) -> bool:
    return abs(first[0] - second[0]) <= tolerance_m and abs(
        first[1] - second[1]
    ) <= tolerance_m


def _free_boundary_face_cells(
    field: MocReflectedDomainCoupledEulerFreeBoundaryResult,
    tolerance_m: float,
) -> tuple[int, ...]:
    points = field.free_boundary_points_m
    polygons = field.cell_vertices_by_cell_m
    if len(points) < 2 or not polygons:
        raise ValueError("downstream field has no boundary faces or cell polygons")
    matches: list[int] = []
    for first, second in zip(points, points[1:], strict=False):
        hits: list[int] = []
        for index, polygon in enumerate(polygons):
            for edge_start, edge_end in zip(polygon, (*polygon[1:], polygon[0])):
                if (
                    _point_matches(first, edge_start, tolerance_m)
                    and _point_matches(second, edge_end, tolerance_m)
                ) or (
                    _point_matches(first, edge_end, tolerance_m)
                    and _point_matches(second, edge_start, tolerance_m)
                ):
                    hits.append(index)
                    break
        if len(hits) != 1:
            raise ValueError(
                "each retained free-boundary face must match exactly one downstream cell"
            )
        matches.append(hits[0])
    if len(set(matches)) != len(matches):
        raise ValueError("free-boundary faces must map to distinct downstream cells")
    return tuple(matches)


def _bound_profile(
    overlap: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
) -> tuple[
    tuple[int, ...],
    tuple[tuple[float, float], ...],
    tuple[float, ...],
    tuple[tuple[float, float, float, float], ...],
]:
    request = overlap.request
    if request is None or request.downstream.coupled_field is None:
        raise ValueError("overlap is missing its retained downstream field")
    field = request.downstream.coupled_field
    tolerance_m = request.position_tolerance_m
    cell_indices = _free_boundary_face_cells(field, tolerance_m)
    points = field.free_boundary_points_m
    face_midpoints = tuple(
        (0.5 * (first[0] + second[0]), 0.5 * (first[1] + second[1]))
        for first, second in zip(points, points[1:])
    )
    stations = tuple(point[0] for point in face_midpoints)
    states_by_cell = overlap.source_remapped_states_by_downstream_cell
    if len(states_by_cell) != len(field.cell_vertices_by_cell_m):
        raise ValueError("remapped state count does not match the downstream mesh")
    states: list[tuple[float, float, float, float]] = []
    for index in cell_indices:
        state = states_by_cell[index]
        if state is None or len(state) != 4 or any(not isfinite(value) for value in state):
            raise ValueError("a free-boundary face has no finite remapped source state")
        states.append(state)
    target_points = request.contract.conservative_state_profile_points_m
    if len(target_points) != len(face_midpoints) or any(
        not _point_matches(first, second, tolerance_m)
        for first, second in zip(target_points, face_midpoints, strict=True)
    ):
        raise ValueError("overlap contract points do not match the retained face midpoints")
    return cell_indices, face_midpoints, stations, tuple(states)


def _overlap_euler_normal_flux_profile(
    overlap: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
    cell_indices: tuple[int, ...],
    face_midpoints: tuple[tuple[float, float], ...],
    source_states: tuple[tuple[float, float, float, float], ...],
) -> tuple[MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget, ...]:
    """Build exact Euler normal fluxes from remapped cell-average states."""

    if overlap.request is None or overlap.request.downstream.coupled_request is None:
        raise ValueError("overlap is missing its retained downstream request")
    field = overlap.request.downstream.coupled_field
    if field is None:
        raise ValueError("overlap is missing its retained downstream field")
    request = overlap.request.downstream.coupled_request
    gamma = float(request.mixed_regime_request.control_section.samples[0].gamma)
    if not isfinite(gamma) or gamma <= 1.0:
        raise ValueError("downstream gamma must be finite and greater than one")
    if len(cell_indices) != len(face_midpoints) or len(source_states) != len(face_midpoints):
        raise ValueError("overlap flux inputs must align one-to-one with boundary faces")

    points = field.free_boundary_points_m
    tolerance_m = overlap.request.position_tolerance_m
    targets: list[MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget] = []
    for face_index, (cell_index, midpoint, state) in enumerate(
        zip(cell_indices, face_midpoints, source_states, strict=True)
    ):
        first, second = points[face_index : face_index + 2]
        polygon = field.cell_vertices_by_cell_m[cell_index]
        matching_edges = tuple(
            (edge_start, edge_end)
            for edge_start, edge_end in zip(
                polygon,
                (*polygon[1:], polygon[0]),
                strict=True,
            )
            if (
                _point_matches(first, edge_start, tolerance_m)
                and _point_matches(second, edge_end, tolerance_m)
            )
            or (
                _point_matches(first, edge_end, tolerance_m)
                and _point_matches(second, edge_start, tolerance_m)
            )
        )
        if len(matching_edges) != 1:
            raise ValueError("each overlap face must bind to one oriented downstream cell edge")
        edge_start, edge_end = matching_edges[0]
        delta_x = edge_end[0] - edge_start[0]
        delta_y = edge_end[1] - edge_start[1]
        segment_length = sqrt(delta_x * delta_x + delta_y * delta_y)
        if not isfinite(segment_length) or segment_length <= 0.0:
            raise ValueError("overlap boundary contains a degenerate face")
        normal_x = delta_y / segment_length
        normal_y = -delta_x / segment_length

        density, momentum_x, momentum_y, total_energy = state
        if not all(isfinite(value) for value in state) or density <= 0.0:
            raise ValueError("overlap source state must be finite with positive density")
        velocity_x = momentum_x / density
        velocity_y = momentum_y / density
        pressure = (gamma - 1.0) * (
            total_energy
            - 0.5 * density * (velocity_x * velocity_x + velocity_y * velocity_y)
        )
        if not isfinite(pressure) or pressure <= 0.0:
            raise ValueError("overlap source state must have positive ideal-gas pressure")
        normal_velocity = velocity_x * normal_x + velocity_y * normal_y
        sound_speed = sqrt(gamma * pressure / density)
        flux = (
            density * normal_velocity,
            density * velocity_x * normal_velocity + pressure * normal_x,
            density * velocity_y * normal_velocity + pressure * normal_y,
            (total_energy + pressure) * normal_velocity,
        )
        targets.append(
            MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget(
                midpoint_m=midpoint,
                normal_m=(normal_x, normal_y),
                segment_length_m=segment_length,
                flux=flux,
                maximum_wave_speed_m_s=abs(normal_velocity) + sound_speed,
                scheme="euler-normal-flux-from-overlap-remapped-cell-average-v1",
            )
        )
    return tuple(targets)


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult:
    """Replayable overlap-fed PDE solve, including any open residuals."""

    status: MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus
    request: MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveRequest | None
    source_cell_indices: tuple[int, ...] = ()
    boundary_face_midpoints_m: tuple[tuple[float, float], ...] = ()
    boundary_stations_m: tuple[float, ...] = ()
    source_state_profile: tuple[tuple[float, float, float, float], ...] = ()
    source_flux_profile: tuple[MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget, ...] = ()
    fresh_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None = None
    field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None
    field_audit: MocReflectedDomainCoupledEulerFreeBoundaryAudit | None = None
    source_frame_verified: bool = False
    request_binding_verified: bool = False
    state_profile_consumed: bool = False
    flux_profile_consumed: bool = False
    flux_profile_frame_verified: bool = False
    boundary_geometry_consumed: bool = False
    residuals_recomputed: bool = False
    residuals_within_tolerance: bool = False
    global_coupling_verified: bool = False
    chain_promotion_blocked: bool = True
    production_claim_allowed: bool = False
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus,
        ):
            raise TypeError("status must be a typed overlap-boundary solve status")
        if self.request is not None and not isinstance(
            self.request,
            MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveRequest,
        ):
            raise TypeError("request must be a typed overlap-boundary solve request")
        for name in (
            "source_frame_verified",
            "request_binding_verified",
            "state_profile_consumed",
            "flux_profile_consumed",
            "flux_profile_frame_verified",
            "boundary_geometry_consumed",
            "residuals_recomputed",
            "residuals_within_tolerance",
            "global_coupling_verified",
            "chain_promotion_blocked",
            "production_claim_allowed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.global_coupling_verified or self.production_claim_allowed:
            raise ValueError("one-way overlap consumption cannot claim coupling or production")
        if not self.chain_promotion_blocked:
            raise ValueError("overlap-boundary evidence must block chain promotion")
        object.__setattr__(self, "source_cell_indices", tuple(self.source_cell_indices))
        object.__setattr__(self, "boundary_face_midpoints_m", tuple(self.boundary_face_midpoints_m))
        object.__setattr__(self, "boundary_stations_m", tuple(float(v) for v in self.boundary_stations_m))
        object.__setattr__(self, "source_state_profile", tuple(tuple(float(v) for v in row) for row in self.source_state_profile))
        object.__setattr__(self, "source_flux_profile", tuple(self.source_flux_profile))
        if any(
            not isinstance(target, MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget)
            for target in self.source_flux_profile
        ):
            raise TypeError("source_flux_profile must contain typed flux targets")
        object.__setattr__(self, "message", str(self.message))

    @property
    def verified_research_consumption(self) -> bool:
        state_trace_consumed = bool(
            self.request is not None
            and self.request.boundary_condition_mode
            is MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode.ENTROPY_COMPATIBLE_STATE_TRACE
            and self.state_profile_consumed
        )
        fixed_flux_consumed = bool(
            self.request is not None
            and self.request.boundary_condition_mode
            is MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode.REMAPPED_EULER_NORMAL_FLUX
            and self.flux_profile_consumed
            and self.flux_profile_frame_verified
            and self.boundary_geometry_consumed
        )
        return bool(
            self.status
            is MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.VERIFIED_RESEARCH_CONSUMPTION
            and self.source_frame_verified
            and self.request_binding_verified
            and (state_trace_consumed or fixed_flux_consumed)
            and self.residuals_recomputed
            and self.field is not None
            and self.field_audit is not None
            and self.field_audit.candidate is self.field
        )

    @property
    def local_pde_residuals_pass(self) -> bool:
        return bool(
            self.verified_research_consumption
            and self.residuals_within_tolerance
            and self.field_audit is not None
            and self.field_audit.converged
            and self.field_audit.local_consistency_verified
        )

    def as_report(self) -> dict[str, Any]:
        audit = self.field_audit
        return {
            "operator_id": MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID,
            "status": self.status.value,
            "verified_research_consumption": self.verified_research_consumption,
            "local_pde_residuals_pass": self.local_pde_residuals_pass,
            "overlap_source_closure_fingerprint": (
                None if self.request is None else self.request.overlap.source_closure_fingerprint
            ),
            "source_cell_indices": self.source_cell_indices,
            "boundary_face_midpoints_m": self.boundary_face_midpoints_m,
            "boundary_stations_m": self.boundary_stations_m,
            "source_state_profile": self.source_state_profile,
            "source_flux_profile": tuple(target.as_report() for target in self.source_flux_profile),
            "source_frame_verified": self.source_frame_verified,
            "request_binding_verified": self.request_binding_verified,
            "state_profile_consumed": self.state_profile_consumed,
            "flux_profile_consumed": self.flux_profile_consumed,
            "flux_profile_frame_verified": self.flux_profile_frame_verified,
            "boundary_geometry_consumed": self.boundary_geometry_consumed,
            "residuals_recomputed": self.residuals_recomputed,
            "residuals_within_tolerance": self.residuals_within_tolerance,
            "solver_status": None if self.field is None else self.field.status.value,
            "solver_iterations": None if self.field is None else self.field.pseudo_iteration_count,
            "shape_iterations": None if self.field is None else self.field.shape_iteration_count,
            "residual_tolerance": (
                None if self.fresh_request is None else self.fresh_request.euler_residual_tolerance
            ),
            "maximum_conservative_residuals": (
                None
                if audit is None
                else {
                    "mass": audit.maximum_conservative_mass_residual,
                    "streamwise_momentum": audit.maximum_conservative_streamwise_momentum_residual,
                    "transverse_momentum": audit.maximum_conservative_transverse_momentum_residual,
                    "energy": audit.maximum_conservative_energy_residual,
                    "euler": audit.maximum_conservative_euler_residual,
                }
            ),
            "maximum_entropy_transport_residual": (
                None if audit is None else audit.maximum_entropy_transport_residual
            ),
            "boundary_flux_mode": (
                None
                if self.fresh_request is None
                else self.fresh_request.free_boundary_flux_mode.value
            ),
            "global_coupling_verified": False,
            "chain_promotion_blocked": True,
            "production_claim_allowed": False,
            "claim_status": (
                "research-only-one-way-overlap-boundary-consumption; the "
                "remapped entropy-density field is measured but not independently "
                "imposed as a boundary variable"
            ),
            "message": self.message,
        }


def solve_reflected_domain_global_mixed_regime_overlap_boundary(
    request: MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveRequest,
) -> MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult:
    """Feed exact overlap cell averages into a fresh entropy-compatible solve."""

    if not isinstance(request, MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveRequest):
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
            status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.INVALID_INPUT,
            request=None,
            message="request must be a typed overlap-boundary solve request",
        )
    overlap = request.overlap
    overlap_audit = audit_reflected_domain_global_mixed_regime_conservative_mesh_overlap(overlap)
    if not overlap.local_overlap_verified or not overlap_audit.verified:
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
            status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.LINEAGE_FAILURE,
            request=request,
            message="source overlap and its independent replay must pass before equation consumption",
        )
    try:
        cell_indices, midpoints, stations, states = _bound_profile(overlap)
        downstream = overlap.request.downstream
        flux_profile: tuple[MocReflectedDomainCoupledEulerFreeBoundaryFluxTarget, ...] = ()
        base_request = downstream.coupled_request
        if base_request is None or downstream.coupled_field is None:
            raise ValueError("downstream result has no exact retained solver request")
        if downstream.coupled_field.request is not base_request:
            raise ValueError("downstream field and retained request identities differ")
        if base_request.upstream_state_equation is not None:
            raise ValueError("overlap boundary input cannot replace an existing upstream state equation")
        if base_request.entropy_closure_profile is not None:
            raise ValueError("overlap boundary input cannot silently replace an entropy closure profile")
        if request.boundary_condition_mode is (
            MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode
            .ENTROPY_COMPATIBLE_STATE_TRACE
        ):
            fresh_request = replace(
                base_request,
                free_boundary_pressure_profile_Pa=None,
                free_boundary_pressure_profile_x_stations_m=None,
                free_boundary_pressure_profile_source=None,
                free_boundary_flux_mode=(
                    MocReflectedDomainCoupledEulerFreeBoundaryFluxMode
                    .CONSERVATIVE_STATE_TRACE_ENTROPY_COMPATIBLE_RUSANOV
                ),
                free_boundary_conservative_state_profile=states,
                free_boundary_conservative_state_profile_x_stations_m=stations,
                free_boundary_conservative_state_profile_source=_SOURCE,
                free_boundary_conservative_flux_profile=None,
                free_boundary_conservative_flux_profile_source=None,
                source=MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID,
            )
            flux_profile = ()
        else:
            flux_profile = _overlap_euler_normal_flux_profile(
                overlap,
                cell_indices,
                midpoints,
                states,
            )
            geometry_points = downstream.coupled_field.free_boundary_points_m
            fresh_request = replace(
                base_request,
                free_boundary_pressure_profile_Pa=None,
                free_boundary_pressure_profile_x_stations_m=None,
                free_boundary_pressure_profile_source=None,
                free_boundary_geometry_profile_y_m=tuple(point[1] for point in geometry_points),
                free_boundary_geometry_profile_x_stations_m=tuple(point[0] for point in geometry_points),
                free_boundary_geometry_profile_source=_GEOMETRY_SOURCE,
                free_boundary_geometry_profile_lower_ordinate_m=float(
                    base_request.mixed_regime_request.control_section.points_m[0][1]
                ),
                free_boundary_flux_mode=(
                    MocReflectedDomainCoupledEulerFreeBoundaryFluxMode
                    .CONSERVATIVE_STATE_TRACE_RUSANOV
                ),
                free_boundary_conservative_state_profile=states,
                free_boundary_conservative_state_profile_x_stations_m=stations,
                free_boundary_conservative_state_profile_source=_SOURCE,
                free_boundary_conservative_flux_profile=flux_profile,
                free_boundary_conservative_flux_profile_source=_FLUX_SOURCE,
                source=MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID,
            )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
            status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.LINEAGE_FAILURE,
            request=request,
            message=f"overlap boundary frame could not be bound: {error}",
        )
    try:
        field = solve_reflected_domain_coupled_euler_free_boundary(fresh_request)
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
            status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.SOLVER_FAILURE,
            request=request,
            source_cell_indices=cell_indices,
            boundary_face_midpoints_m=midpoints,
            boundary_stations_m=stations,
            source_state_profile=states,
            source_flux_profile=flux_profile,
            fresh_request=fresh_request,
            source_frame_verified=True,
            request_binding_verified=True,
            message=f"fresh overlap-fed downstream equation solve failed: {error}",
        )
    try:
        field_audit = measure_reflected_domain_coupled_euler_free_boundary(field)
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
            status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.INDEPENDENT_AUDIT_FAILURE,
            request=request,
            source_cell_indices=cell_indices,
            boundary_face_midpoints_m=midpoints,
            boundary_stations_m=stations,
            source_state_profile=states,
            source_flux_profile=flux_profile,
            fresh_request=fresh_request,
            field=field,
            source_frame_verified=True,
            request_binding_verified=True,
            message=f"independent downstream Euler audit failed to run: {error}",
        )
    if request.boundary_condition_mode is (
        MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode
        .ENTROPY_COMPATIBLE_STATE_TRACE
    ):
        bound = bool(
            field.request is fresh_request
            and fresh_request.mixed_regime_request is base_request.mixed_regime_request
            and fresh_request.free_boundary_conservative_state_profile == states
            and fresh_request.free_boundary_conservative_state_profile_x_stations_m == stations
            and fresh_request.free_boundary_conservative_state_profile_source == _SOURCE
        )
        consumed = bool(field.free_boundary_conservative_state_profile_consumed)
        flux_consumed = False
        flux_frame_verified = False
        geometry_consumed = False
    else:
        geometry_points = downstream.coupled_field.free_boundary_points_m
        expected_flux = _overlap_euler_normal_flux_profile(
            overlap,
            cell_indices,
            midpoints,
            states,
        )
        bound = bool(
            field.request is fresh_request
            and fresh_request.mixed_regime_request is base_request.mixed_regime_request
            and fresh_request.free_boundary_conservative_state_profile == states
            and fresh_request.free_boundary_conservative_state_profile_x_stations_m == stations
            and fresh_request.free_boundary_conservative_state_profile_source == _SOURCE
            and fresh_request.free_boundary_conservative_flux_profile == expected_flux
            and fresh_request.free_boundary_conservative_flux_profile_source == _FLUX_SOURCE
            and fresh_request.free_boundary_geometry_profile_y_m
            == tuple(point[1] for point in geometry_points)
            and fresh_request.free_boundary_geometry_profile_x_stations_m
            == tuple(point[0] for point in geometry_points)
            and fresh_request.free_boundary_geometry_profile_source == _GEOMETRY_SOURCE
        )
        consumed = False
        flux_consumed = bool(field.free_boundary_conservative_flux_profile_consumed)
        flux_frame_verified = bool(
            field.free_boundary_conservative_flux_profile_frame_verified
        )
        geometry_consumed = bool(field.free_boundary_geometry_profile_consumed)
    residuals_recomputed = bool(field_audit.candidate is field and field_audit.residual_channels_recomputed)
    residual_values = (
        field_audit.maximum_conservative_mass_residual,
        field_audit.maximum_conservative_streamwise_momentum_residual,
        field_audit.maximum_conservative_transverse_momentum_residual,
        field_audit.maximum_conservative_energy_residual,
        field_audit.maximum_conservative_euler_residual,
    )
    within_tolerance = bool(
        residuals_recomputed
        and all(value is not None and value <= fresh_request.euler_residual_tolerance for value in residual_values)
        and field_audit.converged
    )
    provisional = MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
        status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.VERIFIED_RESEARCH_CONSUMPTION,
        request=request,
        source_cell_indices=cell_indices,
        boundary_face_midpoints_m=midpoints,
        boundary_stations_m=stations,
        source_state_profile=states,
        source_flux_profile=flux_profile,
        fresh_request=fresh_request,
        field=field,
        field_audit=field_audit,
        source_frame_verified=True,
        request_binding_verified=bound,
        state_profile_consumed=consumed,
        flux_profile_consumed=flux_consumed,
        flux_profile_frame_verified=flux_frame_verified,
        boundary_geometry_consumed=geometry_consumed,
        residuals_recomputed=residuals_recomputed,
        residuals_within_tolerance=within_tolerance,
        message=(
            "exact overlap Euler normal fluxes were consumed on the retained "
            "boundary geometry; entropy and solver convergence gates remain open"
            if request.boundary_condition_mode
            is MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode.REMAPPED_EULER_NORMAL_FLUX
            else "exact overlap cell averages were consumed by a fresh "
            "entropy-compatible downstream Euler solve; local conservative "
            "residual admission remains open"
        ),
    )
    audit = audit_reflected_domain_global_mixed_regime_overlap_boundary(provisional)
    if not audit.verified:
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult(
            status=MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveStatus.INDEPENDENT_AUDIT_FAILURE,
            request=request,
            source_cell_indices=cell_indices,
            boundary_face_midpoints_m=midpoints,
            boundary_stations_m=stations,
            source_state_profile=states,
            source_flux_profile=flux_profile,
            fresh_request=fresh_request,
            field=field,
            field_audit=field_audit,
            source_frame_verified=True,
            request_binding_verified=bound,
            state_profile_consumed=consumed,
            flux_profile_consumed=flux_consumed,
            flux_profile_frame_verified=flux_frame_verified,
            boundary_geometry_consumed=geometry_consumed,
            residuals_recomputed=residuals_recomputed,
            residuals_within_tolerance=within_tolerance,
            message=audit.message,
        )
    return provisional


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAudit:
    """Independent replay of the face mapping and consumed PDE residuals."""

    status: MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAuditStatus
    candidate: MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult | None
    overlap_audit_verified: bool = False
    face_cell_map_recomputed: bool = False
    source_profile_recomputed: bool = False
    request_binding_recomputed: bool = False
    field_consumption_recomputed: bool = False
    residuals_recomputed: bool = False
    promotion_flags_verified: bool = False
    message: str = ""

    @property
    def verified(self) -> bool:
        return bool(
            self.status
            is MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAuditStatus.VERIFIED_RESEARCH_REPLAY
            and self.candidate is not None
            and self.overlap_audit_verified
            and self.face_cell_map_recomputed
            and self.source_profile_recomputed
            and self.request_binding_recomputed
            and self.field_consumption_recomputed
            and self.residuals_recomputed
            and self.promotion_flags_verified
        )

    def as_report(self) -> dict[str, Any]:
        return {
            "operator_id": MOC_GLOBAL_MIXED_REGIME_OVERLAP_BOUNDARY_SOLVE_OPERATOR_ID,
            "status": self.status.value,
            "verified": self.verified,
            "overlap_audit_verified": self.overlap_audit_verified,
            "face_cell_map_recomputed": self.face_cell_map_recomputed,
            "source_profile_recomputed": self.source_profile_recomputed,
            "request_binding_recomputed": self.request_binding_recomputed,
            "field_consumption_recomputed": self.field_consumption_recomputed,
            "residuals_recomputed": self.residuals_recomputed,
            "promotion_flags_verified": self.promotion_flags_verified,
            "global_coupling_verified": False,
            "production_claim_allowed": False,
            "message": self.message,
        }


def audit_reflected_domain_global_mixed_regime_overlap_boundary(
    candidate: MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult,
) -> MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAudit:
    """Recompute overlap lineage, boundary mapping, and Euler residual evidence."""

    status = MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAuditStatus
    if not isinstance(candidate, MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveResult):
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAudit(
            status=status.INVALID_INPUT,
            candidate=None,
            message="candidate must be a typed overlap-boundary solve result",
        )
    request = candidate.request
    field = candidate.field
    fresh_request = candidate.fresh_request
    field_audit = candidate.field_audit
    if request is None or field is None or fresh_request is None or field_audit is None:
        return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAudit(
            status=status.REPLAY_FAILURE,
            candidate=candidate,
            message="candidate does not retain its overlap, fresh request, PDE field, and independent audit",
        )
    overlap_audit: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit = (
        audit_reflected_domain_global_mixed_regime_conservative_mesh_overlap(request.overlap)
    )
    face_map_ok = False
    profile_ok = False
    request_ok = False
    field_ok = False
    residuals_ok = False
    try:
        indices, midpoints, stations, states = _bound_profile(request.overlap)
        face_map_ok = indices == candidate.source_cell_indices and midpoints == candidate.boundary_face_midpoints_m
        profile_ok = stations == candidate.boundary_stations_m and states == candidate.source_state_profile
        base_request = request.overlap.request.downstream.coupled_request
        if request.boundary_condition_mode is (
            MocReflectedDomainGlobalMixedRegimeOverlapBoundaryConditionMode
            .ENTROPY_COMPATIBLE_STATE_TRACE
        ):
            request_ok = bool(
                base_request is not None
                and fresh_request is not base_request
                and fresh_request.mixed_regime_request is base_request.mixed_regime_request
                and fresh_request.free_boundary_flux_mode
                is MocReflectedDomainCoupledEulerFreeBoundaryFluxMode.CONSERVATIVE_STATE_TRACE_ENTROPY_COMPATIBLE_RUSANOV
                and fresh_request.free_boundary_conservative_state_profile == states
                and fresh_request.free_boundary_conservative_state_profile_x_stations_m == stations
                and fresh_request.free_boundary_conservative_state_profile_source == _SOURCE
                and fresh_request.free_boundary_pressure_profile_Pa is None
                and fresh_request.free_boundary_conservative_flux_profile is None
                and candidate.source_flux_profile == ()
            )
            field_ok = bool(
                field.request is fresh_request
                and field.free_boundary_conservative_state_profile_consumed
                and not candidate.flux_profile_consumed
                and not candidate.flux_profile_frame_verified
            )
        else:
            expected_flux = _overlap_euler_normal_flux_profile(
                request.overlap,
                indices,
                midpoints,
                states,
            )
            geometry_points = request.overlap.request.downstream.coupled_field.free_boundary_points_m
            geometry_x = tuple(point[0] for point in geometry_points)
            geometry_y = tuple(point[1] for point in geometry_points)
            request_ok = bool(
                base_request is not None
                and fresh_request is not base_request
                and fresh_request.mixed_regime_request is base_request.mixed_regime_request
                and fresh_request.free_boundary_flux_mode
                is MocReflectedDomainCoupledEulerFreeBoundaryFluxMode.CONSERVATIVE_STATE_TRACE_RUSANOV
                and fresh_request.free_boundary_conservative_state_profile == states
                and fresh_request.free_boundary_conservative_state_profile_x_stations_m == stations
                and fresh_request.free_boundary_conservative_state_profile_source == _SOURCE
                and fresh_request.free_boundary_conservative_flux_profile == expected_flux
                and candidate.source_flux_profile == expected_flux
                and fresh_request.free_boundary_conservative_flux_profile_source == _FLUX_SOURCE
                and fresh_request.free_boundary_pressure_profile_Pa is None
                and fresh_request.free_boundary_geometry_profile_x_stations_m == geometry_x
                and fresh_request.free_boundary_geometry_profile_y_m == geometry_y
                and fresh_request.free_boundary_geometry_profile_source == _GEOMETRY_SOURCE
                and fresh_request.free_boundary_geometry_profile_lower_ordinate_m
                == float(base_request.mixed_regime_request.control_section.points_m[0][1])
                and not candidate.state_profile_consumed
            )
            field_ok = bool(
                field.request is fresh_request
                and field.free_boundary_conservative_flux_profile_consumed
                and field.free_boundary_conservative_flux_profile_frame_verified
                and field.free_boundary_geometry_profile_consumed
                and candidate.flux_profile_consumed
                and candidate.flux_profile_frame_verified
                and candidate.boundary_geometry_consumed
            )
        replayed = measure_reflected_domain_coupled_euler_free_boundary(field)
        residual_names = (
            "maximum_conservative_mass_residual",
            "maximum_conservative_streamwise_momentum_residual",
            "maximum_conservative_transverse_momentum_residual",
            "maximum_conservative_energy_residual",
            "maximum_conservative_euler_residual",
        )
        residuals_ok = bool(
            replayed.candidate is field
            and replayed.residual_channels_recomputed
            and field_audit.residual_channels_recomputed
            and replayed.status is field_audit.status
            and all(
                getattr(replayed, name) == getattr(field_audit, name)
                for name in residual_names
            )
            and candidate.residuals_recomputed
            and candidate.residuals_within_tolerance == replayed.converged
        )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError):
        pass
    promotion_ok = bool(
        not candidate.global_coupling_verified
        and candidate.chain_promotion_blocked
        and not candidate.production_claim_allowed
        and not field.canonical_free_boundary_verified
        and not field.canonical_euler_verified
        and field.chain_promotion_blocked
        and not field.production_claim_allowed
        and not field_audit.physical_closure_verified
        and field_audit.chain_promotion_blocked
        and not field_audit.production_claim_allowed
    )
    verified = bool(
        candidate.verified_research_consumption
        and overlap_audit.verified
        and face_map_ok
        and profile_ok
        and request_ok
        and field_ok
        and residuals_ok
        and promotion_ok
    )
    return MocReflectedDomainGlobalMixedRegimeOverlapBoundarySolveAudit(
        status=(status.VERIFIED_RESEARCH_REPLAY if verified else status.REPLAY_FAILURE),
        candidate=candidate,
        overlap_audit_verified=overlap_audit.verified,
        face_cell_map_recomputed=face_map_ok,
        source_profile_recomputed=profile_ok,
        request_binding_recomputed=request_ok,
        field_consumption_recomputed=field_ok,
        residuals_recomputed=residuals_ok,
        promotion_flags_verified=promotion_ok,
        message=(
            "independent replay verified the exact face-cell source states, "
            "fresh request consumption, Euler residuals, and fail-closed claims"
            if verified
            else "overlap-fed downstream equation evidence did not replay exactly"
        ),
    )
