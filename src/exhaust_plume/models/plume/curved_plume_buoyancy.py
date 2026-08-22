"""Hydrostatic buoyancy source terms for the curved-plume kernel."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyVector3,
    _validateNonnegativeFinite,
)
from exhaust_plume.models.plume.curved_plume_closures import (
    CurvedPlumeSourceTermModel,
    CurvedPlumeSourceTerms,
)
from exhaust_plume.models.plume.curved_plume_state import (
    CurvedPlumeSource,
    CurvedPlumeStation,
)


@dataclass(frozen=True)
class HydrostaticBuoyancySourceTermModel:
  """Net hydrostatic pressure-gradient and gravity source term.

  The model assumes that the plume is locally pressure matched and that the
  ambient pressure gradient is hydrostatic under ``gravity_mps2``. The net
  force per unit plume-centerline length is

  ``(rho_plume - rho_ambient) * area * gravity``.

  The curved-plume conserved energy excludes gravitational potential energy,
  so the corresponding mechanical work ``force dot velocity`` is returned as
  an energy source per unit length. This keeps a non-entraining calorically
  perfect plume isothermal while buoyancy changes its kinetic energy.
  """

  gravity_mps2: FloatArray = field(
      default_factory=lambda: np.asarray((0., 0., -9.80665), dtype=float)
  )

  def __post_init__(self) -> None:
    gravity = _asReadOnlyVector3('gravity_mps2', self.gravity_mps2)
    if float(np.linalg.norm(gravity)) <= 0.:
      raise ValueError('Expected `gravity_mps2` to be non-zero.')
    ####
    object.__setattr__(self, 'gravity_mps2', gravity)
  ####

  def calculateSourceTerms(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> CurvedPlumeSourceTerms:
    _validateNonnegativeFinite('arc_length_m', arc_length_m)
    del source
    force_Npm = (
        (station.density_kgpm3 - station.ambient_density_kgpm3)
        * station.area_m2
        * self.gravity_mps2
    )
    energy_source_Wpm = float(force_Npm @ station.velocity_mps)
    return CurvedPlumeSourceTerms(
        force_Npm=force_Npm,
        energy_source_Wpm=energy_source_Wpm,
    )
  ####
####


@dataclass(frozen=True)
class CompositeCurvedPlumeSourceTermModel:
  """Add independent force and energy source-term closures."""

  models: tuple[CurvedPlumeSourceTermModel, ...]

  def __post_init__(self) -> None:
    object.__setattr__(self, 'models', tuple(self.models))
  ####

  def calculateSourceTerms(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> CurvedPlumeSourceTerms:
    _validateNonnegativeFinite('arc_length_m', arc_length_m)
    force_Npm = np.zeros(3, dtype=float)
    energy_source_Wpm = 0.
    for model in self.models:
      terms = model.calculateSourceTerms(
          arc_length_m=arc_length_m,
          station=station,
          source=source,
      )
      force_Npm += terms.force_Npm
      energy_source_Wpm += terms.energy_source_Wpm
    ####
    return CurvedPlumeSourceTerms(
        force_Npm=force_Npm,
        energy_source_Wpm=energy_source_Wpm,
    )
  ####
####


__all__ = (
    'CompositeCurvedPlumeSourceTermModel',
    'HydrostaticBuoyancySourceTermModel',
)
