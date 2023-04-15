from __future__ import annotations
from binascii import crc32
from dataclasses import dataclass, field
from crdts.interfaces import (
    ClockProtocol, CRDTProtocol, DataWrapperProtocol, StateUpdateProtocol
)
from enum import Enum
import json
import struct
from types import NoneType
from typing import Any, Hashable, Optional
from uuid import uuid1


@dataclass
class NoneWrapper:
    """Implementation of DataWrapperProtocol for use in removing
        registers from the LWWMap by setting them to a None value.
    """
    value: NoneType = field(default=None)

    def __hash__(self) -> int:
        return hash(None)

    def __eq__(self, other) -> bool:
        return type(self) == type(other)

    def pack(self) -> bytes:
        return b''

    @classmethod
    def unpack(cls, data: bytes) -> NoneWrapper:
        return cls()


@dataclass
class StateUpdate:
    clock_uuid: bytes
    ts: Any
    data: Hashable


@dataclass
class ScalarClock:
    """Implements a Lamport logical scalar clock."""
    counter: int = field(default=0)
    uuid: bytes = field(default_factory=lambda: uuid1().bytes)

    def read(self) -> int:
        """Return the current timestamp."""
        return self.counter

    def update(self, data: int) -> int:
        """Update the clock and return the current time stamp."""
        assert type(data) is int, 'data must be int'

        if data >= self.counter:
            self.counter = data + 1

        return self.counter

    @staticmethod
    def is_later(ts1: int, ts2: int) -> bool:
        """Return True iff ts1 > ts2."""
        assert type(ts1) is int, 'ts1 must be int'
        assert type(ts2) is int, 'ts2 must be int'

        if ts1 > ts2:
            return True
        return False

    @staticmethod
    def are_concurrent(ts1: int, ts2: int) -> bool:
        """Return True if not ts1 > ts2 and not ts2 > ts1."""
        assert type(ts1) is int, 'ts1 must be int'
        assert type(ts2) is int, 'ts2 must be int'

        return not (ts1 > ts2) and not (ts2 > ts1)

    @staticmethod
    def compare(ts1: int, ts2: int) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable.
        """
        assert type(ts1) is int, 'ts1 must be int'
        assert type(ts2) is int, 'ts2 must be int'

        if ts1 > ts2:
            return 1
        elif ts2 > ts1:
            return -1
        return 0

    def pack(self) -> bytes:
        """Packs the clock into bytes."""
        return struct.pack(
            f'!I{len(self.uuid)}s',
            self.counter,
            self.uuid
        )

    @classmethod
    def unpack(cls, data: bytes) -> ScalarClock:
        """Unpacks a clock from bytes."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) >= 5, 'data must be at least 5 bytes'

        return cls(*struct.unpack(
            f'!I{len(data)-4}s',
            data
        ))


