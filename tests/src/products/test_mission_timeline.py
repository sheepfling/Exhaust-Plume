from __future__ import annotations

from math import sqrt

import pytest

from exhaust_plume.api.v1 import Pose, TimeModel, VisualSampling, VisualSectionedTubeRequest
from exhaust_plume.products import (
    GrayRadiationProfile,
    MissionProductEvaluator,
    MissionSignatureEvaluator,
    MissionState,
    MissionTimeline,
    MissionTimelineRangeError,
    MissionVisualizationEvaluator,
    ModelSignatureSampling,
    ModelSignatureBlockedError,
    ModelSignatureReadiness,
    ModelVisualizationLane,
    evaluate_model_signature,
    standardize_model_visualization,
)

from src.models.moc.test_reflected_domain import _patch
from src.products.test_model_signature import _profile, _straight_bundles
from src.products.test_model_visualization import (
    _basic_result,
    _curved_result,
    _reduced_result,
    _straight_result,
)


def _pose(
    translation_m: tuple[float, float, float],
    rotation_xyzw: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> Pose:
    return Pose(
        frame_id="world",
        translation_m=translation_m,
        rotation_xyzw=rotation_xyzw,
    )


def _timeline() -> MissionTimeline:
    return MissionTimeline(
        (
            MissionState(
                time_s=0.0,
                source_pose=_pose((0.0, 0.0, 0.0)),
                geopotential_altitude_m=0.0,
                throttle_fraction=1.0,
                remaining_propellant_mass_kg=100.0,
                operating_point_id="liftoff",
                dynamic_state={"engine_mode": "boost"},
                ambient_state={"atmosphere_model": "standard"},
            ),
            MissionState(
                time_s=10.0,
                source_pose=_pose((100.0, 20.0, 1_000.0), (0.0, 0.0, 1.0, 0.0)),
                geopotential_altitude_m=1_000.0,
                throttle_fraction=0.5,
                remaining_propellant_mass_kg=40.0,
                operating_point_id="sustain",
                dynamic_state={"engine_mode": "sustain"},
                ambient_state={"atmosphere_model": "upper-standard"},
            ),
        )
    )


def _profile_for_state(state: MissionState) -> GrayRadiationProfile:
    throttle = state.throttle_fraction or 0.0
    return GrayRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        source_function_w_sr_m=(2.0 * throttle, 3.0 * throttle, 4.0 * throttle),
        absorption_coefficient_per_m=(0.5, 1.0, 1.5),
        profile_id=f"mission-gray-{state.time_s:g}",
    )


def _visual_evaluator(visualization) -> MissionVisualizationEvaluator:
    return MissionVisualizationEvaluator(
        timeline=_timeline(),
        visualization_at=lambda _state: visualization,
        request=VisualSectionedTubeRequest(
            output_frame_id=visualization.frame_id,
            sampling=VisualSampling(maximum_section_count=8),
        ),
    )


def test_timeline_interpolates_vehicle_state_and_cursor_is_functional() -> None:
    timeline = _timeline()

    midpoint = timeline.sample_at(5.0)
    initial = timeline.cursor_at()
    advanced = initial.advance_by(5.0)

    assert midpoint.time_s == pytest.approx(5.0)
    assert midpoint.source_pose.translation_m == pytest.approx((50.0, 10.0, 500.0))
    assert midpoint.source_pose.rotation_xyzw == pytest.approx((0.0, 0.0, sqrt(0.5), sqrt(0.5)))
    assert midpoint.geopotential_altitude_m == pytest.approx(500.0)
    assert midpoint.throttle_fraction == pytest.approx(0.75)
    assert midpoint.remaining_propellant_mass_kg == pytest.approx(70.0)
    assert midpoint.operating_point_id == "liftoff"
    assert dict(midpoint.dynamic_state) == {"engine_mode": "boost"}
    assert initial.state.time_s == pytest.approx(0.0)
    assert advanced.state == midpoint
    with pytest.raises(ValueError, match="cannot advance backward"):
        advanced.advance_to(4.0)
    with pytest.raises(MissionTimelineRangeError, match="outside"):
        timeline.sample_at(10.1)


