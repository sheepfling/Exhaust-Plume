# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from itertools import product
from typing import ClassVar, Dict, List, Optional, Set, Tuple, Union

from numpy import argmin, argsort, vstack
from numpy.linalg import norm

from exhaust_plume.util.cache_decorator import cache
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.color_util import ColorRGB, StandardRGB
from exhaust_plume.util.unset_util import Unset, UnsetType

__all__ = (
    'SelectGraphicRendition', 'getAllTerminalColors',
    'determineClosestVisualColorCode', 'determineClosestVisualColor',
    'getNClosestColors', 'getNFurthestColors', 'FontTypeOption', 'ConcealOption',
    'StrikeThroughOption', 'BlinkOption', 'UnderlineOption', 'FrameOption',
    'OverlineOption', 'ScriptOption', 'ProportionalSpacingOption', 'ReverseVideoOption',
    'FontOption', 'ForegroundOption', 'BackgroundOption', 'TerminalFormat',
    'CLEAR_FORMAT', 'BOLD', 'FAINT', 'CLEAR_INTENSITY',
    'BLINKING', 'UNDERLINE', 'CLEAR_UNDERLINE', 'FG_BLACK',
    'FG_RED', 'FG_GREEN', 'FG_YELLOW', 'FG_BLUE',
    'FG_MAGENTA', 'FG_CYAN', 'FG_WHITE', 'BG_BLACK',
    'BG_RED', 'BG_GREEN', 'BG_YELLOW', 'BG_BLUE',
    'BG_MAGENTA', 'BG_CYAN', 'BG_WHITE', 'FG',
    'BG', 'FGBG', 'removeFormat', 'getLengthWithoutFormat',
)
#############################

_format_rgx = re.compile(r'\x1b\[([0-9;]+)m')


