# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import MISSING, dataclass, fields as getDataclassFields
from enum import Enum
from fractions import Fraction
from pathlib import Path
from pprint import pformat
from typing import Any, ClassVar, Dict, Generator, List, Mapping, Optional, Pattern, Sequence, Tuple, Type, TypeVar, Union

from numpy import inf, isnan, ndarray, pi

from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.dataclass_util import dataclassIsEqual, dataclassRepr
from exhaust_plume.util.enum_util import normalizeEnumNameForMapping
from exhaust_plume.util.unset_util import Unset, UnsetType

__all__ = (
    'SettingsInterface',
    ####
    'FieldMetadata',
    'BasicFieldMetadata',
    'AnyFieldMetadata',
    'ConstantFieldMetadata',
    'IntFieldMetadata',
    'FloatFieldMetadata',
    'ChoiceFieldMetadata',
    'RepeatedFieldMetadata',
    'AggregateFieldMetadata',
    'SwitchFieldMetadata',
    'PathFieldMetadata',
    'MappingFieldMetadata',
    'StringFieldMetadata',
    ###
    'PhysicalUnitValue',
    'PhysicalUnit',
    ####
    'Decibel',
    'Degree',
    'Hertz',
    'Joule',
    'Kilogram',
    'Kilometer',
    'Meter',
    'Newton',
    'Radian',
    'Second',
    'Sines',
    'Watt',
    ###
    'Peta',
    'Tera',
    'Giga',
    'Mega',
    'Kilo',
    'Centi',
    'Milli',
    'Micro',
    'Nano',
)

###################################
log = getCleanLogger(__name__)

# TODO-List:
# - add code to output description of object config option
# - add code to check if field is mis-capitalized when parsing config.

CallerIds = Tuple[Optional[int], ...]


class SettingsInterface(ABC):

  def asConfig(self, caller_ids: Optional[CallerIds] = None) -> Dict[str, Any]:
    # Check for recursion!
    if caller_ids is None:  # TODO This is a hack -
      caller_ids = tuple()
    ##
    id_self = id(self)
    try:
      found_idx = caller_ids.index(id_self)
      return RecursedConfig(
          class_name=type(self).__name__,
          total_depth=len(caller_ids),  # because id_self has yet to be added to list
          levels_up=len(caller_ids) - found_idx,
      ).asConfig(caller_ids)
    except ValueError:
      pass
    ##
    return self._asConfig(caller_ids + (id_self,))
  ##

  @abstractmethod
  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    ...
  ##

  @abstractmethod
  def __eq__(self, other: object) -> bool:
    pass
  ##

  @abstractmethod
  def __repr__(self) -> str:
    pass
  ##

  # TODO[future] - Re-add as abstract method
  @classmethod
  def getConfigMetadata(cls) -> BasicFieldMetadata:
    raise NotImplementedError('Not Implemented')
  ##
##


