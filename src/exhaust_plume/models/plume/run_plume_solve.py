# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, fields
from typing import Any, List, Mapping, Optional, Sequence

from numpy import array, asarray, full, inf, isfinite, linspace, nan, nanmax, nanmin, ndarray, polyval, ptp

from exhaust_plume.log.extra_log_levels import VERBOSE, setDefaultLogLevels
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger
from exhaust_plume.models.plume.plume_solve import ZoneCoordinates, ZoneResult, ZoneType, calculatePlumeZones, printPrettyTableZones
from exhaust_plume.util.arg_util import getRangeLimitedType
from exhaust_plume.util.atmosphere.pdas_atmosphere_interpolator import PdasAtmosphereScalarState, calculateAtmosphereStateFromGeopotentialAltitude
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM

log = getCleanLogger(__name__)

@dataclass(frozen=True)
class ScriptOptions:
  altitude_m: float = 10.e3
  nozzle_pressure_atm: float = 69.
  nozzle_temperature_K: float = 2000.
  nozzle_mach: float = 4.130
  nozzle_radius_m: float = 1.
  num_expansion_lines: int = 2
  num_compression_lines: int = 1
  num_plumes: int = 1
  gamma: float = 1.33
  show_plots: bool = False

  @classmethod
  def addArgumentsToParser(cls, parser: ArgumentParser) -> ArgumentParser:
    defaults = ScriptOptions()
    parser.add_argument('--show-plots', action='store_true', help='Displays plots')
    parser.add_argument(
        '--num-plumes', type=getRangeLimitedType(typ=int, min_val=1, max_val=None, ),
        default=defaults.num_plumes, help="Number of plumes to calculate",
    )
    parser.add_argument(
        '--altitude-m', type=float, default=defaults.altitude_m,
        help="Altitude of the plume. Determines atmospheric parameters",
    )
    parser.add_argument(
        '--num-expansion-lines', type=getRangeLimitedType(typ=int, min_val=2, max_val=None, ),
        default=defaults.num_expansion_lines, help="Number of expansion fans")
    parser.add_argument(
        '--num-compression-lines', type=getRangeLimitedType(typ=int, min_val=1, max_val=None, ),
        default=defaults.num_compression_lines, help="Number of reflected compression lines")
    parser.add_argument(
        '--nozzle-pressure-atm', type=getRangeLimitedType(typ=float, min_val=0., max_val=inf, max_is_valid=False),
        default=defaults.nozzle_pressure_atm, help='Nozzle pressure in Atmospheres (atm).',
    )
    parser.add_argument(
        '--nozzle-temperature-K', type=getRangeLimitedType(typ=float, min_val=0., max_val=inf, max_is_valid=False),
        default=defaults.nozzle_temperature_K, help='Nozzle temperature in Kelvin',
    )
    parser.add_argument(
        '--nozzle-mach', type=getRangeLimitedType(typ=float, min_val=1., max_val=inf, max_is_valid=False),
        default=defaults.nozzle_mach, help='Nozzle exit speed in mach',
    )
    parser.add_argument(
        '--nozzle-radius', type=getRangeLimitedType(typ=float, min_val=0., max_val=inf, max_is_valid=False),
        dest='nozzle_radius_m',
        default=defaults.nozzle_radius_m, help='Nozzle radius in meters',
    )
    parser.add_argument(
        '--gamma', type=getRangeLimitedType(typ=float, min_val=0., max_val=None, min_is_valid=False),
        default=defaults.gamma, help='Gas gamma (γ=Cp/Cv)')
    return parser
  ####

  @classmethod
  def fromNamespace(cls, args: Namespace) -> ScriptOptions:
    out = ScriptOptions(
        num_expansion_lines=int(args.num_expansion_lines),
        num_compression_lines=int(args.num_compression_lines),
        num_plumes=int(args.num_plumes),
        show_plots=bool(args.show_plots),
        gamma=float(args.gamma),
        altitude_m=float(args.altitude_m),
        nozzle_mach=float(args.nozzle_mach),
        nozzle_radius_m=float(args.nozzle_radius_m),
        nozzle_temperature_K=float(args.nozzle_temperature_K),
        nozzle_pressure_atm=float(args.nozzle_pressure_atm),
    )
    return out
  ####
####


