"""Stops the site from queuing up behind a Redis that is not answering.

Every cache miss costs one connection attempt, and a page with a dozen
thumbnails makes dozens of them. With Redis down each one waits out the
connect timeout, and the page never finishes inside the proxy's own limit -
so a cache, which is supposed to be optional, takes the page down with it.

The guard sits on the connection itself, which is the one place both users of
Redis pass through: the cache and the view counters. After a few failures in a
row it refuses to dial for a while and fails instantly instead, and the first
success afterwards clears it.

The count lives in one process. With several web processes each learns on its
own, which costs a few extra attempts and needs no shared state to go wrong.
"""

import logging
import threading
import time

import redis

logger = logging.getLogger(__name__)

FAILURES_BEFORE_OPENING = 3
COOLDOWN_SECONDS = 30


class _Circuit:
    def __init__(self, failures_before_opening, cooldown_seconds):
        self._failures_before_opening = failures_before_opening
        self._cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._failures = 0
        self._open_until = 0.0

    def is_open(self):
        with self._lock:
            return time.monotonic() < self._open_until

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self._failures_before_opening:
                self._open_until = time.monotonic() + self._cooldown_seconds
                logger.warning(
                    "redis guard: %s failed connections, not dialling for %ss",
                    self._failures,
                    self._cooldown_seconds,
                )

    def record_success(self):
        with self._lock:
            if self._failures:
                logger.info("redis guard: connection restored")
            self._failures = 0
            self._open_until = 0.0


_circuit = _Circuit(FAILURES_BEFORE_OPENING, COOLDOWN_SECONDS)


class GuardedConnection(redis.Connection):
    """A connection that gives up quickly while Redis is known to be down.

    Subclasses ConnectionError on purpose: everything above already treats that
    as "Redis is not available", so nothing else has to learn a new error.
    """

    def connect(self):
        if _circuit.is_open():
            raise redis.ConnectionError("redis guard: not dialling, Redis is down")
        try:
            super().connect()
        except redis.ConnectionError:
            _circuit.record_failure()
            raise
        _circuit.record_success()
