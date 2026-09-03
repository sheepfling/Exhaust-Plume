from __future__ import annotations

import pytest

from exhaust_plume.api.v1 import (
    SampleStatus,
    SampleStatusCode,
    SpectralSignatureRequest,
    SpectralSignatureResult,
    TimeModel,
)
from exhaust_plume.products import (
    SignatureAngularBinning,
    SignatureTimeline,
    SignatureTimelineSample,
    SignatureTimelineSelectionError,
    build_signature_angular_heatmap,
    build_signature_direction_series,
    direction_to_azimuth_elevation,
    evaluate_signature_table_asset,
)
from exhaust_plume.providers.signature_table import (
    SignatureTableConfiguration,
    SignatureTableDefinition,
)


def _request() -> SpectralSignatureRequest:
    return SpectralSignatureRequest(
        direction_frame_id="source-local",
        operating_point_id="showcase",
        source_to_observer_directions=(
            (-1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        wavelengths_m=(1.0e-6, 2.0e-6),
    )


def _definition() -> SignatureTableDefinition:
    return SignatureTableDefinition(
        frame_id="source-local",
        wavelengths_m=(1.0e-6, 2.0e-6),
        direction_cosine_nodes=(-1.0, 0.0, 1.0),
        spectral_radiant_intensity_w_sr_m=((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)),
        spectral_radiant_intensity_w_sr_m_by_time=(
            ((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)),
            ((2.0, 4.0), (6.0, 8.0), (10.0, 12.0)),
        ),
        time_nodes_s=(0.0, 2.0),
        asset_id="signature-timeline-test",
        operating_point_id="showcase",
    )


def _timeline() -> SignatureTimeline:
    definition = _definition()
    request = _request()
    configuration = SignatureTableConfiguration(time_model=TimeModel.PRESCRIBED_TRANSIENT)
    return SignatureTimeline(
        samples=tuple(
            SignatureTimelineSample(
                request=request,
                result=evaluate_signature_table_asset(
                    definition,
                    request,
                    configuration=configuration,
                    time_s=time_s,
                ),
            )
            for time_s in (0.0, 2.0)
        )
    )


def test_direction_projection_uses_declared_azimuth_elevation_convention() -> None:
    east = direction_to_azimuth_elevation((1.0, 0.0, 0.0))
    north = direction_to_azimuth_elevation((0.0, 1.0, 0.0))
    zenith = direction_to_azimuth_elevation((0.0, 0.0, 1.0))

    assert east.azimuth_deg == pytest.approx(0.0)
    assert north.azimuth_deg == pytest.approx(90.0)
    assert zenith.azimuth_deg == pytest.approx(0.0)
    assert zenith.elevation_deg == pytest.approx(90.0)


def test_angular_heatmap_keeps_exact_time_samples_and_missing_bins() -> None:
    timeline = _timeline()
    heatmap = build_signature_angular_heatmap(
        timeline,
        time_s=2.0,
        wavelength_index=1,
        binning=SignatureAngularBinning(azimuth_bin_count=4, elevation_bin_count=2),
    )

    assert heatmap.direction_frame_id == "source-local"
    assert heatmap.wavelength_m == pytest.approx(2.0e-6)
    assert heatmap.valid_direction_count == 5
    assert heatmap.invalid_direction_count == 0
    assert heatmap.cell_at(2, 1).mean_spectral_radiant_intensity_w_sr_m == pytest.approx(10.0)
    assert heatmap.cell_at(0, 0).mean_spectral_radiant_intensity_w_sr_m is None
    with pytest.raises(SignatureTimelineSelectionError, match="exact signature timeline sample"):
        build_signature_angular_heatmap(timeline, time_s=1.0, wavelength_index=0)


def test_direction_series_and_source_trajectory_retain_source_result_lineage() -> None:
    timeline = _timeline()
    series = build_signature_direction_series(timeline, direction_index=2, wavelength_index=0)
    trajectory = timeline.source_trajectory()

    assert series.direction == (1.0, 0.0, 0.0)
    assert series.times_s == (0.0, 2.0)
    assert series.spectral_radiant_intensity_w_sr_m == pytest.approx((5.0, 10.0))
    assert series.validity_mask == (True, True)
    assert len(series.result_ids) == 2
    assert trajectory.frame_id == "world"
    assert trajectory.positions_m == ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def test_heatmap_keeps_invalid_direction_samples_out_of_display_aggregate() -> None:
    timeline = _timeline()
    payload = timeline.samples[1].result.model_dump(mode="python")
    payload["spectral_radiant_intensity"] = (
        (2.0, 4.0),
        (6.0, 8.0),
        (0.0, 0.0),
        (6.0, 8.0),
        (6.0, 8.0),
    )
    payload["validity_mask"] = (
        (True, True),
        (True, True),
        (False, False),
        (True, True),
        (True, True),
    )
    payload["direction_status"] = (
        SampleStatus(code=SampleStatusCode.OK),
        SampleStatus(code=SampleStatusCode.OK),
        SampleStatus(code=SampleStatusCode.OUTSIDE_APPLICABILITY),
        SampleStatus(code=SampleStatusCode.OK),
        SampleStatus(code=SampleStatusCode.OK),
    )
    invalid_result = SpectralSignatureResult.model_validate(payload)
    invalid_timeline = SignatureTimeline(
        (timeline.samples[0], SignatureTimelineSample(timeline.samples[1].request, invalid_result))
    )

    heatmap = build_signature_angular_heatmap(
        invalid_timeline,
        time_s=2.0,
        wavelength_index=1,
        binning=SignatureAngularBinning(azimuth_bin_count=4, elevation_bin_count=2),
    )

    selected_cell = heatmap.cell_at(2, 1)
    assert heatmap.valid_direction_count == 4
    assert heatmap.invalid_direction_count == 1
    assert selected_cell.valid_direction_indices == (4,)
    assert selected_cell.invalid_direction_indices == (2,)
    assert selected_cell.mean_spectral_radiant_intensity_w_sr_m == pytest.approx(8.0)


def test_timeline_rejects_changed_direction_or_wavelength_axes() -> None:
    timeline = _timeline()
    changed_request = _request().model_copy(update={"wavelengths_m": (1.0e-6, 3.0e-6)})
    changed_sample = SignatureTimelineSample(
        request=changed_request,
        result=timeline.samples[1].result,
    )

    with pytest.raises(ValueError, match="one wavelength axis"):
        SignatureTimeline((timeline.samples[0], changed_sample))
