from __future__ import annotations
from binascii import crc32
from bisect import bisect
from dataclasses import dataclass, field
from decimal import Decimal
from .counter import Counter
from .datawrappers import (
    BytesWrapper,
    CTDataWrapper,
    DecimalWrapper,
    IntWrapper,
    NoneWrapper,
    RGATupleWrapper,
    StrWrapper,
)
from .gset import GSet
from .interfaces import (
    ClockProtocol,
    CRDTProtocol,
    DataWrapperProtocol,
    PackableProtocol,
    StateUpdateProtocol,
)
from .lwwregister import LWWRegister
from .orset import ORSet
from .pncounter import PNCounter
from .rgarray import RGArray
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from enum import Enum
from random import randrange
from types import NoneType
from typing import Any, Hashable, Optional
from uuid import uuid1
import json
import struct


class LWWMap:
    """Implements the Last Writer Wins Map CRDT.
        https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-l-w-w-map/index.html
    """
    names: ORSet
    registers: dict[DataWrapperProtocol, LWWRegister]
    clock: ClockProtocol

    def __init__(self, names: ORSet = None, registers: dict = None,
                clock: ClockProtocol = None
    ) -> None:
        """Initialize an LWWMap from an ORSet of names, a list of
            LWWRegisters, and a shared clock.
        """
        assert type(names) is ORSet or names is None, \
            'names must be an ORSet or None'
        assert type(registers) is dict or registers is None, \
            'registers must be a dict mapping names to LWWRegisters or None'
        assert isinstance(clock, ClockProtocol) or clock is None, \
            'clock must be a ClockProtocol or None'

        names = ORSet() if names is None else names
        registers = {} if registers is None else registers
        clock = ScalarClock() if clock is None else clock

        names.clock = clock

        for name in registers:
            assert name in names.observed or name in names.removed, \
                'each register name must be in the names ORSet'
            assert type(registers[name]) is LWWRegister, \
                'each element of registers must be an LWWRegister'
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
    def unpack(cls, data: bytes, inject: dict = {}) -> LWWMap:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 13, 'data must be at least 13 bytes'
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
        assert clock_class in dependencies, f'cannot find {clock_class}'
        assert hasattr(dependencies[clock_class], 'unpack'), \
            f'{clock_class} missing unpack method'
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

    def update(self, state_update: StateUpdateProtocol) -> LWWMap:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple of (str, DataWrapperProtocol, int, DataWrapperProtocol)'
        assert len(state_update.data) == 4, \
            'state_update.data must be tuple of (str, DataWrapperProtocol, int, DataWrapperProtocol)'

        op, name, writer, value = state_update.data
        assert type(op) is str and op in ('o', 'r'), \
            'state_update.data[0] must be str op one of (\'o\', \'r\')'
        assert isinstance(name, DataWrapperProtocol), \
            'state_update.data[1] must be DataWrapperProtocol name'
        assert type(writer) is int, \
            'state_update.data[2] must be int writer id'
        assert isinstance(value, DataWrapperProtocol), \
            'state_update.data[3] must be DataWrapperProtocol value'

        ts = state_update.ts

        if op == 'o':
            # try to add to the names ORSet
            self.names.update(StateUpdate(self.clock.uuid, ts, ('o', name)))

            # if register missing and name added successfully, create register
            if name not in self.registers and name in self.names.read():
                self.registers[name] = LWWRegister(name, value, self.clock, ts, writer)

        if op == 'r':
            # try to remove from the names ORSet
            self.names.update(StateUpdate(self.clock.uuid, ts, ('r', name)))

        # if the register exists, update it
        if name in self.registers:
            self.registers[name].update(StateUpdate(self.clock.uuid, ts, (writer, value)))

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        names_checksums = self.names.checksums()
        total_last_update = 0
        total_last_writer = 0
        total_register_crc32 = 0

        for name in self.names.read():
            total_register_crc32 += crc32(self.registers[name].pack())
            total_last_update += self.registers[name].last_update
            total_last_writer += self.registers[name].last_writer

        return (
            total_last_update % 2**32,
            total_last_writer % 2**32,
            total_register_crc32 % 2**32,
            *names_checksums
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        registers_history = {}
        orset_history = self.names.history()
        history = []

        for name in self.registers:
            registers_history[name] = self.registers[name].history()

        for update in orset_history:
            name = update.data[1]
            if name in registers_history:
                register_update = registers_history[name][0]
                history.append(StateUpdate(
                    update.clock_uuid,
                    register_update.ts,
                    (update.data[0], name, register_update.data[0], register_update.data[1])
                ))

        return tuple(history)

    def extend(self, name: DataWrapperProtocol, value: DataWrapperProtocol,
                writer: int) -> StateUpdate:
        """Extends the dict with name: value. Returns a StateUpdate."""
        assert isinstance(name, DataWrapperProtocol), \
            'name must be a DataWrapperProtocol'
        assert isinstance(value, DataWrapperProtocol) or value is None, \
            'value must be a DataWrapperProtocol or None'
        assert type(writer) is int, 'writer must be an int'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            ('o', name, writer, value)
        )
        self.update(state_update)

        return state_update

    def unset(self, name: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Removes the key name from the dict. Returns a StateUpdate."""
        assert isinstance(name, DataWrapperProtocol), \
            'name must be a DataWrapperProtocol'
        assert type(writer) is int, 'writer must be an int'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            ('r', name, writer, NoneWrapper())
        )
        self.update(state_update)

        return state_update


class FIArray:
    """Implements a fractionally-indexed array CRDT."""
    positions: LWWMap
    clock: ClockProtocol
    cache_full: list[DataWrapperProtocol]
    cache: list[Any]

    def __init__(self, positions: LWWMap = None, clock: ClockProtocol = None) -> None:
        """Initialize an FIArray from an LWWMap of item positions and a
            shared clock.
        """
        assert type(positions) is LWWMap or positions is None, \
            'positions must be an LWWMap or None'
        assert isinstance(clock, ClockProtocol) or clock is None, \
            'clock must be a ClockProtocol or None'

        clock = ScalarClock() if clock is None else clock
        positions = LWWMap(clock=clock) if positions is None else positions

        self.positions = positions
        self.clock = clock
        self.cache_full = None
        self.cache = None

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return self.positions.pack()

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> FIArray:
        """Unpack the data bytes string into an instance."""
        positions = LWWMap.unpack(data, inject)
        return cls(positions=positions, clock=positions.clock)

    def read(self) -> tuple[Any]:
        """Return the eventually consistent data view. Cannot be used for
            preparing deletion updates.
        """
        if self.cache is None:
            if self.cache_full is None:
                self.calculate_cache()
            self.cache = [item.value for item in self.cache_full]

        return tuple(self.cache)

    def read_full(self) -> tuple[DataWrapperProtocol]:
        """Return the full, eventually consistent list of items without
            tombstones but with complete DataWrapperProtocols rather than
            the underlying values. Use this for preparing deletion
            updates -- only a DataWrapperProtocol can be used for delete.
        """
        if self.cache_full is None:
            self.calculate_cache()

        return tuple(self.cache_full)

    def update(self, state_update: StateUpdateProtocol) -> FIArray:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple'
        assert state_update.data[0] in ('o', 'r'), \
            'state_update.data[0] must be in (\'o\', \'r\')'
        assert isinstance(state_update.data[1], DataWrapperProtocol), \
            'state_update.data[1] must be instance implementing DataWrapperProtocol'
        assert type(state_update.data[2]) is int, \
            'state_update.data[2] must be writer int'
        assert type(state_update.data[3]) in (DecimalWrapper, NoneWrapper), \
            'state_update.data[3] must be DecimalWrapper or NoneWrapper'

        self.positions.update(state_update)
        self.update_cache(state_update.data[1], state_update.data[0] == 'o')

        return self

    def checksums(self) -> tuple[int]:
        """Returns checksums for the underlying data to detect
            desynchronization due to network partition.
        """
        return self.positions.checksums()

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return self.positions.history()

    @classmethod
    def index_offset(cls, index: Decimal) -> Decimal:
        """Adds a small random offset."""
        assert type(index) is Decimal, 'index must be a Decimal'

        _, exponent = cls.least_significant_digit(index)
        exponent -= 1
        return index + Decimal(f'{randrange(1, 9)}E{exponent}')

    @classmethod
    def index_between(cls, first: Decimal, second: Decimal) -> Decimal:
        """Return an index between first and second with a random offset."""
        assert type(first) is Decimal, 'first must be a Decimal'
        assert type(second) is Decimal, 'second must be a Decimal'

        return cls.index_offset(Decimal(first + second)/Decimal(2))

    @staticmethod
    def least_significant_digit(number: Decimal) -> tuple[int, int]:
        """Returns the least significant digit and its place as an exponent
            of 10, e.g. 0.201 -> (1, -3).
        """
        num_string = str(number)
        first_exponent = None

        if 'E' in num_string:
            first_exponent = int(num_string.split('E')[1])

        if '.' in num_string:
            digit = int(num_string.split('.')[1][-1])
            exponent = -len(num_string.split('.')[1])
        else:
            exponent = len(num_string) - len(num_string.rstrip('0'))
            digit = int(num_string[-exponent-1])

        if first_exponent:
            exponent += first_exponent

        return (digit, exponent)

    def put(self, item: DataWrapperProtocol, writer: int,
        index: Decimal) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the item
            at the index.
        """
        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (
                'o',
                item,
                writer,
                DecimalWrapper(index)
            )
        )

        self.update(state_update)

        return state_update

    def put_between(self, item: DataWrapperProtocol, writer: int,
        first: DataWrapperProtocol, second: DataWrapperProtocol) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the item
            at an index between first and second.
        """
        assert first in self.read_full(), 'first must already be assigned a position'
        assert second in self.read_full(), 'second must already be assigned a position'

        first_index = self.positions.registers[first].value.value
        second_index = self.positions.registers[second].value.value
        index = self.index_between(first_index, second_index)

        return self.put(item, writer, index)

    def put_before(self, item: DataWrapperProtocol, writer: int,
        other: DataWrapperProtocol) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the item
            before the other item.
        """
        assert other in self.read_full(), 'other must already be assigned a position'

        before_index = self.positions.registers[other].value.value
        first_index = self.read_full().index(other)

        if first_index > 0:
            prior = self.read_full()[first_index-1]
            prior_index = self.positions.registers[prior].value.value
        else:
            prior_index = Decimal(0)

        index = self.index_between(before_index, prior_index)

        return self.put(item, writer, index)

    def put_after(self, item: DataWrapperProtocol, writer: int,
        other: DataWrapperProtocol) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the item
            after the other item.
        """
        assert other in self.read_full(), 'other must already be assigned a position'

        after_index = self.positions.registers[other].value.value
        first_index = self.read_full().index(other)

        if len(self.read_full()) > first_index+1:
            next = self.read_full()[first_index+1]
            next_index = self.positions.registers[next].value.value
        else:
            next_index = Decimal(1)

        index = self.index_between(after_index, next_index)

        return self.put(item, writer, index)

    def put_first(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the
            item at an index between 0 and the first item.
        """
        if len(self.read_full()) > 0:
            first = self.read_full()[0]
            first_index = self.positions.registers[first].value.value
            # average between 0 and first index
            index = Decimal(Decimal(0) + first_index)/Decimal(2)
        else:
            # average between 0 and 1
            index = Decimal('0.5')

        # add random offset
        index = self.index_offset(index)

        return self.put(item, writer, index)

    def put_last(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the
            item at an index between the last item and 1.
        """
        if len(self.read_full()) > 0:
            last = self.read_full()[-1]
            last_index = self.positions.registers[last].value.value
            # average between last index and 1
            index = Decimal(last_index + Decimal(1))/Decimal(2)
        else:
            # average between 0 and 1
            index = Decimal('0.5')

        # add random offset
        index = self.index_offset(index)

        return self.put(item, writer, index)

    def delete(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that deletes the
            item.
        """
        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (
                'r',
                item,
                writer,
                NoneWrapper()
            )
        )

        self.update(state_update)

        return state_update

    def calculate_cache(self) -> None:
        """Reads the items from the underlying LWWMap, orders them, then
            sets the cache_full list. Resets the cache.
        """
        # create list of all items
        positions = self.positions.read()
        items = [key for key in positions]
        # sort by (index, wrapper class name, wrapped value)
        items.sort(key=lambda item: (positions[item], item.__class__.__name__, item.value))

        # set instance values
        self.cache_full = items
        self.cache = None

    def update_cache(self, item: DataWrapperProtocol, visible: bool) -> None:
        """Updates the cache by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets the cache.
        """
        assert isinstance(item, DataWrapperProtocol), 'item must be DataWrapperProtocol'
        assert type(visible) is bool, 'visible must be bool'

        positions = self.positions.read()

        if self.cache_full is None:
            self.calculate_cache()

        if item in self.cache_full:
            self.cache_full.remove(item)

        if visible and item in positions:
            # find correct insertion index
            # sort by (index, wrapper class name, wrapped value)
            index = bisect(
                self.cache_full,
                (positions[item], item.__class__.__name__, item.value),
                key=lambda a: (positions[a], a.__class__.__name__, a.value)
            )
            self.cache_full.insert(index, item)

        self.cache = None


