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
from dataclasses import dataclass, field, replace
from math import acos, isfinite, sin, sqrt
from types import MappingProxyType
from typing import Any, TypeAlias, cast

from exhaust_plume.contracts.ray_transfer_v1 import (
    SpectralRayTransferRequest,
    SpectralRayTransferResult as ProviderSpectralRayTransferResult,
)
from exhaust_plume.contracts.common_v1 import (
    ProductClaims,
    SampleStatus,
)

from exhaust_plume.api.v1 import (
    FpaDetectorFrameResult,
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
    FPA_TEMPORAL_EXPOSURE_OPERATOR_ID,
    FpaDigitizationPolicy,
    FpaDigitizedExpectation,
    FpaPixelGeometry,
    FpaPixelImage,
    digitize_expected_electrons,
    integrate_fpa_exposure_samples,
    integrate_spectral_ray_result_to_fpa,
)
from exhaust_plume.validation.fpa_visualization import (
    FpaSourceReference,
    FpaViewProjection,
    FpaVisualizationInput,
    FpaVisualizationSpec,
    project_fpa_view,
)
from exhaust_plume.validation.fpa_detector_frame import to_fpa_detector_frame
from exhaust_plume.validation.sensor_operators import AtmosphericPathLayer

__all__ = (
    "MISSION_STATE_EVOLUTION_SCHEMA",
    "MISSION_TIMELINE_SCHEMA",
    "MissionCursor",
    "MissionEvolutionCursor",
    "MissionFpaEvaluator",
    "MissionFpaExposure",
    "MissionFpaSample",
    "MissionFpaTimeline",
    "MissionRayRadianceQuery",
    "MissionRayTransferEvaluator",
    "MissionRayTransferSample",
    "MissionProductEvaluator",
    "MissionProductSample",
    "MissionSignatureEvaluator",
    "MissionSignatureSample",
    "MissionState",
    "MissionStateStepper",
    "MissionStateTransition",
    "MissionTimeline",
    "MissionTimelineRangeError",
    "MissionVisualizationEvaluator",
    "MissionVisualizationSample",
    "MissionVisualizationTimeline",
)


MISSION_TIMELINE_SCHEMA = "plume.mission-timeline@1"
MISSION_STATE_EVOLUTION_SCHEMA = "plume.mission-state-evolution@1"