@total_ordering
class SelectGraphicRendition(Enum):
  # DOCME
  Reset = 0  # Reset or normal	All attributes off
  Bold = 1  # Bold or increased intensity: As with faint, the color change is a PC (SCO / CGA) invention.
  Faint = 2  # Faint, decreased intensity, or dim: May be implemented as a light font weight like bold.
  Italic = 3  # Italic: Not widely supported. Sometimes treated as inverse or blink.
  FontTypeItalic = Italic  # alias ^
  Underline = 4  # Underline: Style extensions exist for Kitty, VTE, mintty and iTerm2.
  BlinkSlow = 5  # Slow blink: Sets blinking to less than 150 times per minute
  BlinkFast = 6  # Rapid blink: MS-DOS ANSI.SYS, 150+ per minute; not widely supported
  ReverseVideo = 7  # Reverse video or invert: Swap foreground and background colors; inconsistent emulation
  Conceal = 8  # Conceal or hide: Not widely supported.
  Strikethrough = 9  # Crossed-out, or strike: Characters legible but marked as if for deletion. Not supported in Terminal.app
  FontPrimary = 10  # Primary (default) font:
  AlternateFont0 = FontPrimary
  # 11-19: Alternative font: Select alternative font n − 10
  AlternateFont1 = 11
  AlternateFont2 = 12
  AlternateFont3 = 13
  AlternateFont4 = 14
  AlternateFont5 = 15
  AlternateFont6 = 16
  AlternateFont7 = 17
  AlternateFont8 = 18
  AlternateFont9 = 19
  Fraktur = 20  # Fraktur (Gothic): Rarely supported
  FontTypeFraktur = Fraktur  # alias ^
  FontTypeBlackLetter = Fraktur  # alias ^
  UnderlineDouble = 21  # Doubly underlined; or: not bold: Double-underline per ECMA-48,[5]: 8.3.117  but instead disables bold intensity on several terminals, including in the Linux kernel's console before version 4.17.
  IntensityNormal = 22  # Normal intensity: Neither bold nor faint; color changes where intensity is implemented as such.
  FontTypeNot = 23  # Neither italic, nor blackletter:
  UnderlineNot = 24  # Not underlined: Neither singly nor doubly underlined
  BlinkingNot = 25  # Not blinking: Turn blinking off
  ProportionalSpacing = 26  # Proportional spacing: ITU T.61 and T.416, not known to be used on terminals
  ReverseVideoNot = 27  # Not reversed:
  ConcealNot = 28  # Reveal: Not concealed
  Reveal = ConcealNot  # alias ^
  StrikethroughNot = 29  # Not crossed out:
  # Value =  30–37      # Set foreground color:
  SetForegroundBlack = 30
  SetForegroundRed = 31
  SetForegroundGreen = 32
  SetForegroundYellow = 33
  SetForegroundBlue = 34
  SetForegroundMagenta = 35
  SetForegroundCyan = 36
  SetForegroundWhite = 37
  # Value =  38         # Set foreground color: Next arguments are 5;n or 2;r;g;b
  # (2;r;g;b seems to not be supported widely)
  SetForegroundCustom = 38
  SetForegroundDefault = 39  # Default foreground color: Implementation defined (according to standard)
  # Value =  40–47      # Set background color:
  SetBackgroundBlack = 30
  SetBackgroundRed = 31
  SetBackgroundGreen = 32
  SetBackgroundYellow = 33
  SetBackgroundBlue = 34
  SetBackgroundMagenta = 35
  SetBackgroundCyan = 36
  SetBackgroundWhite = 37
  # Value =  48         # Set background color: Next arguments are 5;n or 2;r;g;b
  # (2;r;g;b seems to not be supported widely)
  SetBackgroundCustom = 48
  SetBackgroundDefault = 49  # Default background color: Implementation defined (according to standard)
  ProportionalSpacingNot = 50  # Disable proportional spacing
  FrameRectangle = 51  # Framed: Implemented as "emoji variation selector" in mintty.
  FrameCircle = 52  # Encircled
  Encircled = FrameCircle  # alias ^
  Overlined = 53  # Overlined: Not supported in Terminal.app
  FramedNot = 54  # Neither framed nor encircled:
  OverlinedNot = 55  # Not overlined:
  SetUnderlineColor = 58  # Set underline color: Not in standard; implemented in Kitty, VTE, mintty, and iTerm2. Next arguments are 5;n or 2;r;g;b.
  SetUnderlineColorDefault = 59  # Default underline color: Not in standard; implemented in Kitty, VTE, mintty, and iTerm2.
  # Ideogram or Sideline Settings
  IdeogramUnderline = 60  # Ideogram underline or right side line: Rarely supported
  SideLineRight = IdeogramUnderline  # alternate implementation ^
  IdeogramUnderlineDouble = 61  # Ideogram double underline, or double line on the right side
  SideLineRightDouble = IdeogramUnderlineDouble  # alternate implementation ^
  IdeogramOverline = 62  # Ideogram overline or left side line
  SideLineLeft = IdeogramOverline  # alternate implementation ^
  IdeogramOverlineDouble = 63  # Ideogram double overline, or double line on the left side
  SideLineLeftDouble = IdeogramOverlineDouble  # alternate implementation ^
  IdeogramStressMarking = 64  # Ideogram stress marking
  IdeogramReset = 65  # No ideogram attributes: Reset the effects of all of 60–64
  ScriptSuper = 73  # Superscript: Implemented only in mintty
  SuperScript = ScriptSuper  # alias ^
  ScriptSub = 74  # Subscript
  SubScript = ScriptSub  # alias ^
  ScriptNot = 75  # Neither superscript nor subscript
  # Value =  90–97      # Set bright foreground color: Not in standard; originally implemented by aixterm
  SetForegroundBlackBright = 90
  SetForegroundRedBright = 91
  SetForegroundGreenBright = 92
  SetForegroundYellowBright = 93
  SetForegroundBlueBright = 94
  SetForegroundMagentaBright = 95
  SetForegroundCyanBright = 96
  SetForegroundWhiteBright = 97
  # Value =  100–107    #	Set bright background color
  SetBackgroundBlackBright = 100
  SetBackgroundRedBright = 101
  SetBackgroundGreenBright = 102
  SetBackgroundYellowBright = 103
  SetBackgroundBlueBright = 104
  SetBackgroundMagentaBright = 105
  SetBackgroundCyanBright = 106
  SetBackgroundWhiteBright = 107

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


