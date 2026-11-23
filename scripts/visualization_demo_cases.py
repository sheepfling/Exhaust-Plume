"""Scenario construction shared by the offline demo scenes."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

CASE_PATH = REPO_ROOT / "fixtures/products/visualization_demo_cases_v1.json"


def _curved_integral_result(config: Mapping[str, Any]) -> Any:
  from exhaust_plume.models.plume.curved_plume_closures import ConstantEntrainment, CurvedPlumeOptions
  from exhaust_plume.models.plume.curved_plume_solver import solveCurvedPlume
  from exhaust_plume.models.plume.curved_plume_state import AmbientState, CurvedPlumeSource, UniformAmbientField

  source_config = config['source']
  ambient_config = config['ambient']
  ambient = AmbientState.fromIdealGas(
    velocity_mps=np.asarray(ambient_config['velocity_mps'], dtype=float),
    pressure_Pa=ambient_config['pressure_Pa'],
    temperature_K=ambient_config['temperature_K'],
    specific_heat_JpkgK=ambient_config['specific_heat_JpkgK'],
    gas_constant_JpkgK=ambient_config['gas_constant_JpkgK'],
  )
  source = CurvedPlumeSource(
    position_m=np.asarray(source_config['position_m'], dtype=float),
    velocity_mps=np.asarray(source_config['velocity_mps'], dtype=float),
    mass_flow_kgps=source_config['mass_flow_kgps'],
    temperature_K=source_config['temperature_K'],
    static_pressure_Pa=source_config['static_pressure_Pa'],
    specific_heat_JpkgK=source_config['specific_heat_JpkgK'],
    gas_constant_JpkgK=source_config['gas_constant_JpkgK'],
    exhaust_mass_fraction=source_config['exhaust_mass_fraction'],
  )
  options = CurvedPlumeOptions(
    max_arc_length_m=config['max_arc_length_m'],
    number_of_stations=config['number_of_stations'],
    relative_tolerance=config['relative_tolerance'],
    absolute_tolerance=config['absolute_tolerance'],
    max_step_m=config['max_step_m'],
  )
  return solveCurvedPlume(
    source=source,
    ambient_field=UniformAmbientField(ambient),
    entrainment_model=ConstantEntrainment(config['entrainment_kgpspm']),
    options=options,
  )


def _gray_ray_result(
  gray_config: Mapping[str, Any],
) -> tuple[Any, Any, tuple[float, ...], Any]:
  from exhaust_plume.api.v1 import Pose, SPECTRAL_RAY_TRANSFER_V1, SpectralRayTransferRequest
  from exhaust_plume.geometry import SectionedTubeSupport
  from exhaust_plume.products.model_signature import GrayRadiationProfile
  from exhaust_plume.providers import GrayRayTransferDefinition, GrayRayTransferProvider
  from exhaust_plume.radiation import planck_spectral_radiance_W_m2_sr_m

  support_config = gray_config['support']
  wavelengths = tuple(float(value) for value in gray_config['wavelengths_m'])
  support = SectionedTubeSupport(
    frame_id=support_config['frame_id'],
    centers_m=tuple(tuple(float(value) for value in point) for point in support_config['centers_m']),
    radii_m=tuple(float(value) for value in support_config['radii_m']),
  )
  source = planck_spectral_radiance_W_m2_sr_m(
    wavelengths,
    float(gray_config['source_temperature_K']),
    emissivity=float(gray_config['emissivity']),
  )
  profile = GrayRadiationProfile(
    wavelengths_m=wavelengths,
    source_function_w_sr_m=source,
    absorption_coefficient_per_m=tuple(float(value) for value in gray_config['absorption_coefficient_per_m']),
    profile_id=str(gray_config['profile_id']),
  )
  definition = GrayRayTransferDefinition(
    frame_id=support.frame_id,
    support=support,
    wavelengths_m=wavelengths,
    source_function_w_sr_m=profile.source_function_w_sr_m,
    absorption_coefficient_per_m=profile.absorption_coefficient_per_m,
    asset_id=str(gray_config['case_id']),
  )
  rays = gray_config['rays']
  request = SpectralRayTransferRequest(
    ray_frame_id=support.frame_id,
    ray_origins_m=tuple(tuple(float(value) for value in ray['origin_m']) for ray in rays),
    ray_directions=tuple(tuple(float(value) for value in ray['direction']) for ray in rays),
    ray_t_min_m=tuple(float(gray_config['ray_t_min_m']) for _ray in rays),
    ray_t_max_m=tuple(float(gray_config['ray_t_max_m']) for _ray in rays),
    wavelengths_m=wavelengths,
  )
  provider = GrayRayTransferProvider()
  session = provider.create_session(definition=definition)
  try:
    snapshot = session.create_snapshot(
      time_s=0.0,
      source_pose=Pose(frame_id=support.frame_id, translation_m=(0.0, 0.0, 0.0), rotation_xyzw=(0.0, 0.0, 0.0, 1.0)),
      dynamic_state={'whitepaper_case_id': gray_config['case_id']},
      ambient_state={},
    )
    result = snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  finally:
    session.close()
  ####
  return request, result, wavelengths, profile


def _straight_integral_result(config: Mapping[str, Any]) -> Any:
  from math import pow

  from exhaust_plume.contracts.handoff import PlumeFluxSection
  from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
  from exhaust_plume.models.integral.straight import IntegralStraightConfiguration, continue_straight_plume
  from exhaust_plume.models.nozzle.contracts import AmbientInput, NozzleExitInput
  from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit

  gas = CaloricallyPerfectGas.dry_air(gamma=float(config['gamma']))
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=config['ambient_pressure_Pa'], temperature_K=config['ambient_temperature_K']),
    gas,
  )
  pressure_ratio = pow(1.0 + (gas.gamma - 1.0) * float(config['mach']) ** 2 / 2.0, gas.gamma / (gas.gamma - 1.0))
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=config['mach'],
      total_pressure_Pa=float(config['ambient_pressure_Pa']) * pressure_ratio,
      total_temperature_K=config['total_temperature_K'],
      exit_radius_m=config['exit_radius_m'],
    ),
    gas,
  )
  handoff = PlumeFluxSection.from_nozzle_exit(exit_state, ambient_pressure_Pa=ambient.pressure_Pa)
  return continue_straight_plume(
    handoff=handoff,
    ambient=ambient,
    gas=gas,
    config=IntegralStraightConfiguration(
      max_axial_distance_m=config['max_axial_distance_m'],
      step_m=config['step_m'],
      entrainment_coefficient=config['entrainment_coefficient'],
    ),
  )
