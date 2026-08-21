# -*- coding: utf-8 -*-
""" This module contains the definitions of the message types that will be sent during the simulation, and their expected channels """
from __future__ import annotations

import sys
from collections.abc import Collection as AbcCollection, Hashable as AbcHashable
from functools import total_ordering
from typing import Any, ClassVar, Collection, Dict, Iterator, Optional, Sequence, Tuple, Union, overload

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import AggregateFieldMetadata, CallerIds, IntFieldMetadata, RepeatedFieldMetadata, SettingsInterface

__all__ = (
    'EmissionId', 'EmissionReturnUid',
    'EmissionUid', 'GroupId', 'Uid',
    'TrackId', 'TrackUid',
)
########################
log = getCleanLogger(__name__)

########
_abcs_have_typing: bool = sys.version_info[0:2] >= (3, 9,)

_uid_parent_classes: Tuple[Any, ...]
if _abcs_have_typing:
  _uid_parent_classes = (AbcCollection[int], AbcHashable,)  # pragma: no cover
else:
  _uid_parent_classes = (AbcCollection, Collection[int], AbcHashable,)  # pragma: no cover
##
########


@total_ordering
class Uid(*_uid_parent_classes):  # type: ignore[misc]
  """ Unique ID for the simulation given to updateable objects """
  ROOT: ClassVar[Uid]
  INVALID: ClassVar[Uid]

  __slots__ = ('__data',)

  def __init__(self, uid: Optional[Union[Uid, Tuple[int, ...]]] = None, ):
    super().__init__()
    self.__data: Tuple[int, ...]
    if uid is None:
      self.__data = tuple()
    else:
      self.__data = tuple(uid)
    ##
  ##

  @property
  def is_root(self) -> bool:
    return self == self.ROOT
  ##

  @property
  def is_valid(self) -> bool:
    return (self.is_root or self > self.INVALID)
  ##

  @property
  def parent(self) -> Uid:
    return Uid(self[:-1])
  ##

  def __len__(self) -> int:
    return len(self.__data)
  ##

  def __iter__(self) -> Iterator[int]:
    yield from self.__data
  ##

  @overload
  def __getitem__(self, item: int) -> int:
    """ Overload for getitem single value """

  @overload
  def __getitem__(self, item: slice) -> Uid:
    """ Overload for getitem slice """

  def __getitem__(self, item: Union[int, slice]) -> Union[int, Uid]:
    if isinstance(item, int):
      return self.__data[item]
    else:
      return Uid(self.__data[item])
    ##
  ##

  def __contains__(self, item: int) -> bool:
    return item in self.__data
  ##

  def __eq__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.__data == other.__data
    ##
    return NotImplemented
  ##

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.__data < other.__data
    ##
    return NotImplemented
  ##

  def __hash__(self) -> int:
    return hash(self.__data)
  ##

  def __truediv__(self, rhs: Union[Uid, Sequence[int]]) -> Uid:
    """ Returns a new UID with the rhs appended to the end """
    if isinstance(rhs, Uid):
      return Uid(self.__data + rhs.__data)
    else:
      return Uid(self.__data + tuple(r for r in rhs))
    ##
  ##

  def __rtruediv__(self, lhs: Union[Uid, Tuple[int, ...], Sequence[int]]) -> Uid:
    """ Returns a new UID with the lhs prepended to the beginning """
    if isinstance(lhs, Uid):
      return Uid(lhs.__data + self.__data)
    else:
      return Uid(tuple(x for x in lhs) + self.__data)
    ##
  ##

  def __add__(self, rhs: int) -> Uid:
    """ Returns a new UID with the tail incremented by the value """
    if isinstance(rhs, (int, float,)):
      return Uid(self.__data[:-1] + (int(self.__data[-1] + rhs),))
    ##
    raise TypeError(f'Cannot add type:{type(rhs).__name__} to {type(self).__name__}. rhs:{rhs}')
  ##

  def __radd__(self, lhs: int) -> Uid:
    """ Returns a new UID with the tail incremented by the value """
    if isinstance(lhs, (int, float,)):
      return Uid(self.__data[:-1] + (int(self.__data[-1] + lhs),))
    ##
    raise TypeError(f'Cannot add type:{type(lhs).__name__} to {type(self).__name__}. lhs:{lhs}')
  ##

  def __repr__(self) -> str:
    return repr(self.__data)
  ##

  @classmethod
  def getConfigMetadata(cls) -> RepeatedFieldMetadata:
    out = RepeatedFieldMetadata.createZeroOrMoreRepeat(
        label='UID',
        description='Sequence of integers that uniquely identify this object.\nAn ID of (0,) indicates an invalid ID.',
        optional=False,
        repeat_label='Number of IDs',
        repeat_description=None,
        value=IntFieldMetadata(
            label='ID number',
            description='ID number. 0 indicates an invalid ID',
            optional=False,
            default=None,
            min_value=0,
            max_value=None,
        ),
    )
    return out
  ##