@dataclass
class GSet:
    """Implements the Grow-only Set (GSet) CRDT."""
    members: set = field(default_factory=set)
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = self.clock.pack()
        members = bytes(json.dumps(list(self.members), separators=(',', ':')), 'utf-8')
        clock_size, set_size = len(clock), len(members)

        return struct.pack(
            f'!ii{clock_size}s{set_size}s',
            clock_size,
            set_size,
            clock,
            members
        )

    @classmethod
    def unpack(cls, data: bytes) -> GSet:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 8, 'data must be more than 8 bytes'

        clock_size, set_size, _ = struct.unpack(
            f'!II{len(data)-8}s',
            data
        )
        _, _, clock_bytes, set_bytes = struct.unpack(
            f'!II{clock_size}s{set_size}s',
            data
        )

        clock = ScalarClock.unpack(clock_bytes)
        members = set(json.loads(str(set_bytes, 'utf-8')))

        return cls(members=members, clock=clock)

    def read(self) -> set:
        """Return the eventually consistent data view."""
        return self.members.copy()

    def update(self, state_update: StateUpdateProtocol) -> GSet:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'

        if state_update.data not in self.members:
            self.members.add(state_update.data)

        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        total_crc32 = 0
        for member in self.members:
            total_crc32 += crc32(bytes(json.dumps(member), 'utf-8'))

        return (
            self.clock.read(),
            len(self.members),
            total_crc32 % 2**32,
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        updates = []

        for member in self.members:
            updates.append(StateUpdate(self.clock.uuid, self.clock.read()-1, member))

        return tuple(updates)

    def add(self, member: Hashable) -> StateUpdate:
        """Create, apply, and return a StateUpdate adding member to the set."""
        assert type(hash(member)) is int, 'member must be hashable'

        ts = self.clock.read()
        state_update = StateUpdate(self.clock.uuid, ts, member)
        self.update(state_update)

        return state_update


@dataclass
class Counter:
    """Implements the Counter CRDT."""
    counter: int = field(default=0)
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = self.clock.pack()
        clock_size = len(clock)

        return struct.pack(
            f'!I{clock_size}sI',
            clock_size,
            clock,
            self.counter
        )

    @classmethod
    def unpack(cls, data: bytes) -> Counter:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 8, 'data must be more than 8 bytes'

        clock_size, _ = struct.unpack(f'!I{len(data)-4}s', data)
        _, clock_bytes, counter = struct.unpack(f'!I{clock_size}sI', data)
        clock = ScalarClock.unpack(clock_bytes)

        return cls(counter=counter, clock=clock)

    def read(self) -> int:
        """Return the eventually consistent data view."""
        return self.counter

    def update(self, state_update: StateUpdateProtocol) -> Counter:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is int, 'state_update.data must be an int'

        self.counter = max([self.counter, state_update.data])
        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.counter,
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return (StateUpdate(self.clock.uuid, self.clock.read()-1, self.counter),)

    def increase(self, amount: int = 1) -> StateUpdate:
        """Increase the counter by the given amount (default 1). Returns
            the StateUpdate that should be propagated to the network.
        """
        assert type(amount) is int, 'amount must be int'
        assert amount > 0, 'amount must be positive'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            self.counter + amount
        )
        self.update(state_update)

        return state_update


