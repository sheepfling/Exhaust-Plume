# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from dataclasses import dataclass
from pprint import pformat
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from numpy import arctan2, deg2rad, eye, ndarray, pi, rad2deg, sqrt
from scipy.spatial.transform import Rotation

from exhaust_plume.earth.earth_model import EarthModel
from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import AggregateFieldMetadata, CallerIds, Degree, FloatFieldMetadata, RepeatedFieldMetadata, SettingsInterface, SwitchFieldMetadata
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.dataclass_util import dataclassIsClose, dataclassIsEqual, dataclassRepr
from exhaust_plume.util.misc import popOrNone
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT
from exhaust_plume.util.position import PositionECEF, PositionLLA, position_robust_metadata, robustPositionEcefFromConfig

__all__ = (
    'OrientationLTP',
    'OrientationOffset',
    ####
    'robustOrientationOffsetFromConfig',
)
#####################
log = getCleanLogger(__name__)


@dataclass(frozen=True)
class OrientationLTP(SettingsInterface):
  """ Defines a pointing vector relative to a LTP defined by the position.
  The elevation is the angle from the horizon to where the nose points.
  The azimuth is the amount of rotation from +North -> +East (+curl about +Down) where the nose points.

  The body frame is defined as NSD - Nose, Starboard, Down
  The world frame is defined as XYZ - the ECEF standard
  """
  roll: float  # radians - Positive Curl about +North/Nose in LTP defined by position
  elevation: float  # radians - Positive Curl about +East in LTP defined by position
  azimuth: float  # radians - Positive Curl about +Down in LTP defined by position
  position: PositionECEF

  def __post_init__(self) -> None:
    # DOCME
    if not isinstance(self.position, PositionECEF):
      raise ValueError(f'Position is unexpected type:{type(self.position).__name__}. Expected {PositionECEF.__name__}')
    ##
  ##

  @cached_property
  def roll_deg(self) -> float:
    # DOCME
    return float(rad2deg(self.roll))
  ##

  @cached_property
  def elevation_deg(self) -> float:
    # DOCME
    return float(rad2deg(self.elevation))
  ##

  @cached_property
  def azimuth_deg(self) -> float:
    # DOCME
    return float(rad2deg(self.azimuth))
  ##

  @property
  def pitch(self) -> float:
    # DOCME
    # Pitch and Elevation are synonymous
    return self.elevation
  ##

  @property
  def pitch_deg(self) -> float:
    # DOCME
    # Pitch and Elevation are synonymous
    return self.elevation_deg
  ##

  @property
  def yaw(self) -> float:
    # DOCME
    # Yaw and Azimuth are synonymous
    return self.azimuth
  ##

  @property
  def yaw_deg(self) -> float:
    # DOCME
    # Yaw and Azimuth are synonymous
    return self.azimuth_deg
  ##

  @cached_property
  def rotation_ned_from_body(self) -> Rotation:
    # DOCME
    # (About body axes NSD - Nose, Starboard, Down)
    # Apply Roll Transformation +N, then
    # Apply Pitch/Elevation Transformation +S, then
    # Apply Yaw/Azimuth Transformation +D, then
    # (current frame is NED frame)
    nose, starboard, down = eye(3)
    roll_rot = Rotation.from_rotvec(self.roll * nose)  # Body->NED
    pitch = Rotation.from_rotvec(self.elevation * starboard)  # Body->NED
    yaw = Rotation.from_rotvec(self.azimuth * down)  # Body->NED
    ned_from_body = yaw * (pitch * roll_rot)
    return ned_from_body
  ##

  def getNedFromBody(self) -> Rotation:
    return self.rotation_ned_from_body
  ##

  @cached_property
  def rotation_body_from_ned(self) -> Rotation:
    # DOCME
    return self.rotation_ned_from_body.inv()
  ##

  def getBodyFromNed(self) -> Rotation:
    # DOCME
    return self.rotation_body_from_ned
  ##

  @cached_property
  def rotation_ecef_from_ned(self) -> Rotation:
    # DOCME
    X, Y, Z = eye(3)
    # Apply -90 about +Y=+Starboard to change axes from NED->ECEF
    frame_change = Rotation.from_rotvec(-pi / 2. * Y)  # NED->ECEF

    # Apply -latitude about +Y
    # Apply +longitude about +Z
    lla: PositionLLA = self.position.asLLA()
    lat_rot = Rotation.from_rotvec(-lla.latitude_rad * Y)
    lon_rot = Rotation.from_rotvec(lla.longitude_rad * Z)

    ecef_from_ned = lon_rot * (lat_rot * frame_change)
    return ecef_from_ned
  ##

  def getEcefFromNed(self) -> Rotation:
    return self.rotation_ecef_from_ned
  ##

  @cached_property
  def rotation_ned_from_ecef(self) -> Rotation:
    # DOCME
    return self.rotation_ecef_from_ned.inv()
  ##

  def getNedFromEcef(self) -> Rotation:
    # DOCME
    return self.rotation_ned_from_ecef
  ##

  @cached_property
  def rotation_ecef_from_body(self) -> Rotation:
    # DOCME
    return self.rotation_ecef_from_ned * self.rotation_ned_from_body
  ##

  def getEcefFromBody(self) -> Rotation:
    # DOCME
    return self.rotation_ecef_from_body
  ##

  def getEcefOrientationOffset(self) -> OrientationOffset:
    """ Calculates orientation offset from ECEF frame (vs NED frame) """
    # offset=body; base=ecef/world
    ori_offset = OrientationOffset.fromOffsetFromBaseRotation(self.getBodyFromEcef())
    return ori_offset
  ##

  @cached_property
  def rotation_body_from_ecef(self) -> Rotation:
    # DOCME
    return self.rotation_ecef_from_body.inv()
  ##

  def getBodyFromEcef(self) -> Rotation:
    # DOCME
    return self.rotation_body_from_ecef
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:  # DOCME
    out = dataclassIsClose(self, other, rtol=rtol, atol=atol, equal_nan=equal_nan)
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """
    :return: settings as config dictionary
    """
    out = {
        'roll_deg': self.roll_deg,
        'elevation_deg': self.elevation_deg,
        'azimuth_deg': self.azimuth_deg,
        'position': self.position.asConfig(caller_ids),
    }
    return out
  ##

  def replace(self, *,
              roll: Optional[float] = None,
              elevation: Optional[float] = None,
              azimuth: Optional[float] = None,
              position: Optional[PositionECEF] = None,
              ) -> OrientationLTP:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param roll: value to be replaced if not None
    @param elevation: value to be replaced if not None
    @param azimuth: value to be replaced if not None
    @param position: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = OrientationLTP(
        roll=self.roll if roll is None else roll,
        elevation=self.elevation if elevation is None else elevation,
        azimuth=self.azimuth if azimuth is None else azimuth,
        position=self.position if position is None else position,
    )
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Orientation LTP',
        description="""Defines an orientation relative to the Local-Tangent-Plane (LTP) defined by the position.""",
        optional=False,
        fields={
            'azimuth_deg': FloatFieldMetadata.createFinite(
                label='Yaw',
                description='Positive Curl about +Down (Z)',
                optional=False,
                default=0.,
                units=Degree,
            ),
            'elevation_deg': FloatFieldMetadata.createFinite(
                label='Pitch',
                description='Positive Curl about East',
                optional=False,
                default=0.,
                units=Degree,
            ),
            'roll_deg': FloatFieldMetadata.createFinite(
                label='Roll',
                description='Positive Curl about North',
                optional=True,
                default=0.,
                units=Degree,
            ),
            'position': position_robust_metadata.replace(
                label='Reference Position',
                optional=True,
            ),
        }
    )
    return out
  ##

  @classmethod
  def fromConfig(
      cls,
      config: Mapping[str, Any],
      debug_config_prefix: str = '',
      position: Optional[PositionECEF] = None,
      earth_model: EarthModel = EarthModel.WGS84,
  ) -> OrientationLTP:
    """ Loads settings from config dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :param position: reference position for LTP if unspecified in the config dictionary
    :param earth_model: only used if position specified in-config is not explicitly ECEF (e.g. LLA or NED)
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    if position is None:
      position_config = popOrNone(config, 'position')
      if position_config is None:
        raise ValueError(f'{debug_config_prefix}: If `position` argument is not supplied, then `position` must be supplied in the config.')
      ##
      try:
        position = robustPositionEcefFromConfig(
            position_config,
            debug_config_prefix=f'{debug_config_prefix}.position',
            earth_model=earth_model,
        )
      except Exception as e:
        raise ValueError(f'{debug_config_prefix}: If position is not specified as a parameter, then it must be in the configuration.') from e
      ##
    ##
    if position is None:
      raise ValueError(f'{debug_config_prefix}: Either position needs to be in the config or needs to be passed in as a parameter.')
    ##
    roll = _getAngleFromConfig(config, 'roll')
    if roll is None:
      # Roll is default 0.
      roll = 0.
    ##
    elevation = _getAngleFromConfig(config, 'elevation')
    if elevation is None:
      elevation = _getAngleFromConfig(config, 'pitch')
    ##
    azimuth = _getAngleFromConfig(config, 'azimuth')
    if azimuth is None:
      azimuth = _getAngleFromConfig(config, 'yaw')
    ##
    if (elevation is None) or (azimuth is None):
      raise ValueError(f'{debug_config_prefix}: Orientation angles must be specified. Elevation or Azimuth is unspecified. Specify (regex notation) (roll)?, (azimuth|yaw)(_rad|_deg)?, and (elevation|pitch)(_rad|_deg)?')
    ##
    out = OrientationLTP(
        roll=roll,
        elevation=elevation,
        azimuth=azimuth,
        position=position
    )
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

##


@dataclass(frozen=True)
class OrientationOffset(SettingsInterface):
  """ Orientation Offset from base/inertial in Nose-Starboard-Down (NSD). """

  roll: float  # radians - Positive Curl about +Nose (1)
  pitch: float  # radians - Positive Curl about +Starboard (2)
  yaw: float  # radians - Positive Curl about +Down (3)

  @cached_property
  def roll_deg(self) -> float:
    # DOCME
    return float(rad2deg(self.roll))
  ##

  @cached_property
  def pitch_deg(self) -> float:
    # DOCME
    return float(rad2deg(self.pitch))
  ##

  @cached_property
  def yaw_deg(self) -> float:
    # DOCME
    return float(rad2deg(self.yaw))
  ##

  @cached_property
  def rotation_base_from_offset(self) -> Rotation:
    """ Returns the rotation that rotates offset (body) values to base (world) values, that is base from offset """
    # (About base axes NSD - Nose, Starboard, Down)
    # Apply Roll Transformation +N, then
    # Apply Pitch Transformation +S, then
    # Apply Yaw Transformation +D, then
    # (current frame is Base/NSD frame)
    nose, starboard, down = eye(3)
    roll_rot = Rotation.from_rotvec(self.roll * nose)  # Base->NED
    pitch = Rotation.from_rotvec(self.pitch * starboard)  # Base->NED
    yaw = Rotation.from_rotvec(self.yaw * down)  # Base->NED
    base_from_offset = yaw * (pitch * roll_rot)
    return base_from_offset
  ##

  def getBaseFromOffset(self) -> Rotation:
    """ Returns the rotation that rotates base/world values from offset/body coordinates. """
    return self.rotation_base_from_offset
  ##

  @cached_property
  def rotation_offset_from_base(self) -> Rotation:
    return self.rotation_base_from_offset.inv()
  ##

  def getOffsetFromBase(self) -> Rotation:
    """ Returns the rotation that rotates offset/body values from base/world coordinates. """
    return self.rotation_offset_from_base
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:  # DOCME
    out = dataclassIsClose(self, other, rtol=rtol, atol=atol, equal_nan=equal_nan)
    return out
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """
    :return: settings as config dictionary
    """
    out = {
        'roll_deg': self.roll_deg,
        'pitch_deg': self.pitch_deg,
        'yaw_deg': self.yaw_deg,
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Orientation Offset',
        description="""Orientation Offset from base/inertial in Nose-Starboard-Down (NSD).""",
        optional=False,
        fields={
            'yaw_deg': FloatFieldMetadata.createFinite(
                label='Yaw',
                description='Positive Curl about +Down (Z)',
                optional=False,
                default=0.,
                units=Degree,
            ),
            'pitch_deg': FloatFieldMetadata.createFinite(
                label='Pitch',
                description='Positive Curl about +Starboard (Y)',
                optional=False,
                default=0.,
                units=Degree,
            ),
            'roll_deg': FloatFieldMetadata.createFinite(
                label='Roll',
                description='Positive Curl about +Nose (X)',
                optional=True,
                default=0.,
                units=Degree,
            ),
        }
    )
    return out
  ##

  def replace(self, *,
              roll: Optional[float] = None,
              pitch: Optional[float] = None,
              yaw: Optional[float] = None,
              ) -> OrientationOffset:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param roll: value to be replaced if not None
    @param pitch: value to be replaced if not None
    @param yaw: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = OrientationOffset(
        roll=self.roll if roll is None else roll,
        pitch=self.pitch if pitch is None else pitch,
        yaw=self.yaw if yaw is None else yaw,
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> OrientationOffset:
    """ Loads settings from config dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    roll = _getAngleFromConfig(config, 'roll')
    if roll is None:
      roll = 0.
      log.log(CONFIG, f'{debug_config_prefix}: `roll` was unspecified. Defaulting to {roll}.')
    ##
    pitch = _getAngleFromConfig(config, 'pitch')
    if pitch is None:
      raise ValueError(f'{debug_config_prefix}: Expected `pitch` to be specified. Got:{config}')
    ##
    yaw = _getAngleFromConfig(config, 'yaw')
    if yaw is None:
      raise ValueError(f'{debug_config_prefix}: Expected `yaw` to be specified. Got:{config}')
    ##
    out = OrientationOffset(
        roll=roll,
        pitch=pitch,
        yaw=yaw
    )
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  @classmethod
  def fromBaseFromOffsetMatrix(cls, base_from_offset: ndarray) -> OrientationOffset:
    """ Determines Yaw, Pitch, Roll from the given matrix

    These equations were derived from the following snippet and also from the links given:
    # https://web.archive.org/web/20220315223538/https://planning.cs.uiuc.edu/node103.html
    # https://archive.ph/mUxFc
    ```
    from sympy import Matrix, atan, atan2, cos, eye, sin, symbols, trigsimp
    y,p,r = symbols('y p r')

    def getRotationMatrix(ax1,ax2,sym):
      # extrinsic rotation
      M = eye(3)
      M[ax1,ax1]=cos(sym)
      M[ax2,ax2]=cos(sym)
      M[ax1,ax2]=-sin(sym)
      M[ax2,ax1]=+sin(sym)
      return M
    ##

    # NSD
    # Yaw = N->S
    Yaw = getRotationMatrix(0,1,y)
    # Pitch = D->N
    Pitch = getRotationMatrix(2,0,p)
    # Roll = S->D
    Roll = getRotationMatrix(1,2,r)

    nsd_from_body = Yaw @ Pitch @ Roll
    matrix = nsd_from_body

    yaw_atan2=trigsimp(atan2(matrix[1, 0], matrix[0, 0]))
    yaw_atan =trigsimp(atan(matrix[1, 0] / matrix[0, 0]))
    pitch_atan2 = trigsimp(atan2(-matrix[2, 0], sqrt(matrix[2, 1]**2 + matrix[2, 2]**2)))
    pitch_atan = trigsimp(atan(-matrix[2, 0] / sqrt(matrix[2, 1]**2 + matrix[2, 2]**2)))
    roll_atan2 = trigsimp(atan2(matrix[2, 1], matrix[2, 2]))
    roll_atan = trigsimp(atan(matrix[2, 1]/ matrix[2, 2]))
    ```
    """
    matrix = base_from_offset
    out = OrientationOffset(
        yaw=arctan2(matrix[1, 0], matrix[0, 0]),
        pitch=arctan2(-matrix[2, 0], sqrt(matrix[2, 1]**2 + matrix[2, 2]**2)),
        roll=arctan2(matrix[2, 1], matrix[2, 2]),
    )
    return out
  ##

  @classmethod
  def fromOffsetFromBaseMatrix(cls, offset_from_base: ndarray) -> OrientationOffset:
    # DOCME
    base_from_offset = offset_from_base.T
    return cls.fromBaseFromOffsetMatrix(base_from_offset=base_from_offset)
  ##

  @classmethod
  def fromBaseFromOffsetRotation(cls, base_from_offset: Rotation) -> OrientationOffset:
    # DOCME
    return cls.fromBaseFromOffsetMatrix(base_from_offset=base_from_offset.as_matrix())
  ##

  @classmethod
  def fromOffsetFromBaseRotation(cls, offset_from_base: Rotation) -> OrientationOffset:
    # DOCME
    base_from_offset = offset_from_base.inv()
    return cls.fromBaseFromOffsetMatrix(base_from_offset=base_from_offset.as_matrix())
  ##
