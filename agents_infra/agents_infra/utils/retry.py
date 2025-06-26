import functools
import random


def jitter(base, cap):
    """
    Generator for decorralated jitter backoff.

    Parameters:
        base (int | float): Minimum delay (in seconds).
        cap (int | float): Maximum delay (in seconds).
    """
    if base == cap:
        yield base

    if base > cap:
        raise ValueError('Minimum delay cannot be larger than maximum delay')

    interval = base

    while True:
        interval = min(cap, random.uniform(base, interval * 3))
        yield interval


def make_callback(callback, *args, **kwargs):
    return functools.partial(callback, *args, **kwargs)
