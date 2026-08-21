# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from logging import Formatter, LogRecord, getLogger
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Mapping, Optional, Set, Tuple, Union

from exhaust_plume.log.extra_log_levels import CONFIG, CRITICAL, DEBUG, ERROR, INFO, NOTE, NOTSET, STATUS, TRACE, TRACE_EXTRA, VERBOSE, WARNING, getNameFromLevel
from exhaust_plume.log.terminal_format import (
    BG, BG_BLACK, BG_WHITE, BLINKING, BOLD, CLEAR_FORMAT, CLEAR_INTENSITY, FG, FGBG, FG_BLACK, FG_WHITE, UNDERLINE, determineClosestVisualColor, getNClosestColors,
    getNFurthestColors, removeFormat,
)
from exhaust_plume.util.color_util import ColorRGB
from exhaust_plume.util.unset_util import Unset, UnsetType

__all__ = (
    'ColoredFormatter',
    'loadColoredConfig',
)
#############################################

# TODO-List
# - Add option for simulation time formatter, right now is hardcoded ot "{:g}"
# - Add options to set colors for critical, error, warning, etc.

_formatter_lut = {
    '$RESET': CLEAR_FORMAT,
    '$BOLD': BOLD,
    '$UNDERLINE': UNDERLINE,
    '$BLINK': BLINKING,
}


def _createMessageFormat(message: str, use_color: bool = True) -> str:
  """ Creates a static string that the log.Formatter class uses to format the log record. """
  if use_color:
    for k, v in _formatter_lut.items():
      message = message.replace(k, v)
    ##
  else:
    for k in _formatter_lut.keys():
      message = message.replace(k, '')
    ##
  ##
  return message
##


_COLORS: DefaultDict[Union[str, int], str] = defaultdict(lambda: FG_WHITE, {
    'CRITICAL': FGBG('#141414', '#FF0000'),
    CRITICAL: FGBG('#141414', '#FF0000'),
    'ERROR': FG('#FF1800'),
    ERROR: FG('#FF1800'),
    'WARNING': FG('#FF8C00'),
    WARNING: FG('#FF8C00'),
    'INFO': FG('#CCCCCC'),
    INFO: FG('#CCCCCC'),
    'DEBUG': FG('#FFE11C'),
    DEBUG: FG('#FFE11C'),
    'STATUS': FG('#32CD32'),
    STATUS: FG('#32CD32'),
    'NOTE': FG('#00D9D5'),
    NOTE: FG('#00D9D5'),
    'CONFIG': FG('#008B8B'),
    CONFIG: FG('#008B8B'),
    'VERBOSE': FG('#1E90FF'),
    VERBOSE: FG('#1E90FF'),
    'TRACE': FG('#af61cc'),  # 0ccc1e
    TRACE: FG('#af61cc'),  # 9932CC
    'TRACE_EXTRA': FG('#DE5DCF'),
    TRACE_EXTRA: FG('#DE5DCF'),
    'NOTSET': FG('#FFFFFF'),
    NOTSET: FG('#FFFFFF'),
})


@dataclass(frozen=True)
class ExtraModuleFormatOptions:
  # DOCME
  icon: Optional[str] = None
  foreground_accent_color_escape: Optional[str] = None

  def replace(self, *,
              icon: Union[UnsetType, Optional[str]] = Unset,
              foreground_accent_color_escape: Union[UnsetType, Optional[str]] = Unset,
              ) -> ExtraModuleFormatOptions:
    out = ExtraModuleFormatOptions(
        icon=self.icon if isinstance(icon, UnsetType) else icon,
        foreground_accent_color_escape=self.foreground_accent_color_escape if isinstance(foreground_accent_color_escape, UnsetType) else foreground_accent_color_escape,
    )
    return out
  ##
##