@dataclass(frozen=True)
class RecursedConfig(SettingsInterface):
  config_metadata: ClassVar[AggregateFieldMetadata]
  class_name: Optional[str]
  total_depth: int
  levels_up: int

  def __post_init__(self) -> None:
    super().__init__()
    if self.levels_up > self.total_depth:
      raise ValueError(f'{type(self).__name__} seems to have invalid level up:{self.levels_up} which is greater than total depth:{self.total_depth}')
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "RecursedConfig"
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def replace(self, *,
              class_name: Union[UnsetType, Optional[str]] = Unset,
              total_depth: Optional[int] = None,
              levels_up: Optional[int] = None,
              ) -> RecursedConfig:
    out = RecursedConfig(
        class_name=self.class_name if isinstance(class_name, UnsetType) else class_name,
        total_depth=self.total_depth if total_depth is None else total_depth,
        levels_up=self.levels_up if levels_up is None else levels_up,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'class_name': self.class_name,
        'total_depth': self.total_depth,
        'levels_up': self.levels_up,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> RecursedConfig:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    # Reuses the same intrusive key as metadata config
    if _metadata_intrusive_key in config:
      intrusive_key = str(config.pop(_metadata_intrusive_key))
      config_typename = cls.getConfigTypename()
      if normalizeEnumNameForMapping(intrusive_key) != config_typename.lower():
        raise ValueError(f'{debug_config_prefix}: Intrusive key {_metadata_intrusive_key}:{intrusive_key} did not match {config_typename},'
                         f' meaning this config does not represent a value of type {cls.__name__}.'
                         f' Config:{config}')
      ##
    ##
    class_name = config.pop('class_name')
    if class_name is not None:
      class_name = str(class_name)
    ##
    out = RecursedConfig(
        class_name=class_name,
        total_depth=int(config.pop('total_depth')),
        levels_up=int(config.pop('levels_up')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents the event that recursion has occurred in the config and how many levels up the recursion started',
        optional=False,
        fields={
            'class_name': StringFieldMetadata(
                label='Class Name',
                description='Name of the class where this recursion occurred.',
                default=f_defaults['class_name'],
                optional=True,
            ),
            'total_depth': IntFieldMetadata(
                label='Levels',
                description='How deep field is from the root level of the config.',
                default=f_defaults['total_depth'],
                optional=False,
                min_value=1,
                max_value=None,
            ),
            'levels_up': IntFieldMetadata(
                label='Levels',
                description='How many levels up the recursion starts',
                default=f_defaults['levels_up'],
                optional=False,
                min_value=1,
                max_value=None,
            ),
        }
    )
    return out
  ##

##

######################################################


@dataclass(frozen=True)
class PhysicalUnitValue(SettingsInterface):
  power: Union[int, Fraction] = 1
  value: Union[int, float] = 1

  def __post_init__(self) -> None:
    if not isinstance(self.power, (int, Fraction,)):
      object.__setattr__(self, 'power', Fraction(self.power))
    ##
    if not isinstance(self.value, int) and (self.value == int(self.value)):
      # convert to int if equal
      object.__setattr__(self, 'value', int(self.value))
    ##
  ##

  def invert(self) -> PhysicalUnitValue:
    return PhysicalUnitValue(-self.power, 1 / self.value)
  ##

  def __mul__(self, rhs: Union[int, float, Fraction, PhysicalUnitValue]) -> PhysicalUnitValue:
    new_value: Union[int, float, Fraction]
    if isinstance(rhs, PhysicalUnitValue):
      new_value = self.value * rhs.value
      nv_int = int(new_value)
      return PhysicalUnitValue(self.power + rhs.power, nv_int if (new_value == nv_int) else float(new_value))
    ##
    # if plain number, then treated as unitless
    if rhs == int(rhs):
      rhs = int(rhs)  # cast to int if possible
    ##
    new_value = self.value * rhs
    nv_int = int(new_value)
    return PhysicalUnitValue(self.power, nv_int if (new_value == nv_int) else float(new_value))
  ##

  def __rmul__(self, lhs: Union[int, float, Fraction, PhysicalUnitValue]) -> PhysicalUnitValue:
    return (self * lhs)  # multiplication is commutative
  ##

  def __truediv__(self, rhs: Union[int, float, Fraction, PhysicalUnitValue]) -> PhysicalUnitValue:
    # eg. (4 m / 4 m) = 1
    if isinstance(rhs, PhysicalUnitValue):
      return (self * rhs.invert())
    ##
    return self * (1 / rhs)
  ##

  def __rtruediv__(self, lhs: Union[int, float, Fraction, PhysicalUnitValue]) -> PhysicalUnitValue:
    # lhs / self
    return (lhs * self.invert())
  ##

  def __pow__(self, rhs: Union[int, float, Fraction]) -> PhysicalUnitValue:
    if not isinstance(rhs, int):
      rhs = Fraction(rhs)
    ##
    return PhysicalUnitValue(self.power * rhs, self.value**rhs)
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

  def replace(self, *,
              power: Optional[Union[int, Fraction]] = None,
              value: Optional[Union[int, float]] = None,
              ) -> PhysicalUnitValue:
    out = PhysicalUnitValue(
        power=self.power if power is None else power,
        value=self.value if value is None else value,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    if isinstance(self.power, Fraction):
      power_config = {
          'numerator': self.power.numerator,
          'denominator': self.power.denominator,
      }
    else:
      power_config = {
          'numerator': self.power,
          'denominator': 1,
      }
    ##
    out = {
        'value': float(self.value),
        'power': power_config,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PhysicalUnitValue:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    power_config = config.pop('power')
    power: Union[int, Fraction]
    if isinstance(power_config, (str, int,)):
      power = int(power_config)
    else:
      # fraction
      power = Fraction(
          numerator=int(power_config.pop('numerator')),
          denominator=int(power_config.pop('denominator')),
      )
    ##
    out = PhysicalUnitValue(
        value=float(config.pop('value')),
        power=power,
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    power_default = f_defaults['power']
    if power_default is not None:
      power_default = Fraction(power_default)
    ##
    out = AggregateFieldMetadata(
        label='Physical Unit',
        description='Represents a single physical unit',
        fields={
            'value': FloatFieldMetadata.createFinite(
                label='Value',
                description='Scale factor for this particular unit.'
                            ' Typically defaulted to one.'
                            ' Non-one values are used to indicate a scale factor.'
                            ' When combined with other physical units, the scale factors are collected into a single unitless value.',
                units=None,
                default=f_defaults['value'],
            ),
            'power': AggregateFieldMetadata(  # TODO[improvement] make untagged switch
                label='Exponent of the unit',
                description=None,
                fields={
                    'numerator': IntFieldMetadata(
                        label='Numerator',
                        description=None,
                        default=power_default.numerator if power_default is not None else None,
                        min_value=None,
                        max_value=None,
                        optional=False,
                    ),
                    'denominator': IntFieldMetadata(
                        label='Denominator',
                        description=None,
                        default=power_default.denominator if power_default is not None else None,
                        min_value=None,
                        max_value=None,
                        optional=False,
                    ),
                },
                optional=False,
            ),
        },
        optional=False,
    )
    return out
  ##
##


@dataclass(frozen=True)
class PhysicalUnit(SettingsInterface):
  standard_unit_aliases: ClassVar[Mapping[str, PhysicalUnit]] = {}
  standard_abbreviations: ClassVar[Mapping[Union[str, PhysicalUnit, Tuple[Tuple[str, PhysicalUnitValue], ...]], str]] = {}
  standard_prefixes: ClassVar[Mapping[Union[int, float], str]] = {}
  unitless_unit: ClassVar[str] = ''

  units: Mapping[str, PhysicalUnitValue]
  name: Optional[str] = None

  def __post_init__(self) -> None:
    if not self.units:
      object.__setattr__(self, 'units', {self.unitless_unit: _PUV1})
    ##
  ##

  @cached_property
  def is_unitless(self) -> bool:
    if len(self.units) != 1:
      return len(self.units) == 0
    ##
    return self.unitless_unit in self.units
  ##

  @cached_property
  def total_value(self) -> Union[int, float]:
    total: Union[int, float] = 1  # try to keep as int at start
    for u in self.units.values():
      total *= u.value
    ##
    return total
  ##

  @cached_property
  def abbreviated_name(self) -> Optional[str]:
    name = self.name
    if name is None:
      return self.getCompactString()
    elif name in PhysicalUnit.standard_abbreviations:
      standard_alias = PhysicalUnit.standard_abbreviations[name]
      if isinstance(standard_alias, PhysicalUnit):
        return standard_alias.name
      else:
        return standard_alias
      ##
    elif name:
      return name
    ##
    return self.getCompactString()
  ##

  def invert(self) -> PhysicalUnit:
    units = {k: v.invert() for k, v in self.units.items()}
    if self.unitless_unit in units:
      units[self.unitless_unit] = units[self.unitless_unit].replace(power=1)
    ##
    return PhysicalUnit(PhysicalUnit.normalizeUnits(units))
  ##

  def replace(
      self, *,
      units: Optional[Mapping[str, PhysicalUnitValue]] = None,
      name: Union[UnsetType, Optional[str]] = Unset,
  ) -> PhysicalUnit:
    out = PhysicalUnit(
        units=self.units if units is None else units,
        name=self.name if isinstance(name, UnsetType) else name,
    )
    return out
  ##

  def __mul__(self, rhs: Union[int, float, Fraction, PhysicalUnit]) -> PhysicalUnit:
    if not isinstance(rhs, PhysicalUnit):
      # scalar
      if rhs == 0:
        return PhysicalUnit({})
      elif rhs == 1:
        return self
      ##
      uu = self.units.get(self.unitless_unit, _PUV1) * rhs
      return PhysicalUnit({**self.units, self.unitless_unit: uu})
    ##
    kw = {**self.units}
    for k, v in rhs.units.items():
      if k in kw:
        if k == self.unitless_unit:
          kw[k] *= rhs.units[k].value
        else:
          kw[k] *= rhs.units[k]
        ##
      else:
        kw[k] = v
      ##
    ##
    return PhysicalUnit(PhysicalUnit.normalizeUnits(kw))
  ##

  def __rmul__(self, lhs: Union[int, float, Fraction, PhysicalUnit]) -> PhysicalUnit:
    return (self * lhs)  # multiplication is commutative
  ##

  def __truediv__(self, rhs: Union[int, float, Fraction, PhysicalUnit]) -> PhysicalUnit:
    if isinstance(rhs, PhysicalUnit):
      return self * (rhs.invert())
    ##
    return self * (1 / rhs)
  ##

  def __rtruediv__(self, lhs: Union[int, float, Fraction, PhysicalUnit]) -> PhysicalUnit:
    # lhs / self
    return lhs * (self.invert())
  ##

  def __pow__(self, rhs: Union[int, Fraction]) -> PhysicalUnit:
    if rhs == 0:
      return PhysicalUnit({PhysicalUnit.unitless_unit: _PUV1})
    ##
    if rhs == 1:
      return self
    ##
    new_units = {**self.units}
    for k, v in new_units.items():
      new_units[k] = v**rhs
    ##
    return PhysicalUnit(PhysicalUnit.normalizeUnits(new_units))
  ##

  def __hash__(self) -> int:
    return hash((tuple(self.units.items()), self.name,))
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

  def getCompactString(self) -> str:
    if not self.units:
      return ''
    ##
    pieces = []
    total_value = self.total_value
    first_unit_prefix = ''
    if self.unitless_unit in self.units:
      is_single_unit = len(self.units) == 2
    else:
      is_single_unit = len(self.units) == 1
    ##
    if total_value != 1:
      if total_value in self.standard_prefixes and is_single_unit:
        first_unit_prefix = self.standard_prefixes[total_value]
      else:
        pieces.append(f'{total_value}')
      ##
    ##
    neg_pieces: List[str] = []
    for idx, name in enumerate(k for k in self.units.keys() if k != self.unitless_unit):
      if name is None:
        continue
      ##
      v = self.units[name]
      name_unit = ((name, v,),)
      if name in self.standard_abbreviations:
        name = self.standard_abbreviations[name]
      elif is_single_unit and name_unit in self.standard_abbreviations:
        name = self.standard_abbreviations[name_unit]
        v = _PUV1  # NOTE if a standard abbreviated unit key has some (value then the total value will be incorrect)
      ##
      if v.power == 1:
        power_s = ''
      else:
        num: Optional[int]
        den: Optional[int]
        if isinstance(v.power, Fraction):
          num = v.power.numerator
          den = v.power.denominator
        else:
          num = v.power
          den = None
        ##
        if den == 1:
          den = None
        ##
        if not is_single_unit:
          num = abs(num)
          if num == 1 and den is None:
            num = None
          ##
        ##
        if num is None:
          power_s = ''
        elif den is None:
          power_s = f'^{num}'
        else:
          power_s = f'^({num}/{den})'
        ##
      ##
      piece = (first_unit_prefix if idx == 0 else '') + name + power_s
      if v.power >= 0:
        pieces.append(piece)
      else:
        neg_pieces.append(piece)
      ##
    ##
    if neg_pieces:
      if not is_single_unit:
        pieces.append('/')
      ##
      if len(neg_pieces) > 1:
        pieces.append('(')
      ##
      pieces.extend(neg_pieces)
      if len(neg_pieces) > 1:
        pieces.append(')')
      ##
    ##
    return ' '.join(pieces)
  ##

  def normalize(self) -> PhysicalUnit:
    return PhysicalUnit(units=PhysicalUnit.normalizeUnits(self.units), name=self.name)
  ##

  def standardize(self) -> PhysicalUnit:
    return PhysicalUnit(units=PhysicalUnit.standardizeUnits(self.units), name=self.name)
  ##

  @classmethod
  def fromString(cls,
                 units_string: str,
                 name: Optional[str] = None,
                 normalize: bool = True,
                 standardize: bool = False,
                 ) -> PhysicalUnit:
    units = {k: PhysicalUnitValue(power=v, value=1) for k, v in _parse(units_string).items()}
    if normalize:
      units = cls.normalizeUnits(units)
    ##
    if standardize:
      units = cls.standardizeUnits(units)
    ##
    return PhysicalUnit(units, name=name)
  ##

  @classmethod
  def normalizeUnits(cls, units: Mapping[str, PhysicalUnitValue]) -> Dict[str, PhysicalUnitValue]:
    if not units:
      return {}
    ##
    units = {**units}
    null_units = {k: v for k, v in units.items() if v.power == 0}
    for k, v in null_units.items():
      del units[k]
    ##
    unit_total_value: Union[int, float] = 1
    for k, v in units.items():
      if v.value != 1:
        unit_total_value *= v.value
        units[k] = PhysicalUnitValue(power=v.power, value=1)
      ##
    ##
    if unit_total_value != 1:
      units[cls.unitless_unit] = units.get(cls.unitless_unit, _PUV1) * unit_total_value
    ##
    if cls.unitless_unit in units:
      uu = units.get(cls.unitless_unit, _PUV1)
      if uu.value == 1:
        del units[cls.unitless_unit]
      elif uu.power != 1:
        units[cls.unitless_unit] = PhysicalUnitValue(power=1, value=uu.value**(uu.power))
      ##
    ##
    return units
  ##

  @classmethod
  def standardizeUnits(cls, units: Mapping[str, PhysicalUnitValue]) -> Dict[str, PhysicalUnitValue]:
    units = {**units}
    units_to_replace = {}
    for k, v in units.items():
      if k in cls.standard_unit_aliases and v != cls.standard_unit_aliases[k]**v.power:
        units_to_replace[k] = v
      ##
    ##
    if not units_to_replace:
      return units
    ##
    total_pu = PhysicalUnit(units)
    for k, v in units_to_replace.items():
      replacement_unit = cls.standard_unit_aliases[k]**v.power
      old_unit = PhysicalUnit({k: v})
      scale_pu = replacement_unit / old_unit
      total_pu = total_pu * scale_pu
    ##
    out = {**total_pu.units}
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        'units': {name: unit.asConfig(caller_ids) for name, unit in self.units.items()},
        'name': self.name,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PhysicalUnit:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    overall_name = config['name'] if 'name' in config else None
    if overall_name is not None:
      overall_name = str(overall_name)
    ##
    units_config = config.pop('units')
    units = {}
    for name, unit_config in units_config.items():
      unit = PhysicalUnitValue.fromConfig(unit_config, f'{debug_config_prefix}.units.{name}')
      units[name] = unit
    ##
    out = PhysicalUnit(
        name=overall_name,
        units=units,
    ).normalize()
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    out = AggregateFieldMetadata(
        label='Physical Unit',
        description='The unit or combination of units that describe a value.',
        optional=False,
        fields={
            'name': StringFieldMetadata(
                label='Name',
                description='An alias or simple name for this unit. Eg. Newton for "kg m / s^2"',
                optional=True,
                default=f_defaults['name'],
            ),
            'units': MappingFieldMetadata(
                label='Units',
                description='Series of physical units that comprise this entire unit',
                optional=False,
                value=PhysicalUnitValue.getConfigMetadata(),
            ),
        }
    )
    return out
  ##
##

######################################################


class FieldMetadata(SettingsInterface):
  @classmethod
  @abstractmethod
  def getConfigTypename(cls) -> str:
    ...
  ##

  @abstractmethod
  def unpackValue(self, value: Any, check_value: bool = False) -> Any:
    """ Unpacks metadata config to expected config object """
  ##

  @abstractmethod
  def packValue(self, config_value: Any, check_value: bool = False) -> Any:
    """ Takes in setting config (value for scalar fields) and returns a generic metadata config (value for scalar fields)"""
  ##

  @abstractmethod
  def isValueValid(self, value: Any) -> bool:
    pass
  ##

  @classmethod
  @abstractmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    pass
  ##

  @classmethod
  @abstractmethod
  def fromConfig(cls: Type[F], config: Mapping[str, Any], debug_config_prefix: str = '') -> BasicFieldMetadata:
    pass
  ##

  @classmethod
  def _checkConfigIntrusiveKey(cls, config: Dict[str, Any], debug_config_prefix: str) -> None:
    if _metadata_intrusive_key in config:
      intrusive_key = str(config.pop(_metadata_intrusive_key))
      if normalizeEnumNameForMapping(intrusive_key) != cls.getConfigTypename().lower():
        raise ValueError(f'{debug_config_prefix}: Intrusive key {_metadata_intrusive_key}:{intrusive_key} did not match {cls.getConfigTypename()},'
                         f' meaning this config does not represent a value of type {cls.__name__}.'
                         f' Config:{config}')
      ##
    ##
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##
##


@dataclass(frozen=True)
class BasicFieldMetadata(FieldMetadata, ABC):
  label: str
  description: Optional[str]
  optional: bool

  def __post_init__(self) -> None:
    if not isinstance(self.label, str):
      raise ValueError(f'Expected `label` to be of type str. Got:{self.label!r}')
    ##
    if self.description is not None and not isinstance(self.description, str):
      raise ValueError(f'Expected `description` to be None or of type str. Got:{self.description!r}')
    ##
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

  @classmethod
  @abstractmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    out = AggregateFieldMetadata(
        label='Descriptive Field',
        description='Metadata field that only holds label and description and no value',
        optional=False,
        fields={
            'label': StringFieldMetadata(
                label='Label',
                description='Short human readable string.',
                default=f_defaults['label'],
                optional=False,
            ),
            'description': StringFieldMetadata(
                label='Description',
                description='Optional longer string describing characteristics of the field',
                default=f_defaults['description'],
                optional=True,
            ),
            'optional': BoolFieldMetadata(
                label='Optional',
                description='Determines if the field itself is optional',
                default=f_defaults['optional'],
                optional=False,
            ),
        }
    )
    return out
  ##
##


@dataclass(frozen=True)
class AnyFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  default: Optional[Any]

  def __post_init__(self) -> None:
    super().__post_init__()
    if isinstance(self.default, ndarray):
      self.default.flags.writeable = False
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "AnyFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[Any]:
    return value
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> T:
    return config_value
  ##

  def isValueValid(self, value: Any) -> bool:
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              default: Union[UnsetType, Optional[Any]] = Unset,
              optional: Optional[bool] = None,
              ) -> AnyFieldMetadata:
    out = AnyFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        default=self.default if isinstance(default, UnsetType) else default,
        optional=self.optional if optional is None else optional,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    configged_default = self.default
    if isinstance(self.default, SettingsInterface):
      configged_default = self.default.asConfig(caller_ids)
    elif isinstance(self.default, tuple):
      configged_default = list(self.default)  # yaml doesn't like tuples
    elif isinstance(self.default, dict):
      for k, v in self.default.items():
        if isinstance(v, SettingsInterface):
          configged_default[k] = v.asConfig(caller_ids)  # type: ignore[index]
        elif isinstance(v, tuple):
          configged_default[k] = list(v)  # type: ignore[index] # yaml doesn't like tuples
        ##
        # Only handle 1 level nested objects for Any default object - generically unpacking could end up with recursion
      ##
    ##
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': configged_default,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> AnyFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    out = AnyFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        default=config.pop('default'),
        optional=bool(config.pop('optional')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains any type of value',
        optional=False,
        fields={
            **super_af.fields,
            'default': AnyFieldMetadata(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
            ),
        }
    )
    return out
  ##

  def __hash__(self) -> int:
    tup = (
        self.label,
        self.description,
        repr(self.default),  # can't guarantee hashability for Any object, but at least this is moderately unique
        self.optional,
    )
    return hash(tup)
  ##

##


@dataclass(frozen=True)
class ConstantFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  value: Any

  def __post_init__(self) -> None:
    super().__post_init__()
    if isinstance(self.value, ndarray):
      self.value.flags.writeable = False
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "ConstantFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = True) -> Optional[Any]:
    if self.optional and value is None:
      return None
    ##
    if check_value:
      if value != self.value:
        raise ValueError(f'Cannot unpack value because it is not equal to the constant. Value:{value}. Expected constant:{self.value}')
      ##
    ##
    return value
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> T:
    if self.optional and config_value is None:
      return None
    ##
    if config_value != self.value:
      raise ValueError(f'Cannot pack value because it is not equal to the constant. Config:{config_value}. Expected constant:{self.value}')
    ##
    return config_value
  ##

  def isValueValid(self, value: Any) -> bool:
    if self.optional and value is None:
      return True
    ##
    return value == self.value
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              value: Union[UnsetType, Optional[Any]] = Unset,
              ) -> ConstantFieldMetadata:
    out = ConstantFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        value=self.value if isinstance(value, UnsetType) else value,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    configged_value = self.value
    if isinstance(self.value, SettingsInterface):
      configged_value = self.value.asConfig(caller_ids)
    elif isinstance(self.value, tuple):
      configged_value = list(self.value)  # yaml doesn't like tuples
    elif isinstance(self.value, dict):
      for k, v in self.value.items():
        if isinstance(v, SettingsInterface):
          configged_value[k] = v.asConfig(caller_ids)
        elif isinstance(v, tuple):
          configged_value[k] = list(v)  # yaml doesn't like tuples
        ##
        # Only handle 1 level nested objects for Any value object - generically unpacking could end up with recursion
      ##
    ##
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'value': configged_value,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> ConstantFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    out = ConstantFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        value=config.pop('value'),
        optional=bool(config.pop('optional')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains any type of value',
        optional=False,
        fields={
            **super_af.fields,
            'value': AnyFieldMetadata(
                label='Value',
                description='Holds constant value',
                default=f_defaults['value'],
                optional=True,
            ),
        }
    )
    return out
  ##

  def __hash__(self) -> int:
    tup = (
        self.label,
        self.description,
        repr(self.value),  # can't guarantee hashability for Any object, but at least this is moderately unique
        self.optional,
    )
    return hash(tup)
  ##

##


@dataclass(frozen=True)
class StringFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  default: Optional[str]

  def __post_init__(self) -> None:
    super().__post_init__()
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "StringFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = True) -> Optional[str]:
    if self.optional and value is None:
      return None
    ##
    if value is not None:
      value = str(value)
    ##
    return value
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> Optional[str]:
    if self.optional and config_value is None:
      return None
    ##
    # casting to string is to permissive (esp. for untagged switches), do a type check
    if not isinstance(config_value, str):
      raise ValueError(f'Config value is not a string. Got:{config_value}')
    ##
    return config_value
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      if self.optional:
        return True
      else:
        return False
      ##
    ##
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              default: Union[UnsetType, Optional[str]] = Unset,
              ) -> StringFieldMetadata:
    out = StringFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        default=self.default if isinstance(default, UnsetType) else default,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': self.default,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> StringFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = str(default)
    ##
    out = StringFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        default=default,
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains a string',
        optional=False,
        fields={
            **super_af.fields,
            'default': StringFieldMetadata(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
            ),
        }
    )
    return out
  ##

##


@dataclass(frozen=True)
class BoolFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  default: Optional[bool]

  def __post_init__(self) -> None:
    super().__post_init__()
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "BoolFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[bool]:
    if self.optional:
      return bool(value) if value is not None else None
    else:
      return bool(value)
    ##
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> Optional[bool]:
    if self.optional and config_value is None:
      return None
    ##
    # casting to bool is to permissive (esp. for untagged switches), do a type check
    if not isinstance(config_value, bool):
      raise ValueError(f'Config value is not a bool. Got:{config_value}')
    ##
    return config_value
  ##

  def isValueValid(self, value: Any) -> bool:
    if not self.optional and value is None:
      return False
    ##
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              default: Union[UnsetType, Optional[bool]] = Unset,
              optional: Optional[bool] = None,
              ) -> BoolFieldMetadata:
    out = BoolFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        default=self.default if isinstance(default, UnsetType) else default,
        optional=self.optional if optional is None else optional,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': self.default,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> BoolFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = bool(default)
    ##
    out = BoolFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        default=default,
        optional=bool(config.pop('optional')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains a bool',
        optional=False,
        fields={
            **super_af.fields,
            'default': BoolFieldMetadata(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
            ),
        }
    )
    return out
  ##

