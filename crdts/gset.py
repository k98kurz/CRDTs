from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    CTDataWrapper,
    DecimalWrapper,
    IntWrapper,
    NoneWrapper,
    RGATupleWrapper,
    StrWrapper,
)
from .errors import tressa
from .interfaces import (
    ClockProtocol,
    DataWrapperProtocol,
    StateUpdateProtocol,
)
from .scalarclock import ScalarClock
from .serialization import serialize_part, deserialize_part
from .stateupdate import StateUpdate
from binascii import crc32
from dataclasses import dataclass, field
from types import NoneType
from typing import Any
import json
import struct


AcceptableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType

@dataclass
class GSet:
    """Implements the Grow-only Set (GSet) CRDT."""
    members: set[AcceptableType] = field(default_factory=set)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    update_history: dict[AcceptableType, StateUpdateProtocol] = field(default_factory=dict)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return serialize_part([
            self.clock,
            self.members,
            [
                (k, v) for k,v in self.update_history.items()
            ]
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> GSet:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 8, 'data must be more than 8 bytes')
        clock, members, update_history = deserialize_part(
            data,
            inject={**inject, 'StateUpdate': StateUpdate}
        )
        return cls(members, clock, {k:v for k,v in update_history})

    def read(self) -> set:
        """Return the eventually consistent data view."""
        return self.members.copy()

    def update(self, state_update: StateUpdateProtocol) -> GSet:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(isinstance(state_update.data, AcceptableType),
            'state_update.data must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')

        if state_update.data not in self.members:
            self.members.add(state_update.data)

        self.clock.update(state_update.ts)
        self.update_history[state_update.data] = state_update

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure. If from_ts and/or
            until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        total_crc32 = 0
        updates = []
        for member, state_update in self.update_history.items():
            if from_ts is not None and until_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts) or \
                    self.clock.is_later(state_update.ts, until_ts):
                    continue
            elif from_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts):
                    continue
            elif until_ts is not None:
                if self.clock.is_later(state_update.ts, until_ts):
                    continue
            updates.append(member)
            total_crc32 += crc32(serialize_part(member))

        return (
            self.clock.read() if until_ts is None else until_ts,
            len(updates),
            total_crc32 % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes. If from_ts and/
            or until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        updates = []

        for member in self.members:
            state_update = self.update_history[member]
            if from_ts is not None and until_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts) or \
                    self.clock.is_later(state_update.ts, until_ts):
                    continue
            elif from_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts):
                    continue
            elif until_ts is not None:
                if self.clock.is_later(state_update.ts, until_ts):
                    continue
            updates.append(state_update)

        return tuple(updates)

    def add(self, member: AcceptableType, /, *,
            update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Create, apply, and return a StateUpdate adding member to the set."""
        tressa(isinstance(member, AcceptableType),
            'member must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')

        ts = self.clock.read()
        state_update = update_class(clock_uuid=self.clock.uuid, ts=ts, data=member)
        self.update(state_update)

        return state_update
