from __future__ import annotations
from .errors import tert, vert
from dataclasses import dataclass
from packify import unpack, pack, SerializableType
from typing import Hashable


@dataclass
class StateUpdate:
    """Default class for encoding delta states."""
    clock_uuid: bytes
    ts: SerializableType
    data: Hashable

    def pack(self) -> bytes:
        """Serialize a StateUpdate. Assumes that all types within
            update.data and update.ts are packable by packify.
        """
        return pack([
            self.clock_uuid,
            self.ts,
            self.data,
        ])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> StateUpdate:
        """Deserialize a StateUpdate. Assumes that all types within
            update.data and update.ts are either built-in types or
            packify.Packables accessible from the inject dict.
        """
        tert(type(data) in (bytes, bytearray), 'data must be bytes or bytearray')
        vert(len(data) >= 12, 'data must be at least 12 long')
        uuid, ts, data = unpack(data, inject=inject)
        return cls(clock_uuid=uuid, ts=ts, data=data)

    def __repr__(self) -> str:
        return f'StateUpdate(clock_uuid={self.clock_uuid.hex()}, ts={self.ts}, data={self.data})'
