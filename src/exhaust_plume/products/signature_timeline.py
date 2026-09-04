"""Renderer-neutral angular and time views for spectral-signature samples.

``SpectralSignatureResult`` intentionally carries values and result metadata,
while the direction and wavelength axes remain on the request that produced
it.  This module keeps that pair intact when a caller collects a compatible
time series.  It then exposes sampled angular bins and exact direction traces
without inventing a physical angular coordinate, interpolating directions, or
turning missing values into zero.

The azimuth/elevation projection is a display convention only: azimuth is
measured about +z from +x toward +y and elevation is measured from the xy
plane.  Both are expressed in the request's declared direction frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite
from typing import Any, cast

from exhaust_plume.api.v1 import (
    Pose,
    SampleStatus,
    SpectralSignatureRequest,
    SpectralSignatureResult,
)

__all__ = (
    "SIGNATURE_ANGULAR_TIMELINE_SCHEMA",
    "AngularCoordinates",
    "SignatureAngularBinning",
    "SignatureAngularHeatmap",
    "SignatureAngularHeatmapCell",
    "SignatureDirectionSeries",
    "SignatureSourceTrajectory",
    "SignatureTimeline",
    "SignatureTimelineQuery",
    "SignatureTimelineSample",
    "SignatureTimelineSelectionError",
    "build_signature_angular_heatmap",
    "build_signature_direction_series",
    "direction_to_azimuth_elevation",
)


SIGNATURE_ANGULAR_TIMELINE_SCHEMA = "plume.signature.angular-timeline@1"


def _integer_in_range(name: str, value: object, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    ####
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must lie in [{minimum}, {maximum}]")
    ####
    return value
####


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


@dataclass(frozen=True, slots=True)
class AngularCoordinates:
    """One exact source-to-observer direction in the display convention."""

    direction: tuple[float, float, float]
    azimuth_deg: float
    elevation_deg: float
####


def direction_to_azimuth_elevation(direction: tuple[float, float, float]) -> AngularCoordinates:
    """Project one declared unit direction to a non-physical display plane.

    The returned azimuth belongs to ``[-180, 180)`` degrees.  The +z and -z
    poles use an azimuth of zero because azimuth is undefined there; callers
    must retain the original unit vector for any physical interpretation.
    """

    if not isinstance(direction, tuple) or len(direction) != 3:
        raise TypeError("direction must be a three-coordinate tuple")
    ####
    x, y, z = tuple(_finite(f"direction[{index}]", value) for index, value in enumerate(direction))
    azimuth_deg = degrees(atan2(y, x))
    if azimuth_deg >= 180.0:
        azimuth_deg = -180.0
    ####
    horizontal_norm = hypot(x, y)
    elevation_deg = degrees(atan2(z, horizontal_norm))
    if horizontal_norm == 0.0:
        azimuth_deg = 0.0
    ####
    return AngularCoordinates(
        direction=(x, y, z),
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
    )
####


@dataclass(frozen=True, slots=True)
class SignatureTimelineSample:
    """The exact request/result pair for one signature snapshot."""

    request: SpectralSignatureRequest
    result: SpectralSignatureResult

    def __post_init__(self) -> None:
        if not isinstance(self.request, SpectralSignatureRequest):
            raise TypeError("request must be SpectralSignatureRequest")
        ####
        if not isinstance(self.result, SpectralSignatureResult):
            raise TypeError("result must be SpectralSignatureResult")
        ####
        if self.request.direction_frame_id != self.result.metadata.output_frame_id:
            raise ValueError("request direction_frame_id must equal the signature result output frame")
        ####
        direction_count = len(self.request.source_to_observer_directions)
        wavelength_count = len(self.request.wavelengths_m)
        if len(self.result.spectral_radiant_intensity) != direction_count:
            raise ValueError("signature result direction count must match the request")
        ####
        if any(len(row) != wavelength_count for row in self.result.spectral_radiant_intensity):
            raise ValueError("signature result wavelength count must match the request")
        ####
    ####

    @property
    def time_s(self) -> float:
        """Return the immutable snapshot time carried by the source result."""

        return self.result.metadata.snapshot.time_s
    ####
####


class SignatureTimelineSelectionError(ValueError):
    """Raised when a display requests an unavailable exact sample or axis."""
####


@dataclass(frozen=True, slots=True)
class SignatureTimelineQuery:
    """One exact, source-bound spectral radiant-intensity point query.

    The query preserves the product's declared intensity units and lineage.
    An invalid point has ``spectral_radiant_intensity_w_sr_m=None`` even when
    the wire result carries its required zero placeholder.  This prevents a
    consumer from treating a failed sample as a physical zero.
    """

    source_result_id: str
    time_s: float
    direction_frame_id: str
    direction_index: int
    direction: tuple[float, float, float]
    angular_coordinates: AngularCoordinates
    wavelength_index: int
    wavelength_m: float
    spectral_radiant_intensity_w_sr_m: float | None
    absolute_standard_uncertainty_w_sr_m: float | None
    valid: bool
    status: SampleStatus
####


@dataclass(frozen=True, slots=True)
class SignatureTimeline:
    """Time-ordered compatible signature samples with no temporal interpolation.

    All samples retain the same exact direction frame, direction vectors, and
    wavelength axis.  This is deliberately stricter than a plotting helper:
    visual comparisons across changed angular or spectral grids must first be
    reconciled by an explicit product-level resampling process.
    """

    samples: tuple[SignatureTimelineSample, ...]

    def __post_init__(self) -> None:
        samples = tuple(self.samples)
        if not samples:
            raise ValueError("signature timeline requires at least one sample")
        ####
        if any(not isinstance(sample, SignatureTimelineSample) for sample in samples):
            raise TypeError("signature timeline samples must be SignatureTimelineSample")
        ####
        if any(second.time_s <= first.time_s for first, second in zip(samples, samples[1:])):
            raise ValueError("signature timeline sample times must be strictly increasing")
        ####
        reference = samples[0].request
        for sample in samples[1:]:
            request = sample.request
            if request.direction_frame_id != reference.direction_frame_id:
                raise ValueError("signature timeline samples must use one direction_frame_id")
            ####
            if request.source_to_observer_directions != reference.source_to_observer_directions:
                raise ValueError("signature timeline samples must use identical direction vectors")
            ####
            if request.wavelengths_m != reference.wavelengths_m:
                raise ValueError("signature timeline samples must use one wavelength axis")
            ####
        ####
        object.__setattr__(self, "samples", samples)
    ####

    @property
    def direction_frame_id(self) -> str:
        return self.samples[0].request.direction_frame_id
    ####

    @property
    def directions(self) -> tuple[tuple[float, float, float], ...]:
        return self.samples[0].request.source_to_observer_directions
    ####

    @property
    def wavelengths_m(self) -> tuple[float, ...]:
        return self.samples[0].request.wavelengths_m
    ####

    @property
    def times_s(self) -> tuple[float, ...]:
        return tuple(sample.time_s for sample in self.samples)
    ####

    def sample_at(self, time_s: float) -> SignatureTimelineSample:
        """Return one exact sampled time; no temporal interpolation is implied."""

        selected_time_s = _finite("time_s", time_s)
        for sample in self.samples:
            if sample.time_s == selected_time_s:
                return sample
            ####
        ####
        raise SignatureTimelineSelectionError(
            f"time_s={selected_time_s} is not an exact signature timeline sample"
        )
    ####

    def query_at(
        self,
        *,
        time_s: float,
        direction_index: int,
        wavelength_index: int,
    ) -> SignatureTimelineQuery:
        """Return one exact time/direction/wavelength point without interpolation.

        The returned value is ``None`` when the selected point is invalid.  A
        caller that needs a continuously varying time must explicitly resolve
        a new provider snapshot or apply a separately documented interpolation
        operator before constructing a timeline.
        """

        selected_direction_index = _direction_index(self, direction_index)
        selected_wavelength_index = _wavelength_index(self, wavelength_index)
        sample = self.sample_at(time_s)
        valid = sample.result.validity_mask[selected_direction_index][selected_wavelength_index]
        value = (
            sample.result.spectral_radiant_intensity[selected_direction_index][selected_wavelength_index]
            if valid
            else None
        )
        uncertainty = (
            sample.result.absolute_standard_uncertainty[selected_direction_index][selected_wavelength_index]
            if valid and sample.result.absolute_standard_uncertainty is not None
            else None
        )
        direction = self.directions[selected_direction_index]
        return SignatureTimelineQuery(
            source_result_id=sample.result.metadata.result_id,
            time_s=sample.time_s,
            direction_frame_id=self.direction_frame_id,
            direction_index=selected_direction_index,
            direction=direction,
            angular_coordinates=direction_to_azimuth_elevation(direction),
            wavelength_index=selected_wavelength_index,
            wavelength_m=self.wavelengths_m[selected_wavelength_index],
            spectral_radiant_intensity_w_sr_m=value,
            absolute_standard_uncertainty_w_sr_m=uncertainty,
            valid=valid,
            status=sample.result.direction_status[selected_direction_index],
        )
    ####

    def source_trajectory(self) -> "SignatureSourceTrajectory":
        """Return the declared source-pose samples when they share one frame."""

        poses = tuple(sample.result.metadata.snapshot.source_pose for sample in self.samples)
        frame_id = poses[0].frame_id
        if any(pose.frame_id != frame_id for pose in poses[1:]):
            raise SignatureTimelineSelectionError(
                "source trajectory requires one source-pose frame_id; no transform is available"
            )
        ####
        return SignatureSourceTrajectory(
            frame_id=frame_id,
            times_s=self.times_s,
            source_poses=poses,
        )
    ####
####


@dataclass(frozen=True, slots=True)
class SignatureAngularBinning:
    """Explicit display aggregation policy for sampled direction vectors."""

    azimuth_bin_count: int = 24
    elevation_bin_count: int = 12

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "azimuth_bin_count",
            _integer_in_range("azimuth_bin_count", self.azimuth_bin_count, minimum=1, maximum=720),
        )
        object.__setattr__(
            self,
            "elevation_bin_count",
            _integer_in_range("elevation_bin_count", self.elevation_bin_count, minimum=1, maximum=360),
        )
    ####

    def indices_for(self, coordinates: AngularCoordinates) -> tuple[int, int]:
        """Return the equirectangular display bin for exact coordinates."""

        azimuth_fraction = (coordinates.azimuth_deg + 180.0) / 360.0
        elevation_fraction = (coordinates.elevation_deg + 90.0) / 180.0
        azimuth_index = min(self.azimuth_bin_count - 1, int(azimuth_fraction * self.azimuth_bin_count))
        elevation_index = min(self.elevation_bin_count - 1, int(elevation_fraction * self.elevation_bin_count))
        return azimuth_index, elevation_index
    ####

    def azimuth_bounds_deg(self, index: int) -> tuple[float, float]:
        resolved_index = _integer_in_range(
            "azimuth index",
            index,
            minimum=0,
            maximum=self.azimuth_bin_count - 1,
        )
        width = 360.0 / self.azimuth_bin_count
        lower = -180.0 + resolved_index * width
        return lower, lower + width
    ####

    def elevation_bounds_deg(self, index: int) -> tuple[float, float]:
        resolved_index = _integer_in_range(
            "elevation index",
            index,
            minimum=0,
            maximum=self.elevation_bin_count - 1,
        )
        height = 180.0 / self.elevation_bin_count
        lower = -90.0 + resolved_index * height
        return lower, lower + height
    ####
####


@dataclass(frozen=True, slots=True)
class SignatureAngularHeatmapCell:
    """One display bin, retaining missing/invalid samples independently."""

    azimuth_index: int
    elevation_index: int
    azimuth_bounds_deg: tuple[float, float]
    elevation_bounds_deg: tuple[float, float]
    sampled_direction_indices: tuple[int, ...]
    valid_direction_indices: tuple[int, ...]
    invalid_direction_indices: tuple[int, ...]
    mean_spectral_radiant_intensity_w_sr_m: float | None
    mean_absolute_standard_uncertainty_w_sr_m: float | None

    @property
    def has_sample(self) -> bool:
        return bool(self.sampled_direction_indices)
    ####
####


@dataclass(frozen=True, slots=True)
class SignatureAngularHeatmap:
    """A sampled, binned angular slice at one exact time and wavelength."""

    schema: str
    source_result_id: str
    time_s: float
    direction_frame_id: str
    wavelength_index: int
    wavelength_m: float
    binning: SignatureAngularBinning
    cells: tuple[SignatureAngularHeatmapCell, ...]
    valid_direction_count: int
    invalid_direction_count: int

    def cell_at(self, azimuth_index: int, elevation_index: int) -> SignatureAngularHeatmapCell:
        """Return one cell using display-bin indices, not physical coordinates."""

        resolved_azimuth_index = _integer_in_range(
            "azimuth index",
            azimuth_index,
            minimum=0,
            maximum=self.binning.azimuth_bin_count - 1,
        )
        resolved_elevation_index = _integer_in_range(
            "elevation index",
            elevation_index,
            minimum=0,
            maximum=self.binning.elevation_bin_count - 1,
        )
        return self.cells[
            resolved_elevation_index * self.binning.azimuth_bin_count + resolved_azimuth_index
        ]
    ####
####


@dataclass(frozen=True, slots=True)
class SignatureDirectionSeries:
    """One exact direction/wavelength trace across signature sample times."""

    direction_frame_id: str
    direction_index: int
    direction: tuple[float, float, float]
    angular_coordinates: AngularCoordinates
    wavelength_index: int
    wavelength_m: float
    times_s: tuple[float, ...]
    spectral_radiant_intensity_w_sr_m: tuple[float | None, ...]
    absolute_standard_uncertainty_w_sr_m: tuple[float | None, ...]
    validity_mask: tuple[bool, ...]
    result_ids: tuple[str, ...]
####


@dataclass(frozen=True, slots=True)
class SignatureSourceTrajectory:
    """Exact source-pose samples associated with a signature timeline."""

    frame_id: str
    times_s: tuple[float, ...]
    source_poses: tuple[Pose, ...]

    @property
    def positions_m(self) -> tuple[tuple[float, float, float], ...]:
        return tuple(pose.translation_m for pose in self.source_poses)
    ####
####


def _wavelength_index(timeline: SignatureTimeline, index: object) -> int:
    return _integer_in_range(
        "wavelength_index",
        index,
        minimum=0,
        maximum=len(timeline.wavelengths_m) - 1,
    )
####


def _direction_index(timeline: SignatureTimeline, index: object) -> int:
    return _integer_in_range(
        "direction_index",
        index,
        minimum=0,
        maximum=len(timeline.directions) - 1,
    )
####


def build_signature_angular_heatmap(
    timeline: SignatureTimeline,
    *,
    time_s: float,
    wavelength_index: int,
    binning: SignatureAngularBinning | None = None,
) -> SignatureAngularHeatmap:
    """Build one angular heatmap from exact samples in a selected time slice.

    A cell's intensity is the arithmetic display aggregate of valid directions
    that fall into that cell.  Empty cells and cells with only invalid
    directions have ``None`` intensity; neither represents a physical zero.
    """

    if not isinstance(timeline, SignatureTimeline):
        raise TypeError("timeline must be SignatureTimeline")
    ####
    selected_binning = binning or SignatureAngularBinning()
    if not isinstance(selected_binning, SignatureAngularBinning):
        raise TypeError("binning must be SignatureAngularBinning or None")
    ####
    selected_wavelength_index = _wavelength_index(timeline, wavelength_index)
    sample = timeline.sample_at(time_s)
    buckets: dict[tuple[int, int], list[int]] = {}
    for direction_index, direction in enumerate(timeline.directions):
        coordinates = direction_to_azimuth_elevation(direction)
        buckets.setdefault(selected_binning.indices_for(coordinates), []).append(direction_index)
    ####

    cells: list[SignatureAngularHeatmapCell] = []
    valid_direction_count = 0
    invalid_direction_count = 0
    for elevation_index in range(selected_binning.elevation_bin_count):
        for azimuth_index in range(selected_binning.azimuth_bin_count):
            sampled_indices = tuple(buckets.get((azimuth_index, elevation_index), ()))
            valid_indices = tuple(
                direction_index
                for direction_index in sampled_indices
                if sample.result.validity_mask[direction_index][selected_wavelength_index]
            )
            invalid_indices = tuple(
                direction_index
                for direction_index in sampled_indices
                if direction_index not in valid_indices
            )
            valid_direction_count += len(valid_indices)
            invalid_direction_count += len(invalid_indices)
            if valid_indices:
                values = tuple(
                    sample.result.spectral_radiant_intensity[direction_index][selected_wavelength_index]
                    for direction_index in valid_indices
                )
                mean_intensity = sum(values) / len(values)
                if sample.result.absolute_standard_uncertainty is None:
                    mean_uncertainty = None
                else:
                    uncertainties = tuple(
                        sample.result.absolute_standard_uncertainty[direction_index][selected_wavelength_index]
                        for direction_index in valid_indices
                    )
                    mean_uncertainty = sum(uncertainties) / len(uncertainties)
                ####
            else:
                mean_intensity = None
                mean_uncertainty = None
            ####
            cells.append(
                SignatureAngularHeatmapCell(
                    azimuth_index=azimuth_index,
                    elevation_index=elevation_index,
                    azimuth_bounds_deg=selected_binning.azimuth_bounds_deg(azimuth_index),
                    elevation_bounds_deg=selected_binning.elevation_bounds_deg(elevation_index),
                    sampled_direction_indices=sampled_indices,
                    valid_direction_indices=valid_indices,
                    invalid_direction_indices=invalid_indices,
                    mean_spectral_radiant_intensity_w_sr_m=mean_intensity,
                    mean_absolute_standard_uncertainty_w_sr_m=mean_uncertainty,
                )
            )
        ####
    ####
    return SignatureAngularHeatmap(
        schema=SIGNATURE_ANGULAR_TIMELINE_SCHEMA,
        source_result_id=sample.result.metadata.result_id,
        time_s=sample.time_s,
        direction_frame_id=timeline.direction_frame_id,
        wavelength_index=selected_wavelength_index,
        wavelength_m=timeline.wavelengths_m[selected_wavelength_index],
        binning=selected_binning,
        cells=tuple(cells),
        valid_direction_count=valid_direction_count,
        invalid_direction_count=invalid_direction_count,
    )
####


def build_signature_direction_series(
    timeline: SignatureTimeline,
    *,
    direction_index: int,
    wavelength_index: int,
) -> SignatureDirectionSeries:
    """Build a masked time trace for one exact direction and wavelength."""

    if not isinstance(timeline, SignatureTimeline):
        raise TypeError("timeline must be SignatureTimeline")
    ####
    selected_direction_index = _direction_index(timeline, direction_index)
    selected_wavelength_index = _wavelength_index(timeline, wavelength_index)
    values: list[float | None] = []
    uncertainties: list[float | None] = []
    validity: list[bool] = []
    for sample in timeline.samples:
        valid = sample.result.validity_mask[selected_direction_index][selected_wavelength_index]
        validity.append(valid)
        values.append(
            sample.result.spectral_radiant_intensity[selected_direction_index][selected_wavelength_index]
            if valid
            else None
        )
        if valid and sample.result.absolute_standard_uncertainty is not None:
            uncertainties.append(
                sample.result.absolute_standard_uncertainty[selected_direction_index][selected_wavelength_index]
            )
        else:
            uncertainties.append(None)
        ####
    ####
    direction = timeline.directions[selected_direction_index]
    return SignatureDirectionSeries(
        direction_frame_id=timeline.direction_frame_id,
        direction_index=selected_direction_index,
        direction=direction,
        angular_coordinates=direction_to_azimuth_elevation(direction),
        wavelength_index=selected_wavelength_index,
        wavelength_m=timeline.wavelengths_m[selected_wavelength_index],
        times_s=timeline.times_s,
        spectral_radiant_intensity_w_sr_m=tuple(values),
        absolute_standard_uncertainty_w_sr_m=tuple(uncertainties),
        validity_mask=tuple(validity),
        result_ids=tuple(sample.result.metadata.result_id for sample in timeline.samples),
    )
####
