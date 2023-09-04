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
from .mvregister import MVRegister
from .orset import ORSet
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
import json
import struct


class MVMap:
    """Implements a Map CRDT using Multi-Value Registers.
        https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-m-v-map/index.html
    """
    names: ORSet
    registers: dict[DataWrapperProtocol, MVRegister]
    clock: ClockProtocol

    def __init__(self, names: ORSet = None, registers: dict = None,
                clock: ClockProtocol = None
    ) -> None:
        """Initialize an MVMap from an ORSet of names, a list of
            MVRegisters, and a shared clock.
        """
        tressa(type(names) is ORSet or names is None,
            'names must be an ORSet or None')
        tressa(type(registers) is dict or registers is None,
            'registers must be a dict mapping names to MVRegisters or None')
        tressa(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')

        names = ORSet() if names is None else names
        registers = {} if registers is None else registers
        clock = ScalarClock() if clock is None else clock

        names.clock = clock

        for name in registers:
            tressa(name in names.observed or name in names.removed,
                'each register name must be in the names ORSet')
            tressa(type(registers[name]) is MVRegister,
                'each element of registers must be an MVRegister')
            registers[name].clock = clock

        self.names = names
        self.registers = registers
        self.clock = clock

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        names = self.names.pack()
        registers = {}

        for name in self.names.read():
            name_class = name.__class__.__name__
            key = name_class + '_' + name.pack().hex()
            value_class = self.registers[name].__class__.__name__
            registers[key] = value_class + '_' + self.registers[name].pack().hex()

        registers = json.dumps(registers, separators=(',', ':'), sort_keys=True)
        registers = bytes(registers, 'utf-8')

        clock_size = len(clock)
        names_size = len(names)
        registers_size = len(registers)

        return struct.pack(
            f'!III{clock_size}s{names_size}s{registers_size}s',
            clock_size,
            names_size,
            registers_size,
            clock,
            names,
            registers
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> MVMap:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 13, 'data must be at least 13 bytes')
        dependencies = {**globals(), **inject}

        # parse sizes
        clock_size, names_size, registers_size, _ = struct.unpack(
            f'!III{len(data)-12}s',
            data
        )

        # parse the rest of the data
        _, _, _, clock, names, registers_raw = struct.unpack(
            f'!III{clock_size}s{names_size}s{registers_size}s',
            data
        )

        # parse the clock and names
        clock_class, _, clock = clock.partition(b'_')
        clock_class = str(bytes.fromhex(str(clock_class, 'utf-8')), 'utf-8')
        tressa(clock_class in dependencies, f'cannot find {clock_class}')
        tressa(hasattr(dependencies[clock_class], 'unpack'),
            f'{clock_class} missing unpack method')
        clock = dependencies[clock_class].unpack(clock)
        names = ORSet.unpack(names, inject)

        # parse the registers
        registers_raw = json.loads(str(registers_raw, 'utf-8'))
        registers = {}

        for key in registers_raw:
            # resolve key to name
            name_class, name = key.split('_')
            name = dependencies[name_class].unpack(bytes.fromhex(name))

            # resolve value
            value_class, value = registers_raw[key].split('_')
            value = dependencies[value_class].unpack(bytes.fromhex(value), inject)

            # add to registers
            registers[name] = value

        return cls(names, registers, clock)

    def read(self) -> dict:
        """Return the eventually consistent data view."""
        result = {}

        for name in self.names.read():
            result[name] = self.registers[name].read()

        return result

    def update(self, state_update: StateUpdateProtocol) -> MVMap:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple of (str, DataWrapperProtocol, DataWrapperProtocol)')
        tressa(len(state_update.data) == 3,
            'state_update.data must be tuple of (str, DataWrapperProtocol, DataWrapperProtocol)')

        op, name, value = state_update.data
        tressa(type(op) is str and op in ('o', 'r'),
            'state_update.data[0] must be str op one of (\'o\', \'r\')')
        tressa(isinstance(name, DataWrapperProtocol),
            'state_update.data[1] must be DataWrapperProtocol name')
        tressa(isinstance(value, DataWrapperProtocol),
            'state_update.data[3] must be DataWrapperProtocol value')

        ts = state_update.ts

        if op == 'o':
            # try to add to the names ORSet
            self.names.update(StateUpdate(self.clock.uuid, ts, ('o', name)))

            # if register missing and name added successfully, create register
            if name not in self.registers and name in self.names.read():
                self.registers[name] = MVRegister(name, [value], self.clock, ts)

        if op == 'r':
            # try to remove from the names ORSet
            self.names.update(StateUpdate(self.clock.uuid, ts, ('r', name)))

        # if the register exists, update it
        if name in self.registers:
            self.registers[name].update(StateUpdate(self.clock.uuid, ts, value))

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        names_checksums = self.names.checksums()
        total_last_update = 0
        total_register_crc32 = 0

        for name in self.names.read():
            packed = self.registers[name].pack()
            total_register_crc32 += crc32(packed)
            total_last_update += self.registers[name].last_update

        return (
            total_last_update % 2**32,
            total_register_crc32 % 2**32,
            *names_checksums
        )

    def history(self, update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdateProtocols that will
            converge to the underlying data. Useful for
            resynchronization by replaying updates from divergent nodes.
        """
        registers_history: dict[DataWrapperProtocol, tuple[StateUpdateProtocol]] = {}
        orset_history = self.names.history(update_class)
        history = []

        for name in self.registers:
            registers_history[name] = self.registers[name].history(update_class)

        for update in orset_history:
            name = update.data[1]
            if name in registers_history:
                register_update = registers_history[name][0]
                update_class = register_update.__class__
                history.append(update_class(
                    clock_uuid=update.clock_uuid,
                    ts=register_update.ts,
                    data=(update.data[0], name, register_update.data)
                ))

        return tuple(history)

    def extend(self, name: DataWrapperProtocol, value: DataWrapperProtocol, /,
                *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Extends the dict with name: value. Returns an update_class
            (StateUpdate by default) that should be propagated to all
            nodes.
        """
        tressa(isinstance(name, DataWrapperProtocol),
            'name must be a DataWrapperProtocol')
        tressa(isinstance(value, DataWrapperProtocol) or value is None,
            'value must be a DataWrapperProtocol or None')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('o', name, value)
        )
        self.update(state_update)

        return state_update

    def unset(self, name: DataWrapperProtocol, /, *,
              update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Removes the key name from the dict. Returns a StateUpdate."""
        tressa(isinstance(name, DataWrapperProtocol),
            'name must be a DataWrapperProtocol')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('r', name, NoneWrapper())
        )
        self.update(state_update)

        return state_update