class ColoredFormatter(Formatter):

  def __init__(self, *args: object, use_color: bool = True, use_icon: bool = True, **kwargs: object):
    # DOCME
    self.__use_color = bool(use_color)
    self.__use_icon = bool(use_icon)
    self.__extra_module_format: Dict[str, ExtraModuleFormatOptions] = dict()
    self.__sim_time_format: str = '{:4.2f}'
    fmt: Optional[Any] = None
    if 'fmt' in kwargs:
      fmt = kwargs.pop('fmt')
      if fmt is not None:
        fmt = _createMessageFormat(str(fmt), self.__use_color)
      ##
    ##
    self.__num_id_hash_chars = 4
    super().__init__(fmt, *args, **kwargs)  # type: ignore[arg-type]  # would pass in exact types, but python <3.7 does not have typing.Literal
  ##

  def setUseIcon(self, use_icon: bool) -> None:
    """ Enables or disables icon use. """
    self.__use_icon = bool(use_icon)
  ##

  def setUseColor(self, use_color: bool) -> None:
    """ Enables or disables color use. """
    self.__use_color = bool(use_color)
  ##

  def setModuleIcon(self, module_name: str, icon: str) -> None:
    # DOCME
    if module_name not in self.__extra_module_format:
      self.__extra_module_format[module_name] = ExtraModuleFormatOptions()
    ##
    self.__extra_module_format[module_name] = self.__extra_module_format[module_name].replace(icon=icon)
  ##

  def setModuleForegroundAccent(self, module_name: str, accent_color: str) -> None:
    # DOCME
    if module_name not in self.__extra_module_format:
      self.__extra_module_format[module_name] = ExtraModuleFormatOptions()
    ##
    self.__extra_module_format[module_name] = self.__extra_module_format[module_name].replace(foreground_accent_color_escape=FG(accent_color))
  ##

  def format(self, record: LogRecord) -> str:
    """ Modify the levelname to include the color """
    if self.__use_color:
      levelname = getNameFromLevel(record.levelno) or record.levelname
      record.levelname = f'{_COLORS[levelname]}{levelname}{CLEAR_FORMAT}'
    ##
    module_extra_format = self.__extra_module_format[record.name] if record.name in self.__extra_module_format else None
    use_accent_colors = self.__use_color and (module_extra_format is not None and module_extra_format.foreground_accent_color_escape is not None)
    ######
    # Modify the filename to skip the extension
    name_without_extension = Path(record.filename).stem
    if use_accent_colors and module_extra_format is not None and module_extra_format.foreground_accent_color_escape is not None:
      name_without_extension = module_extra_format.foreground_accent_color_escape + name_without_extension + CLEAR_FORMAT
    ##
    record.filename = name_without_extension
    ######
    # Actually format the record
    out = Formatter.format(self, record)
    ######
    # Add an icon
    if self.__use_icon and (module_extra_format is not None and module_extra_format.icon is not None):
      out = out.replace('$ICON', module_extra_format.icon)
    else:
      out = out.replace('$ICON', '')
    ##
    ######
    # Check for object stuff
    if hasattr(record, 'object'):
      obj = getattr(record, 'object')
      class_name = type(obj).__name__
      out = out.replace('$CLASS_NAME', f'{class_name}.')
      uid = obj.uid if hasattr(obj, 'uid') else (obj.getUid() if hasattr(obj, 'getUid') else None)
      proxy_uid = obj.proxy_uid if hasattr(obj, 'proxy_uid') else None
      owner_uid = obj.owner_uid if hasattr(obj, 'owner_uid') else None
      class_info_pieces: List[str] = []
      if owner_uid is not None:
        class_info_pieces.append(('o' if uid is not None else '') + f'{owner_uid}')
      ##
      if proxy_uid is not None:
        class_info_pieces.append(f'p{proxy_uid}')
      ##
      if uid is not None:
        class_info_pieces.append(f'{uid}')
      ##
      if len(class_info_pieces) == 0:
        # Append a hex of the object's python id
        id_hash_str = hex(id(obj))[2:]
        class_info_pieces.append(f'i{id_hash_str[:self.__num_id_hash_chars]}')
      ##
      class_info_pieces = [x for x in class_info_pieces if x is not None and x]
      if len(class_info_pieces) == 1:
        class_info = class_info_pieces[0]
      else:
        class_info = f'({":".join(x for x in class_info_pieces if x if not None and x)})'
      ##
      if self.__use_color:
        class_info = BOLD + class_info + CLEAR_INTENSITY
      ##
      out = out.replace('$CLASS_INFO', class_info)
    else:
      out = out.replace('$CLASS_NAME', '')
      out = out.replace('$CLASS_INFO', '')
    ##
    if hasattr(record, 'sim_time'):
      sim_time = getattr(record, 'sim_time')
      if sim_time is not None:
        out = out.replace('$SIM_TIME', 'Time:' + self.__sim_time_format.format(sim_time))
      else:
        out = out.replace('$SIM_TIME', '')
      ##
    else:
      out = out.replace('$SIM_TIME', '')
    ##
    ######
    if self.__use_color:
      # Make sure that line resets format
      out += CLEAR_FORMAT
    else:
      out = removeFormat(out)
    ##
    return out
  ##
