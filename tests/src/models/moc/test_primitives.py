from __future__ import annotations

from math import isclose, pi

import pytest

from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  characteristic_invariants,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
  mach_angle_rad,
  maximum_prandtl_meyer_angle_rad,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)


@pytest.mark.parametrize('gamma', (1.2, 1.4, 1.67))
@pytest.mark.parametrize('mach', (1.000001, 1.2, 2.0, 5.0, 25.0))
def test_prandtl_meyer_forward_inverse_round_trip(gamma: float, mach: float) -> None:
  angle = prandtl_meyer_angle_rad(mach, gamma)
  result = inverse_prandtl_meyer_angle_rad(angle, gamma)

  assert result.status is MocPrimitiveStatus.CONVERGED
  assert result.value is not None
  assert isclose(result.value, mach, rel_tol=2.0e-9, abs_tol=2.0e-9)
  assert result.residual is not None
  assert abs(result.residual) <= 1.0e-12 + 1.0e-10 * abs(angle)


def test_prandtl_meyer_domain_rejects_asymptotic_angle() -> None:
  maximum = maximum_prandtl_meyer_angle_rad(1.4)
  result = inverse_prandtl_meyer_angle_rad(maximum, 1.4)

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.value is None


def test_prandtl_meyer_rejects_subsonic_forward_input() -> None:
  with pytest.raises(ValueError, match='at least one'):
    prandtl_meyer_angle_rad(0.99, 1.4)


def test_supersonic_pressure_inversion_reconstructs_ratio() -> None:
  gamma = 1.4
  mach = 3.2
  ratio = (1.0 + 0.5 * (gamma - 1.0) * mach**2) ** (gamma / (gamma - 1.0))
  result = supersonic_mach_from_stagnation_pressure_ratio(ratio, gamma)

  assert result.converged
  assert result.value == pytest.approx(mach)
  assert result.residual == pytest.approx(0.0, abs=1.0e-10)


def test_characteristic_invariants_and_mach_angle_are_explicit() -> None:
  state = CharacteristicState(x_m=1.0, y_m=0.5, theta_rad=0.08, mach=2.0, gamma=1.4)
  k_plus, k_minus = characteristic_invariants(state)

  assert k_plus == pytest.approx(state.theta_rad - state.nu_rad)
  assert k_minus == pytest.approx(state.theta_rad + state.nu_rad)
  assert mach_angle_rad(state.mach) == pytest.approx(0.5235987755982988)


def test_interior_compatibility_closes_both_invariants_and_forward_geometry() -> None:
  plus_source = CharacteristicState(x_m=0.0, y_m=-0.15, theta_rad=-0.02, mach=2.0, gamma=1.4)
  minus_source = CharacteristicState(x_m=0.0, y_m=0.15, theta_rad=0.02, mach=2.0, gamma=1.4)
  result = interior_characteristic_point(plus_source, minus_source)

  assert result.converged
  assert result.state is not None
  assert result.point_m is not None
  assert result.point_m[0] > max(plus_source.x_m, minus_source.x_m)
  assert result.invariant_residual_plus == pytest.approx(0.0, abs=1.0e-12)
  assert result.invariant_residual_minus == pytest.approx(0.0, abs=1.0e-12)
  assert result.geometry_residual is not None
  assert result.geometry_residual <= 1.0e-10


def test_interior_compatibility_rejects_negative_compatible_nu() -> None:
  plus_source = CharacteristicState(x_m=0.0, y_m=-0.1, theta_rad=0.8, mach=2.0, gamma=1.4)
  minus_source = CharacteristicState(x_m=0.0, y_m=0.1, theta_rad=-0.8, mach=1.1, gamma=1.4)
  result = interior_characteristic_point(plus_source, minus_source)

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.state is None


def test_centerline_compatibility_uses_family_invariant() -> None:
  source = CharacteristicState(x_m=0.0, y_m=0.25, theta_rad=-0.15, mach=2.5, gamma=1.4)
  result = centerline_characteristic_point(source, CharacteristicFamily.MINUS)

  assert result.converged
  assert result.state is not None
  assert result.point_m is not None
  assert result.point_m[1] == 0.0
  assert result.point_m[0] > source.x_m
  assert result.state.theta_rad == 0.0
  assert result.invariant_residual_minus == pytest.approx(0.0, abs=1.0e-12)


def test_centerline_reports_nonforward_geometry() -> None:
  source = CharacteristicState(x_m=1.0, y_m=0.25, theta_rad=0.0, mach=1.1, gamma=1.4)
  result = centerline_characteristic_point(source, CharacteristicFamily.PLUS)

  assert result.status is MocPrimitiveStatus.GEOMETRY_FAILURE
  assert result.point_m is None


def test_maximum_prandtl_meyer_angle_is_bounded() -> None:
  maximum = maximum_prandtl_meyer_angle_rad(1.4)
  assert 0.0 < maximum < pi
