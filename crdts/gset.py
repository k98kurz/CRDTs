from __future__ import annotations
from .errors import tressa, tert
from .interfaces import (
    ClockProtocol,
    StateUpdateProtocol,
)
from .merkle import get_merkle_history, resolve_merkle_histories
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from dataclasses import dataclass, field
from packify import SerializableType, pack, unpack
from typing import Any


@dataclass
class GSet:
    """Implements the Grow-only Set (GSet) CRDT."""
    members: set[SerializableType] = field(default_factory=set)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    update_history: dict[SerializableType, StateUpdateProtocol] = field(default_factory=dict)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return pack([
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
        clock, members, update_history = unpack(
            data,
            inject={**globals(), **inject}
        )
        return cls(members, clock, {k:v for k,v in update_history})

    def read(self, inject: dict = {}) -> set[SerializableType]:
        """Return the eventually consistent data view."""
        return self.members.copy()

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> GSet:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(isinstance(state_update.data, SerializableType),
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
            if from_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(state_update.ts, until_ts):
                    continue
            updates.append(member)
            total_crc32 += crc32(pack(member))

        return (
            self.clock.read() if until_ts is None else until_ts,
            len(updates),
            total_crc32 % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes. If from_ts and/
            or until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        updates = []

        for member in self.members:
            state_update = self.update_history[member]
            if from_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(state_update.ts, until_ts):
                    continue
            updates.append(state_update)

        return tuple(updates)

    def get_merkle_history(self, /, *,
                           update_class: type[StateUpdateProtocol] = StateUpdate
                           ) -> list[bytes, list[bytes], dict[bytes, bytes]]:
        """Get a Merklized history for the StateUpdates of the form
            [root, [content_id for update in self.history()], {
            content_id: packed for update in self.history()}] where
            packed is the result of update.pack() and content_id is the
            sha256 of the packed update.
        """
        return get_merkle_history(self, update_class=update_class)

    def resolve_merkle_histories(self, history: list[bytes, list[bytes]]) -> list[bytes]:
        """Accept a history of form [root, leaves] from another node.
            Return the leaves that need to be resolved and merged for
            synchronization.
        """
        return resolve_merkle_histories(self, history=history)

    def add(self, member: SerializableType, /, *,
            update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Create, apply, and return a StateUpdate adding member to the set."""
        tert(isinstance(member, SerializableType),
            f'member must be {SerializableType}')

        ts = self.clock.read()
        state_update = update_class(clock_uuid=self.clock.uuid, ts=ts, data=member)
        self.update(state_update)

        return state_update
