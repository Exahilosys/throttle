import time
import functools
import operator

from . import schedules


__all__ = ('Base', 'Valve', 'Sling', 'wrap')


class Base:

    __slots__ = ('_bucket',)

    def __init__(self, bucket = None):

        self._bucket = bucket or []

    @property
    def bucket(self):

        """
        Get the bucket.
        """

        return self._bucket

    def count(self, key = None):

        """
        Get the number of values adhering to the key.
        """

        values = self._bucket

        return len(tuple(filter(key, values) if key else values))

    def left(self, limit, **kwargs):

        """
        Get the number of room left according to the limit.
        """

        return limit - self.count(**kwargs)

    def _observe(self, value, delay):

        """
        Track value, and discard it after delay.
        """

        raise NotImplementedError()

    def check(self,
              delay,
              limit,
              value,
              key = None,
              bypass = False,
              excess = None,
              rate = 1):

        """
        Check if the valve is open. If it is, track value.
        Returns the number of spaces left before adding value.
        """

        left = self.left(limit, key = key)

        if excess:

            delay *= (left + excess) / limit

        delay *= rate

        if excess or bypass or left:

            self._observe(value, delay)

        left = max(0, left)

        return left


class Valve(Base):

    """
    You can only have `limit` of `key`'d values every `rate` seconds.
    """

    __slots__  = ('_schedule',)

    def __init__(self, *args, loop = None, **kwargs):

        super().__init__(*args, **kwargs)

        schedule = schedules.asyncio(loop) if loop else schedules.threading()

        self._schedule = schedule

    def _observe(self, value, delay):

        """
        Track value, wait for delay and discard it.
        """

        self._bucket.append(value)

        manage = functools.partial(self._bucket.remove, value)

        return self._schedule(delay, manage)


class Static(Base):

    """
    Works like `Valve`, except it does not use any asynchronous functions.
    """

    __slots__ = ('_memory', '_time', '_state')

    def __init__(self, *args, time = time.monotonic, **kwargs):

        super().__init__(*args, **kwargs)

        self._memory = []

        self._time = time

    def _clean(self):

        """
        Discard all expired values.
        """

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

    def _observe(self, value, delay):

        """
        Clean all expired values.
        Track value and it's expected expiry time.
        """

        expiry = self._state + delay

        self._bucket.append(value)

        self._memory.append(expiry)

        return expiry

    def check(self, *args, full = True, **kwargs):

        self._state = self._time()

        left = super().check(*args, **kwargs)

        self._clean()

        return left


fail = object()


def wrap(*args, strict = False, fetch = None, valve = None, **kwargs):

    if not valve:

        valve = Static()

    check = functools.partial(valve.check, *args, **kwargs)

    def decorator(function):

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
