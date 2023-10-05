from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import crdts
from crdts import (
    classes,
    datawrappers,
    interfaces,
    errors
)
from dataclasses import dataclass, field


class CustomStateUpdate(classes.StateUpdate):
    pass


@dataclass
class StrClock:
    """Implements a logical clock using strs."""
    counter: str = field(default='0')
    uuid: bytes = field(default=b'1234567890')
    default_ts: str = field(default='')

    def read(self) -> str:
        """Return the current timestamp."""
        return self.counter

    def update(self, data: str) -> str:
        """Update the clock and return the current time stamp."""
        assert type(data) is str, 'data must be str'

        if len(data) >= len(self.counter):
            self.counter = data + '1'

        return self.counter

    @staticmethod
    def is_later(ts1: str, ts2: str) -> bool:
        """Return True iff len(ts1) > len(ts2)."""
        assert type(ts1) is str, 'ts1 must be str'
        assert type(ts2) is str, 'ts2 must be str'

        if len(ts1) > len(ts2):
            return True
        return False

    @staticmethod
    def are_concurrent(ts1: str, ts2: str) -> bool:
        """Return True if len(ts1) == len(ts2)."""
        assert type(ts1) is str, 'ts1 must be str'
        assert type(ts2) is str, 'ts2 must be str'

        return len(ts1) == len(ts2)

    @staticmethod
    def compare(ts1: str, ts2: str) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable.
        """
        assert type(ts1) is str, 'ts1 must be str'
        assert type(ts2) is str, 'ts2 must be str'

        if len(ts1) > len(ts2):
            return 1
        elif len(ts2) > len(ts1):
            return -1
        return 0

    def pack(self) -> bytes:
        """Packs the clock into bytes."""
        return bytes(self.counter, 'utf-8') + b'_' + self.uuid

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> StrClock:
        """Unpacks a clock from bytes."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) >= 5, 'data must be at least 5 bytes'

        counter, _, uuid = data.partition(b'_')

        return cls(counter=str(counter, 'utf-8'), uuid=uuid)

    @classmethod
    def serialize_ts(cls, ts: str) -> bytes:
        return bytes(ts, 'utf-8')

    @classmethod
    def deserialize_ts(cls, ts: bytes, /, *, inject: dict = {}) -> str:
        return str(ts, 'utf-8')
