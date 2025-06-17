import random


def jitter(base, cap):
    """
    Generator for decorralated jitter backoff.

    Parameters:
        base (int | float): Minimum delay (in seconds).
        cap (int | float): Maximum delay (in seconds).
    """
    interval = base

    while True:
        interval = min(cap, random.uniform(base, interval * 3))
        yield interval
