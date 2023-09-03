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


class MVRegister:
    """Implements the Multi-Value Register CRDT."""
    name: DataWrapperProtocol
    values: list[DataWrapperProtocol]
    clock: ClockProtocol
    last_updates: Any

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
        # pack name
        name = self.name.__class__.__name__ + '_' + self.name.pack().hex()
        name = bytes(name, 'utf-8')
        name_size = len(name)

        # pack clock
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        clock_size = len(clock)

        # pack values
        packed_values = b''
        for value in self.values:
            value_type = bytes(value.__class__.__name__, 'utf-8')
            value_type_size = len(value_type)
            value_packed = value.pack()
            value_size = len(value_packed)
            value_package = struct.pack(
                f'!II{value_type_size}s{value_size}s',
                value_type_size,
                value_size,
                value_type,
                value_packed
            )
            packed_values = packed_values + value_package
        values_size = len(packed_values)

        # pack last_update
        last_update = self.clock.wrap_ts(self.last_update)
        ts_class = bytes(last_update.__class__.__name__, 'utf-8')
        ts_class_size = len(ts_class)
        last_update = last_update.pack()
        last_update_size = len(last_update)

        return struct.pack(
            f'!IIIII{name_size}s{clock_size}s{values_size}s' +
            f'{ts_class_size}s{last_update_size}s',
            ts_class_size,
            last_update_size,
            name_size,
            clock_size,
            values_size,
            name,
            clock,
            packed_values,
            ts_class,
            last_update,
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> MVRegister:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 26, 'data must be at least 26 bytes')
        dependencies = {**globals(), **inject}

        # parse
        ts_class_size, last_update_size, name_size, clock_size, values_size, data = struct.unpack(
            f'!IIIII{len(data)-20}s',
            data
        )
        name, clock, packed_values, ts_class, last_update = struct.unpack(
            f'!{name_size}s{clock_size}s{values_size}s' +
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

        # parse values
        values = []
        while len(packed_values):
            value_type_size, value_size, packed_values = struct.unpack(
                f'!II{len(packed_values)-8}s',
                packed_values
            )
            remaining = len(packed_values) - value_type_size - value_size
            value_type, value, packed_values = struct.unpack(
                f'!{value_type_size}s{value_size}s{remaining}s',
                packed_values
            )
            value_type = str(value_type, 'utf-8')
            tressa(value_type in dependencies, f'cannot find {value_type}')
            value = dependencies[value_type].unpack(value)
            tressa(isinstance(value, DataWrapperProtocol),
                'value_type must implement DataWrapperProtocol')
            values.append(value)

        # parse last_update
        ts_class = str(ts_class, 'utf-8')
        tressa(ts_class in dependencies,
            'last_update wrapped class must be resolvable from globals')
        tressa(hasattr(dependencies[ts_class], 'unpack'),
            f'{ts_class} missing unpack method')
        last_update = dependencies[ts_class].unpack(last_update)
        tressa(isinstance(last_update, DataWrapperProtocol),
            'last_update class must implement DataWrapperProtocol')
        last_update = last_update.value

        return cls(name, values, clock, last_update)

    def read(self) -> tuple[DataWrapperProtocol]:
        """Return the eventually consistent data view."""
        return tuple([value.__class__.unpack(value.pack()) for value in self.values])

    @classmethod
    def compare_values(cls, value1: DataWrapperProtocol,
                       value2: DataWrapperProtocol) -> bool:
        return value1.pack() > value2.pack()

    def update(self, state_update: StateUpdateProtocol) -> MVRegister:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(isinstance(state_update.data, DataWrapperProtocol),
            'state_update.data must be DataWrapperProtocol')

        # set the value if the update happens after current state
        if self.clock.is_later(state_update.ts, self.last_update):
            self.last_update = state_update.ts
            self.values = [state_update.data]

        if self.clock.are_concurrent(state_update.ts, self.last_update):
            # preserve all concurrent updates
            if state_update.data not in self.values:
                self.values.append(state_update.data)
                self.values.sort(key=lambda item: item.pack())

        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.last_update,
            sum([crc32(v.pack()) for v in self.values]) % 2**32,
        )

    def history(self, update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying updates from divergent
            nodes.
        """
        return tuple([
            update_class(self.clock.uuid, self.last_update, v)
            for v in self.values
        ])

    def write(self, value: DataWrapperProtocol, /, *,
              update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Writes the new value to the register and returns an
            update_class (StateUpdate by default).
        """
        tressa(isinstance(value, DataWrapperProtocol) or value is None,
            'value must be a DataWrapperProtocol or None')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=value
        )
        self.update(state_update)

        return state_update