def getAllTerminalColors() -> Dict[int, ColorRGB]:
  # DOCME
  # Custom Foreground/Background 256 color code
  # Used in conjunction with 5;{number} color escape code

  # Standard colors are defined in this order
  standard_colors: Dict[int, Tuple[int, int, int]] = {
      0: (0, 0, 0,),  # black
      1: (1, 0, 0,),  # red
      2: (0, 1, 0,),  # green
      3: (1, 1, 0,),  # yellow
      4: (0, 0, 1,),  # blue
      5: (1, 0, 1,),  # magenta
      6: (0, 1, 1,),  # cyan
      7: (1, 1, 1,),  # white
  }

  all_colors: Dict[int, Tuple[int, int, int]] = {}

  # First [0,16) are standard, then high-intensity (same order)
  for num, color_tuple in standard_colors.items():
    # Standard Colors: channel * 0x80
    all_colors[num] = (color_tuple[0] * 0x80, color_tuple[1] * 0x80, color_tuple[2] * 0x80,)
    # High-Intense number = standard number + 8
    # High-Intensity Colors: channel * 0xFF
    all_colors[num + 8] = (color_tuple[0] * 0xFF, color_tuple[1] * 0xFF, color_tuple[2] * 0xFF,)
  ##

  # Next set [16, 232) is a 6x6x6 color cube
  color_cube_num_offset = 16
  color_cube_color_start_after_0 = 0x5F
  color_cube_color_increment = 40
  color_cube_channel_numbers = 6

  for color_idx, rgb_idxs in enumerate(product(*[list(range(color_cube_channel_numbers))] * 3)):
    color_num = color_idx + color_cube_num_offset
    color = tuple(0 if c == 0 else (color_cube_color_start_after_0 + (c - 1) * color_cube_color_increment) for c in rgb_idxs)
    all_colors[color_num] = (color[0], color[1], color[2],)
  ##

  grayscale_num_offset = 232
  grayscale_numbers = 24
  grayscale_color_start = 8
  grayscale_color_increment = 10

  for grayscale_idx in range(grayscale_numbers):
    grayscale_num = grayscale_num_offset + grayscale_idx
    grayscale_color = (grayscale_color_start + grayscale_idx * grayscale_color_increment,) * 3
    all_colors[grayscale_num] = grayscale_color
  ##
  out: Dict[int, ColorRGB] = {}
  output_colors: Set[Tuple[int, int, int]] = set()
  for num, standard_rgb in all_colors.items():
    if standard_rgb in output_colors:
      # Don't add duplicate colors
      continue
    ##
    out[num] = ColorRGB.fromStandardRgb(StandardRGB(r=standard_rgb[0], g=standard_rgb[1], b=standard_rgb[2]))
    output_colors.add(standard_rgb)
  ##
  return out
##


_all_terminal_colors = getAllTerminalColors()
# Matrix of ITP(scaled) representation of all terminal colors
_all_terminal_index_to_code: Dict[int, int] = {idx: code for idx, code in enumerate(sorted(_all_terminal_colors.keys()))}
_terminal_colors_itps_matrix = vstack([rgb.asItpScaled() for num, rgb in sorted(_all_terminal_colors.items())])


@cache
def _determineClosestVisualColorCode(color: Tuple[float, float, float]) -> int:
  # DOCME
  color_rgb = ColorRGB(r=color[0], g=color[1], b=color[2])
  query_itp = color_rgb.asItpScaled()
  distances = norm(_terminal_colors_itps_matrix - query_itp, axis=-1)
  min_idx = int(argmin(distances))
  code = _all_terminal_index_to_code[min_idx]
  return int(code)
##


def determineClosestVisualColorCode(color: ColorRGB) -> int:
  # DOCME
  # Wraps the cached version with a tuple call to make sure the object is hashable
  code = _determineClosestVisualColorCode(color.asTuple())
  return int(code)
