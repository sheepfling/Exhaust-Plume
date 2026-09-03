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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import acos, isfinite, sin, sqrt
from types import MappingProxyType
from typing import Any, cast

from exhaust_plume.api.v1 import (
    Pose,
    SnapshotMetadata,
    SpectralSignatureResult,
    TimeModel,
    VisualSectionedTubeRequest,
    VisualSectionedTubeResult,
    canonical_digest,
)
from exhaust_plume.products.model_signature import (
    GrayRadiationProfile,
    ModelSignatureAssessment,
    ModelSignatureBlockedError,
    ModelSignatureSampling,
    assess_model_signature_readiness,
    evaluate_model_signature,
)
from exhaust_plume.products.model_visualization import (
    StandardizedModelVisualization,
    evaluate_standardized_model_visualization,
)

__all__ = (
    "MISSION_TIMELINE_SCHEMA",
    "MissionCursor",
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


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must be numeric") from error
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _optional_finite(name: str, value: float | None) -> float | None:
    return None if value is None else _finite(name, value)


def _copy_context(name: str, value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    copied = dict(value)
    try:
        canonical_digest(copied)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain canonicalizable contract data") from error
    return MappingProxyType(copied)


def _interpolate_scalar(first: float | None, second: float | None, fraction: float) -> float | None:
    if first is None or second is None:
        return None
    return first + (second - first) * fraction


def _normalized_quaternion(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    norm = sqrt(sum(component * component for component in value))
    return tuple(component / norm for component in value)  # type: ignore[return-value]


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
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _normalized_quaternion(
            tuple(left + (right - left) * fraction for left, right in zip(first, second_adjusted))  # type: ignore[arg-type]
        )
    angle = acos(dot)
    sine = sin(angle)
    first_weight = sin((1.0 - fraction) * angle) / sine
    second_weight = sin(fraction * angle) / sine
    return _normalized_quaternion(
        tuple(first_weight * left + second_weight * right for left, right in zip(first, second_adjusted))  # type: ignore[arg-type]
    )


def _interpolate_pose(first: Pose, second: Pose, fraction: float) -> Pose:
    if first.frame_id != second.frame_id:
        raise ValueError("mission timeline poses must use one frame_id")
    return Pose(
        frame_id=first.frame_id,
        translation_m=cast(
            tuple[float, float, float],
            tuple(left + (right - left) * fraction for left, right in zip(first.translation_m, second.translation_m)),
        ),
        rotation_xyzw=_slerp(first.rotation_xyzw, second.rotation_xyzw, fraction),
    )


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
        altitude = _optional_finite("geopotential_altitude_m", self.geopotential_altitude_m)
        throttle = _optional_finite("throttle_fraction", self.throttle_fraction)
        propellant_mass = _optional_finite(
            "remaining_propellant_mass_kg",
            self.remaining_propellant_mass_kg,
        )
        if throttle is not None and not 0.0 <= throttle <= 1.0:
            raise ValueError("throttle_fraction must lie in [0, 1]")
        if propellant_mass is not None and propellant_mass < 0.0:
            raise ValueError("remaining_propellant_mass_kg must be nonnegative")
        if self.operating_point_id is not None and not self.operating_point_id:
            raise ValueError("operating_point_id must be nonempty when supplied")
        object.__setattr__(self, "time_s", time_s)
        object.__setattr__(self, "geopotential_altitude_m", altitude)
        object.__setattr__(self, "throttle_fraction", throttle)
        object.__setattr__(self, "remaining_propellant_mass_kg", propellant_mass)
        object.__setattr__(self, "dynamic_state", _copy_context("dynamic_state", self.dynamic_state))
        object.__setattr__(self, "ambient_state", _copy_context("ambient_state", self.ambient_state))

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

    def snapshot_ambient_state(self) -> dict[str, object]:
        """Return ambient context suitable for a provider snapshot digest."""

        return {
            "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
            "time_s": self.time_s,
            "geopotential_altitude_m": self.geopotential_altitude_m,
            "declared_ambient_state": dict(self.ambient_state),
        }


class MissionTimelineRangeError(ValueError):
    """Raised when a sample or cursor advance leaves a prescribed timeline."""


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
        if any(not isinstance(state, MissionState) for state in states):
            raise TypeError("mission timeline states must be MissionState")
        if any(second.time_s <= first.time_s for first, second in zip(states, states[1:])):
            raise ValueError("mission timeline state times must be strictly increasing")
        frame_id = states[0].source_pose.frame_id
        if any(state.source_pose.frame_id != frame_id for state in states[1:]):
            raise ValueError("mission timeline poses must use one frame_id")
        for field_name in (
            "geopotential_altitude_m",
            "throttle_fraction",
            "remaining_propellant_mass_kg",
        ):
            populated = tuple(getattr(state, field_name) is not None for state in states)
            if any(populated) and not all(populated):
                raise ValueError(f"{field_name} must be supplied at every timeline state or omitted from all states")
        object.__setattr__(self, "states", states)

    @property
    def start_time_s(self) -> float:
        return self.states[0].time_s

    @property
    def end_time_s(self) -> float:
        return self.states[-1].time_s

    def sample_at(self, time_s: float) -> MissionState:
        """Return an immutable state at ``time_s`` without extrapolation."""

        requested_time_s = _finite("time_s", time_s)
        if requested_time_s < self.start_time_s or requested_time_s > self.end_time_s:
            raise MissionTimelineRangeError(f"time_s={requested_time_s} lies outside [{self.start_time_s}, {self.end_time_s}]")
        state_times = tuple(state.time_s for state in self.states)
        upper_index = bisect_left(state_times, requested_time_s)
        if self.states[upper_index].time_s == requested_time_s:
            return self.states[upper_index]
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

    def cursor_at(self, time_s: float | None = None) -> "MissionCursor":
        """Create a non-mutating cursor at the start or an exact/interpolated time."""

        return MissionCursor(
            timeline=self,
            state=self.sample_at(self.start_time_s if time_s is None else time_s),
        )


@dataclass(frozen=True, slots=True)
class MissionCursor:
    """A functional cursor: advancing returns a new cursor, never mutating history."""

    timeline: MissionTimeline
    state: MissionState

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        if not isinstance(self.state, MissionState):
            raise TypeError("state must be MissionState")
        canonical = self.timeline.sample_at(self.state.time_s)
        if canonical != self.state:
            raise ValueError("cursor state must be a sample from its timeline")

    def advance_to(self, time_s: float) -> "MissionCursor":
        """Return a cursor at a later prescribed time."""

        requested_time_s = _finite("time_s", time_s)
        if requested_time_s < self.state.time_s:
            raise ValueError("mission cursor cannot advance backward in time")
        return MissionCursor(timeline=self.timeline, state=self.timeline.sample_at(requested_time_s))

    def advance_by(self, duration_s: float) -> "MissionCursor":
        """Return a cursor advanced by a nonnegative duration."""

        resolved_duration_s = _finite("duration_s", duration_s)
        if resolved_duration_s < 0.0:
            raise ValueError("duration_s must be nonnegative")
        return self.advance_to(self.state.time_s + resolved_duration_s)


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


@dataclass(frozen=True, slots=True)
class MissionVisualizationSample:
    """A standardized lane and its canonical visual product at one mission time."""

    state: MissionState
    visualization: StandardizedModelVisualization
    visual_product: VisualSectionedTubeResult


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
        if not callable(self.visualization_at):
            raise TypeError("visualization_at must be callable")
        if not isinstance(self.request, VisualSectionedTubeRequest):
            raise TypeError("request must be VisualSectionedTubeRequest")
        if not self.provider_version:
            raise ValueError("provider_version must not be empty")

    def _evaluate_state(self, state: MissionState) -> MissionVisualizationSample:
        visualization = self.visualization_at(state)
        if not isinstance(visualization, StandardizedModelVisualization):
            raise TypeError("visualization_at must return StandardizedModelVisualization")
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

    def sample_at(self, time_s: float) -> MissionVisualizationSample:
        """Resolve and return the visual product at a scheduled mission time."""

        return self._evaluate_state(self.timeline.sample_at(time_s))

    def evaluate_at(self, time_s: float) -> VisualSectionedTubeResult:
        """Return the canonical visual sectioned-tube product at ``time_s``."""

        return self.sample_at(time_s).visual_product

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionVisualizationSample:
        """Evaluate a cursor originating from this evaluator's timeline."""

        if not isinstance(cursor, MissionCursor):
            raise TypeError("cursor must be MissionCursor")
        if cursor.timeline is not self.timeline:
            raise ValueError("cursor must originate from this evaluator's timeline")
        return self._evaluate_state(cursor.state)


@dataclass(frozen=True, slots=True)
class MissionSignatureSample:
    """One flow/signature result tied to an immutable mission-state snapshot."""

    state: MissionState
    visualization: StandardizedModelVisualization
    optical_profile: GrayRadiationProfile
    signature: SpectralSignatureResult


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
    optical_profile_at: Callable[[MissionState], GrayRadiationProfile]
    sampling: ModelSignatureSampling | None = None
    allow_partial_results: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        if not callable(self.visualization_at):
            raise TypeError("visualization_at must be callable")
        if not callable(self.optical_profile_at):
            raise TypeError("optical_profile_at must be callable")
        if self.sampling is not None and not isinstance(self.sampling, ModelSignatureSampling):
            raise TypeError("sampling must be ModelSignatureSampling or None")
        if not isinstance(self.allow_partial_results, bool):
            raise TypeError("allow_partial_results must be bool")

    def _evaluate_state(self, state: MissionState) -> MissionSignatureSample:
        visualization = self.visualization_at(state)
        optical_profile = self.optical_profile_at(state)
        if not isinstance(visualization, StandardizedModelVisualization):
            raise TypeError("visualization_at must return StandardizedModelVisualization")
        if not isinstance(optical_profile, GrayRadiationProfile):
            raise TypeError("optical_profile_at must return GrayRadiationProfile")
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
            time_model=TimeModel.PRESCRIBED_TRANSIENT,
        )
        return MissionSignatureSample(
            state=state,
            visualization=visualization,
            optical_profile=optical_profile,
            signature=signature,
        )

    def sample_at(self, time_s: float) -> MissionSignatureSample:
        """Resolve flow/optics and evaluate the spectral signature at one time."""

        return self._evaluate_state(self.timeline.sample_at(time_s))

    def evaluate_at(self, time_s: float) -> SpectralSignatureResult:
        """Return the far-field spectral radiant-intensity product at one time."""

        return self.sample_at(time_s).signature

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionSignatureSample:
        """Evaluate the state held by a cursor created from this timeline."""

        if not isinstance(cursor, MissionCursor):
            raise TypeError("cursor must be MissionCursor")
        if cursor.timeline is not self.timeline:
            raise ValueError("cursor must originate from this evaluator's timeline")
        return self._evaluate_state(cursor.state)


@dataclass(frozen=True, slots=True)
class MissionProductSample:
    """The visual product plus an available or explicitly blocked signature."""

    state: MissionState
    visualization: StandardizedModelVisualization
    visual_product: VisualSectionedTubeResult
    signature_assessment: ModelSignatureAssessment
    optical_profile: GrayRadiationProfile | None
    signature: SpectralSignatureResult | None

    @property
    def signature_available(self) -> bool:
        return self.signature is not None


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
    optical_profile_at: Callable[[MissionState], GrayRadiationProfile] | None = None
    sampling: ModelSignatureSampling | None = None
    allow_partial_results: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.visualization_evaluator, MissionVisualizationEvaluator):
            raise TypeError("visualization_evaluator must be MissionVisualizationEvaluator")
        if self.optical_profile_at is not None and not callable(self.optical_profile_at):
            raise TypeError("optical_profile_at must be callable or None")
        if self.sampling is not None and not isinstance(self.sampling, ModelSignatureSampling):
            raise TypeError("sampling must be ModelSignatureSampling or None")
        if not isinstance(self.allow_partial_results, bool):
            raise TypeError("allow_partial_results must be bool")

    @property
    def timeline(self) -> MissionTimeline:
        return self.visualization_evaluator.timeline

    def _evaluate_visual_sample(self, visual_sample: MissionVisualizationSample) -> MissionProductSample:
        state = visual_sample.state
        optical_profile = None if self.optical_profile_at is None else self.optical_profile_at(state)
        if optical_profile is not None and not isinstance(optical_profile, GrayRadiationProfile):
            raise TypeError("optical_profile_at must return GrayRadiationProfile")
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
                time_model=TimeModel.PRESCRIBED_TRANSIENT,
            )
        return MissionProductSample(
            state=state,
            visualization=visual_sample.visualization,
            visual_product=visual_sample.visual_product,
            signature_assessment=assessment,
            optical_profile=optical_profile,
            signature=signature,
        )

    def sample_at(self, time_s: float) -> MissionProductSample:
        """Return every currently valid product at one scheduled mission time."""

        return self._evaluate_visual_sample(self.visualization_evaluator.sample_at(time_s))

    def evaluate_cursor(self, cursor: MissionCursor) -> MissionProductSample:
        """Return every currently valid product at the cursor's mission state."""

        return self._evaluate_visual_sample(self.visualization_evaluator.evaluate_cursor(cursor))

    def visual_at(self, time_s: float) -> VisualSectionedTubeResult:
        """Return the canonical visual product at one scheduled mission time."""

        return self.visualization_evaluator.evaluate_at(time_s)

    def signature_at(self, time_s: float) -> SpectralSignatureResult:
        """Return a signature or raise its typed, machine-readable block."""

        sample = self.sample_at(time_s)
        if sample.signature is None:
            reasons = "; ".join(sample.signature_assessment.reasons)
            raise ModelSignatureBlockedError(f"{sample.visualization.lane_id} cannot provide a mission signature ({sample.signature_assessment.readiness.value}): {reasons}")
        return sample.signature