##


def _getJndComment(jnd: float) -> str:
  # DOCME
  if jnd == 0:
    return 'Identical'
  elif jnd < 1:
    return 'Not noticeable'
  elif jnd < 4:
    return 'Noticeable'
  elif jnd < 15:
    return 'Significant'
  else:
    return 'Very Significant'
  ##
##


def _getExampleDisplay(color_rgb: ColorRGB) -> List[str]:
  # DOCME
  hex_code = color_rgb.asHexColorCode()
  fg = FG(hex_code)
  bg = BG(hex_code)
  out = [
      f'Foreground:{CLEAR_FORMAT}{fg}{hex_code} {BG_BLACK}{hex_code} {BG_WHITE}{hex_code} {CLEAR_FORMAT}',
      f'Background:{CLEAR_FORMAT}{bg}{hex_code} {FG_BLACK}{hex_code} {FG_WHITE}{hex_code} {CLEAR_FORMAT}',
  ]
  return out
##


def _getConfigColorDebug(config: Mapping[str, Any], num_example_alternates: int = 3, indent: str = '  ') -> str:
  # DOCME
  out_lines = []
  memos: List[Any] = [config, ]  # list of values pushed to stack to prevent object recursion
  num_example_alternates = max(1, num_example_alternates)
  ###
  # Recurse dictionary structure to discover all colors
  stack: List[Tuple[str, Any]] = [('', config)]
  name2specified_color: Dict[str, ColorRGB] = {}
  while stack:
    name_prefix, config = stack.pop()
    # Push all children keys if config is a dict
    try:
      this_prefix = f'{name_prefix}.' if name_prefix else ''
      for k, v in config.items():
        if v in memos:
          continue
        ##
        stack.append((f'{this_prefix}{k}', v,))
        memos.append(v)
      ##
      continue
    except AttributeError:
      pass
    ##
    # Try to display value if config is convertible to a color code
    try:
      color_rgb = ColorRGB.fromHexColorCode(str(config))
      name2specified_color[name_prefix] = color_rgb
      continue
    except (AttributeError, IndexError, ValueError, TypeError,):
      pass
    ##
    # Otherwise try to push configs children array elements
    try:
      if len(config) > 1:
        # make sure that item being pushed isn't the same thing over and over
        # e.g. if config = 'e' then it keeps pushing the same item over and over
        for idx, item in enumerate(config):
          if item in memos:
            continue
          ##
          stack.append((f'{name_prefix}[{idx}]', item,))
          memos.append(item)
        ##
      ##
      continue
    except (AttributeError, TypeError):
      pass
    ##
  ##
  ###
  specified_color2names: DefaultDict[Tuple[float, ...], Set[str]] = defaultdict(set)
  for name, specified_color in name2specified_color.items():
    specified_color2names[tuple(specified_color)].add(name)
  ##
  num_all_specified_colors = len(specified_color2names)
  specified_color2actual_color: Dict[Tuple[float, ...], ColorRGB] = {tuple_rgb: determineClosestVisualColor(ColorRGB.fromTuple(tuple_rgb)) for tuple_rgb in specified_color2names}
  num_all_actual_colors = len(specified_color2actual_color)
  num_total_collisions = num_all_specified_colors - num_all_actual_colors
  actual_color2specified_colors = defaultdict(set)
  actual_color2names: DefaultDict[Tuple[float, ...], Set[str]] = defaultdict(set)
  for spec_color_tup, actual_color in specified_color2actual_color.items():
    actual_color2specified_colors[tuple(actual_color)].add(spec_color_tup)
    actual_color2names[tuple(actual_color)].update(specified_color2names[spec_color_tup])
  ##
  out_lines.append('Logging Config Colors:')
  out_lines.append(f'Number of Specified Colors: {num_all_specified_colors}')
  out_lines.append(f'Number of Actual Colors: {num_all_actual_colors}')
  out_lines.append(f'Number of Color collisions: {num_total_collisions}')
  for actual_color_idx, (tuple_actual_rgb, specified_colors) in enumerate(actual_color2specified_colors.items()):
    actual_rgb = ColorRGB.fromTuple(tuple_actual_rgb)
    hex_code = actual_rgb.asHexColorCode()
    out_lines.append(f'- Actual Terminal Color: # {actual_color_idx + 1}/{num_all_actual_colors}')
    out_lines.append(indent * 2 + f'Actual Hex:{hex_code}')
    for example in _getExampleDisplay(actual_rgb):
      out_lines.append(indent * 2 + example)
    ##
    out_lines.append(indent * 2 + f'From Specified Colors: {len(specified_colors)}')
    num_specified_colors = len(specified_colors)
    for specified_color_idx, tuple_specified_rgb in enumerate(sorted(specified_colors)):
      specified_rgb = ColorRGB.fromTuple(tuple_specified_rgb)
      jnd = actual_rgb.calculateJustNoticeableDifference(specified_rgb)
      jnd_comment = _getJndComment(jnd)
      names = sorted(specified_color2names[tuple_specified_rgb])
      out_lines.append(indent * 2 + f'- Specified Color: # {specified_color_idx + 1:2d}/{num_specified_colors}')
      out_lines.append(indent * 3 + f'Specified Hex: {specified_rgb.asHexColorCode()}')
      out_lines.append(indent * 3 + f'Distance from Actual (ΔE):{jnd:3.1f}')
      out_lines.append(indent * 3 + f'Perception Difference from Actual: {repr(jnd_comment)}')
      num_names = len(names)
      out_lines.append(indent * 3 + f'Names:  # {num_names} total')
      for name in names:
        out_lines.append(indent * 4 + f'- {repr(name)}')
      ##
      if num_specified_colors > 1:
        # Show alternates if more than one color was specified (and thus collided)
        out_lines.append(indent * 3 + 'Next Best Terminal Color Examples:')
        closest_term_colors = getNClosestColors(specified_rgb, N=num_example_alternates + 1)
        closest_term_colors = closest_term_colors[1:]  # Skip the best because that one was already displayed
        for close_idx, term_color in enumerate(closest_term_colors):
          hex_code = term_color.asHexColorCode()
          jnd = specified_rgb.calculateJustNoticeableDifference(term_color)
          out_lines.append(indent * 4 + f'- Alternate Color Example # {close_idx + 1}/{num_example_alternates}')
          out_lines.append(indent * 5 + f'Hex: {repr(hex_code)}')
          out_lines.append(indent * 5 + f'ΔE: {jnd:3.1f}')
          for example in _getExampleDisplay(term_color):
            out_lines.append(indent * 5 + example)
          ##
        ##
      ##
    ##
    out_lines.append('')
  ##
  out_lines.append('')
  out_lines.append('All Actual Colors Palette (and Alternates):')
  for actual_idx, tuple_actual_rgb in enumerate(sorted(actual_color2specified_colors.keys())):
    out_lines.append(f'- Palette Color {actual_idx + 1}/{num_all_actual_colors}')
    actual_rgb = ColorRGB(*tuple_actual_rgb)
    hex_code = actual_rgb.asHexColorCode()
    out_lines.append(indent * 2 + f'Hex: {hex_code}')
    for example in _getExampleDisplay(actual_rgb):
      out_lines.append(indent * 2 + example)
    ##
    closest_term_colors = getNClosestColors(color=actual_rgb, N=num_example_alternates + 1)
    closest_term_colors = closest_term_colors[1:]  # best match is self
    out_lines.append(indent * 2 + f'Closest Alternates ({num_example_alternates}):')
    for idx, alternate_rgb in enumerate(closest_term_colors):
      jnd = actual_rgb.calculateJustNoticeableDifference(alternate_rgb)
      out_lines.append(indent * 3 + f'- Closest {idx + 1}/{num_example_alternates}:')
      out_lines.append(indent * 4 + f'Hex: {repr(alternate_rgb.asHexColorCode())}')
      out_lines.append(indent * 4 + f'ΔE: {jnd:3.1f}')
      for example in _getExampleDisplay(alternate_rgb):
        out_lines.append(indent * 4 + example)
      ##
    ##
    furthest_term_colors = getNFurthestColors(color=actual_rgb, N=num_example_alternates)
    out_lines.append(indent * 2 + f'Furthest Alternates ({num_example_alternates}):')
    for idx, alternate_rgb in enumerate(furthest_term_colors):
      jnd = actual_rgb.calculateJustNoticeableDifference(alternate_rgb)
      out_lines.append(indent * 3 + f'- Furthest {idx + 1}/{num_example_alternates}:')
      out_lines.append(indent * 4 + f'Hex: {repr(alternate_rgb.asHexColorCode())}')
      out_lines.append(indent * 4 + f'ΔE: {jnd:3.1f}')
      for example in _getExampleDisplay(alternate_rgb):
        out_lines.append(indent * 4 + example)
      ##
    ##
  ##
  out_lines.append('')
  return '\n'.join(out_lines)
