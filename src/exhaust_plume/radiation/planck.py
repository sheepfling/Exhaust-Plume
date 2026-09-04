"""Thermal continuum radiation primitives.

These functions provide the explicit blackbody/gray source term needed by a
bounded thermal Signature input. They do not model molecular bands, chemical
populations, non-LTE effects, atmospheric transfer, or detector response.
"""

from __future__ import annotations

from math import expm1, isfinite
from typing import Sequence

__all__ = (
  'PLANCK_C1_W_M2',
  'PLANCK_C2_M_K',
  'planck_spectral_radiance_W_m2_sr_m',
)

# Exact SI constants used by the Planck law.
PLANCK_C1_W_M2 = 2.0 * 6.62607015e-34 * 299792458.0**2
PLANCK_C2_M_K = 6.62607015e-34 * 299792458.0 / 1.380649e-23


def _axis(wavelengths_m: Sequence[float]) -> tuple[float, ...]:
  values = tuple(float(value) for value in wavelengths_m)
  if not values:
    raise ValueError('wavelengths_m must not be empty')
  ####
  if any(not isfinite(value) or value <= 0.0 for value in values):
    raise ValueError('wavelengths_m must be finite and positive')
  ####
  return values
####


def planck_spectral_radiance_W_m2_sr_m(
  wavelengths_m: Sequence[float],
  temperature_K: float,
  *,
  emissivity: float = 1.0,
) -> tuple[float, ...]:
  """Return blackbody/gray spectral radiance in ``W m^-2 sr^-1 m^-1``.

  ``emissivity`` is a wavelength-independent gray multiplier in ``[0, 1]``.
  Very large Planck exponents are treated as a finite underflow-to-zero
  radiance. The wavelength sequence is not reordered.
  """

  wavelengths = _axis(wavelengths_m)
  temperature = float(temperature_K)
  if not isfinite(temperature) or temperature <= 0.0:
    raise ValueError('temperature_K must be finite and positive')
  ####
  gray_emissivity = float(emissivity)
  if not isfinite(gray_emissivity) or not 0.0 <= gray_emissivity <= 1.0:
    raise ValueError('emissivity must be finite and in [0, 1]')
  ####
  radiance: list[float] = []
  for wavelength in wavelengths:
    exponent = PLANCK_C2_M_K / (wavelength * temperature)
    if exponent >= 709.0:
      value = 0.0
    else:
      value = PLANCK_C1_W_M2 / (wavelength**5 * expm1(exponent))
    ####
    radiance.append(gray_emissivity * value)
  ####
  return tuple(radiance)
####
