"""A persistent cache of environmental data, and of data derived from it.

Fetching environmental data from remote services (such as PVGIS and NEWA), and deriving data
from it (such as heating degree days and consumption profiles), is slow. The results are kept in
a `diskcache.Cache` at the `ENV_CACHE_PATH` setting (see `config/default_paths.py`), which
persists between runs and is shared between processes. The cache evicts the least recently used
entries beyond `ENV_CACHE_SIZE_LIMIT` bytes (default 1 GiB).

Entries are keyed by `environment_cache_key`, from the identity of the environment server that
served the data (its class name and version), so that a new version of a server does not use the
data of an old one. Locations are rounded to 3 dp of latitude and longitude (about 100 m) and
heights to the nearest metre, so that nearby requests share an entry; a server should fetch its
data at the rounded location, so that the data does not depend on which request was made first.
"""
from functools import lru_cache
from typing import Any, Callable, Hashable, TypeVar

import diskcache
import pandas as pd

from config import settings
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.core.timespan.timespan import TimeSpan

DEFAULT_SIZE_LIMIT = 2**30

T = TypeVar('T')

CacheIdentity = tuple[str, str]
"""The class name and version of an environment server, identifying its data in cache keys."""


@lru_cache
def get_environment_cache() -> diskcache.Cache:
    """The persistent cache shared by environment servers and the modules using their data.

    Returns:
        The cache, opened at the `ENV_CACHE_PATH` setting.
    """
    return diskcache.Cache(
        str(settings.get('ENV_CACHE_PATH')),
        size_limit = int(settings.get('ENV_CACHE_SIZE_LIMIT', DEFAULT_SIZE_LIMIT)),
    )


def round_location(location: Location) -> tuple[float, float]:
    """The latitude and longitude of a location, rounded to 3 dp.

    Args:
        location: The location.

    Returns:
        The rounded latitude and longitude.
    """
    # Adding 0. turns -0. into 0., so that both give the same key
    return round(location.lat, 3) + 0., round(location.lon, 3) + 0.


def round_height(height: float) -> int:
    """A height rounded to the nearest metre.

    Args:
        height: The height (m).

    Returns:
        The rounded height.
    """
    return int(round(height))


def _time_key(time: Any) -> str:
    stamp = pd.Timestamp(time)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert('UTC')
    return stamp.isoformat()


def environment_cache_key(
    identity: CacheIdentity,
    measure: str,
    location: Location,
    timespan: TimeSpan,
    height: float | None = None,
    **params: Hashable,
) -> tuple[Hashable, ...]:
    """The key of an entry in the environment cache.

    Args:
        identity: Class name and version of the environment server serving the data.
        measure: Name of the data held, e.g. `'wind_speeds'` or `'heating_degree_days'`.
        location: Location of the data; rounded to 3 dp of latitude and longitude.
        timespan: Time span of the data; its start and end form part of the key.
        height: Height of the data above ground level, where appropriate; rounded to the nearest metre.
        **params: Any other parameters that the data depends on, such as a timestep or a plane
            orientation. Values should be simple types (`str`, `int`, `float`, `bool` or `None`).

    Returns:
        The key.
    """
    return (
        *identity,
        measure,
        *round_location(location),
        _time_key(timespan.start),
        _time_key(timespan.end),
        None if height is None else round_height(height),
        tuple(sorted(params.items())),
    )


_MISSING = object()

def get_or_set(
    key: Hashable,
    compute: Callable[[], T],
    cache: diskcache.Cache | None = None,
) -> T:
    """The cached value of a key, computing and caching it if absent.

    Args:
        key: Key of the entry, from `environment_cache_key`.
        compute: Function computing the value when it is not cached.
        cache: The cache; defaults to `get_environment_cache()`.

    Returns:
        The value.
    """
    if cache is None:
        cache = get_environment_cache()
    value = cache.get(key, default = _MISSING)
    if value is _MISSING:
        value = compute()
        cache.set(key, value)
    return value
