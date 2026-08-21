# -*- coding: utf-8 -*-
""" This module contains the definitions of the message types that will be sent during the simulation, and their expected channels """
from __future__ import annotations

from collections.abc import Hashable as AbcHashable
from enum import Enum
from functools import total_ordering
from math import nan
from pprint import pformat
from typing import Any, ClassVar, Dict, Mapping, Optional, Union

from numpy import allclose, arcsin, arctan2, array, asarray, eye, full_like, isclose, isfinite, isnan, ndarray, rad2deg, trace, zeros
from numpy.linalg import norm
from scipy.spatial.transform import Rotation

from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import AggregateFieldMetadata, CallerIds, ChoiceFieldMetadata, FloatFieldMetadata, Meter, Radian, RepeatedFieldMetadata, Second, SettingsInterface
from exhaust_plume.track_filters.states import EcefStateCovariance_PVA, EcefState_PVA
from exhaust_plume.uid import EmissionId, EmissionReturnUid, EmissionUid, GroupId, TrackId, TrackUid, Uid
from exhaust_plume.util.bounded_numeric import PositiveFiniteFloat
from exhaust_plume.util.enum_util import normalizeEnumNameForMapping
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, makeReadOnly
from exhaust_plume.util.physical_constants import SPEED_OF_LIGHT
from exhaust_plume.util.type_hints import TypeAlias

__all__ = (
    'DEFAULT_ACCELERATION', 'DEFAULT_ANGULAR_VELOCITY', 'DEFAULT_DIRECTION', 'DEFAULT_ORIENTATION', 'DEFAULT_POLARIZATION',
    'DEFAULT_POSITION', 'DEFAULT_POSITION_VELOCITY_ACCELERATION_COVARIANCE', 'DEFAULT_VELOCITY',
    'DESTRUCTION_PLATFORM_MESSAGE',
    'DROP_TRACK_MESSAGE',
    'AccelerationType', 'AngularVelocityType', 'AreaType',
    'DirectionType', 'DistanceType', 'Emission', 'EmissionReturn',
    'FrequencyType', 'OrientationType', 'PlatformState', 'PolarizationStandard',
    'PolarizationType', 'PositionType',
    'PowerType', 'RadianType', 'RangeRateType', 'RangeType',
    'RcsLogMessage', 'RcsMagnitudeType', 'RcsQuery', 'RcsResponse',
    'TimeType', 'TrackData', 'UnitlessType', 'VelocityType', 'WavelengthType',
)
########################
log = getCleanLogger(__name__)

AngularVelocityType = ndarray  # ECEF xyz, rad /second
FrequencyType: TypeAlias = PositiveFiniteFloat  # Hz
DirectionType = ndarray  # ECEF xyz, unitless unitvector
AreaType = float
DistanceType = float
OrientationType = ndarray  # quaternion
PolarizationType = ndarray  # size 2, unitless unitvector, complex; see polarization_note in polarization.py

PositionType = ndarray  # ECEF xyz , meters
VelocityType = ndarray  # ECEF xyz, meter / second
AccelerationType = ndarray  # ECEF xyz, meter / second^2
# PositionVelocityAccelerationState = ndarray  # (9,)
# EcefStateCovariance_PVA = ndarray  # (9,9,)
PowerType = float  # Watts
RadianType = float  # radians
RangeType = float
RangeRateType = float
RcsMagnitudeType = float  # meters squared, non-negative real
TimeType = float
UnitlessType = float
WavelengthType: TypeAlias = PositiveFiniteFloat

DEFAULT_ORIENTATION: OrientationType = makeReadOnly(array([0., 0., 0., 1., ], dtype='float'))  # body to Ecef rotation (x,y,z,W) - W is scalar, scipy convention
DEFAULT_ANGULAR_VELOCITY: AngularVelocityType = makeReadOnly(zeros((3,), dtype='float'))
DEFAULT_DIRECTION: DirectionType = makeReadOnly(array([1., 0., 0., ], dtype='float'))

DEFAULT_POSITION: PositionType = makeReadOnly(zeros((3,), dtype='float'))
DEFAULT_VELOCITY: PositionType = makeReadOnly(zeros((3,), dtype='float'))
DEFAULT_ACCELERATION: PositionType = makeReadOnly(zeros((3,), dtype='float'))
DEFAULT_POSITION_VELOCITY_ACCELERATION_COVARIANCE = EcefStateCovariance_PVA(makeReadOnly(zeros((9, 9,), dtype='float')))


@total_ordering
class PolarizationStandard(Enum):
  """Commonly used Polarization values. It should be noted that any size 2, complex unitvector is a valid polarization.
  """
  # In order to be an enum these values must be immutable (therefore they are tuples. Convert to numpy arrays before use as PolarizationType's)
  str2enum: ClassVar[Mapping[str, PolarizationStandard]]
  Horizontal = (complex(1., 0.), complex(0., 0.),)
  Vertical = (complex(0., 0.), complex(1., 0.),)
  RightHandCircular = (complex(1., 0.) / 2**.5, complex(0., -1.) / 2**.5,)
  LeftHandCircular = (complex(1., 0.) / 2**.5, complex(0, +1.) / 2**.5,)
  Default = RightHandCircular

  def asarray(self) -> PolarizationType:
    return asarray(self.value, dtype='complex')
  ##

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return (self.value[0].real, self.value[0].imag, self.value[1].real, self.value[1].imag,) < \
          (other.value[0].real, other.value[0].imag, other.value[1].real, other.value[1].imag,)
    ##
    return NotImplemented
  ##

  @classmethod
  def getConfigMetadata(cls) -> ChoiceFieldMetadata:
    out = ChoiceFieldMetadata(
        label='Polarization Standard',
        description='Choices of standard polarization values.',
        default=None,
        optional=False,
        choice2label={normalizeEnumNameForMapping(e.name): e.value for e in cls},
    )
    return out
  ##

  @classmethod
  def fromString(cls, value: str) -> PolarizationStandard:
    try:
      return cls.str2enum[normalizeEnumNameForMapping(value)]  # type: ignore[index,attr-defined]
    except KeyError as e:
      raise ValueError(f'Unknown {cls.__name__} value:{value}. Valid options are:{list(cls.str2enum.keys())}') from e  # type: ignore[index,attr-defined]
    ##
  ##

##


DEFAULT_POLARIZATION: PolarizationType = makeReadOnly(PolarizationStandard.RightHandCircular.asarray())
PolarizationStandard.str2enum = {normalizeEnumNameForMapping(e.name): e for e in PolarizationStandard}
#################################


