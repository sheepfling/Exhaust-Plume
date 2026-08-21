# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto as getAutoEnumValue
from functools import total_ordering
from itertools import chain
from typing import Any, ClassVar, DefaultDict, Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, TypeVar, Union

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.log.terminal_colormaps import ColorMap, getConstantColorMap
from exhaust_plume.log.terminal_format import BOLD, CLEAR_FORMAT, CLEAR_INTENSITY, CLEAR_UNDERLINE, FAINT, TerminalFormat, UNDERLINE, getLengthWithoutFormat
from exhaust_plume.util.color_util import ColorRGB
from exhaust_plume.util.dict_util import lod2dol
from exhaust_plume.util.misc import deduplicateStable, tryFloatOrDefault, tryFloatOrNan

__all__ = (
    'Justify',
    'ColumnSortOrder',
    'ColumnColorOption',
    'PrettyTable',
)
######################################
log = getCleanLogger(__name__)

T = TypeVar('T')


@total_ordering
class Justify(Enum):
  # DOCME
  Left = getAutoEnumValue()
  Right = getAutoEnumValue()
  Center = getAutoEnumValue()
  Default = Left

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.name < other.name
    ##
    return NotImplemented
  ##
##


@total_ordering
class ColumnSortOrder(Enum):
  AsIs = getAutoEnumValue()
  Ascending = getAutoEnumValue()
  Descending = getAutoEnumValue()

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@dataclass(frozen=True)
class ColumnColorOption:
  cmap: Optional[ColorMap] = None
  color: Optional[ColorRGB] = None
  order: ColumnSortOrder = ColumnSortOrder.AsIs

  def getColorMap(self) -> Optional[ColorMap]:
    if self.cmap is not None:
      return self.cmap
    elif self.color is not None:
      return getConstantColorMap(self.color)
    ##
    return None
  ##
##


def _padJustify(value: str, length: int, pad: str, justify: Optional[Justify]) -> str:
  # DOCME
  """
  pad: assumes pad displays as a single char
  """
  value_len = getLengthWithoutFormat(value)
  total_pad_len = length - value_len
  if justify == Justify.Left:
    left_pad_len = 0
    right_pad_len = total_pad_len
  elif justify == Justify.Right:
    left_pad_len = total_pad_len
    right_pad_len = 0
  elif justify == Justify.Center:
    left_pad_len = total_pad_len // 2
    right_pad_len = (total_pad_len + 1) // 2
  else:
    left_pad_len = total_pad_len
    right_pad_len = 0
  ##
  out = [
      left_pad_len * pad,
      value,
      right_pad_len * pad,
  ]
  return ''.join(out)
##


def _getTableTitleLine(title: str, table_width: int, bold_title: bool, underline_title: bool,
                       pad: str = ' ', justify: Justify = Justify.Center) -> str:
  # DOCME
  title_formatted = ''.join([
      BOLD * bold_title,
      UNDERLINE * underline_title,
      title,
      CLEAR_UNDERLINE * underline_title,
      CLEAR_INTENSITY * bold_title,
  ])
  out = _padJustify(
      value=title_formatted,
      length=table_width,
      pad=pad,
      justify=justify
  )
  return out
##


def _getTableRow(contents: Mapping[Hashable, str], widths: Mapping[Any, int], column_order: Iterable[Hashable],
                 show_borders: bool, pad: str, spacer: str, faint_spacer: bool,
                 bold_values: bool, underline_values: bool,
                 justification: Optional[Mapping[Any, Optional[Justify]]] = None,
                 ) -> str:
  # DOCME
  value_prefix = ''.join((
      BOLD * bold_values,
      UNDERLINE * underline_values,
  ))
  value_suffix = ''.join((
      CLEAR_INTENSITY * bold_values,
      CLEAR_UNDERLINE * underline_values,
  ))
  out = []
  if show_borders:
    if faint_spacer:
      out.append(FAINT)
    ##
    out.append(spacer)
    out.append(pad)
    if faint_spacer:
      out.append(CLEAR_INTENSITY)
    ##
  ##
  for col_idx, col in enumerate(column_order):
    if col_idx > 0:
      if faint_spacer:
        out.append(FAINT)
      ##
      out.append(pad)
      if faint_spacer:
        out.append(CLEAR_INTENSITY)
      ##
    ##
    out.append(_padJustify(
        value=f'{value_prefix}{contents[col]}{value_suffix}',
        length=widths[col],
        justify=justification[col] if (justification is not None and col in justification) else Justify.Default,
        pad=' ',
    ))
    if show_borders:
      if faint_spacer:
        out.append(FAINT)
      ##
      out.append(pad)
      out.append(spacer)
      if faint_spacer:
        out.append(CLEAR_INTENSITY)
      ##
    ##
  ##
  return ''.join(out)