MissionRayTransferAtState: TypeAlias = tuple[
    SpectralRayTransferRequest,
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
    return cast(Mapping[str, object], _freeze_context(copied))
####


def _freeze_context(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_context(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_context(item) for item in value)
    return value
####


def _thaw_context(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_context(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_context(item) for item in value]
    return value
####


def _copy_continuous_state(value: Mapping[str, object]) -> Mapping[str, float]:
    if not isinstance(value, Mapping):
        raise TypeError("continuous_state must be a mapping")
    ####
    copied: dict[str, float] = {}
    for key, sample in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("continuous_state keys must be nonempty strings")
        ####
        copied[key] = _finite(f"continuous_state[{key}]", sample)
    ####
    return MappingProxyType(copied)
####


def _interpolate_continuous_state(
    first: Mapping[str, float],
    second: Mapping[str, float],
    fraction: float,
) -> dict[str, float]:
    return {
        key: first[key] + (second[key] - first[key]) * fraction
        for key in first
    }
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
    operating condition wholly from ``continuous_state`` or ``dynamic_state``.
    ``continuous_state`` carries named numeric operating values such as
    chemistry fractions or chamber controls; it is interpolated between
    schedule nodes. ``dynamic_state`` and ``ambient_state`` carry categorical
    or model-specific context and are held from the lower node. The timeline
    never derives chemistry, engine depletion, or atmosphere from those values.
    """

    time_s: float
    source_pose: Pose
    geopotential_altitude_m: float | None = None
    throttle_fraction: float | None = None
    remaining_propellant_mass_kg: float | None = None
    operating_point_id: str | None = None
    dynamic_state: Mapping[str, object] = field(default_factory=dict)
    ambient_state: Mapping[str, object] = field(default_factory=dict)
    continuous_state: Mapping[str, float] = field(default_factory=dict)
    evolution_provenance: Mapping[str, object] = field(default_factory=dict)

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
        object.__setattr__(self, "continuous_state", _copy_continuous_state(self.continuous_state))
        object.__setattr__(
            self,
            "evolution_provenance",
            _copy_context("evolution_provenance", self.evolution_provenance),
        )
    ####

    def snapshot_dynamic_state(self) -> dict[str, object]:
        """Return declared vehicle state suitable for a provider snapshot digest."""

        snapshot: dict[str, object] = {
            "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
            "time_s": self.time_s,
            "geopotential_altitude_m": self.geopotential_altitude_m,
            "throttle_fraction": self.throttle_fraction,
            "remaining_propellant_mass_kg": self.remaining_propellant_mass_kg,
            "operating_point_id": self.operating_point_id,
            "declared_dynamic_state": _thaw_context(self.dynamic_state),
            "continuous_operating_state": dict(self.continuous_state),
        }
        if self.evolution_provenance:
            snapshot["evolution_provenance"] = _thaw_context(
                self.evolution_provenance
            )
        return snapshot
    ####

    @property
    def fingerprint_sha256(self) -> str:
        """Return a digest of the exact mission state and its transition lineage."""

        return canonical_digest(
            {
                "schema": MISSION_TIMELINE_SCHEMA,
                "source_pose": self.source_pose,
                "dynamic_state": self.snapshot_dynamic_state(),
                "ambient_state": self.snapshot_ambient_state(),
            }
        )
    ####

    def snapshot_ambient_state(self) -> dict[str, object]:
        """Return ambient context suitable for a provider snapshot digest."""

        return {
            "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
            "time_s": self.time_s,
            "geopotential_altitude_m": self.geopotential_altitude_m,
            "declared_ambient_state": _thaw_context(self.ambient_state),
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


def _resolve_mission_ray_transfer(
    state: MissionState,
    resolver: Callable[[MissionState], MissionRayTransferAtState],
) -> MissionRayTransferAtState:
    """Resolve one ray result and prove that it belongs to the exact state."""

    resolved_ray = resolver(state)
    if not isinstance(resolved_ray, tuple) or len(resolved_ray) != 2:
        raise TypeError(
            "ray_transfer_at must return (SpectralRayTransferRequest, SpectralRayTransferResult)"
        )
    ####
    ray_request, ray_transfer = resolved_ray
    if not isinstance(ray_request, SpectralRayTransferRequest):
        raise TypeError(
            "ray_transfer_at must return the exact SpectralRayTransferRequest"
        )
    ####
    if not isinstance(ray_transfer, ProviderSpectralRayTransferResult):
        raise TypeError(
            "ray_transfer_at must return the provider SpectralRayTransferResult"
        )
    ####
    if ray_transfer.metadata.request_digest_sha256 != canonical_digest(ray_request):
        raise ValueError(
            "ray-transfer result request digest must exactly match the supplied request"
        )
    ####
    if ray_transfer.metadata.output_frame_id != ray_request.ray_frame_id:
        raise ValueError(
            "ray-transfer result output frame must exactly match the ray request frame"
        )
    ####
    if (
        len(ray_transfer.source_spectral_radiance) != len(ray_request.ray_origins_m)
        or any(
            len(row) != len(ray_request.wavelengths_m)
            for row in ray_transfer.source_spectral_radiance
        )
    ):
        raise ValueError("ray-transfer result axes must match the exact request")
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
    return ray_request, ray_transfer
####


class MissionTimelineRangeError(ValueError):
    """Raised when a sample or cursor advance leaves a prescribed timeline."""
####


@dataclass(frozen=True, slots=True)
class MissionTimeline:
    """A bounded prescribed mission schedule with deterministic interpolation.

    Translation, attitude, altitude, throttle, remaining propellant mass, and
    named ``continuous_state`` values are interpolated between nodes.
    ``operating_point_id``, ``dynamic_state``, and ``ambient_state`` are held
    from the lower node because they are discrete/model-specific declarations.
    Continuous values must have the same keys at every node. Exact node samples
    always preserve the original declared state.
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
        continuous_keys = tuple(sorted(states[0].continuous_state))
        if any(
            tuple(sorted(state.continuous_state)) != continuous_keys
            for state in states[1:]
        ):
            raise ValueError(
                "continuous_state keys must match at every timeline state"
            )
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
            continuous_state=_interpolate_continuous_state(
                lower.continuous_state,
                upper.continuous_state,
                fraction,
            ),
            evolution_provenance=(
                {}
                if not (lower.evolution_provenance or upper.evolution_provenance)
                else {
                    "schema": MISSION_STATE_EVOLUTION_SCHEMA,
                    "kind": "prescribed-interpolation",
                    "lower_state_fingerprint_sha256": lower.fingerprint_sha256,
                    "upper_state_fingerprint_sha256": upper.fingerprint_sha256,
                    "fraction": fraction,
                }
            ),
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


MissionStateTransition: TypeAlias = Callable[[MissionState, float], MissionState]


@dataclass(frozen=True, slots=True)
class MissionStateStepper:
    """Caller-owned vehicle-state transition used for explicit mission stepping.

    The transition receives an immutable state and a duration in seconds, and
    returns the complete state at the resulting mission time. The caller owns
    trajectory, burn, propellant, atmosphere, and operating-point physics;
    this adapter validates time/frame continuity and records versioned state
    lineage for product evaluators. Reproducibility depends on
    the caller keeping a given stepper identity/version deterministic.
    """

    stepper_id: str
    stepper_version: str
    transition: MissionStateTransition

    def __post_init__(self) -> None:
        if not isinstance(self.stepper_id, str) or not self.stepper_id.strip():
            raise ValueError("stepper_id must be a nonempty string")
        if (
            not isinstance(self.stepper_version, str)
            or not self.stepper_version.strip()
        ):
            raise ValueError("stepper_version must be a nonempty string")
        if not callable(self.transition):
            raise TypeError("transition must be callable")
    ####

    def start(self, initial_state: MissionState) -> "MissionEvolutionCursor":
        """Create an immutable evolution cursor from one exact initial state."""

        if not isinstance(initial_state, MissionState):
            raise TypeError("initial_state must be MissionState")
        initial_fingerprint = initial_state.fingerprint_sha256
        evolution_id = canonical_digest(
            {
                "schema": MISSION_STATE_EVOLUTION_SCHEMA,
                "stepper_id": self.stepper_id,
                "stepper_version": self.stepper_version,
                "initial_state_fingerprint_sha256": initial_fingerprint,
            }
        )
        state = replace(
            initial_state,
            evolution_provenance={
                "schema": MISSION_STATE_EVOLUTION_SCHEMA,
                "evolution_id": evolution_id,
                "stepper_id": self.stepper_id,
                "stepper_version": self.stepper_version,
                "step_index": 0,
                "parent_state_fingerprint_sha256": initial_fingerprint,
                "duration_s": 0.0,
            },
        )
        return MissionEvolutionCursor(
            stepper=self,
            state=state,
            evolution_id=evolution_id,
            step_index=0,
        )
    ####

    def evolve(
        self,
        initial_state: MissionState,
        step_durations_s: Sequence[float],
    ) -> MissionTimeline:
        """Run explicit state steps and return a product-ready mission schedule."""

        try:
            raw_durations = tuple(step_durations_s)
        except TypeError as error:
            raise TypeError("step_durations_s must be an iterable of durations") from error
        durations = tuple(
            _finite("step_durations_s item", duration)
            for duration in raw_durations
        )
        if any(duration <= 0.0 for duration in durations):
            raise ValueError("step durations must be positive")
        cursor = self.start(initial_state)
        states = [cursor.state]
        for duration in durations:
            cursor = cursor.advance_by(duration)
            states.append(cursor.state)
        return MissionTimeline(tuple(states))
    ####
####


@dataclass(frozen=True, slots=True)
class MissionEvolutionCursor:
    """Functional cursor that advances through caller-supplied state dynamics."""

    stepper: MissionStateStepper
    state: MissionState
    evolution_id: str
    step_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.stepper, MissionStateStepper):
            raise TypeError("stepper must be MissionStateStepper")
        if not isinstance(self.state, MissionState):
            raise TypeError("state must be MissionState")
        if (
            not isinstance(self.evolution_id, str)
            or len(self.evolution_id) != 64
            or any(character not in "0123456789abcdef" for character in self.evolution_id)
        ):
            raise ValueError("evolution_id must be a lowercase SHA-256 digest")
        if (
            isinstance(self.step_index, bool)
            or not isinstance(self.step_index, int)
            or self.step_index < 0
        ):
            raise ValueError("step_index must be a nonnegative integer")
        provenance = self.state.evolution_provenance
        if (
            provenance.get("schema") != MISSION_STATE_EVOLUTION_SCHEMA
            or provenance.get("evolution_id") != self.evolution_id
            or provenance.get("stepper_id") != self.stepper.stepper_id
            or provenance.get("stepper_version") != self.stepper.stepper_version
            or provenance.get("step_index") != self.step_index
        ):
            raise ValueError("cursor state must retain its exact evolution provenance")
    ####

    def advance_by(self, duration_s: float) -> "MissionEvolutionCursor":
        """Return a new cursor after one caller-defined state transition."""

        duration = _finite("duration_s", duration_s)
        if duration < 0.0:
            raise ValueError("duration_s must be nonnegative")
        if duration == 0.0:
            return self
        input_fingerprint = self.state.fingerprint_sha256
        next_state = self.stepper.transition(self.state, duration)
        if not isinstance(next_state, MissionState):
            raise TypeError("transition must return MissionState")
        if self.state.fingerprint_sha256 != input_fingerprint:
            raise ValueError("transition must not mutate its input mission state")
        expected_time = self.state.time_s + duration
        time_tolerance = 1.0e-12 * max(1.0, abs(expected_time))
        if abs(next_state.time_s - expected_time) > time_tolerance:
            raise ValueError(
                "transition result time_s must equal the input time plus duration"
            )
        if next_state.source_pose.frame_id != self.state.source_pose.frame_id:
            raise ValueError("transition must preserve the source-pose frame")
        next_state = replace(
            next_state,
            time_s=expected_time,
            evolution_provenance={
                "schema": MISSION_STATE_EVOLUTION_SCHEMA,
                "evolution_id": self.evolution_id,
                "stepper_id": self.stepper.stepper_id,
                "stepper_version": self.stepper.stepper_version,
                "step_index": self.step_index + 1,
                "parent_state_fingerprint_sha256": input_fingerprint,
                "duration_s": duration,
            },
        )
        return MissionEvolutionCursor(
            stepper=self.stepper,
            state=next_state,
            evolution_id=self.evolution_id,
            step_index=self.step_index + 1,
        )
    ####

    def advance_to(self, time_s: float) -> "MissionEvolutionCursor":
        """Return a new cursor at an explicit later mission time."""

        target = _finite("time_s", time_s)
        if target < self.state.time_s:
            raise ValueError("mission evolution cursor cannot advance backward")
        return self.advance_by(target - self.state.time_s)
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
class MissionVisualizationTimeline:
    """Exact, schema-compatible visual snapshots for mission playback.

    Each sample is a freshly evaluated visual product.  The timeline keeps
    geometry and field arrays comparable by requiring one model lane, output
    frame, section count, and channel schema; it never interpolates visual
    geometry or feature values between mission times.
    """

    samples: tuple[MissionVisualizationSample, ...]

    def __post_init__(self) -> None:
        samples = tuple(self.samples)
        if not samples:
            raise ValueError("Visualization timeline requires at least one sample")
        ####
        if any(
            not isinstance(sample, MissionVisualizationSample)
            for sample in samples
        ):
            raise TypeError(
                "Visualization timeline samples must be MissionVisualizationSample"
            )
        ####
        if any(
            second.state.time_s <= first.state.time_s
            for first, second in zip(samples, samples[1:])
        ):
            raise ValueError(
                "Visualization timeline sample times must be strictly increasing"
            )
        ####
        reference = samples[0]
        reference_visualization = reference.visualization
        reference_product = reference.visual_product
        reference_channel_names = tuple(reference_product.channels)
        reference_section_channel_ids = tuple(
            channel.channel_id
            for channel in reference_visualization.section_channels
        )
        reference_section_count = len(reference_product.sections)
        for sample in samples:
            product = sample.visual_product
            visualization = sample.visualization
            if product.metadata.snapshot.time_s != sample.state.time_s:
                raise ValueError(
                    "Visualization timeline product time must equal mission state time"
                )
            ####
            if sample.state.source_pose.frame_id != reference.state.source_pose.frame_id:
                raise ValueError(
                    "Visualization timeline samples must use one source-pose frame_id"
                )
            ####
            if visualization.lane != reference_visualization.lane:
                raise ValueError(
                    "Visualization timeline samples must use one model visualization lane"
                )
            ####
            if (
                visualization.model_id != reference_visualization.model_id
                or visualization.model_version != reference_visualization.model_version
            ):
                raise ValueError(
                    "Visualization timeline samples must use one model identity"
                )
            ####
            if visualization.frame_id != reference_visualization.frame_id:
                raise ValueError(
                    "Visualization timeline samples must use one visualization frame_id"
                )
            ####
            if product.metadata.output_frame_id != reference_product.metadata.output_frame_id:
                raise ValueError(
                    "Visualization timeline samples must use one output_frame_id"
                )
            ####
            if len(product.sections) != reference_section_count:
                raise ValueError(
                    "Visualization timeline samples must use one section count"
                )
            ####
            if tuple(product.channels) != reference_channel_names:
                raise ValueError(
                    "Visualization timeline samples must use one visual channel schema"
                )
            ####
            if tuple(
                channel.channel_id for channel in visualization.section_channels
            ) != reference_section_channel_ids:
                raise ValueError(
                    "Visualization timeline samples must use one section channel schema"
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
    def lane_id(self) -> str:
        """Return the single model lane used throughout the timeline."""

        return self.samples[0].visualization.lane_id
    ####

    @property
    def output_frame_id(self) -> str:
        """Return the shared canonical Visualization output frame."""

        return self.samples[0].visual_product.metadata.output_frame_id
    ####

    @property
    def source_positions_m(self) -> tuple[tuple[float, float, float], ...]:
        """Return the source trajectory positions at each exact sample time."""

        return tuple(sample.state.source_pose.translation_m for sample in self.samples)
    ####

    @property
    def visual_products(self) -> tuple[VisualSectionedTubeResult, ...]:
        """Return the canonical visual products in time order."""

        return tuple(sample.visual_product for sample in self.samples)
    ####

    def sample_at(self, time_s: float) -> MissionVisualizationSample:
        """Return one exact visual sample; no temporal interpolation is implied."""

        selected_time_s = _finite("time_s", time_s)
        for sample in self.samples:
            if sample.state.time_s == selected_time_s:
                return sample
            ####
        ####
        raise MissionTimelineRangeError(
            f"time_s={selected_time_s} is not an exact Visualization timeline sample"
        )
    ####
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

    def evaluate_timeline(
        self,
        times_s: Sequence[float],
    ) -> MissionVisualizationTimeline:
        """Evaluate exact Visualization snapshots at increasing mission times.

        Each requested time is freshly resolved through ``visualization_at``.
        The returned timeline validates that the snapshots remain in one
        renderer-comparable lane and schema; no visual values are interpolated.
        """

        try:
            requested_times = tuple(_finite("times_s item", value) for value in times_s)
        except TypeError:
            raise TypeError("times_s must be an iterable of mission times") from None
        ####
        if not requested_times:
            raise ValueError("Visualization timeline requires at least one mission time")
        ####
        if any(
            second <= first
            for first, second in zip(requested_times, requested_times[1:])
        ):
            raise ValueError(
                "Visualization timeline mission times must be strictly increasing"
            )
        ####
        return MissionVisualizationTimeline(
            tuple(self.sample_at(time_s) for time_s in requested_times)
        )
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
class MissionRayRadianceQuery:
    """One exact mission-time spectral radiance value for one requested ray.

    ``source_position_m`` is the booster/plume source pose in its declared
    frame. ``ray_origin_m`` and ``ray_direction`` use ``ray_frame_id``; this
    query does not imply a coordinate transform between those frames or claim
    a pointwise radiance field inside the plume. The optional uncertainty is
    the provider-reported absolute standard uncertainty for this exact source
    radiance sample; ``None`` means no estimate was supplied.
    """

    state_fingerprint_sha256: str
    capability_id: str
    result_id: str
    request_digest_sha256: str
    snapshot_id: str
    session_id: str
    time_s: float
    source_position_frame_id: str
    source_position_m: tuple[float, float, float]
    source_altitude_m: float | None
    ray_frame_id: str
    ray_index: int
    ray_origin_m: tuple[float, float, float]
    ray_direction: tuple[float, float, float]
    wavelength_index: int
    wavelength_m: float
    spectral_radiance_W_m2_sr_m: float | None
    absolute_standard_uncertainty_W_m2_sr_m: float | None
    background_transmittance: float | None
    valid: bool
    hit: bool
    plume_intersection_t_m: tuple[float, float] | None
    status: SampleStatus
    claims: ProductClaims
####


@dataclass(frozen=True, slots=True)
class MissionRayTransferSample:
    """The exact request/result pair resolved for one mission-state snapshot."""

    state: MissionState
    request: SpectralRayTransferRequest
    result: ProviderSpectralRayTransferResult

    def __post_init__(self) -> None:
        if not isinstance(self.state, MissionState):
            raise TypeError("state must be MissionState")
        ####
        request, result = _resolve_mission_ray_transfer(
            self.state,
            lambda _state: (self.request, self.result),
        )
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "result", result)
    ####

    def query_at(
        self,
        *,
        ray_index: int,
        wavelength_index: int,
    ) -> MissionRayRadianceQuery:
        """Return one exact ray/wavelength radiance point without interpolation."""

        if isinstance(ray_index, bool) or not isinstance(ray_index, int):
            raise TypeError("ray_index must be an integer")
        ####
        if not 0 <= ray_index < len(self.request.ray_origins_m):
            raise ValueError("ray_index is outside the exact ray request")
        ####
        if isinstance(wavelength_index, bool) or not isinstance(wavelength_index, int):
            raise TypeError("wavelength_index must be an integer")
        ####
        if not 0 <= wavelength_index < len(self.request.wavelengths_m):
            raise ValueError("wavelength_index is outside the exact wavelength axis")
        ####
        valid = self.result.validity_mask[ray_index][wavelength_index]
        radiance = (
            self.result.source_spectral_radiance[ray_index][wavelength_index]
            if valid
            else None
        )
        uncertainty = (
            self.result.absolute_standard_uncertainty[ray_index][wavelength_index]
            if valid and self.result.absolute_standard_uncertainty is not None
            else None
        )
        transmittance = (
            self.result.background_transmittance[ray_index][wavelength_index]
            if valid
            else None
        )
        snapshot = self.result.metadata.snapshot
        return MissionRayRadianceQuery(
            state_fingerprint_sha256=self.state.fingerprint_sha256,
            capability_id=self.result.metadata.capability.wire_id,
            result_id=self.result.metadata.result_id,
            request_digest_sha256=self.result.metadata.request_digest_sha256,
            snapshot_id=snapshot.snapshot_id,
            session_id=snapshot.session_id,
            time_s=self.state.time_s,
            source_position_frame_id=self.state.source_pose.frame_id,
            source_position_m=self.state.source_pose.translation_m,
            source_altitude_m=self.state.geopotential_altitude_m,
            ray_frame_id=self.request.ray_frame_id,
            ray_index=ray_index,
            ray_origin_m=self.request.ray_origins_m[ray_index],
            ray_direction=self.request.ray_directions[ray_index],
            wavelength_index=wavelength_index,
            wavelength_m=self.request.wavelengths_m[wavelength_index],
            spectral_radiance_W_m2_sr_m=radiance,
            absolute_standard_uncertainty_W_m2_sr_m=uncertainty,
            background_transmittance=transmittance,
            valid=valid,
            hit=self.result.hit_mask[ray_index],
            plume_intersection_t_m=(
                None
                if self.result.plume_intersection_t_m is None
                else self.result.plume_intersection_t_m[ray_index]
            ),
            status=self.result.ray_status[ray_index],
            claims=self.result.metadata.claims,
        )
    ####
####


@dataclass(frozen=True, slots=True)
class MissionRayTransferEvaluator:
    """Resolve and query source spectral radiance at prescribed mission times."""

    timeline: MissionTimeline
    ray_transfer_at: Callable[[MissionState], MissionRayTransferAtState]

    def __post_init__(self) -> None:
        if not isinstance(self.timeline, MissionTimeline):
            raise TypeError("timeline must be MissionTimeline")
        ####
        if not callable(self.ray_transfer_at):
            raise TypeError("ray_transfer_at must be callable")
    ####

    def sample_at(self, time_s: float) -> MissionRayTransferSample:
        """Resolve one exact mission state and its ray-transfer result."""

        state = self.timeline.sample_at(time_s)
        resolved_ray = self.ray_transfer_at(state)
        if not isinstance(resolved_ray, tuple) or len(resolved_ray) != 2:
            raise TypeError(
                "ray_transfer_at must return (SpectralRayTransferRequest, SpectralRayTransferResult)"
            )
        ####
        return MissionRayTransferSample(
            state=state,
            request=resolved_ray[0],
            result=resolved_ray[1],
        )
    ####

    def query_at(
        self,
        *,
        time_s: float,
        ray_index: int,
        wavelength_index: int,
    ) -> MissionRayRadianceQuery:
        """Resolve time and return an exact ray/wavelength radiance value.

        The caller-owned resolver runs on the requested mission state. Values
        from neighboring mission times are never interpolated.
        """

        return self.sample_at(time_s).query_at(
            ray_index=ray_index,
            wavelength_index=wavelength_index,
        )
    ####
####


@dataclass(frozen=True, slots=True)
class MissionFpaSample:
    """One explicit downstream FPA evaluation at a mission-state snapshot."""

    state: MissionState
    ray_request: SpectralRayTransferRequest
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
    def wavelengths_m(self) -> tuple[float, ...]:
        """Return the wavelength axis retained by the exact ray request."""

        return self.ray_request.wavelengths_m
    ####

    @property
    def digitized_available(self) -> bool:
        """Whether an explicit deterministic ADC expectation was requested."""

        return self.digitized is not None
    ####

    def to_detector_frame_result(self) -> FpaDetectorFrameResult:
        """Serialize this exact mission snapshot into the downstream FPA contract."""

        return to_fpa_detector_frame(self.inputs, geometry=self.geometry)
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
        resolved_spec = spec or FpaVisualizationSpec.for_input(
            sample.inputs,
            view_kind="fpa.overview",
        )
        return project_fpa_view(sample.inputs, resolved_spec)
    ####
####


@dataclass(frozen=True, slots=True)
class MissionFpaExposure:
    """One source-bound detector exposure integrated over mission-time samples."""

    sample_times_s: tuple[float, ...]
    samples: tuple[MissionFpaSample, ...]
    image: FpaPixelImage
    source: FpaSourceReference
    digitization_policy: FpaDigitizationPolicy | None
    digitized: FpaDigitizedExpectation | None
    inputs: FpaVisualizationInput

    def __post_init__(self) -> None:
        times = tuple(_finite("sample_times_s item", value) for value in self.sample_times_s)
        samples = tuple(self.samples)
        if len(times) < 2 or len(samples) != len(times):
            raise ValueError("an exposure requires matching times and at least two samples")
        ####
        if any(not isinstance(sample, MissionFpaSample) for sample in samples):
            raise TypeError("exposure samples must be MissionFpaSample values")
        ####
        if times != tuple(sample.state.time_s for sample in samples):
            raise ValueError("exposure sample times must match the retained mission samples")
        ####
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError("exposure sample times must be strictly increasing")
        ####
        if not isinstance(self.image, FpaPixelImage):
            raise TypeError("image must be FpaPixelImage")
        ####
        if self.digitization_policy is not None and not isinstance(
            self.digitization_policy, FpaDigitizationPolicy
        ):
            raise TypeError("digitization_policy must be FpaDigitizationPolicy or None")
        ####
        if self.digitized is not None and not isinstance(
            self.digitized, FpaDigitizedExpectation
        ):
            raise TypeError("digitized must be FpaDigitizedExpectation or None")
        ####
        if self.image.exposure_s != times[-1] - times[0]:
            raise ValueError("integrated image exposure_s must equal the sampled interval")
        ####
        if not isinstance(self.source, FpaSourceReference):
            raise TypeError("source must be FpaSourceReference")
        ####
        if not isinstance(self.inputs, FpaVisualizationInput):
            raise TypeError("inputs must be FpaVisualizationInput")
        ####
        if self.inputs.image != self.image or self.inputs.source != self.source:
            raise ValueError("exposure visualization inputs must retain the integrated image and source")
        ####
        if self.inputs.digitized != self.digitized:
            raise ValueError("exposure visualization inputs must retain the digitized result")
        ####
        if self.inputs.digitization_policy != self.digitization_policy:
            raise ValueError("exposure visualization inputs must retain the digitization policy")
        ####
        object.__setattr__(self, "sample_times_s", times)
        object.__setattr__(self, "samples", samples)
    ####

    def to_detector_frame_result(self) -> FpaDetectorFrameResult:
        """Serialize this integrated exposure with its exact sample-time lineage."""

        return to_fpa_detector_frame(self.inputs, geometry=self.samples[0].geometry)
    ####

    @property
    def start_time_s(self) -> float:
        return self.sample_times_s[0]
    ####

    @property
    def end_time_s(self) -> float:
        return self.sample_times_s[-1]
    ####

    @property
    def exposure_s(self) -> float:
        return self.end_time_s - self.start_time_s
    ####

    @property
    def digitized_available(self) -> bool:
        return self.digitized is not None
    ####

    def project(self, spec: FpaVisualizationSpec | None = None) -> FpaViewProjection:
        """Project the integrated exposure into the renderer-neutral FPA view."""

        resolved_spec = spec or FpaVisualizationSpec.for_input(
            self.inputs,
            view_kind="fpa.exposure.integrated",
        )
        return project_fpa_view(self.inputs, resolved_spec)
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

    def _evaluate_state(
        self,
        state: MissionState,
        *,
        exposure_s_override: float | None = None,
    ) -> MissionFpaSample:
        ray_request, ray_transfer = _resolve_mission_ray_transfer(
            state,
            self.ray_transfer_at,
        )
        ####
        wavelengths = tuple(ray_request.wavelengths_m)
        if len(wavelengths) < 2 or any(value <= 0.0 for value in wavelengths):
            raise ValueError("wavelengths_m must contain at least two positive values")
        ####
        if any(
            right <= left for left, right in zip(wavelengths, wavelengths[1:])
        ):
            raise ValueError("wavelengths_m must be strictly increasing")
        ####

        geometry = self.geometry_at(state)
        detector = self.detector_at(state)
        if not isinstance(geometry, FpaPixelGeometry):
            raise TypeError("geometry_at must return FpaPixelGeometry")
        ####
        if not isinstance(detector, DetectorResponse):
            raise TypeError("detector_at must return DetectorResponse")
        ####
        exposure_s = _finite(
            "exposure_s",
            self.exposure_s_at(state)
            if exposure_s_override is None
            else exposure_s_override,
        )
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
            ray_request,
            ray_transfer,
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
            ray_request=ray_request,
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

    def integrate_exposure(
        self,
        sample_times_s: Sequence[float],
    ) -> MissionFpaExposure:
        """Integrate a fresh source and detector evaluation over one exposure.

        ``sample_times_s`` supplies the exposure endpoints and quadrature
        samples. The ray, atmosphere, background, geometry, and detector
        resolvers are evaluated independently at each exact mission state.
        Each evaluation uses a one-second detector image as the instantaneous
        electron rate; the exposure is then integrated with the composite
        trapezoid rule. ``exposure_s_at`` remains the duration policy for
        single-time ``sample_at`` calls and is not used to weight this
        explicitly bounded interval.
        """

        try:
            times = tuple(
                _finite("sample_times_s item", value)
                for value in sample_times_s
            )
        except TypeError as error:
            raise TypeError("sample_times_s must be an iterable of mission times") from error
        ####
        if len(times) < 2:
            raise ValueError("an exposure requires at least two mission times")
        ####
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError("exposure sample times must be strictly increasing")
        ####
        samples = tuple(
            self._evaluate_state(
                self.timeline.sample_at(time_s),
                exposure_s_override=1.0,
            )
            for time_s in times
        )
        ####
        MissionFpaTimeline(samples)
        reference = samples[0]
        if any(
            sample.digitization_policy != reference.digitization_policy
            for sample in samples[1:]
        ):
            raise ValueError(
                "an exposure must use one unchanged digitization policy"
            )
        ####
        sources = tuple(sample.source for sample in samples)
        for source in sources[1:]:
            if (
                source.capability_id != sources[0].capability_id
                or source.schema_version != sources[0].schema_version
                or source.provider_id != sources[0].provider_id
                or source.frame_id != sources[0].frame_id
                or source.source_fidelity != sources[0].source_fidelity
            ):
                raise ValueError(
                    "an exposure must retain one ray provider, frame, schema, and fidelity"
                )
        ####
        lineages = tuple(
            source.source_provenance.get("model_lineage_id")
            for source in sources
        )
        if any(lineage != lineages[0] for lineage in lineages[1:]):
            raise ValueError("an exposure must retain one source model lineage")
        ####
        applicability_statuses = tuple(
            str(source.source_applicability.get("status", "inside")).casefold()
            for source in sources
        )
        if any(status not in {"inside", "marginal"} for status in applicability_statuses):
            raise ValueError("every exposure sample must remain in supported applicability")
        ####
        image = integrate_fpa_exposure_samples(
            times,
            tuple(sample.image for sample in samples),
            detector=reference.detector,
        )
        source_records = tuple(
            {
                "time_s": sample.state.time_s,
                "provider_id": sample.source.provider_id,
                "session_id": sample.source.session_id,
                "snapshot_id": sample.source.snapshot_id,
                "content_sha256": sample.source.content_sha256,
                "source_reference": sample.source.model_dump(mode="json"),
                "source_provenance": dict(sample.source.source_provenance),
                "source_applicability": dict(sample.source.source_applicability),
            }
            for sample in samples
        )
        integration_record = {
            "schema": "plume.mission-fpa-exposure@1",
            "operator_id": FPA_TEMPORAL_EXPOSURE_OPERATOR_ID,
            "quadrature_rule": "composite-trapezoidal",
            "sample_times_s": list(times),
            "integrated_image": image,
            "input_sources": source_records,
        }
        digest = canonical_digest(integration_record)
        source_status_values = {source.source_status.casefold() for source in sources}
        if source_status_values <= {"inside", "marginal"}:
            source_status = (
                "marginal" if "marginal" in source_status_values else "inside"
            )
        elif source_status_values <= {"ok", "partial", "degraded"}:
            source_status = next(
                status
                for status in ("degraded", "partial", "ok")
                if status in source_status_values
            )
        else:
            raise ValueError("exposure samples mix incompatible source status domains")
        ####
        applicability_status = (
            "marginal" if "marginal" in applicability_statuses else "inside"
        )
        applicability_reasons = tuple(dict.fromkeys(
            str(reason)
            for source in sources
            for reason in source.source_applicability.get("reasons", ())
        ))
        composite_source = FpaSourceReference(
            capability_id=sources[0].capability_id,
            schema_version=sources[0].schema_version,
            provider_id=sources[0].provider_id,
            session_id=f"mission-exposure-session-{digest[:24]}",
            snapshot_id=f"mission-exposure-snapshot-{digest[24:48]}",
            content_sha256=digest,
            frame_id=sources[0].frame_id,
            source_status=source_status,
            source_fidelity=dict(sources[0].source_fidelity),
            source_applicability={
                "supported": True,
                "status": applicability_status,
                "reasons": list(applicability_reasons),
            },
            source_provenance={
                "mission_timeline_schema": MISSION_TIMELINE_SCHEMA,
                "mission_fpa_exposure_schema": "plume.mission-fpa-exposure@1",
                "mission_exposure_operator_id": FPA_TEMPORAL_EXPOSURE_OPERATOR_ID,
                "quadrature_rule": "composite-trapezoidal",
                "sample_times_s": list(times),
                "input_sources": list(source_records),
            },
            operator_chain=(
                *sources[0].operator_chain,
                FPA_TEMPORAL_EXPOSURE_OPERATOR_ID,
            ),
        )
        image = replace(
            image,
            source_binding=composite_source.ray_source_binding,
        )
        policy = reference.digitization_policy
        digitized = (
            None
            if policy is None
            else digitize_expected_electrons(image, policy=policy)
        )
        inputs = FpaVisualizationInput(
            image=image,
            source=composite_source,
            detector_response=reference.detector,
            digitized=digitized,
            digitization_policy=policy,
            camera_optics=reference.geometry.camera_optics,
            validation_status="prescribed-transient-exposure-composition",
        )
        return MissionFpaExposure(
            sample_times_s=times,
            samples=samples,
            image=image,
            source=composite_source,
            digitization_policy=policy,
            digitized=digitized,
            inputs=inputs,
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
        resolved_spec = spec or FpaVisualizationSpec.for_input(
            sample.inputs,
            view_kind="fpa.overview",
        )
        return project_fpa_view(sample.inputs, resolved_spec)
    ####
####
