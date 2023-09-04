from __future__ import annotations
from .datawrappers import DecimalWrapper, NoneWrapper
from .errors import tressa
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .lwwmap import LWWMap
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from bisect import bisect
from decimal import Decimal
from random import randrange
from typing import Any


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
        tressa(type(positions) is LWWMap or positions is None,
            'positions must be an LWWMap or None')
        tressa(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')

        clock = ScalarClock() if clock is None else clock
        positions = LWWMap(clock=clock) if positions is None else positions
        positions.clock = clock
        for name in positions.registers:
            positions.registers[name].clock = clock

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
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple')
        tressa(state_update.data[0] in ('o', 'r'),
            'state_update.data[0] must be in (\'o\', \'r\')')
        tressa(isinstance(state_update.data[1], DataWrapperProtocol),
            'state_update.data[1] must be instance implementing DataWrapperProtocol')
        tressa(type(state_update.data[2]) is int,
            'state_update.data[2] must be writer int')
        tressa(type(state_update.data[3]) in (DecimalWrapper, NoneWrapper),
            'state_update.data[3] must be DecimalWrapper or NoneWrapper')

        self.positions.update(state_update)
        self.update_cache(state_update.data[1], state_update.data[0] == 'o')

        return self

    def checksums(self) -> tuple[int]:
        """Returns checksums for the underlying data to detect
            desynchronization due to network partition.
        """
        return self.positions.checksums()

    def history(self, update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return self.positions.history(update_class)

    @classmethod
    def index_between(cls, first: Decimal, second: Decimal) -> Decimal:
        """Return an index between first and second with a random offset."""
        tressa(type(first) is Decimal, 'first must be a Decimal')
        tressa(type(second) is Decimal, 'second must be a Decimal')

        return Decimal(first + second)/Decimal(2)

    def put(self, item: DataWrapperProtocol, writer: int,
            index: Decimal, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at the index.
        """
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'o',
                item,
                writer,
                DecimalWrapper(index)
            )
        )

        self.update(state_update)

        return state_update

    def put_between(self, item: DataWrapperProtocol, writer: int,
                    first: DataWrapperProtocol, second: DataWrapperProtocol,
                    update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at an index between first and
            second.
        """
        tressa(first in self.read_full(), 'first must already be assigned a position')
        tressa(second in self.read_full(), 'second must already be assigned a position')

        first_index = self.positions.registers[first].value.value
        second_index = self.positions.registers[second].value.value
        index = self.index_between(first_index, second_index)

        return self.put(item, writer, index, update_class)

    def put_before(self, item: DataWrapperProtocol, writer: int,
                   other: DataWrapperProtocol,
                   update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item before the other item.
        """
        tressa(other in self.read_full(), 'other must already be assigned a position')

        before_index = self.positions.registers[other].value.value
        first_index = self.read_full().index(other)

        if first_index > 0:
            prior = self.read_full()[first_index-1]
            prior_index = self.positions.registers[prior].value.value
        else:
            prior_index = Decimal(0)

        index = self.index_between(before_index, prior_index)

        return self.put(item, writer, index, update_class)

    def put_after(self, item: DataWrapperProtocol, writer: int,
                  other: DataWrapperProtocol,
                  update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item after the other item.
        """
        tressa(other in self.read_full(), 'other must already be assigned a position')

        after_index = self.positions.registers[other].value.value
        first_index = self.read_full().index(other)

        if len(self.read_full()) > first_index+1:
            next = self.read_full()[first_index+1]
            next_index = self.positions.registers[next].value.value
        else:
            next_index = Decimal(1)

        index = self.index_between(after_index, next_index)

        return self.put(item, writer, index, update_class)

    def put_first(self, item: DataWrapperProtocol, writer: int, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at an index between 0 and the
            first item.
        """
        if len(self.read_full()) > 0:
            first = self.read_full()[0]
            first_index = self.positions.registers[first].value.value
            # average between 0 and first index
            index = Decimal(Decimal(0) + first_index)/Decimal(2)
        else:
            # average between 0 and 1
            index = Decimal('0.5')

        return self.put(item, writer, index, update_class)

    def put_last(self, item: DataWrapperProtocol, writer: int,
                 update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at an index between the last
            item and 1.
        """
        if len(self.read_full()) > 0:
            last = self.read_full()[-1]
            last_index = self.positions.registers[last].value.value
            # average between last index and 1
            index = Decimal(last_index + Decimal(1))/Decimal(2)
        else:
            # average between 0 and 1
            index = Decimal('0.5')

        return self.put(item, writer, index, update_class)

    def delete(self, item: DataWrapperProtocol, writer: int,
               update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that deletes the item.
        """
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
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
        tressa(isinstance(item, DataWrapperProtocol), 'item must be DataWrapperProtocol')
        tressa(type(visible) is bool, 'visible must be bool')

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
