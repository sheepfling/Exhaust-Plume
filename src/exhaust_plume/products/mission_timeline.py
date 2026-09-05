"""Prescribed, immutable mission-time sampling for plume products.

The plume solvers in this repository evaluate one operating point at a time.
This module provides the composition seam for a moving, throttling vehicle:
a caller declares a time-ordered schedule, supplies the flow and optical
resolvers appropriate to its propulsion model, then obtains independent
snapshots or advances an immutable cursor through that schedule.

It deliberately does not infer engine depletion, nozzle conditions,
atmosphere, chemistry, or radiation from throttle and altitude.  Those are
model-specific closures and must be provided by the resolver callbacks.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from math import acos, isfinite, sin, sqrt
from types import MappingProxyType
from typing import Any, TypeAlias, cast

from exhaust_plume.contracts.ray_transfer_v1 import (
    SpectralRayTransferResult as ProviderSpectralRayTransferResult,
)

from exhaust_plume.api.v1 import (
    Pose,
    SnapshotMetadata,
    SpectralSignatureRequest,
    SpectralSignatureResult,
    TimeModel,
    VisualSectionedTubeRequest,
    VisualSectionedTubeResult,
    canonical_digest,
)
from exhaust_plume.products.model_signature import (
    GrayOpticalProfile,
    GrayRadiationProfile,
    LineRadiationProfile,
    ModelSignatureAssessment,
    ModelSignatureBlockedError,
    ModelSignatureSampling,
    SectionedGrayRadiationProfile,
    SectionedLineRadiationProfile,
    assess_model_signature_readiness,
    evaluate_model_signature,
)
from exhaust_plume.products.model_visualization import (
    StandardizedModelVisualization,
    evaluate_standardized_model_visualization,
)
from exhaust_plume.products.signature_timeline import (
    SignatureTimeline,
    SignatureTimelineQuery,
    SignatureTimelineSample,
)
from exhaust_plume.validation.fpa_operators import (
    DetectorResponse,
    FpaDigitizationPolicy,
    FpaDigitizedExpectation,
    FpaPixelGeometry,
    FpaPixelImage,
    digitize_expected_electrons,
    integrate_spectral_ray_result_to_fpa,
)
from exhaust_plume.validation.fpa_visualization import (
    FpaSourceReference,
    FpaViewProjection,
    FpaVisualizationInput,
    FpaVisualizationSpec,
    project_fpa_view,
)
from exhaust_plume.validation.sensor_operators import AtmosphericPathLayer

__all__ = (
    "MISSION_TIMELINE_SCHEMA",
    "MissionCursor",
    "MissionFpaEvaluator",
    "MissionFpaSample",
    "MissionFpaTimeline",
    "MissionProductEvaluator",
    "MissionProductSample",
    "MissionSignatureEvaluator",
    "MissionSignatureSample",
    "MissionState",
    "MissionTimeline",
    "MissionTimelineRangeError",
    "MissionVisualizationEvaluator",
    "MissionVisualizationSample",
)


MISSION_TIMELINE_SCHEMA = "plume.mission-timeline@1"

MissionRayTransferAtState: TypeAlias = tuple[
    Sequence[float],
    ProviderSpectralRayTransferResult,
]


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    ####
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must be numeric") from error
    ####
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    ####
    return numeric
####


def _optional_finite(name: str, value: float | None) -> float | None:
    return None if value is None else _finite(name, value)
####


def _copy_context(name: str, value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    ####
    copied = dict(value)
    try:
        canonical_digest(copied)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain canonicalizable contract data") from error
    ####
    return MappingProxyType(copied)
####


def _interpolate_scalar(first: float | None, second: float | None, fraction: float) -> float | None:
    if first is None or second is None:
        return None
    ####
    return first + (second - first) * fraction
####


def _normalized_quaternion(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    norm = sqrt(sum(component * component for component in value))
    return tuple(component / norm for component in value)  # type: ignore[return-value]
####


def _slerp(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    fraction: float,
) -> tuple[float, float, float, float]:
    second_adjusted = second
    dot = sum(left * right for left, right in zip(first, second_adjusted))
    if dot < 0.0:
        second_adjusted = tuple(-value for value in second_adjusted)  # type: ignore[assignment]
        dot = -dot
    ####
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _normalized_quaternion(
            tuple(left + (right - left) * fraction for left, right in zip(first, second_adjusted))  # type: ignore[arg-type]
        )
    ####
    angle = acos(dot)
    sine = sin(angle)
    first_weight = sin((1.0 - fraction) * angle) / sine
    second_weight = sin(fraction * angle) / sine
    return _normalized_quaternion(
        tuple(first_weight * left + second_weight * right for left, right in zip(first, second_adjusted))  # type: ignore[arg-type]
    )
####


def _interpolate_pose(first: Pose, second: Pose, fraction: float) -> Pose:
    if first.frame_id != second.frame_id:
        raise ValueError("mission timeline poses must use one frame_id")
    ####
    return Pose(
        frame_id=first.frame_id,
        translation_m=cast(
            tuple[float, float, float],
            tuple(left + (right - left) * fraction for left, right in zip(first.translation_m, second.translation_m)),
        ),
        rotation_xyzw=_slerp(first.rotation_xyzw, second.rotation_xyzw, fraction),
    )
####


@dataclass(frozen=True, slots=True)
class MissionState:
    """One declared vehicle/plume condition at a mission time.

    The scalar fields are optional because an application may drive the actual
    operating condition wholly from ``dynamic_state``.  When a field is used
    in a ``MissionTimeline``, it must be populated at every schedule node so
    interpolation remains unambiguous.
    """

    time_s: float
    source_pose: Pose
    geopotential_altitude_m: float | None = None
    throttle_fraction: float | None = None
    remaining_propellant_mass_kg: float | None = None
    operating_point_id: str | None = None
    dynamic_state: Mapping[str, object] = field(default_factory=dict)
    ambient_state: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        time_s = _finite("time_s", self.time_s)
        if not isinstance(self.source_pose, Pose):
            raise TypeError("source_pose must be Pose")
        ####
        altitude = _optional_finite("geopotential_altitude_m", self.geopotential_altitude_m)
        throttle = _optional_finite("throttle_fraction", self.throttle_fraction)
        propellant_mass = _optional_finite(
            "remaining_propellant_mass_kg",
            self.remaining_propellant_mass_kg,
        )
        if throttle is not None and not 0.0 <= throttle <= 1.0:
            raise ValueError("throttle_fraction must lie in [0, 1]")
        ####
        if propellant_mass is not None and propellant_mass < 0.0:
            raise ValueError("remaining_propellant_mass_kg must be nonnegative")
        ####
        if self.operating_point_id is not None and not self.operating_point_id:
            raise ValueError("operating_point_id must be nonempty when supplied")
        ####
        object.__setattr__(self, "time_s", time_s)
        object.__setattr__(self, "geopotential_altitude_m", altitude)
        object.__setattr__(self, "throttle_fraction", throttle)
        object.__setattr__(self, "remaining_propellant_mass_kg", propellant_mass)
        object.__setattr__(self, "dynamic_state", _copy_context("dynamic_state", self.dynamic_state))
        object.__setattr__(self, "ambient_state", _copy_context("ambient_state", self.ambient_state))
    ####

    def snapshot_dynamic_state(self) -> dict[str, object]:
        """Return declared vehicle state suitable for a provider snapshot digest."""

        return {
            "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
            "time_s": self.time_s,
            "geopotential_altitude_m": self.geopotential_altitude_m,
            "throttle_fraction": self.throttle_fraction,
            "remaining_propellant_mass_kg": self.remaining_propellant_mass_kg,
            "operating_point_id": self.operating_point_id,
            "declared_dynamic_state": dict(self.dynamic_state),
        }
    ####

    def snapshot_ambient_state(self) -> dict[str, object]:
        """Return ambient context suitable for a provider snapshot digest."""

        return {
            "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
            "time_s": self.time_s,
            "geopotential_altitude_m": self.geopotential_altitude_m,
            "declared_ambient_state": dict(self.ambient_state),
        }
    ####
####


def _resolve_atmospheric_path_layers(
    resolver: Callable[[MissionState], Sequence[AtmosphericPathLayer] | None] | None,
    state: MissionState,
) -> tuple[AtmosphericPathLayer, ...] | None:
    if resolver is None:
        return None
    ####
    resolved = resolver(state)
    if resolved is None:
        return None
    ####
    try:
        layers = tuple(resolved)
    except TypeError as error:
        raise TypeError(
            "atmospheric_path_layers_at must return AtmosphericPathLayer values or None"
        ) from error
    ####
    if not layers:
        raise ValueError("atmospheric_path_layers_at must return at least one layer")
    ####
    if not all(isinstance(layer, AtmosphericPathLayer) for layer in layers):
        raise TypeError(
            "atmospheric_path_layers_at must return AtmosphericPathLayer values"
        )
    ####
    return layers
####


def _resolve_background_spectral_radiance(
    resolver: Callable[[MissionState], Sequence[Sequence[float]] | None] | None,
    state: MissionState,
) -> tuple[tuple[float, ...], ...] | None:
    if resolver is None:
        return None
    ####
    resolved = resolver(state)
    if resolved is None:
        return None
    ####
    try:
        rows = tuple(
            tuple(
                _finite(f"background_spectral_radiance[{row_index}][{column_index}]", value)
                for column_index, value in enumerate(row)
            )
            for row_index, row in enumerate(resolved)
        )
    except TypeError as error:
        raise TypeError(
            "background_spectral_radiance_at must return a numeric matrix or None"
        ) from error
    ####
    if not rows or not rows[0]:
        raise ValueError(
            "background_spectral_radiance_at must return a non-empty matrix"
        )
    ####
    return rows
####


class MissionTimelineRangeError(ValueError):
    """Raised when a sample or cursor advance leaves a prescribed timeline."""
####


@dataclass(frozen=True, slots=True)
class MissionTimeline:
    """A bounded prescribed mission schedule with deterministic interpolation.

    Translation, attitude, altitude, throttle, and remaining propellant mass
    are interpolated between nodes.  ``operating_point_id`` and the context
    mappings are held from the lower node because they are discrete/model
    specific declarations.  Exact node samples always preserve the original
    declared state.
    """

    states: tuple[MissionState, ...]

    def __post_init__(self) -> None:
        states = tuple(self.states)
        if not states:
            raise ValueError("mission timeline requires at least one state")
        ####
        if any(not isinstance(state, MissionState) for state in states):
            raise TypeError("mission timeline states must be MissionState")
        ####
        if any(second.time_s <= first.time_s for first, second in zip(states, states[1:])):
            raise ValueError("mission timeline state times must be strictly increasing")
        ####
        frame_id = states[0].source_pose.frame_id
        if any(state.source_pose.frame_id != frame_id for state in states[1:]):
            raise ValueError("mission timeline poses must use one frame_id")
        ####
        for field_name in (
            "geopotential_altitude_m",
            "throttle_fraction",
            "remaining_propellant_mass_kg",
        ):
            populated = tuple(getattr(state, field_name) is not None for state in states)
            if any(populated) and not all(populated):
                raise ValueError(f"{field_name} must be supplied at every timeline state or omitted from all states")
            ####
        ####
        object.__setattr__(self, "states", states)
    ####

    @property
    def start_time_s(self) -> float:
        return self.states[0].time_s
    ####

    @property
    def end_time_s(self) -> float:
        return self.states[-1].time_s
    ####

    def sample_at(self, time_s: float) -> MissionState:
        """Return an immutable state at ``time_s`` without extrapolation."""

        requested_time_s = _finite("time_s", time_s)
        if requested_time_s < self.start_time_s or requested_time_s > self.end_time_s:
            raise MissionTimelineRangeError(f"time_s={requested_time_s} lies outside [{self.start_time_s}, {self.end_time_s}]")
        ####
        state_times = tuple(state.time_s for state in self.states)
        upper_index = bisect_left(state_times, requested_time_s)
        if self.states[upper_index].time_s == requested_time_s:
            return self.states[upper_index]
        ####
        lower = self.states[upper_index - 1]
        upper = self.states[upper_index]
        fraction = (requested_time_s - lower.time_s) / (upper.time_s - lower.time_s)
        return MissionState(
            time_s=requested_time_s,
            source_pose=_interpolate_pose(lower.source_pose, upper.source_pose, fraction),
            geopotential_altitude_m=_interpolate_scalar(
                lower.geopotential_altitude_m,
                upper.geopotential_altitude_m,
                fraction,
            ),
            throttle_fraction=_interpolate_scalar(
                lower.throttle_fraction,
                upper.throttle_fraction,
                fraction,
            ),
            remaining_propellant_mass_kg=_interpolate_scalar(
                lower.remaining_propellant_mass_kg,
                upper.remaining_propellant_mass_kg,
                fraction,
            ),
            operating_point_id=lower.operating_point_id,
            dynamic_state=lower.dynamic_state,
            ambient_state=lower.ambient_state,
        )
    ####

    def cursor_at(self, time_s: float | None = None) -> "MissionCursor":
        """Create a non-mutating cursor at the start or an exact/interpolated time."""

        return MissionCursor(
            timeline=self,
            state=self.sample_at(self.start_time_s if time_s is None else time_s),
        )
    ####
####


@dataclass(frozen=True, slots=True)
class MissionCursor:
    """A functional cursor: advancing returns a new cursor, never mutating history."""

    timeline: MissionTimeline
    state: MissionState

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        ####
        if not isinstance(self.state, MissionState):
            raise TypeError("state must be MissionState")
        ####
        canonical = self.timeline.sample_at(self.state.time_s)
        if canonical != self.state:
            raise ValueError("cursor state must be a sample from its timeline")
        ####
    ####

    def advance_to(self, time_s: float) -> "MissionCursor":
        """Return a cursor at a later prescribed time."""

        requested_time_s = _finite("time_s", time_s)
        if requested_time_s < self.state.time_s:
            raise ValueError("mission cursor cannot advance backward in time")
        ####
        return MissionCursor(timeline=self.timeline, state=self.timeline.sample_at(requested_time_s))
    ####

    def advance_by(self, duration_s: float) -> "MissionCursor":
        """Return a cursor advanced by a nonnegative duration."""

        resolved_duration_s = _finite("duration_s", duration_s)
        if resolved_duration_s < 0.0:
            raise ValueError("duration_s must be nonnegative")
        ####
        return self.advance_to(self.state.time_s + resolved_duration_s)
    ####
####


def _mission_visual_snapshot(
    state: MissionState,
    visualization: StandardizedModelVisualization,
) -> SnapshotMetadata:
    """Build deterministic visual-product metadata for one mission state."""

    dynamic_digest = canonical_digest(state.snapshot_dynamic_state())
    ambient_digest = canonical_digest(state.snapshot_ambient_state())
    provider_state_digest = canonical_digest(visualization.model_dump())
    session_id = canonical_digest(
        {
            "schema": MISSION_TIMELINE_SCHEMA,
            "provider": "plume.visual.model-lane",
            "lane": visualization.lane_id,
            "model_id": visualization.model_id,
            "model_version": visualization.model_version,
        }
    )[:24]
    snapshot_id = canonical_digest(
        {
            "session": session_id,
            "time_s": state.time_s,
            "source_pose": state.source_pose,
            "dynamic": dynamic_digest,
            "ambient": ambient_digest,
            "provider": provider_state_digest,
        }
    )[:24]
    return SnapshotMetadata(
        snapshot_id=snapshot_id,
        session_id=session_id,
        time_s=state.time_s,
        source_pose=state.source_pose,
        dynamic_state_digest_sha256=dynamic_digest,
        ambient_state_digest_sha256=ambient_digest,
        provider_state_digest_sha256=provider_state_digest,
    )
####


@dataclass(frozen=True, slots=True)
class MissionVisualizationSample:
    """A standardized lane and its canonical visual product at one mission time."""

    state: MissionState
    visualization: StandardizedModelVisualization
    visual_product: VisualSectionedTubeResult
####


@dataclass(frozen=True, slots=True)
class MissionVisualizationEvaluator:
    """Evaluate any standardized model lane as a prescribed transient visual product.

    ``visualization_at`` is the application-owned flow-model resolver.  It
    may run a static solver at changing scheduled inputs, choose a fidelity
    lane, or retrieve a cached result; this adapter always binds its output to
    the supplied immutable mission state before emitting the canonical visual
    sectioned-tube product.
    """

    timeline: MissionTimeline
    visualization_at: Callable[[MissionState], StandardizedModelVisualization]
    request: VisualSectionedTubeRequest
    provider_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        ####
        if not callable(self.visualization_at):
            raise TypeError("visualization_at must be callable")
        ####
        if not isinstance(self.request, VisualSectionedTubeRequest):
            raise TypeError("request must be VisualSectionedTubeRequest")
        ####
        if not self.provider_version:
            raise ValueError("provider_version must not be empty")
        ####
    ####

    def _evaluate_state(self, state: MissionState) -> MissionVisualizationSample:
        visualization = self.visualization_at(state)
        if not isinstance(visualization, StandardizedModelVisualization):
            raise TypeError("visualization_at must return StandardizedModelVisualization")
        ####
        visual_product = evaluate_standardized_model_visualization(
            visualization,
            self.request,
            _mission_visual_snapshot(state, visualization),
            provider_version=self.provider_version,
            time_model=TimeModel.PRESCRIBED_TRANSIENT,
        )
        provenance = visual_product.metadata.provenance.model_copy(
            update={
                "metadata": {
                    **dict(visual_product.metadata.provenance.metadata),
                    "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
                    "mission_time_s": f"{state.time_s:.17g}",
                    "mission_source_frame_id": state.source_pose.frame_id,
                }
            }
        )
        visual_product = visual_product.model_copy(update={"metadata": visual_product.metadata.model_copy(update={"provenance": provenance})})
        return MissionVisualizationSample(
            state=state,
            visualization=visualization,
            visual_product=visual_product,
        )
    ####

    def sample_at(self, time_s: float) -> MissionVisualizationSample:
        """Resolve and return the visual product at a scheduled mission time."""

        return self._evaluate_state(self.timeline.sample_at(time_s))
    ####

    def evaluate_at(self, time_s: float) -> VisualSectionedTubeResult:
        """Return the canonical visual sectioned-tube product at ``time_s``."""

        return self.sample_at(time_s).visual_product
    ####

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionVisualizationSample:
        """Evaluate a cursor originating from this evaluator's timeline."""

        if not isinstance(cursor, MissionCursor):
            raise TypeError("cursor must be MissionCursor")
        ####
        if cursor.timeline is not self.timeline:
            raise ValueError("cursor must originate from this evaluator's timeline")
        ####
        return self._evaluate_state(cursor.state)
    ####