##


def determineClosestVisualColor(color: ColorRGB) -> ColorRGB:
  # DOCME
  # Wraps the cached version with a tuple call to make sure the object is hashable
  code = _determineClosestVisualColorCode(color.asTuple())
  term_color = _all_terminal_colors[code]
  return term_color
##


def getNClosestColors(color: ColorRGB, N: int) -> List[ColorRGB]:
  # DOCME
  color = ColorRGB(*color)
  query_itps = color.asItpScaled()
  distances = norm(_terminal_colors_itps_matrix - query_itps, axis=-1)
  sort_idx = argsort(distances)
  closest_idx = sort_idx[:N]
  out = [_all_terminal_colors[_all_terminal_index_to_code[idx]] for idx in closest_idx]
  return out
##


def getNFurthestColors(color: ColorRGB, N: int) -> List[ColorRGB]:
  # DOCME
  color = ColorRGB(*color)
  query_itps = color.asItpScaled()
  distances = norm(_terminal_colors_itps_matrix - query_itps, axis=-1)
  sort_idx = argsort(distances)
  furthest_idx = sort_idx[-N:]
  out = [_all_terminal_colors[_all_terminal_index_to_code[idx]] for idx in furthest_idx]
  return out
##


@total_ordering
class Intensity(Enum):
  # DOCME
  Bold = SelectGraphicRendition.Bold.value
  Faint = SelectGraphicRendition.Faint.value
  Clear = SelectGraphicRendition.IntensityNormal.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class FontTypeOption(Enum):
  # DOCME
  Italic = SelectGraphicRendition.Italic.value
  Fraktur = SelectGraphicRendition.Fraktur.value
  Clear = SelectGraphicRendition.FontTypeNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class ConcealOption(Enum):
  # DOCME
  Set = SelectGraphicRendition.Conceal.value
  Clear = SelectGraphicRendition.ConcealNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class StrikeThroughOption(Enum):
  # DOCME
  Single = SelectGraphicRendition.Strikethrough.value
  Clear = SelectGraphicRendition.StrikethroughNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class BlinkOption(Enum):
  # DOCME
  Slow = SelectGraphicRendition.BlinkSlow.value
  Fast = SelectGraphicRendition.BlinkFast.value
  Clear = SelectGraphicRendition.BlinkingNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class UnderlineOption(Enum):
  # DOCME
  Single = SelectGraphicRendition.Underline.value
  Double = SelectGraphicRendition.UnderlineDouble.value
  Clear = SelectGraphicRendition.UnderlineNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class FrameOption(Enum):
  # DOCME
  Rectangle = SelectGraphicRendition.FrameRectangle.value
  Circle = SelectGraphicRendition.FrameCircle.value
  Clear = SelectGraphicRendition.FramedNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class OverlineOption(Enum):
  # DOCME
  Single = SelectGraphicRendition.Overlined.value
  Clear = SelectGraphicRendition.OverlinedNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class ScriptOption(Enum):
  # DOCME
  Super = SelectGraphicRendition.ScriptSuper.value
  Sub = SelectGraphicRendition.ScriptSub.value
  Clear = SelectGraphicRendition.ScriptNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class ProportionalSpacingOption(Enum):
  # DOCME
  Set = SelectGraphicRendition.ProportionalSpacing.value
  Clear = SelectGraphicRendition.ProportionalSpacingNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class ReverseVideoOption(Enum):
  # DOCME
  Set = SelectGraphicRendition.ReverseVideo.value
  Clear = SelectGraphicRendition.ReverseVideoNot.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class FontOption(Enum):
  # DOCME
  Font0 = SelectGraphicRendition.AlternateFont0.value
  Default = Font0
  Font1 = SelectGraphicRendition.AlternateFont1.value
  Font2 = SelectGraphicRendition.AlternateFont2.value
  Font3 = SelectGraphicRendition.AlternateFont3.value
  Font4 = SelectGraphicRendition.AlternateFont4.value
  Font5 = SelectGraphicRendition.AlternateFont5.value
  Font6 = SelectGraphicRendition.AlternateFont6.value
  Font7 = SelectGraphicRendition.AlternateFont7.value
  Font8 = SelectGraphicRendition.AlternateFont8.value
  Font9 = SelectGraphicRendition.AlternateFont9.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class ForegroundOption(Enum):
  # DOCME
  Black = SelectGraphicRendition.SetForegroundBlack.value
  BlackBright = SelectGraphicRendition.SetForegroundBlackBright.value
  Red = SelectGraphicRendition.SetForegroundRed.value
  RedBright = SelectGraphicRendition.SetForegroundRedBright.value
  Green = SelectGraphicRendition.SetForegroundGreen.value
  GreenBright = SelectGraphicRendition.SetForegroundGreenBright.value
  Yellow = SelectGraphicRendition.SetForegroundYellow.value
  YellowBright = SelectGraphicRendition.SetForegroundYellowBright.value
  Blue = SelectGraphicRendition.SetForegroundBlue.value
  BlueBright = SelectGraphicRendition.SetForegroundBlueBright.value
  Magenta = SelectGraphicRendition.SetForegroundMagenta.value
  MagentaBright = SelectGraphicRendition.SetForegroundMagentaBright.value
  Cyan = SelectGraphicRendition.SetForegroundCyan.value
  CyanBright = SelectGraphicRendition.SetForegroundCyanBright.value
  White = SelectGraphicRendition.SetForegroundWhite.value
  WhiteBright = SelectGraphicRendition.SetForegroundWhiteBright.value
  ##
  Custom = SelectGraphicRendition.SetForegroundCustom.value
  Default = SelectGraphicRendition.SetForegroundDefault.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


