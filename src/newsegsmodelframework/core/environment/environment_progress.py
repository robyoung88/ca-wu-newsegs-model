"""Reporting waits for environmental data to whoever is running a model.

Fetching environmental data from remote services (such as NEWA) can take minutes, deep within a
model run: the model runs its modules, which run their generators, which ask the environment
server for data. Rather than pass a progress callback through every layer, the code running the
model sets a reporter for the current context with `reporting_waits`, and the environment servers
and cache mark each wait with `awaiting`. The reporter is told when a wait starts, with a message
saying what is awaited, and when it ends.

The reporter is held in a `ContextVar`, so runs in different threads (or tasks) report only their
own waits, and code that sets no reporter is unaffected.

While a wait lasts, it is reported again every `WAIT_REPORT_INTERVAL_S` seconds, from a thread, so
that a run waiting minutes for data is seen to be alive: the dispatcher fails runs whose progress
has not been updated for 5 minutes.
"""
import logging
logger = logging.getLogger(__name__)

from contextlib import contextmanager
from contextvars import ContextVar
import threading
from typing import Callable, Iterator

WaitReporter = Callable[[str | None], None]
"""Told the message of a wait when it starts, and None when there is no longer a wait (or the
message of the wait it was within, if it was nested)."""

WAIT_REPORT_INTERVAL_S = 60.
"""How often (s) a wait is reported again while it lasts."""

class _Waits:
    """The reporter of a `reporting_waits` block, and the wait under way, which a thread reports again while it
    lasts."""

    def __init__(self, reporter: WaitReporter):
        self.reporter = reporter
        self._message: str | None = None
        # Held while reporting, so that the thread never reports a wait after it has ended
        self._lock = threading.Lock()
        self._ended = threading.Event()
        self._thread: threading.Thread | None = None

    def report(self, message: str | None) -> None:
        """Report the wait under way, or None if there is none."""
        with self._lock:
            self._message = message
            _report(self.reporter, message)
        if message is not None and self._thread is None:
            self._thread = threading.Thread(target = self._report_again, daemon = True, name = 'environment-wait-reporter')
            self._thread.start()

    def _report_again(self) -> None:
        while not self._ended.wait(WAIT_REPORT_INTERVAL_S):
            with self._lock:
                if self._message is not None and not self._ended.is_set():
                    _report(self.reporter, self._message)

    def end(self) -> None:
        """Stop reporting."""
        with self._lock:
            self._ended.set()

_reporter: ContextVar[_Waits | None] = ContextVar('environment_wait_reporter', default = None)
_current: ContextVar[str | None] = ContextVar('environment_wait_message', default = None)

AWAITING = 'Awaiting environmental data'
"""Start of the message of every wait."""

@contextmanager
def reporting_waits(reporter: WaitReporter) -> Iterator[None]:
    """Report the waits for environmental data within the block to a reporter.

    Args:
        reporter: Told the message of each wait as it starts, and None as it ends.
    """
    waits = _Waits(reporter)
    reporter_token = _reporter.set(waits)
    current_token = _current.set(None)
    try:
        yield
    finally:
        waits.end()
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
    waits = _reporter.get()
    if waits is None:
        yield
        return
    message = f'{AWAITING}: {description}'
    if typical_duration:
        message += f' ({typical_duration})'
    previous = _current.get()
    token = _current.set(message)
    waits.report(message)
    try:
        yield
    finally:
        _current.reset(token)
        waits.report(previous)