##


def _getAngleFromConfig(config: Dict[str, Any], name: str) -> Optional[float]:
  """ Gets angle in radians. Mutates the config dict """
  angle = None
  if angle is not None:
    angle = float(config.pop(name))
  ##
  if angle is None and f'{name}_rad' in config:
    angle = float(config.pop(f'{name}_rad'))
  ##
  if angle is None and f'{name}_rad' in config:
    angle = float(config.pop(f'{name}_rad'))
  ##
  if angle is None and f'{name}_deg' in config:
    angle = float(deg2rad(float(config.pop(f'{name}_deg'))))
  ##
  return angle
##


quaternion_metadata = RepeatedFieldMetadata.createFixedRepeat(
    count=4,
    label='Quaternion XYZW',
    description='Quaternion components - Scalar last convention',
    optional=False,
    value=FloatFieldMetadata.createFinite(
        label='Component XYZW',
        description='Quaternion components - Scalar last convention',
        optional=False,
        default=None,
        units=None,
    )
)

orientation_offset_robust_metadata = SwitchFieldMetadata(
    label='Orientation',
    description='Orientation',
    optional=False,
    default=None,
    switch_key=None,  # UNTAGGED
    switch_key_is_intrusive=False,
    switch_label='Constructor Type',
    switch_description=None,
    choice2value={
        'ypr': OrientationOffset.getConfigMetadata(),  # default to YPR first
        'quaternion': quaternion_metadata,
        'ltp': OrientationLTP.getConfigMetadata(),
    },
)


