from __future__ import annotations

import pytest

from exhaust_plume.models.gas import FrozenMixtureGas, SpeciesDefinition, SpeciesMassFraction
from exhaust_plume.products import (
    GrayRadiationProfile,
    LineRadiationProfile,
    LtePopulationClosure,
    LteTransition,
    ModelSignatureBlockedError,
    ModelSignatureReadiness,
    ModelSignatureSampling,
    SectionedGrayRadiationProfile,
    SectionedLineRadiationProfile,
    SpectralLine,
    ModelVisualizationLane,
    assess_model_signature_readiness,
    evaluate_model_signature,
    standardize_model_visualization,
)

from src.models.moc.test_reflected_domain import _patch
from src.products.test_model_visualization import (
    _MocResult,
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
####


def _straight_bundles():
    return tuple(
        standardize_model_visualization(result, lane=lane)
        for lane, result in (
            (ModelVisualizationLane.BASIC_SHOCK_CELL, _basic_result()),
            (ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN, _reduced_result()),
            (ModelVisualizationLane.STRAIGHT_INTEGRAL, _straight_result()),
        )
    )
####


def test_readiness_requires_an_explicit_optical_profile() -> None:
    bundle = _straight_bundles()[0]

    without_profile = assess_model_signature_readiness(bundle)
    with_profile = assess_model_signature_readiness(bundle, optical_profile=_profile())

    assert without_profile.readiness is ModelSignatureReadiness.BLOCKED_MISSING_OPTICAL_PROFILE
    assert with_profile.readiness is ModelSignatureReadiness.READY
    assert with_profile.production_claim_allowed is False
####


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
    ####
####


def test_curved_lane_reaches_gray_transport_and_planar_moc_remains_blocked() -> None:
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

    assert curved_assessment.readiness is ModelSignatureReadiness.READY
    assert moc_assessment.readiness is ModelSignatureReadiness.BLOCKED_PLANAR_TRANSPORT
    curved_signature = evaluate_model_signature(curved, _profile())
    assert curved_signature.metadata.claims.radiation.value == "gray_approximate"
    assert curved_signature.metadata.provenance.metadata["production_claim_allowed"] == "false"
    with pytest.raises(ModelSignatureBlockedError, match="planar-MOC field"):
        evaluate_model_signature(moc, _profile())
    ####
####


def test_production_fit_planar_visualization_keeps_signature_length_gate_explicit() -> None:
    class ProductionFitResult(_MocResult):
        candidate_field = _MocResult.field
        fitted_shock_points_m = _MocResult.field.shock_boundary_points_m
        status = "converged_local_production_shock_cell_fit"
        local_fit_verified = True
        chain_promotion_blocked = True
        production_claim_allowed = False
        start_x_m = 0.5
        end_x_m = 2.0
    ####

    visualization = standardize_model_visualization(
        ProductionFitResult(),
        lane=ModelVisualizationLane.PLANAR_MOC,
    )
    assessment = assess_model_signature_readiness(
        visualization,
        optical_profile=_profile(),
    )

    assert assessment.readiness is ModelSignatureReadiness.BLOCKED_PLANAR_TRANSPORT
    assert any("no accepted physical length" in reason for reason in assessment.reasons)
####


def test_profile_and_sampling_reject_invalid_optical_inputs() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        GrayRadiationProfile(
            wavelengths_m=(1.0e-6, 1.0e-6),
            source_function_w_sr_m=(1.0, 1.0),
            absorption_coefficient_per_m=(1.0, 1.0),
        )
    ####
    with pytest.raises(ValueError, match="matching lengths"):
        GrayRadiationProfile(
            wavelengths_m=(1.0e-6, 2.0e-6),
            source_function_w_sr_m=(1.0,),
            absorption_coefficient_per_m=(1.0, 1.0),
        )
    ####
    with pytest.raises(ValueError, match=r"in \[3, 128\]"):
        ModelSignatureSampling(transverse_sample_count=2)
    ####
####


def test_sectioned_gray_profile_builds_planck_sources_and_requires_matching_sections() -> None:
    profile = SectionedGrayRadiationProfile.from_blackbody(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        temperatures_K=(900.0, 1200.0),
        absorption_coefficient_per_m_by_section=(
            (0.5, 0.6, 0.7),
            (0.8, 0.9, 1.0),
        ),
    )

    assert len(profile.source_function_w_sr_m_by_section) == 2
    assert profile.source_function_w_sr_m_by_section[1][0] > profile.source_function_w_sr_m_by_section[0][0]
    with pytest.raises(ValueError, match="match absorption section count"):
        SectionedGrayRadiationProfile.from_blackbody(
            wavelengths_m=(1.0e-6, 2.0e-6),
            temperatures_K=(900.0,),
            absorption_coefficient_per_m_by_section=((0.5, 0.6), (0.8, 0.9)),
        )
    ####
####


def test_model_signature_can_use_section_varying_profile_without_promoting_claims() -> None:
    bundle = _straight_bundles()[0]
    section_count = len(bundle.sectioned_tube.sections) - 1
    profile = SectionedGrayRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        source_function_w_sr_m_by_section=tuple(
            (2.0 + index, 3.0 + index, 4.0 + index)
            for index in range(section_count)
        ),
        absorption_coefficient_per_m_by_section=tuple(
            (0.5, 1.0, 1.5)
            for _index in range(section_count)
        ),
        profile_id="test-sectioned-gray-profile",
    )

    signature = evaluate_model_signature(
        bundle,
        profile,
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
    )

    assert any(value > 0.0 for row in signature.spectral_radiant_intensity for value in row)
    assert signature.metadata.provenance.metadata["optical_profile_mode"] == "piecewise-axial-section"
    assert signature.metadata.provenance.metadata["optical_profile_section_count"] == str(section_count)
    assert signature.metadata.provenance.metadata["production_claim_allowed"] == "false"