@total_ordering
class BackgroundOption(Enum):
  # DOCME
  Black = SelectGraphicRendition.SetBackgroundBlack.value
  BlackBright = SelectGraphicRendition.SetBackgroundBlackBright.value
  Red = SelectGraphicRendition.SetBackgroundRed.value
  RedBright = SelectGraphicRendition.SetBackgroundRedBright.value
  Green = SelectGraphicRendition.SetBackgroundGreen.value
  GreenBright = SelectGraphicRendition.SetBackgroundGreenBright.value
  Yellow = SelectGraphicRendition.SetBackgroundYellow.value
  YellowBright = SelectGraphicRendition.SetBackgroundYellowBright.value
  Blue = SelectGraphicRendition.SetBackgroundBlue.value
  BlueBright = SelectGraphicRendition.SetBackgroundBlueBright.value
  Magenta = SelectGraphicRendition.SetBackgroundMagenta.value
  MagentaBright = SelectGraphicRendition.SetBackgroundMagentaBright.value
  Cyan = SelectGraphicRendition.SetBackgroundCyan.value
  CyanBright = SelectGraphicRendition.SetBackgroundCyanBright.value
  White = SelectGraphicRendition.SetBackgroundWhite.value
  WhiteBright = SelectGraphicRendition.SetBackgroundWhiteBright.value
  ##
  Custom = SelectGraphicRendition.SetBackgroundCustom.value
  Default = SelectGraphicRendition.SetBackgroundDefault.value

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.value < other.value
    ##
    return NotImplemented
  ##
##


CLEAR_FORMAT = '\x1b[0m'