####


@dataclass(frozen=True, slots=True)
class MissionSignatureSample:
    """One flow/signature result tied to an immutable mission-state snapshot."""

    state: MissionState
    visualization: StandardizedModelVisualization
    optical_profile: GrayOpticalProfile
    signature: SpectralSignatureResult
    atmospheric_path_layers: tuple[AtmosphericPathLayer, ...] | None = None
####


@dataclass(frozen=True, slots=True)
class MissionSignatureEvaluator:
    """Evaluate a prescribed mission through caller-owned flow/optical resolvers.

    The resolvers are intentionally explicit.  For example, an application
    can convert altitude to an ambient state, combine throttle with a
    propulsion table to obtain nozzle conditions, run a selected flow solver,
    and choose a chemistry/optics profile.  This adapter records that sampled
    vehicle state while leaving those physical closures visible to the caller.
    """

    timeline: MissionTimeline
    visualization_at: Callable[[MissionState], StandardizedModelVisualization]
    optical_profile_at: Callable[[MissionState], GrayOpticalProfile]
    sampling: ModelSignatureSampling | None = None
    allow_partial_results: bool = False
    atmospheric_path_layers_at: Callable[
        [MissionState], Sequence[AtmosphericPathLayer] | None
    ] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        ####
        if not callable(self.visualization_at):
            raise TypeError("visualization_at must be callable")
        ####
        if not callable(self.optical_profile_at):
            raise TypeError("optical_profile_at must be callable")
        ####
        if self.sampling is not None and not isinstance(self.sampling, ModelSignatureSampling):
            raise TypeError("sampling must be ModelSignatureSampling or None")
        ####
        if not isinstance(self.allow_partial_results, bool):
            raise TypeError("allow_partial_results must be bool")
        ####
        if self.atmospheric_path_layers_at is not None and not callable(
            self.atmospheric_path_layers_at
        ):
            raise TypeError("atmospheric_path_layers_at must be callable or None")
        ####
    ####

    def _evaluate_state(self, state: MissionState) -> MissionSignatureSample:
        visualization = self.visualization_at(state)
        optical_profile = self.optical_profile_at(state)
        if not isinstance(visualization, StandardizedModelVisualization):
            raise TypeError("visualization_at must return StandardizedModelVisualization")
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
            raise TypeError("optical_profile_at must return a supported optical profile")
        ####
        atmospheric_path_layers = _resolve_atmospheric_path_layers(
            self.atmospheric_path_layers_at,
            state,
        )
        signature = evaluate_model_signature(
            visualization,
            optical_profile,
            sampling=self.sampling,
            operating_point_id=state.operating_point_id,
            allow_partial_results=self.allow_partial_results,
            time_s=state.time_s,
            source_pose=state.source_pose,
            dynamic_state=state.snapshot_dynamic_state(),
            ambient_state=state.snapshot_ambient_state(),
            atmospheric_path_layers=atmospheric_path_layers,
            time_model=TimeModel.PRESCRIBED_TRANSIENT,
        )
        return MissionSignatureSample(
            state=state,
            visualization=visualization,
            optical_profile=optical_profile,
            signature=signature,
            atmospheric_path_layers=atmospheric_path_layers,
        )
    ####

    def sample_at(self, time_s: float) -> MissionSignatureSample:
        """Resolve flow/optics and evaluate the spectral signature at one time."""

        return self._evaluate_state(self.timeline.sample_at(time_s))
    ####

    def evaluate_at(self, time_s: float) -> SpectralSignatureResult:
        """Return the far-field spectral radiant-intensity product at one time."""

        return self.sample_at(time_s).signature
    ####

    def evaluate_timeline(self, times_s: Sequence[float]) -> SignatureTimeline:
        """Resolve exact Signature samples into a compatible time series.

        The requested times must be strictly increasing and lie within the
        prescribed mission timeline.  Each sample is freshly resolved through
        the caller-owned flow and optical callbacks; this method never
        interpolates Signature values or reuses a neighboring provider result.
        The returned timeline can be passed directly to the angular heatmap,
        masked direction-series, and exact point-query utilities.
        """

        try:
            requested_times = tuple(times_s)
        except TypeError as error:
            raise TypeError("times_s must be an iterable of mission times") from error
        ####
        if not requested_times:
            raise ValueError("times_s must contain at least one mission time")
        ####
        samples: list[SignatureTimelineSample] = []
        for time_s in requested_times:
            sample = self.sample_at(time_s)
            sampling = self.sampling or ModelSignatureSampling()
            request = SpectralSignatureRequest(
                direction_frame_id=sample.visualization.frame_id,
                operating_point_id=sample.state.operating_point_id,
                source_to_observer_directions=sampling.source_to_observer_directions,
                wavelengths_m=sample.optical_profile.wavelengths_m,
                allow_partial_results=self.allow_partial_results,
            )
            samples.append(
                SignatureTimelineSample(
                    request=request,
                    result=sample.signature,
                )
            )
        ####
        return SignatureTimeline(tuple(samples))
    ####

    def query_at(
        self,
        *,
        time_s: float,
        direction_index: int,
        wavelength_index: int,
    ) -> SignatureTimelineQuery:
        """Resolve and query one Signature point at an arbitrary mission time.

        The mission state and caller-owned flow/optical resolvers are evaluated
        at ``time_s``.  Only the resulting point is selected; no values from
        neighboring Signature results are interpolated.
        """

        sample = self.sample_at(time_s)
        sampling = self.sampling or ModelSignatureSampling()
        request = SpectralSignatureRequest(
            direction_frame_id=sample.visualization.frame_id,
            operating_point_id=sample.state.operating_point_id,
            source_to_observer_directions=sampling.source_to_observer_directions,
            wavelengths_m=sample.optical_profile.wavelengths_m,
            allow_partial_results=self.allow_partial_results,
        )
        timeline_sample = SignatureTimelineSample(
            request=request,
            result=sample.signature,
        )
        return SignatureTimeline((timeline_sample,)).query_at(
            time_s=sample.state.time_s,
            direction_index=direction_index,
            wavelength_index=wavelength_index,
        )
    ####

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionSignatureSample:
        """Evaluate the state held by a cursor created from this timeline."""

        if not isinstance(cursor, MissionCursor):
            raise TypeError("cursor must be MissionCursor")
        ####
        if cursor.timeline is not self.timeline:
            raise ValueError("cursor must originate from this evaluator's timeline")
        ####
        return self._evaluate_state(cursor.state)
    ####
