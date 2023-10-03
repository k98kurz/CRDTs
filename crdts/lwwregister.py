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
from .errors import tressa
from .interfaces import (
    ClockProtocol,
    DataWrapperProtocol,
    StateUpdateProtocol,
)
from .merkle import get_merkle_history, resolve_merkle_histories
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from packify import SerializableType, pack, unpack
from typing import Any


class LWWRegister:
    """Implements the Last Writer Wins Register CRDT."""
    name: SerializableType
    value: SerializableType
    clock: ClockProtocol
    last_update: Any
    last_writer: int

    def __init__(self, name: SerializableType,
                 value: SerializableType = None,
                 clock: ClockProtocol = None,
                 last_update: Any = None,
                 last_writer: int = 0) -> None:
        if clock is None:
            clock = ScalarClock()
        if last_update is None:
            last_update = clock.default_ts

        self.name = name
        self.value = value
        self.clock = clock
        self.last_update = last_update
        self.last_writer = last_writer

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return pack([
            self.name,
            self.clock,
            self.value,
            self.last_update,
            self.last_writer
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> LWWRegister:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 26, 'data must be at least 26 bytes')
        name, clock, value, last_update, last_writer = unpack(
            data, inject={**globals(), **inject}
        )
        return cls(
            name=name,
            clock=clock,
            value=value,
            last_update=last_update,
            last_writer=last_writer,
        )

    def read(self, /, *, inject: dict = {}) -> SerializableType:
        """Return the eventually consistent data view."""
        return unpack(
            pack(self.value), inject={**globals(), **inject}
        )

    @classmethod
    def compare_values(cls, value1: SerializableType,
                       value2: SerializableType) -> bool:
        return pack(value1) > pack(value2)

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> LWWRegister:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple of (int, SerializableType)')
        tressa(len(state_update.data) == 2,
            'state_update.data must be tuple of (int, SerializableType)')
        tressa(type(state_update.data[0]) is int,
            'state_update.data[0] must be int writer_id')
        tressa(isinstance(state_update.data[1], SerializableType),
            'state_update.data[1] must be SerializableType')

        # set the value if the update happens after current state
        if self.clock.is_later(state_update.ts, self.last_update):
            self.last_update = state_update.ts
            self.last_writer = state_update.data[0]
            self.value = state_update.data[1]

        if self.clock.are_concurrent(state_update.ts, self.last_update):
            # use writer int and value as tie breakers for concurrent updates
            if (state_update.data[0] > self.last_writer) or (
                    state_update.data[0] == self.last_writer and
                    self.compare_values(state_update.data[1], self.value)
                ):
                self.last_writer = state_update.data[0]
                self.value = state_update.data[1]

        self.clock.update(state_update.ts)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.last_update,
            self.last_writer,
            crc32(pack(self.value)),
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

        return (update_class(
            clock_uuid=self.clock.uuid,
            ts=self.last_update,
            data=(self.last_writer, self.value)
        ),)

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

    def write(self, value: SerializableType, writer: int, /, *,
              update_class: type[StateUpdateProtocol] = StateUpdate,
              inject: dict = {}) -> StateUpdateProtocol:
        """Writes the new value to the register and returns an
            update_class (StateUpdate by default). Requires a writer int
            for tie breaking.
        """
        tressa(isinstance(value, SerializableType) or value is None,
            'value must be a SerializableType or None')
        tressa(type(writer) is int, 'writer must be an int')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(writer, value)
        )
        self.update(state_update, inject=inject)

        return state_update