@dataclass(frozen=True)
class TerminalFormat:
  # DOCME
  CLEAR_FORMAT: ClassVar[str] = CLEAR_FORMAT

  intensity: Optional[Intensity] = None
  font_type: Optional[FontTypeOption] = None
  conceal: Optional[ConcealOption] = None
  blink: Optional[BlinkOption] = None
  underline: Optional[UnderlineOption] = None
  overline: Optional[OverlineOption] = None
  proportional: Optional[ProportionalSpacingOption] = None
  reverse: Optional[ReverseVideoOption] = None
  font: Optional[FontOption] = None
  foreground_color: Optional[ColorRGB] = None
  background_color: Optional[ColorRGB] = None
  foreground_code: Optional[Union[ForegroundOption, int]] = None  # if None and fg_color is set, then in post init to the closest visual corresponding color code
  background_code: Optional[Union[BackgroundOption, int]] = None  # if None and bf_color is set, then in post init to the closest visual corresponding color code

  def __post_init__(self) -> None:
    # DOCME
    if self.foreground_color is not None:
      object.__setattr__(self, 'foreground_code', determineClosestVisualColorCode(self.foreground_color))
    ##
    if self.background_color is not None:
      object.__setattr__(self, 'background_code', determineClosestVisualColorCode(self.background_color))
    ##
  ##

  @cached_property
  def modifier_string(self) -> str:
    return self.getModifierString()
  ##

  def getModifierString(self) -> str:
    # DOCME
    values: List[str] = []
    if self.intensity is not None:
      values.append(f'\x1b[{self.intensity.value}m')
    ##
    values.extend(f'\x1b[{opt.value}m' for opt in (self.font_type, self.conceal, self.blink, self.underline, self.overline, self.proportional, self.reverse, self.font,) if opt is not None)
    if isinstance(self.foreground_code, int):
      # 256 Code
      values.append(f'\x1b[{ForegroundOption.Custom.value};5;{self.foreground_code}m')
    elif isinstance(self.foreground_code, ForegroundOption):
      if self.foreground_code != ForegroundOption.Custom:
        values.append(f'\x1b[{self.foreground_code.value}m')
      ##
    ##
    if isinstance(self.background_code, int):
      # 256 Code
      values.append(f'\x1b[{BackgroundOption.Custom.value};5;{self.background_code}m')
    elif isinstance(self.background_code, BackgroundOption):
      if self.background_code != BackgroundOption.Custom:
        values.append(f'\x1b[{self.background_code.value}m')
      ##
    ##
    out = ''.join(values)
    return out
  ##

  def replace(self, *,
              intensity: Union[UnsetType, Intensity] = Unset,
              font_type: Union[UnsetType, FontTypeOption] = Unset,
              conceal: Union[UnsetType, ConcealOption] = Unset,
              blink: Union[UnsetType, BlinkOption] = Unset,
              underline: Union[UnsetType, UnderlineOption] = Unset,
              overline: Union[UnsetType, OverlineOption] = Unset,
              proportional: Union[UnsetType, ProportionalSpacingOption] = Unset,
              reverse: Union[UnsetType, ReverseVideoOption] = Unset,
              font: Union[UnsetType, FontOption] = Unset,
              foreground_color: Union[UnsetType, ColorRGB] = Unset,
              background_color: Union[UnsetType, ColorRGB] = Unset,
              foreground_code: Union[UnsetType, Optional[Union[ForegroundOption, int]]] = Unset,
              background_code: Union[UnsetType, Optional[Union[BackgroundOption, int]]] = Unset,
              ) -> TerminalFormat:
    out = TerminalFormat(
        intensity=self.intensity if isinstance(intensity, UnsetType) else intensity,
        font_type=self.font_type if isinstance(font_type, UnsetType) else font_type,
        conceal=self.conceal if isinstance(conceal, UnsetType) else conceal,
        blink=self.blink if isinstance(blink, UnsetType) else blink,
        underline=self.underline if isinstance(underline, UnsetType) else underline,
        overline=self.overline if isinstance(overline, UnsetType) else overline,
        proportional=self.proportional if isinstance(proportional, UnsetType) else proportional,
        reverse=self.reverse if isinstance(reverse, UnsetType) else reverse,
        font=self.font if isinstance(font, UnsetType) else font,
        foreground_color=self.foreground_color if isinstance(foreground_color, UnsetType) else foreground_color,
        background_color=self.background_color if isinstance(background_color, UnsetType) else background_color,
        foreground_code=self.foreground_code if isinstance(foreground_code, UnsetType) else foreground_code,
        background_code=self.background_code if isinstance(background_code, UnsetType) else background_code,
    )
    return out
  ##
##


def removeFormat(value: str) -> str:
  # DOCME
  out = []
  idx = 0
  for match in _format_rgx.finditer(value):
    out.append(value[idx:match.start()])
    idx = match.end()
  ##
  if idx < len(value):
    out.append(value[idx:])
  ##
  return ''.join(out)
