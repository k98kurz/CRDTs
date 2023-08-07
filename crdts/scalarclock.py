from __future__ import annotations
from .datawrappers import IntWrapper
from .errors import tressa
from dataclasses import dataclass, field
from uuid import uuid1
import struct


@dataclass
class ScalarClock:
    """Implements a Lamport logical scalar clock."""
    counter: int = field(default=1)
    uuid: bytes = field(default_factory=lambda: uuid1().bytes)
    default_ts: int = field(default=0)

    def read(self) -> int:
        """Return the current timestamp."""
        return self.counter

    def update(self, data: int) -> int:
        """Update the clock and return the current time stamp."""
        tressa(type(data) is int, 'data must be int')

        if data >= self.counter:
            self.counter = data + 1

        return self.counter

    @staticmethod
    def is_later(ts1: int, ts2: int) -> bool:
        """Return True iff ts1 > ts2."""
        tressa(type(ts1) is int, 'ts1 must be int')
        tressa(type(ts2) is int, 'ts2 must be int')

        if ts1 > ts2:
            return True
        return False

    @staticmethod
    def are_concurrent(ts1: int, ts2: int) -> bool:
        """Return True if not ts1 > ts2 and not ts2 > ts1."""
        tressa(type(ts1) is int, 'ts1 must be int')
        tressa(type(ts2) is int, 'ts2 must be int')

        return not (ts1 > ts2) and not (ts2 > ts1)

    @staticmethod
    def compare(ts1: int, ts2: int) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable.
        """
        tressa(type(ts1) is int, 'ts1 must be int')
        tressa(type(ts2) is int, 'ts2 must be int')

        if ts1 > ts2:
            return 1
        elif ts2 > ts1:
            return -1
        return 0

    def pack(self) -> bytes:
        """Packs the clock into bytes."""
        return struct.pack(
            f'!I{len(self.uuid)}s',
            self.counter,
            self.uuid
        )

    @classmethod
    def unpack(cls, data: bytes) -> ScalarClock:
        """Unpacks a clock from bytes."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) >= 5, 'data must be at least 5 bytes')

        return cls(*struct.unpack(
            f'!I{len(data)-4}s',
            data
        ))

    @classmethod
    def wrap_ts(cls, ts: int) -> IntWrapper:
        """Wrap a timestamp in an IntWrapper."""
        return IntWrapper(ts)