@dataclass
class ORSet:
    """Implements the Observed Removed Set (ORSet) CRDT. Comprised of
        two Sets with a read method that removes the removed set members
        from the observed set. Add-biased. Note that int members are
        converted to str for json compatibility.
    """
    observed: set = field(default_factory=set)
    observed_metadata: dict = field(default_factory=dict)
    removed: set = field(default_factory=set)
    removed_metadata: dict = field(default_factory=dict)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    cache: Optional[tuple] = field(default=None)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock_bytes = self.clock.pack()
        clock_size = len(clock_bytes)

        data = bytes(json.dumps(
            {
                'o': self.observed_metadata,
                'r': self.removed_metadata
            },
            separators=(',', ':'),
            sort_keys=True
        ), 'utf-8')

        return struct.pack(
            f'!I{clock_size}s{len(data)}s',
            clock_size,
            clock_bytes,
            data
        )

    @classmethod
    def unpack(cls, data: bytes) -> ORSet:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 19, 'data must be more than 19 bytes'

        clock_size, _ = struct.unpack(f'!I{len(data)-4}s', data)
        _, clock, sets = struct.unpack(
            f'!I{clock_size}s{len(data)-4-clock_size}s',
            data
        )
        clock = ScalarClock.unpack(clock)
        sets = json.loads(str(sets, 'utf-8'))
        observed_metadata = sets['o']
        observed = set(observed_metadata.keys())
        removed_metadata = sets['r']
        removed = set(removed_metadata.keys())

        return cls(observed, observed_metadata, removed, removed_metadata, clock)

    def read(self) -> set:
        """Return the eventually consistent data view."""
        if self.cache is not None:
            if self.cache[0] == self.clock.read():
                return self.cache[1]

        difference = self.observed.difference(self.removed)
        self.cache = (self.clock.read(), difference)

        return difference

    def update(self, state_update: StateUpdateProtocol) -> ORSet:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple'
        assert len(state_update.data) == 2, \
            'state_update.data must be 2 long'
        assert state_update.data[0] in ('o', 'r'), \
            'state_update.data[0] must be in (\'o\', \'r\')'
        assert type(hash(state_update.data[1])) is int, \
            'state_update.data[1] must be hashable'

        op, member = state_update.data
        member = member.hex() if type(member) is bytes else member
        ts = state_update.ts

        if op == 'o':
            # add to observed
            if member not in self.removed or (
                member in self.removed_metadata and
                not self.clock.is_later(self.removed_metadata[member], ts)
            ):
                self.observed.add(member)
                oldts = self.observed_metadata[member] if member in self.observed_metadata else -1
                if self.clock.is_later(ts, oldts):
                    self.observed_metadata[member] = ts

            # remove from removed
            if member in self.removed and (
                member in self.removed_metadata and
                not self.clock.is_later(self.removed_metadata[member], ts)
            ):
                self.removed.remove(member)
                del self.removed_metadata[member]

        if op == 'r':
            # add to removed
            if member not in self.observed or (
                member in self.observed_metadata and
                self.clock.is_later(ts, self.observed_metadata[member])
            ):
                self.removed.add(member)
                oldts = self.removed_metadata[member] if member in self.removed_metadata else -1
                if self.clock.is_later(ts, oldts):
                    self.removed_metadata[member] = ts

            # remove from observed
            if member in self.observed and (
                member in self.observed_metadata and
                self.clock.is_later(ts, self.observed_metadata[member])
            ):
                self.observed.remove(member)
                del self.observed_metadata[member]

        self.clock.update(ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        total_observed_crc32 = 0
        for o in self.observed:
            if type(o) is str:
                total_observed_crc32 += crc32(bytes(o, 'utf-8'))
            else:
                total_observed_crc32 += crc32(bytes(str(o), 'utf-8'))

        total_removed_crc32 = 0
        for r in self.removed:
            if type(r) is str:
                total_removed_crc32 += crc32(bytes(r, 'utf-8'))
            else:
                total_removed_crc32 += crc32(bytes(str(r), 'utf-8'))

        return (
            len(self.observed),
            len(self.removed),
            total_observed_crc32 % 2**32,
            total_removed_crc32 % 2**32,
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        updates = []

        for o in self.observed:
            updates.append(
                StateUpdate(
                    self.clock.uuid,
                    self.observed_metadata[o],
                    ('o', o)
                )
            )

        for r in self.removed:
            updates.append(
                StateUpdate(
                    self.clock.uuid,
                    self.removed_metadata[r],
                    ('r', r)
                )
            )

        return tuple(updates)

    def observe(self, member: Hashable) -> StateUpdate:
        """Adds the given member to the observed set."""
        assert type(hash(member)) is int, 'member must be Hashable'

        member = str(member) if type(member) is int else member
        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            ('o', member)
        )

        self.update(state_update)

        return state_update

    def remove(self, member: Hashable) -> StateUpdate:
        """Adds the given member to the removed set."""
        assert type(hash(member)) is int, 'member must be Hashable'

        member = str(member) if type(member) is int else member
        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            ('r', member)
        )

        self.update(state_update)

        return state_update


@dataclass
class PNCounter:
    """Implements the Positive Negative Counter (PNCounter) CRDT.
        Comprised of two Counter CRDTs with a read method that subtracts
        the negative counter from the positive counter.
    """
    positive: int = field(default=0)
    negative: int = field(default=0)
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = self.clock.pack()
        clock_size = len(clock)

        return struct.pack(
            f'!I{clock_size}sII',
            clock_size,
            clock,
            self.positive,
            self.negative,
        )

    @classmethod
    def unpack(cls, data: bytes) -> PNCounter:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 20, 'data must be more than 20 bytes'

        clock_size, _ = struct.unpack(f'!I{len(data)-4}s', data)
        _, clock, positive, negative = struct.unpack(
            f'!I{clock_size}sII',
            data
        )
        clock = ScalarClock.unpack(clock)

        return cls(positive, negative, clock)

    def read(self) -> int:
        """Return the eventually consistent data view."""
        return self.positive - self.negative

    def update(self, state_update: StateUpdateProtocol) -> PNCounter:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple of 2 ints'
        assert len(state_update.data) == 2, \
            'state_update.data must be tuple of 2 ints'
        assert type(state_update.data[0]) is int, \
            'state_update.data must be tuple of 2 ints'
        assert type(state_update.data[1]) is int, \
            'state_update.data must be tuple of 2 ints'

        self.positive = max([self.positive, state_update.data[0]])
        self.negative = max([self.negative, state_update.data[1]])
        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.clock.read(),
            self.positive,
            self.negative,
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return (StateUpdate(self.clock.uuid, self.clock.read()-1, (self.positive, self.negative)),)

    def increase(self, amount: int = 1) -> StateUpdate:
        """Increase the counter by the given amount (default 1). Returns
            the StateUpdate that should be propagated to the network.
        """
        assert type(amount) is int, 'amount must be int'
        assert amount > 0, 'amount must be positive'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (self.positive + amount, self.negative)
        )
        self.update(state_update)

        return state_update

    def decrease(self, amount: int = 1) -> StateUpdate:
        """Decrease the counter by the given amount (default 1). Returns
            the StateUpdate that should be propagated to the network.
        """
        assert type(amount) is int, 'amount must be int'
        assert amount > 0, 'amount must be positive'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (self.positive, self.negative + amount)
        )
        self.update(state_update)

        return state_update