def test_mission_evaluator_resolves_and_records_prescribed_time_state() -> None:
    timeline = _timeline()
    visualization = _straight_bundles()[0]
    evaluator = MissionSignatureEvaluator(
        timeline=timeline,
        visualization_at=lambda _state: visualization,
        optical_profile_at=_profile_for_state,
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
    )

    initial = evaluator.sample_at(0.0)
    midpoint = evaluator.evaluate_cursor(timeline.cursor_at().advance_by(5.0))
    final = evaluator.sample_at(10.0)

    assert midpoint.signature.metadata.snapshot.time_s == pytest.approx(5.0)
    assert midpoint.signature.metadata.snapshot.source_pose == midpoint.state.source_pose
    assert midpoint.signature.metadata.claims.time_model is TimeModel.PRESCRIBED_TRANSIENT
    assert midpoint.signature.metadata.provenance.metadata["signature_time_model"] == "prescribed_transient"
    assert midpoint.signature.metadata.snapshot.dynamic_state_digest_sha256 != (initial.signature.metadata.snapshot.dynamic_state_digest_sha256)
    assert final.signature.metadata.snapshot.ambient_state_digest_sha256 != (initial.signature.metadata.snapshot.ambient_state_digest_sha256)
    assert midpoint.signature.spectral_radiant_intensity != initial.signature.spectral_radiant_intensity
    assert final.signature.spectral_radiant_intensity != initial.signature.spectral_radiant_intensity


def test_all_five_lanes_emit_canonical_visual_products_at_mission_time() -> None:
    visualizations = tuple(
        standardize_model_visualization(result, lane=lane)
        for lane, result in (
            (ModelVisualizationLane.BASIC_SHOCK_CELL, _basic_result()),
            (ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN, _reduced_result()),
            (ModelVisualizationLane.STRAIGHT_INTEGRAL, _straight_result()),
            (ModelVisualizationLane.CURVED_INTEGRAL, _curved_result()),
            (ModelVisualizationLane.PLANAR_MOC, _patch()[0]),
        )
    )

    for visualization in visualizations:
        sample = _visual_evaluator(visualization).sample_at(5.0)

        assert sample.visual_product.metadata.capability.wire_id == "plume.visual.sectioned-tube@1"
        assert sample.visual_product.metadata.claims.time_model is TimeModel.PRESCRIBED_TRANSIENT
        assert sample.visual_product.metadata.snapshot.time_s == pytest.approx(5.0)
        assert sample.visual_product.metadata.snapshot.source_pose == sample.state.source_pose
        assert sample.visual_product.metadata.provenance.metadata["mission_timeline_schema"] == "plume.mission-timeline@1"
        assert sample.visual_product.metadata.provenance.metadata["model_lane"] == visualization.lane_id


def test_combined_mission_product_evaluator_preserves_visual_when_signature_is_blocked() -> None:
    straight_products = MissionProductEvaluator(
        visualization_evaluator=_visual_evaluator(_straight_bundles()[0]),
        optical_profile_at=_profile_for_state,
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
    )
    curved_products = MissionProductEvaluator(
        visualization_evaluator=_visual_evaluator(
            standardize_model_visualization(
                _curved_result(),
                lane=ModelVisualizationLane.CURVED_INTEGRAL,
            )
        ),
        optical_profile_at=_profile_for_state,
    )

    straight_sample = straight_products.sample_at(5.0)
    curved_sample = curved_products.sample_at(5.0)

    assert straight_sample.signature_available
    assert straight_sample.signature is not None
    assert straight_sample.signature.metadata.snapshot.time_s == pytest.approx(5.0)
    assert straight_sample.signature.metadata.claims.time_model is TimeModel.PRESCRIBED_TRANSIENT
    assert curved_sample.visual_product.metadata.claims.time_model is TimeModel.PRESCRIBED_TRANSIENT
    assert curved_sample.signature is None
    assert curved_sample.signature_assessment.readiness is ModelSignatureReadiness.BLOCKED_CURVED_TRANSPORT
    with pytest.raises(ModelSignatureBlockedError, match="blocked-curved-transport"):
        curved_products.signature_at(5.0)


def test_direct_bridge_accepts_explicit_snapshot_state() -> None:
    source_pose = _pose((4.0, 5.0, 6.0))
    signature = evaluate_model_signature(
        _straight_bundles()[0],
        _profile(),
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
        time_s=12.5,
        source_pose=source_pose,
        dynamic_state={"throttle_fraction": 0.8},
        ambient_state={"geopotential_altitude_m": 1_200.0},
        time_model=TimeModel.PRESCRIBED_TRANSIENT,
    )

    assert signature.metadata.snapshot.time_s == pytest.approx(12.5)
    assert signature.metadata.snapshot.source_pose == source_pose
    assert signature.metadata.claims.time_model is TimeModel.PRESCRIBED_TRANSIENT
    assert signature.metadata.provenance.metadata["signature_time_model"] == "prescribed_transient"


def test_timeline_rejects_partial_scalar_schedule() -> None:
    with pytest.raises(ValueError, match="throttle_fraction must be supplied"):
        MissionTimeline(
            (
                MissionState(time_s=0.0, source_pose=_pose((0.0, 0.0, 0.0)), throttle_fraction=1.0),
                MissionState(time_s=1.0, source_pose=_pose((0.0, 0.0, 1.0))),
            )
        )
