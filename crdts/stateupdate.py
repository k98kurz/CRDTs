from __future__ import annotations
from .errors import tressa
from .serialization import deserialize_part, serialize_part
from dataclasses import dataclass
from typing import Any, Hashable
import struct


@dataclass
class StateUpdate:
    clock_uuid: bytes
    ts: Any
    data: Hashable

    def pack(self) -> bytes:
        """Serialize a StateUpdate. Assumes that all types within
            update.data and update.ts are either built-in types or
            PackableProtocols accessible from this scope.
        """
        # serialize timestamp
        uuid = serialize_part(self.clock_uuid)
        ts = serialize_part(self.ts)
        data = serialize_part(self.data)

        return struct.pack(
            f'!III{len(uuid)}s{len(ts)}s{len(data)}s',
            len(uuid),
            len(ts),
            len(data),
            uuid,
            ts,
            data
        )

    @classmethod
    def unpack(cls, data: bytes) -> StateUpdate:
        """Deserialize a StateUpdate. Assumes that all types within
            update.data and update.ts are either built-in types or
            PackableProtocols accessible from this scope.
        """
        tressa(type(data) in (bytes, bytearray), 'data must be bytes or bytearray')
        tressa(len(data) >= 12, 'data must be at least 12 long')

        uuid_len, ts_len, data_len, _ = struct.unpack(f'!III{len(data)-12}s', data)
        _, _, _, uuid, ts, data = struct.unpack(f'III{uuid_len}s{ts_len}s{data_len}s', data)

        uuid = deserialize_part(uuid)
        ts = deserialize_part(ts)
        data = deserialize_part(data)

        return cls(clock_uuid=uuid, ts=ts, data=data)
