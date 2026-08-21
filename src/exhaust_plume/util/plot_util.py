# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import inspect
import pickle
import warnings
from functools import wraps
from io import BytesIO
from os.path import extsep
from pathlib import Path
from pickle import PicklingError
from typing import Callable, Optional, TypeVar

from matplotlib import pyplot as plt
from matplotlib.text import Text
from numpy import array, newaxis, vstack

from exhaust_plume.log.extra_log_levels import NOTE
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.decorator_util import doublewrap
from exhaust_plume.util.filename_util import slugify
from exhaust_plume.util.path_util import reprPathForLogging
from exhaust_plume.util.plot_types import AxesSubplotType, FigureType
from exhaust_plume.util.type_hints import ParamSpec

__all__ = (
    'getFigureTitle',
    'saveFigure',
    'getFigureData',
    'equalizeAxes3D',
    'getDebuggingCallerTitle',
    'close_figs',
)
##########################
log = getCleanLogger(__name__)


def getDebuggingCallerTitle() -> str:
  callstack = inspect.stack()
  if len(callstack) < 1:
    return 'base frame'
  ##
  caller_frame = callstack[1]
  out = f'{caller_frame.filename}: {caller_frame.function} line {caller_frame.lineno}'
  return out
##


def getFigureTitle(fig: FigureType) -> Optional[str]:
  # DOCME
  if fig is None:
    return None
  ##
  out = None
  if hasattr(fig, '_suptitle'):
    try:
      # noinspection PyProtectedMember
      out = fig._suptitle.get_text()
    except AttributeError:
      pass
    ##
  ##
  if out is None and hasattr(fig, 'axes'):
    # no sup title so get it from axes
    axes = fig.axes
    if not axes or not hasattr(axes, '__len__') or len(axes) <= 0:
      log.info(f'Figure:{fig} had no axes and no _suptitle, so a title was unable to be determined')
      return None
    ##
    ax = axes[0]
    out = ax.get_title()
  ##
  if out is None:
    return None
  elif isinstance(out, str):
    return out
  elif isinstance(out, Text):
    return str(out.get_text())
  else:
    log.warning(f'Unknown return type from get_title:{type(out).__name__}. Returning None. Value:{out}')
    return None
  ##
##


DEFAULT_FIGURE_FORMAT = 'png'


def saveFigure(fig: FigureType, save_pickle: bool, output_folder: Path = Path('.'),
               output_format: Optional[str] = DEFAULT_FIGURE_FORMAT, filename_prefix: Optional[str] = None) -> Optional[Path]:
  """ Saves a figure as an image (or also a pickle) using the title to output_path_prefix

  @param fig: Pyplot figure
  @param output_folder: Creates folder if necessary
  @param save_pickle: save binary representation of the figure using pickle
  @param output_format: image format default 'png'
  @param filename_prefix: Optional prefix for the filename that is prepended before the slugified title
  @return: None
  """
  if output_format is None:
    output_format = DEFAULT_FIGURE_FORMAT
  ##
  fig_title = getFigureTitle(fig)
  if not fig_title or fig_title is None:
    slug_fig_title = ''
  else:
    slug_fig_title = slugify(fig_title)
  ##
  filename = ('' if filename_prefix is None else filename_prefix) + slug_fig_title
  if not filename:
    log.warning(f'Figure {fig} has no title/filename. Unable to save!.')
    return None
  ##
  output_folder.mkdir(exist_ok=True, parents=True)
  filepath = (output_folder / filename).with_suffix(extsep + output_format)
  # TODO[plotting,improvement] add bbox_inches='tight' to stop legend cutoff
  # https://stackoverflow.com/a/42303455/18487576
  if filepath.exists():
    log.info(f'Overwriting file that already exists:{reprPathForLogging(filepath)}')
  ##
  filepath.parent.mkdir(parents=True, exist_ok=True)
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=UserWarning)
    fig.savefig(str(filepath), format=output_format, bbox_inches='tight')
    log.log(NOTE, f'Saved figure {reprPathForLogging(filepath)} with format {output_format!r}')
  ##
  if save_pickle:
    pickle_filename = filepath.with_suffix(f'{extsep}fig{extsep}pkl')
    try:
      with open(str(pickle_filename), 'wb') as fout:
        fig_data = pickle.dumps(fig)
        fout.write(fig_data)
        log.log(NOTE, f'Saved {len(fig_data)} bytes to pickled fig file {reprPathForLogging(pickle_filename)}')
      ##
    except (AttributeError, PicklingError) as e:
      log.warning(f'Figure {fig_title} was unable to be pickled with exception: {e}', exc_info=True)
    ##
  ##
  return filepath
##


def getFigureData(fig: FigureType, width_in: Optional[float] = None, height_in: Optional[float] = None,
                  dpi: Optional[int] = None, fmt: Optional[str] = None) -> bytes:
  """ Saves figure to byte buffer and returns those bytes.  """
  buf = BytesIO()
  if (width_in is not None) and (height_in is not None):
    fig.set_size_inches(float(width_in), float(height_in))
  ##
  fig.savefig(buf, format=fmt if fmt is not None else 'png', dpi=dpi)
  buf.seek(0)
  data = buf.read()
  return data
##


def equalizeAxes3D(ax: Optional[AxesSubplotType] = None) -> None:
  if ax is None:
    ax = plt.gca()
  ##
  lims = vstack([
      ax.get_xlim(),
      ax.get_ylim(),
      ax.get_zlim(),
  ])
  max_diff = max(abs(lims[..., 1] - lims[..., 0]).ravel())
  centers = lims.mean(axis=-1)
  new_lims = centers[..., newaxis] + array([-.5, .5])[newaxis, ...] * max_diff
  ax.set_xlim(new_lims[0, ...])
  ax.set_ylim(new_lims[1, ...])
  ax.set_zlim(new_lims[2, ...])
##


P = ParamSpec('P')
T = TypeVar('T')

# NOTE - it seems that in pycharm doesn't handle type annotations very well with decorated functions, therefore
# when using @close_figs the args should always be double-checked because the linter may not catch it.


@doublewrap
def close_figs(func: Callable[P, T], *, on_exception: bool = True, **decorator_kwargs: object) -> Callable[P, T]:  # type: ignore[misc,valid-type] # as of mypy 0.991 ParamSpec is not supported in Callable
  """ Closes allocated figs by function under certain conditions.
  on_exception: only closes figs on receiving an exception
  """
  @wraps(func)
  def wrapped(*a: P.args, **kw: P.kwargs) -> T:  # type: ignore[name-defined] # ParamSpec doesn't work well with mypy
    initial_fignums = plt.get_fignums()
    try:
      out = func(*a, **kw)
    except Exception as e:
      final_fignums = plt.get_fignums()
      if on_exception:
        new_fignums = set(final_fignums) - set(initial_fignums)
        log.debug(f'Close figs wrapper caught exception and is closing figs:{new_fignums}. Exception:{e}')
        for fignum in new_fignums:
          plt.close(fignum)
        ##
      else:
        log.debug(f'Close figs wrapper caught exception but is not closing new figs. Exception:{e}')
      ##
      raise
    ##
    return out
  ##
  return wrapped
##