##


@dataclass(frozen=True)
class PathFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  default: Optional[Path]
  path_type: Optional[str]
  error_if_not_exist: bool

  def __post_init__(self) -> None:
    super().__post_init__()
    if self.path_type is not None:
      # Normalize path type enum
      pt = normalizeEnumNameForMapping(self.path_type)
      if pt not in _path_type2label:
        raise ValueError(f'`path_type` is not one of the expected values. Got:{self.path_type!r} Valid choices are:{list(_strict_path_type_option2label.values())}')
      ##
      object.__setattr__(self, 'path_type', _path_type2label[pt])
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "PathFieldMetadata"
  ##

  @property
  def must_be_file(self) -> bool:
    return self.path_type == _path_type_option_label_file
  ##

  @property
  def must_be_dir(self) -> bool:
    return self.path_type == _path_type_option_label_dir
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[Path]:
    if value is None and self.optional:
      return None
    ##
    out = Path(value) if value is not None else None  # type: ignore[arg-type]
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> Optional[Path]:
    if self.optional and config_value is None:
      return None
    ##
    out = Path(config_value) if config_value is not None else None  # type: ignore[arg-type]
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return self.optional
    ##
    value = Path(value)
    if value.exists():
      if self.must_be_file:
        return value.is_file()
      elif self.must_be_dir:
        return value.is_dir()
      ##
    else:
      if self.error_if_not_exist:
        return False
      ##
    ##
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              default: Union[UnsetType, Optional[Path]] = Unset,
              path_type: Union[UnsetType, Optional[str]] = Unset,
              error_if_not_exist: Optional[bool] = None,
              optional: Optional[bool] = None,
              ) -> PathFieldMetadata:
    out = PathFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        default=self.default if isinstance(default, UnsetType) else default,
        path_type=self.path_type if isinstance(path_type, UnsetType) else path_type,
        error_if_not_exist=self.error_if_not_exist if error_if_not_exist is None else error_if_not_exist,
        optional=self.optional if optional is None else optional,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': str(self.default) if self.default is not None else None,
        'path_type': self.path_type,
        'error_if_not_exist': bool(self.error_if_not_exist),
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PathFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = Path(default)
    ##
    path_type = config.pop('path_type')
    if path_type is not None:
      path_type = str(path_type)
    ##
    out = PathFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        default=default,
        path_type=path_type,
        error_if_not_exist=bool(config.pop('error_if_not_exist')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains a Path',
        optional=False,
        fields={
            **super_af.fields,
            'default': PathFieldMetadata(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
                error_if_not_exist=False,
                path_type=None,
            ),
            'path_type': ChoiceFieldMetadata(
                label='Path Type',
                description='Determines if the path should represent a file, a directory, or unspecified',
                optional=True,
                default=f_defaults['path_type'],
                choice2label={normalizeEnumNameForMapping(v): v for v in _strict_path_type_option2label.values()},
            ),
            'error_if_not_exist': BoolFieldMetadata(
                label='Error if not Exist',
                description='If true, then the path must exist. If false, then the file may exist or not',
                optional=False,
                default=f_defaults['error_if_not_exist'],
            ),
        }
    )
    return out
  ##

  @classmethod
  def createFileField(
      cls,
      label: str,
      description: Optional[str],
      optional: bool,
      default: Optional[Path],
      error_if_not_exist: bool,
  ) -> PathFieldMetadata:
    out = PathFieldMetadata(
        label=label,
        description=description,
        optional=optional,
        default=default,
        path_type=_path_type_option_label_file,
        error_if_not_exist=error_if_not_exist,
    )
    return out
  ##

