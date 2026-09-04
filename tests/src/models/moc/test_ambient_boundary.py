from __future__ import annotations

from math import pi

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientBoundarySample,
  MocAmbientBoundaryStatus,
  validate_ambient_pressure_boundary,
)


def _matched_samples() -> tuple[MocAmbientBoundarySample, ...]:
  ambient_pressure = 100000.0
  mach = 2.0
  gamma = 1.4
  pressure_ratio = (1.0 + 0.5 * (gamma - 1.0) * mach * mach) ** (
    gamma / (gamma - 1.0)
  )
  total_pressure = ambient_pressure * pressure_ratio
  return tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=0.0,
        mach=mach,
        gamma=gamma,
      ),
      total_pressure_Pa=total_pressure,
    )
    for index in range(3)
  )
####


def test_ambient_pressure_boundary_requires_pressure_and_tangency() -> None:
  result = validate_ambient_pressure_boundary(_matched_samples(), 100000.0)

  assert result.status is MocAmbientBoundaryStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert result.maximum_absolute_pressure_residual is not None
  assert result.maximum_absolute_pressure_residual < 1.0e-12
  assert result.maximum_absolute_tangent_residual == 0.0
####


def test_ambient_pressure_boundary_rejects_pressure_mismatch() -> None:
  samples = tuple(
    MocAmbientBoundarySample(
      point_m=sample.point_m,
      state=sample.state,
      total_pressure_Pa=1.1 * sample.total_pressure_Pa,
    )
    for sample in _matched_samples()
  )

  result = validate_ambient_pressure_boundary(samples, 100000.0)

  assert result.status is MocAmbientBoundaryStatus.PRESSURE_FAILURE
  assert not result.converged
  assert result.maximum_absolute_pressure_residual is not None
  assert result.maximum_absolute_pressure_residual > 0.0
####


def test_ambient_pressure_boundary_rejects_non_tangent_perimeter() -> None:
  samples = tuple(
    MocAmbientBoundarySample(
      point_m=(sample.point_m[0], sample.point_m[1] - 0.1 * index),
      state=CharacteristicState(
        x_m=sample.point_m[0],
        y_m=sample.point_m[1] - 0.1 * index,
        theta_rad=sample.state.theta_rad,
        mach=sample.state.mach,
        gamma=sample.state.gamma,
      ),
      total_pressure_Pa=sample.total_pressure_Pa,
    )
    for index, sample in enumerate(_matched_samples())
  )

  result = validate_ambient_pressure_boundary(
    samples,
    100000.0,
    tangent_tolerance=1.0e-10,
  )

  assert result.status is MocAmbientBoundaryStatus.TANGENT_FAILURE
  assert not result.converged
  assert result.maximum_absolute_tangent_residual is not None
  assert result.maximum_absolute_tangent_residual > 0.0
####


def test_ambient_pressure_boundary_rejects_a_reversed_flow_tangent() -> None:
  samples = tuple(
    MocAmbientBoundarySample(
      point_m=sample.point_m,
      state=CharacteristicState(
        x_m=sample.point_m[0],
        y_m=sample.point_m[1],
        theta_rad=pi,
        mach=sample.state.mach,
        gamma=sample.state.gamma,
      ),
      total_pressure_Pa=sample.total_pressure_Pa,
    )
    for sample in _matched_samples()
  )

  result = validate_ambient_pressure_boundary(samples, 100000.0)

  assert result.status is MocAmbientBoundaryStatus.TANGENT_FAILURE
  assert not result.converged
  assert result.maximum_absolute_tangent_residual is not None
  assert result.maximum_absolute_tangent_residual < 1.0e-12
####


def test_ambient_pressure_boundary_rejects_a_first_sample_below_axis() -> None:
  matched = _matched_samples()
  first = matched[0]
  samples = (
    MocAmbientBoundarySample(
      point_m=(first.point_m[0], -0.1),
      state=CharacteristicState(
        x_m=first.point_m[0],
        y_m=-0.1,
        theta_rad=first.state.theta_rad,
        mach=first.state.mach,
        gamma=first.state.gamma,
      ),
      total_pressure_Pa=first.total_pressure_Pa,
    ),
    *matched[1:],
  )

  result = validate_ambient_pressure_boundary(samples, 100000.0)

  assert result.status is MocAmbientBoundaryStatus.GEOMETRY_FAILURE
  assert not result.converged
  assert 'below the symmetry line' in result.message
####