def robustOrientationOffsetFromConfig(
    config: Union[Mapping[str, Any], ndarray, Sequence[float]],
    reference_position: Optional[PositionECEF] = None,
    earth_model: EarthModel = EarthModel.WGS84,
    debug_config_prefix: str = '',
) -> OrientationOffset:
  try:
    return OrientationOffset.fromBaseFromOffsetRotation(Rotation.from_quat(config))  # type: ignore[arg-type]
  except (ValueError, TypeError,):
    pass
  ##
  try:
    return OrientationOffset.fromConfig(config, debug_config_prefix=debug_config_prefix)  # type: ignore[arg-type]
  except (ValueError, TypeError, AttributeError,):
    pass
  ##
  try:
    ori_ltp = OrientationLTP.fromConfig(
        config,  # type: ignore[arg-type]
        position=reference_position,
        earth_model=earth_model,
        debug_config_prefix=debug_config_prefix,
    )
    return OrientationOffset.fromBaseFromOffsetRotation(ori_ltp.getEcefFromBody())
  except (ValueError, TypeError, AttributeError,):
    pass
  ##
  raise ValueError(
      f'{debug_config_prefix}: Unable to robustly determine orientation from config.'
      f' It is not a Quaternion (XYZW), {OrientationOffset.__name__}, nor {OrientationLTP.__name__} config.'
      f' Got:{config!r}'
  )
##
