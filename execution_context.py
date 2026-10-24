"""Per-task replay storage/clock; never changes process environment or user DB."""
from contextlib import contextmanager
from contextvars import ContextVar

root = ContextVar('replay_storage', default=None)
clock = ContextVar('replay_clock', default=None)
market_data = ContextVar('replay_market_data', default=None)


@contextmanager
def replay(directory,bundle=None):
    storage_token = root.set(directory)
    clock_token = clock.set(None)
    market_token = market_data.set(bundle)
    try:
        yield
    finally:
        clock.reset(clock_token)
        root.reset(storage_token)
        market_data.reset(market_token)