class PlatformState(AbcHashable, SettingsInterface):
  """ Data structure representing a platform/object's state in ECEF coordinates
  orientation: ECEF from body (body to world rotation) [x,y,z,W] that is vec_ecef = q_orientation * vec_body * inv(q_orientation)
  angular_velocity: world frame coordinates of omega
  """
  __slots__ = (
      '__uid', '__timestamp', '__position', '__velocity', '__acceleration', '__orientation', '__angular_velocity',
      '__cache_hash', '__cache_state', '__cache_rotation_ecef_from_body', '__cache_rotation_body_from_ecef', '__cache_is_destroyed',
      '__cache_repr',
  )
  public_channel: ClassVar[str]
  destroyed_state: ClassVar[PlatformState]

  def __init__(
      self, *,
      uid: Uid,
      timestamp: TimeType,
      position: PositionType,
      velocity: VelocityType,
      acceleration: AccelerationType,
      orientation: OrientationType,
      angular_velocity: AngularVelocityType,
  ):
    super().__init__()
    self.__uid = uid
    self.__timestamp = float(timestamp)
    self.__position = makeReadOnly(asarray(position, 'float'))
    self.__velocity = makeReadOnly(asarray(velocity, 'float'))
    self.__acceleration = makeReadOnly(asarray(acceleration, 'float'))
    self.__orientation = makeReadOnly(asarray(orientation, 'float'))
    self.__angular_velocity = makeReadOnly(asarray(angular_velocity, 'float'))
    self.__cache_state: Optional[EcefState_PVA] = None
    self.__cache_rotation_ecef_from_body: Optional[Rotation] = None
    self.__cache_rotation_body_from_ecef: Optional[Rotation] = None
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    self.__cache_is_destroyed: bool = (
        all(isnan(self.__position).ravel()) and
        all(isnan(self.__velocity).ravel()) and
        all(isnan(self.__acceleration).ravel()) and
        all(isnan(self.__orientation).ravel()) and
        all(isnan(self.__angular_velocity).ravel())
    )
    if not isfinite(self.timestamp):
      raise ValueError(f'Field `timestamp` must be finite. Got:{self.__timestamp}. Data:{self}')
    ##
    if not self.__cache_is_destroyed:
      for f in ('position', 'velocity', 'acceleration', 'orientation', 'angular_velocity',):
        v = getattr(self, f'_{type(self).__name__}__{f}')
        if not all(isfinite(v).ravel()):
          raise ValueError(f'Field `{f}` must be finite if not a destruction message. Got:{v}. Data:{self}')
        ##
      ##
    ##
    for f, expected_shape in (('position', (3,)), ('velocity', (3,)), ('acceleration', (3,),), ('orientation', (4,)), ('angular_velocity', (3,)),):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v.shape != expected_shape:
        raise ValueError(f'Field `{f}` to have shape {expected_shape}. Got:{v.shape} Data:{self}')
      ##
    ##
  ##

  @property
  def uid(self) -> Uid:
    return self.__uid
  ##

  @property
  def timestamp(self) -> TimeType:
    return self.__timestamp
  ##

  @property
  def position(self) -> PositionType:
    return self.__position
  ##

  @property
  def velocity(self) -> VelocityType:
    return self.__velocity
  ##

  @property
  def acceleration(self) -> AccelerationType:
    return self.__acceleration
  ##

  @property
  def orientation(self) -> OrientationType:
    return self.__orientation
  ##

  @property
  def angular_velocity(self) -> AngularVelocityType:
    return self.__angular_velocity
  ##

  @property
  def state(self) -> EcefState_PVA:
    if self.__cache_state is None:
      self.__cache_state = makeReadOnly(EcefState_PVA.fromComponents(
          position=self.position,
          velocity=self.velocity,
          acceleration=self.acceleration,
      ))
    ##
    return self.__cache_state
  ##

  @property
  def rotation_ecef_from_body(self) -> Rotation:
    if self.__cache_rotation_ecef_from_body is None:
      self.__cache_rotation_ecef_from_body = Rotation.from_quat(self.orientation)
    ##
    return self.__cache_rotation_ecef_from_body
  ##

  @property
  def rotation_body_from_ecef(self) -> Rotation:
    return self.rotation_ecef_from_body.inv()
  ##

  @property
  def is_destroyed(self) -> bool:
    # all fields except uid & timestamp must be NaN
    return self.__cache_is_destroyed
  ##

  def linearPropagate(self, dt: TimeType) -> PlatformState:
    """ Linearly propagates the PlatformState ahead dt seconds into the future. Propagates the position by the constant velocity and rotates the orientation by the angular velocity

    Parameters
    ----------
    dt : Time to propagate the state forward

    Returns
    -------
    PlatformState : propagated state

    """
    if dt == 0.:
      return self
    ##
    timestamp = self.__timestamp + dt
    position = self.__position
    velocity = self.__velocity
    orientation = self.__orientation
    if not self.is_destroyed:
      position = self.__position + self.__velocity * dt + .5 * self.__acceleration * dt**2
      velocity = self.__velocity + self.__acceleration * dt
      if any(w != 0. for w in self.__angular_velocity):
        # Since this conversion process is involved, check if the angular velocity is non-zero before doing any of the propagation business
        # NOTE:
        # q = quaternion
        # R = Rotation.from_rotvec
        # R.apply(v) = q*[0,v]*inv(q) = (R.as_matrix()@v.T).T
        R_ecef_from_body = self.rotation_ecef_from_body
        w_ecef = R_ecef_from_body.apply(self.__angular_velocity)
        rotvec = dt * w_ecef
        R_update = Rotation.from_rotvec(rotvec)
        R_toworld2 = R_update * R_ecef_from_body
        orientation = R_toworld2.as_quat()
      else:
        orientation = self.__orientation
      ##
    ##
    out = PlatformState(
        uid=self.__uid,
        timestamp=timestamp,
        position=position,
        velocity=velocity,
        acceleration=self.__acceleration,
        orientation=orientation,
        angular_velocity=self.__angular_velocity,

    )
    return out
  ##

  def linearPropagateToTime(self, new_time: TimeType) -> PlatformState:
    """ Linearly propagates the PlatformState ahead `dt` seconds into the future.
     Propagates the position by the constant velocity and propagates the covariance by the state propagation matrix

    Parameters
    ----------
    new_time : Time to propagate the state forward

    Returns
    -------
    PlatformState : propagated state
    """
    if new_time == self.__timestamp:
      return self
    elif self.is_destroyed:
      return self.replace(
          timestamp=new_time
      )
    ##
    return self.linearPropagate(new_time - self.__timestamp).replace(timestamp=new_time)  # makes replacement time exact
  ##

  def linearPropagatePosition(self, dt: TimeType) -> PositionType:
    return (self.__position + (dt * self.__velocity) + (((dt**2) / 2) * self.__acceleration))
  ##

  def linearPropagatePositionToTime(self, new_time: TimeType) -> PositionType:
    return self.linearPropagatePosition(dt=new_time - self.__timestamp)
  ##

  def replace(self, *,
              uid: Optional[Uid] = None,
              timestamp: Optional[TimeType] = None,
              position: Optional[PositionType] = None,
              velocity: Optional[VelocityType] = None,
              acceleration: Optional[AccelerationType] = None,
              orientation: Optional[OrientationType] = None,
              angular_velocity: Optional[AngularVelocityType] = None,
              ) -> PlatformState:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param uid: value to be replaced if not None
    @param timestamp: value to be replaced if not None
    @param position: value to be replaced if not None
    @param velocity: value to be replaced if not None
    @param acceleration: value to be replaced if not None
    @param orientation: value to be replaced if not None
    @param angular_velocity: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = PlatformState(
        uid=self.__uid if uid is None else uid,
        timestamp=self.__timestamp if timestamp is None else timestamp,
        position=self.__position if position is None else position,
        velocity=self.__velocity if velocity is None else velocity,
        acceleration=self.__acceleration if acceleration is None else acceleration,
        orientation=self.__orientation if orientation is None else orientation,
        angular_velocity=self.__angular_velocity if angular_velocity is None else angular_velocity,
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise

    """
    if not isinstance(other, type(self)):
      return False
    ##
    if self.is_destroyed and other.is_destroyed:
      return (
          (self.__uid == other.__uid) and
          allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan)
      )
    ##
    return (
        (self.__uid == other.__uid) and
        allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__position, other.__position, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__velocity, other.__velocity, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__acceleration, other.__acceleration, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__orientation, other.__orientation, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__angular_velocity, other.__angular_velocity, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
    ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    if self.is_destroyed and rhs.is_destroyed:
      return (
          (self.__uid == rhs.__uid) and
          (self.__timestamp == rhs.__timestamp)
      )
    ##
    return (
        (self.__uid == rhs.__uid) and
        (self.__timestamp == rhs.__timestamp) and
        (self.__position.shape == rhs.__position.shape) and all((self.__position == rhs.__position).ravel()) and
        (self.__velocity.shape == rhs.__velocity.shape) and all((self.__velocity == rhs.__velocity).ravel()) and
        (self.__acceleration.shape == rhs.__acceleration.shape) and all((self.__acceleration == rhs.__acceleration).ravel()) and
        (self.__orientation.shape == rhs.__orientation.shape) and all((self.__orientation == rhs.__orientation).ravel()) and
        (self.__angular_velocity.shape == rhs.__angular_velocity.shape) and all((self.__angular_velocity == rhs.__angular_velocity).ravel())
    )
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__uid,
          self.__timestamp,
          self.__position.data.tobytes(),
          self.__velocity.data.tobytes(),
          self.__acceleration.data.tobytes(),
          self.__orientation.data.tobytes(),
          self.__angular_velocity.data.tobytes(),
      ))
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = (
          f'{type(self).__name__}('
          f'uid={self.__uid!r}, '
          f'timestamp={self.__timestamp!r}, '
          f'position={self.__position!r}, '
          f'velocity={self.__velocity!r}, '
          f'acceleration={self.__acceleration!r}, '
          f'orientation={self.__orientation!r}, '
          f'angular_velocity={self.__angular_velocity!r})'
      )
    ##
    return self.__cache_repr
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        'uid': [int(u) for u in self.__uid],
        'timestamp': float(self.__timestamp),
        'position': [float(x) for x in self.__position],
        'velocity': [float(x) for x in self.__velocity],
        'acceleration': [float(x) for x in self.__acceleration],
        'orientation': [float(x) for x in self.__orientation],
        'angular_velocity': [float(x) for x in self.__angular_velocity],
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Platform Data',
        description=cls.__doc__,
        optional=False,
        fields={
            'uid': Uid.getConfigMetadata(),
            'timestamp': FloatFieldMetadata.createFinite(
                label='Timestamp',
                description=None,
                optional=False,
                default=None,
                units=Second,
            ),
            'position': RepeatedFieldMetadata.createFixedRepeat(
                label='Position',
                description='ECEF Position',
                optional=False,
                count=3,
                value=FloatFieldMetadata.createFinite(
                    label='Coordinate',
                    description='ECEF XYZ',
                    optional=False,
                    default=None,
                    units=Meter,
                ),
            ),
            'velocity': RepeatedFieldMetadata.createFixedRepeat(
                label='Velocity',
                description='ECEF Velocity',
                optional=False,
                count=3,
                value=FloatFieldMetadata.createFinite(
                    label='Coordinate',
                    description='ECEF XYZ',
                    optional=False,
                    default=None,
                    units=Meter / Second,
                ),
            ),
            'acceleration': RepeatedFieldMetadata.createFixedRepeat(
                label='Acceleration',
                description='ECEF Acceleration',
                optional=False,
                count=3,
                value=FloatFieldMetadata.createFinite(
                    label='Coordinate',
                    description='ECEF XYZ',
                    optional=False,
                    default=None,
                    units=Meter / Second**2,
                ),
            ),
            'orientation': RepeatedFieldMetadata.createFixedRepeat(
                label='Orientation Quaternion XYZW',
                description='Orientation in scalar last convention.\nECEF from body (body to world rotation) [x,y,z,W] that is vec_ecef = q_orientation * vec_body * inv(q_orientation)',
                optional=False,
                count=4,
                value=FloatFieldMetadata.createFinite(
                    label='Coordinate',
                    description='XYZW',
                    optional=False,
                    default=None,
                    units=None,
                ),
            ),
            'angular_velocity': RepeatedFieldMetadata.createFixedRepeat(
                label='Angular Velocity',
                description='World frame coordinates of omega/angular velocity',
                optional=False,
                count=3,
                value=FloatFieldMetadata.createFinite(
                    label='Coordinate',
                    description='ECEF XYZ',
                    optional=False,
                    default=None,
                    units=Radian / Second,
                ),
            ),
        },
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PlatformState:
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    out = PlatformState(
        uid=Uid(tuple(int(x) for x in config.pop('uid'))) if 'uid' in config else Uid.INVALID,
        timestamp=TimeType(config.pop('timestamp')),
        position=asarray(config.pop('position'), 'float'),
        velocity=asarray(config.pop('velocity'), 'float'),
        acceleration=asarray(config.pop('acceleration'), 'float'),
        orientation=asarray(config.pop('orientation'), 'float'),
        angular_velocity=asarray(config.pop('angular_velocity'), 'float'),
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
##


class Emission(AbcHashable):
  """ Data class representing an RF emission from a platform.

  group_id:  unique id to the emitter, typically radar track UID, but could also refer to search. Used to correlate emissions to prior emissions in time
  emission_id:  unique id to the emitter, used to correlate emissions to their returns
  timestamp:  seconds
  power: Peak power in Watts
  beam_direction: unit vector from emitter towards main beam of emission.
  NOTE: this vector must be normalized prior to assignment
  polarization_source: PolarizationType
  Polarization vector in Horizontal,Vertical in the direction of beam_direction (from the source)
  See Polarization Note, above for more clarification on polarization conventions
  NOTE: this vector must be normalized prior to assignment
  """
  public_channel: ClassVar[str]

  __slots__ = (
      '__source_uid', '__group_id', '__emission_id', '__timestamp', '__power', '__frequency',
      '__beam_direction', '__polarization_source', '__emitter_state',
      '__cache_uid', '__cache_beam_direction_emitter', '__cache_wavelength',
      '__cache_hash', '__cache_repr',
  )

  def __init__(
      self, *,
      source_uid: Uid,
      group_id: GroupId,
      emission_id: EmissionId,
      timestamp: TimeType,
      power: PowerType,
      frequency: FrequencyType,
      beam_direction: DirectionType,
      polarization_source: PolarizationType,
      emitter_state: PlatformState,
  ):
    super().__init__()
    if emitter_state.is_destroyed:
      raise ValueError(f'Cannot construct valid {Emission.__name__} because `destroyed_platform_prob` is destroyed. Got:{emitter_state}')
    ##
    self.__source_uid = Uid(source_uid)
    self.__group_id = GroupId(group_id)
    self.__emission_id = EmissionId(emission_id)
    self.__timestamp = float(timestamp)
    self.__power = FrequencyType(power)
    self.__frequency = FrequencyType(frequency)
    self.__beam_direction = makeReadOnly(asarray(beam_direction, 'float'))
    self.__polarization_source = makeReadOnly(asarray(polarization_source, 'complex'))
    self.__emitter_state = emitter_state
    self.__cache_uid: Optional[EmissionUid] = None
    self.__cache_beam_direction_emitter: Optional[DirectionType] = None
    self.__cache_wavelength: Optional[WavelengthType] = None
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    for f in ('timestamp', 'power', 'frequency', 'beam_direction', 'polarization_source',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if not all(isfinite(v).ravel()):
        raise ValueError(f'Field `{f}` must be finite. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('power', 'frequency',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v <= 0:
        raise ValueError(f'Field `{f}` must be greater than 0. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('beam_direction', 'polarization_source',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      nrm = norm(v)
      if not isclose(nrm, 1.):
        raise ValueError(f'Field `{f}` must have norm==1. Got:{nrm}. Data:{self}')
      ##
    ##
    for f, expected_shape in (('beam_direction', (3,)), ('polarization_source', (2,)),):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v.shape != expected_shape:
        raise ValueError(f'Field `{f}` to have shape {expected_shape}. Got:{v.shape} Data:{self}')
      ##
    ##
  ##

  @property
  def source_uid(self) -> Uid:
    return self.__source_uid
  ##

  @property
  def group_id(self) -> GroupId:
    return self.__group_id
  ##

  @property
  def emission_id(self) -> EmissionId:
    return self.__emission_id
  ##

  @property
  def timestamp(self) -> TimeType:
    return self.__timestamp
  ##

  @property
  def power(self) -> PowerType:
    return self.__power
  ##

  @property
  def frequency(self) -> FrequencyType:
    return self.__frequency
  ##

  @property
  def beam_direction(self) -> DirectionType:
    return self.__beam_direction
  ##

  @property
  def polarization_source(self) -> PolarizationType:
    return self.__polarization_source
  ##

  @property
  def emitter_state(self) -> PlatformState:
    return self.__emitter_state
  ##

  @property
  def uid(self) -> EmissionUid:
    """ Tuple of the structure's source UID, emission ID, and group id. This will most likely give a unique identifier for this Emission as long as the source keeps the emission and group id's unique.

    Returns
    -------
    EmissionUidType : identifier for this Emission structure

    """
    if self.__cache_uid is None:
      self.__cache_uid = EmissionUid(source_uid=self.source_uid, group_id=self.group_id, emission_id=self.emission_id)
    ##
    return self.__cache_uid
  ##

  @property
  def wavelength(self) -> WavelengthType:
    if self.__cache_wavelength is None:
      self.__cache_wavelength = WavelengthType(SPEED_OF_LIGHT / self.frequency)
    ##
    return self.__cache_wavelength
  ##

  @property
  def beam_direction_emitter(self) -> DirectionType:
    """ Gets beam direction in the emitter frame of reference"""
    if self.__cache_beam_direction_emitter is None:
      self.__cache_beam_direction_emitter = makeReadOnly(self.emitter_state.rotation_body_from_ecef.apply(self.beam_direction))
    ##
    return self.__cache_beam_direction_emitter
  ##

  def replace(self, *,
              source_uid: Optional[Uid] = None,
              group_id: Optional[GroupId] = None,
              emission_id: Optional[EmissionId] = None,
              timestamp: Optional[TimeType] = None,
              power: Optional[PowerType] = None,
              frequency: Optional[FrequencyType] = None,
              beam_direction: Optional[DirectionType] = None,
              polarization_source: Optional[PolarizationType] = None,
              emitter_state: Optional[PlatformState] = None,
              ) -> Emission:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param source_uid: value to be replaced if not None
    @param group_id: value to be replaced if not None
    @param emission_id: value to be replaced if not None
    @param timestamp: value to be replaced if not None
    @param power: value to be replaced if not None
    @param frequency: value to be replaced if not None
    @param beam_direction: value to be replaced if not None
    @param polarization_source: value to be replaced if not None
    @param emitter_state: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = Emission(
        source_uid=self.source_uid if source_uid is None else source_uid,
        group_id=self.__group_id if group_id is None else group_id,
        emission_id=self.__emission_id if emission_id is None else emission_id,
        timestamp=self.__timestamp if timestamp is None else timestamp,
        power=self.__power if power is None else power,
        frequency=self.__frequency if frequency is None else frequency,
        beam_direction=self.__beam_direction if beam_direction is None else beam_direction,
        polarization_source=self.__polarization_source if polarization_source is None else polarization_source,
        emitter_state=self.__emitter_state if emitter_state is None else emitter_state,
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise

    """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__source_uid == other.__source_uid) and
        (self.__group_id == other.__group_id) and
        (self.__emission_id == other.__emission_id) and
        allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan, ) and
        allclose(self.__power, other.__power, rtol=rtol, atol=atol, equal_nan=equal_nan, ) and
        allclose(self.__frequency, other.__frequency, rtol=rtol, atol=atol, equal_nan=equal_nan, ) and
        allclose(self.__beam_direction, other.__beam_direction, rtol=rtol, atol=atol, equal_nan=equal_nan, ) and
        allclose(self.__polarization_source, other.__polarization_source, rtol=rtol, atol=atol, equal_nan=equal_nan, ) and
        self.__emitter_state.isClose(other.__emitter_state, rtol=rtol, atol=atol, equal_nan=equal_nan, )
    )
    return out
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
  ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    out = (
        (self.__source_uid == rhs.__source_uid) and
        (self.__group_id == rhs.__group_id) and
        (self.__emission_id == rhs.__emission_id) and
        (self.__timestamp == rhs.__timestamp) and
        (self.__power == rhs.__power) and
        (self.__frequency == rhs.__frequency) and
        (self.__beam_direction.shape == rhs.__beam_direction.shape) and all((self.__beam_direction == rhs.__beam_direction).ravel()) and
        (self.__polarization_source.shape == rhs.__polarization_source.shape) and all((self.__polarization_source == rhs.__polarization_source).ravel()) and
        (self.__emitter_state == rhs.__emitter_state)
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__source_uid,
          self.__group_id,
          self.__emission_id,
          self.__timestamp,
          self.__power,
          self.__frequency,
          self.__beam_direction.data.tobytes(),
          self.__polarization_source.data.tobytes(),
          self.__emitter_state,
      ))
      values = (getattr(self, name) for name in self.__slots__)
      self.__cache_hash = hash(x.data.tobytes() if isinstance(x, ndarray) else x for x in values)
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = (
          f'{type(self).__name__}('
          f'source_uid={self.__source_uid!r}, '
          f'group_id={self.__group_id!r}, '
          f'emission_id={self.__emission_id!r}, '
          f'timestamp={self.__timestamp!r}, '
          f'power={self.__power!r}, '
          f'frequency={self.__frequency!r}, '
          f'beam_direction={self.__beam_direction!r}, '
          f'polarization_source={self.__polarization_source!r}, '
          f'emitter_state={self.__emitter_state!r})'
      )
    ##
    return self.__cache_repr
  ##