##


def getLengthWithoutFormat(value: str) -> int:
  # DOCME
  total = len(value)
  for match in _format_rgx.finditer(value):
    total -= (match.end() - match.start())
  ##
  return total
##


# Commonly used formats as constants / functions
BOLD = TerminalFormat(intensity=Intensity.Bold).getModifierString()
FAINT = TerminalFormat(intensity=Intensity.Faint).getModifierString()
CLEAR_INTENSITY = TerminalFormat(intensity=Intensity.Clear).getModifierString()
BLINKING = TerminalFormat(blink=BlinkOption.Slow).getModifierString()
UNDERLINE = TerminalFormat(underline=UnderlineOption.Single).getModifierString()
CLEAR_UNDERLINE = TerminalFormat(underline=UnderlineOption.Clear).getModifierString()
###
FG_BLACK = TerminalFormat(foreground_code=ForegroundOption.Black).getModifierString()
FG_RED = TerminalFormat(foreground_code=ForegroundOption.Red).getModifierString()
FG_GREEN = TerminalFormat(foreground_code=ForegroundOption.Green).getModifierString()
FG_YELLOW = TerminalFormat(foreground_code=ForegroundOption.Yellow).getModifierString()
FG_BLUE = TerminalFormat(foreground_code=ForegroundOption.Blue).getModifierString()
FG_MAGENTA = TerminalFormat(foreground_code=ForegroundOption.Magenta).getModifierString()
FG_CYAN = TerminalFormat(foreground_code=ForegroundOption.Cyan).getModifierString()
FG_WHITE = TerminalFormat(foreground_code=ForegroundOption.White).getModifierString()
###
BG_BLACK = TerminalFormat(background_code=BackgroundOption.Black).getModifierString()
BG_RED = TerminalFormat(background_code=BackgroundOption.Red).getModifierString()
BG_GREEN = TerminalFormat(background_code=BackgroundOption.Green).getModifierString()
BG_YELLOW = TerminalFormat(background_code=BackgroundOption.Yellow).getModifierString()
BG_BLUE = TerminalFormat(background_code=BackgroundOption.Blue).getModifierString()
BG_MAGENTA = TerminalFormat(background_code=BackgroundOption.Magenta).getModifierString()
BG_CYAN = TerminalFormat(background_code=BackgroundOption.Cyan).getModifierString()
BG_WHITE = TerminalFormat(background_code=BackgroundOption.White).getModifierString()
###

ColorSpec = Union[str, Tuple[int, ...], Tuple[float, ...]]


def _convertColorSpecToRGB(color: ColorSpec) -> ColorRGB:
  # DOCME
  if isinstance(color, str):
    return ColorRGB.fromHexColorCode(color)
  else:
    return ColorRGB.fromStandardRgb(StandardRGB(r=color[0], g=color[1], b=color[2]))
  ##
##


def FG(color: ColorSpec) -> str:
  """ creates color code string from:
   - from hex color code ex. #xFFE0FE,
   - or a 0-255 rgb color code ex.(255,123,13,)
  """
  term_format = TerminalFormat(foreground_color=_convertColorSpecToRGB(color))
  return term_format.getModifierString()
##


def BG(color: ColorSpec) -> str:
  """ creates color code string from:
   - from hex color code ex. #xFFE0FE,
   - or a 0-255 rgb color code ex.(255,123,13,)
  """
  term_format = TerminalFormat(background_color=_convertColorSpecToRGB(color))
  return term_format.getModifierString()
##


def FGBG(foreground_color: ColorSpec, background_color: ColorSpec) -> str:
  """ creates color code string from:
   - from hex color code ex. #xFFE0FE,
   - r a 0-255 rgb color code ex.(255,123,13,)
  """
  term_format = TerminalFormat(
      foreground_color=_convertColorSpecToRGB(foreground_color),
      background_color=_convertColorSpecToRGB(background_color)
  )
  return term_format.getModifierString()
##