##


@dataclass(frozen=True)
class IntFieldMetadata(BasicFieldMetadata):
  """ Max value is inclusive """
  config_metadata: ClassVar[AggregateFieldMetadata]
  default: Optional[int]
  min_value: Optional[int]
  max_value: Optional[int]

  def __post_init__(self) -> None:
    super().__post_init__()
    if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
      raise ValueError(
          f'Because min and max were supplied, it was expected that min value should be less than or equal the max value.'
          f' Got min:{self.min_value} max:{self.max_value}'
      )
    ##
    if self.default is not None:
      if not self.isValueValid(self.default):
        raise ValueError(f'Specified default value was not valid. Default:{self.default}')
      ##
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "IntFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[int]:
    if self.optional and value is None:
      return None
    ##
    try:
      out = int(value)
    except (TypeError, ValueError,) as e:
      raise ValueError(f'Could not unpack value as {type(self).__name__}. Config:{value}') from e
    ##
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> Optional[int]:
    if self.optional and config_value is None:
      return None
    ##
    try:
      out = int(config_value)  # type: ignore[call-overload]
    except (TypeError, ValueError,) as e:
      raise ValueError(f'Could not pack value as {type(self).__name__}. Config:{config_value}') from e
    ##
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return self.optional
    ##
    try:
      value = int(value)
    except (TypeError, ValueError,):
      return False
    ##
    if self.min_value is not None and not (value >= self.min_value):
      return False
    ##
    if self.max_value is not None and not (value <= self.max_value):
      return False
    ##
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              default: Union[UnsetType, Optional[int]] = Unset,
              min_value: Union[UnsetType, Optional[int]] = Unset,
              max_value: Union[UnsetType, Optional[int]] = Unset,
              ) -> IntFieldMetadata:
    out = IntFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        default=self.default if isinstance(default, UnsetType) else default,
        min_value=self.min_value if isinstance(min_value, UnsetType) else min_value,
        max_value=self.max_value if isinstance(max_value, UnsetType) else max_value,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': self.default,
        'min_value': self.min_value,
        'max_value': self.max_value,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> IntFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = int(default)
    ##
    min_val = config.pop('min_value')
    if min_val is not None:
      min_val = int(min_val)
    ##
    max_val = config.pop('max_value')
    if max_val is not None:
      max_val = int(max_val)
    ##
    out = IntFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        default=default,
        min_value=min_val,
        max_value=max_val,
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains an integer',
        optional=False,
        fields={
            **super_af.fields,
            'default': IntFieldMetadata(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
                min_value=None,
                max_value=None,
            ),
            'min_value': IntFieldMetadata(
                label='Minimum Value',
                description='Holds optional minimum value',
                default=f_defaults['min_value'],
                optional=True,
                min_value=None,
                max_value=None,
            ),
            'max_value': IntFieldMetadata(
                label='Maximum Value',
                description='Holds optional inclusive maximum value',
                default=f_defaults['max_value'],
                optional=True,
                min_value=None,
                max_value=None,
            ),
        }
    )
    return out
  ##

##


@dataclass(frozen=True)
class FloatFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  units: Optional[PhysicalUnit]
  default: Optional[float]
  min_value: Optional[float]
  min_is_valid: bool
  max_value: Optional[float]
  max_is_valid: bool

  def __post_init__(self) -> None:
    super().__post_init__()
    if self.min_value is not None and self.max_value is not None and self.min_value >= self.max_value:
      raise ValueError(
          f'Because min and max were supplied, it was expected that min value should be less than the max value.'
          f' Got min:{self.min_value} max:{self.max_value}'
      )
    ##
    if self.min_value is not None and isnan(self.min_value):
      raise ValueError(f'Expected min value to be not nan. Got:{self.min_value}')
    ##
    if self.max_value is not None and isnan(self.max_value):
      raise ValueError(f'Expected max value to be not nan. Got:{self.max_value}')
    ##
    if self.default is not None:
      if not self.isValueValid(self.default):
        raise ValueError(f'Specified default value was not valid. Default:{self.default}. Metadata:{self}')
      ##
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "FloatFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[float]:
    if self.optional and value is None:
      return None
    ##
    try:
      out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError,) as e:
      raise ValueError(f'Could not unpack value as {type(self).__name__}. Config:{value}') from e
    ##
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def packValue(self, config_value: T, check_value: bool = False) -> Optional[float]:
    if self.optional and config_value is None:
      return None
    ##
    try:
      out = float(config_value)  # type: ignore[arg-type]
    except (TypeError, ValueError,) as e:
      raise ValueError(f'Could not pack value as {type(self).__name__}. Config:{config_value}') from e
    ##
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return self.optional
    ##
    try:
      value = float(value)
    except (TypeError, ValueError,):
      return False
    ##
    if self.min_value is not None:
      if self.min_is_valid:
        if not (value >= self.min_value):
          return False
        ##
      else:
        if not (value > self.min_value):
          return False
        ##
      ##
    ##
    if self.max_value is not None:
      if self.max_is_valid:
        if not (value <= self.max_value):
          return False
        ##
      else:
        if not (value < self.max_value):
          return False
        ##
      ##
    ##
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              default: Union[UnsetType, Optional[float]] = Unset,
              units: Union[UnsetType, Optional[PhysicalUnit]] = Unset,
              min_value: Union[UnsetType, Optional[float]] = Unset,
              min_is_valid: Optional[bool] = None,
              max_value: Union[UnsetType, Optional[float]] = Unset,
              max_is_valid: Optional[bool] = None,
              optional: Optional[bool] = None,
              ) -> FloatFieldMetadata:
    out = FloatFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        default=self.default if isinstance(default, UnsetType) else default,
        units=self.units if isinstance(units, UnsetType) else units,
        min_value=self.min_value if isinstance(min_value, UnsetType) else min_value,
        min_is_valid=self.min_is_valid if min_is_valid is None else min_is_valid,
        max_value=self.max_value if isinstance(max_value, UnsetType) else max_value,
        max_is_valid=self.max_is_valid if max_is_valid is None else max_is_valid,
        optional=self.optional if optional is None else optional,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'units': self.units.asConfig(caller_ids) if self.units is not None else None,
        'default': self.default,
        'min_value': self.min_value,
        'min_is_valid': self.min_is_valid,
        'max_value': self.max_value,
        'max_is_valid': self.max_is_valid,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> FloatFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = float(default)
    ##
    min_val = config.pop('min_value')
    if min_val is not None:
      min_val = float(min_val)
    ##
    max_val = config.pop('max_value')
    if max_val is not None:
      max_val = float(max_val)
    ##
    units = config.pop('units')
    if units is not None:
      if isinstance(units, str):
        units = PhysicalUnit.fromString(units)
      else:
        units = PhysicalUnit.fromConfig(units, debug_config_prefix=f'{debug_config_prefix}.units')
      ##
    ##
    out = FloatFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        units=units,
        default=default,
        min_value=min_val,
        min_is_valid=bool(config.pop('min_is_valid')),
        max_value=max_val,
        max_is_valid=bool(config.pop('max_is_valid')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains a float (real number)',
        optional=False,
        fields={
            **super_af.fields,
            'default': FloatFieldMetadata.createUnbound(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
                units=None,
            ),
            'units': MappingFieldMetadata(
                label='Units',
                description='Units that describe this field',
                optional=True,
                value=PhysicalUnit.getConfigMetadata(),
            ),
            'min_value': FloatFieldMetadata.createUnbound(
                label='Minimum Value',
                description='Holds minimum value',
                default=f_defaults['min_value'],
                optional=True,
                units=None,
            ),
            'min_is_valid': BoolFieldMetadata(
                label='Minimum Value is Value',
                description='Determines if minimum value is valid (inclusive) or not value (exclusive).',
                default=f_defaults['min_is_valid'],
                optional=False,
            ),
            'max_value': FloatFieldMetadata.createUnbound(
                label='Maximum Value',
                description='Holds maximum value',
                default=f_defaults['max_value'],
                optional=True,
                units=None,
            ),
            'max_is_valid': BoolFieldMetadata(
                label='Maximum Value is Value',
                description='Determines if maximum value is valid (inclusive) or not value (exclusive).',
                default=f_defaults['max_is_valid'],
                optional=False,
            ),
        }
    )
    return out
  ##

  # TODO add option for nan valid

  @classmethod
  def createUnbound(
      cls,
      label: str,
      description: Optional[str],
      units: Optional[PhysicalUnit],
      default: Optional[float],
      optional: bool = False,
  ) -> FloatFieldMetadata:
    out = FloatFieldMetadata(
        label=label,
        description=description,
        units=units,
        default=default,
        optional=optional,
        min_value=-inf,
        min_is_valid=True,
        max_value=inf,
        max_is_valid=True,
    )
    return out
  ##

  @classmethod
  def createFinite(cls,
                   label: str,
                   description: Optional[str],
                   units: Optional[PhysicalUnit],
                   default: Optional[float],
                   optional: bool = False,
                   ) -> FloatFieldMetadata:
    out = FloatFieldMetadata(
        label=label,
        description=description,
        units=units,
        default=default,
        optional=optional,
        min_value=-inf,
        min_is_valid=False,
        max_value=inf,
        max_is_valid=False,
    )
    return out
  ##

  @classmethod
  def createPositiveFinite(
      cls,
      label: str,
      description: Optional[str],
      units: Optional[PhysicalUnit],
      default: Optional[float],
      optional: bool = False,
  ) -> FloatFieldMetadata:
    out = FloatFieldMetadata(
        label=label,
        description=description,
        units=units,
        default=default,
        optional=optional,
        min_value=0,
        min_is_valid=False,
        max_value=inf,
        max_is_valid=False,
    )
    return out
  ##

  @classmethod
  def createNonNegativeFinite(
      cls,
      label: str,
      description: Optional[str],
      units: Optional[PhysicalUnit],
      default: Optional[float],
      optional: bool = False,
  ) -> FloatFieldMetadata:
    out = FloatFieldMetadata(
        label=label,
        description=description,
        units=units,
        default=default,
        optional=optional,
        min_value=0,
        min_is_valid=True,
        max_value=inf,
        max_is_valid=False,
    )
    return out
  ##