##


class EmissionReturn(AbcHashable):
  """ Data structure representing the two-way Emission Return from an emitter, to reflector, and then to receiver
  emission_id:  unique id to the emitter, used to correlate emissions to their returns
  timestamp:  time of initial emission
  power_return: The radar range equation is: Ptx * [(1/(4*pi*R1^2)) * * sigma * (1/(4*pi*R2^2))] * (Gtx * Grx*lambda^2/(4*pi)) = Prx
    Power return term reduction is the emission power times the terms in the [] brackets. Antenna Gain's and lambda^2 terms are taken account in the Radar on return
  transit_time:  time from emission to received return
  doppler_shift: Doppler frequency shift is  -(R1'+R2')*(ftx / c)
  reflection_direction:  unit vector to receiver (at receive time) from reflected target (at reflection time)
  polarization_reflector: Polarization vector in Horz,Vert in direction of travel, complex unit vector, default RHC
    Polarization vector in Horizontal,Vertical in the direction of beam_direction (from the reflector)
    See Polarization Note, above for more clarification on polarization conventions
  """
  # no public channel - individual to each receiver

  __slots__ = (
      '__source_uid', '__reflector_uid', '__receiver_uid', '__emission_id', '__timestamp', '__power_return',
      '__transit_time', '__doppler_shift', '__reflection_direction', '__polarization_reflector',
      '__cache_hash', '__cache_receive_time', '__cache_emission_return_uid', '__cache_repr',
  )

  def __init__(
      self, *,
      source_uid: Uid,
      reflector_uid: Uid,
      receiver_uid: Uid,
      emission_id: EmissionId,
      timestamp: TimeType,
      power_return: float,
      transit_time: TimeType,
      doppler_shift: float,
      reflection_direction: DirectionType,
      polarization_reflector: PolarizationType,
  ):
    super().__init__()
    self.__source_uid = Uid(source_uid)
    self.__reflector_uid = Uid(reflector_uid)
    self.__receiver_uid = Uid(receiver_uid)
    self.__emission_id = EmissionId(emission_id)
    self.__timestamp = float(timestamp)
    self.__power_return = float(power_return)
    self.__transit_time = float(transit_time)
    self.__doppler_shift = float(doppler_shift)
    self.__reflection_direction = makeReadOnly(asarray(reflection_direction, 'float'))
    self.__polarization_reflector = makeReadOnly(asarray(polarization_reflector, 'complex'))
    self.__cache_receive_time: Optional[TimeType] = None
    self.__cache_emission_return_uid: Optional[EmissionReturnUid] = None
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    for f in ('timestamp', 'power_return', 'transit_time', 'doppler_shift', 'reflection_direction', 'polarization_reflector',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if not all(isfinite(v).ravel()):
        raise ValueError(f'Field `{f}` must be finite if not a destruction message. Got:{v}. Data:{self}')
      ##
    ##
    # Power return or transit time could be 0
    for f in ('power_return', 'transit_time',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v < 0:
        raise ValueError(f'Field `{f}` must be greater than or equal 0. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('reflection_direction', 'polarization_reflector',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      nrm = norm(v)
      if not isclose(nrm, 1.):
        raise ValueError(f'Field `{f}` must have norm==1. Got:{nrm}. Data:{self}')
      ##
    ##
    for f, expected_shape in (('reflection_direction', (3,)), ('polarization_reflector', (2,)),):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v.shape != expected_shape:
        raise ValueError(f'Field `{f}` to have shape {expected_shape}. Got:{v.shape} Data:{self}')
      ##
    ##
  ##

  @property
  def source_uid(self) -> Uid:
    return self.__source_uid
  ##

  @property
  def reflector_uid(self) -> Uid:
    return self.__reflector_uid
  ##

  @property
  def receiver_uid(self) -> Uid:
    return self.__receiver_uid
  ##

  @property
  def emission_id(self) -> EmissionId:
    return self.__emission_id
  ##

  @property
  def timestamp(self) -> TimeType:
    return self.__timestamp
  ##

  @property
  def power_return(self) -> float:
    return self.__power_return
  ##

  @property
  def transit_time(self) -> TimeType:
    return self.__transit_time
  ##

  @property
  def doppler_shift(self) -> float:
    return self.__doppler_shift
  ##

  @property
  def reflection_direction(self) -> DirectionType:
    return self.__reflection_direction
  ##

  @property
  def polarization_reflector(self) -> PolarizationType:
    return self.__polarization_reflector
  ##

  @property
  def receive_time(self) -> TimeType:
    """ Time at which the receiver received the emission return.

    Returns
    -------
    TimeType: absolute time receiver received this emission return.

    """
    if self.__cache_receive_time is None:
      self.__cache_receive_time = self.timestamp + self.transit_time
    ##
    return self.__cache_receive_time
  ##

  @property
  def uid(self) -> EmissionReturnUid:
    """ Tuple of the structure's source UID, reflector UID, and the emission ID. This will most likely give a unique identifier for this EmissionReturn as long as the source keeps the emission id's unique

    Returns
    -------
    EmissionReturnUidType : identifier for this EmissionReturn structure

    """
    if self.__cache_emission_return_uid is None:
      self.__cache_emission_return_uid = EmissionReturnUid(source_uid=self.source_uid, reflector_uid=self.reflector_uid, receiver_uid=self.receiver_uid, emission_id=self.emission_id)
    ##
    return self.__cache_emission_return_uid
  ##

  def replace(self, *,
              source_uid: Optional[Uid] = None,
              reflector_uid: Optional[Uid] = None,
              receiver_uid: Optional[Uid] = None,
              emission_id: Optional[EmissionId] = None,
              timestamp: Optional[TimeType] = None,
              power_return: Optional[float] = None,
              transit_time: Optional[TimeType] = None,
              doppler_shift: Optional[float] = None,
              reflection_direction: Optional[DirectionType] = None,
              polarization_reflector: Optional[PolarizationType] = None,
              ) -> EmissionReturn:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param source_uid: value to be replaced if not None
    @param reflector_uid: value to be replaced if not None
    @param receiver_uid: value to be replaced if not None
    @param emission_id: value to be replaced if not None
    @param timestamp: value to be replaced if not None
    @param power_return: value to be replaced if not None
    @param transit_time: value to be replaced if not None
    @param doppler_shift: value to be replaced if not None
    @param reflection_direction: value to be replaced if not None
    @param polarization_reflector: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = EmissionReturn(
        source_uid=self.__source_uid if source_uid is None else source_uid,
        reflector_uid=self.__reflector_uid if reflector_uid is None else reflector_uid,
        receiver_uid=self.__receiver_uid if receiver_uid is None else receiver_uid,
        emission_id=self.__emission_id if emission_id is None else emission_id,
        timestamp=self.__timestamp if timestamp is None else timestamp,
        power_return=self.__power_return if power_return is None else power_return,
        transit_time=self.__transit_time if transit_time is None else transit_time,
        doppler_shift=self.__doppler_shift if doppler_shift is None else doppler_shift,
        reflection_direction=self.__reflection_direction if reflection_direction is None else reflection_direction,
        polarization_reflector=self.__polarization_reflector if polarization_reflector is None else polarization_reflector,
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise

    """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__source_uid == other.__source_uid) and
        (self.__reflector_uid == other.__reflector_uid) and
        (self.__receiver_uid == other.__receiver_uid) and
        (self.__emission_id == other.__emission_id) and
        allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__power_return, other.__power_return, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__transit_time, other.__transit_time, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__doppler_shift, other.__doppler_shift, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__reflection_direction, other.__reflection_direction, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__polarization_reflector, other.__polarization_reflector, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
    ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    out = (
        (self.__source_uid == rhs.__source_uid) and
        (self.__reflector_uid == rhs.__reflector_uid) and
        (self.__receiver_uid == rhs.__receiver_uid) and
        (self.__emission_id == rhs.__emission_id) and
        (self.__timestamp == rhs.__timestamp) and
        (self.__power_return == rhs.__power_return) and
        (self.__transit_time == rhs.__transit_time) and
        (self.__doppler_shift == rhs.__doppler_shift) and
        (self.__reflection_direction.shape == rhs.__reflection_direction.shape) and all((self.__reflection_direction == rhs.__reflection_direction).ravel()) and
        (self.__polarization_reflector.shape == rhs.__polarization_reflector.shape) and all((self.__polarization_reflector == rhs.__polarization_reflector).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__source_uid,
          self.__reflector_uid,
          self.__receiver_uid,
          self.__emission_id,
          self.__timestamp,
          self.__power_return,
          self.__transit_time,
          self.__doppler_shift,
          self.__reflection_direction.data.tobytes(),
          self.__polarization_reflector.data.tobytes(),
      ))
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'source_uid={self.__source_uid!r}, ' \
                          f'reflector_uid={self.__reflector_uid!r}, ' \
                          f'receiver_uid={self.__receiver_uid!r}, ' \
                          f'emission_id={self.__emission_id!r}, ' \
                          f'timestamp={self.__timestamp!r}, ' \
                          f'power_return={self.__power_return!r}, ' \
                          f'transit_time={self.__transit_time!r}, ' \
                          f'doppler_shift={self.__doppler_shift!r}, ' \
                          f'reflection_direction={self.__reflection_direction!r}, ' \
                          f'polarization_reflector={self.__polarization_reflector!r})'
    ##
    return self.__cache_repr
  ##
##

####################


class TrackData(AbcHashable):
  """ Data structure representing a ECEF track state. This may be used as both tracking data and also as handover/cueing data
  group_id: GroupId  # not universally unique, but unique id to the track data reporter, Used to correlate series of tracks over time (e.g. the handover track that started the tracks)
  track_id: TrackId  # not universally unique, but unique to the track data reporter
  """
  __slots__ = (
      '__reporter_uid', '__group_id', '__track_id', '__timestamp', '__position', '__velocity', '__acceleration', '__covariance',
      '__cache_uid', '__cache_state', '__cache_is_drop_track', '__cache_hash', '__cache_repr',
  )
  public_channel: ClassVar[str]

  def __init__(
      self, *,
      reporter_uid: Uid,
      group_id: GroupId,
      track_id: TrackId,
      timestamp: TimeType,
      position: PositionType,
      velocity: VelocityType,
      acceleration: AccelerationType,
      covariance: Union[EcefStateCovariance_PVA, ndarray],
  ):
    super().__init__()
    self.__reporter_uid = Uid(reporter_uid)
    self.__group_id = GroupId(group_id)
    self.__track_id = TrackId(track_id)
    self.__timestamp = float(timestamp)
    self.__position = makeReadOnly(asarray(position, 'float'))
    self.__velocity = makeReadOnly(asarray(velocity, 'float'))
    self.__acceleration = makeReadOnly(asarray(acceleration, 'float'))
    self.__covariance:EcefStateCovariance_PVA = makeReadOnly(EcefStateCovariance_PVA(asarray(covariance, 'float')))
    self.__cache_uid: Optional[TrackUid] = None
    self.__cache_state: Optional[EcefState_PVA] = None
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    self.__cache_is_drop_track: bool = (
        all(isnan(self.__position).ravel()) and
        all(isnan(self.__velocity).ravel()) and
        all(isnan(self.__acceleration).ravel()) and
        all(isnan(self.__covariance).ravel())
    )
    if not isfinite(self.__timestamp):
      raise ValueError(f'Field `timestamp` must be finite. Got:{self.__timestamp}. Data:{self}')
    ##
    if not self.__cache_is_drop_track:
      for f in ('position', 'velocity', 'acceleration', 'covariance',):
        v = getattr(self, f'_{type(self).__name__}__{f}')
        if not all(isfinite(v).ravel()):
          raise ValueError(f'Field `{f}` must be finite if not a drop-track message. Got:{v}. Data:{self}')
        ##
      ##
    ##
    for f, expected_shape in (('position', (3,)), ('velocity', (3,)), ('acceleration', (3,),), ('covariance', (9, 9,)),):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v.shape != expected_shape:
        raise ValueError(f'Field `{f}` to have shape {expected_shape}. Got:{v.shape} Data:{self}')
      ##
    ##
  ##

  @property
  def reporter_uid(self) -> Uid:
    return self.__reporter_uid
  ##

  @property
  def group_id(self) -> GroupId:
    return self.__group_id
  ##

  @property
  def track_id(self) -> TrackId:
    return self.__track_id
  ##

  @property
  def timestamp(self) -> TimeType:
    return self.__timestamp
  ##

  @property
  def position(self) -> PositionType:
    return self.__position
  ##

  @property
  def velocity(self) -> VelocityType:
    return self.__velocity
  ##

  @property
  def acceleration(self) -> AccelerationType:
    return self.__acceleration
  ##

  @property
  def covariance(self) -> EcefStateCovariance_PVA:
    return self.__covariance
  ##

  @property
  def uid(self) -> TrackUid:
    """ Tuple of the structure's reporter UID and the track's id. This will most likely give a unique identifier for this TrackData as long as the reporter keeps the track id's unique

    @return: identifier for this TrackData structure
    """
    if self.__cache_uid is None:
      self.__cache_uid = TrackUid(reporter_uid=self.reporter_uid, group_id=self.group_id, track_id=self.track_id)
    ##
    return self.__cache_uid
  ##

  @property
  def state(self) -> EcefState_PVA:
    if self.__cache_state is None:
      self.__cache_state = makeReadOnly(EcefState_PVA.fromComponents(
          position=self.position,
          velocity=self.velocity,
          acceleration=self.acceleration,
      ))
    ##
    return self.__cache_state
  ##

  @property
  def is_drop_track(self) -> bool:
    # all fields except id's & timestamp must be NaN
    return self.__cache_is_drop_track
  ##

  @property
  def position_covariance(self) -> ndarray:
    # gets position covariance sub-matrix
    return self.getPositionCovariance(self.covariance)
  ##

  @property
  def velocity_covariance(self) -> ndarray:
    # gets velocity covariance sub-matrix
    return self.getVelocityCovariance(self.covariance)
  ##

  @property
  def acceleration_covariance(self) -> ndarray:
    # gets acceleration covariance sub-matrix
    return self.getAccelerationCovariance(self.covariance)
  ##

  @property
  def position_variance(self) -> float:
    return self.getPositionVariance(self.covariance)
  ##

  @property
  def velocity_variance(self) -> float:
    return self.getVelocityVariance(self.covariance)
  ##

  @property
  def acceleration_variance(self) -> float:
    return self.getAccelerationVariance(self.covariance)
  ##

  def linearPropagate(self, dt: TimeType) -> TrackData:
    """ Linearly propagates the TrackData ahead `dt` seconds into the future.
     Propagates the position by the constant velocity and propagates the covariance by the state propagation matrix

    Parameters
    ----------
    dt : Amount of time to propagate the state forward

    Returns
    -------
    TrackData : propagated state
    """
    if self.is_drop_track:
      return self.replace(timestamp=self.timestamp + dt)
    elif dt == 0.:
      return self
    ##
    F = eye(9)  # F is the linear forward propagation matrix
    # ppp,vvv,aaa
    F[(0, 1, 2), (3, 4, 5)] = dt
    F[(0, 1, 2), (6, 7, 8)] = .5 * (dt**2)
    F[(3, 4, 5), (6, 7, 8)] = dt
    out = self.replace(
        timestamp=self.timestamp + dt,
        position=self.position + self.velocity * dt + .5 * self.acceleration * dt**2,
        velocity=self.velocity + self.acceleration * dt,
        covariance=EcefStateCovariance_PVA(F @ self.covariance @ F.T),
    )
    return out
  ##

  def linearPropagateToTime(self, new_time: TimeType) -> TrackData:
    """ Linearly propagates the TrackData ahead `dt` seconds into the future.
     Propagates the position by the constant velocity and propagates the covariance by the state propagation matrix

    Parameters
    ----------
    new_time : Time to propagate the state forward

    Returns
    -------
    TrackData : propagated state
    """
    if new_time == self.__timestamp:
      return self
    elif self.is_drop_track:
      return self.replace(
          timestamp=new_time
      )
    ##
    return self.linearPropagate(new_time - self.__timestamp).replace(timestamp=new_time)  # makes replacement time exact
  ##

  def linearPropagatePosition(self, dt: TimeType) -> PositionType:
    return self.__position + (dt * self.__velocity) + (((dt**2) / 2) * self.__acceleration)
  ##

  def linearPropagatePositionToTime(self, new_time: TimeType) -> PositionType:
    return self.linearPropagatePosition(new_time - self.__timestamp)
  ##

  def replace(self, *,
              reporter_uid: Optional[Uid] = None,
              group_id: Optional[GroupId] = None,
              track_id: Optional[TrackId] = None,
              timestamp: Optional[TimeType] = None,
              position: Optional[PositionType] = None,
              velocity: Optional[VelocityType] = None,
              acceleration: Optional[AccelerationType] = None,
              covariance: Optional[EcefStateCovariance_PVA] = None,
              ) -> TrackData:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param reporter_uid: value to be replaced if not None
    @param group_id: value to be replaced if not None
    @param track_id: value to be replaced if not None
    @param timestamp: value to be replaced if not None
    @param position: value to be replaced if not None
    @param velocity: value to be replaced if not None
    @param acceleration: value to be replaced if not None
    @param covariance: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = TrackData(
        reporter_uid=self.__reporter_uid if reporter_uid is None else reporter_uid,
        group_id=self.__group_id if group_id is None else group_id,
        track_id=self.__track_id if track_id is None else track_id,
        timestamp=self.__timestamp if timestamp is None else timestamp,
        position=self.__position if position is None else position,
        velocity=self.__velocity if velocity is None else velocity,
        acceleration=self.__acceleration if acceleration is None else acceleration,
        covariance=self.__covariance if covariance is None else covariance,
    )
    return out
  ##

  def updateTrackUid(self, track_uid: TrackUid) -> TrackData:
    return self.replace(
        reporter_uid=track_uid.reporter_uid,
        group_id=track_uid.group_id,
        track_id=track_uid.track_id,
    )
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise

    """
    if not isinstance(other, type(self)):
      return False
    ##
    return (
        (self.__reporter_uid == other.__reporter_uid) and
        (self.__group_id == other.__group_id) and
        (self.__track_id == other.__track_id) and
        allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__position, other.__position, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__velocity, other.__velocity, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__acceleration, other.__acceleration, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__covariance, other.__covariance, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
    ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    return (
        (self.__reporter_uid == rhs.__reporter_uid) and
        (self.__group_id == rhs.__group_id) and
        (self.__track_id == rhs.__track_id) and
        (self.__timestamp == rhs.__timestamp) and
        ((self.is_drop_track and rhs.is_drop_track) or (
            (self.__position.shape == rhs.__position.shape) and all((self.__position == rhs.__position).ravel()) and
            (self.__velocity.shape == rhs.__velocity.shape) and all((self.__velocity == rhs.__velocity).ravel()) and
            (self.__acceleration.shape == rhs.__acceleration.shape) and all((self.__acceleration == rhs.__acceleration).ravel()) and
            (self.__covariance.shape == rhs.__covariance.shape) and all((self.__covariance == rhs.__covariance).ravel())
        ))
    )
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__reporter_uid,
          self.__group_id,
          self.__track_id,
          self.__timestamp,
          self.__position.data.tobytes(),
          self.__velocity.data.tobytes(),
          self.__acceleration.data.tobytes(),
          self.__covariance.data.tobytes(),
      ))
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'reporter_uid={self.__reporter_uid!r}, ' \
                          f'group_id={self.__group_id!r}, ' \
                          f'track_id={self.__track_id!r}, ' \
                          f'timestamp={self.__timestamp!r}, ' \
                          f'position={self.__position!r}, ' \
                          f'velocity={self.__velocity!r}, ' \
                          f'acceleration={self.__acceleration!r}, ' \
                          f'covariance={self.__covariance!r})'
    ##
    return self.__cache_repr
  ##

  @classmethod
  def getPositionCovariance(cls, covariance: EcefStateCovariance_PVA) -> ndarray:
    # gets position covariance sub-matrix
    if isinstance(covariance, EcefStateCovariance_PVA):
      return covariance.position_covar
    else:
      return covariance[EcefStateCovariance_PVA.position_slice, EcefStateCovariance_PVA.position_slice]
    ##
  ##

  @classmethod
  def getVelocityCovariance(cls, covariance: EcefStateCovariance_PVA) -> ndarray:
    # gets velocity covariance sub-matrix
    if isinstance(covariance, EcefStateCovariance_PVA):
      return covariance.velocity_covar
    else:
      return covariance[EcefStateCovariance_PVA.velocity_slice, EcefStateCovariance_PVA.velocity_slice]
    ##
  ##

  @classmethod
  def getAccelerationCovariance(cls, covariance: EcefStateCovariance_PVA) -> ndarray:
    # gets acceleration covariance sub-matrix
    if isinstance(covariance, EcefStateCovariance_PVA):
      return covariance.acceleration_covar
    else:
      return covariance[EcefStateCovariance_PVA.acceleration_slice, EcefStateCovariance_PVA.acceleration_slice]
    ##
  ##

  @classmethod
  def getPositionVariance(cls, covariance: EcefStateCovariance_PVA) -> float:
    # gets sum of position variances
    return float(trace(cls.getPositionCovariance(covariance)))
  ##

  @classmethod
  def getVelocityVariance(cls, covariance: EcefStateCovariance_PVA) -> float:
    # gets sum of velocity variances
    return float(trace(cls.getVelocityCovariance(covariance)))
  ##

  @classmethod
  def getAccelerationVariance(cls, covariance: EcefStateCovariance_PVA) -> float:
    # gets sum of acceleration variances
    return float(trace(cls.getAccelerationCovariance(covariance)))
  ##
##


####################
class RcsQuery(AbcHashable):
  """ Data structure that combines all the necessary parameters to determine an object's RCS
  direction_in: Direction in towards the reflector in the reflector's frame.
                If the incoming wave (in the reflector's frame) is traveling from +x to -x, then this will be equal to [-1,0,0]
  direction_out: Direction out from the reflector in the reflector's frame.
                 If the outgoing wave (in the reflector's frame) is traveling from -x to +x, then this will be equal to [+1,0,0]
  polarization_source: Polarization of the incoming wave in the plane perpendicular to direction_in
                       The polarization is from the point of view of the source
                       (left- or right-handedness is determined by pointing one's left or right thumb
                       away from the source, in the same direction that the wave is propagating)
  """
  __slots__ = (
      '__reflector_uid', '__timestamp', '__frequency', '__direction_in', '__direction_out', '__polarization_source',
      '__cache_hash', '__cache_repr',
      '__cache_azimuth_out_rad', '__cache_azimuth_out_deg',
      '__cache_elevation_out_rad', '__cache_elevation_out_deg',
      '__cache_is_monostatic',
  )

  def __init__(
      self, *,
      reflector_uid: Uid,
      timestamp: TimeType,
      frequency: FrequencyType,
      direction_in: DirectionType,
      direction_out: DirectionType,
      polarization_source: PolarizationType,
  ):
    super().__init__()
    self.__reflector_uid = Uid(reflector_uid)
    self.__timestamp = float(timestamp)
    self.__frequency = FrequencyType(frequency)
    self.__direction_in = makeReadOnly(asarray(direction_in, 'float'))
    self.__direction_out = makeReadOnly(asarray(direction_out, 'float'))
    self.__polarization_source = makeReadOnly(asarray(polarization_source, 'complex'))
    self.__cache_azimuth_out_rad: Optional[float] = None
    self.__cache_azimuth_out_deg: Optional[float] = None
    self.__cache_elevation_out_rad: Optional[float] = None
    self.__cache_elevation_out_deg: Optional[float] = None
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    for f in ('timestamp', 'frequency', 'direction_in', 'direction_out', 'polarization_source',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if not all(isfinite(v).ravel()):
        raise ValueError(f'Field `{f}` must be finite. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('frequency',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v <= 0:
        raise ValueError(f'Field `{f}` must be greater than 0. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('direction_in', 'direction_out', 'polarization_source',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      nrm = norm(v)
      if not isclose(nrm, 1.):
        raise ValueError(f'Field `{f}` must have norm==1. Got:{nrm}. Data:{self}')
      ##
    ##
    for f, expected_shape in (('direction_in', (3,)), ('direction_out', (3,)), ('polarization_source', (2,)),):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v.shape != expected_shape:
        raise ValueError(f'Field `{f}` to have shape {expected_shape}. Got:{v.shape} Data:{self}')
      ##
    ##
    self.__cache_is_monostatic = all((self.__direction_in == -self.__direction_out).ravel())
  ##

  @property
  def reflector_uid(self) -> Uid:
    return self.__reflector_uid
  ##

  @property
  def timestamp(self) -> TimeType:
    return self.__timestamp
  ##

  @property
  def frequency(self) -> FrequencyType:
    return self.__frequency
  ##

  @property
  def direction_in(self) -> DirectionType:
    return self.__direction_in
  ##

  @property
  def direction_out(self) -> DirectionType:
    return self.__direction_out
  ##

  @property
  def polarization_source(self) -> PolarizationType:
    return self.__polarization_source
  ##

  @property
  def is_monostatic(self) -> bool:
    """ Illuminator is Receiver; Direction in = -Direction out. """
    return self.__cache_is_monostatic
  ##

  @property
  def azimuth_out_rad(self) -> float:
    if self.__cache_azimuth_out_rad is None:
      self.__cache_azimuth_out_rad = float(arctan2(self.direction_out[..., 1], self.direction_out[..., 0]))
    ##
    return self.__cache_azimuth_out_rad
  ##

  @property
  def azimuth_out_deg(self) -> float:
    if self.__cache_azimuth_out_deg is None:
      self.__cache_azimuth_out_deg = float(rad2deg(self.azimuth_out_rad))
    ##
    return self.__cache_azimuth_out_deg
  ##

  @property
  def elevation_out_rad(self) -> float:
    if self.__cache_elevation_out_rad is None:
      self.__cache_elevation_out_rad = float(-arcsin(self.direction_out[..., 2]))
    ##
    return self.__cache_elevation_out_rad
  ##

  @property
  def elevation_out_deg(self) -> float:
    if self.__cache_elevation_out_deg is None:
      self.__cache_elevation_out_deg = float(rad2deg(self.elevation_out_rad))
    ##
    return self.__cache_elevation_out_deg
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise
    """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__reflector_uid == other.__reflector_uid) and
        allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__frequency, other.__frequency, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__direction_in, other.__direction_in, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__direction_out, other.__direction_out, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__polarization_source, other.__polarization_source, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def replace(self, *,
              reflector_uid: Optional[Uid] = None,
              timestamp: Optional[TimeType] = None,
              frequency: Optional[FrequencyType] = None,
              direction_in: Optional[DirectionType] = None,
              direction_out: Optional[DirectionType] = None,
              polarization_source: Optional[PolarizationType] = None,
              ) -> RcsQuery:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param reflector_uid: value to be replaced if not None
    @param timestamp: value to be replaced if not None
    @param frequency: value to be replaced if not None
    @param direction_in: value to be replaced if not None
    @param direction_out: value to be replaced if not None
    @param polarization_source: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = RcsQuery(
        reflector_uid=self.__reflector_uid if reflector_uid is None else reflector_uid,
        timestamp=self.__timestamp if timestamp is None else timestamp,
        frequency=self.__frequency if frequency is None else frequency,
        direction_in=self.__direction_in if direction_in is None else direction_in,
        direction_out=self.__direction_out if direction_out is None else direction_out,
        polarization_source=self.__polarization_source if polarization_source is None else polarization_source,
    )
    return out
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
    ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    out = (
        (self.__reflector_uid == rhs.__reflector_uid) and
        (self.__timestamp == rhs.__timestamp) and
        (self.__frequency == rhs.__frequency) and
        (self.__direction_in.shape == rhs.__direction_in.shape) and all((self.__direction_in == rhs.__direction_in).ravel()) and
        (self.__direction_out.shape == rhs.__direction_out.shape) and all((self.__direction_out == rhs.__direction_out).ravel()) and
        (self.__polarization_source.shape == rhs.__polarization_source.shape) and all((self.__polarization_source == rhs.__polarization_source).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__reflector_uid,
          self.__timestamp,
          self.__frequency,
          self.__direction_in.data.tobytes(),
          self.__direction_out.data.tobytes(),
          self.__polarization_source.data.tobytes(),
      ))
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'reflector_uid={self.__reflector_uid!r}, ' \
                          f'timestamp={self.__timestamp!r}, ' \
                          f'frequency={self.__frequency!r}, ' \
                          f'direction_in={self.__direction_in!r}, ' \
                          f'direction_out={self.__direction_out!r}, ' \
                          f'polarization_source={self.__polarization_source!r})'
    ##
    return self.__cache_repr
  ##
##


class RcsResponse(AbcHashable):
  """ Data structure representing a Receiver announcing which channel it expects to receive EmissionReturn data on
  polarization_reflector: Polarization vector in Horz,Vert in direction of travel, complex unit vector, default RHC
  Polarization vector in Horizontal,Vertical in the direction of beam_direction (from the reflector)
  The default behavior for RCS Reflector objects should be to just simply copy the polarization from the Query to the Response,
  as this would signify the simplest type of reflection.
  It should be noted that if the observer is held constant the handedness changes.
  This typical in a Monostatic Radar (both Tx & Rx). This is because the convention swaps from source-derived
  handedness to receiver derived handedness. If the convention is always held to be source-derived then the
  handedness does not change after a reflection (rather the observer changes)

  Simply put, the simplest type reflection is represented by a RcsResponse that has the exact same
  polarization value as the RcsQuery
  NOTE: it is assumed that polarization reflector is a dtype='complex' and normalized
  """
  __slots__ = (
      '__reflector_uid', '__rcs', '__polarization_reflector',
      '__cache_hash', '__cache_repr',
  )

  def __init__(
      self, *,
      reflector_uid: Uid,
      rcs: RcsMagnitudeType,
      polarization_reflector: PolarizationType,
  ):
    super().__init__()
    self.__reflector_uid = Uid(reflector_uid)
    self.__rcs = float(rcs)
    self.__polarization_reflector = makeReadOnly(asarray(polarization_reflector, 'complex'))
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    for f in ('rcs', 'polarization_reflector',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if not all(isfinite(v).ravel()):
        raise ValueError(f'Field `{f}` must be finite. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('rcs',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v < 0:
        raise ValueError(f'Field `{f}` must be greater than or equal to 0. Got:{v}. Data:{self}')
      ##
    ##
    for f in ('polarization_reflector',):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      nrm = norm(v)
      if not isclose(nrm, 1.):
        raise ValueError(f'Field `{f}` must have norm==1. Got:{nrm}. Data:{self}')
      ##
    ##
    for f, expected_shape in (('polarization_reflector', (2,)),):
      v = getattr(self, f'_{type(self).__name__}__{f}')
      if v.shape != expected_shape:
        raise ValueError(f'Field `{f}` to have shape {expected_shape}. Got:{v.shape} Data:{self}')
      ##
    ##
  ##

  @property
  def reflector_uid(self) -> Uid:
    return self.__reflector_uid
  ##

  @property
  def rcs(self) -> RcsMagnitudeType:
    return self.__rcs
  ##

  @property
  def polarization_reflector(self) -> PolarizationType:
    return self.__polarization_reflector
  ##

  def replace(self, *,
              reflector_uid: Optional[Uid] = None,
              rcs: Optional[RcsMagnitudeType] = None,
              polarization_reflector: Optional[PolarizationType] = None,
              ) -> RcsResponse:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param reflector_uid: value to be replaced if not None
    @param rcs: value to be replaced if not None
    @param polarization_reflector: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = RcsResponse(
        reflector_uid=self.__reflector_uid if reflector_uid is None else reflector_uid,
        rcs=self.__rcs if rcs is None else rcs,
        polarization_reflector=self.__polarization_reflector if polarization_reflector is None else polarization_reflector,
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise

    """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__reflector_uid == other.__reflector_uid) and
        allclose(self.__rcs, other.__rcs, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__polarization_reflector, other.__polarization_reflector, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
    ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    out = (
        (self.__reflector_uid == rhs.__reflector_uid) and
        (self.__rcs == rhs.__rcs) and
        (self.__polarization_reflector.shape == rhs.__polarization_reflector.shape) and all((self.__polarization_reflector == rhs.__polarization_reflector).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__reflector_uid,
          self.__rcs,
          self.__polarization_reflector.data.tobytes(),
      ))
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'reflector_uid={self.__reflector_uid!r}, ' \
                          f'rcs={self.__rcs!r}, ' \
                          f'polarization_reflector={self.__polarization_reflector!r})'
    ##
    return self.__cache_repr
  ##

##


class RcsLogMessage(AbcHashable):
  """ Combination of RCS query and response. """
  __slots__ = (
      '__caller_uid', '__timestamp', '__emission_return_uid', '__query', '__response',
      '__cache_hash', '__cache_repr',
  )
  public_channel: ClassVar[str]

  def __init__(
      self, *,
      caller_uid: Uid,
      timestamp: TimeType,
      emission_return_uid: EmissionReturnUid,
      query: RcsQuery,
      response: RcsResponse,
  ):
    super().__init__()
    self.__caller_uid = caller_uid
    self.__timestamp = timestamp
    self.__emission_return_uid = emission_return_uid
    self.__query = query
    self.__response = response
    self.__cache_hash: Optional[int] = None
    self.__cache_repr: Optional[str] = None
    if not isfinite(self.timestamp):
      raise ValueError(f'Field `timestamp` must be finite. Got:{self.__timestamp}. Data:{self}')
    ##
  ##

  @property
  def caller_uid(self) -> Uid:
    return self.__caller_uid
  ##

  @property
  def timestamp(self) -> TimeType:
    return self.__timestamp
  ##

  @property
  def emission_return_uid(self) -> EmissionReturnUid:
    return self.__emission_return_uid
  ##

  @property
  def query(self) -> RcsQuery:
    return self.__query
  ##

  @property
  def response(self) -> RcsResponse:
    return self.__response
  ##

  def replace(self, *,
              caller_uid: Optional[Uid] = None,
              timestamp: Optional[TimeType] = None,
              emission_return_uid: Optional[EmissionReturnUid] = None,
              query: Optional[RcsQuery] = None,
              response: Optional[RcsResponse] = None,
              ) -> RcsLogMessage:
    out = RcsLogMessage(
        caller_uid=self.__caller_uid if caller_uid is None else caller_uid,
        timestamp=self.__timestamp if timestamp is None else timestamp,
        emission_return_uid=self.__emission_return_uid if emission_return_uid is None else emission_return_uid,
        query=self.__query if query is None else query,
        response=self.__response if response is None else response,
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

    Parameters
    ----------
    other: object
      other value for comparison
    rtol: float
      Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
    atol: float
      Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
    equal_nan: bool
      Consider NaN values to be equal. Default False.

    Returns
    -------
    bool
      True if all the fields are close within a tolerance, False otherwise

    """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__caller_uid == other.__caller_uid) and
        allclose(self.__timestamp, other.__timestamp, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        (self.__emission_return_uid == other.__emission_return_uid) and
        (self.__query.isClose(other.__query, rtol=rtol, atol=atol, equal_nan=equal_nan)) and
        self.__response.isClose(other.__response, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def __eq__(self, rhs: object) -> bool:
    """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

    Parameters
    ----------
    rhs: value to be compared

    Returns
    -------
    bool : returns True if same type and all the fields are exactly equal, False otherwise

    """
    if not isinstance(rhs, type(self)):
      return False
    ##
    out = (
        (self.__caller_uid == rhs.__caller_uid) and
        (self.__timestamp == rhs.__timestamp) and
        (self.__emission_return_uid == rhs.__emission_return_uid) and
        (self.__query == rhs.__query) and
        (self.__response == rhs.__response)
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_hash is None:
      self.__cache_hash = hash((
          self.__caller_uid,
          self.__timestamp,
          self.__emission_return_uid,
          self.__query,
          self.__response,
      ))
    ##
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    """ Calculates hash for the class

    @return: hash of class
    """
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'caller_uid={self.__caller_uid!r}, ' \
                          f'timestamp={self.__timestamp!r}, ' \
                          f'emission_return_uid={self.__emission_return_uid!r}, ' \
                          f'query={self.__query!r}, ' \
                          f'response={self.__response!r})'
    ##
    return self.__cache_repr
  ##
##
####################
# Definitions for standard channels to publish state data on. All of these channels are considered public and any model can publish to these


PLATFORM_STATE_CHANNEL = f'{PlatformState.__name__}'
EMISSION_CHANNEL = f'{Emission.__name__}'
TRACK_DATA_CHANNEL = f'{TrackData.__name__}'  # Should be created track data (not immature tracks)
IMMATURE_TRACK_DATA_CHANNEL = f'Immature{TrackData.__name__}'
RCS_LOG_MESSAGE_CHANNEL = f'{RcsLogMessage.__name__}'
PlatformState.public_channel = f'{PlatformState.__name__}'
Emission.public_channel = f'{Emission.__name__}'
TrackData.public_channel = f'{TrackData.__name__}'  # Should be created track data (not immature tracks)
RcsLogMessage.public_channel = f'{RcsLogMessage.__name__}'
####################

# Platform State denoting a destruction. To send an appropriate message,
# the timestamp should be more recent than any of the newest platform messages
# and also the uid should be a valid unique id.
DESTRUCTION_PLATFORM_MESSAGE = PlatformState(
    uid=Uid.INVALID,  # non-NaN field
    timestamp=0.,  # non-NaN field
    position=makeReadOnly(full_like(DEFAULT_POSITION, nan)),
    velocity=makeReadOnly(full_like(DEFAULT_VELOCITY, nan)),
    acceleration=makeReadOnly(full_like(DEFAULT_ACCELERATION, nan)),
    orientation=makeReadOnly(full_like(DEFAULT_ORIENTATION, nan)),
    angular_velocity=makeReadOnly(full_like(DEFAULT_ANGULAR_VELOCITY, nan)),
)

# Track Data denoting a drop track. To send an appropriate message,
# then the time should be more recent than any of the newest track messages
# and also the id's should also be valid
DROP_TRACK_MESSAGE = TrackData(
    reporter_uid=Uid.INVALID,  # non-NaN field
    group_id=GroupId.INVALID,  # non-NaN field
    track_id=TrackId.INVALID,  # non-NaN field
    timestamp=0.,  # non-NaN field
    position=makeReadOnly(full_like(DEFAULT_POSITION, nan)),
    velocity=makeReadOnly(full_like(DEFAULT_VELOCITY, nan)),
    acceleration=makeReadOnly(full_like(DEFAULT_ACCELERATION, nan)),
    covariance=makeReadOnly(full_like(DEFAULT_POSITION_VELOCITY_ACCELERATION_COVARIANCE, nan)),
)