def plotNormalizedZoneValues(zones: Sequence[ZoneResult], atmos_stat: PdasAtmosphereScalarState, num_plumes: int) -> List[Any]:
  from matplotlib import pyplot as plt

  indices = range(len(zones))
  machs = array([z.mach for z in zones])
  total_pressure_Pa = array([z.total_pressure for z in zones])
  total_density_kgmp3 = array([z.static_density for z in zones])
  spec_energy_Jpkg = array([z.specific_total_energy_Jpkg for z in zones])
  name2value_groups = {
      'Static': {
          'Static Pressue/Atmosphere': array([z.static_pressure for z in zones]) / atmos_stat.getPressure_Pa(),
          'Static Temperature/Atmosphere': array([z.static_temperature for z in zones]) / atmos_stat.getTemperature_K(),
          'Mach/Max': machs / nanmax(machs),
      },
      'Total': {
          'Total Density/Atmosphere': total_density_kgmp3 / atmos_stat.getDensity_kgpm3(),
          'Total Pressure/Atmosphere': total_pressure_Pa / atmos_stat.getPressure_Pa(),
          'Specific Energy/Atmosphere': spec_energy_Jpkg / (atmos_stat.getPressure_Pa() / atmos_stat.getDensity_kgpm3()),
      }
  }

  figs = []
  for group_name, name2value in name2value_groups.items():
    fig, ax = plt.subplots(1, 1)
    for name, value in name2value.items():
      ax.plot(indices, value / nanmax(value), label=name)
    ####
    ax.set_xlabel('Region Index')
    ax.set_ylabel('Atmosphere Normalized Values / Max')
    ax.grid()
    ax.legend()
    ax.set_title(f'Normalized Region {group_name} Parameters for {num_plumes} Plumes')
    figs.append(fig)
  ####
  return figs
####


def plotTotalPressureDensity(zones: Sequence[ZoneResult], num_plumes: int) -> List[Any]:
  from matplotlib import pyplot as plt

  indices = range(len(zones))
  total_pressure_Pa = array([z.total_pressure for z in zones])
  total_density_kgmp3 = array([z.static_density for z in zones])
  fig, ax0 = plt.subplots(1, 1)
  axs = [ax0, ax0.twinx()]
  names = [
      r'Total Density $\left[\frac{\mathrm{kg}}{\mathrm{m}^3}\right]$',
      r'Total Pressure $\left[\mathrm{MPa}\right]$',
  ]
  values = [
      total_density_kgmp3,
      total_pressure_Pa * 1e-6,
  ]
  colors = ['C0', 'C1', ]
  for ax, name, value, color in zip(axs, names, values, colors):
    ax.plot(indices, value, color=color)
    ax.set_xlabel('Region Index')
    ax.set_ylabel(name, color=color)
    ax.tick_params(axis='y', color=color, labelcolor=color)
    ax.grid()
  ####
  ax0.set_title(f'Total Pressure & Density for {num_plumes} Plumes')
  return [fig, ]
####


def plotSpecificEnergy(zones: Sequence[ZoneResult], num_plumes: int) -> List[Any]:
  import matplotlib.ticker as mticker
  from matplotlib import pyplot as plt

  indices = range(len(zones))
  spec_energy_Jpkg = array([z.specific_total_energy_Jpkg for z in zones])
  fig, ax = plt.subplots(1, 1)
  ax.plot(indices, spec_energy_Jpkg / nanmax(spec_energy_Jpkg) * 100.)
  ax.set_xlabel('Region Index')
  ax.set_ylabel(r'Specific Energy/Max %')
  ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=2))
  ax.grid()
  ax.set_title(f'Specific Energy for {num_plumes} Plumes')
  return [fig, ]
####


def plotZoneCoordinates2D(zones: Sequence[ZoneResult], extra: Optional[Mapping[str, Any]] = None) -> List[Any]:
  from matplotlib import pyplot as plt

  figs = []
  fig, ax = plt.subplots(1, 1)
  if extra is None:
    extra = {}
  ####
  for zone in zones:
    c = zone.coordinates.corners_ru
    if not all(isfinite(c).ravel()):
      continue
    ####
    idx = [*range(len(c)), 0]
    ax.plot(c[idx, 0], c[idx, 1], '--', label=f'{zone.label} {zone.plume_index},{zone.group_index}')
  ####
  if 'points' in extra:
    extra_points: Mapping[str, ndarray] = extra['points']
    for name, point in extra_points.items():
      ax.plot(point[0], point[1], '.', label=f'{name}')
    ####
    if 'plume_fit' in extra:
      point_A = extra_points['A']
      point_F = extra_points['F']
      point_G = extra_points['G']
      mid_point = (point_G[0] + point_F[0]) / 2.
      x = linspace(point_A[0], point_A[0] + 2 * (mid_point - point_A[0]), 100)
      p: ndarray = extra['plume_fit']
      y = polyval(p, x)
      ax.plot(x, y, label='Plume Fit', markersize=25)
    ####
  ####
  ax.set_xlabel('Right')
  ax.set_ylabel('Up')
  ax.grid()
  ax.legend()
  figs.append(fig)
  return figs
####