##


Uid.ROOT = Uid()
Uid.INVALID = Uid((0,))


class GroupId(int):
  """ Not universally unique, but should be unique to reporter, though not guaranteed """
  INVALID: ClassVar[GroupId]

  @property
  def is_valid(self) -> bool:
    return self > self.INVALID
  ##

  @classmethod
  def getConfigMetadata(cls) -> IntFieldMetadata:
    out = IntFieldMetadata(
        label='Group ID',
        description=(
            "Group ID's indicate tracks or emissions that come from a similar source."
            "\nFor tracks the group ID usually indicates the designation track ID."
            "\nFor emissions the group ID usually indicates emissions used for a single track ID."
            "\nZero indicates an invalid Group id."
        ).strip(),
        optional=False,
        default=cls.INVALID,
        min_value=0,
        max_value=None,
    )
    return out
  ##

##


GroupId.INVALID = GroupId(0)


class TrackId(int):
  """ Not universally unique, but should be unique to reporter, though not guaranteed """
  INVALID: ClassVar[TrackId]

  @property
  def is_valid(self) -> bool:
    return self > self.INVALID
  ##

  @classmethod
  def getConfigMetadata(cls) -> IntFieldMetadata:
    out = IntFieldMetadata(
        label='Track ID',
        description="Track ID's indicate a single track. Should the track drop and pick up the number may increment",
        optional=False,
        default=cls.INVALID,
        min_value=0,
        max_value=None,
    )
    return out
  ##

##


TrackId.INVALID = TrackId(0)


class EmissionId(int):
  """ Not universally unique, but should be unique to reporter, though not guaranteed """
  INVALID: ClassVar[EmissionId]

  @property
  def is_valid(self) -> bool:
    return self > self.INVALID
  ##

  @classmethod
  def getConfigMetadata(cls) -> IntFieldMetadata:
    out = IntFieldMetadata(
        label='Emission ID',
        description="Emission ID's indicate a single emission from an emitter.",
        optional=False,
        default=cls.INVALID,
        min_value=0,
        max_value=None,
    )
    return out
  ##
##


EmissionId.INVALID = EmissionId(0)


@total_ordering
class EmissionUid(SettingsInterface, AbcHashable):
  """ Tuple of the structure's source UID, emission ID, and group id. This will most likely give a unique identifier for this Emission as long as the source keeps the emission and group id's unique. """
  INVALID: ClassVar[EmissionUid]
  __slots__ = ('__data', '__cache_repr',)

  def __init__(self, source_uid: Uid, group_id: GroupId, emission_id: EmissionId, ):
    super().__init__()
    self.__data: Tuple[Uid, GroupId, EmissionId] = (source_uid, group_id, emission_id,)
    self.__cache_repr: Optional[str] = None
  ##

  @property
  def source_uid(self) -> Uid:
    return self.__data[0]
  ##

  @property
  def group_id(self) -> GroupId:
    return self.__data[1]
  ##

  @property
  def emission_id(self) -> EmissionId:
    return self.__data[2]
  ##

  @property
  def is_valid(self) -> bool:
    return (
        self.__data[0].is_valid and
        self.__data[1].is_valid and
        self.__data[2].is_valid
    )
  ##

  def __iter__(self) -> Iterator[Union[Uid, GroupId, EmissionId]]:
    yield self.__data[0]
    yield self.__data[1]
    yield self.__data[2]
  ##

  def replace(self, *,
              source_uid: Optional[Uid] = None,
              group_id: Optional[GroupId] = None,
              emission_id: Optional[EmissionId] = None,
              ) -> EmissionUid:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param source_uid: value to be replaced if not None
    @param group_id: value to be replaced if not None
    @param emission_id: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = EmissionUid(
        source_uid=self.source_uid if source_uid is None else source_uid,
        group_id=self.group_id if group_id is None else group_id,
        emission_id=self.emission_id if emission_id is None else emission_id,
    )
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    return self.__data == other.__data
  ##

  def __lt__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return NotImplemented
    ##
    return self.__data < other.__data
  ##

  def __hash__(self) -> int:
    return hash(self.__data)
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'source_uid={self.__data[0]!r}, ' \
                          f'group_id={self.__data[1]!r}, ' \
                          f'emission_id={self.__data[2]!r})'
    ##
    return self.__cache_repr
  ##

  def _asConfig(self, caller_ids: Optional[CallerIds]) -> Dict[str, Any]:
    out = {
        'source_uid': list(self.source_uid),
        'group_id': int(self.group_id),
        'emission_id': int(self.emission_id),
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Emission UID',
        description="""Combination of IDs to make a unique ID.""",
        optional=False,
        fields={
            'source_uid': Uid.getConfigMetadata().replace(
                label='Source UID',
                description='UID of the emitter source',
            ),
            'group_id': GroupId.getConfigMetadata().replace(
                description='Emission group ID. Usually indicates which the Track ID this correspond to.',
            ),
            'emission_id': EmissionId.getConfigMetadata(),
        }
    )
    return out
  ##