##


def loadColoredConfig(config: Mapping[str, Any]) -> None:
  # DOCME
  print_debug_colors = config.get('debug_colors', False)
  if print_debug_colors:
    try:
      print(_getConfigColorDebug(config['debug_colors']))
    except Exception as e:
      print(f'Caught exception:{e} while trying to print config debug colors')
    ##
  ##
  colored_config_options = config.get('colored_formatter_options', {})
  use_colors = colored_config_options.get('use_colors', True)
  use_icons = colored_config_options.get('use_icons', True)

  if 'loggers' not in config or config['loggers'] is None:
    return
  ##
  loggers = config['loggers']
  if not hasattr(loggers, 'items'):
    return
  ##
  for logger_module_name, logger_config in loggers.items():
    module_log = getLogger(logger_module_name)
    if not hasattr(module_log, 'handlers'):
      continue
    ##
    handlers = module_log.handlers
    try:
      for handler in handlers:
        if not hasattr(handler, 'formatter'):
          continue
        ##
        formatter = handler.formatter
        if formatter is None:
          continue
        ##
        if isinstance(formatter, ColoredFormatter):
          formatter.setUseColor(use_color=use_colors)
          formatter.setUseIcon(use_icon=use_icons)
          if 'icon' in logger_config and hasattr(formatter, 'setModuleIcon'):
            formatter.setModuleIcon(logger_module_name, logger_config['icon'])
          ##
          if 'foreground_accent_color' in logger_config and hasattr(formatter, 'setModuleForegroundAccent'):
            formatter.setModuleForegroundAccent(logger_module_name, logger_config['foreground_accent_color'])
          ##
        ##
      ##
    except (AttributeError, TypeError,):
      pass
    ##
  ##
##
