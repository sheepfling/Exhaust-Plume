"""Explicit signature bridges for the standardized plume-model lanes.

Flow models do not become spectral signatures merely because they contain
temperature, pressure, or a visual envelope.  This module makes the missing
radiation seam explicit.  The three straight lanes can be evaluated through
the bounded ray-transfer provider when a caller supplies an optical profile;
that profile may be gray or an explicit LTE line source.  Curved integral and
planar-MOC lanes remain typed transport blocks until their own optical
geometry providers exist.

The resulting signature is either a gray approximation or explicit spectral
engineering evidence.  It carries the flow-lane lineage and claim ceiling.
Caller-bound LTE population closures are allowed as source engineering
inputs, but this bridge does not claim reactions, non-LTE population closure,
atmosphere, detector response, or external validation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Any, TypeAlias, cast

import numpy as np

from exhaust_plume.api.v1 import (
    ApplicabilityStatus,
    Derivation,
    GeometryClaim,
    Pose,
    ProductClaims,
    RadiationClaim,
    SpectralRayTransferRequest,
    SpectralSignatureResult,
    SPECTRAL_RAY_TRANSFER_V1,
    TimeModel,
    canonical_digest,
)
from exhaust_plume.geometry import SectionedTubeSupport
from exhaust_plume.products.model_visualization import (
    ModelVisualizationLane,
    StandardizedModelVisualization,
)
from exhaust_plume.providers.gray_ray_transfer import (
    GrayRayTransferConfiguration,
    GrayRayTransferDefinition,
    GrayRayTransferProvider,
)
from exhaust_plume.providers.curved_gray_ray_transfer import CurvedGrayRayTransferProvider
from exhaust_plume.radiation import (
    FarFieldRayIntegration,
    LineRadiationProfile,
    LtePopulationClosure,
    LteTransition,
    SectionedLineRadiationProfile,
    SpectralLine,
    far_field_from_rays,
    planck_spectral_radiance_W_m2_sr_m,
)

__all__ = (
    "GRAY_MODEL_SIGNATURE_ADAPTER_SCHEMA",
    "LINE_MODEL_SIGNATURE_ADAPTER_SCHEMA",
    "SECTIONED_LINE_MODEL_SIGNATURE_ADAPTER_SCHEMA",
    "GrayRadiationProfile",
    "GrayOpticalProfile",
    "LineRadiationProfile",
    "LtePopulationClosure",
    "LteTransition",
    "SectionedLineRadiationProfile",
    "SpectralLine",
    "SectionedGrayRadiationProfile",
    "ModelSignatureAssessment",
    "ModelSignatureBlockedError",
    "ModelSignatureReadiness",
    "ModelSignatureSampling",
    "assess_model_signature_readiness",
    "evaluate_model_signature",
)


GRAY_MODEL_SIGNATURE_ADAPTER_SCHEMA = "plume.signature.model-gray-bridge@1"
LINE_MODEL_SIGNATURE_ADAPTER_SCHEMA = "plume.signature.model-lte-line-bridge@1"
SECTIONED_LINE_MODEL_SIGNATURE_ADAPTER_SCHEMA = (
    "plume.signature.model-lte-line-sectioned-bridge@1"
)

Vector3: TypeAlias = tuple[float, float, float]

_STRAIGHT_SIGNATURE_LANES = frozenset(
    {
        ModelVisualizationLane.BASIC_SHOCK_CELL,
        ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN,
        ModelVisualizationLane.STRAIGHT_INTEGRAL,
    }
)
_CURVED_SIGNATURE_LANES = frozenset({ModelVisualizationLane.CURVED_INTEGRAL})


def _finite(name: str, value: object) -> float:
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    ####
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    ####
    return numeric
####


def _unit_vector(name: str, value: Sequence[float]) -> Vector3:
    if len(value) != 3:
        raise ValueError(f"{name} must contain three coordinates")
    ####
    vector = tuple(_finite(f"{name}[{index}]", component) for index, component in enumerate(value))
    norm = sqrt(sum(component * component for component in vector))
    if abs(norm - 1.0) > 1.0e-6:
        raise ValueError(f"{name} must be unit length")
    ####
    return tuple(component / norm for component in vector)  # type: ignore[return-value]
####


def _strict_axis(name: str, values: Sequence[float]) -> tuple[float, ...]:
    axis = tuple(_finite(f"{name}[{index}]", value) for index, value in enumerate(values))
    if len(axis) < 2 or any(value <= 0.0 for value in axis):
        raise ValueError(f"{name} must contain at least two positive values")
    ####
    if any(next_value <= value for value, next_value in zip(axis, axis[1:])):
        raise ValueError(f"{name} must be strictly increasing")
    ####
    return axis
####


def _nonnegative_spectrum(name: str, values: Sequence[float]) -> tuple[float, ...]:
    spectrum = tuple(_finite(f"{name}[{index}]", value) for index, value in enumerate(values))
    if not spectrum or any(value < 0.0 for value in spectrum):
        raise ValueError(f"{name} must be finite and nonnegative")
    ####
    return spectrum
####


@dataclass(frozen=True, slots=True)
class GrayRadiationProfile:
    """Caller-supplied homogeneous gray source and absorption spectra."""

    wavelengths_m: tuple[float, ...]
    source_function_w_sr_m: tuple[float, ...]
    absorption_coefficient_per_m: tuple[float, ...]
    profile_id: str = "explicit-gray-profile"

    def __post_init__(self) -> None:
        wavelengths = _strict_axis("wavelengths_m", self.wavelengths_m)
        source = _nonnegative_spectrum("source_function_w_sr_m", self.source_function_w_sr_m)
        absorption = _nonnegative_spectrum(
            "absorption_coefficient_per_m",
            self.absorption_coefficient_per_m,
        )
        if len(wavelengths) != len(source) or len(wavelengths) != len(absorption):
            raise ValueError("gray optical profile arrays must have matching lengths")
        ####
        if not self.profile_id:
            raise ValueError("profile_id must not be empty")
        ####
        object.__setattr__(self, "wavelengths_m", wavelengths)
        object.__setattr__(self, "source_function_w_sr_m", source)
        object.__setattr__(self, "absorption_coefficient_per_m", absorption)
    ####

    @classmethod
    def from_blackbody(
        cls,
        wavelengths_m: Sequence[float],
        temperature_K: float,
        absorption_coefficient_per_m: Sequence[float],
        *,
        emissivity: float = 1.0,
        profile_id: str = "blackbody-gray-profile",
    ) -> GrayRadiationProfile:
        """Build a gray source profile from an explicit thermal continuum.

        Absorption remains caller-supplied. This method supplies only the
        Planck source term and does not infer chemistry or line emission.
        """

        wavelengths = tuple(float(value) for value in wavelengths_m)
        source = planck_spectral_radiance_W_m2_sr_m(
            wavelengths,
            temperature_K,
            emissivity=emissivity,
        )
        return cls(
            wavelengths_m=wavelengths,
            source_function_w_sr_m=source,
            absorption_coefficient_per_m=tuple(absorption_coefficient_per_m),
            profile_id=profile_id,
        )
    ####
####



@dataclass(frozen=True, slots=True)
class SectionedGrayRadiationProfile:
    """Caller-supplied gray spectra resolved per straight support section.

    A section is the interval between two adjacent centers in the
    standardized sectioned-tube support.  This profile carries no chemistry
    inference: every source and absorption spectrum remains an explicit
    caller-owned input and is recorded in the Signature lineage.
    """

    wavelengths_m: tuple[float, ...]
    source_function_w_sr_m_by_section: tuple[tuple[float, ...], ...]
    absorption_coefficient_per_m_by_section: tuple[tuple[float, ...], ...]
    profile_id: str = "sectioned-gray-profile"

    def __post_init__(self) -> None:
        wavelengths = _strict_axis("wavelengths_m", self.wavelengths_m)
        source_sections = tuple(
            _nonnegative_spectrum(
                f"source_function_w_sr_m_by_section[{index}]",
                spectrum,
            )
            for index, spectrum in enumerate(self.source_function_w_sr_m_by_section)
        )
        absorption_sections = tuple(
            _nonnegative_spectrum(
                f"absorption_coefficient_per_m_by_section[{index}]",
                spectrum,
            )
            for index, spectrum in enumerate(self.absorption_coefficient_per_m_by_section)
        )
        if not source_sections or len(source_sections) != len(absorption_sections):
            raise ValueError("sectioned gray source and absorption arrays must have matching nonzero lengths")
        ####
        if any(
            len(spectrum) != len(wavelengths)
            for spectrum in source_sections + absorption_sections
        ):
            raise ValueError("sectioned gray optical arrays must match wavelengths_m")
        ####
        if not self.profile_id:
            raise ValueError("profile_id must not be empty")
        ####
        object.__setattr__(self, "wavelengths_m", wavelengths)
        object.__setattr__(self, "source_function_w_sr_m_by_section", source_sections)
        object.__setattr__(self, "absorption_coefficient_per_m_by_section", absorption_sections)
    ####

    @classmethod
    def from_blackbody(
        cls,
        wavelengths_m: Sequence[float],
        temperatures_K: Sequence[float],
        absorption_coefficient_per_m_by_section: Sequence[Sequence[float]],
        *,
        emissivity: float = 1.0,
        profile_id: str = "sectioned-blackbody-gray-profile",
    ) -> SectionedGrayRadiationProfile:
        """Build one explicit Planck continuum source per support section."""

        wavelengths = tuple(float(value) for value in wavelengths_m)
        temperatures = tuple(_finite(f"temperatures_K[{index}]", value) for index, value in enumerate(temperatures_K))
        absorption_sections = tuple(
            tuple(float(value) for value in spectrum)
            for spectrum in absorption_coefficient_per_m_by_section
        )
        if len(temperatures) != len(absorption_sections):
            raise ValueError("temperatures_K must match absorption section count")
        ####
        source_sections = tuple(
            planck_spectral_radiance_W_m2_sr_m(
                wavelengths,
                temperature,
                emissivity=emissivity,
            )
            for temperature in temperatures
        )
        return cls(
            wavelengths_m=wavelengths,
            source_function_w_sr_m_by_section=source_sections,
            absorption_coefficient_per_m_by_section=absorption_sections,
            profile_id=profile_id,
        )
    ####
####



GrayOpticalProfile: TypeAlias = (
    GrayRadiationProfile
    | SectionedGrayRadiationProfile
    | LineRadiationProfile
    | SectionedLineRadiationProfile
)


@dataclass(frozen=True, slots=True)
class ModelSignatureSampling:
    """Orthographic ray-grid policy for the bounded gray bridge."""

    source_to_observer_directions: tuple[Vector3, ...] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    transverse_sample_count: int = 17
    plane_margin_fraction: float = 0.10

    def __post_init__(self) -> None:
        directions = tuple(_unit_vector(f"source_to_observer_directions[{index}]", direction) for index, direction in enumerate(self.source_to_observer_directions))
        if not directions:
            raise ValueError("source_to_observer_directions must not be empty")
        ####
        if isinstance(self.transverse_sample_count, bool) or not 3 <= self.transverse_sample_count <= 128:
            raise ValueError("transverse_sample_count must be an integer in [3, 128]")
        ####
        if not isfinite(self.plane_margin_fraction) or not 0.0 <= self.plane_margin_fraction <= 1.0:
            raise ValueError("plane_margin_fraction must be finite and in [0, 1]")
        ####
        object.__setattr__(self, "source_to_observer_directions", directions)
    ####
####



class ModelSignatureReadiness(str, Enum):
    READY = "ready-with-explicit-gray-profile"
    BLOCKED_MISSING_OPTICAL_PROFILE = "blocked-missing-optical-profile"
    BLOCKED_CURVED_TRANSPORT = "blocked-curved-transport"
    BLOCKED_PLANAR_TRANSPORT = "blocked-planar-transport"
    BLOCKED_INVALID_SUPPORT = "blocked-invalid-support"
    BLOCKED_UNSUPPORTED_LANE = "blocked-unsupported-lane"
####


@dataclass(frozen=True, slots=True)
class ModelSignatureAssessment:
    """Machine-readable result of the flow-to-signature boundary audit."""

    schema: str
    lane_id: str
    model_id: str
    readiness: ModelSignatureReadiness
    signature_capability: str
    flow_geometry_ready: bool
    optical_profile_ready: bool
    transport_geometry_ready: bool
    production_claim_allowed: bool
    claim_ceiling: str
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.readiness is ModelSignatureReadiness.READY
    ####


    def model_dump(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "lane_id": self.lane_id,
            "model_id": self.model_id,
            "readiness": self.readiness.value,
            "signature_capability": self.signature_capability,
            "flow_geometry_ready": self.flow_geometry_ready,
            "optical_profile_ready": self.optical_profile_ready,
            "transport_geometry_ready": self.transport_geometry_ready,
            "production_claim_allowed": self.production_claim_allowed,
            "claim_ceiling": self.claim_ceiling,
            "reasons": list(self.reasons),
        }
    ####
####



class ModelSignatureBlockedError(ValueError):
    """Raised when a flow lane cannot honestly enter the current signature path."""
####


def _profile_adapter_schema(profile: GrayOpticalProfile | None) -> str:
    if isinstance(profile, SectionedLineRadiationProfile):
        return SECTIONED_LINE_MODEL_SIGNATURE_ADAPTER_SCHEMA
    ####
    return (
        LINE_MODEL_SIGNATURE_ADAPTER_SCHEMA
        if isinstance(profile, LineRadiationProfile)
        else GRAY_MODEL_SIGNATURE_ADAPTER_SCHEMA
    )
####


def _profile_claim_ceiling(profile: GrayOpticalProfile | None) -> str:
    if isinstance(profile, (LineRadiationProfile, SectionedLineRadiationProfile)):
        population_note = (
            "caller-bound LTE population closure from explicit transition data; "
            if _profile_has_population_closure(profile)
            else "no chemical population closure; "
        )
        return (
            "explicit LTE line-source/Voigt spectral engineering; "
            f"{population_note}no reactions, non-LTE inference, atmosphere, "
            "detector, or external validation"
        )
    ####
    return "gray-approximate; no chemistry, atmosphere, detector, or external validation"
####


def _profile_mode(profile: GrayOpticalProfile) -> str:
    if isinstance(profile, SectionedLineRadiationProfile):
        return "piecewise-axial-lte-line-by-line-voigt"
    ####
    if isinstance(profile, LineRadiationProfile):
        return "lte-line-by-line-voigt"
    ####
    if isinstance(profile, SectionedGrayRadiationProfile):
        return "piecewise-axial-section"
    ####
    return "homogeneous"
####


def _profile_has_population_closure(profile: GrayOpticalProfile) -> bool:
    profiles = (
        profile.profiles_by_section
        if isinstance(profile, SectionedLineRadiationProfile)
        else (profile,)
    )
    return any(
        isinstance(item, LineRadiationProfile)
        and any(line.population_closure is not None for line in item.lines)
        for item in profiles
    )
####


def _profile_section_count(profile: GrayOpticalProfile) -> int:
    if isinstance(profile, (SectionedGrayRadiationProfile, SectionedLineRadiationProfile)):
        return len(profile.source_function_w_sr_m_by_section)
    ####
    return 1
####


def _support_from_visualization(visualization: StandardizedModelVisualization) -> SectionedTubeSupport:
    sections = visualization.sectioned_tube.sections
    return SectionedTubeSupport(
        frame_id=visualization.frame_id,
        centers_m=tuple(section.center_m for section in sections),
        radii_m=tuple(section.radius_major_m for section in sections),
    )
####


def _support_readiness(
    visualization: StandardizedModelVisualization,
    *,
    allow_curved: bool = False,
) -> tuple[bool, SectionedTubeSupport | None, str | None]:
    try:
        support = _support_from_visualization(visualization)
    except (TypeError, ValueError) as error:
        return False, None, str(error)
    ####
    if not support.is_straight and not allow_curved:
        return False, support, "the standardized section support is not straight"
    ####
    return True, support, None
####


def assess_model_signature_readiness(
    visualization: StandardizedModelVisualization,
    *,
    optical_profile: GrayOpticalProfile | None = None,
) -> ModelSignatureAssessment:
    """Report whether a standardized flow lane can enter the gray bridge."""

    if not isinstance(visualization, StandardizedModelVisualization):
        raise TypeError("visualization must be StandardizedModelVisualization")
    ####
    lane = visualization.lane
    profile_ready = isinstance(
        optical_profile,
        (
            GrayRadiationProfile,
            SectionedGrayRadiationProfile,
            LineRadiationProfile,
            SectionedLineRadiationProfile,
        ),
    )
    common_ceiling = _profile_claim_ceiling(optical_profile)
    if lane in _STRAIGHT_SIGNATURE_LANES or lane in _CURVED_SIGNATURE_LANES:
        support_ready, _support, support_reason = _support_readiness(
            visualization,
            allow_curved=lane in _CURVED_SIGNATURE_LANES,
        )
        if isinstance(
            optical_profile,
            (SectionedGrayRadiationProfile, SectionedLineRadiationProfile),
        ) and _support is not None and not _support.is_straight:
            support_ready = False
            support_reason = "section-varying optical profiles require a straight section support"
        ####
        if lane in _CURVED_SIGNATURE_LANES and _support is not None and _support.is_straight:
            support_ready = False
            support_reason = "the curved signature lane requires a non-straight section support"
        ####
        reasons: list[str] = []
        if support_reason is not None:
            reasons.append(support_reason)
        ####
        if not profile_ready:
            reasons.append(
                "an explicit supported wavelength-resolved source/absorption profile is required"
            )
        ####
        if not support_ready:
            readiness = ModelSignatureReadiness.BLOCKED_INVALID_SUPPORT
        elif not profile_ready:
            readiness = ModelSignatureReadiness.BLOCKED_MISSING_OPTICAL_PROFILE
        else:
            readiness = ModelSignatureReadiness.READY
        ####
        return ModelSignatureAssessment(
            schema=_profile_adapter_schema(optical_profile),
            lane_id=visualization.lane_id,
            model_id=visualization.model_id,
            readiness=readiness,
            signature_capability="plume.signature.spectral-radiant-intensity@1",
            flow_geometry_ready=support_ready,
            optical_profile_ready=profile_ready,
            transport_geometry_ready=support_ready,
            production_claim_allowed=False,
            claim_ceiling=common_ceiling,
            reasons=tuple(reasons) if reasons else ("straight section support and explicit optical profile are available",),
        )
    ####
    planar_reasons = [
        "planar-MOC field requires a planar field/ray transport provider",
        "the sectioned-tube envelope is illustrative and cannot stand in for the MOC field",
    ]
    if visualization.diagnostics.get('production_fit_physical_length_accepted') is False:
        planar_reasons.append(
            'solver-generated shock-cell fit geometry has no accepted physical '
            'length and cannot enter Signature transport'
        )
    ####
    return ModelSignatureAssessment(
        schema=_profile_adapter_schema(optical_profile),
        lane_id=visualization.lane_id,
        model_id=visualization.model_id,
        readiness=ModelSignatureReadiness.BLOCKED_PLANAR_TRANSPORT,
        signature_capability="plume.signature.spectral-radiant-intensity@1",
        flow_geometry_ready=True,
        optical_profile_ready=profile_ready,
        transport_geometry_ready=False,
        production_claim_allowed=False,
        claim_ceiling=common_ceiling,
        reasons=tuple(planar_reasons),
    )
####


def _cross(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    vector = np.cross(first, second)
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-14:
        raise ValueError("observer direction does not admit a transverse basis")
    ####
    return vector / norm
####


def _transverse_basis(direction: Vector3) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    observer = np.asarray(direction, dtype=float)
    reference = np.asarray((0.0, 0.0, 1.0) if abs(observer[2]) < 0.9 else (0.0, 1.0, 0.0))
    first = _cross(observer, reference)
    second = _cross(observer, first)
    return observer, first, second
####


def _bounds_for_direction(
    support: SectionedTubeSupport,
    direction: Vector3,
    margin_fraction: float,
) -> tuple[np.ndarray, np.ndarray, float, float, float, float, float]:
    observer, first, second = _transverse_basis(direction)
    centers = np.asarray(support.centers_m, dtype=float)
    radii = np.asarray(support.radii_m, dtype=float)
    reference = np.mean(centers, axis=0)
    relative = centers - reference
    first_projection = relative @ first
    second_projection = relative @ second
    longitudinal_projection = relative @ observer
    transverse_extent = max(float(np.max(radii)), 1.0e-9)
    first_lower = float(np.min(first_projection - radii))
    first_upper = float(np.max(first_projection + radii))
    second_lower = float(np.min(second_projection - radii))
    second_upper = float(np.max(second_projection + radii))
    first_span = first_upper - first_lower
    second_span = second_upper - second_lower
    margin = margin_fraction * max(first_span, second_span, transverse_extent)
    first_lower -= margin
    first_upper += margin
    second_lower -= margin
    second_upper += margin
    depth = float(np.max(np.abs(longitudinal_projection) + radii)) + margin + 1.0e-9
    return reference, observer, first_lower, first_upper, second_lower, second_upper, depth
####


def _build_ray_grid(
    support: SectionedTubeSupport,
    sampling: ModelSignatureSampling,
    wavelengths_m: tuple[float, ...],
) -> tuple[SpectralRayTransferRequest, FarFieldRayIntegration]:
    origins: list[Vector3] = []
    directions: list[Vector3] = []
    t_min: list[float] = []
    t_max: list[float] = []
    direction_indices: list[int] = []
    weights: list[float] = []
    count = sampling.transverse_sample_count
    for direction_index, direction in enumerate(sampling.source_to_observer_directions):
        reference, observer, first_lower, first_upper, second_lower, second_upper, depth = _bounds_for_direction(
            support,
            direction,
            sampling.plane_margin_fraction,
        )
        _observer, first_basis, second_basis = _transverse_basis(direction)
        first_step = (first_upper - first_lower) / count
        second_step = (second_upper - second_lower) / count
        weight = first_step * second_step
        for first_index in range(count):
            first_coordinate = first_lower + (first_index + 0.5) * first_step
            for second_index in range(count):
                second_coordinate = second_lower + (second_index + 0.5) * second_step
                origin = reference + observer * depth
                origin = origin + first_basis * first_coordinate + second_basis * second_coordinate
                origins.append(cast(Vector3, tuple(float(value) for value in origin)))
                directions.append(cast(Vector3, tuple(float(-value) for value in observer)))
                t_min.append(0.0)
                t_max.append(2.0 * depth)
                direction_indices.append(direction_index)
                weights.append(weight)
            ####
        ####
    ####
    request = SpectralRayTransferRequest(
        ray_frame_id=support.frame_id,
        ray_origins_m=tuple(origins),
        ray_directions=tuple(directions),
        ray_t_min_m=tuple(t_min),
        ray_t_max_m=tuple(t_max),
        wavelengths_m=wavelengths_m,
    )
    integration = FarFieldRayIntegration(
        direction_frame_id=support.frame_id,
        source_to_observer_directions=sampling.source_to_observer_directions,
        ray_direction_indices=tuple(direction_indices),
        ray_projected_area_weights_m2=tuple(weights),
    )
    return request, integration
####


def _attach_flow_lineage(
    signature: SpectralSignatureResult,
    visualization: StandardizedModelVisualization,
    profile: GrayOpticalProfile,
    sampling: ModelSignatureSampling,
    time_model: TimeModel,
) -> SpectralSignatureResult:
    parent = signature.metadata
    parent_provenance = parent.provenance
    optical_profile_digest = canonical_digest(profile)
    adapter_schema = _profile_adapter_schema(profile)
    claim_ceiling = _profile_claim_ceiling(profile)
    lineage_payload = {
        "adapter_schema": adapter_schema,
        "flow_lane": visualization.lane_id,
        "flow_model_id": visualization.model_id,
        "flow_model_version": visualization.model_version,
        "optical_profile_id": profile.profile_id,
        "optical_profile_digest": optical_profile_digest,
        "sampling": sampling,
    }
    provenance = parent_provenance.model_copy(
        update={
            "model_lineage_id": canonical_digest(lineage_payload),
            "metadata": {
                **dict(parent_provenance.metadata),
                "flow_model_lane": visualization.lane_id,
                "flow_model_id": visualization.model_id,
                "flow_model_version": visualization.model_version,
                "flow_model_fidelity": visualization.claims.model_fidelity,
                "flow_model_validation": visualization.claims.validation_level,
                "flow_geometry_claim": visualization.claims.geometry_claim.value,
                "signature_adapter_schema": adapter_schema,
                "signature_claim_ceiling": claim_ceiling,
                "optical_profile_id": profile.profile_id,
                "optical_profile_digest": optical_profile_digest,
                "optical_profile_mode": _profile_mode(profile),
                "optical_profile_section_count": str(
                    _profile_section_count(profile)
                ),
                "ray_grid_policy": f"{sampling.transverse_sample_count}x{sampling.transverse_sample_count} per observer direction",
                "signature_time_model": time_model.value,
                "production_claim_allowed": "false",
            },
        }
    )
    applicability_status = parent.applicability.status
    reasons = list(parent.applicability.reasons)
    if visualization.applicability_status is not ApplicabilityStatus.INSIDE:
        applicability_status = ApplicabilityStatus.MARGINAL
        reasons.append(f"flow lane applicability is {visualization.applicability_status.value}")
    ####
    metadata = parent.model_copy(
        update={
            "claims": ProductClaims(
                geometry=GeometryClaim.NOT_APPLICABLE,
                radiation=(
                    RadiationClaim.SPECTRAL_ENGINEERING
                    if isinstance(profile, (LineRadiationProfile, SectionedLineRadiationProfile))
                    else RadiationClaim.GRAY_APPROXIMATE
                ),
                time_model=time_model,
                derivation=Derivation.ADAPTED,
                consistency=parent.claims.consistency,
            ),
            "applicability": parent.applicability.model_copy(
                update={
                    "status": applicability_status,
                    "reasons": tuple(reasons),
                }
            ),
            "provenance": provenance,
            "warnings": parent.warnings
            + (
                (
                    (
                        "signature uses a caller-bound LTE population closure "
                        "from explicit transition data; no reactions or non-LTE "
                        "population closure was inferred"
                        if _profile_has_population_closure(profile)
                        else "signature uses an explicit LTE line-source profile "
                        "with caller-supplied Voigt optical depths; no chemical "
                        "population closure was inferred"
                    )
                    if isinstance(profile, (LineRadiationProfile, SectionedLineRadiationProfile))
                    else "signature uses an explicit gray optical profile; no chemistry or molecular spectral source was inferred"
                ),
                f"flow geometry came from {visualization.lane_id} and retains its declared fidelity ceiling",
                "signature is not a detector, atmospheric-path, or focal-plane-array prediction",
            ),
        }
    )
    return signature.model_copy(update={"metadata": metadata})
####


def evaluate_model_signature(
    visualization: StandardizedModelVisualization,
    optical_profile: GrayOpticalProfile,
    *,
    sampling: ModelSignatureSampling | None = None,
    operating_point_id: str | None = None,
    allow_partial_results: bool = False,
    time_s: float = 0.0,
    source_pose: Pose | None = None,
    dynamic_state: Mapping[str, object] | None = None,
    ambient_state: Mapping[str, object] | None = None,
    time_model: TimeModel = TimeModel.STEADY,
) -> SpectralSignatureResult:
    """Evaluate a supported standardized flow lane as a gray signature snapshot.

    ``time_s`` and the supplied state mappings are recorded in the immutable
    provider snapshot.  They do not on their own change the static flow or
    optical inputs; callers that need a prescribed transient should resolve a
    visualization and optical profile for each time before calling this seam.
    """

    if not isinstance(visualization, StandardizedModelVisualization):
        raise TypeError("visualization must be StandardizedModelVisualization")
    ####
    if not isinstance(
        optical_profile,
        (
            GrayRadiationProfile,
            SectionedGrayRadiationProfile,
            LineRadiationProfile,
            SectionedLineRadiationProfile,
        ),
    ):
        raise TypeError(
            "optical_profile must be a GrayRadiationProfile, "
            "SectionedGrayRadiationProfile, LineRadiationProfile, or "
            "SectionedLineRadiationProfile"
        )
    ####
    if not isinstance(allow_partial_results, bool):
        raise TypeError("allow_partial_results must be bool")
    ####
    resolved_time_s = _finite("time_s", time_s)
    if source_pose is not None and not isinstance(source_pose, Pose):
        raise TypeError("source_pose must be Pose or None")
    ####
    if dynamic_state is not None and not isinstance(dynamic_state, Mapping):
        raise TypeError("dynamic_state must be a mapping or None")
    ####
    if ambient_state is not None and not isinstance(ambient_state, Mapping):
        raise TypeError("ambient_state must be a mapping or None")
    ####
    if not isinstance(time_model, TimeModel):
        raise TypeError("time_model must be TimeModel")
    ####
    selected_sampling = sampling or ModelSignatureSampling()
    assessment = assess_model_signature_readiness(
        visualization,
        optical_profile=optical_profile,
    )
    if not assessment.ready:
        raise ModelSignatureBlockedError(f"{visualization.lane_id} cannot enter the gray signature bridge ({assessment.readiness.value}): {'; '.join(assessment.reasons)}")
    ####
    support_ready, support, support_reason = _support_readiness(
        visualization,
        allow_curved=visualization.lane in _CURVED_SIGNATURE_LANES,
    )
    if visualization.lane in _CURVED_SIGNATURE_LANES and support is not None and support.is_straight:
        support_ready = False
        support_reason = "the curved signature lane requires a non-straight section support"
    ####
    if not support_ready or support is None:
        raise ModelSignatureBlockedError(support_reason or "flow support is not transport-ready")
    ####
    request, integration = _build_ray_grid(support, selected_sampling, optical_profile.wavelengths_m)
    if isinstance(
        optical_profile,
        (SectionedGrayRadiationProfile, SectionedLineRadiationProfile),
    ):
        definition = GrayRayTransferDefinition(
            frame_id=support.frame_id,
            support=support,
            wavelengths_m=optical_profile.wavelengths_m,
            source_function_w_sr_m_by_section=optical_profile.source_function_w_sr_m_by_section,
            absorption_coefficient_per_m_by_section=optical_profile.absorption_coefficient_per_m_by_section,
            asset_id=f"model-gray-optics:{visualization.lane_id}:{optical_profile.profile_id}",
        )
    else:
        definition = GrayRayTransferDefinition(
            frame_id=support.frame_id,
            support=support,
            wavelengths_m=optical_profile.wavelengths_m,
            source_function_w_sr_m=optical_profile.source_function_w_sr_m,
            absorption_coefficient_per_m=optical_profile.absorption_coefficient_per_m,
            asset_id=f"model-gray-optics:{visualization.lane_id}:{optical_profile.profile_id}",
            allow_curved_support=visualization.lane in _CURVED_SIGNATURE_LANES,
        )
    ####
    if visualization.lane in _CURVED_SIGNATURE_LANES:
        provider = CurvedGrayRayTransferProvider()
    else:
        provider = GrayRayTransferProvider(
            GrayRayTransferConfiguration(
                provider_id="plume.adapter.model-gray-ray-transfer",
                provider_version="1.0.0",
            )
        )
    ####
    session = provider.create_session(definition=definition)
    try:
        snapshot = session.create_snapshot(
            time_s=resolved_time_s,
            source_pose=source_pose
            or Pose(
                frame_id=support.frame_id,
                translation_m=(0.0, 0.0, 0.0),
                rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
            ),
            dynamic_state={
                "flow_model_lane": visualization.lane_id,
                "flow_model_id": visualization.model_id,
                "optical_profile_id": optical_profile.profile_id,
                "caller_dynamic_state": dict(dynamic_state or {}),
            },
            ambient_state=dict(ambient_state or {}),
        )
        ray_result = snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
    finally:
        session.close()
    ####
    signature = far_field_from_rays(
        request,
        ray_result,
        integration,
        allow_partial_results=allow_partial_results,
        operating_point_id=operating_point_id,
    )
    return _attach_flow_lineage(
        signature,
        visualization,
        optical_profile,
        selected_sampling,
        time_model,
    )
####