##


EmissionUid.INVALID = EmissionUid(source_uid=Uid.INVALID, group_id=GroupId.INVALID, emission_id=EmissionId.INVALID, )


@total_ordering
class EmissionReturnUid(SettingsInterface, AbcHashable):
  """ Tuple of the structure's source UID, reflector UID, and the emission ID.
  This will most likely give a unique identifier
  for this EmissionReturn as long as the source keeps the emission id's unique """
  INVALID: ClassVar[EmissionReturnUid]

  __slots__ = ('__data', '__cache_repr',)

  def __init__(self, source_uid: Uid, reflector_uid: Uid, receiver_uid: Uid, emission_id: EmissionId, ):
    super().__init__()
    self.__data: Tuple[Uid, Uid, Uid, EmissionId] = (source_uid, reflector_uid, receiver_uid, emission_id,)
    self.__cache_repr: Optional[str] = None
  ##

  @property
  def source_uid(self) -> Uid:
    return self.__data[0]
  ##

  @property
  def reflector_uid(self) -> Uid:
    return self.__data[1]
  ##

  @property
  def receiver_uid(self) -> Uid:
    return self.__data[2]
  ##

  @property
  def emission_id(self) -> EmissionId:
    return self.__data[3]
  ##

  @property
  def is_valid(self) -> bool:
    return (
        self.__data[0].is_valid and
        self.__data[1].is_valid and
        self.__data[2].is_valid and
        self.__data[3].is_valid
    )
  ##

  def replace(self, *,
              source_uid: Optional[Uid] = None,
              reflector_uid: Optional[Uid] = None,
              receiver_uid: Optional[Uid] = None,
              emission_id: Optional[EmissionId] = None,
              ) -> EmissionReturnUid:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param source_uid: value to be replaced if not None
    @param reflector_uid: value to be replaced if not None
    @param receiver_uid: value to be replaced if not None
    @param emission_id: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = EmissionReturnUid(
        source_uid=self.source_uid if source_uid is None else source_uid,
        reflector_uid=self.reflector_uid if reflector_uid is None else reflector_uid,
        receiver_uid=self.receiver_uid if receiver_uid is None else receiver_uid,
        emission_id=self.emission_id if emission_id is None else emission_id,
    )
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    return self.__data == other.__data
  ##

  def __lt__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return NotImplemented
    ##
    return self.__data < other.__data
  ##

  def __iter__(self) -> Iterator[Union[Uid, EmissionId]]:
    yield self.__data[0]
    yield self.__data[1]
    yield self.__data[2]
    yield self.__data[3]
  ##

  def __hash__(self) -> int:
    return hash(self.__data)
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'source_uid={self.__data[0]!r}, ' \
                          f'reflector_uid={self.__data[1]!r}, ' \
                          f'receiver_uid={self.__data[2]!r}, ' \
                          f'emission_id={self.__data[3]!r})'
    ##
    return self.__cache_repr
  ##

  def _asConfig(self, caller_ids: Optional[CallerIds]) -> Dict[str, Any]:
    out = {
        'source_uid': list(self.source_uid),
        'reflector_uid': list(self.reflector_uid),
        'receiver_uid': list(self.receiver_uid),
        'emission_id': int(self.emission_id),
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Emission Return UID',
        description="""Combination of IDs to make a unique ID.""",
        optional=False,
        fields={
            'source_uid': Uid.getConfigMetadata().replace(
                label='Source UID',
                description='UID of the emitter source',
            ),
            'reflector_uid': Uid.getConfigMetadata().replace(
                label='Reflector UID',
                description='UID of the reflector',
            ),
            'receiver_uid': Uid.getConfigMetadata().replace(
                label='Receiver UID',
                description='UID of the emission receiver',
            ),
            'emission_id': EmissionId.getConfigMetadata(),
        }
    )
    return out
  ##

