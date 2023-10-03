from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    CTDataWrapper,
    DecimalWrapper,
    IntWrapper,
    NoneWrapper,
    RGAItemWrapper,
    StrWrapper,
)
from .errors import tressa, tert, vert
from .interfaces import (
    ClockProtocol,
    DataWrapperProtocol,
    StateUpdateProtocol,
)
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from hashlib import sha256
from packify import SerializableType, pack, unpack
from typing import Any


class MVRegister:
    """Implements the Multi-Value Register CRDT."""
    name: DataWrapperProtocol
    values: list[DataWrapperProtocol]
    clock: ClockProtocol
    last_update: Any

    def __init__(self, name: DataWrapperProtocol,
                 values: list[DataWrapperProtocol] = [],
                 clock: ClockProtocol = None,
                 last_update: Any = None) -> None:
        if clock is None:
            clock = ScalarClock()
        if last_update is None:
            last_update = clock.default_ts

        self.name = name
        self.values = values
        self.clock = clock
        self.last_update = last_update

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return pack([
            self.name,
            self.clock,
            self.last_update,
            self.values
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> MVRegister:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 26, 'data must be at least 26 bytes')
        name, clock, last_update, values = unpack(
            data, inject={**globals(), **inject}
        )
        return cls(name, values, clock, last_update)

    def read(self, inject: dict = {}) -> tuple[SerializableType]:
        """Return the eventually consistent data view."""
        return tuple([
            unpack(
                pack(value), inject={**globals(), **inject}
            )
            for value in self.values
        ])

    @classmethod
    def compare_values(cls, value1: SerializableType,
                       value2: SerializableType) -> bool:
        return pack(value1) > pack(value2)

    def update(self, state_update: StateUpdateProtocol) -> MVRegister:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(isinstance(state_update.data, SerializableType),
            'state_update.data must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')

        # set the value if the update happens after current state
        if self.clock.is_later(state_update.ts, self.last_update):
            self.last_update = state_update.ts
            self.values = [state_update.data]

        if self.clock.are_concurrent(state_update.ts, self.last_update):
            # preserve all concurrent updates
            if state_update.data not in self.values:
                self.values.append(state_update.data)
                self.values.sort(key=lambda item: pack(item))

        self.clock.update(state_update.ts)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.last_update,
            sum([crc32(pack(v)) for v in self.values]) % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying updates from divergent
            nodes.
        """
        if from_ts is not None and self.clock.is_later(from_ts, self.last_update):
            return tuple()
        if until_ts is not None and self.clock.is_later(self.last_update, until_ts):
            return tuple()

        return tuple([
            update_class(clock_uuid=self.clock.uuid, ts=self.last_update, data=v)
            for v in self.values
        ])

    def get_merkle_history(self, /, *,
                           update_class: type[StateUpdateProtocol] = StateUpdate
                           ) -> list[bytes, list[bytes], dict[bytes, bytes]]:
        """Get a Merklized history for the StateUpdates of the form
            [root, [content_id for update in self.history()], {
            content_id: packed for update in self.history()}] where
            packed is the result of update.pack() and content_id is the
            sha256 of the packed update.
        """
        history = self.history(update_class=update_class)
        leaves = [
            update.pack()
            for update in history
        ]
        leaf_ids = [
            sha256(leaf).digest()
            for leaf in leaves
        ]
        history = {
            leaf_id: leaf
            for leaf_id, leaf in zip(leaf_ids, leaves)
        }
        leaf_ids.sort()
        root = sha256(b''.join(leaf_ids)).digest()
        return [root, leaf_ids, history]

    def resolve_merkle_histories(self, history: list[bytes, list[bytes]]) -> list[bytes]:
        """Accept a history of form [root, leaves] from another node.
            Return the leaves that need to be resolved and merged for
            synchronization.
        """
        tert(type(history) in (list, tuple), 'history must be [[bytes, ], bytes]')
        vert(len(history) >= 2, 'history must be [[bytes, ], bytes]')
        tert(all([type(leaf) is bytes for leaf in history[1]]),
             'history must be [[bytes, ], bytes]')
        local_history = self.get_merkle_history()
        if local_history[0] == history[0]:
            return []
        return [
            leaf for leaf in history[1]
            if leaf not in local_history[1]
        ]

    def write(self, value: SerializableType, /, *,
              update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Writes the new value to the register and returns an
            update_class (StateUpdate by default).
        """
        tressa(isinstance(value, SerializableType),
            'value must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=value
        )
        self.update(state_update)

        return state_update