@dataclass
class FIArray:
    """Implements a fractionally-indexed array CRDT."""
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        ...

    @classmethod
    def unpack(cls, data: bytes) -> RGArray:
        """Unpack the data bytes string into an instance."""
        ...

    def read(self):
        """Return the eventually consistent data view."""
        ...

    def update(self, state_update: StateUpdateProtocol) -> RGArray:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        ...

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        ...

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        ...

    def insert(self, index, item) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that inserts the
            item at the index.
        """
        ...

    def delete(self, index) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that deletes the
            specified item.
        """
        ...

    def move(self, item, index) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that moves the
            specified item to the new index.
        """
        ...


@dataclass
class RGArray:
    """Implements the Replicated Growable Array CRDT."""
    items: list[tuple[bytes, DataWrapperProtocol, bool]] = field(default_factory=list)
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        ...

    @classmethod
    def unpack(cls, data: bytes) -> RGArray:
        """Unpack the data bytes string into an instance."""
        ...

    def read(self):
        """Return the eventually consistent data view."""
        ...

    def update(self, state_update: StateUpdateProtocol) -> RGArray:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        ...

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        ...

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        ...

    def insert(self, index, item) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that inserts the
            item at the index.
        """
        ...

    def delete(self, index) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that deletes the
            specified item.
        """
        ...


@dataclass
class LWWRegister:
    """Implements the Last Writer Wins Register CRDT."""
    name: str
    value: DataWrapperProtocol = field(default_factory=NoneWrapper)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    last_update: int = field(default=0)
    last_writer: int = field(default=0)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        name = bytes(self.name, 'utf-8')
        name_size = len(name)
        clock = self.clock.pack()
        clock_size = len(clock)
        value_type = bytes(self.value.__class__.__name__, 'utf-8')
        value_type_size = len(value_type)
        value = self.value.pack()
        value_size = len(value)

        return struct.pack(
            f'!IIIIII{name_size}s{clock_size}s{value_type_size}s{value_size}s',
            self.last_update,
            self.last_writer,
            name_size,
            clock_size,
            value_type_size,
            value_size,
            name,
            clock,
            value_type,
            value
        )

    @classmethod
    def unpack(cls, data: bytes) -> LWWRegister:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 26, 'data must be at least 26 bytes'

        # parse
        last_update, last_writer, name_size, clock_size, value_type_size, value_size, _ = struct.unpack(
            f'!IIIIII{len(data)-24}s',
            data
        )
        _, _, _, _, _, _, name, clock, value_type, value = struct.unpack(
            f'!IIIIII{name_size}s{clock_size}s{value_type_size}s{value_size}s',
            data
        )
        name = str(name, 'utf-8')
        clock = ScalarClock.unpack(clock)
        value_type = str(value_type, 'utf-8')

        # more conditions and parsing
        assert value_type in globals(), 'value_type must be resolvable from globals'
        value = globals()[value_type].unpack(value)
        assert isinstance(value, DataWrapperProtocol), \
            'value_type must implement DataWrapperProtocol'

        return cls(name, value, clock, last_update, last_writer)

    def read(self) -> DataWrapperProtocol:
        """Return the eventually consistent data view."""
        return self.value.__class__.unpack(self.value.pack())

    def update(self, state_update: StateUpdateProtocol) -> LWWRegister:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple of (int, DataWrapperProtocol)'
        assert len(state_update.data) == 2, \
            'state_update.data must be tuple of (int, DataWrapperProtocol)'
        assert type(state_update.data[0]) is int, \
            'state_update.data[0] must be int writer_id'
        assert isinstance(state_update.data[1], DataWrapperProtocol), \
            'state_update.data[1] must be DataWrapperProtocol'

        # set the value if the update happens after current state
        if self.clock.is_later(state_update.ts, self.last_update):
            self.last_update = state_update.ts
            self.last_writer = state_update.data[0]
            self.value = state_update.data[1]

        # use writer int as tie breaker for concurrent updates
        if (self.clock.are_concurrent(state_update.ts, self.last_update)
                and state_update.data[0] > self.last_writer):
            self.last_writer = state_update.data[0]
            self.value = state_update.data[1]

        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.last_update,
            self.last_writer,
            crc32(self.value.pack()),
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return (StateUpdate(
            self.clock.uuid,
            self.last_update,
            (self.last_writer, self.value)
        ),)

    def write(self, value: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Writes the new value to the register and returns a
            StateUpdate. Requires a writer int for tie breaking.
        """
        assert isinstance(value, DataWrapperProtocol) or value is None, \
            'value must be a DataWrapperProtocol or None'
        assert type(writer) is int, 'writer must be an int'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (writer, value)
        )
        self.update(state_update)

        return state_update


