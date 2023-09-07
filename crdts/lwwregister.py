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
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .scalarclock import ScalarClock
from .serialization import serialize_part, deserialize_part
from .stateupdate import StateUpdate
from binascii import crc32
from typing import Any


class LWWRegister:
    """Implements the Last Writer Wins Register CRDT."""
    name: DataWrapperProtocol
    value: DataWrapperProtocol
    clock: ClockProtocol
    last_update: Any
    last_writer: int

    def __init__(self, name: DataWrapperProtocol,
                 value: DataWrapperProtocol = None,
                 clock: ClockProtocol = None,
                 last_update: Any = None,
                 last_writer: int = 0) -> None:
        if value is None:
            value = NoneWrapper()
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
        return serialize_part([
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
        name, clock, value, last_update, last_writer = deserialize_part(
            data, inject={**globals(), **inject}
        )
        return cls(
            name=name,
            clock=clock,
            value=value,
            last_update=last_update,
            last_writer=last_writer,
        )

    def read(self, /, *, inject: dict = {}) -> DataWrapperProtocol:
        """Return the eventually consistent data view."""
        return deserialize_part(
            serialize_part(self.value), inject={**globals(), **inject}
        )

    @classmethod
    def compare_values(cls, value1: DataWrapperProtocol,
                       value2: DataWrapperProtocol) -> bool:
        return value1.pack() > value2.pack()

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> LWWRegister:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple of (int, DataWrapperProtocol)')
        tressa(len(state_update.data) == 2,
            'state_update.data must be tuple of (int, DataWrapperProtocol)')
        tressa(type(state_update.data[0]) is int,
            'state_update.data[0] must be int writer_id')
        tressa(isinstance(state_update.data[1], DataWrapperProtocol),
            'state_update.data[1] must be DataWrapperProtocol')

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
            crc32(self.value.pack()),
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

    def write(self, value: DataWrapperProtocol, writer: int, /, *,
              update_class: type[StateUpdateProtocol] = StateUpdate,
              inject: dict = {}) -> StateUpdateProtocol:
        """Writes the new value to the register and returns an
            update_class (StateUpdate by default). Requires a writer int
            for tie breaking.
        """
        tressa(isinstance(value, DataWrapperProtocol) or value is None,
            'value must be a DataWrapperProtocol or None')
        tressa(type(writer) is int, 'writer must be an int')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(writer, value)
        )
        self.update(state_update, inject=inject)

        return state_update
