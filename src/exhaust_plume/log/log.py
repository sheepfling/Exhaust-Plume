# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.resources
import io
import os
import sys
from logging import Logger as py_Logger, NullHandler as py_NullHandler, getLogger as py_getLogger
from logging.config import dictConfig as py_dictConfig
from pathlib import Path
from typing import Optional, Union

import yaml

import exhaust_plume.log.extra_log_levels  # NOQA # ensures that extra log names are created at this point.
from exhaust_plume.constants import MODULE_NAME
from exhaust_plume.log.colored_formatter import loadColoredConfig
from exhaust_plume.log.make_folder_handler import MakeFolderHandler

__all__ = (
    'getCleanLogger',
    'configureLogging',
    'getRootLogger',
    'getLogger',
    'MakeFolderHandler',
    'loadColoredConfig',
)
#############################
_DEFAULT_CONFIG_PKG = f'{MODULE_NAME}.etc'
_DEFAULT_CONFIG_NAME = 'logging_config.yaml'


def getCleanLogger(module_name: str) -> py_Logger:
  """ Gets a module logger object and removes any existing handlers """
  out = py_getLogger(module_name)
  for handler in out.handlers:
    out.removeHandler(handler)
  ##
  out.addHandler(py_NullHandler())
  return out
##


log = getCleanLogger(__name__)


def getRootLogger(logger: py_Logger) -> py_Logger:
  """  Ascends parental hierarchy till there is a parent that is equal to itself (the root)
  """
  out = logger
  while out.parent is not None:
    parent = out.parent
    if parent is None:
      return out
    ##
    grandparent = parent.parent
    out = parent
    if parent == grandparent or grandparent is None:
      break
    ##
  ##
  return out
##


def configureLogging(config_file: Optional[Union[str, Path]] = None,
                     incremental: Optional[bool] = None,
                     ) -> bool:
  """
  Setup log configuration from YML file or using defaults.

  If `config_file` is None, the function will attempt to load the file described by
  the EXHAUST_PLUME_LOG_CONFIG environment variable. If this variable is empty, the packaged
  default log configuration will be used.

  Parameters
  ----------
  config_file : Optional[Union[str, Path]], optional
    Location of YML file describing log configuration.
    The default is None.
  incremental : Optional[bool]
    if specificied as True, then the logger config is added onto existing configuration
    typically useful if a library's logging is configured and then lastly this
    logging is configured.

  Returns
  -------
  bool
    True if the log configuration was successfully loaded.

  """
  if config_file is None:
    # check for environment variable configuration
    config_file = os.getenv(f'{MODULE_NAME}_LOG_CONFIG'.upper())
  ##
  if not config_file:
    # no env var or input arg - use the default embedded config
    with importlib.resources.open_text(_DEFAULT_CONFIG_PKG, _DEFAULT_CONFIG_NAME) as fin:
      file_text = fin.read()
    ##
  else:
    if not isinstance(config_file, Path):
      config_file = Path(config_file)
    ##
    if not config_file.exists():
      log.warning(f'Could not configure logging with file:{config_file.expanduser().resolve().absolute()} because it does not exist.')
      return False
    ##
    with open(config_file, 'rt', newline='', encoding='utf-8') as fin:
      file_text = fin.read()
    ##
  ##
  config_data = yaml.safe_load(file_text)
  incremental_set = False
  if incremental is not None:
    config_data['incremental'] = bool(incremental)
    incremental_set = True
  ##
  try:
    py_dictConfig(config_data)
  except ValueError as e:
    if not incremental_set:
      raise
    ##
    # Try once again without incremental set
    log.warning(f"Could not configure incremental logging config. Trying again without incremental set. Error:{e}")
    del config_data['incremental']
    py_dictConfig(config_data)
  ##

  loadColoredConfig(config_data)

  if sys.platform == 'win32':
    # apply Windows-specific fixes to support the UTF-8 icons and colored output

    # make sure stdout is in UTF-8 mode
    # Sometimes has issues on Windows
    if isinstance(sys.stdout, io.TextIOWrapper) and sys.version_info >= (3, 7):
      sys.stdout.reconfigure(encoding='utf-8')
    ##

    # activate ANSI colors for terminal
    # see https://stackoverflow.com/a/293633/18487576
    os.system('color')
  ##

  return True
##


def getLogger(module_name: str) -> py_Logger:
  """ Gets a module logger object as is without removing any handlers. """
  out = py_getLogger(module_name)
  return out
##