##


def _areAllNumeric(values: Sequence[Any]) -> bool:
  # DOCME
  is_numeric = all(tryFloatOrDefault(v, None) is not None for v in values)
  return is_numeric
##


def _applySort(values: Sequence[str], option: ColumnSortOrder, use_numeric_sort: bool = False) -> Sequence[str]:
  # DOCME
  if use_numeric_sort:
    if option == ColumnSortOrder.Ascending:
      return sorted(values, key=lambda v: tryFloatOrNan(v))
    elif option == ColumnSortOrder.Descending:
      return sorted(values, reverse=True, key=lambda v: tryFloatOrNan(v))
    ##
  else:
    if option == ColumnSortOrder.Ascending:
      return sorted(values)
    elif option == ColumnSortOrder.Descending:
      return sorted(values, reverse=True)
    ##
  ##
  return values
##


def _applyColormap(values: Sequence[str], fg_opt: Optional[ColumnColorOption], bg_opt: Optional[ColumnColorOption], is_numeric: bool) -> List[str]:
  # DOCME
  if fg_opt is None and bg_opt is None:
    return list(values)
  ##
  uniq_values = deduplicateStable(values)
  fg_colors: Dict[str, Optional[ColorRGB]] = {value: None for value in uniq_values}
  if fg_opt is not None:
    fg_map = fg_opt.getColorMap() if fg_opt is not None else None
    if fg_map is not None:
      fg_colors = {value: color for value, color in zip(_applySort(uniq_values, fg_opt.order, use_numeric_sort=is_numeric), fg_map(len(uniq_values)))}
    ##
  ##
  bg_colors: Dict[str, Optional[ColorRGB]] = {value: None for value in uniq_values}
  if bg_opt is not None:
    bg_map = bg_opt.getColorMap() if bg_opt is not None else None
    if bg_map is not None:
      bg_colors = {value: color for value, color in zip(_applySort(uniq_values, bg_opt.order, use_numeric_sort=is_numeric), bg_map(len(uniq_values)))}
    ##
  ##
  value2format = {value: TerminalFormat(foreground_color=fg_colors[value], background_color=bg_colors[value]).getModifierString() for value in uniq_values}
  out: List[str] = []
  for value in values:
    fmt = value2format[value]
    out.append(f'{fmt}{value}{CLEAR_FORMAT}')
  ##
  return out
##