####


@dataclass(frozen=True, slots=True)
class MissionProductSample:
    """The visual product plus an available or explicitly blocked signature."""

    state: MissionState
    visualization: StandardizedModelVisualization
    visual_product: VisualSectionedTubeResult
    signature_assessment: ModelSignatureAssessment
    optical_profile: GrayOpticalProfile | None
    signature: SpectralSignatureResult | None
    atmospheric_path_layers: tuple[AtmosphericPathLayer, ...] | None = None

    @property
    def signature_available(self) -> bool:
        return self.signature is not None
    ####
####


@dataclass(frozen=True, slots=True)
class MissionProductEvaluator:
    """Return visual and signature products from the same mission-state sample.

    The visual product is available for every standardized model lane.  When
    an optical resolver is supplied, the signature is evaluated only if the
    lane's transport readiness is ``ready``.  Otherwise the returned sample
    preserves the visual product and exposes the typed readiness block instead
    of silently substituting a lower-fidelity signature path.
    """

    visualization_evaluator: MissionVisualizationEvaluator
    optical_profile_at: Callable[[MissionState], GrayOpticalProfile] | None = None
    sampling: ModelSignatureSampling | None = None
    allow_partial_results: bool = False
    atmospheric_path_layers_at: Callable[
        [MissionState], Sequence[AtmosphericPathLayer] | None
    ] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.visualization_evaluator, MissionVisualizationEvaluator):
            raise TypeError("visualization_evaluator must be MissionVisualizationEvaluator")
        ####
        if self.optical_profile_at is not None and not callable(self.optical_profile_at):
            raise TypeError("optical_profile_at must be callable or None")
        ####
        if self.sampling is not None and not isinstance(self.sampling, ModelSignatureSampling):
            raise TypeError("sampling must be ModelSignatureSampling or None")
        ####
        if not isinstance(self.allow_partial_results, bool):
            raise TypeError("allow_partial_results must be bool")
        ####
        if self.atmospheric_path_layers_at is not None and not callable(
            self.atmospheric_path_layers_at
        ):
            raise TypeError("atmospheric_path_layers_at must be callable or None")
        ####
    ####

    @property
    def timeline(self) -> MissionTimeline:
        return self.visualization_evaluator.timeline
    ####

    def _evaluate_visual_sample(self, visual_sample: MissionVisualizationSample) -> MissionProductSample:
        state = visual_sample.state
        optical_profile = None if self.optical_profile_at is None else self.optical_profile_at(state)
        atmospheric_path_layers = _resolve_atmospheric_path_layers(
            self.atmospheric_path_layers_at,
            state,
        )
        if optical_profile is not None and not isinstance(
            optical_profile,
            (
                GrayRadiationProfile,
                SectionedGrayRadiationProfile,
                LineRadiationProfile,
                SectionedLineRadiationProfile,
            ),
        ):
            raise TypeError("optical_profile_at must return a supported optical profile")
        ####
        assessment = assess_model_signature_readiness(
            visual_sample.visualization,
            optical_profile=optical_profile,
        )
        signature = None
        if assessment.ready and optical_profile is not None:
            signature = evaluate_model_signature(
                visual_sample.visualization,
                optical_profile,
                sampling=self.sampling,
                operating_point_id=state.operating_point_id,
                allow_partial_results=self.allow_partial_results,
                time_s=state.time_s,
                source_pose=state.source_pose,
                dynamic_state=state.snapshot_dynamic_state(),
                ambient_state=state.snapshot_ambient_state(),
                atmospheric_path_layers=atmospheric_path_layers,
                time_model=TimeModel.PRESCRIBED_TRANSIENT,
            )
        ####
        return MissionProductSample(
            state=state,
            visualization=visual_sample.visualization,
            visual_product=visual_sample.visual_product,
            signature_assessment=assessment,
            optical_profile=optical_profile,
            signature=signature,
            atmospheric_path_layers=atmospheric_path_layers,
        )
    ####

    def sample_at(self, time_s: float) -> MissionProductSample:
        """Return every currently valid product at one scheduled mission time."""

        return self._evaluate_visual_sample(self.visualization_evaluator.sample_at(time_s))
    ####

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionProductSample:
        """Return every currently valid product at the cursor's mission state."""

        return self._evaluate_visual_sample(self.visualization_evaluator.evaluate_cursor(cursor))
    ####

    def visual_at(self, time_s: float) -> VisualSectionedTubeResult:
        """Return the canonical visual product at one scheduled mission time."""

        return self.visualization_evaluator.evaluate_at(time_s)
    ####

    def signature_at(self, time_s: float) -> SpectralSignatureResult:
        """Return a signature or raise its typed, machine-readable block."""

        sample = self.sample_at(time_s)
        if sample.signature is None:
            reasons = "; ".join(sample.signature_assessment.reasons)
            raise ModelSignatureBlockedError(f"{sample.visualization.lane_id} cannot provide a mission signature ({sample.signature_assessment.readiness.value}): {reasons}")
        ####
        return sample.signature
    ####