##


EmissionReturnUid.INVALID = EmissionReturnUid(source_uid=Uid.INVALID, reflector_uid=Uid.INVALID, receiver_uid=Uid.INVALID, emission_id=EmissionId.INVALID)


@total_ordering
class TrackUid(SettingsInterface, AbcHashable):
  """ Tuple of the structure's reporter UID and the track's id.
  This will most likely give a unique identifier for this TrackData as long as the reporter keeps the track id's unique """
  INVALID: ClassVar[TrackUid]

  __slots__ = ('__data', '__cache_repr',)

  def __init__(self, reporter_uid: Uid, group_id: GroupId, track_id: TrackId, ):
    super().__init__()
    self.__data: Tuple[Uid, GroupId, TrackId] = (reporter_uid, GroupId(group_id), TrackId(track_id),)
    self.__cache_repr: Optional[str] = None
  ##

  @property
  def reporter_uid(self) -> Uid:
    return self.__data[0]
  ##

  @property
  def group_id(self) -> GroupId:
    return self.__data[1]
  ##

  @property
  def track_id(self) -> TrackId:
    return self.__data[2]
  ##

  @property
  def is_valid(self) -> bool:
    return (
        self.__data[0].is_valid and
        self.__data[1].is_valid and
        self.__data[2].is_valid
    )
  ##

  def replace(self, *,
              reporter_uid: Optional[Uid] = None,
              group_id: Optional[GroupId] = None,
              track_id: Optional[TrackId] = None,
              ) -> TrackUid:
    """ Returns another instance with fields replaced if given as keyword argument,
    otherwise the same value is kept

    @param reporter_uid: value to be replaced if not None
    @param group_id: value to be replaced if not None
    @param track_id: value to be replaced if not None
    @return: same struct but with replaced fields as given
    """
    out = TrackUid(
        reporter_uid=self.reporter_uid if reporter_uid is None else reporter_uid,
        group_id=self.group_id if group_id is None else group_id,
        track_id=self.track_id if track_id is None else track_id,
    )
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    return self.__data == other.__data
  ##

  def __lt__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return NotImplemented
    ##
    return self.__data < other.__data
  ##

  def __iter__(self) -> Iterator[Union[Uid, GroupId, TrackId]]:
    yield self.__data[0]
    yield self.__data[1]
    yield self.__data[2]
  ##

  def __hash__(self) -> int:
    return hash(self.__data)
  ##

  def __repr__(self) -> str:
    if self.__cache_repr is None:
      self.__cache_repr = f'{type(self).__name__}(' \
                          f'reporter_uid={self.__data[0]!r}, ' \
                          f'group_id={self.__data[1]!r}, ' \
                          f'track_id={self.__data[2]!r})'
    ##
    return self.__cache_repr
  ##

  def _asConfig(self, caller_ids: Optional[CallerIds]) -> Dict[str, Any]:
    out = {
        'reporter_uid': list(self.reporter_uid),
        'group_id': int(self.group_id),
        'track_id': int(self.track_id),
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Track UID',
        description="""Combination of IDs to make a unique ID.""",
        optional=False,
        fields={
            'reporter_uid': Uid.getConfigMetadata().replace(
                label='Reporter UID',
                description='UID of the track reporter',
            ),
            'group_id': GroupId.getConfigMetadata(),
            'track_id': TrackId.getConfigMetadata(),
        }
    )
    return out
  ##

##


TrackUid.INVALID = TrackUid(reporter_uid=Uid.INVALID, group_id=GroupId.INVALID, track_id=TrackId.INVALID)