##


@dataclass(frozen=True)
class ChoiceFieldMetadata(BasicFieldMetadata):
  """ A single choice field. """
  config_metadata: ClassVar[AggregateFieldMetadata]
  default: Optional[str]
  choice2label: Mapping[str, str]
  case_insensitive: bool = True

  def __post_init__(self) -> None:
    super().__post_init__()
    if len(self.choice2label) <= 0:
      raise ValueError(f'Expected at least one choice. Got:{self.choice2label}')
    ##
    if self.case_insensitive:
      initial_choices = frozenset(self.choice2label.keys())
      object.__setattr__(self, 'choice2label', {normalizeEnumNameForMapping(choice): case for choice, case in self.choice2label.items()})
      if len(initial_choices) != len(self.choice2label):
        final2initial_choices = defaultdict(list)
        for initial_choice in initial_choices:
          final2initial_choices[normalizeEnumNameForMapping(initial_choice)].append(initial_choice)
        ##
        bad_choices = {k: v for k, v in final2initial_choices.items() if len(v) > 1}
        raise ValueError(f'Choice is case-insensitive, but some choices are indistinguishable. {bad_choices}')
      ##
      if self.default is not None:
        object.__setattr__(self, 'default', normalizeEnumNameForMapping(self.default))
      ##
    ##
    if self.default is not None and self.default not in self.choice2label:
      raise ValueError(f'Default value was specified, but not a valid choice. Default:{self.default}. Choices:{list(self.choice2label.keys())}')
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "ChoiceFieldMetadata"
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return self.optional
    ##
    if self.case_insensitive:
      value = normalizeEnumNameForMapping(value)
    ##
    return value in self.choice2label
  ##

  def packValue(self, config_value: str, check_value: bool = False) -> str:
    if config_value is None:
      if self.optional:
        return None
      ##
      raise ValueError(f'Config to be packed is {config_value}, but metadata is not optional. Metadata:{self}')
    ##
    if not isinstance(config_value, str):
      raise ValueError(f'Unable to pack non-string as a choice. Got:{config_value}')
    ##
    out = config_value
    if self.case_insensitive:
      out = normalizeEnumNameForMapping(config_value)
    ##
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[str]:
    if self.optional and value is None:
      return None
    ##
    out = value
    if self.case_insensitive:
      out = normalizeEnumNameForMapping(value)
    ##
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def __hash__(self) -> int:
    tup = (
        self.label,
        self.description,
        tuple(self.choice2label.items()),
        self.optional,
        self.case_insensitive,
    )
    return hash(tup)
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              default: Union[UnsetType, Optional[str]] = Unset,
              choice2label: Optional[Mapping[str, str]] = None,
              optional: Optional[bool] = None,
              case_insensitive: Optional[bool] = None,
              ) -> ChoiceFieldMetadata:
    out = ChoiceFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        default=self.default if isinstance(default, UnsetType) else default,
        choice2label=self.choice2label if choice2label is None else choice2label,
        optional=self.optional if optional is None else optional,
        case_insensitive=self.case_insensitive if case_insensitive is None else case_insensitive,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': self.default,
        'choice2label': self.choice2label,
        'case_insensitive': self.case_insensitive,
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> ChoiceFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = str(default)
    ##
    out = ChoiceFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        default=default,
        choice2label={str(k): str(v) for k, v in config.pop('choice2label').items()},
        case_insensitive=bool(config.pop('case_insensitive')),
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
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains a bool',
        optional=False,
        fields={
            **super_af.fields,
            'default': StringFieldMetadata(
                label='Default',
                description='Holds default value',
                default=f_defaults['default'],
                optional=True,
            ),
            'choice2label': MappingFieldMetadata(
                label='Choice To Label',
                description='Holds the mapping of choice values to labels',
                optional=False,
                value=StringFieldMetadata(
                    label='Label',
                    description='Label for a choice',
                    optional=False,
                    default=None,
                ),
            ),
            'case_insensitive': BoolFieldMetadata(
                label='Case Insensitive',
                description='Determines if the choice values should be interpreted case-insensitively.',
                optional=False,
                default=f_defaults['case_insensitive'],
            ),
        }
    )
    return out
  ##

##


@dataclass(frozen=True)
class MappingFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  value: FieldMetadata
  # TODO[minor,improvement] add specification for key type, for now, there hasn't been a need.

  def __post_init__(self) -> None:
    super().__post_init__()
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "MappingFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[Dict[str, Any]]:
    if self.optional and value is None:
      return None
    ##
    out = {**value}
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def packValue(self, config_value: Optional[Mapping[str, Any]], check_value: bool = False) -> Optional[Dict[str, Any]]:
    if self.optional and config_value is None:
      return None
    ##
    out = {**config_value}  # type: ignore[dict-item,list-item]
    if check_value and not self.isValueValid(out):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return self.optional
    ##
    for k, v in value.items():
      if not self.value.isValueValid(v):
        return False
      ##
    ##
    return True
  ##

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              value: Optional[FieldMetadata] = None,
              ) -> MappingFieldMetadata:
    out = MappingFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        value=self.value if value is None else value,
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'value': self.value.asConfig(caller_ids=caller_ids),
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains unspecified number of keys and homogenous value pairs',
        optional=False,
        fields={
            **super_af.fields,
            'value': _metametadata_switch_field,
        },
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> MappingFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    out = MappingFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        value=createMetadataFromConfig(config.pop('value'), debug_config_prefix=f'{debug_config_prefix}.value'),
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


@dataclass(frozen=True)
class RepeatedFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  config_wrapper_repeat_key: ClassVar[str] = 'repeat'
  config_wrapper_value_key: ClassVar[str] = 'value'
  repeat: IntFieldMetadata
  value: FieldMetadata

  def __post_init__(self) -> None:
    super().__post_init__()
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "RepeatedFieldMetadata"
  ##

  @property
  def is_fixed(self) -> bool:
    if self.repeat.min_value is None or self.repeat.max_value is None:
      return False
    ##
    return self.repeat.min_value == self.repeat.max_value
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> List[Any]:
    try:
      if self.repeat.min_value is None or self.repeat.max_value is None or (self.repeat.min_value != self.repeat.max_value):
        # Not fixed
        repeat_raw_value = value[self.config_wrapper_repeat_key]
        repeat_value = int(repeat_raw_value)
      else:
        # Fixed
        repeat_value = self.repeat.min_value
      ##
      data = value[self.config_wrapper_value_key]
      if len(data) < repeat_value:
        raise ValueError(f'Not enough data. Expected {repeat_value} repetitions. Got data:{data}')
      ##
      return [self.value.unpackValue(d, check_value=check_value) for d in data[:repeat_value]]
    except Exception as e:
      raise ValueError(f'Caught exception:{e!r} with config:{value} metadata:{self}') from e
    ##
  ##

  def packValue(self, config_value: Sequence[Any], check_value: bool = False) -> Dict[str, Any]:
    # TODO how should optional be packed here?
    out: Dict[str, Any] = {
        self.config_wrapper_repeat_key: len(config_value),
        self.config_wrapper_value_key: [self.value.packValue(v, check_value=check_value) for v in config_value],
    }
    if check_value and not self.repeat.isValueValid(len(config_value)):
      raise ValueError(f'Could not process invalid value:{out}. Metadata:{self}')
    ##
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return False
    ##
    if not self.repeat.isValueValid(len(value)):
      return False
    ##
    for v in value:
      if not self.value.isValueValid(v):
        return False
      ##
    ##
    return True
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              repeat: Optional[IntFieldMetadata] = None,
              value: Optional[FieldMetadata] = None,
              ) -> RepeatedFieldMetadata:
    out = RepeatedFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        repeat=self.repeat if repeat is None else repeat,
        value=self.value if value is None else value,
    )
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a tagged union / a choice of fields',
        optional=False,
        fields={
            **super_af.fields,
            'repeat': IntFieldMetadata.getConfigMetadata().replace(
                label='Repeat',
                description='Describes how many value elements can be present',
            ),
            'value': _metametadata_switch_field,
        }
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> RepeatedFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    out = RepeatedFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        repeat=IntFieldMetadata.fromConfig(config.pop('repeat'), debug_config_prefix=f'{debug_config_prefix}.repeat'),
        value=createMetadataFromConfig(config.pop('value'), debug_config_prefix=f'{debug_config_prefix}.value'),
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

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'repeat': self.repeat.asConfig(caller_ids),
        'value': self.value.asConfig(caller_ids),
    }
    return out
  ##

  @classmethod
  def createZeroOrMoreRepeat(
      cls,
      label: str,
      description: Optional[str],
      repeat_label: str,
      repeat_description: Optional[str],
      value: FieldMetadata,
      optional: bool = False,
      default: int = 0,  # TODO fix this argname
  ) -> RepeatedFieldMetadata:
    out = RepeatedFieldMetadata(
        repeat=IntFieldMetadata(
            label=repeat_label,
            description=repeat_description,
            default=max(0, default or 0),
            min_value=0,
            max_value=None,
            optional=False,
        ),
        label=label,
        description=description,
        value=value,
        optional=optional,
    )
    return out
  ##

  @classmethod
  def createOneOrMoreRepeat(
      cls,
      label: str,
      description: Optional[str],
      repeat_label: str,
      repeat_description: Optional[str],
      value: FieldMetadata,
      optional: bool = False,
      default: int = 1,  # TODO fix this argname
  ) -> RepeatedFieldMetadata:
    out = RepeatedFieldMetadata(
        repeat=IntFieldMetadata(
            label=repeat_label,
            description=repeat_description,
            default=max(default or 0, 1),
            min_value=1,
            max_value=None,
            optional=False,
        ),
        label=label,
        description=description,
        value=value,
        optional=optional,
    )
    return out
  ##

  @classmethod
  def createFixedRepeat(
      cls,
      count: int,
      label: str,
      description: Optional[str],
      value: FieldMetadata,
      optional: bool = False,
  ) -> RepeatedFieldMetadata:
    if count <= 0:
      raise ValueError(f'Expeted count to be greater than zero. Got:{count}')
    ##
    out = RepeatedFieldMetadata(
        repeat=IntFieldMetadata(
            label='',
            description=None,
            default=count,
            min_value=count,
            max_value=count,
            optional=False,
        ),
        label=label,
        description=description,
        value=value,
        optional=optional,
    )
    return out
  ##