class PrettyTable:
  # DOCME
  __INDEX: ClassVar[Hashable] = object()
  DEFAULT_PAD = ' '
  DEFAULT_SPACER = '|'
  DEFAULT_JUNCTION_SPACER = '+'
  DEFAULT_JUNCTION_PAD = '-'
  DEFAULT_COLUMN_JUSTIFY_NUMERIC = Justify.Right
  DEFAULT_COLUMN_JUSTIFY_OTHER = Justify.Left

  def __init__(
      self,
      list_of_dicts: Iterable[Mapping[Any, Any]],
      *,
      title: Optional[str] = None, show_title: Optional[bool] = None, bold_title: Optional[bool] = None, underline_title: Optional[bool] = None,
      justify_title: Optional[Justify] = None,
      show_border: Optional[bool] = None, faint_border: Optional[bool] = None,
      show_header: Optional[bool] = None, bold_header: Optional[bool] = None, underline_header: Optional[bool] = None,
      show_row_index: Optional[bool] = None,
      column_justification: Optional[Mapping[Hashable, Justify]] = None,
      column_fg_colormaps: Optional[Mapping[Hashable, ColumnColorOption]] = None,
      column_bg_colormaps: Optional[Mapping[Hashable, ColumnColorOption]] = None,
  ):
    # DOCME
    #####
    # Data
    self.data = [dict(d) for d in list_of_dicts]
    self.__column2index = {self.__INDEX: 0}
    #####
    # Pads/Junctions
    self.pad: str = self.DEFAULT_PAD
    self.spacer: str = self.DEFAULT_SPACER
    self.junction_spacer: str = self.DEFAULT_JUNCTION_SPACER
    self.junction_pad: str = self.DEFAULT_JUNCTION_PAD
    #####
    # Title
    self.title: Optional[str] = title
    self.show_title: bool = True if show_title is None else bool(show_title)
    self.bold_title: bool = True if bold_title is None else bool(bold_title)
    self.underline_title: bool = True if underline_title is None else bool(underline_title)
    self.justify_title: Justify = Justify.Center if justify_title is None else justify_title
    #####
    # Border
    self.show_border: bool = True if show_border is None else bool(show_border)
    self.faint_border: bool = True if faint_border is None else bool(faint_border)
    #####
    # Header
    self.show_header: bool = True if show_header is None else bool(show_header)
    # If not specified then bold, unless no borders then not bold
    self.bold_header: Optional[bool] = None if bold_header is None else bool(bold_header)
    # If not specified then no underline, unless no borders then underline
    self.underline_header: Optional[bool] = underline_header
    #####
    self.show_row_index: bool = True if show_row_index is None else bool(show_row_index)
    #####
    # Get column ordering
    for index, row in enumerate(self.data):
      row[self.__INDEX] = index
      for header, value in row.items():
        if header not in self.__column2index:
          self.__column2index[header] = len(self.__column2index)
        ##
      ##
    ##
    #####
    # Column Justification
    self.__numeric_cols: Dict[Hashable, bool] = {col: _areAllNumeric(values) for col, values in lod2dol(self.data).items()}
    self.__col_just = {col: (self.DEFAULT_COLUMN_JUSTIFY_NUMERIC if is_numeric else self.DEFAULT_COLUMN_JUSTIFY_OTHER) for col, is_numeric in self.__numeric_cols.items()}
    if column_justification is not None:
      for col, just in column_justification.items():
        if just not in Justify:
          log.info(f'Invalid Justification value:{just} for column:{col!r}')
          continue
        ##
        self.__col_just[col] = just
      ##
    ##
    self.__col_fg_maps: Mapping[Hashable, ColumnColorOption] = dict(column_fg_colormaps) if column_fg_colormaps is not None else {}
    self.__col_bg_maps: Mapping[Hashable, ColumnColorOption] = dict(column_bg_colormaps) if column_bg_colormaps is not None else {}
  ##

  @classmethod
  def getIndexColumn(cls) -> Hashable:
    # DOCME
    return cls.__INDEX
  ##

  @property
  def columns(self) -> List[Hashable]:
    # DOCME
    col_idx = list(self.__column2index.items())
    col_idx.sort(key=lambda kv: kv[1])
    cols = [col for col, idx in col_idx]
    return cols
  ##

  def get_string(
      self, *,
      title: Optional[str] = None, show_title: Optional[bool] = None,
      bold_title: Optional[bool] = None, underline_title: Optional[bool] = None,
      justify_title: Optional[Justify] = None,
      show_border: Optional[bool] = None, faint_border: Optional[bool] = None,
      show_header: Optional[bool] = None, bold_header: Optional[bool] = None, underline_header: Optional[bool] = None,
      show_row_index: Optional[bool] = None,
      column_justification: Optional[Dict[Hashable, Justify]] = None,
      center_table_under_large_title: bool = True,
      line_prefix: Union[str, int] = 0
  ) -> str:
    # DOCME
    ############
    # Border
    if show_border is None:
      show_border = self.show_border
    ##
    if faint_border is None:
      faint_border = self.faint_border
    ##
    ############
    # Title
    if title is None:
      title = self.title
    ##
    if (self.show_title is not None and not self.show_title) or (show_title is not None and not show_title):
      title = None
    ##
    if bold_title is None:
      bold_title = self.bold_title
    ##
    if underline_title is None:
      underline_title = self.underline_title
    ##
    if justify_title is None:
      justify_title = self.justify_title
    ##
    ############
    # Header
    if show_header is None:
      show_header = self.show_header
    ##
    if bold_header is None:
      bold_header = self.bold_header
    ##
    if bold_header is None:
      if show_border:
        bold_header = True
      else:
        bold_header = False
      ##
    ##
    if underline_header is None:
      underline_header = self.underline_header
    ##
    if underline_header is None:
      if show_border:
        underline_header = False
      else:
        underline_header = True
      ##
    ##
    ############
    if show_row_index is None:
      show_row_index = self.show_row_index
    ##
    ############
    # Offset
    if isinstance(line_prefix, int):
      line_prefix = ' ' * line_prefix
    ##
    ############
    # Columns
    if column_justification is None:
      nonopt_column_justification = self.__col_just
    else:
      nonopt_column_justification = {**self.__col_just, **column_justification}
    ##
    column2name: Dict[Hashable, str] = {col: str(col) for col in (self.columns if show_row_index else self.columns[1:])}
    if show_row_index:
      column2name[self.__INDEX] = 'Index'
    ##
    row_strings: Sequence[DefaultDict[Hashable, str]] = [defaultdict(str, {col: str(val) if val is not None else '' for col, val in row.items()}) for row in self.data]
    if not row_strings:
      row_strings = [defaultdict(str, {'': 'No Data', }), ]
      column2name[''] = ''
      show_header = False
    ##
    for col in column2name.keys():
      values = _applyColormap(
          values=[row[col] for row in row_strings],
          fg_opt=self.__col_fg_maps.get(col, None),
          bg_opt=self.__col_bg_maps.get(col, None),
          is_numeric=self.__numeric_cols[col] if col in self.__numeric_cols else False,
      )
      for row_idx, value in enumerate(values):
        row_strings[row_idx][col] = value
      ##
    ##
    column_widths = {col: [getLengthWithoutFormat(row[col]) for row in row_strings] for col in column2name}
    max_column_widths = {col: max(widths) if widths else 0 for col, widths in column_widths.items()}
    max_column_widths = {col: max(getLengthWithoutFormat(column2name[col]), width) for col, width in max_column_widths.items()}

    column_pad = getLengthWithoutFormat(self.pad) + (getLengthWithoutFormat(self.spacer) if show_border else 0)
    table_pad = len(max_column_widths) * column_pad + (1 if show_border else -1) * getLengthWithoutFormat(self.pad)
    table_width = sum(max_column_widths.values()) + table_pad
    title_lines: List[str] = []
    if title is not None:
      title_lines.append(
          _getTableTitleLine(
              title=title,
              table_width=table_width,
              bold_title=bold_title,
              underline_title=underline_title,
              pad=' ',
              justify=justify_title
          )
      )
    ##
    #########
    # Top Line
    table_lines: List[str] = []
    spacer_contents = {col: self.junction_pad * width for col, width in max_column_widths.items()}
    if faint_border:
      for col, content in spacer_contents.items():
        spacer_contents[col] = f'{FAINT}{content}{CLEAR_INTENSITY}'
      ##
    ##
    spacer_line = _getTableRow(
        contents=spacer_contents,
        widths=max_column_widths,
        column_order=column2name.keys(),
        spacer=self.junction_spacer,
        pad=self.junction_pad,
        show_borders=True,
        bold_values=False,
        underline_values=False,
        faint_spacer=faint_border,
        justification=None,
    )
    if show_border:
      table_lines.append(spacer_line)
    ##
    if show_header:
      # Header Columns
      header_just = {col: (Justify.Center if show_border else Justify.Left) for col in column2name.keys()}
      table_lines.append(
          _getTableRow(
              contents=column2name,
              widths=max_column_widths,
              column_order=column2name.keys(),
              spacer=self.spacer,
              pad=self.pad,
              show_borders=show_border,
              bold_values=bold_header,
              underline_values=underline_header,
              faint_spacer=faint_border,
              justification=header_just,
          )
      )
      if show_border:
        table_lines.append(spacer_line)
      ##
    ##
    #########
    # Table Body
    table_lines.extend(
        _getTableRow(
            contents=row,
            widths=max_column_widths,
            column_order=column2name.keys(),
            spacer=self.spacer,
            pad=self.pad,
            show_borders=show_border,
            bold_values=False,
            underline_values=False,
            faint_spacer=faint_border,
            justification=nonopt_column_justification,
        ) for row in row_strings
    )
    #########
    # End Table
    if show_border:
      table_lines.append(spacer_line)
    ##
    #########
    title_width: int = 0 if title is None else len(title)
    table_left_pad = (' ' * ((title_width - table_width) // 2)) if (center_table_under_large_title and table_width < title_width) else ''
    out = '\n'.join(line_prefix + line for line in chain(
        title_lines,
        (table_left_pad + line for line in table_lines),
    ))
    return out
  ##

##
