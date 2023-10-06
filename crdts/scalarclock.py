from __future__ import annotations
from .errors import tert, vert
from dataclasses import dataclass, field
from packify import pack, unpack
from uuid import uuid4
import struct


@dataclass
class ScalarClock:
    """Implements a Lamport logical scalar clock."""
    counter: int = field(default=1)
    uuid: bytes = field(default_factory=lambda: uuid4().bytes)
    default_ts: int = field(default=0)

    def read(self) -> int:
        """Return the current timestamp."""
        return self.counter

    def update(self, data: int) -> int:
        """Update the clock and return the current time stamp. Raises
            TypeError for invalid data.
        """
        tert(type(data) is int, 'data must be int')

        if data >= self.counter:
            self.counter = data + 1

        return self.counter

    @staticmethod
    def is_later(ts1: int, ts2: int) -> bool:
        """Return True iff ts1 > ts2. Raises TypeError for invalid ts1
            or ts2.
        """
        tert(type(ts1) is int, 'ts1 must be int')
        tert(type(ts2) is int, 'ts2 must be int')

        if ts1 > ts2:
            return True
        return False

    @staticmethod
    def are_concurrent(ts1: int, ts2: int) -> bool:
        """Return True if not ts1 > ts2 and not ts2 > ts1. Raises
            TypeError for invalid ts1 or ts2.
        """
        tert(type(ts1) is int, 'ts1 must be int')
        tert(type(ts2) is int, 'ts2 must be int')

        return not (ts1 > ts2) and not (ts2 > ts1)

    @staticmethod
    def compare(ts1: int, ts2: int) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable. Raises
            TypeError for invalid ts1 or ts2.
        """
        tert(type(ts1) is int, 'ts1 must be int')
        tert(type(ts2) is int, 'ts2 must be int')

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
    def unpack(cls, data: bytes, inject: dict = {}) -> ScalarClock:
        """Unpacks a clock from bytes. Raises TypeError or ValueError
            for invalid data.
        """
        tert(type(data) is bytes, 'data must be bytes')
        vert(len(data) >= 5, 'data must be at least 5 bytes')

        return cls(*struct.unpack(
            f'!I{len(data)-4}s',
            data
        ))

    @staticmethod
    def serialize_ts(ts: int) -> bytes:
        """Serialize a timestamp to bytes."""
        return pack(ts)

    @staticmethod
    def deserialize_ts(ts: bytes, /, *, inject: dict = {}) -> int:
        """Deserialize a timestamp from bytes."""
        return unpack(ts, inject=inject)

    def __repr__(self) -> str:
        return f"ScalarClock(counter={self.counter}, uuid={self.uuid.hex()}" + \
            f", default_ts={self.default_ts})"