##


@dataclass(frozen=True)
class AggregateFieldMetadata(BasicFieldMetadata):
  config_metadata: ClassVar[AggregateFieldMetadata]
  fields: Mapping[str, FieldMetadata]
  default: Optional[Mapping[str, Any]] = None

  def __post_init__(self) -> None:
    super().__post_init__()
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "AggregateFieldMetadata"
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Optional[Dict[str, Any]]:
    if self.optional and value is None:
      return None
    ##
    try:
      value_keys = value.keys()
    except (AttributeError,) as e:
      raise ValueError(f'Expected packed value:{value} to be unpackable. Metadata:{self}') from e
    ##
    out = {}
    for k, md in self.fields.items():
      try:
        v = value[k]
      except (KeyError,) as e:
        if hasattr(md, 'optional') and md.optional:
          continue
        ##
        raise ValueError(f'Caught exception:{e!r}. Field keys:{self.fields.keys()} Value keys:{value_keys}') from e
      ##
      out[k] = md.unpackValue(v, check_value=check_value)
    ##
    # Already checked all
    return out
  ##

  def packValue(self, config_value: Optional[Mapping[str, Any]], check_value: bool = False) -> Optional[Dict[str, Any]]:
    if self.optional and config_value is None:
      return None
    ##
    out = {}
    for k, md_v in self.fields.items():
      try:
        v = config_value[k]  # type: ignore[index]
      except (IndexError, KeyError,) as e:
        if hasattr(md_v, 'optional') and md_v.optional:
          continue
        ##
        raise ValueError(f'Could not find key:{k!r} in config. config:{config_value}. metadata:{self}') from e
      except (ValueError, TypeError,) as e:
        # not a mapping typically
        raise ValueError(f'Could not index config. key:{k!r}\nmetadata field:{md_v};\nconfig:{config_value!r};\nmetadata:{self}') from e
      ##
      try:
        out[k] = md_v.packValue(v, check_value=check_value)
      except Exception as e:
        raise ValueError(f'Caught exception, trying to pack key:{k!r} value:{v}. Exception:{e!r}\nConfig:{config_value!r}\nMetadata:{self}') from e
      ##
    ##
    # Already checked all
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    out: Dict[str, Any] = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'fields': fields,
        'default': self.default,
    }
    field_caller_ids = caller_ids + (None,)  # extra item to represent this an item of an item
    for k, v in self.fields.items():
      fields[k] = v.asConfig(caller_ids=field_caller_ids)
    ##
    return out
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              fields: Optional[Mapping[str, FieldMetadata]] = None,
              default: Union[UnsetType, Optional[Mapping[str, Any]]] = Unset,
              ) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        fields=self.fields if fields is None else fields,
        default=self.default if isinstance(default, UnsetType) else default,
    )
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return False
    ##
    for k, v in value.items():
      if k not in self.fields:
        return False
      ##
      v_md = self.fields[k]
      if not v_md.isValueValid(v):
        return False
      ##
    ##
    return True
  ##

  def __hash__(self) -> int:
    tup = tuple(self.asConfig(tuple()))
    return hash(tup)
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a field that contains specified key value pairs',
        optional=False,
        fields={
            **super_af.fields,
            'fields': MappingFieldMetadata(
                label='Fields',
                description='Holds the descriptions of the fields',
                value=_metametadata_switch_field,
                optional=False,
            ),
            'default': MappingFieldMetadata(
                label='Default',
                description='Holds the default value',
                value=AnyFieldMetadata.getConfigMetadata(),
                optional=True,
            ),
        }
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> AggregateFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    agg_fields = {}
    field_config = config.pop('fields')
    for k, config_v in field_config.items():
      v = createMetadataFromConfig(config_v, debug_config_prefix=f'{debug_config_prefix}.fields.{k}')
      agg_fields[str(k)] = v
    ##
    out = AggregateFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        fields=agg_fields,
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


