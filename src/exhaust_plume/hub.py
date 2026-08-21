# -*- coding: utf-8 -*-
""" This module contains the Hub class which is used for publishing and
subscribing to and from channels within a python application.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field as Field
from itertools import product
from typing import AbstractSet, Any, DefaultDict, Deque, Dict, Hashable, Mapping, Optional, Set

from exhaust_plume.log.extra_log_levels import DEBUG, NOTE, TRACE, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'Hub',
    'ChannelType',
    'NameType',
    'ChannelNameKey',
)
######################################
log = getCleanLogger(__name__)

ChannelType = Hashable
NameType = Hashable


@dataclass
class _Subscription:
  # DOCME
  inbox: Deque[Any]
  count: int = 0
  whitelist: Optional[Set[NameType]] = None
  blacklist: Optional[Set[NameType]] = None
##


@dataclass
class PubSubInfo:
  # DOCME
  name: Optional[Hashable]
  publish_counts: DefaultDict[ChannelType, int] = Field(default_factory=lambda: defaultdict(int))
  subscriptions: Dict[ChannelType, _Subscription] = Field(default_factory=dict)
##


@dataclass(frozen=True)
class ChannelNameKey:
  __slots__ = ('channel', 'name',)
  channel: ChannelType
  name: NameType

  def __getstate__(self) -> Dict[str, Any]:
    return dict((slot, getattr(self, slot)) for slot in self.__slots__ if hasattr(self, slot))
  ##

  def __setstate__(self, state: Mapping[str, Any]) -> None:
    for slot, value in state.items():
      object.__setattr__(self, slot, value)  # <- use object.__setattr__
    ##
  ##
##


class Hub:
  """ Functions a hub for publishers and subscribers. """

  def __init__(self, hub: Optional[Hub] = None):
    """ Default and copy constructor for a Hub object

    Parameters
    ----------
    hub : Optional hub to copy channel subscriptions from.

    """
    self.__pubsub_infos: Dict[Optional[NameType], PubSubInfo] = {None: PubSubInfo(name=None)}
    self.__channel2sub_names: DefaultDict[ChannelType, Set[NameType]] = defaultdict(set)
    if hub is not None:
      self.__pubsub_infos = deepcopy(hub.__pubsub_infos)
      self.__channel2sub_names = deepcopy(hub.__channel2sub_names)
    ##
  ##

  ##########
  # Properties
  @property
  def num_channels(self) -> int:
    """ Returns the number of the total number of channels

    Returns
    -------
    int : number of total channels published or subscribe to

    """
    return len(self.subscribers)
  ##

  @property
  def channels(self) -> Set[ChannelType]:
    """ Returns view of all the channels that have been published to or subscribed from

    Returns
    -------
    all the channels that have been published to or subscribed from
    """
    channels = set(self.__channel2sub_names)
    return channels
  ##

  @property
  def subscribed_channels(self) -> Set[ChannelType]:
    """ Returns list of all channels that have subscribers.
    Channels that have been published to or announced, but not subscribed to are not included.

    Returns
    -------
    List[ChannelType] : list of subscribed channels
    """
    out = {sub_channel for info in self.__pubsub_infos.values() for sub_channel in info.subscriptions}
    return out
  ##

  @property
  def publishers(self) -> Dict[ChannelType, Set[NameType]]:
    # DOCME
    publishers: DefaultDict[ChannelType, Set[NameType]] = defaultdict(set)
    for name, info in self.__pubsub_infos.items():
      for pub_channel in info.publish_counts:
        publishers[pub_channel].add(name)
      ##
    ##
    out = {**publishers}
    return out
  ##

  @property
  def subscribers(self) -> Dict[ChannelType, Set[NameType]]:
    # DOCME
    subscribers: DefaultDict[ChannelType, Set[NameType]] = defaultdict(set)
    for name, info in self.__pubsub_infos.items():
      for sub_channel in info.subscriptions.keys():
        subscribers[sub_channel].add(name)
      ##
    ##
    out = {**subscribers}
    return out
  ##
  # /Properties
  ##########

  ##########
  # Public
  def getAllPublisherAndSubscriberNames(self) -> Set[NameType]:
    # DOCME
    out = {name for name in self.__pubsub_infos if name is not None}
    return out
  ##

  def hasSubscribers(self, channel: ChannelType) -> bool:
    """ Returns true if the hub has any subscribers on the specified channel

    Parameters
    ----------
    channel : the channel to check if there are any subscribers on

    Returns
    -------
    bool : True if the specified channel has any subscribers, False otherwise
    """
    return (channel in self.__channel2sub_names) and len(self.__channel2sub_names[channel]) > 0
  ##

  def getNumSubscribers(self, channel: ChannelType) -> int:
    """ Returns how many subscribers a particular channel has

    Parameters
    ----------
    channel : the channel to see how many subscribers are present

    Returns
    -------
    int : the number of subscribers for the specified channel
    """
    return len(self.__channel2sub_names[channel]) if (channel in self.__channel2sub_names) else 0
  ##

  def isSubscribed(self, channel: ChannelType, name: NameType) -> bool:
    # DOCME
    # Returns true/false if the channel,name has been subscribed to already
    try:
      channel_subscribers = self.__channel2sub_names[channel]
      return name in channel_subscribers
    except KeyError:
      return False
    ##
  ##

  def getQueue(self, channel: ChannelType, name: NameType) -> Optional[deque]:
    """ Returns the subscription message queue that was supplied on subscription for a particular channel and name. If not subscribed then returns None

    Parameters
    ----------
    channel : channel to look for
    name : subscriber name to look for

    Returns
    -------
    Optional[deque] : the subscriber's message queue if subscribed, otherwise None
    """
    try:
      info = self.__pubsub_infos[name]
      return info.subscriptions[channel].inbox
    except KeyError:
      if log.isEnabledFor(NOTE):
        log.log(NOTE, f'Hub:{id(self)} Channel:{channel} does not have queue for name:{name}. Returning None.', extra={'object': self, })
      ##
      return None
    ##
  ##

  def subscribe(self, channel: ChannelType, name: NameType, queue: deque, whitelist: Optional[AbstractSet[NameType]] = None, blacklist: Optional[AbstractSet[NameType]] = None) -> None:
    """ Subscribes a name to a particular channel with a callback

    Parameters
    ----------
    channel : channel to be subscribed to
    name : name of subscriber
    queue : reference to the queue that the subscriber owns and will inspect if there are any new messages
    whitelist: Filter on the subscriber side. Checks if the incoming name is in the set of names before appending a copy to the inbox
    blacklist: Filter on the subscriber side. Checks if the incoming name is NOT in the set of names before appending a copy to the inbox

    Notes
    -----
    It is possible to subscribe twice however the second subscription just overrides the first's message queue with another.

    Returns
    -------
    None
    """
    if name not in self.__pubsub_infos:
      self.__pubsub_infos[name] = PubSubInfo(name=name)
    ##
    self.__channel2sub_names[channel].add(name)
    channel2subscription = self.__pubsub_infos[name].subscriptions
    if name in channel2subscription:
      if log.isEnabledFor(DEBUG):
        log.debug(f'Hub:{id(self)} Name:{name} already subscribed to Channel:{channel}. Overriding existing queue.', extra={'object': self, })
      ##
      return
    ##
    channel2subscription[channel] = _Subscription(
        inbox=queue,
        whitelist=set(whitelist) if whitelist is not None else None,
        blacklist=set(blacklist) if blacklist is not None else None,
    )
    if log.isEnabledFor(TRACE):
      log.log(TRACE, f'Hub:{id(self)} New subscriber:{name} on Channel:{channel}. '
                     f'Channel now has {len(channel2subscription)} subscribers. {list(channel2subscription)}',
              extra={'object': self, })
    ##
  ##

  def announceChannel(self, channel: ChannelType, *, name: Optional[NameType] = None) -> None:
    """ Simply announces that messages will be published on this channel.

    Parameters
    ----------
    channel : channel to be published message on
    name : optional parameter to tell the hub who is publishing

    Returns
    -------
    None
    """
    self.__updatePublishers(channel, name)
    if channel not in self.__channel2sub_names:
      self.__channel2sub_names[channel] = set()
    ##
  ##

  def publish(self, channel: ChannelType, msg: object, *, name: Optional[NameType] = None) -> None:
    """ Publishes on a certain channel.

    Parameters
    ----------
    channel : channel to be published message on
    msg : message to be sent to all the subscribers.
    name : optional parameter to tell the hub who is publishing

    Notes
    -----
    It should be noted that the hub does not copy the message to be published so the publisher should send a copy of the data
    so that doesn't modify the data after publishing it.

    Returns
    -------
    None
    """
    publisher_name = name
    self.__updatePublishers(channel=channel, name=publisher_name)
    pub_info = self.__pubsub_infos[publisher_name]
    pub_info.publish_counts[channel] += 1
    if channel not in self.__channel2sub_names:
      self.__channel2sub_names[channel] = set()
      return
    ##
    num_sent = 0
    num_total = 0
    for subscriber_name in self.__channel2sub_names[channel]:
      num_total += 1
      sub_info = self.__pubsub_infos[subscriber_name].subscriptions[channel]
      if (sub_info.whitelist is not None) and (publisher_name not in sub_info.whitelist):
        # if name is not in whitelist then subscriber has prefiltered / ignored this message
        continue
      elif (sub_info.blacklist is not None) and (publisher_name in sub_info.blacklist):
        # if name is in blacklist then subscriber has prefiltered / ignored this message
        continue
      ##
      sub_info.inbox.append(msg)
      sub_info.count += 1
    ##
    if num_sent != num_total and log.isEnabledFor(TRACE):
      num_excluded = num_total - num_sent
      log.log(TRACE, f"Channel:{channel} Publish by:{publisher_name} could have sent {num_total}, but only {num_sent} were sent because of subscriber "
              f"pre-filtering. (num excluded={num_excluded})", extra={'object': self, })
    ##
  ##

  def unsubscribe(self, channel: ChannelType, name: NameType) -> bool:
    """ Removes the name's callback from the channel

    Parameters
    ----------
    channel : Channel to remove name from
    name : name to be unsubscribed from channel

    Returns
    -------
    bool : True if removed, False if did not remove or did not exist
    """
    out = True
    try:
      del self.__pubsub_infos[name].subscriptions[channel]
      self.__channel2sub_names[channel].discard(name)
    except KeyError:
      out = False
    ##
    if log.isEnabledFor(NOTE):
      msg = 'Deleted channel successfully' if out else 'Channel was not subscribed, so unsubscribe did nothing.'
      log.log(NOTE, f'Hub:{id(self)} Unsubscribing name:{name} from Channel:{channel}. {msg}', extra={'object': self, })
    ##
    return out
  ##

  def clear(self) -> None:
    """ Clears the entirety of the callbacks dictionary

    Returns
    -------
    None
    """
    self.__pubsub_infos.clear()
    self.__channel2sub_names.clear()
    self.__pubsub_infos[None] = PubSubInfo(name=None)
    if log.isEnabledFor(TRACE):
      log.log(TRACE, f'Hub:{id(self)} Clearing hub of all data', extra={'object': self, })
    ##
  ##

  def getPublishCounts(self) -> Dict[ChannelNameKey, int]:
    # DOCME
    out: Dict[ChannelNameKey, int] = {ChannelNameKey(chn, name): 0 for chn, name in product(self.channels, self.__pubsub_infos)}
    for name, info in self.__pubsub_infos.items():
      for channel, count in info.publish_counts.items():
        key = ChannelNameKey(channel=channel, name=name)
        out[key] = count
      ##
    ##
    return out
  ##

  def getSubscriptionCounts(self) -> Dict[ChannelNameKey, int]:
    # DOCME
    out: Dict[ChannelNameKey, int] = {ChannelNameKey(chn, name): 0 for chn, name in product(self.channels, self.__pubsub_infos)}
    for name, info in self.__pubsub_infos.items():
      for channel, sub_info in info.subscriptions.items():
        key = ChannelNameKey(channel=channel, name=name)
        out[key] = sub_info.count
      ##
    ##
    return out
  ##
  # / Public
  ##########

  ##########
  # Private
  def __updatePublishers(self, channel: ChannelType, name: Optional[NameType]) -> None:
    # DOCME
    if name is None:
      log.info(f'Hub:{id(self)} Announced publisher:{name} on Channel:{channel}. but name is None, so doing nothing', extra={'object': self, })
      return
    ##
    if name not in self.__pubsub_infos:
      self.__pubsub_infos[name] = PubSubInfo(name=name)
    ##
    info = self.__pubsub_infos[name]
    if channel not in info.publish_counts:
      info.publish_counts[channel] = 0
    ##
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'Hub:{id(self)} Announced publisher:{name} on Channel:{channel}.', extra={'object': self, })
    ##
  ##
  # /Private
  ##########
##