class CausalTree:
    """Implements a Causal Tree CRDT."""
    positions: LWWMap
    clock: ClockProtocol
    cache: list[CTDataWrapper]

    def __init__(self, positions: LWWMap = None, clock: ClockProtocol = None) -> None:
        """Initialize a CausalTree from an LWWMap of item positions and a
            shared clock.
        """
        assert type(positions) is LWWMap or positions is None, \
            'positions must be an LWWMap or None'
        assert isinstance(clock, ClockProtocol) or clock is None, \
            'clock must be a ClockProtocol or None'

        clock = ScalarClock() if clock is None else clock
        positions = LWWMap(clock=clock) if positions is None else positions

        self.positions = positions
        self.clock = clock
        self.cache_full = None
        self.cache = None

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return self.positions.pack()

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> CausalTree:
        """Unpack the data bytes string into an instance."""
        positions = LWWMap.unpack(data, inject)
        return cls(positions=positions, clock=positions.clock)

    def read(self) -> tuple[Any]:
        """Return the eventually consistent data view. Cannot be used for
            preparing deletion updates.
        """
        if self.cache is None:
            self.calculate_cache()

        return tuple([item.value.value for item in self.cache if item.visible])

    def read_full(self) -> tuple[CTDataWrapper]:
        """Return the full, eventually consistent list of items with
            tombstones and complete DataWrapperProtocols rather than the
            underlying values. Use this for preparing deletion updates --
            only a DataWrapperProtocol can be used for delete.
        """
        if self.cache is None:
            self.calculate_cache()

        return tuple(self.cache)

    def update(self, state_update: StateUpdateProtocol) -> CausalTree:
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple'
        assert state_update.data[0] in ('o', 'r'), \
            'state_update.data[0] must be in (\'o\', \'r\')'
        assert isinstance(state_update.data[1], DataWrapperProtocol), \
            'state_update.data[1] must be instance implementing DataWrapperProtocol'
        assert type(state_update.data[2]) is int, \
            'state_update.data[2] must be writer int'
        assert type(state_update.data[3]) is CTDataWrapper, \
            'state_update.data[3] must be CTDataWrapper'

        state_update.data[3].visible = state_update.data[0] == 'o'
        self.positions.update(state_update)
        self.update_cache(state_update.data[3])

    def checksums(self) -> tuple[int]:
        """Returns checksums for the underlying data to detect
            desynchronization due to network partition.
        """
        return self.positions.checksums()

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return self.positions.history()

    def put(self, item: DataWrapperProtocol, writer: int, uuid: bytes,
            parent: bytes = b'') -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the item
            at the index.
        """
        assert type(uuid) is bytes, "uuid must be bytes"
        assert type(parent) is bytes, "parent must be bytes"
        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (
                'o',
                BytesWrapper(uuid),
                writer,
                CTDataWrapper(item, uuid, parent)
            )
        )

        self.update(state_update)

        return state_update

    def put_after(self, item: DataWrapperProtocol, writer: int,
        parent: CTDataWrapper) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the item
            after the parent item.
        """
        assert parent in [item.value for item in self.read_full()], \
            'parent must already be assigned a position'

        uuid = uuid1().bytes
        parent = self.positions.registers[parent].value.uuid

        return self.put(item, writer, uuid, parent)

    def put_first(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that puts the
            item at an index between 0 and the first item.
        """
        return self.put(item, writer, uuid1().bytes, b'')

    def delete(self, ctdw: CTDataWrapper, writer: int) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that deletes the
            item specified by ctdw.
        """
        assert ctdw.value in self.positions.registers

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (
                'r',
                BytesWrapper(ctdw.uuid),
                writer,
                CTDataWrapper(NoneWrapper(), ctdw.uuid, ctdw.parent, False)
            )
        )

        self.update(state_update)

        return state_update

    def calculate_cache(self) -> None:
        """Reads the items from the underlying LWWMap, orders them, then
            sets the cache list.
        """
        # create list of all items
        positions = [
            self.positions.registers[register].value
            for register in self.positions.registers
        ]

        # create linked lists
        parsed: dict[bytes, CTDataWrapper] = {}
        for p in positions:
            if p.uuid not in parsed:
                parsed[p.uuid] = p
            if p.parent_uuid not in parsed:
                for r in positions:
                    if r.uuid == p.parent_uuid:
                        parsed[r.uuid] = r
                        break
            if p.parent_uuid in parsed:
                parsed[p.parent_uuid].add_child(p)
                p.set_parent(parsed[p.parent_uuid])

        # function for getting sorted list of children
        def get_children(parent_uuid: bytes) -> list[CTDataWrapper]:
            children = [v for _, v in parsed.items() if v.parent_uuid == parent_uuid]
            return sorted(children, key=lambda ctdw: ctdw.uuid)

        def get_list(parent_uuid: bytes) -> list[CTDataWrapper]:
            result = []
            children = get_children(parent_uuid)
            for child in children:
                result.append(child)
                child_list = get_list(child.uuid)
                result.extend(child_list)
            return result

        self.cache = get_list(b'')

    def update_cache(self, item: CTDataWrapper) -> None:
        """Updates the cache by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets the cache.
        """
        assert isinstance(item, CTDataWrapper), 'item must be CTDataWrapper'

        if BytesWrapper(item.uuid) not in self.positions.registers:
            return

        if self.cache is None:
            self.calculate_cache()

        if len(self.cache) == 0:
            self.cache.append(item)
            return

        def remove_children(ctdw: CTDataWrapper) -> list[CTDataWrapper]:
            if len(ctdw.children()) == 0:
                return []
            children = []
            for child in ctdw.children():
                children.append(child)
                self.cache.remove(child)
                children.extend(remove_children(child))
            return children

        for ctdw in self.cache:
            if ctdw.uuid != item.uuid:
                continue
            ctdw.visible = item.visible
            if ctdw.parent_uuid == item.parent_uuid:
                return
            self.cache.remove(ctdw)
            children = remove_children(ctdw)
            for child in children:
                self.update_cache(child)
            break

        def walk(item: CTDataWrapper) -> CTDataWrapper:
            if not len(item.children()) > 0:
                return item
            children = sorted(list(item.children()), key=lambda c: c.uuid)
            return walk(children[-1])

        for i in range(len(self.cache)):
            ctdw = self.cache[i]
            if ctdw.uuid == item.parent_uuid:
                item.set_parent(ctdw)
                ctdw.add_child(item)
                if len(ctdw.children()) > 0:
                    children = sorted(list(ctdw.children()), key=lambda c: c.uuid)
                    if children.index(item) > 0:
                        before = children[children.index(item)-1]
                        index = self.cache.index(walk(before))
                        self.cache.insert(index, item)
                    else:
                        self.cache.insert(i + 1, item)
                    return
                else:
                    self.cache.insert(i + 1, item)
                    return


