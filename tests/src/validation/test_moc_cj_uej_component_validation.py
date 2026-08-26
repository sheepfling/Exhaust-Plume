from __future__ import annotations

from math import cos
from types import SimpleNamespace

from pytest import approx

from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.moc.primitives import CharacteristicState
from scripts.validate_moc_cj_uej_component import (
  MocCJRunConfiguration,
  _sample_moc_profile,
  _sample_centerline_mach,
  _score_samples,
  _typed_claim,
)


def test_moc_configuration_keeps_explicit_adapter_and_refinement_counts() -> None:
  configuration = MocCJRunConfiguration()

  assert configuration.near_sonic_exit_mach == approx(1.000001)
  assert configuration.characteristic_count == 64
  assert configuration.refinement_counts == (16, 32, 64)


def test_moc_centerline_sampling_does_not_extrapolate_open_support() -> None:
  samples, skipped = _sample_centerline_mach(
    [
      {
        'x_over_D': '0.25',
        'mach_number': '1.2',
        'mach_digitization_uncertainty_abs': '0.02',
      },
      {
        'x_over_D': '0.75',
        'mach_number': '1.4',
        'mach_digitization_uncertainty_abs': '0.02',
      },
    ],
    model_x_over_D=(0.0, 0.5),
    model_mach=(1.0, 1.3),
  )

  assert len(samples) == 1
  assert samples[0]['predicted'] == approx(1.15)
  assert skipped == {'outside_open_moc_support': 1}


def test_moc_profile_sampling_is_bounded_and_uses_declared_state_assumptions() -> None:
  state = CharacteristicState(
    x_m=0.1,
    y_m=0.02,
    theta_rad=0.1,
    mach=2.0,
    gamma=1.4,
  )
  zone = SimpleNamespace(
    state_at=lambda point: state if point[0] >= 0.0 else None,
    static_pressure_at=lambda point: 101325.0 if point[0] >= 0.0 else None,
  )
  configuration = MocCJRunConfiguration()

  samples, skipped = _sample_moc_profile(
    [
      {
        'x_over_D': '0.1',
        'radial_position_y_over_D': '0.25',
        'value': '1.0',
        'value_digitization_uncertainty': '0.02',
      },
      {
        'x_over_D': '-0.1',
        'radial_position_y_over_D': '0.25',
        'value': '1.0',
        'value_digitization_uncertainty': '0.02',
      },
    ],
    zone=zone,
    diameter_m=0.038,
    quantity='static_pressure_ratio',
    ambient_pressure_Pa=configuration.ambient_pressure_Pa,
    gas=CaloricallyPerfectGas.dry_air(),
    total_temperature_K=configuration.total_temperature_K,
  )

  assert len(samples) == 1
  assert samples[0]['predicted'] == approx(1.0)
  assert skipped == {'outside_open_moc_support': 1}

  gas = CaloricallyPerfectGas.dry_air()
  velocity_samples, velocity_skipped = _sample_moc_profile(
    [{
      'x_over_D': '0.1',
      'radial_position_y_over_D': '0.25',
      'value': '1.0',
      'value_digitization_uncertainty': '0.02',
    }],
    zone=zone,
    diameter_m=0.038,
    quantity='axial_velocity',
    ambient_pressure_Pa=configuration.ambient_pressure_Pa,
    gas=gas,
    total_temperature_K=configuration.total_temperature_K,
  )

  assert velocity_skipped == {}
  assert velocity_samples[0]['predicted'] == approx(
    gas.velocity_mps(
      state.mach,
      gas.static_temperature_from_total(state.mach, configuration.total_temperature_K),
    ) * cos(state.theta_rad)
  )


def test_moc_component_score_retains_partial_coverage_and_nonacceptance() -> None:
  result = _score_samples(
    [
      {'x_over_D': 0.1, 'observed': 1.0, 'predicted': 1.1, 'uncertainty': 0.1},
      {'x_over_D': 0.2, 'observed': 1.2, 'predicted': 1.1, 'uncertainty': 0.2},
    ],
    observed_count=4,
    skipped={'outside_open_moc_support': 2},
    metadata={'profile_id': 'centerline'},
  )

  assert result['comparison_status'] == 'quantified-diagnostic'
  assert result['coverage_fraction'] == approx(0.5)
  assert result['metrics']['rmse'] == approx(0.1)
  assert result['metrics']['digitization_uncertainty_weighted_rmse'] == approx(0.7905694150)
  assert result['claim_status'] == 'not_accepted'


def test_moc_typed_component_claim_is_proposed_not_accepted() -> None:
  claim = _typed_claim('archive-sha256', MocCJRunConfiguration())

  assert claim['claim_id'] == 'VAL-003-CJ-UEJ-MOC-CENTERLINE-MACH-DIAGNOSTIC'
  assert claim['measurement_operator_id'] == 'op.field.profile-probe'
  assert claim['evidence_level'] == 3
  assert claim['status'] == 'proposed'
