# -*- coding: utf-8 -*-
"""
@author: nathan.tendick

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum, auto as getAutoEnumValue
from numbers import Integral
from typing import Any, ClassVar, Dict, List, Sequence, Tuple, Union

from numpy import argmax, argmin, asarray, cos, eye, full, isfinite, isnan, nan, nanmax, ndarray, polyfit, polyval, ptp, repeat, roots, sin, tan, vstack
from numpy.linalg import pinv

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.aero.constants import MAX_ITER_DEFAULT
from exhaust_plume.util.aero.expansion_fan import ExpansionFanState
from exhaust_plume.util.aero.flow_state import FlowState
from exhaust_plume.util.aero.ideal_gas import calcDensityFromSpecificVolume, calcIdealGasSpecificVolumeFromPressureSpecificWork, calcIdealGasSpecificWorkFromMolarMassTemperature
from exhaust_plume.util.aero.isentropic_flow import calcIsentropicStaticDensity, calcIsentropicStaticPressure, calcIsentropicStaticTemperature
from exhaust_plume.util.aero.oblique_shock import ObliqueShockState
from exhaust_plume.util.atmosphere.constants import MOLAR_MASS_DRY_AIR_kg
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.dataclass_util import dataclassIsClose, dataclassIsEqual
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, makeReadOnly, unitize
from exhaust_plume.util.physical_constants import ATM_PER_PASCAL

###########################################
log = getCleanLogger(__name__)


def _validate_positive_finite(name: str, value: float) -> None:
  try:
    value_float = float(value)
  except (TypeError, ValueError) as exc:
    raise ValueError(f'Expected `{name}` to be a finite positive number. Got:{value}') from exc
  if not isfinite(value_float) or value_float <= 0.:
    raise ValueError(f'Expected `{name}` to be a finite positive number. Got:{value}')
  ##
##


def _validate_gamma(gamma: float) -> None:
  _validate_positive_finite('gamma', gamma)
  if float(gamma) <= 1.:
    raise ValueError(f'Expected `gamma` to be greater than 1. Got:{gamma}')
  ##
##


def _validate_count(name: str, value: int, minimum: int) -> None:
  if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
    raise ValueError(f'Expected `{name}` to be an integer greater than or equal to {minimum}. Got:{value}')
  ##
##


def calcLineIntersection2d(*,
                           line1_offset: ndarray, line1_direction: ndarray,
                           line2_offset: ndarray, line2_direction: ndarray) -> ndarray:
  # line1_dir * p1 + line1_offset = line2_dir * p2 + line2_offset
  line_param = pinv(vstack([line1_direction, -line2_direction]).T) @ (line2_offset - line1_offset)
  intersection_point = line1_offset + line_param[0] * line1_direction
  return intersection_point
##


def fitParabolaFromPoints2d(points: Sequence[ndarray]) -> ndarray:
  # returns parameters used to be used in a polyval
  x, y = vstack(points).T
  p = polyfit(y=y, x=x, deg=2)
  return p
##


def calcLineParabolaIntersection2d(line_offset: ndarray, line_direction: ndarray, parabola_coeff: ndarray) -> ndarray:
  """ Calculates first intersection with a line and a parabola.
  Assumes that line direction is not straight up (direction x component !=0)
  """
  line_slope = line_direction[1] / line_direction[0]
  line_coeff = asarray([0., line_slope, -line_slope * line_offset[0] + line_offset[1], ])
  intersection_x = roots(parabola_coeff - line_coeff)
  # Get first positive intersection
  intersection_x = min(intersection_x[intersection_x > 0])
  intersection_y = polyval(line_coeff, intersection_x)
  return asarray([intersection_x, intersection_y])
##


RIGHT, UP = makeReadOnly(eye(2))

M_reflect_up = makeReadOnly(vstack([RIGHT, -UP]))


class ZoneType(Enum):
  Isentropic = getAutoEnumValue()
  ObliqueShock = getAutoEnumValue()
  ExpansionFan = getAutoEnumValue()
##


@dataclass
class ZoneCoordinates:
  corners_ru: ndarray

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if isinstance(v, ndarray):
        v.flags.writeable = False
      ##
    ##
    if len(self.corners_ru.shape) != 2 or self.corners_ru.shape[-1] != 2:
      raise ValueError(f'Expected corners to shape:(...,2). Got:{self.corners_ru.shape}')
    ##
  ##

  @cached_property
  def center(self) -> ndarray:
    return self.corners_ru.mean(axis=0)
  ##

  @cached_property
  def width(self) -> float:
    return ptp(self.corners_ru[..., 0])
  ##

  @cached_property
  def height(self) -> float:
    return ptp(self.corners_ru[..., 1])
  ##

  @cached_property
  def top_left_corner(self) -> ndarray:
    out_corners = self.corners_ru[self.corners_ru[..., 1] >= self.center[..., 1], ...]
    if len(out_corners) != 1:
      return out_corners[argmin(out_corners[..., 0]), ...]
    else:
      return out_corners[0, ...]
    ##
  ##

  @cached_property
  def top_right_corner(self) -> ndarray:
    out_corners = self.corners_ru[self.corners_ru[..., 1] >= self.center[..., 1], ...]
    if len(out_corners) != 1:
      return out_corners[argmax(out_corners[..., 0]), ...]
    else:
      return out_corners[0, ...]
    ##
  ##

  @cached_property
  def bottom_left_corner(self) -> ndarray:
    out_corners = self.corners_ru[self.corners_ru[..., 1] <= self.center[..., 1], ...]
    if len(out_corners) != 1:
      return out_corners[argmin(out_corners[..., 0]), ...]
    else:
      return out_corners[0, ...]
    ##
  ##

  @cached_property
  def bottom_right_corner(self) -> ndarray:
    out_corners = self.corners_ru[self.corners_ru[..., 1] <= self.center[..., 1], ...]
    if len(out_corners) != 1:
      return out_corners[argmax(out_corners[..., 0]), ...]
    else:
      return out_corners[0, ...]
    ##
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    return dataclassIsClose(self, other, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def __hash__(self) -> int:
    tup = tuple(x.data.tobytes() if isinstance(x, ndarray) else x for x in (
        getattr(self, f.name) for f in fields(self)
    ))
    return hash(tup)
  ##

##


@dataclass(frozen=True)
class ZoneResult(FlowState):
  PLUME_INDEX_START_NUMBER: ClassVar[int] = 1
  GROUP_NUMBER_START: ClassVar[int] = 1
  GROUP_INDEX_START: ClassVar[int] = 1

  plume_index: int
  group_number: int
  group_index: int
  label: str
  type: ZoneType
  beta: float
  theta: float
  coordinates: ZoneCoordinates

  @cached_property
  def static_pressure_atm(self) -> float:
    return self.static_pressure * ATM_PER_PASCAL
  ##

  def asFlowState(self) -> FlowState:
    out = FlowState(
        static_pressure=self.static_pressure,
        static_temperature=self.static_temperature,
        mach=self.mach,
        gamma=self.gamma,
        static_density=self.static_density,
    )
    return out
  ##

  def replace(self, coordinates: ZoneCoordinates) -> ZoneResult:
    out = ZoneResult(
        plume_index=self.plume_index,
        group_number=self.group_number,
        group_index=self.group_index,
        label=self.label,
        type=self.type,
        beta=self.beta,
        theta=self.theta,
        coordinates=coordinates,
        gamma=self.gamma,
        mach=self.mach,
        static_pressure=self.static_pressure,
        static_temperature=self.static_temperature,
        static_density=self.static_density,
    )
    return out
  ##

  def asObliqueShockState(self) -> ObliqueShockState:
    out = ObliqueShockState(
        shock_angle_deg=self.beta,
        oblique_angle_deg=self.theta,
        static_pressure=self.static_pressure,
        static_temperature=self.static_temperature,
        mach=self.mach,
        gamma=self.gamma,
        static_density=self.static_density,
    )
    return out
  ##

  @classmethod
  def fromFlowState(cls,
                    label: str,
                    plume_index: int, group_number: int, group_index: int,
                    coordinates: ZoneCoordinates,
                    beta: float, theta: float,
                    state: FlowState,
                    ) -> ZoneResult:
    if isinstance(state, ObliqueShockState):
      typ = ZoneType.ObliqueShock
    elif isinstance(state, ExpansionFanState):
      typ = ZoneType.ExpansionFan
    else:
      typ = ZoneType.Isentropic
    ##
    out = ZoneResult(
        label=label,
        plume_index=plume_index,
        group_number=group_number,
        group_index=group_index,
        coordinates=coordinates,
        beta=beta,
        theta=theta,
        static_pressure=state.static_pressure,
        static_temperature=state.static_temperature,
        mach=state.mach,
        gamma=state.gamma,
        type=typ,
        static_density=state.static_density,
    )
    return out
  ##

  @classmethod
  def fromExpansionFan(cls, state: ExpansionFanState, label: str,
                       coordinates: ZoneCoordinates,
                       plume_index: int, group_number: int, group_index: int,
                       ) -> ZoneResult:
    return cls.fromFlowState(
        state=state, coordinates=coordinates,
        plume_index=plume_index, label=label, group_index=group_index, group_number=group_number,
        beta=nan, theta=state.turn_deg,
    )
  ##

  @classmethod
  def fromObliqueShockState(cls, state: ObliqueShockState, label: str,
                            coordinates: ZoneCoordinates,
                            plume_index: int,
                            group_number: int,
                            group_index: int, ) -> ZoneResult:
    return cls.fromFlowState(
        state=state, coordinates=coordinates,
        plume_index=plume_index, label=label, group_index=group_index, group_number=group_number,
        beta=state.shock_angle_deg, theta=state.oblique_angle_deg,
    )
  ##

##


def printPrettyTableZones(zones: Sequence[Union[ZoneResult, ObliqueShockState, ExpansionFanState, FlowState]],
                          title: str,
                          p_amtos: float) -> None:
  from exhaust_plume.log.terminal_colormaps import PiYG as tc_PiYG, RdBu as tc_RdBu, hot as tc_hot, rainbow as tc_rainbow, terrain as tc_terrain
  from exhaust_plume.util.pretty_table import ColumnColorOption, ColumnSortOrder, PrettyTable

  lods = []
  keys = [
      'Plume', 'Group', '#', 'Type', 'Label', 'Beta', 'Theta',
      'Static P/Atmos',
      'Static Temp', 'Mach',
      'Energy %',
      'Total Pressure %',
      'Total Density %',
  ]
  data: Dict[str, Any]
  max_energy = nanmax([z.specific_total_energy_Jpkg for z in zones])
  max_total_pressure = nanmax([z.total_pressure for z in zones])
  max_total_density = nanmax([z.total_density for z in zones])
  for z in zones:
    data = {k: None for k in keys}
    beta = None
    theta = None
    if isinstance(z, ZoneResult):
      data['Plume'] = z.plume_index
      data['Group'] = z.group_number
      data['#'] = z.group_index
      data['Type'] = z.type.name
      data['Label'] = z.label
      beta = z.beta
      theta = z.theta
    elif isinstance(z, ObliqueShockState):
      beta = z.shock_angle_deg
      theta = z.oblique_angle_deg
    elif isinstance(z, ExpansionFanState):
      theta = z.turn_deg
    ##
    if beta is not None and not isnan(beta):
      data['Beta'] = f'{beta:#4.4g}'
    ##
    if theta is not None and not isnan(theta):
      data['Theta'] = f'{theta:#4.4g}'
    ##
    data['Static P/Atmos'] = None if isnan(z.static_pressure) else f'{z.static_pressure / p_amtos:f}'
    data['Static Temp'] = None if isnan(z.static_temperature) else f'{z.static_temperature:#4.4g}'
    data['Mach'] = None if isnan(z.mach) else f'{z.mach:#4.4g}'
    data['Energy %'] = None if isnan(z.specific_total_energy_Jpkg) else f'{z.specific_total_energy_Jpkg / max_energy * 100.:#6.2f}'
    data['Total Pressure %'] = None if isnan(z.total_pressure) else f'{z.total_pressure / max_total_pressure * 100.:#6.2f}'
    data['Total Density %'] = None if isnan(z.total_density) else f'{z.total_density / max_total_density * 100.:#6.2f}'
    lods.append(data)
  ##
  pt = PrettyTable(
      list_of_dicts=lods,
      title=title,
      show_border=True,
      show_row_index=False,
      column_fg_colormaps={
          'Type': ColumnColorOption(cmap=tc_rainbow, order=ColumnSortOrder.Descending),
          'Label': ColumnColorOption(cmap=tc_rainbow, order=ColumnSortOrder.Descending),
          'Plume': ColumnColorOption(cmap=tc_rainbow, order=ColumnSortOrder.Descending),
          'Group': ColumnColorOption(cmap=tc_rainbow, order=ColumnSortOrder.Descending),
          '#': ColumnColorOption(cmap=tc_rainbow, order=ColumnSortOrder.Descending),
          'Static Temp': ColumnColorOption(cmap=tc_jet, order=ColumnSortOrder.Ascending),
          'Mach': ColumnColorOption(cmap=tc_PiYG, order=ColumnSortOrder.Descending),
          'Static P/Atmos': ColumnColorOption(cmap=tc_RdBu, order=ColumnSortOrder.Descending),
          'Beta': ColumnColorOption(cmap=tc_terrain, order=ColumnSortOrder.Descending),
          'Theta': ColumnColorOption(cmap=tc_terrain, order=ColumnSortOrder.Descending),
          'Energy %': ColumnColorOption(cmap=lambda N: tc_hot(N + 1)[1:], order=ColumnSortOrder.Ascending),
          'Total Pressure %': ColumnColorOption(cmap=tc_RdBu, order=ColumnSortOrder.Descending),
          'Total Density %': ColumnColorOption(cmap=tc_RdBu, order=ColumnSortOrder.Descending),
      },
  )
  print(pt.get_string(show_header=True, show_row_index=False))
##


def calculateOverExpandedPrecursorStates(zone1: FlowState,
                                         atmospheric_pressure: float,
                                         rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT,
                                         max_iter: int = MAX_ITER_DEFAULT,
                                         ) -> Tuple[ObliqueShockState, ObliqueShockState]:
  # Zone 2 is an oblique shock to equalize pressure
  zone2_os = ObliqueShockState.fromUpstreamStateToEqualizedPressureState(
      upstream=zone1,
      downstream_static_pressure=atmospheric_pressure,
      rtol=rtol, atol=atol, max_iter=max_iter,
  )
  # Zone 3 - 2nd oblique shock from hitting the centerline
  zone3_os = ObliqueShockState.fromUpstreamState(
      upstream=zone2_os, oblique_angle_deg=zone2_os.oblique_angle_deg,
  )

  out = (zone2_os, zone3_os,)
  return out
##


def calculateUnderExpandedPlumeStates_Expansion(
        zone1: FlowState,
        atmospheric_pressure: float,
        num_fan_lines: int = 2,  # number of lines to evaluate method of characteristics
        atol: float = ATOL_DEFAULT, rtol: float = RTOL_DEFAULT, max_iter: int = MAX_ITER_DEFAULT,
) -> Tuple[Sequence[ExpansionFanState], Sequence[ExpansionFanState]]:
  """ Calculates states in the first half of the plume """
  # Expansion fan to equalize pressure
  zone2_efs = ExpansionFanState.fromUpstreamStateToEqualizedPressureState(
      zone1,
      downstream_static_pressure=atmospheric_pressure,
      num_fan_lines=num_fan_lines,
      rtol=rtol, atol=atol, max_iter=max_iter,
  )

  # How hardcoded second expansion fan worked:
  # Upstream 2b, Turn 2A -> 3A
  # Upstream 3a, Turn 2B -> 3B
  # Therefore, Upstreams starts with last fan from first group,
  # and then subsequent upsreams are the newly generated fan states
  # However, the turns are equal to the first expansion turns in order
  expansion_angles_deg = [z.turn_deg for z in zone2_efs]
  zone3_efs = []
  prev_state = zone2_efs[-1]
  for expansion_angle_deg in expansion_angles_deg:
    zone3_efs.append(ExpansionFanState.fromTurnedUpstreamState(
        upstream=prev_state,
        turn_deg=expansion_angle_deg,
        rtol=rtol, atol=atol, max_iter=max_iter,
    ))
    prev_state = zone3_efs[-1]
  ##

  out = (zone2_efs, zone3_efs,)
  return out
##


def calculateUnderExpandedPlumeStates_Compression(
        upstream: FlowState,
        total_expansion_angle_deg: float,
        atmospheric_pressure: float,
        num_compression_fans: int = 1,
        atol: float = ATOL_DEFAULT, rtol: float = RTOL_DEFAULT, max_iter: int = MAX_ITER_DEFAULT,
) -> Tuple[List[ObliqueShockState], List[ObliqueShockState]]:
  """ Calculates latter Expansion states assuming just a Single Oblique shock
  """
  # Zone 4 are the PM compression waves
  # but the only one that matters is the first one because this one equalizes the pressure
  # the rest of the waves collapse into this one.
  expansion_angles_deg = repeat(total_expansion_angle_deg / num_compression_fans, num_compression_fans)

  zone4_oss = []
  prev_state = upstream
  for expansion_angle_deg in expansion_angles_deg[1:]:
    zone4_oss.append(ObliqueShockState.fromUpstreamState(
        upstream=prev_state,
        oblique_angle_deg=expansion_angle_deg,
    ))
    prev_state = zone4_oss[-1]
  ##

  zone4_oss.append(ObliqueShockState.fromUpstreamStateToEqualizedPressureState(
      upstream=prev_state,
      downstream_static_pressure=atmospheric_pressure,
      rtol=rtol, atol=atol, max_iter=max_iter,
  ))

  zone5_oss = []
  prev_state = zone4_oss[-1]
  for expansion_angle_deg in expansion_angles_deg:
    zone5_oss.append(ObliqueShockState.fromUpstreamState(
        upstream=prev_state,
        oblique_angle_deg=expansion_angle_deg,
    ))
    prev_state = zone5_oss[-1]
  ##

  out = (zone4_oss, zone5_oss,)
  return out
##


def calculateUnderExpandedPlumeStates(
        zone1: FlowState,
        atmospheric_pressure: float,
        num_expansion_lines: int,
        num_compression_lines: int,
        atol: float = ATOL_DEFAULT, rtol: float = RTOL_DEFAULT, max_iter: int = MAX_ITER_DEFAULT,
) -> Tuple[Sequence[ExpansionFanState], Sequence[ExpansionFanState], List[ObliqueShockState], List[ObliqueShockState]]:
  # Expansion fan to equalize pressure

  zone2_efs, zone3_efs = calculateUnderExpandedPlumeStates_Expansion(
      zone1=zone1,
      atmospheric_pressure=atmospheric_pressure,
      num_fan_lines=num_expansion_lines,
      rtol=rtol, atol=atol, max_iter=max_iter,
  )

  zone4_oss, zone5_oss = calculateUnderExpandedPlumeStates_Compression(
      upstream=zone3_efs[-1],
      atmospheric_pressure=atmospheric_pressure,
      rtol=rtol, atol=atol, max_iter=max_iter,
      num_compression_fans=num_compression_lines,
      total_expansion_angle_deg=sum(z.turn_deg for z in zone3_efs),
  )

  out = (zone2_efs, zone3_efs, zone4_oss, zone5_oss,)
  return out
##


def calculateOverExpandedPrecursorZones(zone1: ZoneResult,
                                        atmospheric_pressure: float,
                                        rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT,
                                        max_iter: int = MAX_ITER_DEFAULT,
                                        ) -> List[ZoneResult]:
  """ Only calculates enough initial zones to get to an equivalent UnderExandped case. """
  zone2_os, zone3_os = calculateOverExpandedPrecursorStates(
      zone1=zone1.asFlowState(),
      atmospheric_pressure=atmospheric_pressure,
      rtol=rtol, atol=atol, max_iter=max_iter,
  )

  plume_index = zone1.plume_index + 1

  # Now the coordinates for Zone 1 & Zone 2 are known, (zone 3 is unknown at this point)
  point_A = zone1.coordinates.top_left_corner
  point_B = zone1.coordinates.bottom_left_corner
  height = zone1.coordinates.height
  point_C = point_B + RIGHT * (height * cos(zone2_os.shock_angle_deg))

  # Adjust zone1's coordinates because now right corner is known
  zone1 = zone1.replace(ZoneCoordinates(vstack([point_A, point_B, point_C])))

  # Now find intersection of slip line (point A downwards by θ) and
  # second oblique (from point C upwards by β2)
  # TODO[improvement]: can fail if high mach >8
  point_D = calcLineIntersection2d(
      line1_offset=point_A,
      line1_direction=asarray([cos(zone2_os.oblique_angle_rad), -sin(zone2_os.oblique_angle_rad), ]),
      line2_offset=point_C,
      line2_direction=asarray([cos(zone3_os.shock_angle_rad - zone3_os.oblique_angle_rad), sin(zone3_os.shock_angle_rad - zone3_os.oblique_angle_rad), ]),
  )
  point_E = point_C + ((point_D - point_C) @ RIGHT) * RIGHT

  zone2 = ZoneResult.fromObliqueShockState(
      zone2_os, label='Pressure Equalization Compression',
      coordinates=ZoneCoordinates(vstack([
          point_A,
          point_C,
          point_D,
      ])),
      plume_index=plume_index,
      group_number=ZoneResult.GROUP_NUMBER_START,
      group_index=ZoneResult.GROUP_INDEX_START,
  )

  zone3 = ZoneResult.fromObliqueShockState(
      zone3_os, label='Centerline Compression',
      coordinates=ZoneCoordinates(vstack([
          point_C,
          point_D,
          point_E,
      ])),
      plume_index=zone2.plume_index,
      group_number=zone2.group_number + 1,
      group_index=ZoneResult.GROUP_INDEX_START,
  )

  zones = [
      zone1,
      zone2,
      zone3,
  ]
  return zones
##


def calculateUnderExpandedPlumeZones(
        zone1: ZoneResult,
        atmospheric_pressure: float,
        num_expansion_lines: int,
        num_compression_lines: int,
        rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, max_iter: int = MAX_ITER_DEFAULT,
) -> Tuple[List[ZoneResult], Dict[str, Any]]:
  # Expansion fan to equalize pressure
  zone2_efs, zone3_efs, zone4_oss, zone5_oss = calculateUnderExpandedPlumeStates(
      zone1.asFlowState(),
      atmospheric_pressure=atmospheric_pressure,
      num_expansion_lines=num_expansion_lines,
      rtol=rtol, atol=atol, max_iter=max_iter,
      num_compression_lines=num_compression_lines,
  )

  plume_index = zone1.plume_index + 1
  point_A = zone1.coordinates.top_right_corner
  point_B = zone1.coordinates.bottom_right_corner
  height = zone1.coordinates.height
  zone2s = []
  cumulative_turn_rad = 0.
  for i, zone_ef in enumerate(zone2_efs):
    zone2s.append(ZoneResult.fromExpansionFan(
        label='Expansion Fan',
        plume_index=plume_index,
        group_number=ZoneResult.GROUP_NUMBER_START,
        group_index=i + ZoneResult.GROUP_INDEX_START,
        state=zone_ef,
        coordinates=ZoneCoordinates(vstack([
            point_A,
            point_B + RIGHT * (height / tan(zone_ef.upstream_mach_line_rad - cumulative_turn_rad)),
            point_B + RIGHT * (height / tan(zone_ef.mach_line_rad - zone_ef.turn_rad - cumulative_turn_rad)),
        ]))
    ))
    cumulative_turn_rad += zone_ef.turn_rad
  ##

  # Adjust Zone1 now that right point is known
  zone1 = zone1.replace(ZoneCoordinates(vstack([
      zone1.coordinates.top_left_corner,
      zone1.coordinates.bottom_left_corner,
      zone2s[0].coordinates.bottom_left_corner,
  ])))

  # zone2s[-1] coordinates are incomplete at this point
  expansion_slipline_offset = point_A  # the initial fan rotation/expansion point
  expansion_slipline_direction = asarray([cos(cumulative_turn_rad), sin(cumulative_turn_rad)])  # the outer edge slipline direction

  # points along the centerline
  expansion_centerline_points = [z.coordinates.bottom_left_corner for z in zone2s]
  # note:
  point_C = expansion_centerline_points[0]
  point_D = expansion_centerline_points[-1]
  initial_expansion_directions = [unitize(point - expansion_slipline_offset) for point in expansion_centerline_points]
  reflected_initial_expansion_directions = [M_reflect_up @ direction for direction in initial_expansion_directions]
  direction_D_towards_G = reflected_initial_expansion_directions[-1]

  reflected_lower_intersection_points = [
      calcLineIntersection2d(
          line1_offset=expansion_slipline_offset,
          line1_direction=initial_expansion_directions[-1],
          line2_offset=offset,
          line2_direction=direction,
      ) for offset, direction in zip(expansion_centerline_points[:-1], reflected_initial_expansion_directions[:-1])
  ]
  # Last point should be exactly on centerline
  reflected_lower_intersection_points.append(expansion_centerline_points[-1])  # point_D

  # Note:
  point_E = reflected_lower_intersection_points[0]
  # Now calculate last fan - the pressure equalization fan - points
  last_initial_fan_bottom_point = reflected_lower_intersection_points[0]
  last_initial_fan_top_right_point = calcLineIntersection2d(
      line1_offset=expansion_slipline_offset,
      line1_direction=expansion_slipline_direction,
      line2_offset=reflected_lower_intersection_points[0],
      line2_direction=reflected_initial_expansion_directions[0],
  )  # point_F
  point_F = last_initial_fan_top_right_point

  zone2s[-1] = zone2s[-1].replace(ZoneCoordinates(vstack([
      expansion_slipline_offset,
      last_initial_fan_bottom_point,
      last_initial_fan_top_right_point,
  ])))  # the pressure eq fan - last initial fan

  # The last initial fan point should be symmetric with last fan reflected direction
  # across the plume shape at large
  # So calculate intersection of the horizontal from the last initial fan top right
  # and the last reflected fan line from the centerline
  point_G = calcLineIntersection2d(
      line1_offset=point_F,
      line1_direction=RIGHT,
      line2_offset=point_D,
      line2_direction=direction_D_towards_G,
  )

  # TODO[plume,improvement] - this is a hack - don't know of a better way right now.
  # Then the three points, A,F,G are fit to a parabola to determine upper slip line for second reflection
  parabola_fit = fitParabolaFromPoints2d([point_A, point_F, point_G])

  # TODO[improvement]: note this fails in the case of very high pressure.
  # TODO[improvement]: this fails if mach low <1.5
  reflection_slip_intersection_points = [calcLineParabolaIntersection2d(
      line_offset=point, line_direction=direction,
      parabola_coeff=parabola_fit,
  ) for point, direction in zip(reflected_lower_intersection_points, reflected_initial_expansion_directions)]

  zone3_group_number = zone2s[-1].group_number + 1
  zone3s = []
  for i, zone_ef in enumerate(zone3_efs):
    points = [
        reflection_slip_intersection_points[i],  # top-left
        reflected_lower_intersection_points[i],  # bottom-left
    ]
    if i + 1 < len(zone3_efs):
      points.append(reflected_lower_intersection_points[i + 1])  # bottom-right
      points.append(reflection_slip_intersection_points[i + 1])  # top-right
    else:
      # TODO[plume] not great, because last region is incomplete
      points.append((reflection_slip_intersection_points[i] @ RIGHT) * RIGHT)
    ##

    zone3s.append(ZoneResult.fromExpansionFan(
        state=zone_ef,
        label='Reflected Expansion Fan',
        plume_index=plume_index,
        group_number=zone3_group_number,
        group_index=i + ZoneResult.GROUP_INDEX_START,
        coordinates=ZoneCoordinates(vstack(points)),
    ))
  ##

  # TODO[improvement]: Can fail  in the case of low mach <1.1
  point_H = calcLineIntersection2d(
      line1_offset=point_B,
      line1_direction=RIGHT,
      line2_offset=point_G,
      line2_direction=asarray([cos(zone4_oss[0].shock_angle_rad), -sin(zone4_oss[0].shock_angle_rad)]),
  )

  point_I = calcLineIntersection2d(
      line1_offset=point_A,
      line1_direction=RIGHT,
      line2_offset=point_G,
      line2_direction=asarray([cos(zone4_oss[0].oblique_angle_rad), -sin(zone4_oss[0].oblique_angle_rad)]),
  )

  os5_phi = zone5_oss[0].shock_angle_rad - zone5_oss[0].oblique_angle_rad
  point_J = calcLineIntersection2d(
      line1_offset=point_B,
      line1_direction=RIGHT,
      line2_offset=point_I,
      line2_direction=asarray([-cos(os5_phi), -sin(os5_phi)]),
  )

  point_K = point_J + ((point_I - point_J) @ RIGHT) * RIGHT
  # point_J2 = calcLineIntersection2d(
  #   line1_offset=point_G,
  #   line1_direction=asarray([cos(zone4_os.oblique_angle_rad), -sin(zone4_os.oblique_angle_rad)]),
  #   line2_offset=point_I,
  #   line2_direction=asarray([cos(os5_phi), sin(os5_phi)]),
  # )

  # Adjust last zone3 fan
  zone3s[-1] = zone3s[-1].replace(ZoneCoordinates(vstack([
      point_D,
      point_G,
      point_H,
  ])))

  zone4s = []
  zone4_group_number = zone3s[-1].group_number + 1
  for i, zone4_os in enumerate(zone4_oss):
    if i + 1 == len(zone4_oss):
      label = 'Pressure Equalization Compression'
      coordinates = ZoneCoordinates(vstack([
          point_G,
          point_H,
          point_J,
          point_I,
      ]))
    else:
      label = 'Reflected Expansion Compression'
      coordinates = ZoneCoordinates(full((3, 2), nan))
    ##
    zone4s.append(ZoneResult.fromObliqueShockState(
        state=zone4_os,
        label=label,
        plume_index=plume_index,
        group_number=zone4_group_number,
        group_index=i + ZoneResult.GROUP_INDEX_START,
        coordinates=coordinates,
    ))
  ##

  zone5_group_number = zone4s[-1].group_number + 1
  zone5s = []
  for i, zone5_os in enumerate(zone5_oss):
    if i + 1 == len(zone5_oss):
      label = 'Centerline Compression Exit'
      coordinates = ZoneCoordinates(vstack([
          point_I,
          point_J,
          point_K,
      ]))
    else:
      label = 'Centerline Compression'
      coordinates = ZoneCoordinates(full((3, 2), nan))
    ##
    zone5s.append(ZoneResult.fromObliqueShockState(
        state=zone5_os,
        label=label,
        plume_index=plume_index,
        group_number=zone5_group_number,
        group_index=i + ZoneResult.GROUP_INDEX_START,
        coordinates=coordinates,
    ))
  ##

  zones = [
      zone1,
      *zone2s,
      *zone3s,
      *zone4s,
      *zone5s,
  ]

  extra = {
      'points': {
          'A': point_A,
          'B': point_B,
          'C': point_C,
          'D': point_D,
          'E': point_E,
          'F': point_F,
          'G': point_G,
          'H': point_H,
          'I': point_I,
          'J': point_J,
          'K': point_K,
      },
      'plume_fit': parabola_fit,
  }

  out = (zones, extra,)
  return out
##


def calcNozzleExitFlowState(mach: float,
                            total_temperature: float,
                            total_pressure: float,
                            gamma: float,
                            ) -> FlowState:
  """Calculate the static state at a nozzle exit from total conditions."""
  _validate_positive_finite('mach', mach)
  _validate_positive_finite('total_temperature', total_temperature)
  _validate_positive_finite('total_pressure', total_pressure)
  _validate_gamma(gamma)
  total_density = calcDensityFromSpecificVolume(
      specific_volume_m3pkg=calcIdealGasSpecificVolumeFromPressureSpecificWork(
          pressure_Pa=total_pressure,
          specific_work_Jpkg=calcIdealGasSpecificWorkFromMolarMassTemperature(
              molar_mass_kg=MOLAR_MASS_DRY_AIR_kg,
              temperature_K=total_temperature,
          )
      )
  )
  static_pressure = calcIsentropicStaticPressure(mach=mach, total_pressure=total_pressure, gamma=gamma)
  static_temperature = calcIsentropicStaticTemperature(mach=mach, total_temperature=total_temperature, gamma=gamma)
  static_density = calcIsentropicStaticDensity(mach=mach, total_density=total_density, gamma=gamma)
  state = FlowState(
      mach=mach,
      static_pressure=static_pressure,
      static_temperature=static_temperature,
      static_density=static_density,
      gamma=gamma,
  )
  return state
##


def calculatePlumeZones(nozzle_mach: float,
                        nozzle_total_temperature: float,
                        nozzle_total_pressure: float,
                        nozzle_radius: float,
                        atmospheric_pressure: float,
                        gamma: float,
                        num_expansion_lines: int,
                        num_compression_lines: int,
                        num_plumes: int,
                        ) -> Tuple[List[ZoneResult], Dict[str, Any]]:
  """Calculate plume zones and construction details for one or more plumes.

  The current geometry construction requires a supersonic nozzle, at least two
  expansion lines, and at least one compression line.
  """
  _validate_positive_finite('nozzle_mach', nozzle_mach)
  if float(nozzle_mach) <= 1.:
    raise ValueError(f'Expected `nozzle_mach` to be greater than 1. Got:{nozzle_mach}')
  _validate_positive_finite('nozzle_total_temperature', nozzle_total_temperature)
  _validate_positive_finite('nozzle_total_pressure', nozzle_total_pressure)
  _validate_positive_finite('nozzle_radius', nozzle_radius)
  _validate_positive_finite('atmospheric_pressure', atmospheric_pressure)
  _validate_gamma(gamma)
  _validate_count('num_expansion_lines', num_expansion_lines, minimum=2)
  _validate_count('num_compression_lines', num_compression_lines, minimum=1)
  _validate_count('num_plumes', num_plumes, minimum=1)
  zones = [
      # Initial zone is isentropic nozzle expansion
      ZoneResult.fromFlowState(
          state=calcNozzleExitFlowState(
              mach=nozzle_mach,
              total_pressure=nozzle_total_pressure,
              total_temperature=nozzle_total_temperature,
              gamma=gamma,
          ),
          beta=nan,
          theta=nan,
          label='Nozzle Exit',
          coordinates=ZoneCoordinates(vstack([
              0. * RIGHT,
              0. * RIGHT,
              nozzle_radius * UP,
          ])),
          plume_index=ZoneResult.PLUME_INDEX_START_NUMBER,
          group_number=ZoneResult.GROUP_NUMBER_START,
          group_index=ZoneResult.GROUP_INDEX_START,
      )
  ]
  if zones[-1].static_pressure <= atmospheric_pressure:
    over_expanded_precursor_zones = calculateOverExpandedPrecursorZones(
        zone1=zones.pop(),
        atmospheric_pressure=atmospheric_pressure,
    )
    zones.extend(over_expanded_precursor_zones)
  ##
  extra: Dict[str, Any] = {}
  for plume_index in range(num_plumes):
    under_exp_zones, extra = calculateUnderExpandedPlumeZones(
        zone1=zones.pop(),
        atmospheric_pressure=atmospheric_pressure,
        num_compression_lines=num_compression_lines,
        num_expansion_lines=num_expansion_lines,
    )
    zones.extend(under_exp_zones)
  ##

  out = (zones, extra)
  return out
##