####


@dataclass(frozen=True, slots=True)
class MissionFpaSample:
    """One explicit downstream FPA evaluation at a mission-state snapshot."""

    state: MissionState
    wavelengths_m: tuple[float, ...]
    ray_transfer: ProviderSpectralRayTransferResult
    geometry: FpaPixelGeometry
    detector: DetectorResponse
    exposure_s: float
    source: FpaSourceReference
    image: FpaPixelImage
    digitization_policy: FpaDigitizationPolicy | None
    digitized: FpaDigitizedExpectation | None
    inputs: FpaVisualizationInput
    background_spectral_radiance: tuple[tuple[float, ...], ...] | None = None
    atmospheric_path_layers: tuple[AtmosphericPathLayer, ...] | None = None

    @property
    def digitized_available(self) -> bool:
        """Whether an explicit deterministic ADC expectation was requested."""

        return self.digitized is not None
    ####
####


@dataclass(frozen=True, slots=True)
class MissionFpaTimeline:
    """Exact, compatible downstream FPA samples with no time interpolation.

    A timeline is intentionally stricter than a collection used only for
    logging: every sample must use the same wavelength axis, pixel geometry,
    and detector response.  This preserves a comparable camera/detector
    measurement space while allowing the source ray-transfer snapshot,
    exposure, and expected pixel values to evolve with mission time.
    """

    samples: tuple[MissionFpaSample, ...]

    def __post_init__(self) -> None:
        samples = tuple(self.samples)
        if not samples:
            raise ValueError("FPA timeline requires at least one sample")
        ####
        if any(not isinstance(sample, MissionFpaSample) for sample in samples):
            raise TypeError("FPA timeline samples must be MissionFpaSample")
        ####
        if any(
            second.state.time_s <= first.state.time_s
            for first, second in zip(samples, samples[1:])
        ):
            raise ValueError("FPA timeline sample times must be strictly increasing")
        ####
        reference = samples[0]
        for sample in samples[1:]:
            if sample.wavelengths_m != reference.wavelengths_m:
                raise ValueError("FPA timeline samples must use one wavelength axis")
            ####
            if sample.geometry != reference.geometry:
                raise ValueError(
                    "FPA timeline samples must use identical pixel geometry"
                )
            ####
            if sample.detector != reference.detector:
                raise ValueError(
                    "FPA timeline samples must use one detector response"
                )
            ####
        ####
        object.__setattr__(self, "samples", samples)
    ####

    @property
    def times_s(self) -> tuple[float, ...]:
        """Return the exact mission times represented by the samples."""

        return tuple(sample.state.time_s for sample in self.samples)
    ####

    @property
    def wavelengths_m(self) -> tuple[float, ...]:
        """Return the shared detector wavelength axis."""

        return self.samples[0].wavelengths_m
    ####

    @property
    def geometry(self) -> FpaPixelGeometry:
        """Return the shared pixel geometry."""

        return self.samples[0].geometry
    ####

    @property
    def detector(self) -> DetectorResponse:
        """Return the shared detector response."""

        return self.samples[0].detector
    ####

    def sample_at(self, time_s: float) -> MissionFpaSample:
        """Return one exact FPA sample; no temporal interpolation is implied."""

        selected_time_s = _finite("time_s", time_s)
        for sample in self.samples:
            if sample.state.time_s == selected_time_s:
                return sample
            ####
        ####
        raise MissionTimelineRangeError(
            f"time_s={selected_time_s} is not an exact FPA timeline sample"
        )
    ####

    def project_at(
        self,
        time_s: float,
        spec: FpaVisualizationSpec | None = None,
    ) -> FpaViewProjection:
        """Project one exact downstream sample into the renderer-neutral FPA view."""

        sample = self.sample_at(time_s)
        resolved_spec = spec or FpaVisualizationSpec.for_source(
            sample.source,
            view_kind="fpa.overview",
        )
        return project_fpa_view(sample.inputs, resolved_spec)
    ####
