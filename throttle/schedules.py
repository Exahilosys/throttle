import asyncio as asyncio_
import threading as threading_


__all__ = ()


def threading():

    def execute(delay, manage):

        timer = threading_.Timer(delay, manage)

        timer.start()

        return timer

    return execute


def asyncio(loop):

    def execute(delay, manage):

        handle = loop.call_later(delay, manage)

        return handle

    return execute
