"""Reporting waits for environmental data to whoever is running a model.

Fetching environmental data from remote services (such as NEWA) can take minutes, deep within a
model run: the model runs its modules, which run their generators, which ask the environment
server for data. Rather than pass a progress callback through every layer, the code running the
model sets a reporter for the current context with `reporting_waits`, and the environment servers
and cache mark each wait with `awaiting`. The reporter is told when a wait starts, with a message
saying what is awaited, and when it ends.

The reporter is held in a `ContextVar`, so runs in different threads (or tasks) report only their
own waits, and code that sets no reporter is unaffected.
"""
import logging
logger = logging.getLogger(__name__)

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

WaitReporter = Callable[[str | None], None]
"""Told the message of a wait when it starts, and None when there is no longer a wait (or the
message of the wait it was within, if it was nested)."""

_reporter: ContextVar[WaitReporter | None] = ContextVar('environment_wait_reporter', default = None)
_current: ContextVar[str | None] = ContextVar('environment_wait_message', default = None)

AWAITING = 'Awaiting environmental data'
"""Start of the message of every wait."""

@contextmanager
def reporting_waits(reporter: WaitReporter) -> Iterator[None]:
    """Report the waits for environmental data within the block to a reporter.

    Args:
        reporter: Told the message of each wait as it starts, and None as it ends.
    """
    reporter_token = _reporter.set(reporter)
    current_token = _current.set(None)
    try:
        yield
    finally:
        _current.reset(current_token)
        _reporter.reset(reporter_token)

def _report(reporter: WaitReporter, message: str | None) -> None:
    # Reporting is feedback only, so must not stop the data being fetched
    try:
        reporter(message)
    except Exception: # pylint: disable=broad-except
        logger.exception('Failed to report a wait for environmental data')

@contextmanager
def awaiting(description: str, typical_duration: str | None = None) -> Iterator[None]:
    """Mark a wait for environmental data, reporting it if a reporter is set.

    Args:
        description: What is awaited, e.g. 'wind speeds for (53.255, -3.477) at 10 m from NEWA'.
        typical_duration: How long the wait usually takes, e.g. 'usually 1 to 8 minutes'.
    """
    reporter = _reporter.get()
    if reporter is None:
        yield
        return
    message = f'{AWAITING}: {description}'
    if typical_duration:
        message += f' ({typical_duration})'
    previous = _current.get()
    token = _current.set(message)
    _report(reporter, message)
    try:
        yield
    finally:
        _current.reset(token)
        _report(reporter, previous)