@dataclass(frozen=True)
class SwitchFieldMetadata(BasicFieldMetadata):
  """ Represents a value similar to a tagged union. """
  config_metadata: ClassVar[AggregateFieldMetadata]
  config_wrapper_choice_key: ClassVar[str] = 'choice'
  config_wrapper_value_key: ClassVar[str] = 'value'

  default: Optional[str]
  # TODO - update name to be default_choice
  # TODO - add default data - not just default choice
  switch_label: str
  switch_description: Optional[str]
  choice2value: Mapping[str, BasicFieldMetadata]  # (chioce string, field data)
  switch_key: Optional[str]  # key to store in packed value to denote switch value
  # If switch_key is None, then this switch is untagged, this means that all switch choices
  # are attempted when unpacking/packing - this is more inefficient, but may make sense for very simplistic fields
  # The choices should be ordered so that the most likely switch choice is checked first and so on.
  # Should the switch choices be confusable - ie the configs they can pack are the same
  # Then the untagged switch will have no way to know which is the valid choice and will just pick the first one
  # This type of error is NOT checked for.
  switch_key_is_intrusive: bool  # determines if switch packing, packs the choice value into the value itself (intrusive) or not - if untaged this setting is ignored.
  case_insensitive: bool = True

  def __post_init__(self) -> None:
    super().__post_init__()
    if not self.choice2value:
      raise ValueError('Expected at least one field')
    ##
    if self.switch_key_is_intrusive and self.is_untagged:
      log.info(f'Switch is untagged, but key is marked as intrusive. The intrusive flag will be ignored and set to the correct value. Metadata:{self}')
      object.__setattr__(self, 'switch_key_is_intrusive', False)
    ##
    if self.switch_key_is_intrusive:
      for choice, case in self.choice2value.items():
        if not isinstance(case, (AggregateFieldMetadata, RecursedConfig,)):
          raise ValueError(f'With switch_key_is_intrusive as True, then all field metadata must be of type {AggregateFieldMetadata.__name__}. Got {choice}:{case}')
        ##
      ##
    ##
    if self.case_insensitive:
      initial_choices = frozenset(self.choice2value.keys())
      object.__setattr__(self, 'choice2value', {normalizeEnumNameForMapping(choice): case for choice, case in self.choice2value.items()})
      if len(initial_choices) != len(self.choice2value):
        final2initial_choices = defaultdict(list)
        for initial_choice in initial_choices:
          final2initial_choices[normalizeEnumNameForMapping(initial_choice)].append(initial_choice)
        ##
        bad_choices = {k: v for k, v in final2initial_choices.items() if len(v) > 1}
        raise ValueError(f'Switch is case-insensitive, but some choices are indistinguishable. {bad_choices}')
      ##
      if self.default is not None:
        object.__setattr__(self, 'default', normalizeEnumNameForMapping(self.default))
      ##
    ##
    if self.default is not None and self.default not in self.choice2value:
      raise ValueError(
          f'Default value was specified, but not a valid choice.'
          f' Default:{self.default!r}. Choices:{list(self.choice2value.keys())}'
      )
    ##
  ##

  @classmethod
  def getConfigTypename(cls) -> str:
    return "SwitchFieldMetadata"
  ##

  @property
  def is_untagged(self) -> bool:
    return self.switch_key is None
  ##

  @cached_property
  def switch(self) -> ChoiceFieldMetadata:
    # repacks data as choice field
    out = ChoiceFieldMetadata(
        default=self.default,
        label=self.switch_label,
        description=self.switch_description,
        choice2label={choice: md.label for choice, md in self.choice2value.items()},
        optional=self.optional,
    )
    return out
  ##

  def packValue(self, config_value: Any, check_value: bool = False) -> Any:
    # Packs the choice non-intrusively (packed switch config is non-intrusive,
    # regardless if the config itself is intrusive)
    if self.is_untagged:
      for choice, value_md in self.choice2value.items():
        try:
          return {
              self.config_wrapper_choice_key: choice,
              self.config_wrapper_value_key: {
                  choice: value_md.packValue(config_value, check_value=check_value),
              },
          }
        except (ValueError,):
          pass
        ##
      ##
      # Failed all choices
      raise ValueError(f'Unable to pack untagged config_value with any of the switch choices. config:{config_value}. Choices:{self.choice2value}')
    ##
    # Config value could be one of either - a single switch value or a sequence of switch values
    # If intrusive, then switch_key is not set on data itself.
    out: Dict[str, Any] = {
        self.config_wrapper_choice_key: None,
        self.config_wrapper_value_key: {},
    }
    out_value = out[self.config_wrapper_value_key]
    specific_switch_choice = None
    if self.switch_key in config_value:
      # just a single value
      specific_switch_choice = config_value[self.switch_key]
      if self.case_insensitive:
        specific_switch_choice = normalizeEnumNameForMapping(specific_switch_choice)
      ##
      config_value = {specific_switch_choice: config_value}
    ##
    for orig_choice, v in config_value.items():
      choice = orig_choice
      if self.case_insensitive:
        choice = normalizeEnumNameForMapping(choice)
      ##
      if choice not in self.choice2value:
        continue
      ##
      md_v = self.choice2value[choice]
      out[self.config_wrapper_choice_key] = choice
      out_value[choice] = md_v.packValue(v, check_value=check_value)
      if self.switch_key_is_intrusive:
        out_value[choice][self.switch_key] = orig_choice
      ##
    ##
    if specific_switch_choice is not None and not out:
      log.warning(f'Switch key was specified {self.switch_key}:{specific_switch_choice!r}, but no output was set. This odd, perhaps the choice was misspelled? config:{config_value}')
    ##
    # Already checked all
    return out
  ##

  def unpackValue(self, value: Any, check_value: bool = False) -> Any:
    if self.optional and value is None:
      return None
    ##
    choice_value = value.get(self.config_wrapper_choice_key, None)
    if self.case_insensitive and choice_value is not None:
      choice_value = normalizeEnumNameForMapping(choice_value)
    ##
    if choice_value not in self.choice2value:
      msg = f'Switch choice:{choice_value!r} was not a valid choice. Choices:{[k for k in self.choice2value.keys()]}. Value to be unpacked:{value}'
      if self.optional:
        log.debug(msg)
        return None
      ##
      raise ValueError(msg)
    ##
    # Switch metadata is packed non-intrusively
    data = value.get(self.config_wrapper_value_key, None)
    if data is None:
      # LOG this? it means no data was packed - or the switch packed value itself was a None
      return None
    ##
    choice_md = self.choice2value[choice_value]
    if choice_value not in data:
      raise ValueError(f'Switch data was not packed correctly. Expected {choice_value!r} to be in data:{data}')
    ##
    chosen_value = data.get(choice_value)
    out = choice_md.unpackValue(chosen_value, check_value=check_value)
    if self.switch_key_is_intrusive:
      try:
        out[self.switch_key] = choice_value
      except (AttributeError,) as e:
        log.info(f'Unable to set switch key:{self.switch_key} to value:{choice_value} on output:{out}. Ignoring exception:{e}')
      ##
    ##
    return out
  ##

  def isValueValid(self, value: Any) -> bool:
    if value is None:
      return False
    ##
    switch_choice = value.get(self.config_wrapper_choice_key, None)
    if switch_choice not in self.choice2value:
      return False
    ##
    data = value.get(self.config_wrapper_value_key, None)
    if data is None:
      # LOG this?
      return False
    ##
    return self.choice2value[switch_choice].isValueValid(data.get(switch_choice))
  ##

  def __hash__(self) -> int:
    tup = (
        self.label,
        self.description,
        self.switch_label,
        self.switch_description,
        self.switch_key,
        self.switch_key_is_intrusive,
        tuple(self.choice2value.items()),
    )
    return hash(tup)
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    choice2value: Dict[str, Any] = {}
    out = {
        _metadata_intrusive_key: self.getConfigTypename(),
        'label': self.label,
        'description': self.description,
        'optional': self.optional,
        'default': self.default,
        'switch_label': self.switch_label,
        'switch_description': self.switch_description,
        'switch_key': self.switch_key,
        'switch_key_is_intrusive': self.switch_key_is_intrusive,
        'choice2value': choice2value,
        'case_insensitive': self.case_insensitive,
    }
    field_caller_ids = caller_ids + (None,)  # extra item to represent this an item of an item
    for choice, case in self.choice2value.items():
      choice2value[choice] = case.asConfig(field_caller_ids)
    ##
    return out
  ##

  def replace(self, *,
              label: Optional[str] = None,
              description: Union[UnsetType, Optional[str]] = Unset,
              optional: Optional[bool] = None,
              default: Union[UnsetType, Optional[str]] = Unset,
              switch_label: Optional[str] = None,
              switch_description: Union[UnsetType, Optional[str]] = Unset,
              choice2value: Optional[Mapping[str, BasicFieldMetadata]] = None,
              switch_key: Union[UnsetType, Optional[str]] = Unset,
              switch_key_is_intrusive: Optional[bool] = None,
              case_insensitive: Optional[bool] = None,
              ) -> SwitchFieldMetadata:
    out = SwitchFieldMetadata(
        label=self.label if label is None else label,
        description=self.description if isinstance(description, UnsetType) else description,
        optional=self.optional if optional is None else optional,
        default=self.default if isinstance(default, UnsetType) else default,
        switch_description=self.switch_description if isinstance(switch_description, UnsetType) else switch_description,
        switch_label=self.switch_label if switch_label is None else switch_label,
        switch_key=self.switch_key if isinstance(switch_key, UnsetType) else switch_key,
        choice2value=self.choice2value if choice2value is None else choice2value,
        switch_key_is_intrusive=self.switch_key_is_intrusive if switch_key_is_intrusive is None else switch_key_is_intrusive,
        case_insensitive=self.case_insensitive if case_insensitive is None else case_insensitive,
    )
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return cls.config_metadata
  ##

  @classmethod
  def createConfigMetadata(cls) -> AggregateFieldMetadata:
    f_defaults = {f.name: f.default if f.default is not MISSING else None for f in getDataclassFields(cls)}
    super_af = super().getConfigMetadata()
    out = AggregateFieldMetadata(
        label=cls.getConfigTypename(),
        description='Represents a tagged union / a choice of fields',
        optional=False,
        fields={
            **super_af.fields,
            'default': StringFieldMetadata(
                label='Default',
                description='Default switch choice',
                default=f_defaults['default'],
                optional=True,
            ),
            'switch_label': StringFieldMetadata(
                label='Switch Label',
                description='Label for the switch choice',
                default=f_defaults['switch_label'],
                optional=False,
            ),
            'switch_description': StringFieldMetadata(
                label='Switch Description',
                description='Longer description for the switch choice',
                default=f_defaults['switch_description'],
                optional=True,
            ),
            'switch_key': StringFieldMetadata(
                label='Switch Key',
                description='Key to that holds switch value. For intrusive switches, this value must not conflict with any of the data fieldnames.'
                            ' If let None, then this represents an untagged switch.'
                            ' Untagged switches have no way to know what the data and must try all the switch cases interatively to determine which is a match.'
                            ' For simple user config this may make sense. Confusable untagged switch cases are not checked for programmatically, that is on the developer.',
                default=f_defaults['switch_key'],
                optional=True,
            ),
            'choice2value': MappingFieldMetadata(
                label='Choices',
                description='Holds the choice types',
                value=_metametadata_switch_field,
                optional=False,
            ),
            'switch_key_is_intrusive': BoolFieldMetadata(
                label='Intrusive Switch Key',
                description=(
                    'Determines if the switch key value is stored within the data itself,'
                    ' or if False, then the packed data is abstracted one layer.'
                ),
                default=f_defaults['switch_key_is_intrusive'],
                optional=False,
            ),
            'case_insensitive': BoolFieldMetadata(
                label='Switch Case Insensitive',
                description=(
                    'Determines if the switch key is case-insensitive'
                ),
                default=f_defaults['case_insensitive'],
                optional=False,
            )
        }
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> SwitchFieldMetadata:
    """ Loads settings from dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    cls._checkConfigIntrusiveKey(config=config, debug_config_prefix=debug_config_prefix)
    description = config.pop('description')
    if description is not None:
      description = str(description)
    ##
    default = config.pop('default')
    if default is not None:
      default = str(default)
    ##
    switch_description = config.pop('switch_description')
    if switch_description is not None:
      switch_description = str(switch_description)
    ##
    switch_key = None
    if 'switch_key' in config:
      switch_key = config.pop('switch_key')
    ##
    if switch_key is not None:
      switch_key = str(switch_key)
    ##
    out = SwitchFieldMetadata(
        label=str(config.pop('label')),
        description=description,
        optional=bool(config.pop('optional')),
        default=default,
        switch_key=switch_key,
        switch_label=str(config.pop('switch_label')),
        switch_description=switch_description,
        switch_key_is_intrusive=bool(config.pop('switch_key_is_intrusive')),
        choice2value={
            str(choice): createMetadataFromConfig(case, debug_config_prefix=f'{debug_config_prefix}.fields.{choice}')
            for choice, case in config.pop('choice2value').items()
        },
        case_insensitive=bool(config.pop('case_insensitive')),
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


class MetadataType(Enum):
  str2enum: ClassVar[Mapping[str, MetadataType]]  # case-nonword insensitive

  AggregateFieldMetadata = AggregateFieldMetadata
  AnyFieldMetadata = AnyFieldMetadata
  BoolFieldMetadata = BoolFieldMetadata
  ChoiceField = ChoiceFieldMetadata
  ConstantFieldMetadata = ConstantFieldMetadata
  FloatField = FloatFieldMetadata
  IntField = IntFieldMetadata
  MappingField = MappingFieldMetadata
  PathField = PathFieldMetadata
  RepeatedFieldMetadata = RepeatedFieldMetadata
  StringFieldMetadata = StringFieldMetadata
  SwitchField = SwitchFieldMetadata

  @classmethod
  def fromString(cls, s: str) -> MetadataType:
    try:
      return cls.str2enum[normalizeEnumNameForMapping(s)]  # type: ignore[index]
    except KeyError as e:
      raise ValueError(f'Value:{s!r} does not correspond to a {cls.__name__}. Valid values are:{[k.upper() for k in cls.str2enum.keys()]}') from e  # type: ignore[attr-defined]
    ##
  ##
##


def createMetadataFromConfig(
    config: Mapping[str, Any],
    debug_config_prefix: str = '',
) -> BasicFieldMetadata:
  """ Expects contents of a 'metadata' config dictionary """
  if not config:
    raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
  ##
  config = {**config}
  # Assumes intrusive switch type here
  switch_key = config[_metadata_intrusive_key]
  try:
    metadata_e = MetadataType.fromString(switch_key)
  except ValueError:
    # Attempt to parse as Recursion instead - this is if the config is recursive ie the object contains itself
    # TODO deal with this typing
    return RecursedConfig.fromConfig(config, debug_config_prefix=debug_config_prefix)  # type: ignore[return-value]
  ##
  metadata_typ: Type[FieldMetadata] = metadata_e.value  # type: ignore[assignment]
  return metadata_typ.fromConfig(config, debug_config_prefix=debug_config_prefix)
##


def _setClassVarConfigMetadata() -> None:
  # Because the asConfig code uses id's to determine recursion,
  # the static class variables / methods should be set and return the same value
  # so that the recursion is noted as the correct level, vs a whole recursion cycle deeper
  # AnyFieldMetadata, - not in list because it is not cached like the rest.
  typs = (
      AggregateFieldMetadata,
      BoolFieldMetadata,
      ChoiceFieldMetadata,
      ConstantFieldMetadata,
      FloatFieldMetadata,
      IntFieldMetadata,
      MappingFieldMetadata,
      PathFieldMetadata,
      RecursedConfig,
      RepeatedFieldMetadata,
      StringFieldMetadata,
      SwitchFieldMetadata,
  )
  for t in typs:
    if hasattr(t, 'createConfigMetadata'):
      t.config_metadata = t.createConfigMetadata()  # type: ignore[attr-defined]
    else:
      raise ValueError('Type:{t} does not have createConfigMetadata')
    ##
  ##
##


T = TypeVar('T')
F = TypeVar('F', bound=FieldMetadata)
_metadata_intrusive_key = 'type'
_path_type_option_label_file = normalizeEnumNameForMapping('File')
_path_type_option_label_dir = normalizeEnumNameForMapping('Directory')
_strict_path_type_option2label = {
    normalizeEnumNameForMapping(label): label
    for label in (
        _path_type_option_label_file,
        _path_type_option_label_dir,
    )
}
_path_type2label = {
    **_strict_path_type_option2label,
    'dir': _path_type_option_label_dir,
    'folder': _path_type_option_label_dir,
}

MetadataType.str2enum = {
    normalizeEnumNameForMapping(e.value.getConfigTypename()): e for e in MetadataType  # type: ignore[attr-defined]
}

_metametadata_switch_field = SwitchFieldMetadata(
    label='Value Metadata',
    description='Holds the metadata of the value',
    default=None,
    optional=False,
    switch_label='Metadata Type',
    switch_description=None,
    switch_key=_metadata_intrusive_key,
    switch_key_is_intrusive=False,
    choice2value={'tmp': None},  # type: ignore[dict-item] # standin value until replaced later
    case_insensitive=True,
)

# Order here is important - the switch recursion variable is defined, but not looped yet
_setClassVarConfigMetadata()

# Make the switch variable recursive
object.__setattr__(_metametadata_switch_field, 'switch_key_is_intrusive', True)
object.__setattr__(
    _metametadata_switch_field,
    'choice2value',
    {normalizeEnumNameForMapping(e.value.getConfigTypename()): e.value.getConfigMetadata()  # type: ignore[attr-defined]
     for e in MetadataType},
)

##############################################

_PUV1 = PhysicalUnitValue(power=1, value=1)

# Tokens for parsing a unit string e.g. "m^3 / kg^4 * Hz / s"


class _UnitToken(ABC):
  @classmethod
  @abstractmethod
  def getPattern(cls) -> Pattern[str]:
    pass
  ##

  @classmethod
  @abstractmethod
  def fromString(cls, value: str) -> _UnitToken:
    pass
  ##
##


@dataclass(frozen=True)
class _NameToken(_UnitToken):
  pattern: ClassVar[Pattern[str]] = re.compile(r'[a-zA-Z_]\w*')
  name: str

  @classmethod
  def fromString(cls, value: str) -> _NameToken:
    return cls(value)
  ##

  @classmethod
  def getPattern(cls) -> Pattern[str]:
    return cls.pattern
  ##
##


@dataclass(frozen=True)
class _ValueToken(_UnitToken):
  pattern: ClassVar[Pattern[str]] = re.compile(r'(?P<num>[-+]?(?:\d+(?:\.\d*)?|\.\d+))(?:\s*/\s*(?P<den>\d+(?:\.\d*)?|\.\d+))?')
  value: Union[int, Fraction]

  @classmethod
  def fromString(cls, value: str) -> _ValueToken:
    m = cls.pattern.match(value)
    if not m:
      raise ValueError(f'Unable to create {cls.__name__} from {value!r}')
    ##
    mg = m.groupdict()
    num = float(mg['num'])
    den = 1 if 'den' not in mg else mg['den']
    if den is None:
      den = 1
    else:
      den = float(den)
    ##
    if int(num) != num or int(den) != den:
      out = cls(Fraction.from_float(num / den))
    else:
      out = cls(Fraction(int(num), int(den)))
    ##
    return out
  ##

  @classmethod
  def getPattern(cls) -> Pattern[str]:
    return cls.pattern
  ##
##


@dataclass(frozen=True)
class _MultiplyToken(_UnitToken):
  pattern: ClassVar[Pattern[str]] = re.compile(r'\*(?!\*)')

  @classmethod
  def fromString(cls, value: str) -> _MultiplyToken:
    return cls()
  ##

  @classmethod
  def getPattern(cls) -> Pattern[str]:
    return cls.pattern
  ##
##


@dataclass(frozen=True)
class _DivideToken(_UnitToken):
  pattern: ClassVar[Pattern[str]] = re.compile(r'/')

  @classmethod
  def fromString(cls, value: str) -> _DivideToken:
    return cls()
  ##

  @classmethod
  def getPattern(cls) -> Pattern[str]:
    return cls.pattern
  ##
##


@dataclass(frozen=True)
class _PowerToken(_UnitToken):
  pattern: ClassVar[Pattern[str]] = re.compile(r'\*\*|\^')

  @classmethod
  def fromString(cls, value: str) -> _PowerToken:
    return cls()
  ##

  @classmethod
  def getPattern(cls) -> Pattern[str]:
    return cls.pattern
  ##
##


_token_types: Sequence[Type[_UnitToken]] = (
    _NameToken,
    _ValueToken,
    _PowerToken,
    _MultiplyToken,
    _DivideToken,
)
_token_types_patterns: Sequence[Tuple[Type[_UnitToken], Pattern[str]]] = tuple((typ, typ.getPattern(),) for typ in _token_types)


def _createToken(s: str) -> Tuple[_UnitToken, str]:
  s = s.lstrip()
  for index, (ttyp, rgx) in enumerate(_token_types_patterns):
    m = rgx.match(s)
    if not m:
      continue
    ##
    value = m.group(0)
    out_tok = ttyp.fromString(value)
    return (out_tok, s[len(value):],)
  ##
  raise ValueError(f'Unable to create UnitToken from string:{s!r}')
##


def _yieldTokens(s: str) -> Generator[_UnitToken, None, None]:
  while s:
    tok, s = _createToken(s)
    yield tok
  ##
##


def _parse(s: str) -> Dict[str, Union[int, Fraction]]:
  """ Parses tokens and returns unit and power pairs.
  Note that it does NOT
  - parse any hardcoded constants  (5.3 * a)
  - parse nested items e.g. a * b / (c * d)
  - nor fractional powers, e.g. a^(-5/4)
  """
  if not s:
    return {}
  ##
  out: Dict[str, Union[int, Fraction]] = defaultdict(int)
  current_name_tok: Optional[_NameToken] = None
  is_mult = True
  is_power = False
  for token in _yieldTokens(s):
    if isinstance(token, _NameToken):
      if current_name_tok is None:
        current_name_tok = token
      else:
        out[current_name_tok.name] += 1 if is_mult else -1  # no power so just 1
        current_name_tok = token
        is_mult = True  # mult is default
      ##
    elif isinstance(token, _MultiplyToken):
      if is_power:
        raise ValueError('Power operator cannot be preceded by the Multiply operator')
      ##
      is_mult = True
    elif isinstance(token, _DivideToken):
      if is_power:
        raise ValueError('Power operator cannot be preceded by the Divide operator')
      ##
      is_mult = False
    elif isinstance(token, _PowerToken):
      if is_power:
        raise ValueError('Power operator cannot be preceded by another power operator')
      elif current_name_tok is None:
        raise ValueError('Expected name to precede power operator (** or ^)')
      ##
      is_power = True
    elif isinstance(token, _ValueToken):
      # NOTE that parsing fractional power tokens is unsupported e.g. ^(5/3)
      if not is_power:
        raise ValueError(f'Expected Power operator (** or ^) to precede value:{token.value}')
      elif current_name_tok is None:
        raise ValueError(f'Expected name and power operator to preceded value:{token.value}')
      ##
      out[current_name_tok.name] += (1 if is_mult else -1) * token.value
      is_power = False
      current_name_tok = None
      is_mult = True
    ##
  ##
  if current_name_tok is not None:
    out[current_name_tok.name] += 1 if is_mult else -1  # no power so just 1
  ##
  return {**out}
##


Second = PhysicalUnit.fromString('s', name='second')
Hertz = Second.invert().replace(name='Hertz')
Meter = PhysicalUnit.fromString('m', name='meter')
Radian = PhysicalUnit.fromString('rad', name='radian')
Degree = PhysicalUnit.fromString('deg', name='degree')
Kilogram = PhysicalUnit.fromString('kg', name='kilogram')
Kilometer = PhysicalUnit.fromString('km', name='kilometer')
Newton = (Kilogram * Meter / Second**2).replace(name='Newton')
Decibel = PhysicalUnit({}, name='decibel')
Sines = PhysicalUnit({}, name='sines')
Joule = (Meter * Newton).replace(name='Joule')
Watt = (Joule * Second).replace(name='Watt')

Peta = (int(1e15) * PhysicalUnit({})).replace(name='Peta')
Tera = (int(1e12) * PhysicalUnit({})).replace(name='Tera')
Giga = (int(1e9) * PhysicalUnit({})).replace(name='Giga')
Mega = (int(1e6) * PhysicalUnit({})).replace(name='Mega')
Kilo = (int(1e3) * PhysicalUnit({})).replace(name='Kilo')
Centi = (1e-2 * PhysicalUnit({})).replace(name='Centi')
Milli = (1e-3 * PhysicalUnit({})).replace(name='Milli')
Micro = (1e-6 * PhysicalUnit({})).replace(name='Micro')
Nano = (1e-9 * PhysicalUnit({})).replace(name='Nano')

PhysicalUnit.standard_unit_aliases = {
    **PhysicalUnit.standard_unit_aliases,
    's': Second,
    'second': Second,
    'Hertz': Hertz,
    'Hz': Hertz,
    'm': Meter,
    'meter': Meter,
    'radian': Radian,
    'rad': Radian,
    'deg': (Radian * (pi / 180.)).replace(name='degree'),
    'degree': (Radian * (pi / 180.)).replace(name='degree'),
    'kg': Kilogram,
    'N': Newton,
    'kilometer': (1000. * Meter).replace(name='kilometer'),
    'km': (1000. * Meter).replace(name='kilometer'),
    'db': Decibel,
    'dB': Decibel,
    'sines': Sines,
    'J': Joule,
    'W': Watt,
}


def _createStandardAbbreviations() -> Mapping[Union[str, PhysicalUnit, Tuple[Tuple[str, PhysicalUnitValue], ...]], str]:
  out: Dict[Union[str, PhysicalUnit, Tuple[Tuple[str, PhysicalUnitValue], ...]], str] = {}
  for alias, pu in PhysicalUnit.standard_unit_aliases.items():
    if not isinstance(pu, PhysicalUnit) or pu.name is None or pu.name == alias:
      continue
    ##
    out[pu.name] = alias
    out[pu] = alias
    out[tuple(sorted(pu.units.items(), key=lambda name_unit: name_unit[0]))] = alias
  ##
  return out
##


PhysicalUnit.standard_abbreviations = _createStandardAbbreviations()

PhysicalUnit.standard_prefixes = {
    Peta.total_value: 'P',
    Tera.total_value: 'T',
    Giga.total_value: 'G',
    Mega.total_value: 'M',
    Kilo.total_value: 'k',
    Centi.total_value: 'c',
    Milli.total_value: 'm',
    Micro.total_value: 'μ',
    Nano.total_value: 'n',
}
