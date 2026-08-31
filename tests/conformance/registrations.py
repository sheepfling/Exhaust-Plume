"""Provider opt-ins and explicit legacy waivers for API-009."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Callable

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.api import v1
from exhaust_plume.contracts.handoff import PlumeFluxSection
from exhaust_plume.providers import (
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
  SignatureTableDefinition,
  SignatureTableProvider,
  StraightAnalyticalDefinition,
  StraightAnalyticalProvider,
  StraightVisualDefinition,
  StraightVisualProvider,
  ShockCellVisualDefinition,
  ShockCellVisualProvider,
)

from .fakes import (
  FakeFailureProvider,
  FakeRayTransferProvider,
  FakeSignatureOnlyProvider,
  FakeVisualOnlyProvider,
)
from .harness import ProductConformanceCase, ProviderFixture

ROOT = Path(__file__).resolve().parents[2]
_POSE = v1.Pose(
  frame_id='world',
  translation_m=(0.0, 0.0, 0.0),
  rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
)


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
  """One built-in provider symbol, fixture registration, or bounded waiver."""

  provider_symbols: tuple[str, ...]
  fixture_factory: Callable[[], ProviderFixture] | None = None
  waiver_reason: str | None = None

  @property
  def is_registered(self) -> bool:
    return self.fixture_factory is not None
  ####
####


CURRENT_PROVIDER_SYMBOLS = (
  'PrescribedVisualProvider',
  'StraightVisualProvider',
  'StraightAnalyticalProvider',
  'StraightAnalyticalPlumeProviderV0',
  'SignatureTableProvider',
  'StaticPlumeProvider',
  'ShockCellAnalyticalProvider',
  'ShockCellVisualProvider',
)


def _visual_definition() -> PrescribedVisualDefinition:
  sections = tuple(
    v1.VisualSection(
      arc_length_m=float(index),
      center_m=(float(index), 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=0.5 + 0.1 * index,
      radius_minor_m=0.25 + 0.05 * index,
    )
    for index in range(4)
  )
  return PrescribedVisualDefinition(
    frame_id='source-local',
    sections=sections,
    channels={'mixing_weight': (0.0, 0.25, 0.75, 1.0)},
  )
####


def _visual_case() -> ProductConformanceCase:
  return ProductConformanceCase(
    capability=v1.VISUAL_SECTIONED_TUBE_V1,
    request=v1.VisualSectionedTubeRequest(
      output_frame_id='source-local',
      sampling=v1.VisualSampling(maximum_section_count=3),
      requested_channels=('mixing_weight',),
    ),
    expected_frame_id='source-local',
  )
####


def _snapshot_from_standard_session(session: v1.ProductSession, time_s: float) -> v1.ProductSnapshot:
  return session.create_snapshot(
    time_s=time_s,
    source_pose=_POSE,
    dynamic_state={},
    ambient_state={},
  )
####


def _prescribed_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='prescribed visual provider',
    provider_factory=PrescribedVisualProvider,
    session_factory=lambda provider: provider.create_session(definition=_visual_definition()),
    snapshot_factory=_snapshot_from_standard_session,
    products=(_visual_case(),),
    unsupported_capabilities=(
      v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
  )
####


def _straight_visual_fixture() -> ProviderFixture:
  definition = StraightVisualDefinition(
    frame_id='source-local',
    length_m=4.0,
    initial_radius_major_m=0.5,
    initial_radius_minor_m=0.25,
    divergence_angle_rad=0.05,
    base_section_count=9,
  )
  return ProviderFixture(
    name='straight visual provider',
    provider_factory=StraightVisualProvider,
    session_factory=lambda provider: provider.create_session(definition=definition),
    snapshot_factory=_snapshot_from_standard_session,
    products=(ProductConformanceCase(
      capability=v1.VISUAL_SECTIONED_TUBE_V1,
      request=v1.VisualSectionedTubeRequest(
        output_frame_id='source-local',
        sampling=v1.VisualSampling(maximum_section_count=3),
        requested_channels=('core_radius_fraction', 'opacity_weight'),
      ),
      expected_frame_id='source-local',
    ),),
    unsupported_capabilities=(
      v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
  )
####


def _analytical_state() -> object:
  payload = json.loads((ROOT / 'tests' / 'fixtures' / 'physics' / 'first_mvp_regression_v1.json').read_text(
    encoding='utf-8',
  ))
  values = payload['gas']
  gas = CaloricallyPerfectGas.dry_air(gamma=values['gamma'])
  pressure_factor = 1.0 + (gas.gamma - 1.0) * values['mach']**2 / 2.0
  total_pressure = values['ambient_pressure_Pa'] * 1.2 * pressure_factor**(
    gas.gamma / (gas.gamma - 1.0)
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=values['mach'],
      total_pressure_Pa=total_pressure,
      total_temperature_K=values['total_temperature_K'],
      exit_radius_m=values['exit_radius_m'],
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=values['ambient_pressure_Pa'],
      temperature_K=values['ambient_temperature_K'],
    ),
    gas,
  )
  from exhaust_plume.providers import StraightAnalyticalOperatingState
  return StraightAnalyticalOperatingState(nozzle_exit=exit_state, ambient=ambient)
####


def _analytical_snapshot(session: v1.ProductSession, time_s: float) -> v1.ProductSnapshot:
  return session.create_snapshot(
    time_s=time_s,
    source_pose=_POSE,
    dynamic_state={'operating_state': _analytical_state()},
    ambient_state={},
  )
####


def _analytical_fixture() -> ProviderFixture:
  request = ProductConformanceCase(
    capability=v1.VISUAL_SECTIONED_TUBE_V1,
    request=v1.VisualSectionedTubeRequest(
      output_frame_id='source-local',
      sampling=v1.VisualSampling(
        maximum_section_count=16,
        maximum_axial_extent_m=8.0,
      ),
      requested_channels=('core_radius_fraction', 'opacity_weight'),
    ),
    expected_frame_id='source-local',
  )
  definition = StraightAnalyticalDefinition(nozzle_radius_m=1.0)
  return ProviderFixture(
    name='straight analytical provider',
    provider_factory=StraightAnalyticalProvider,
    session_factory=lambda provider: provider.create_session(definition=definition),
    snapshot_factory=_analytical_snapshot,
    products=(request,),
    unsupported_capabilities=(
      v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
    probe_times_s=(0.0,),
  )
####


def _signature_definition() -> SignatureTableDefinition:
  return SignatureTableDefinition(
    frame_id='source-local',
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    direction_cosine_nodes=(-0.5, 0.0, 0.5),
    spectral_radiant_intensity_w_sr_m=(
      (0.5, 1.5, 2.5),
      (1.0, 2.0, 3.0),
      (1.5, 2.5, 3.5),
    ),
    absolute_standard_uncertainty_w_sr_m=(
      (0.05, 0.05, 0.05),
      (0.1, 0.1, 0.1),
      (0.15, 0.15, 0.15),
    ),
  )
####


def _signature_case() -> ProductConformanceCase:
  return ProductConformanceCase(
    capability=v1.SPECTRAL_RADIANT_INTENSITY_V1,
    request=v1.SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=(
        (0.0, 1.0, 0.0),
        (0.5, sqrt(3.0) / 2.0, 0.0),
      ),
      wavelengths_m=(1.5e-6, 2.5e-6),
    ),
    expected_frame_id='source-local',
    partial_request=v1.SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
      wavelengths_m=(2.0e-6,),
      allow_partial_results=True,
    ),
    partial_invalid_indices=(0,),
  )
####


def _engineering_section() -> PlumeFluxSection:
  return PlumeFluxSection(
    center_plume_m=(0.0, 0.0, 0.0),
    normal_plume=(1.0, 0.0, 0.0),
    area_m2=1.0,
    mass_flow_kg_s=2.0,
    momentum_flux_plume_n=(10.0, 0.0, 0.0),
    total_enthalpy_flux_w=1000.0,
    species_mass_flow_rates_kg_s=(('air', 2.0),),
    pressure_Pa=101325.0,
    characteristic_radius_m=0.5,
    provider_metadata={'fixture': 'api-009'},
  )
####


def _signature_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='signature table provider',
    provider_factory=SignatureTableProvider,
    session_factory=lambda provider: provider.create_session(definition=_signature_definition()),
    snapshot_factory=_snapshot_from_standard_session,
    products=(_signature_case(),),
    unsupported_capabilities=(
      v1.VISUAL_SECTIONED_TUBE_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
    engineering_sections=(_engineering_section(),),
  )
####


def _shock_cell_visual_snapshot(session: v1.ProductSession, time_s: float) -> v1.ProductSnapshot:
  operating_state = _analytical_state()
  return session.create_snapshot(
    time_s=time_s,
    source_pose=_POSE,
    dynamic_state={'nozzle_exit': operating_state.nozzle_exit},
    ambient_state={'ambient': operating_state.ambient},
  )
####


def _shock_cell_visual_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='shock-cell visual provider',
    provider_factory=ShockCellVisualProvider,
    session_factory=lambda provider: provider.create_session(
      definition=ShockCellVisualDefinition(nozzle_radius_m=1.0),
    ),
    snapshot_factory=_shock_cell_visual_snapshot,
    products=(ProductConformanceCase(
      capability=v1.VISUAL_SECTIONED_TUBE_V1,
      request=v1.VisualSectionedTubeRequest(
        output_frame_id='straight-axisymmetric-xr',
        sampling=v1.VisualSampling(
          maximum_section_count=16,
          maximum_axial_extent_m=8.0,
        ),
        requested_channels=('core_radius_fraction', 'opacity_weight'),
      ),
      expected_frame_id='straight-axisymmetric-xr',
    ),),
    unsupported_capabilities=(
      v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
    probe_times_s=(0.0,),
  )
####


def _fake_visual_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='fake visual-only provider',
    provider_factory=FakeVisualOnlyProvider,
    session_factory=lambda provider: provider.create_session(definition={}, configuration={}),
    snapshot_factory=_snapshot_from_standard_session,
    products=(ProductConformanceCase(
      capability=v1.VISUAL_SECTIONED_TUBE_V1,
      request=v1.VisualSectionedTubeRequest(
        output_frame_id='source-local',
        sampling=v1.VisualSampling(maximum_section_count=3),
      ),
      expected_frame_id='source-local',
    ),),
    unsupported_capabilities=(
      v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
  )
####


def _fake_signature_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='fake signature-only provider',
    provider_factory=FakeSignatureOnlyProvider,
    session_factory=lambda provider: provider.create_session(definition={}, configuration={}),
    snapshot_factory=_snapshot_from_standard_session,
    products=(ProductConformanceCase(
      capability=v1.SPECTRAL_RADIANT_INTENSITY_V1,
      request=v1.SpectralSignatureRequest(
        direction_frame_id='source-local',
        source_to_observer_directions=((0.0, 1.0, 0.0), (0.5, sqrt(3.0) / 2.0, 0.0)),
        wavelengths_m=(1.0e-6, 2.0e-6),
      ),
      expected_frame_id='source-local',
    ),),
    unsupported_capabilities=(
      v1.VISUAL_SECTIONED_TUBE_CAPABILITY,
      v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
    ),
  )
####


def _fake_ray_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='fake ray-transfer provider',
    provider_factory=FakeRayTransferProvider,
    session_factory=lambda provider: provider.create_session(definition={}, configuration={}),
    snapshot_factory=_snapshot_from_standard_session,
    products=(ProductConformanceCase(
      capability=v1.SPECTRAL_RAY_TRANSFER_V1,
      request=v1.SpectralRayTransferRequest(
        ray_frame_id='source-local',
        ray_origins_m=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ray_directions=((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ray_t_min_m=(0.0, 0.0),
        ray_t_max_m=(1.0, 1.0),
        wavelengths_m=(1.0e-6, 2.0e-6),
      ),
      expected_frame_id='source-local',
    ),),
    unsupported_capabilities=(
      v1.VISUAL_SECTIONED_TUBE_CAPABILITY,
      v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
    ),
  )
####


def _failure_fixture() -> ProviderFixture:
  return ProviderFixture(
    name='fake descriptor-mismatch provider',
    provider_factory=FakeFailureProvider,
    session_factory=lambda provider: provider.create_session(definition={}, configuration={}),
    snapshot_factory=_snapshot_from_standard_session,
    products=(_visual_case(),),
  )
####


PROVIDER_REGISTRATION_TABLE = (
  ProviderRegistration(('PrescribedVisualProvider',), _prescribed_fixture),
  ProviderRegistration(('StraightVisualProvider',), _straight_visual_fixture),
  ProviderRegistration(
    ('StraightAnalyticalProvider', 'StraightAnalyticalPlumeProviderV0'),
    _analytical_fixture,
  ),
  ProviderRegistration(('SignatureTableProvider',), _signature_fixture),
  ProviderRegistration(
    ('StaticPlumeProvider',),
    waiver_reason=(
      'fixture-only 0.1.x compatibility provider; new production providers use '
      'ProductProvider/ProductSession/ProductSnapshot'
    ),
  ),
  ProviderRegistration(
    ('ShockCellAnalyticalProvider',),
    waiver_reason=(
      'legacy spatial capability API retained for 0.1.x compatibility; '
      'use ShockCellVisualProvider for canonical visual output'
    ),
  ),
  ProviderRegistration(('ShockCellVisualProvider',), _shock_cell_visual_fixture),
)


def registered_provider_fixtures() -> tuple[ProviderFixture, ...]:
  return tuple(
    registration.fixture_factory()
    for registration in PROVIDER_REGISTRATION_TABLE
    if registration.fixture_factory is not None
  )
####


def fake_provider_fixtures() -> tuple[ProviderFixture, ...]:
  return (_fake_visual_fixture(), _fake_signature_fixture(), _fake_ray_fixture())
####


def failure_provider_fixture() -> ProviderFixture:
  return _failure_fixture()
####


__all__ = (
  'CURRENT_PROVIDER_SYMBOLS',
  'PROVIDER_REGISTRATION_TABLE',
  'ProviderRegistration',
  'fake_provider_fixtures',
  'failure_provider_fixture',
  'registered_provider_fixtures',
)