class LWWMap:
    """Implements the Last Writer Wins Map CRDT.
        https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-l-w-w-map/index.html
    """
    names: ORSet
    registers: dict[DataWrapperProtocol, LWWRegister]
    clock: ClockProtocol

    def __init__(self, names: ORSet = None, registers: list = None,
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
        clock = self.clock.pack()
        names = self.names.pack()
        registers = {}

        for name in self.names.read():
            name_class = name.__name__
            key = name_class + '_' + name.pack().hex()
            value_class = self.registers[name].__name__
            registers[key] = value_class + '_' + self.registers[name].pack().hex()

        registers = json.dumps(registers, separators=(',', ':'), sort_keys=True)
        registers = bytes(registers, 'utf-8')

        clock_size = len(clock)
        names_size = len(names)
        registers_size = len(registers)

        return struct.pack(
            f'!III{clock_size}s{names_size}s{registers_size}s',
            clock,
            names,
            registers
        )

    @classmethod
    def unpack(cls, data: bytes) -> LWWMap:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 13, 'data must be at least 13 bytes'

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
        clock = ScalarClock.unpack(clock)
        names = ORSet.unpack(names)

        # parse the registers
        registers_raw = json.loads(str(registers_raw, 'utf-8'))
        registers = {}

        for key in registers_raw:
            # resolve key to name
            name_class, name = key.split('_')
            name = globals()[name_class].unpack(bytes.fromhex(name))

            # resolve value
            value_class, value = registers_raw[key].split('_')
            value = globals()[value_class].unpack(bytes.fromhex(value))

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
        assert type(state_update.data[0]) is str and state_update.data[0] in ('o', 'r'), \
            'state_update.data[0] must be str op one of (\'o\', \'r\')'
        assert isinstance(state_update.data[1], DataWrapperProtocol), \
            'state_update.data[1] must be DataWrapperProtocol name'
        assert type(state_update.data[2]) is int, \
            'state_update.data[2] must be int writer id'
        assert isinstance(state_update.data[3], DataWrapperProtocol), \
            'state_update.data[3] must be DataWrapperProtocol value'

        ts = state_update.ts
        op, name, writer, value = state_update.data

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
        assert isinstance(name, DataWrapperProtocol) or name is None, \
            'name must be a DataWrapperProtocol or None'
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
        assert isinstance(name, DataWrapperProtocol) or name is None, \
            'name must be a DataWrapperProtocol or None'
        assert type(writer) is int, 'writer must be an int'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            ('r', name, writer, NoneWrapper())
        )
        self.update(state_update)

        return state_update


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
