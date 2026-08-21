# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from typing import Any, Mapping, Sequence, Union

from numpy import asarray, ndarray
from scipy.spatial.transform import Rotation

from exhaust_plume.log.extra_log_levels import NOTE, TRACE
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.orientation import OrientationOffset

__all__ = (
    'RotationLike',
    'convertRotationLikeToRotation',
    'robustOrientationFromConfig',
)
##################################
log = getCleanLogger(__name__)

RotationLike = Union[Sequence[float], Sequence[Sequence[float]], ndarray, Rotation]


def convertRotationLikeToRotation(rot: RotationLike) -> Rotation:
  if isinstance(rot, Rotation):
    return rot
  ##
  rot = asarray(rot)
  if rot.shape == (4,):
    return Rotation.from_quat(rot)
  elif rot.shape == (3, 3,):
    return Rotation.from_matrix(rot)
  ##
  raise ValueError(
      f'Unable to convert array to Rotation object. (4,) implies quaternion, and (3,3) implies matrix.'
      f' Array shape {rot.shape} is not either')
##


def robustOrientationFromConfig(config: Union[RotationLike, Mapping[str, Any]], debug_config_prefix: str = '') -> Rotation:
  """ Loads orientation from config.

  """
  if config is None:
    log.info(f'{debug_config_prefix}: Config is None. Orientation will be assumed as all zeros/identity.')
    return Rotation.identity()
  ##
  rotation = None
  if isinstance(config, Rotation):
    rotation = config
  ##
  if rotation is None:
    orientation_values = None
    try:
      orientation_values = asarray(config, dtype='float')
    except (TypeError, AttributeError,) as e:
      log.log(NOTE, f'{debug_config_prefix}: Caught exception:{e} while trying to convert config to an array. Config:{config}')
    ##
    if orientation_values is not None:
      try:
        rotation = convertRotationLikeToRotation(orientation_values)
      except ValueError as e:
        raise ValueError(f'{debug_config_prefix}: Caught exception {e} while trying to convert series of floats:{orientation_values}') from e
      ##
    ##
  ##
  if rotation is None:
    try:
      orientation_offset = OrientationOffset.fromConfig(config, debug_config_prefix=debug_config_prefix)
      if log.isEnabledFor(NOTE):
        log.log(NOTE, f'{debug_config_prefix}: Loaded orientation offset as:{orientation_offset}', extra={})
      ##
    except Exception as e:
      raise ValueError(f'{debug_config_prefix}: `orientation` must be specified as a x,y,z,W quaternion, or as {OrientationOffset.__name__} config. Got:{config}') from e
    ##
    rotation = orientation_offset.getBaseFromOffset()   # TODO address - this makes more sense as most rotations are world from body (body to world); old code may have depended on the inverse
  ##
  log.log(TRACE, f'{debug_config_prefix}: loaded {rotation} (as quat:{rotation.as_quat()}', extra={})
  return rotation
##
