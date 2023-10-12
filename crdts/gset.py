from __future__ import annotations
from .errors import tert, vert
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
from typing import Any, Callable, Type


@dataclass
class GSet:
    """Implements the Grow-only Set (GSet) CRDT."""
    members: set[SerializableType] = field(default_factory=set)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    metadata: dict[SerializableType, Any] = field(default_factory=dict)
    listeners: list[Callable] = field(default_factory=list)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return pack([
            self.clock,
            self.members,
            self.metadata,
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> GSet:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        clock, members, metadata = unpack(
            data,
            inject={**globals(), **inject}
        )
        return cls(members, clock, metadata)

    def read(self, inject: dict = {}) -> set[SerializableType]:
        """Return the eventually consistent data view."""
        return self.members.copy()

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> GSet:
        """Apply an update and return self (monad pattern). Raises
            TypeError or ValueError for invalid state_update.clock_uuid
            or state_update.data.
        """
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(isinstance(state_update.data, SerializableType),
            f'state_update.data must be SerializableType ({SerializableType})')

        self.invoke_listeners(state_update)

        if state_update.data not in self.members:
            self.members.add(state_update.data)

        self.clock.update(state_update.ts)
        self.metadata[state_update.data] = state_update.ts

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure. If from_ts and/or
            until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        total_crc32 = 0
        updates = []
        for member, ts in self.metadata.items():
            if from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue
            updates.append(member)
            total_crc32 += crc32(pack(member))

        return (
            crc32(pack(self.clock.read() if until_ts is None else until_ts)),
            len(updates),
            total_crc32 % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes. If from_ts and/
            or until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        updates = []

        for member in self.members:
            ts = self.metadata[member]
            if from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue
            updates.append(update_class(clock_uuid=self.clock.uuid, ts=ts, data=member))

        return tuple(updates)

    def get_merkle_history(self, /, *,
                           update_class: Type[StateUpdateProtocol] = StateUpdate
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
            synchronization. Raises TypeError or ValueError for invalid
            input.
        """
        return resolve_merkle_histories(self, history=history)

    def add(self, member: SerializableType, /, *,
            update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Create, apply, and return a StateUpdate adding member to the set."""
        tert(isinstance(member, SerializableType),
            f'member must be SerializableType ({SerializableType})')

        ts = self.clock.read()
        state_update = update_class(clock_uuid=self.clock.uuid, ts=ts, data=member)
        self.update(state_update)

        return state_update

    def add_listener(self, listener: Callable[[StateUpdateProtocol], None]) -> None:
        """Adds a listener that is called on each update."""
        tert(callable(listener),
             "listener must be Callable[[StateUpdateProtocol], None]")
        self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[StateUpdateProtocol], None]) -> None:
        """Removes a listener if it was previously added."""
        self.listeners.remove(listener)

    def invoke_listeners(self, state_update: StateUpdateProtocol) -> None:
        """Invokes all event listeners, passing them the state_update."""
        for listener in self.listeners:
            listener(state_update)
