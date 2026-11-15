"""Conservative remapping evidence for an embedded mixed-regime mesh.

The global fixed-front Euler reconciliation and the local downstream Euler
solve retain different finite-volume meshes over a common physical region.
This operator intersects their retained cell polygons and remaps conservative
cell averages and relative ideal-gas entropy density only over exact overlap
area. It reports the full-state and entropy-proxy mismatch on that support;
it does not apply feedback to either solver or claim a globally coupled
solution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite, log, sqrt
from typing import Any

import numpy as np

from exhaust_plume.models.moc.global_coupled_downstream import (
    MocReflectedDomainGlobalCoupledDownstreamResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
    MocReflectedDomainGlobalPhysicalClosureResult,
    moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
    MocPhysicalFieldEulerReconciliationResult,
)
from exhaust_plume.validation.moc_global_mixed_regime_state_equation_contract import (
    MocReflectedDomainGlobalMixedRegimeStateEquationContract,
)

__all__ = (
    "MocReflectedDomainGlobalMixedRegimeCellOverlapFragment",
    "MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus",
    "MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest",
    "MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult",
    "MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus",
    "MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit",
    "measure_reflected_domain_global_mixed_regime_conservative_mesh_overlap",
    "audit_reflected_domain_global_mixed_regime_conservative_mesh_overlap",
)


MOC_GLOBAL_MIXED_REGIME_CONSERVATIVE_MESH_OVERLAP_MODEL = "research-global-mixed-regime-conservative-mesh-overlap-v1"
_STATE_COMPONENT_NAMES = (
    "density",
    "streamwise_momentum",
    "transverse_momentum",
    "total_energy",
)
_ENTROPY_PROXY_REFERENCE = 1.0


class _LineageFailure(ValueError):
    pass


class _StateFailure(ValueError):
    pass


class _GeometryFailure(ValueError):
    pass


class MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus(
    str,
    Enum,
):
    """Typed outcomes of exact polygon-overlap remapping."""

    VERIFIED_RESEARCH_OVERLAP = "verified-research-conservative-mesh-overlap"
    PARTIAL_OVERLAP_DIAGNOSTIC = "partial-research-conservative-mesh-overlap"
    INVALID_INPUT = "invalid_input"
    LINEAGE_FAILURE = "conservative-mesh-overlap-lineage-failure"
    GEOMETRY_FAILURE = "conservative-mesh-overlap-geometry-failure"
    STATE_FAILURE = "conservative-mesh-overlap-state-failure"


####


class MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus(
    str,
    Enum,
):
    """Typed outcomes of an independent overlap replay."""

    VERIFIED_RESEARCH_OVERLAP_REPLAY = "verified-research-conservative-mesh-overlap-replay"
    INVALID_INPUT = "invalid_input"
    LINEAGE_FAILURE = "conservative-mesh-overlap-audit-lineage-failure"
    REPLAY_FAILURE = "conservative-mesh-overlap-audit-replay-failure"


####


def _finite_point(value: Any, name: str) -> tuple[float, float]:
    if any(isinstance(component, bool) for component in value):
        raise ValueError(f"{name} must not contain boolean coordinates")
    point = tuple(float(component) for component in value)
    if len(point) != 2 or any(not isfinite(component) for component in point):
        raise ValueError(f"{name} must contain finite 2-D points")
    ####
    return point


####


def _signed_area(polygon: tuple[tuple[float, float], ...]) -> float:
    origin_x, origin_y = polygon[0]
    return 0.5 * sum(
        (polygon[index][0] - origin_x) * (polygon[(index + 1) % len(polygon)][1] - origin_y) - (polygon[(index + 1) % len(polygon)][0] - origin_x) * (polygon[index][1] - origin_y)
        for index in range(len(polygon))
    )


####


def _cross(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    return first[0] * second[1] - first[1] * second[0]


####


def _validate_polygon(
    values: Any,
    name: str,
    tolerance_m: float,
) -> tuple[tuple[float, float], ...]:
    polygon = tuple(_finite_point(point, name) for point in values)
    if len(polygon) < 3:
        raise ValueError(f"{name} must contain at least three vertices")
    ####
    if any(np.hypot(second[0] - first[0], second[1] - first[1]) <= tolerance_m for first, second in zip(polygon, (*polygon[1:], polygon[0]))):
        raise ValueError(f"{name} contains a zero-length edge")
    ####
    area = _signed_area(polygon)
    if not isfinite(area) or abs(area) <= tolerance_m * tolerance_m:
        raise ValueError(f"{name} has degenerate area")
    ####
    orientation = 1.0 if area > 0.0 else -1.0
    turns = tuple(
        orientation
        * _cross(
            (second[0] - first[0], second[1] - first[1]),
            (third[0] - second[0], third[1] - second[1]),
        )
        for first, second, third in zip(
            polygon,
            (*polygon[1:], polygon[0]),
            (*polygon[2:], *polygon[:2]),
            strict=True,
        )
    )
    if any(value < -tolerance_m * tolerance_m for value in turns):
        raise ValueError(f"{name} must be convex and consistently ordered")
    ####
    return polygon


####


def _clean_polygon(
    polygon: list[tuple[float, float]],
    tolerance_m: float,
) -> tuple[tuple[float, float], ...]:
    clean: list[tuple[float, float]] = []
    for point in polygon:
        if not clean or np.hypot(point[0] - clean[-1][0], point[1] - clean[-1][1]) > tolerance_m:
            clean.append(point)
    ####
    if len(clean) > 1 and np.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) <= tolerance_m:
        clean.pop()
    ####
    return tuple(clean)


####


def _clip_convex_polygon(
    subject: tuple[tuple[float, float], ...],
    clip: tuple[tuple[float, float], ...],
    tolerance_m: float,
) -> tuple[tuple[float, float], ...]:
    """Intersect two convex polygons with oriented half-plane clipping."""

    output = list(subject)
    orientation = 1.0 if _signed_area(clip) > 0.0 else -1.0
    for edge_start, edge_end in zip(clip, (*clip[1:], clip[0])):
        if not output:
            return ()
        ####
        edge = (edge_end[0] - edge_start[0], edge_end[1] - edge_start[1])
        edge_length = float(np.hypot(*edge))
        threshold = edge_length * tolerance_m
        input_points = output
        output = []
        previous = input_points[-1]
        previous_distance = orientation * _cross(
            edge,
            (previous[0] - edge_start[0], previous[1] - edge_start[1]),
        )
        previous_inside = previous_distance >= -threshold
        for current in input_points:
            current_distance = orientation * _cross(
                edge,
                (current[0] - edge_start[0], current[1] - edge_start[1]),
            )
            current_inside = current_distance >= -threshold
            if current_inside != previous_inside:
                denominator = previous_distance - current_distance
                if abs(denominator) > 1.0e-30:
                    fraction = previous_distance / denominator
                    fraction = min(1.0, max(0.0, fraction))
                    output.append(
                        (
                            previous[0] + fraction * (current[0] - previous[0]),
                            previous[1] + fraction * (current[1] - previous[1]),
                        )
                    )
                ####
            ####
            if current_inside:
                output.append(current)
            ####
            previous = current
            previous_distance = current_distance
            previous_inside = current_inside
        ####
        output = list(_clean_polygon(output, tolerance_m))
    ####
    return tuple(output)


####


def _primitive(
    state: tuple[float, float, float, float],
    gamma: float,
) -> tuple[float, float]:
    density, momentum_x, momentum_y, energy = state
    if density <= 0.0:
        raise ValueError("conservative state density must be positive")
    ####
    pressure = (gamma - 1.0) * (energy - 0.5 * (momentum_x * momentum_x + momentum_y * momentum_y) / density)
    if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError("conservative state pressure must be positive")
    ####
    return density, pressure


def _entropy_density(
    state: tuple[float, float, float, float],
    gamma: float,
    gas_constant_J_kgK: float,
) -> float:
    """Return rho*s relative to K_ref=1 in the declared SI units."""

    density, pressure = _primitive(state, gamma)
    entropy_proxy = pressure / density**gamma
    specific_entropy = gas_constant_J_kgK / (gamma - 1.0) * log(entropy_proxy / _ENTROPY_PROXY_REFERENCE)
    value = density * specific_entropy
    if not isfinite(value):
        raise ValueError("specific entropy density must be finite")
    ####
    return value


####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest:
    """Exact source, target, and closure identities for one mesh overlap."""

    closure: MocReflectedDomainGlobalPhysicalClosureResult
    contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract
    source_reconciliation: MocPhysicalFieldEulerReconciliationResult
    downstream: MocReflectedDomainGlobalCoupledDownstreamResult
    position_tolerance_m: float = 1.0e-8

    def __post_init__(self) -> None:
        if not isinstance(self.closure, MocReflectedDomainGlobalPhysicalClosureResult):
            raise TypeError("closure must be a typed global physical closure")
        ####
        if not isinstance(
            self.contract,
            MocReflectedDomainGlobalMixedRegimeStateEquationContract,
        ):
            raise TypeError("contract must be a typed state-equation contract")
        ####
        if not isinstance(
            self.source_reconciliation,
            MocPhysicalFieldEulerReconciliationResult,
        ):
            raise TypeError("source_reconciliation must be a typed Euler result")
        ####
        if not isinstance(
            self.downstream,
            MocReflectedDomainGlobalCoupledDownstreamResult,
        ):
            raise TypeError("downstream must be a typed coupled-downstream result")
        ####
        if isinstance(self.position_tolerance_m, bool):
            raise ValueError("position_tolerance_m must not be boolean")
        ####
        tolerance = float(self.position_tolerance_m)
        if not isfinite(tolerance) or tolerance <= 0.0:
            raise ValueError("position_tolerance_m must be finite and positive")
        ####
        object.__setattr__(self, "position_tolerance_m", tolerance)

    ####

    def as_report(self) -> dict[str, Any]:
        return {
            "model": MOC_GLOBAL_MIXED_REGIME_CONSERVATIVE_MESH_OVERLAP_MODEL,
            "state_component_names": _STATE_COMPONENT_NAMES,
            "source_closure_fingerprint": (moc_reflected_domain_global_physical_closure_fingerprint(self.closure)),
            "position_tolerance_m": self.position_tolerance_m,
            "source_cell_count": len(self.source_reconciliation.cell_vertices_by_cell_m),
            "downstream_cell_count": (0 if self.downstream.coupled_field is None else len(self.downstream.coupled_field.cell_vertices_by_cell_m)),
            "research_only": True,
            "global_coupling_verified": False,
            "production_claim_allowed": False,
        }

    ####


####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCellOverlapFragment:
    """One exact convex polygon shared by a source and downstream cell."""

    source_cell_index: int
    downstream_cell_index: int
    intersection_polygon_m: tuple[tuple[float, float], ...]
    area_m2: float

    def __post_init__(self) -> None:
        for name in ("source_cell_index", "downstream_cell_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        ####
        polygon = tuple(_finite_point(point, "intersection_polygon_m") for point in self.intersection_polygon_m)
        if len(polygon) < 3 or abs(_signed_area(polygon)) <= 0.0:
            raise ValueError("intersection polygon must have positive area")
        ####
        area = float(self.area_m2)
        if not isfinite(area) or area <= 0.0:
            raise ValueError("area_m2 must be finite and positive")
        ####
        if abs(abs(_signed_area(polygon)) - area) > max(1.0e-14, area * 1.0e-10):
            raise ValueError("area_m2 must match the retained intersection polygon")
        ####
        object.__setattr__(self, "intersection_polygon_m", polygon)
        object.__setattr__(self, "area_m2", area)

    ####


####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult:
    """Conservative common-area remap and state mismatch, without feedback."""

    status: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus
    request: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest | None
    source_closure_fingerprint: str | None = None
    overlap_fragments: tuple[MocReflectedDomainGlobalMixedRegimeCellOverlapFragment, ...] = ()
    downstream_cell_areas_m2: tuple[float, ...] = ()
    downstream_covered_areas_m2: tuple[float, ...] = ()
    downstream_coverage_fractions: tuple[float, ...] = ()
    source_remapped_states_by_downstream_cell: tuple[tuple[float, float, float, float] | None, ...] = ()
    downstream_relative_state_residuals_by_cell: tuple[tuple[float, float, float, float] | None, ...] = ()
    source_remapped_entropy_density_by_downstream_cell_J_m3K: tuple[float | None, ...] = ()
    downstream_relative_entropy_density_residuals_by_cell: tuple[float | None, ...] = ()
    source_integral_on_overlap: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    downstream_integral_on_overlap: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    integrated_state_residual: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    integrated_relative_state_residual: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    source_entropy_inventory_on_overlap_J_K_per_m: float = 0.0
    downstream_entropy_inventory_on_overlap_J_K_per_m: float = 0.0
    integrated_entropy_inventory_residual_J_K_per_m: float = 0.0
    integrated_relative_entropy_inventory_residual: float = 0.0
    maximum_absolute_entropy_proxy_log_residual: float | None = None
    target_boundary_face_midpoints_verified: bool = False
    source_lineage_verified: bool = False
    downstream_lineage_verified: bool = False
    mesh_geometry_verified: bool = False
    full_downstream_coverage_verified: bool = False
    conservative_remap_verified: bool = False
    overlap_residuals_measured: bool = False
    independent_audit_verified: bool = False
    global_coupling_verified: bool = False
    chain_promotion_blocked: bool = True
    production_claim_allowed: bool = False
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus,
        ):
            raise TypeError("status must be a typed conservative-overlap status")
        ####
        if self.request is not None and not isinstance(
            self.request,
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest,
        ):
            raise TypeError("request must be a typed conservative-overlap request")
        ####
        for name in (
            "target_boundary_face_midpoints_verified",
            "source_lineage_verified",
            "downstream_lineage_verified",
            "mesh_geometry_verified",
            "full_downstream_coverage_verified",
            "conservative_remap_verified",
            "overlap_residuals_measured",
            "independent_audit_verified",
            "global_coupling_verified",
            "chain_promotion_blocked",
            "production_claim_allowed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        ####
        if self.global_coupling_verified or self.production_claim_allowed:
            raise ValueError("mesh overlap evidence cannot claim coupling or production")
        ####
        if not self.chain_promotion_blocked:
            raise ValueError("mesh overlap evidence must block chain promotion")
        ####
        object.__setattr__(self, "overlap_fragments", tuple(self.overlap_fragments))
        object.__setattr__(
            self,
            "downstream_cell_areas_m2",
            tuple(float(value) for value in self.downstream_cell_areas_m2),
        )
        object.__setattr__(
            self,
            "downstream_covered_areas_m2",
            tuple(float(value) for value in self.downstream_covered_areas_m2),
        )
        object.__setattr__(
            self,
            "downstream_coverage_fractions",
            tuple(float(value) for value in self.downstream_coverage_fractions),
        )
        object.__setattr__(
            self,
            "source_remapped_states_by_downstream_cell",
            tuple(self.source_remapped_states_by_downstream_cell),
        )
        object.__setattr__(
            self,
            "downstream_relative_state_residuals_by_cell",
            tuple(self.downstream_relative_state_residuals_by_cell),
        )
        for name in (
            "source_remapped_entropy_density_by_downstream_cell_J_m3K",
            "downstream_relative_entropy_density_residuals_by_cell",
        ):
            values = tuple(None if value is None else float(value) for value in getattr(self, name))
            if any(value is not None and not isfinite(value) for value in values):
                raise ValueError(f"{name} must contain finite values or None")
            ####
            object.__setattr__(self, name, values)
        ####
        for name in (
            "source_integral_on_overlap",
            "downstream_integral_on_overlap",
            "integrated_state_residual",
            "integrated_relative_state_residual",
        ):
            values = tuple(float(value) for value in getattr(self, name))
            if len(values) != 4 or any(not isfinite(value) for value in values):
                raise ValueError(f"{name} must contain four finite components")
            ####
            object.__setattr__(self, name, values)
        ####
        for name in (
            "source_entropy_inventory_on_overlap_J_K_per_m",
            "downstream_entropy_inventory_on_overlap_J_K_per_m",
            "integrated_entropy_inventory_residual_J_K_per_m",
            "integrated_relative_entropy_inventory_residual",
        ):
            value = float(getattr(self, name))
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            ####
            object.__setattr__(self, name, value)
        ####
        if self.maximum_absolute_entropy_proxy_log_residual is not None:
            value = float(self.maximum_absolute_entropy_proxy_log_residual)
            if not isfinite(value) or value < 0.0:
                raise ValueError("maximum_absolute_entropy_proxy_log_residual must be finite and nonnegative")
            ####
            object.__setattr__(self, "maximum_absolute_entropy_proxy_log_residual", value)
        ####
        object.__setattr__(self, "message", str(self.message))

    ####

    @property
    def local_overlap_verified(self) -> bool:
        return bool(
            self.status is MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.VERIFIED_RESEARCH_OVERLAP
            and self.target_boundary_face_midpoints_verified
            and self.source_lineage_verified
            and self.downstream_lineage_verified
            and self.mesh_geometry_verified
            and self.full_downstream_coverage_verified
            and self.conservative_remap_verified
            and self.overlap_residuals_measured
            and self.independent_audit_verified
        )

    ####

    def as_report(self) -> dict[str, Any]:
        return {
            "model": MOC_GLOBAL_MIXED_REGIME_CONSERVATIVE_MESH_OVERLAP_MODEL,
            "state_component_names": _STATE_COMPONENT_NAMES,
            "status": self.status.value,
            "local_overlap_verified": self.local_overlap_verified,
            "source_closure_fingerprint": self.source_closure_fingerprint,
            "source_cell_count": (0 if self.request is None else len(self.request.source_reconciliation.cell_vertices_by_cell_m)),
            "downstream_cell_count": len(self.downstream_cell_areas_m2),
            "overlap_fragment_count": len(self.overlap_fragments),
            "overlap_area_m2": sum(fragment.area_m2 for fragment in self.overlap_fragments),
            "downstream_cell_areas_m2": self.downstream_cell_areas_m2,
            "downstream_covered_areas_m2": self.downstream_covered_areas_m2,
            "downstream_coverage_fractions": self.downstream_coverage_fractions,
            "source_remapped_states_by_downstream_cell": (self.source_remapped_states_by_downstream_cell),
            "downstream_relative_state_residuals_by_cell": (self.downstream_relative_state_residuals_by_cell),
            "source_remapped_entropy_density_by_downstream_cell_J_m3K": (self.source_remapped_entropy_density_by_downstream_cell_J_m3K),
            "downstream_relative_entropy_density_residuals_by_cell": (self.downstream_relative_entropy_density_residuals_by_cell),
            "source_integral_on_overlap": self.source_integral_on_overlap,
            "downstream_integral_on_overlap": self.downstream_integral_on_overlap,
            "integrated_state_residual": self.integrated_state_residual,
            "integrated_relative_state_residual": self.integrated_relative_state_residual,
            "entropy_proxy_reference": _ENTROPY_PROXY_REFERENCE,
            "source_entropy_inventory_on_overlap_J_K_per_m": (self.source_entropy_inventory_on_overlap_J_K_per_m),
            "downstream_entropy_inventory_on_overlap_J_K_per_m": (self.downstream_entropy_inventory_on_overlap_J_K_per_m),
            "integrated_entropy_inventory_residual_J_K_per_m": (self.integrated_entropy_inventory_residual_J_K_per_m),
            "integrated_relative_entropy_inventory_residual": (self.integrated_relative_entropy_inventory_residual),
            "maximum_absolute_entropy_proxy_log_residual": (self.maximum_absolute_entropy_proxy_log_residual),
            "target_boundary_face_midpoints_verified": (self.target_boundary_face_midpoints_verified),
            "source_lineage_verified": self.source_lineage_verified,
            "downstream_lineage_verified": self.downstream_lineage_verified,
            "mesh_geometry_verified": self.mesh_geometry_verified,
            "full_downstream_coverage_verified": self.full_downstream_coverage_verified,
            "conservative_remap_verified": self.conservative_remap_verified,
            "overlap_residuals_measured": self.overlap_residuals_measured,
            "independent_audit_verified": self.independent_audit_verified,
            "global_coupling_verified": False,
            "chain_promotion_blocked": True,
            "production_claim_allowed": False,
            "claim_status": ("research-only-conservative-overlap-remap; the overlap data are not consumed by a fresh two-domain PDE solve"),
            "message": self.message,
        }

    ####


####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit:
    """Independent replay of geometry, coverage, remap, and residuals."""

    status: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus
    candidate: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult | None
    geometry_recomputed: bool = False
    coverage_recomputed: bool = False
    remap_recomputed: bool = False
    residuals_recomputed: bool = False
    lineage_recomputed: bool = False
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus,
        ):
            raise TypeError("status must be a typed overlap-audit status")
        ####
        for name in (
            "geometry_recomputed",
            "coverage_recomputed",
            "remap_recomputed",
            "residuals_recomputed",
            "lineage_recomputed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        ####
        object.__setattr__(self, "message", str(self.message))

    ####

    @property
    def verified(self) -> bool:
        return bool(
            self.status is MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus.VERIFIED_RESEARCH_OVERLAP_REPLAY
            and self.geometry_recomputed
            and self.coverage_recomputed
            and self.remap_recomputed
            and self.residuals_recomputed
            and self.lineage_recomputed
        )

    ####


####


def _state_profile(values: Any, name: str) -> tuple[tuple[float, ...], ...]:
    rows = tuple(tuple(row) for row in values)
    if any(isinstance(value, bool) for row in rows for value in row):
        raise ValueError(f"{name} must not contain boolean state components")
    ####
    states = tuple(tuple(float(value) for value in row) for row in rows)
    if any(len(state) != 4 or any(not isfinite(value) for value in state) for state in states):
        raise ValueError(f"{name} must contain finite four-component states")
    ####
    return states


####


def _mesh_inputs(
    request: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest,
) -> tuple[
    tuple[tuple[tuple[float, float], ...], ...],
    tuple[tuple[float, float, float, float], ...],
    tuple[tuple[tuple[float, float], ...], ...],
    tuple[tuple[float, float, float, float], ...],
    float,
    float,
]:
    reconciliation = request.source_reconciliation
    downstream = request.downstream.coupled_field
    if downstream is None:
        raise _LineageFailure("downstream result has no retained coupled field")
    ####
    source_polygons = tuple(_validate_polygon(polygon, "source cell polygon", request.position_tolerance_m) for polygon in reconciliation.cell_vertices_by_cell_m)
    downstream_polygons = tuple(_validate_polygon(polygon, "downstream cell polygon", request.position_tolerance_m) for polygon in downstream.cell_vertices_by_cell_m)
    source_states = _state_profile(
        reconciliation.conservative_states_by_cell,
        "source reconciliation states",
    )
    downstream_states = _state_profile(
        downstream.conservative_states_by_cell,
        "downstream conservative states",
    )
    if not source_polygons or len(source_polygons) != len(source_states):
        raise _GeometryFailure("source mesh polygons and states are empty or misaligned")
    ####
    if not downstream_polygons or len(downstream_polygons) != len(downstream_states):
        raise _GeometryFailure("downstream mesh polygons and states are empty or misaligned")
    ####
    source_request = reconciliation.request
    if source_request is None or source_request.shock_front_condition.field is None:
        raise _LineageFailure("source reconciliation has no exact source-field request")
    ####
    physical = request.closure.global_euler
    physical = None if physical is None else physical.physical_field
    field = None if physical is None else physical.field
    if field is None or source_request.shock_front_condition.field is not field:
        raise _LineageFailure("source reconciliation is not bound to the exact closure field")
    ####
    source_gamma = float(field.post_shock_boundary_states[0].gamma)
    downstream_request = downstream.request
    if downstream_request is None:
        raise ValueError("downstream field has no retained solver request")
    ####
    downstream_gamma = float(downstream_request.mixed_regime_request.control_section.samples[0].gamma)
    if abs(source_gamma - downstream_gamma) > 1.0e-8:
        raise _StateFailure("source and downstream gamma differ across the overlap")
    ####
    for state in (*source_states, *downstream_states):
        try:
            _primitive(state, source_gamma)
        except ValueError as error:
            raise _StateFailure(str(error)) from error
    ####
    source_gas_constant = float(source_request.gas_constant_J_kgK)
    downstream_gas_constant = float(downstream_request.gas_constant_J_kgK)
    if abs(source_gas_constant - downstream_gas_constant) > 1.0e-10:
        raise _StateFailure("source and downstream gas constants differ across the overlap")
    ####
    return (
        source_polygons,
        tuple(tuple(state) for state in source_states),
        downstream_polygons,
        tuple(tuple(state) for state in downstream_states),
        source_gamma,
        source_gas_constant,
    )


####


def _lineage_status(
    request: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest,
) -> tuple[bool, bool, bool]:
    fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(request.closure)
    source_field = request.closure.global_euler
    source_field = None if source_field is None else source_field.physical_field
    source_field = None if source_field is None else source_field.field
    consumer = request.contract.consumer
    source_ok = bool(
        request.contract.closure is request.closure
        and request.contract.source_closure_fingerprint == fingerprint
        and consumer is not None
        and consumer.closure is request.closure
        and consumer.downstream is request.downstream
        and consumer.source_closure_fingerprint == fingerprint
        and consumer.full_state_trace_consumed
        and request.contract.state_target_frame_verified
        and request.contract.state_target_ready
        and request.source_reconciliation.converged
        and request.source_reconciliation.request is not None
        and request.source_reconciliation.request.shock_front_condition.field is source_field
    )
    downstream_ok = bool(
        request.downstream.closure is request.closure
        and request.downstream.closure_lineage_verified
        and request.downstream.coupled_field is not None
        and request.downstream.coupled_field_audit is not None
        and request.downstream.coupled_field_audit.converged
        and request.downstream.coupled_field_audit.candidate is request.downstream.coupled_field
    )
    target_ok = False
    if request.downstream.coupled_field is not None:
        boundary = request.downstream.coupled_field.free_boundary_points_m
        expected_midpoints = tuple(
            (
                0.5 * (first[0] + second[0]),
                0.5 * (first[1] + second[1]),
            )
            for first, second in zip(boundary, boundary[1:])
        )
        target_points = request.contract.conservative_state_profile_points_m
        target_ok = bool(
            len(expected_midpoints) == len(target_points)
            and all(max(abs(actual[axis] - expected[axis]) for axis in (0, 1)) <= request.position_tolerance_m for actual, expected in zip(target_points, expected_midpoints, strict=True))
        )
    ####
    return source_ok, downstream_ok, target_ok


####


def _compute_overlap(
    request: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest,
) -> dict[str, Any]:
    source_ok, downstream_ok, target_ok = _lineage_status(request)
    if not source_ok or not downstream_ok:
        raise _LineageFailure("source reconciliation and downstream field must share the exact closure identity and pass their local audits")
    ####
    if not target_ok:
        raise _GeometryFailure("contract target points do not match the retained downstream free-boundary face midpoints")
    ####
    (
        source_polygons,
        source_states,
        downstream_polygons,
        downstream_states,
        gamma,
        gas_constant,
    ) = _mesh_inputs(request)
    ####
    fragments: list[MocReflectedDomainGlobalMixedRegimeCellOverlapFragment] = []
    covered_areas = [0.0] * len(downstream_polygons)
    remap_integrals = [[0.0] * 4 for _ in downstream_polygons]
    remap_entropy_integrals = [0.0] * len(downstream_polygons)
    source_integral = [0.0] * 4
    downstream_integral = [0.0] * 4
    source_entropy_inventory = 0.0
    downstream_entropy_inventory = 0.0
    entropy_residuals: list[float] = []
    for source_index, source_polygon in enumerate(source_polygons):
        source_x = tuple(point[0] for point in source_polygon)
        source_y = tuple(point[1] for point in source_polygon)
        for downstream_index, downstream_polygon in enumerate(downstream_polygons):
            if (
                max(source_x) < min(point[0] for point in downstream_polygon)
                or max(point[0] for point in downstream_polygon) < min(source_x)
                or max(source_y) < min(point[1] for point in downstream_polygon)
                or max(point[1] for point in downstream_polygon) < min(source_y)
            ):
                continue
            ####
            intersection = _clip_convex_polygon(
                downstream_polygon,
                source_polygon,
                request.position_tolerance_m,
            )
            if len(intersection) < 3:
                continue
            ####
            area = abs(_signed_area(intersection))
            area_floor = request.position_tolerance_m**2
            if area <= area_floor:
                continue
            ####
            fragment = MocReflectedDomainGlobalMixedRegimeCellOverlapFragment(
                source_cell_index=source_index,
                downstream_cell_index=downstream_index,
                intersection_polygon_m=intersection,
                area_m2=area,
            )
            fragments.append(fragment)
            covered_areas[downstream_index] += area
            for component in range(4):
                remap_integrals[downstream_index][component] += source_states[source_index][component] * area
                source_integral[component] += source_states[source_index][component] * area
                downstream_integral[component] += downstream_states[downstream_index][component] * area
            ####
            source_entropy_density = _entropy_density(
                source_states[source_index],
                gamma,
                gas_constant,
            )
            target_entropy_density = _entropy_density(
                downstream_states[downstream_index],
                gamma,
                gas_constant,
            )
            remap_entropy_integrals[downstream_index] += source_entropy_density * area
            source_entropy_inventory += source_entropy_density * area
            downstream_entropy_inventory += target_entropy_density * area
            ####
            source_density, source_pressure = _primitive(source_states[source_index], gamma)
            target_density, target_pressure = _primitive(
                downstream_states[downstream_index],
                gamma,
            )
            source_entropy = source_pressure / source_density**gamma
            target_entropy = target_pressure / target_density**gamma
            entropy_residuals.append(abs(log(source_entropy / target_entropy)))
        ####
    ####
    cell_areas = tuple(abs(_signed_area(polygon)) for polygon in downstream_polygons)
    fractions = tuple(covered / area for covered, area in zip(covered_areas, cell_areas, strict=True))
    remapped_states: list[tuple[float, float, float, float] | None] = []
    relative_residuals: list[tuple[float, float, float, float] | None] = []
    remapped_entropy_density: list[float | None] = []
    relative_entropy_density_residuals: list[float | None] = []
    for index, covered in enumerate(covered_areas):
        if covered <= request.position_tolerance_m**2:
            remapped_states.append(None)
            relative_residuals.append(None)
            remapped_entropy_density.append(None)
            relative_entropy_density_residuals.append(None)
            continue
        ####
        mapped = tuple(value / covered for value in remap_integrals[index])
        _primitive(mapped, gamma)
        residual = tuple(
            (target - actual) / max(abs(target), 1.0e-12)
            for actual, target in zip(
                mapped,
                downstream_states[index],
                strict=True,
            )
        )
        remapped_states.append(mapped)
        relative_residuals.append(residual)
        mapped_entropy_density = remap_entropy_integrals[index] / covered
        target_entropy_density = _entropy_density(
            downstream_states[index],
            gamma,
            gas_constant,
        )
        remapped_entropy_density.append(mapped_entropy_density)
        relative_entropy_density_residuals.append(
            (target_entropy_density - mapped_entropy_density)
            / max(
                abs(target_entropy_density),
                abs(mapped_entropy_density),
                1.0e-12,
            )
        )
    ####
    residual = tuple(target - source for source, target in zip(source_integral, downstream_integral, strict=True))
    relative_integral = tuple(
        value / max(abs(source), abs(target), 1.0e-12)
        for value, source, target in zip(
            residual,
            source_integral,
            downstream_integral,
            strict=True,
        )
    )
    entropy_residual = downstream_entropy_inventory - source_entropy_inventory
    relative_entropy_residual = entropy_residual / max(
        abs(source_entropy_inventory),
        abs(downstream_entropy_inventory),
        1.0e-12,
    )
    coverage_tolerances = tuple(
        max(
            1.0e-10,
            10.0 * request.position_tolerance_m / max(sqrt(area), 1.0e-12),
        )
        for area in cell_areas
    )
    full_coverage = bool(all(abs(fraction - 1.0) <= tolerance for fraction, tolerance in zip(fractions, coverage_tolerances, strict=True)))
    mesh_geometry_verified = bool(
        len(fragments) > 0
        and all(isfinite(fragment.area_m2) and fragment.area_m2 > 0.0 for fragment in fragments)
        and all(fraction <= 1.0 + tolerance for fraction, tolerance in zip(fractions, coverage_tolerances, strict=True))
    )
    remap_conservative = bool(
        all(covered > request.position_tolerance_m**2 for covered in covered_areas)
        and all(state is not None for state in remapped_states)
        and all(value is not None for value in remapped_entropy_density)
        and all(
            abs(sum(mapped[component] * covered_areas[index] for index, mapped in enumerate(remapped_states) if mapped is not None) - source_integral[component])
            <= 1.0e-12 * max(abs(source_integral[component]), 1.0)
            for component in range(4)
        )
        and abs(sum(value * covered_areas[index] for index, value in enumerate(remapped_entropy_density) if value is not None) - source_entropy_inventory)
        <= 1.0e-12 * max(abs(source_entropy_inventory), 1.0)
    )
    return {
        "source_closure_fingerprint": (moc_reflected_domain_global_physical_closure_fingerprint(request.closure)),
        "overlap_fragments": tuple(fragments),
        "downstream_cell_areas_m2": cell_areas,
        "downstream_covered_areas_m2": tuple(covered_areas),
        "downstream_coverage_fractions": fractions,
        "source_remapped_states_by_downstream_cell": tuple(remapped_states),
        "downstream_relative_state_residuals_by_cell": tuple(relative_residuals),
        "source_remapped_entropy_density_by_downstream_cell_J_m3K": tuple(remapped_entropy_density),
        "downstream_relative_entropy_density_residuals_by_cell": tuple(relative_entropy_density_residuals),
        "source_integral_on_overlap": tuple(source_integral),
        "downstream_integral_on_overlap": tuple(downstream_integral),
        "integrated_state_residual": residual,
        "integrated_relative_state_residual": relative_integral,
        "source_entropy_inventory_on_overlap_J_K_per_m": source_entropy_inventory,
        "downstream_entropy_inventory_on_overlap_J_K_per_m": downstream_entropy_inventory,
        "integrated_entropy_inventory_residual_J_K_per_m": entropy_residual,
        "integrated_relative_entropy_inventory_residual": relative_entropy_residual,
        "maximum_absolute_entropy_proxy_log_residual": max(entropy_residuals, default=None),
        "target_boundary_face_midpoints_verified": target_ok,
        "source_lineage_verified": source_ok,
        "downstream_lineage_verified": downstream_ok,
        "mesh_geometry_verified": mesh_geometry_verified,
        "full_downstream_coverage_verified": full_coverage,
        "conservative_remap_verified": remap_conservative,
        "overlap_residuals_measured": bool(fragments and all(isfinite(value) for value in residual) and isfinite(entropy_residual) and isfinite(relative_entropy_residual)),
    }


####


def _failure(
    status: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus,
    request: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest | None,
    message: str,
) -> MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult:
    return MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult(
        status=status,
        request=request,
        message=message,
    )


####


def measure_reflected_domain_global_mixed_regime_conservative_mesh_overlap(
    request: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest,
) -> MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult:
    """Remap fixed-front source states onto the exact downstream cell mesh."""

    if not isinstance(
        request,
        MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapRequest,
    ):
        return _failure(
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.INVALID_INPUT,
            None,
            "request must be a typed conservative mesh-overlap request",
        )
    ####
    try:
        values = _compute_overlap(request)
    except _LineageFailure as error:
        return _failure(
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.LINEAGE_FAILURE,
            request,
            str(error),
        )
    except _StateFailure as error:
        return _failure(
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.STATE_FAILURE,
            request,
            str(error),
        )
    except _GeometryFailure as error:
        return _failure(
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.GEOMETRY_FAILURE,
            request,
            str(error),
        )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError, IndexError) as error:
        return _failure(
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.GEOMETRY_FAILURE,
            request,
            str(error),
        )
    ####
    lineage_verified = bool(values["source_lineage_verified"] and values["downstream_lineage_verified"] and values["target_boundary_face_midpoints_verified"])
    coverage_verified = bool(values["mesh_geometry_verified"] and values["full_downstream_coverage_verified"])
    remap_verified = bool(values["conservative_remap_verified"])
    status = (
        MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.VERIFIED_RESEARCH_OVERLAP
        if lineage_verified and coverage_verified and remap_verified
        else MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.PARTIAL_OVERLAP_DIAGNOSTIC
    )
    message = (
        "exact source/downstream cell overlap is fully covered and conservatively remapped; the overlap mismatch remains a diagnostic and is not consumed by a fresh two-domain solve"
        if status is (MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapStatus.VERIFIED_RESEARCH_OVERLAP)
        else "overlap, target geometry, or lineage is incomplete; no extrapolation was used"
    )
    provisional = MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult(
        status=status,
        request=request,
        message=message,
        **values,
    )
    ####
    audit = audit_reflected_domain_global_mixed_regime_conservative_mesh_overlap(provisional)
    return replace(provisional, independent_audit_verified=audit.verified)


####


def _close_tuple(
    first: tuple[float, ...],
    second: tuple[float, ...],
    *,
    tolerance: float,
) -> bool:
    return bool(len(first) == len(second) and all(abs(left - right) <= tolerance * max(abs(left), abs(right), 1.0) for left, right in zip(first, second, strict=True)))


def _close_scalar(first: float, second: float, *, tolerance: float) -> bool:
    return abs(first - second) <= tolerance * max(abs(first), abs(second), 1.0)


####


def audit_reflected_domain_global_mixed_regime_conservative_mesh_overlap(
    candidate: MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
) -> MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit:
    """Rebuild polygon intersections and recompute every overlap integral."""

    if (
        not isinstance(
            candidate,
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
        )
        or candidate.request is None
    ):
        return MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit(
            status=(MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus.INVALID_INPUT),
            candidate=candidate
            if isinstance(
                candidate,
                MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapResult,
            )
            else None,
            message="candidate must retain its exact overlap request",
        )
    ####
    try:
        replay = _compute_overlap(candidate.request)
    except _LineageFailure as error:
        return MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit(
            status=(MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus.LINEAGE_FAILURE),
            candidate=candidate,
            message=str(error),
        )
    except (
        _StateFailure,
        _GeometryFailure,
        ArithmeticError,
        FloatingPointError,
        TypeError,
        ValueError,
        IndexError,
    ) as error:
        return MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit(
            status=(MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus.REPLAY_FAILURE),
            candidate=candidate,
            message=str(error),
        )
    ####
    tolerance = max(1.0e-12, candidate.request.position_tolerance_m * 1.0e-6)
    geometry = bool(
        len(candidate.overlap_fragments) == len(replay["overlap_fragments"])
        and all(
            left.source_cell_index == right.source_cell_index
            and left.downstream_cell_index == right.downstream_cell_index
            and left.intersection_polygon_m == right.intersection_polygon_m
            and abs(left.area_m2 - right.area_m2) <= tolerance
            for left, right in zip(
                candidate.overlap_fragments,
                replay["overlap_fragments"],
                strict=True,
            )
        )
    )
    coverage = bool(
        _close_tuple(
            candidate.downstream_cell_areas_m2,
            replay["downstream_cell_areas_m2"],
            tolerance=tolerance,
        )
        and _close_tuple(
            candidate.downstream_covered_areas_m2,
            replay["downstream_covered_areas_m2"],
            tolerance=tolerance,
        )
        and _close_tuple(
            candidate.downstream_coverage_fractions,
            replay["downstream_coverage_fractions"],
            tolerance=tolerance,
        )
    )
    remap = len(candidate.source_remapped_states_by_downstream_cell) == len(replay["source_remapped_states_by_downstream_cell"]) and all(
        left is None and right is None or left is not None and right is not None and _close_tuple(left, right, tolerance=tolerance)
        for left, right in zip(
            candidate.source_remapped_states_by_downstream_cell,
            replay["source_remapped_states_by_downstream_cell"],
            strict=True,
        )
    )
    entropy_remap = len(candidate.source_remapped_entropy_density_by_downstream_cell_J_m3K) == len(replay["source_remapped_entropy_density_by_downstream_cell_J_m3K"]) and all(
        left is None and right is None or left is not None and right is not None and abs(left - right) <= tolerance * max(abs(left), abs(right), 1.0)
        for left, right in zip(
            candidate.source_remapped_entropy_density_by_downstream_cell_J_m3K,
            replay["source_remapped_entropy_density_by_downstream_cell_J_m3K"],
            strict=True,
        )
    )
    remap = bool(remap and entropy_remap)
    cell_residuals = len(candidate.downstream_relative_state_residuals_by_cell) == len(replay["downstream_relative_state_residuals_by_cell"]) and all(
        left is None and right is None or left is not None and right is not None and _close_tuple(left, right, tolerance=tolerance)
        for left, right in zip(
            candidate.downstream_relative_state_residuals_by_cell,
            replay["downstream_relative_state_residuals_by_cell"],
            strict=True,
        )
    )
    entropy_cell_residuals = len(candidate.downstream_relative_entropy_density_residuals_by_cell) == len(replay["downstream_relative_entropy_density_residuals_by_cell"]) and all(
        left is None and right is None or left is not None and right is not None and abs(left - right) <= tolerance * max(abs(left), abs(right), 1.0)
        for left, right in zip(
            candidate.downstream_relative_entropy_density_residuals_by_cell,
            replay["downstream_relative_entropy_density_residuals_by_cell"],
            strict=True,
        )
    )
    residuals = all(
        _close_tuple(getattr(candidate, name), replay[name], tolerance=tolerance)
        for name in (
            "source_integral_on_overlap",
            "downstream_integral_on_overlap",
            "integrated_state_residual",
            "integrated_relative_state_residual",
        )
    )
    residuals = bool(
        residuals
        and all(
            _close_scalar(
                getattr(candidate, name),
                replay[name],
                tolerance=tolerance,
            )
            for name in (
                "source_entropy_inventory_on_overlap_J_K_per_m",
                "downstream_entropy_inventory_on_overlap_J_K_per_m",
                "integrated_entropy_inventory_residual_J_K_per_m",
                "integrated_relative_entropy_inventory_residual",
            )
        )
    )
    entropy_value = replay["maximum_absolute_entropy_proxy_log_residual"]
    if entropy_value is None:
        entropy_matches = candidate.maximum_absolute_entropy_proxy_log_residual is None
    else:
        entropy_matches = bool(
            candidate.maximum_absolute_entropy_proxy_log_residual is not None and abs(candidate.maximum_absolute_entropy_proxy_log_residual - entropy_value) <= tolerance * max(abs(entropy_value), 1.0)
        )
    ####
    residuals = bool(residuals and cell_residuals and entropy_cell_residuals and entropy_matches)
    lineage = bool(
        candidate.source_closure_fingerprint == replay["source_closure_fingerprint"]
        and candidate.source_lineage_verified == replay["source_lineage_verified"]
        and candidate.downstream_lineage_verified == replay["downstream_lineage_verified"]
        and candidate.target_boundary_face_midpoints_verified == replay["target_boundary_face_midpoints_verified"]
        and candidate.mesh_geometry_verified == replay["mesh_geometry_verified"]
        and candidate.full_downstream_coverage_verified == replay["full_downstream_coverage_verified"]
        and candidate.conservative_remap_verified == replay["conservative_remap_verified"]
        and candidate.overlap_residuals_measured == replay["overlap_residuals_measured"]
    )
    verified = bool(geometry and coverage and remap and residuals and lineage)
    return MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAudit(
        status=(
            MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus.VERIFIED_RESEARCH_OVERLAP_REPLAY
            if verified
            else MocReflectedDomainGlobalMixedRegimeConservativeMeshOverlapAuditStatus.REPLAY_FAILURE
        ),
        candidate=candidate,
        geometry_recomputed=geometry,
        coverage_recomputed=coverage,
        remap_recomputed=remap,
        residuals_recomputed=residuals,
        lineage_recomputed=lineage,
        message=("cell intersections, exact coverage, conservative remap, and residuals were independently replayed" if verified else "retained overlap evidence differs from independent replay"),
    )


####
