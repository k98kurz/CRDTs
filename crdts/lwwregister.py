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
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from typing import Any
import struct


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
        # pack name
        name = self.name.__class__.__name__ + '_' + self.name.pack().hex()
        name = bytes(name, 'utf-8')
        name_size = len(name)

        # pack clock
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        clock_size = len(clock)

        # pack value
        value_type = bytes(self.value.__class__.__name__, 'utf-8')
        value_type_size = len(value_type)
        value = self.value.pack()
        value_size = len(value)

        # pack last_update
        last_update = self.clock.wrap_ts(self.last_update)
        ts_class = bytes(last_update.__class__.__name__, 'utf-8')
        ts_class_size = len(ts_class)
        last_update = last_update.pack()
        last_update_size = len(last_update)

        return struct.pack(
            f'!IIIIIII{name_size}s{clock_size}s{value_type_size}s{value_size}s' +
            f'{ts_class_size}s{last_update_size}s',
            ts_class_size,
            last_update_size,
            self.last_writer,
            name_size,
            clock_size,
            value_type_size,
            value_size,
            name,
            clock,
            value_type,
            value,
            ts_class,
            last_update,
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> LWWRegister:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 26, 'data must be at least 26 bytes')
        dependencies = {**globals(), **inject}

        # parse
        ts_class_size, last_update_size, last_writer, name_size, clock_size, value_type_size, value_size, _ = struct.unpack(
            f'!IIIIIII{len(data)-28}s',
            data
        )
        _, _, _, _, _, _, _, name, clock, value_type, value, ts_class, last_update = struct.unpack(
            f'!IIIIIII{name_size}s{clock_size}s{value_type_size}s{value_size}s' +
            f'{ts_class_size}s{last_update_size}s',
            data
        )

        # parse name
        name = str(name, 'utf-8')
        name_class, name_value = name.split('_')
        tressa(name_class in dependencies, f'cannot find {name_class}')
        tressa(hasattr(dependencies[name_class], 'unpack'),
            f'{name_class} missing unpack method')
        name = dependencies[name_class].unpack(bytes.fromhex(name_value))

        # parse clock
        clock_class, _, clock = clock.partition(b'_')
        clock_class = str(bytes.fromhex(str(clock_class, 'utf-8')), 'utf-8')
        tressa(clock_class in dependencies, f'cannot find {clock_class}')
        tressa(hasattr(dependencies[clock_class], 'unpack'),
            f'{clock_class} missing unpack method')
        clock = dependencies[clock_class].unpack(clock)

        # parse value
        value_type = str(value_type, 'utf-8')
        tressa(value_type in dependencies, 'value_type must be resolvable from globals or injected')
        value = dependencies[value_type].unpack(value)
        tressa(isinstance(value, DataWrapperProtocol),
            'value_type must implement DataWrapperProtocol')

        # parse last_update
        ts_class = str(ts_class, 'utf-8')
        tressa(ts_class in dependencies,
            'last_update wrapped class must be resolvable from globals or injected')
        tressa(hasattr(dependencies[ts_class], 'unpack'),
            f'{ts_class} missing unpack method')
        last_update = dependencies[ts_class].unpack(last_update)
        tressa(isinstance(last_update, DataWrapperProtocol),
            'last_update class must implement DataWrapperProtocol')
        last_update = last_update.value

        return cls(name, value, clock, last_update, last_writer)

    def read(self) -> DataWrapperProtocol:
        """Return the eventually consistent data view."""
        return self.value.__class__.unpack(self.value.pack())

    @classmethod
    def compare_values(cls, value1: DataWrapperProtocol,
                       value2: DataWrapperProtocol) -> bool:
        return value1.pack() > value2.pack()

    def update(self, state_update: StateUpdateProtocol) -> LWWRegister:
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
        return (update_class(
            clock_uuid=self.clock.uuid,
            ts=self.last_update,
            data=(self.last_writer, self.value)
        ),)

    def write(self, value: DataWrapperProtocol, writer: int, /, *,
              update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
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
        self.update(state_update)

        return state_update
