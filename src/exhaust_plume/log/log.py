"""Small logging facade used by the study model and command-line runner."""

from __future__ import annotations

import importlib.resources
import logging
import os
from logging.config import dictConfig
from pathlib import Path
from typing import Optional, Union

import yaml

from exhaust_plume.constants import MODULE_NAME

__all__ = ('getCleanLogger', 'configureLogging', 'getRootLogger', 'getLogger')

_DEFAULT_CONFIG_PKG = f'{MODULE_NAME}.etc'
_DEFAULT_CONFIG_NAME = 'logging_config.yaml'


def getCleanLogger(module_name: str) -> logging.Logger:
  """Return a module logger with a no-op handler until configured by the caller."""
  logger = logging.getLogger(module_name)
  for handler in logger.handlers[:]:
    logger.removeHandler(handler)
  logger.addHandler(logging.NullHandler())
  return logger


def getRootLogger(logger: logging.Logger) -> logging.Logger:
  """Return the root logger for a logger hierarchy."""
  root = logger
  while root.parent is not None and root.parent is not root:
    root = root.parent
  return root


def configureLogging(config_file: Optional[Union[str, Path]] = None, incremental: Optional[bool] = None) -> bool:
  """Load the packaged or user-supplied standard-library logging configuration."""
  if config_file is None:
    config_file = os.getenv(f'{MODULE_NAME}_LOG_CONFIG'.upper())

  if config_file:
    path = Path(config_file)
    if not path.exists():
      logging.getLogger(__name__).warning('Logging configuration does not exist: %s', path.expanduser().resolve())
      return False
    file_text = path.read_text(encoding='utf-8')
  else:
    resource = importlib.resources.files(_DEFAULT_CONFIG_PKG).joinpath(_DEFAULT_CONFIG_NAME)
    file_text = resource.read_text(encoding='utf-8')

  config_data = yaml.safe_load(file_text)
  if incremental is not None:
    config_data['incremental'] = bool(incremental)
  dictConfig(config_data)
  return True


def getLogger(module_name: str) -> logging.Logger:
  """Return a logger without changing its handlers."""
  return logging.getLogger(module_name)
