from __future__ import annotations

import pytest

from exhaust_plume.products import (
    GrayRadiationProfile,
    ModelSignatureBlockedError,
    ModelSignatureReadiness,
    ModelSignatureSampling,
    ModelVisualizationLane,
    assess_model_signature_readiness,
    evaluate_model_signature,
    standardize_model_visualization,
)

from src.models.moc.test_reflected_domain import _patch
from src.products.test_model_visualization import (
    _basic_result,
    _curved_result,
    _reduced_result,
    _straight_result,
)


def _profile() -> GrayRadiationProfile:
    return GrayRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        source_function_w_sr_m=(2.0, 3.0, 4.0),
        absorption_coefficient_per_m=(0.5, 1.0, 1.5),
        profile_id="test-gray-profile",
    )


def _straight_bundles():
    return tuple(
        standardize_model_visualization(result, lane=lane)
        for lane, result in (
            (ModelVisualizationLane.BASIC_SHOCK_CELL, _basic_result()),
            (ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN, _reduced_result()),
            (ModelVisualizationLane.STRAIGHT_INTEGRAL, _straight_result()),
        )
    )


def test_readiness_requires_an_explicit_optical_profile() -> None:
    bundle = _straight_bundles()[0]

    without_profile = assess_model_signature_readiness(bundle)
    with_profile = assess_model_signature_readiness(bundle, optical_profile=_profile())

    assert without_profile.readiness is ModelSignatureReadiness.BLOCKED_MISSING_OPTICAL_PROFILE
    assert with_profile.readiness is ModelSignatureReadiness.READY
    assert with_profile.production_claim_allowed is False


def test_all_three_straight_lanes_reach_gray_signature() -> None:
    sampling = ModelSignatureSampling(
        source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        transverse_sample_count=7,
    )

    for bundle in _straight_bundles():
        signature = evaluate_model_signature(bundle, _profile(), sampling=sampling)

        assert len(signature.spectral_radiant_intensity) == 2
        assert all(len(row) == 3 for row in signature.spectral_radiant_intensity)
        assert all(all(row) for row in signature.validity_mask)
        assert signature.metadata.claims.radiation.value == "gray_approximate"
        assert signature.metadata.claims.derivation.value == "adapted"
        assert signature.metadata.provenance.metadata["flow_model_lane"] == bundle.lane_id
        assert signature.metadata.provenance.metadata["production_claim_allowed"] == "false"
        assert any(value > 0.0 for row in signature.spectral_radiant_intensity for value in row)


def test_curved_and_planar_moc_lanes_report_transport_blocks() -> None:
    curved = standardize_model_visualization(
        _curved_result(),
        lane=ModelVisualizationLane.CURVED_INTEGRAL,
    )
    moc = standardize_model_visualization(
        _patch()[0],
        lane=ModelVisualizationLane.PLANAR_MOC,
    )

    curved_assessment = assess_model_signature_readiness(curved, optical_profile=_profile())
    moc_assessment = assess_model_signature_readiness(moc, optical_profile=_profile())

    assert curved_assessment.readiness is ModelSignatureReadiness.BLOCKED_CURVED_TRANSPORT
    assert moc_assessment.readiness is ModelSignatureReadiness.BLOCKED_PLANAR_TRANSPORT
    with pytest.raises(ModelSignatureBlockedError, match="curved/washed geometry"):
        evaluate_model_signature(curved, _profile())
    with pytest.raises(ModelSignatureBlockedError, match="planar-MOC field"):
        evaluate_model_signature(moc, _profile())


def test_profile_and_sampling_reject_invalid_optical_inputs() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        GrayRadiationProfile(
            wavelengths_m=(1.0e-6, 1.0e-6),
            source_function_w_sr_m=(1.0, 1.0),
            absorption_coefficient_per_m=(1.0, 1.0),
        )
    with pytest.raises(ValueError, match="matching lengths"):
        GrayRadiationProfile(
            wavelengths_m=(1.0e-6, 2.0e-6),
            source_function_w_sr_m=(1.0,),
            absorption_coefficient_per_m=(1.0, 1.0),
        )
    with pytest.raises(ValueError, match=r"in \[3, 128\]"):
        ModelSignatureSampling(transverse_sample_count=2)
