# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field as Field
from enum import Enum
from functools import total_ordering
from math import ceil, log10
from pathlib import Path
from random import getrandbits
from time import localtime, strftime, struct_time, time
from typing import Optional, Union

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.path_util import getStemWithoutSuffix
from exhaust_plume.util.unset_util import Unset, UnsetType

__all__ = (
    'FormatSpecifier',
    'FormatData',
    'SimpleDateFormatPattern',
    'slugify',
    'slugifyFilepath',
)
######################################
log = getCleanLogger(__name__)


@total_ordering
class FormatSpecifier(Enum):
  # DOCME
  WeekdayAbbrev = '%a'
  WeekdayFull = '%A'
  MonthAbbrev = '%b'
  MonthFull = '%B'
  DateAndTimeRep = '%c'
  DayOfMonth = '%d'  # [01,31]
  DayOfMonthSpace = '%e'  # day of month with space instead of leading zero
  YearMonthDay = '%F'  # YYYY-MM-DD
  Hour = '%H'  # [00,23]
  Hour24 = Hour
  Hour12 = '%I'  # 12-Hour
  DayOfYear = '%j'  # [01,366]
  MonthNumber = '%m'  # [01,12]
  Minute = '%M'  # [0,59]
  AmPm = '%p'  # (AM|PM)
  Second = '%S'  # [0,61]
  WeekOfYear = '%U'  # Sunday first day of week, [0,53]
  WeekOfYearSunday = WeekOfYear
  # All days in a new year preceding the first Sunday are considered to be in week 0.
  DayOfWeek = '%w'  # [0(Sunday),6]
  WeekOfYearMonday = '%W'
  # Week number of the year (Monday as the first day of the week) as a decimal number [00,53].
  # All days in a new year preceding the first Monday are considered to be in week 0.
  DateRep = '%x'  # prints in locale order
  TimeRep = '%X'
  YearOfCentury = '%y'  # [0,99]
  Year = '%Y'
  TimeZoneNumber = '%z'
  TimeZoneName = '%Z'
  LiteralPercent = '%%'

  ConfigFile = '@ConfigFile'
  MonteIndex = '@MonteIndex'
  MonteTotal = '@MonteTotal'
  Random = '@Rand'

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


SimpleDateFormatPattern: str = f'{FormatSpecifier.Year.value}{FormatSpecifier.MonthNumber.value}{FormatSpecifier.DayOfMonth.value}_' \
                               f'{FormatSpecifier.Hour24.value}{FormatSpecifier.Minute.value}{FormatSpecifier.Second.value}'


@dataclass(frozen=True)
class FormatData:
  # DOCME
  config_file: Optional[Path] = None
  monte_index: Optional[int] = None
  monte_total: Optional[int] = None
  time_data: struct_time = Field(default_factory=lambda: localtime(time()))
  num_rand_bytes: int = 2

  def replace(self, *,
              config_file: Union[UnsetType, Optional[Path]] = Unset,
              monte_index: Union[UnsetType, Optional[int]] = Unset,
              monte_total: Union[UnsetType, Optional[int]] = Unset,
              time_data: Union[UnsetType, struct_time] = Unset,
              num_rand_bytes: Union[UnsetType, int] = Unset,
              ) -> FormatData:
    out = FormatData(
        config_file=self.config_file if isinstance(config_file, UnsetType) else config_file,
        monte_index=self.monte_index if isinstance(monte_index, UnsetType) else monte_index,
        monte_total=self.monte_total if isinstance(monte_total, UnsetType) else monte_total,
        time_data=self.time_data if isinstance(time_data, UnsetType) else time_data,
        num_rand_bytes=self.num_rand_bytes if isinstance(num_rand_bytes, UnsetType) else num_rand_bytes,
    )
    return out
  ##

  def format(self, format_str: str) -> str:
    # DOCME
    out = strftime(format_str, self.time_data)

    config_file_str = '' if self.config_file is None else getStemWithoutSuffix(self.config_file)
    out = out.replace(FormatSpecifier.ConfigFile.value, config_file_str)

    monte_total_str = '' if self.monte_total is None else str(self.monte_total)
    out = out.replace(FormatSpecifier.MonteTotal.value, monte_total_str)

    num_monte_width = int(ceil(log10(self.monte_total)) if self.monte_total is not None else 0.)
    monte_index_str = '' if self.monte_index is None else str(self.monte_index).zfill(num_monte_width)
    out = out.replace(FormatSpecifier.MonteIndex.value, monte_index_str)

    num_decimals = int(ceil(self.num_rand_bytes * 8 * log10(2.)))
    rand_num = getrandbits(8 * self.num_rand_bytes)
    rand_str = str(rand_num).zfill(num_decimals)
    out = out.replace(FormatSpecifier.Random.value, rand_str)
    return out
  ##
##


def slugify(value: str, allow_unicode: bool = False, replacement_char: str = '-') -> str:
  # DOCME
  """
  Taken from https://github.com/django/django/blob/master/django/utils/text.py
  Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
  dashes to single dashes. Remove characters that aren't alphanumerics,
  underscores, or hyphens. Convert to lowercase. Also strip leading and
  trailing whitespace, dashes, and underscores.
  """
  value = str(value)
  if allow_unicode:
    value = unicodedata.normalize('NFKC', value)
  else:
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
  ##
  value = re.sub(rf'[^{replacement_char}\w\s]+', '', value)
  return re.sub(r'\s+', replacement_char, value).strip(f'{replacement_char}_')
##


def slugifyFilepath(filepath: Path, allow_unicode: bool = False, replacement_char: str = '-') -> Path:
  """ Slugifies stem of a path"""
  filepath = Path(filepath)
  return (filepath.parent / slugify(filepath.stem, allow_unicode=allow_unicode, replacement_char=replacement_char)).with_suffix(filepath.suffix)
##
