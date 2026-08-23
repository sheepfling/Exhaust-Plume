"""Neutral supporting products for provider composition."""

from __future__ import annotations

from math import isfinite

from pydantic import Field, field_validator, model_validator

from exhaust_plume.products._base import (
    ContractModel,
    ENGINEERING_FLUX_SECTION_V1,
    ProductMetadata,
    Vector3,
    normalizeVector3,
)


class EngineeringFluxSectionProduct(ContractModel):
  """Conservative centerline sections for provider-to-provider handoff."""

  metadata: ProductMetadata
  position_m: tuple[Vector3, ...] = Field(min_length=1)
  area_m2: tuple[float, ...] = Field(min_length=1)
  mass_flow_kgps: tuple[float, ...] = Field(min_length=1)
  momentum_flux_N: tuple[Vector3, ...] = Field(min_length=1)
  total_energy_flow_W: tuple[float, ...] = Field(min_length=1)
  exhaust_mass_flow_kgps: tuple[float, ...] = Field(min_length=1)

  @property
  def stagnation_enthalpy_flow_W(self) -> tuple[float, ...]:
    """Compatibility name for the neutral total-energy-flow field."""

    return self.total_energy_flow_W
  ####

  @field_validator('position_m', 'momentum_flux_N', mode='before')
  @classmethod
  def normalizeVectors(cls, value: object) -> tuple[Vector3, ...]:
    try:
      return tuple(normalizeVector3(item, name='flux-section vector') for item in value)  # type: ignore[arg-type]
    except TypeError as exc:
      raise ValueError('Expected a sequence of finite three-vectors.') from exc
    ####
  ####

  @field_validator(
      'area_m2', 'mass_flow_kgps', 'total_energy_flow_W', 'exhaust_mass_flow_kgps',
      mode='before',
  )
  @classmethod
  def normalizeScalars(cls, value: object) -> tuple[float, ...]:
    try:
      values = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
      raise ValueError('Expected finite flux-section scalar values.') from exc
    ####
    if any(not isfinite(item) or item < 0. for item in values):
      raise ValueError('Flux-section scalar values must be finite and nonnegative.')
    ####
    return values
  ####

  @model_validator(mode='after')
  def validateProduct(self) -> EngineeringFluxSectionProduct:
    if self.metadata.capability != ENGINEERING_FLUX_SECTION_V1:
      raise ValueError(f'Expected capability {ENGINEERING_FLUX_SECTION_V1}.')
    ####
    count = len(self.position_m)
    for name, values in (
        ('area_m2', self.area_m2),
        ('mass_flow_kgps', self.mass_flow_kgps),
        ('momentum_flux_N', self.momentum_flux_N),
        ('total_energy_flow_W', self.total_energy_flow_W),
        ('exhaust_mass_flow_kgps', self.exhaust_mass_flow_kgps),
    ):
      if len(values) != count:
        raise ValueError(f'Expected `{name}` to have {count} entries.')
      ####
    ####
    if any(area <= 0. for area in self.area_m2):
      raise ValueError('Flux-section areas must be positive.')
    ####
    if any(mass <= 0. for mass in self.mass_flow_kgps):
      raise ValueError('Flux-section mass flow must be positive.')
    ####
    if any(
        exhaust_mass > mass_flow + 1.e-12
        for exhaust_mass, mass_flow in zip(self.exhaust_mass_flow_kgps, self.mass_flow_kgps)
    ):
      raise ValueError('Exhaust mass flow cannot exceed total mass flow.')
    ####
    return self
  ####
####