####


@dataclass(frozen=True, slots=True)
class MissionFpaEvaluator:
    """Evaluate an explicit ray-to-FPA chain over a prescribed mission timeline.

    The ray-transfer resolver owns the flow, chemistry, and optical source
    closures.  Optional background spectra and homogeneous atmospheric paths
    may be resolved separately for each mission state.  The remaining
    resolvers own the instrument geometry, detector response, exposure, and
    optional deterministic ADC policy.  This adapter only composes those
    declared inputs at one mission state; it does not infer a camera model,
    sample noise, or advertise an FPA provider.
    """

    timeline: MissionTimeline
    ray_transfer_at: Callable[[MissionState], MissionRayTransferAtState]
    geometry_at: Callable[[MissionState], FpaPixelGeometry]
    detector_at: Callable[[MissionState], DetectorResponse]
    exposure_s_at: Callable[[MissionState], float]
    digitization_policy_at: Callable[
        [MissionState], FpaDigitizationPolicy | None
    ] | None = None
    background_spectral_radiance_at: Callable[
        [MissionState], Sequence[Sequence[float]] | None
    ] | None = None
    atmospheric_path_layers_at: Callable[
        [MissionState], Sequence[AtmosphericPathLayer] | None
    ] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        ####
        for name in (
            "ray_transfer_at",
            "geometry_at",
            "detector_at",
            "exposure_s_at",
        ):
            if not callable(getattr(self, name)):
                raise TypeError(f"{name} must be callable")
            ####
        ####
        if self.digitization_policy_at is not None and not callable(
            self.digitization_policy_at
        ):
            raise TypeError("digitization_policy_at must be callable or None")
        ####
        if self.background_spectral_radiance_at is not None and not callable(
            self.background_spectral_radiance_at
        ):
            raise TypeError(
                "background_spectral_radiance_at must be callable or None"
            )
        ####
        if self.atmospheric_path_layers_at is not None and not callable(
            self.atmospheric_path_layers_at
        ):
            raise TypeError("atmospheric_path_layers_at must be callable or None")
        ####
    ####

    def _evaluate_state(self, state: MissionState) -> MissionFpaSample:
        resolved_ray = self.ray_transfer_at(state)
        if not isinstance(resolved_ray, tuple) or len(resolved_ray) != 2:
            raise TypeError(
                "ray_transfer_at must return (wavelengths_m, SpectralRayTransferResult)"
            )
        ####
        raw_wavelengths, ray_transfer = resolved_ray
        if not isinstance(ray_transfer, ProviderSpectralRayTransferResult):
            raise TypeError(
                "ray_transfer_at must return the provider SpectralRayTransferResult"
            )
        ####
        wavelengths = tuple(
            _finite(f"wavelengths_m[{index}]", value)
            for index, value in enumerate(raw_wavelengths)
        )
        if len(wavelengths) < 2 or any(value <= 0.0 for value in wavelengths):
            raise ValueError("wavelengths_m must contain at least two positive values")
        ####
        if any(
            right <= left for left, right in zip(wavelengths, wavelengths[1:])
        ):
            raise ValueError("wavelengths_m must be strictly increasing")
        ####

        snapshot = ray_transfer.metadata.snapshot
        if snapshot.time_s != state.time_s:
            raise ValueError(
                "ray-transfer snapshot time_s must exactly match the mission state"
            )
        ####
        if snapshot.source_pose != state.source_pose:
            raise ValueError(
                "ray-transfer snapshot source_pose must exactly match the mission state"
            )
        ####
        expected_dynamic_digest = canonical_digest(state.snapshot_dynamic_state())
        if snapshot.dynamic_state_digest_sha256 != expected_dynamic_digest:
            raise ValueError(
                "ray-transfer snapshot dynamic state must exactly match the mission state"
            )
        ####
        expected_ambient_digest = canonical_digest(state.snapshot_ambient_state())
        if snapshot.ambient_state_digest_sha256 != expected_ambient_digest:
            raise ValueError(
                "ray-transfer snapshot ambient state must exactly match the mission state"
            )
        ####

        geometry = self.geometry_at(state)
        detector = self.detector_at(state)
        if not isinstance(geometry, FpaPixelGeometry):
            raise TypeError("geometry_at must return FpaPixelGeometry")
        ####
        if not isinstance(detector, DetectorResponse):
            raise TypeError("detector_at must return DetectorResponse")
        ####
        exposure_s = _finite("exposure_s", self.exposure_s_at(state))
        if exposure_s <= 0.0:
            raise ValueError("exposure_s_at must return a positive value")
        ####
        policy = (
            None
            if self.digitization_policy_at is None
            else self.digitization_policy_at(state)
        )
        if policy is not None and not isinstance(policy, FpaDigitizationPolicy):
            raise TypeError(
                "digitization_policy_at must return FpaDigitizationPolicy or None"
            )
        ####

        background_spectral_radiance = _resolve_background_spectral_radiance(
            self.background_spectral_radiance_at,
            state,
        )
        atmospheric_path_layers = _resolve_atmospheric_path_layers(
            self.atmospheric_path_layers_at,
            state,
        )
        source = FpaSourceReference.from_ray_result(ray_transfer)
        image = integrate_spectral_ray_result_to_fpa(
            ray_transfer,
            wavelengths,
            geometry=geometry,
            detector=detector,
            exposure_s=exposure_s,
            background_spectral_radiance=background_spectral_radiance,
            atmospheric_path_layers=atmospheric_path_layers,
        )
        digitized = (
            None
            if policy is None
            else digitize_expected_electrons(image, policy=policy)
        )
        inputs = FpaVisualizationInput(
            image=image,
            source=source,
            detector_response=detector,
            digitized=digitized,
            digitization_policy=policy,
            camera_optics=geometry.camera_optics,
        )
        return MissionFpaSample(
            state=state,
            wavelengths_m=wavelengths,
            ray_transfer=ray_transfer,
            geometry=geometry,
            detector=detector,
            exposure_s=exposure_s,
            source=source,
            image=image,
            digitization_policy=policy,
            digitized=digitized,
            inputs=inputs,
            background_spectral_radiance=background_spectral_radiance,
            atmospheric_path_layers=atmospheric_path_layers,
        )
    ####

    def sample_at(self, time_s: float) -> MissionFpaSample:
        """Evaluate the downstream FPA chain at a prescribed mission time."""

        return self._evaluate_state(self.timeline.sample_at(time_s))
    ####

    def evaluate_at(self, time_s: float) -> FpaVisualizationInput:
        """Return source-bound FPA inputs at a prescribed mission time."""

        return self.sample_at(time_s).inputs
    ####

    def evaluate_timeline(self, times_s: Sequence[float]) -> MissionFpaTimeline:
        """Evaluate exact FPA snapshots at strictly increasing mission times.

        Each sample is freshly resolved through the caller-owned ray,
        geometry, detector, exposure, and digitization callbacks.  No
        temporal interpolation, cached pixel image, or detector response is
        introduced by this composition seam.
        """

        try:
            requested_times = tuple(_finite("times_s item", value) for value in times_s)
        except TypeError:
            raise TypeError("times_s must be an iterable of mission times") from None
        ####
        if not requested_times:
            raise ValueError("FPA timeline requires at least one mission time")
        ####
        if any(
            second <= first
            for first, second in zip(requested_times, requested_times[1:])
        ):
            raise ValueError("FPA timeline mission times must be strictly increasing")
        ####
        return MissionFpaTimeline(
            tuple(self.sample_at(time_s) for time_s in requested_times)
        )
    ####

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionFpaSample:
        """Evaluate a cursor originating from this evaluator's timeline."""

        if not isinstance(cursor, MissionCursor):
            raise TypeError("cursor must be MissionCursor")
        ####
        if cursor.timeline is not self.timeline:
            raise ValueError("cursor must originate from this evaluator's timeline")
        ####
        return self._evaluate_state(cursor.state)
    ####

    def project_at(
        self,
        time_s: float,
        spec: FpaVisualizationSpec | None = None,
    ) -> FpaViewProjection:
        """Return a renderer-neutral FPA projection for one mission time."""

        sample = self.sample_at(time_s)
        resolved_spec = spec or FpaVisualizationSpec.for_source(
            sample.source,
            view_kind="fpa.overview",
        )
        return project_fpa_view(sample.inputs, resolved_spec)
    ####
####