class ValidCRDTs(Enum):
    gs = GSet
    ors = ORSet
    c = Counter
    pnc = PNCounter
    rga = RGArray
    lwwr = LWWRegister
    lwwm = LWWMap
    tombstone = NoneType


class CompositeCRDT:
    component_names: ORSet
    component_data: dict
    clock: ClockProtocol

    def __init__(self, component_names: ORSet = None,
                component_data: dict = None, clock: ClockProtocol = None
    ) -> None:
        """Initialize a CompositeCRDT from components and a shared clock."""
        assert isinstance(component_names, ORSet) or component_names is None, 'component_names must be an ORSet or None'
        assert type(component_data) is dict or component_data is None, 'component_data must be a dict or None'
        assert isinstance(clock, ClockProtocol) or clock is None, 'clock must be a ClockProtocol or None'

        component_names = component_names if isinstance(component_names, ORSet) else ORSet()
        component_data = component_data if type(component_data) is dict else {}
        clock = clock if isinstance(clock, ClockProtocol) else ScalarClock()

        component_names.clock = self.clock

        for name in component_data:
            assert isinstance(component_data[name], CRDTProtocol), 'each component must be a CRDT'
            assert name in component_names.observed or name in component_names.removed, \
                'each component name must be referenced in the ORSet'
            component_data[name].clock = clock

        self.component_names = component_names
        self.component_data = component_data
        self.clock = clock

    """Implements the Replicated Growable Array CRDT."""
    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        ...

    @classmethod
    def unpack(cls, data: bytes) -> CompositeCRDT:
        """Unpack the data bytes string into an instance."""
        ...

    def read(self):
        """Return the eventually consistent data view."""
        view = {}

        for name in self.component_names.read():
            view[name] = self.component_data[name].read()

        return view

    def update(self, state_update: StateUpdateProtocol) -> CompositeCRDT:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert len(state_update.data) == 4, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[0]) is str, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[1]) is str, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[2]) is str, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[3]) is StateUpdate or state_update.data[3] is None, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert state_update.data[0] in ('o', 'r'), \
            'state_update.data[0] must be one of (\'o\', \'r\')'
        assert state_update.data[1] in ValidCRDTs.__members__, \
            'state_update.data[1] must name a member of ValidCRDTs enum'

        # parse data
        ts = state_update.ts
        op, crdt_type_name, name, state_update = state_update.data
        crdt_type = ValidCRDTs[crdt_type_name].value

        # observe a component
        if op == 'o':
            # observe the new component
            if name not in self.component_names.observed or name in self.component_names.removed:
                self.component_names.update(StateUpdate(self.clock.uuid, ts, ('o', name)))

            # create an empty instance of the crdt
            if name not in self.component_data:
                crdt = crdt_type()
                crdt.clock = self.clock
                self.component_data[name] = crdt

            # apply the update
            if state_update is not None:
                self.component_data[name].update(state_update)

        # remove a component
        if op == 'r':
            # remove the component
            if name not in self.component_names.removed or name in self.component_names.observed:
                self.component_names.update(StateUpdate(self.clock.uuid, ts, ('r', name)))

            if state_update is not None:
                # create an empty instance of the crdt
                if name not in self.component_data:
                    crdt = crdt_type()
                    crdt.clock = self.clock
                    self.component_data[name] = crdt

                # apply the update
                self.component_data[name].update(state_update)

        return self

    def checksums(self) -> tuple[tuple[str, tuple]]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        checksums = []

        checksums.append(('component_names', self.component_names.checksums()))

        for name in self.component_names.read():
            checksums.append((name, self.component_data[name].checksums()))

        return tuple(checksums)

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        updates = []

        # compile concise list of updates for each component
        for name in self.component_names.read():
            history = self.component_data[name].history()
            classname = ValidCRDTs(self.component_data[name].__class__).name

            for event in history:
                updates.append(StateUpdate(
                    self.clock.uuid,
                    event.ts,
                    ('o', classname, name, event.data)
                ))

        # compile concise list of updates for each tombstone
        for name in self.component_names.removed:
            ts = self.component_names.removed_metadata[name]
            if name in self.component_data:
                classname = ValidCRDTs(self.component_data[name].__class__).name
            else:
                classname = ValidCRDTs.tombstone.name

            updates.append(StateUpdate(
                self.clock.uuid,
                ts,
                ('r', classname, name, None)
            ))

        return tuple(updates)
