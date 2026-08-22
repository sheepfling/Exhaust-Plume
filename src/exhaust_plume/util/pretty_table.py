"""Minimal text table formatter for command-line plume summaries."""

from __future__ import annotations

from typing import Any, Hashable, Mapping, Sequence

__all__ = ('PrettyTable',)


class PrettyTable:
  """Render a list of row dictionaries without a terminal-formatting dependency."""

  def __init__(
      self,
      list_of_dicts: Sequence[Mapping[Hashable, Any]],
      title: str = '',
      show_border: bool = True,
      show_row_index: bool = False,
      **_: Any,
  ) -> None:
    self._rows = list(list_of_dicts)
    self._title = title
    self._show_border = show_border
    self._show_row_index = show_row_index

  def get_string(self, *, show_header: bool = True, show_row_index: bool = False) -> str:
    if not self._rows:
      return self._title

    keys = list(self._rows[0])
    include_index = show_row_index or self._show_row_index
    headers = (['#'] if include_index else []) + [str(key) for key in keys]
    values = []
    for index, row in enumerate(self._rows):
      values.append((([str(index)] if include_index else []) + [self._format(row.get(key)) for key in keys]))

    widths = [len(header) for header in headers]
    for row in values:
      widths = [max(width, len(value)) for width, value in zip(widths, row)]

    def line(fill: str = '-') -> str:
      return '+'.join(fill * (width + 2) for width in widths)

    def row_line(row: Sequence[str]) -> str:
      return '|'.join(f' {value:>{width}} ' for value, width in zip(row, widths))

    output = []
    if self._title:
      output.append(self._title)
    if self._show_border:
      output.append(line())
    if show_header:
      output.append(row_line(headers))
      if self._show_border:
        output.append(line('='))
    output.extend(row_line(row) for row in values)
    if self._show_border:
      output.append(line())
    return '\n'.join(output)

  @staticmethod
  def _format(value: Any) -> str:
    return '' if value is None else str(value)
