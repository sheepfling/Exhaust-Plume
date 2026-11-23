"""Explicit adapters from internal conservative handoff state to wire v1."""

from __future__ import annotations

from typing import Any

from exhaust_plume.contracts.handoff import PlumeFluxSection
from exhaust_plume.contracts.handoff_v1 import (
  HandoffApplicabilityV1,
  HandoffFrameV1,
  HandoffPoseV1,
  HandoffProvenanceV1,
  HandoffSpeciesMassFlowV1,
  PlumeFluxSectionV1,
)


def plume_flux_section_v1_from_solver_state(
    section: PlumeFluxSection,
    *,
    time_s: float,
    frame: HandoffFrameV1,
    section_pose: HandoffPoseV1,
    cross_section_second_moment_m2: tuple[tuple[float, float], tuple[float, float]],
    provenance: HandoffProvenanceV1,
    applicability: HandoffApplicabilityV1,
    uncertainty: dict[str, Any],
) -> PlumeFluxSectionV1:
  """Adapt a solver handoff without inventing missing frame or section data.

  The supplied frame must name the coordinate frame used by the internal
  ``*_plume`` vectors. The supplied section pose must place and orient the
  section in that same frame. Time, cross-section moments, provenance,
  applicability, and uncertainty are required because the internal solver
  state does not carry those wire-level fields. Its
  ``total_enthalpy_flux_w`` maps to stagnation-enthalpy flux; it is never
  relabeled as total energy flow. Internal producer metadata is retained under
  canonical provenance metadata.
  """

  if not isinstance(section, PlumeFluxSection):
    raise TypeError('section must be an internal PlumeFluxSection')
  if not isinstance(frame, HandoffFrameV1):
    raise TypeError('frame must be a HandoffFrameV1')
  if not isinstance(section_pose, HandoffPoseV1):
    raise TypeError('section_pose must be a HandoffPoseV1')
  if not isinstance(provenance, HandoffProvenanceV1):
    raise TypeError('provenance must be a HandoffProvenanceV1')
  if not isinstance(applicability, HandoffApplicabilityV1):
    raise TypeError('applicability must be a HandoffApplicabilityV1')
  if not isinstance(uncertainty, dict):
    raise TypeError('uncertainty must be an explicit JSON-compatible dictionary')
  if section.ambient_pressure_Pa is None:
    raise ValueError('solver handoff cannot be adapted without ambient pressure')
  ####

  if section.advective_momentum_flux_plume_n is None:
    pressure_thrust = tuple(
      (section.pressure_Pa - section.ambient_pressure_Pa) * section.area_m2 * component
      for component in section.normal_plume
    )
    advective_momentum = tuple(
      total - thrust
      for total, thrust in zip(section.momentum_flux_plume_n, pressure_thrust, strict=True)
    )
  else:
    assert section.pressure_thrust_flux_plume_n is not None
    pressure_thrust = section.pressure_thrust_flux_plume_n
    advective_momentum = section.advective_momentum_flux_plume_n
  ####

  producer_metadata = dict(provenance.producer_metadata)
  for key, value in section.provider_metadata.items():
    if key in producer_metadata and producer_metadata[key] != value:
      raise ValueError(f'producer metadata conflicts for key {key!r}')
    producer_metadata[key] = value
  ####
  canonical_provenance = HandoffProvenanceV1.model_validate({
    **provenance.model_dump(mode='python'),
    'producer_metadata': producer_metadata,
  })
  ####

  return PlumeFluxSectionV1(
    time_s=time_s,
    frame=frame,
    section_pose=section_pose,
    center_m=section.center_plume_m,
    normal=section.normal_plume,
    area_m2=section.area_m2,
    mass_flow_kg_s=section.mass_flow_kg_s,
    momentum_flux_N=section.momentum_flux_plume_n,
    advective_momentum_flux_N=advective_momentum,
    pressure_thrust_N=pressure_thrust,
    stagnation_enthalpy_flux_W=section.total_enthalpy_flux_w,
    total_energy_flow_W=None,
    species_mass_flows_kg_s=tuple(
      HandoffSpeciesMassFlowV1(species_id=name, mass_flow_kg_s=rate)
      for name, rate in section.species_mass_flow_rates_kg_s
    ),
    pressure_Pa=section.pressure_Pa,
    ambient_pressure_Pa=section.ambient_pressure_Pa,
    pressure_match_relative_residual=section.pressure_match_relative_residual,
    cross_section_second_moment_m2=cross_section_second_moment_m2,
    characteristic_radius_m=section.characteristic_radius_m,
    provenance=canonical_provenance,
    applicability=applicability,
    uncertainty=uncertainty,
  )
####


__all__ = ('plume_flux_section_v1_from_solver_state',)
