import abc
import time
import functools
import operator

from . import schedules


__all__ = ('Valve', 'Static', 'wrap')


class Base(abc.ABC):

    """An abstract base for all classes implementing frequency check mechanisms.

    :param list bucket:
        Used to track state.
    """

    __slots__ = ('_bucket',)

    def __init__(self, bucket = None):

        self._bucket = bucket or []

    @property
    def bucket(self):

        """
        Storage tracking values.

        .. warning::
            This object is solely internally managed. Changes to it may lead
            to unexpected behavior.
        """

        return self._bucket

    def count(self, key = None):

        """
        Get the number of values adhering to the key.

        :param func key:
            Only count items abiding to this.
        """

        values = self._bucket

        return len(tuple(filter(key, values) if key else values))

    def left(self, limit, **kwargs):

        """
        Get the number of space left according to the limit.

        :param int limit:
            Current count will be deducted from this.
        :param kwargs:
            Passed on to :func:`count`
        """

        return limit - self.count(**kwargs)

    def _setup(self):

        pass

    @abc.abstractmethod
    def _observe(self, value, delay):

        """
        Track value, and discard it after delay.

        :param any value:
            Change according to your ``key`` needs.
        :param int delay:
            Wait for this many seconds before discarding.
        """

        raise NotImplementedError()

    def _cleanup(self):

        pass

    def check(self,
              delay,
              limit,
              value,
              key = None,
              bypass = False,
              excess = None,
              rate = 1):

        """
        Check if the valve is open and track the value accordingly.

        :param float delay:
            Wait for this many seconds before discarding.
        :param int limit:
            Only track the value if the current size is less than this.
        :param any value:
            Something to track, adapt it to your ``key`` needs.
        :param func key:
            Only account for values adhering to this.
        :param bool bypass:
            Track the value regardless of whether it exceeds limit.
        :param int excess:
            Amount of extra values allowed for tracking.
        :param float rate:
            Multiplied against the delay after any modifications to it.

        .. note::
            Using ``excess`` will not affect the result, but will reduce the \
            delay after which extra values are discarded. The formula for the \
            rate-affecting delay is ``(left + excess) / limit``.
        """

        self._setup()

        left = self.left(limit, key = key)

        if excess:

            delay *= (left + excess) / limit

        delay *= rate

        if excess or bypass or left:

            self._observe(value, delay)

        self._cleanup()

        left = max(0, left)

        return left


class Valve(Base):

    """
    Can only have ``limit`` of ``key``'d values every ``rate`` seconds.

    :param asyncio.AbstractEventLoop loop:
        Signal the use of :py:mod:`asyncio` instead of :py:mod:`threading`.
    """

    __slots__  = ('_schedule',)

    def __init__(self, *args, loop = None, **kwargs):

        super().__init__(*args, **kwargs)

        schedule = schedules.asyncio(loop) if loop else schedules.threading()

        self._schedule = schedule

    def _observe(self, value, delay):

        self._bucket.append(value)

        manage = functools.partial(self._bucket.remove, value)

        return self._schedule(delay, manage)


class Static(Base):

    """
    Works like :class:`.Valve`, except it doesn't use any concurrent utilities.

    :param func time:
        Used for calculating expiry timestamps.

    .. note::
        Insourcing time calculations results in :meth:`.check` being almost
        **3x** slower.
    """

    __slots__ = ('_memory', '_time', '_state')

    def __init__(self, *args, time = time.monotonic, **kwargs):

        super().__init__(*args, **kwargs)

        self._memory = []

        self._time = time

    def _setup(self):

        self._state = self._time()

    def _observe(self, value, delay):

        expiry = self._state + delay

        self._bucket.append(value)

        self._memory.append(expiry)

        return expiry

    def _cleanup(self):

        index = 0

        while True:

            try:

                expiry = self._memory[index]

            except IndexError:

                break

            if expiry > self._state:

                index += 1

                continue

            del self._memory[index]

            del self._bucket[index]


def wrap(*args,
         strict = False,
         fetch = None,
         valve = None,
         fail = None,
         **kwargs):

    """
    Decorator for controlling execution.

    :param bool strict:
        Account for arguments when deciding whether to throttle. Similar to
        :func:`functools.lru_cache` returning the same result for the same
        arguments.
    :param func fetch:
        Takes the arbitrary amount of positional and keyword arguments passed
        and returns a single value used for state tracking.
    :param Base valve:
        Used for deciding whether to prevent execution.
    :param any fail:
        Will be returned instead of the actual functon result if throtted.

    Additional arguments will be used as defaults for :func:`~Base.check`.
    """

    if not valve:

        valve = Static()

    def decorator(function):

        check = functools.partial(valve.check, *args, **kwargs)

        nonlocal fetch

        if strict:

            if not fetch:

                def fetch(*args, **kwargs):

                    items = kwargs.items()

                    value = (*args, *items)

                    return value

            def execute(*args, **kwargs):

                value = fetch(*args, **kwargs)

                key = functools.partial(operator.eq, value)

                allow = check(value, key = key)

                return allow

        else:

            if fetch:

                def execute(*args, **kwargs):

                    value = fetch()

                    allow = check(value)

                    return allow

            else:

                def execute(*args, **kwargs):

                    value = None

                    allow = check(value)

                    return allow

        def wrapper(*args, **kwargs):

            allow = execute(*args, **kwargs)

            result = function(*args, **kwargs) if allow else fail

            return result

        wrapper.valve = valve

        return wrapper

    return decorator
