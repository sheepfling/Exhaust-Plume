# -*- coding: utf-8 -*-
""" Path utilities. """
from __future__ import annotations

import os
from os.path import extsep, sep as folder_divider
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

from exhaust_plume.log.extra_log_levels import TRACE, VERBOSE
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.log.terminal_format import BOLD, CLEAR_INTENSITY
from exhaust_plume.util.type_hints import ExtensionsType, PathLike

__all__ = (
    'getExtensions',
    'relpath',
    'searchForFileOnPaths',
    'doesPathHaveTrailingExtensions',
    'getParentStemFromPath',
    'doesStringDenoteFolder',
    'getStemWithoutSuffix',
    'convertPathToString',
    'reprPathForLogging',
)
###################
log = getCleanLogger(__name__)


def reprPathForLogging(filepath: Optional[Union[str, Path]]) -> str:
  if filepath is None:
    return str(None)
  ##
  filepath = Path(filepath).expanduser().resolve().absolute()
  return repr(str(filepath))
##


def convertPathToString(path: PathLike) -> str:
  """ Appends trailing folder divider '/' if the path is a directory """
  if isinstance(path, str):
    return path
  ##
  out = str(path)
  if path.is_dir():
    out += folder_divider
  ##
  return out
##


def getStemWithoutSuffix(path: PathLike) -> str:
  # DOCME
  stem = Path(path).stem
  return stem.split(extsep)[0]
##


def doesStringDenoteFolder(path_str: str) -> bool:
  # Path objects strip trailing sep's, so it needs to be a string
  out = str(path_str).endswith(folder_divider)
  return out
##


def getParentStemFromPath(path: PathLike) -> Tuple[Path, str]:
  """ Returns tuple of
  - path to parent folder or path (if path is a folder)
  - empty string if path is folder or stem of file
  """
  is_dir = False
  if isinstance(path, str):
    is_dir = doesStringDenoteFolder(path_str=path)
  elif isinstance(path, Path):
    is_dir = path.is_dir()
  ##
  path = Path(path)
  folder_parent = path if is_dir else path.parent
  filename_prefix = '' if is_dir else path.stem
  out = (folder_parent, filename_prefix,)
  return out
##


def getExtensions(path: PathLike, case_insensitive: bool = True) -> ExtensionsType:
  """ Returns tuple of all extensions without the extsep prefix. """
  file_exts = tuple(sfx[len(extsep):] for sfx in Path(path).suffixes)
  if case_insensitive:
    file_exts = tuple(ext.lower() for ext in file_exts)
  ##
  return file_exts
##


def relpath(path: PathLike, start: PathLike) -> Path:
  # Wraps os.path.relpath with a Path object instead of a string
  return Path(os.path.relpath(path, start))
##


def doesPathHaveTrailingExtensions(path: PathLike, extensions: ExtensionsType, case_insensitive: bool = True) -> bool:
  # DOCME
  path = Path(path)
  if case_insensitive:
    extensions = tuple(x.lower() for x in extensions)
  ##
  file_exts = getExtensions(path, case_insensitive=case_insensitive)
  out = file_exts[-len(extensions):] == extensions
  return out
##


def searchForFileOnPaths(filepath: PathLike, paths_to_search: Sequence[Path] = tuple(), ) -> Path:
  # DOCME
  if filepath is None or not filepath:
    raise ValueError("filepath is empty or None")
  ##
  filepath = Path(filepath)
  if filepath.exists():
    return filepath
  ##
  if log.isEnabledFor(TRACE):
    log.log(TRACE, f"Filepath {reprPathForLogging(filepath)} was not found. Searching path:{paths_to_search}", extra={})
  ##
  filepath_suffix = filepath
  for pth in paths_to_search:
    test_filepath = pth / filepath_suffix
    if test_filepath.exists():
      if log.isEnabledFor(VERBOSE):
        log.log(VERBOSE, f" Successfully found file: {test_filepath}", extra={})
      ##
      return test_filepath
    ##
    if log.isEnabledFor(TRACE):
      log.log(TRACE, f"{reprPathForLogging(test_filepath)} did not exist. Continuing search.", extra={})
    ##
  ##
  msg = f"Could not find file:{BOLD}{filepath}{CLEAR_INTENSITY} on paths:{[reprPathForLogging(pth) for pth in paths_to_search]}. pwd={reprPathForLogging(Path('.'))}"
  if paths_to_search:
    msg += '\n'
  ##
  for path in paths_to_search:
    file = path / filepath
    file_rel = file
    file_abs = file.expanduser().resolve().absolute()
    msg += f'\tFile (rel):{file_rel} File (abs):{file_abs} Exists?:{file.exists()}\n'
  ##
  raise ValueError(msg)
##