def plotZoneCoordinates3D(zones: Sequence[ZoneResult],
                          num_plumes: int,
                          colormap_key: str = 'static_temperature', num_rotations: int = 30,
                          ) -> List[Any]:
  from matplotlib import pyplot as plt

  from exhaust_plume.models.plume.visualization import generateRevolvedMesh, plotRevolvedMeshes

  if not zones:
    return []
  ####
  figs = []
  meshes = []
  values = []
  if not hasattr(zones[0], colormap_key):
    log.error(f'Colormap key:{colormap_key!r} is not a field of {type(zones[0])}. Valid values are {[f.name for f in fields(zones[0])]}')
    return []
  ####
  for zone in zones:
    mesh = generateRevolvedMesh(zone.coordinates.corners_ru, axis=asarray([1., 0., 0.]), num_rotations=num_rotations)
    meshes.append(mesh)
    values.append(getattr(zone, colormap_key))
  ####

  values = array(values)
  normed_values = (values - nanmin(values)) / ptp(values)
  from matplotlib import colormaps

  colors = colormaps['jet'](normed_values)

  fig = plt.figure(figsize=(10, 10))
  ax, _ = plotRevolvedMeshes(
      meshes=meshes,
      face_colors=colors,
      face_kwargs={
          'edgecolor': (.8, .8, .8, .1,),
          'alpha': .3,
      },
  )
  ax.set_title(f'{num_plumes} Plumes Regions ' + ' '.join(s.capitalize() for s in colormap_key.lower().split('_')))
  figs.append(fig)
  return figs
####


def main() -> None:
  if not configureLogging():
    print('Could not configure logging')
  ####

  parser = ArgumentParser()
  parser = ScriptOptions.addArgumentsToParser(parser)

  args, unknown = parser.parse_known_args(sys.argv[1:])

  if unknown:
    log.warning(f'Unknown arguments passed to sript:{unknown}')
  ####

  opts = ScriptOptions.fromNamespace(args)
  log.debug(f'Parsed options:{opts}')

  # UnderExanded #'s
  # OverExanded #'s
  # under_expanded_alt_m = 10e3
  # over_expanded_alt_m = 5e3

  atmos_stat = calculateAtmosphereStateFromGeopotentialAltitude(
      geopotential_altitude_m=opts.altitude_m,
  )
  out_zones, extra = calculatePlumeZones(
      nozzle_total_temperature=opts.nozzle_temperature_K,
      nozzle_total_pressure=opts.nozzle_pressure_atm * PASCAL_PER_ATM,
      nozzle_mach=opts.nozzle_mach,
      gamma=opts.gamma,
      atmospheric_pressure=atmos_stat.pressure_Pa,
      nozzle_radius=opts.nozzle_radius_m,
      num_expansion_lines=opts.num_expansion_lines,
      num_compression_lines=opts.num_compression_lines,
      num_plumes=opts.num_plumes,
  )
  log.info(f'Atmospheric Pressure: {atmos_stat.pressure_Pa:#7.4g} [Pa]')
  printPrettyTableZones(
      zones=[
          ZoneResult(
              mach=nan,
              static_temperature=atmos_stat.temperature_K,
              static_pressure=atmos_stat.pressure_Pa,
              label='Atmosphere',
              beta=nan,
              theta=nan,
              coordinates=ZoneCoordinates(full((3, 2), nan)),
              gamma=nan,
              plume_index=0,
              group_number=0,
              group_index=0,
              type=ZoneType.Isentropic,
              static_density=atmos_stat.density_kgpm3,
          ),
          *out_zones
      ],
      p_amtos=atmos_stat.pressure_Pa,
      title='Plume Zone Parameters',
  )

  figs = []

  if opts.show_plots:
    figs.extend(plotTotalPressureDensity(zones=out_zones, num_plumes=opts.num_plumes))
    figs.extend(plotSpecificEnergy(zones=out_zones, num_plumes=opts.num_plumes))
    figs.extend(plotNormalizedZoneValues(zones=out_zones, num_plumes=opts.num_plumes, atmos_stat=atmos_stat))

    figs.extend(plotZoneCoordinates2D(zones=out_zones, extra=extra))

    for f in fields(ZoneResult):
      if 'static' not in f.name:
        continue
      ####
      figs.extend(plotZoneCoordinates3D(
          zones=out_zones, num_rotations=20, num_plumes=opts.num_plumes,
          colormap_key=f.name,
      ))
    ####
  ####

  if figs:
    from matplotlib import pyplot as plt

    plt.show()
    for fig in figs:
      if fig is not None:
        continue
      ####
      plt.close(fig)
    ####
  ####
####


if __name__ == "__main__":
  setDefaultLogLevels()
  log = getLogger(__name__)
  log.log(VERBOSE, f'argv {sys.argv[1:]}')
  main()
####