####


def test_sectioned_gray_profile_does_not_enter_curved_transport_lane() -> None:
    curved = standardize_model_visualization(
        _curved_result(),
        lane=ModelVisualizationLane.CURVED_INTEGRAL,
    )
    section_count = len(curved.sectioned_tube.sections) - 1
    profile = SectionedGrayRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6),
        source_function_w_sr_m_by_section=tuple((1.0, 1.0) for _index in range(section_count)),
        absorption_coefficient_per_m_by_section=tuple((1.0, 1.0) for _index in range(section_count)),
    )

    assessment = assess_model_signature_readiness(curved, optical_profile=profile)
    assert assessment.readiness is ModelSignatureReadiness.BLOCKED_INVALID_SUPPORT
    assert "straight section support" in assessment.reasons[0]
####


def test_explicit_lte_line_profile_enters_signature_as_spectral_engineering() -> None:
    bundle = _straight_bundles()[0]
    profile = LineRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        lines=(
            SpectralLine(
                center_wavelength_m=2.0e-6,
                integrated_optical_depth_m=4.0e-7,
                doppler_sigma_m=5.0e-8,
                label="test-line",
            ),
        ),
        source_temperature_K=1_200.0,
        path_length_m=1.0,
        profile_id="test-lte-line-profile",
    )

    assessment = assess_model_signature_readiness(bundle, optical_profile=profile)
    signature = evaluate_model_signature(
        bundle,
        profile,
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
    )

    assert assessment.ready
    assert "LTE" in assessment.claim_ceiling
    assert signature.metadata.claims.radiation.value == "spectral_engineering"
    assert signature.metadata.provenance.metadata["optical_profile_mode"] == "lte-line-by-line-voigt"
    assert signature.metadata.provenance.metadata["signature_adapter_schema"].endswith("@1")
    assert signature.metadata.provenance.metadata["production_claim_allowed"] == "false"
    assert any(value > 0.0 for row in signature.spectral_radiant_intensity for value in row)
####


def test_source_bound_lte_population_closure_preserves_the_restricted_signature_claim() -> None:
    bundle = _straight_bundles()[0]
    mixture = FrozenMixtureGas(
        mixture_id="test-signature-lte-population",
        species=(
            SpeciesDefinition(
                species="test-gas",
                molecular_weight_kg_per_mol=0.020,
                cp_JpkgK=1_000.0,
            ),
        ),
        species_mass_fractions=(SpeciesMassFraction(species="test-gas", mass_fraction=1.0),),
        valid_temperature_range_K=(300.0, 2_000.0),
    )
    state = mixture.state_at(120_000.0, 1_200.0)
    closure = LtePopulationClosure.from_state(
        LteTransition(
            species="test-gas",
            center_wavelength_m=2.0e-6,
            lower_state_energy_J=0.0,
            upper_state_energy_J=1.0e-20,
            lower_degeneracy=1.0,
            upper_degeneracy=1.0,
            integrated_absorption_cross_section_m3=4.0e-28,
            molecular_mass_kg=3.32e-26,
        ),
        state,
        partition_function=4.0,
        path_length_m=1.0,
    )
    profile = LineRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        lines=(closure.to_spectral_line(),),
        source_temperature_K=state.temperature_K,
        path_length_m=1.0,
        source_mixture_state=state,
    )

    assessment = assess_model_signature_readiness(bundle, optical_profile=profile)
    signature = evaluate_model_signature(
        bundle,
        profile,
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
    )

    assert assessment.ready
    assert "caller-bound LTE population closure" in assessment.claim_ceiling
    assert any("no reactions" in warning for warning in signature.metadata.warnings)
    assert signature.metadata.provenance.metadata["production_claim_allowed"] == "false"
####


def test_sectioned_lte_line_profile_enters_signature_with_axial_lineage() -> None:
    bundle = _straight_bundles()[0]
    section_count = len(bundle.sectioned_tube.sections) - 1
    line = SpectralLine(
        center_wavelength_m=2.0e-6,
        integrated_optical_depth_m=4.0e-7,
        doppler_sigma_m=5.0e-8,
        label="sectioned-signature-line",
    )
    profile = SectionedLineRadiationProfile(
        wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
        profiles_by_section=tuple(
            LineRadiationProfile(
                wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
                lines=(line,),
                source_temperature_K=900.0 + 100.0 * index,
                path_length_m=1.0,
                profile_id=f"section-{index}",
            )
            for index in range(section_count)
        ),
        profile_id="test-sectioned-lte-line-profile",
    )

    assessment = assess_model_signature_readiness(bundle, optical_profile=profile)
    signature = evaluate_model_signature(
        bundle,
        profile,
        sampling=ModelSignatureSampling(
            source_to_observer_directions=((1.0, 0.0, 0.0),),
            transverse_sample_count=5,
        ),
    )

    assert assessment.ready
    assert assessment.schema == "plume.signature.model-lte-line-sectioned-bridge@1"
    assert signature.metadata.claims.radiation.value == "spectral_engineering"
    assert signature.metadata.provenance.metadata["optical_profile_mode"] == "piecewise-axial-lte-line-by-line-voigt"
    assert signature.metadata.provenance.metadata["optical_profile_section_count"] == str(section_count)
    assert signature.metadata.provenance.metadata["signature_adapter_schema"] == assessment.schema
    assert signature.metadata.provenance.metadata["production_claim_allowed"] == "false"
    assert any(value > 0.0 for row in signature.spectral_radiant_intensity for value in row)
####
