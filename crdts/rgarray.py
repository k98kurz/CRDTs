from __future__ import annotations
from bisect import bisect
from types import NoneType
from typing import Any
from crdts.datawrappers import RGATupleWrapper
from crdts.interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from crdts.orset import ORSet
from crdts.stateupdate import StateUpdate


class RGArray:
    """Implements the Replicated Growable Array CRDT. This uses the ORSet
        to handle CRDT logic and provides a logical view over top of it.
    """
    items: ORSet
    clock: ClockProtocol
    cache_full: list[RGATupleWrapper]
    cache: tuple[Any]

    def __init__(self, items: ORSet = None, clock: ClockProtocol = None) -> None:
        """Initialize an RGA from an ORSet of items and a shared clock."""
        assert type(items) in (ORSet, NoneType), \
            'items must be ORSet or None'
        assert isinstance(clock, ClockProtocol) or clock is None, \
            'clock must be a ClockProtocol or None'

        items = ORSet() if items is None else items
        clock = items.clock if clock is None else clock
        items.clock = clock

        self.items = items
        self.clock = clock

        self.calculate_cache()

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return self.items.pack()

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> RGArray:
        """Unpack the data bytes string into an instance."""
        items = ORSet.unpack(data, inject)
        return cls(items=items, clock=items.clock)

    def read(self) -> tuple[Any]:
        """Return the eventually consistent data view. Cannot be used for
            preparing deletion updates.
        """
        if self.cache_full is None:
            self.calculate_cache()

        if self.cache is None:
            self.cache = tuple([item.value[0].value for item in self.cache_full])

        return self.cache

    def read_full(self) -> tuple[RGATupleWrapper]:
        """Return the full, eventually consistent list of items without
            tombstones but with complete RGATupleWrappers rather than the
            underlying values. Use this for preparing deletion updates --
            only a RGATupleWrapper can be used for delete.
        """
        if self.cache_full is None:
            self.calculate_cache()

        return tuple(self.cache_full)

    def update(self, state_update: StateUpdateProtocol) -> RGArray:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'

        assert isinstance(state_update.data[1], RGATupleWrapper), 'item must be RGATupleWrapper'

        self.items.update(state_update)
        self.update_cache(state_update.data[1], state_update.data[1] in self.items.read())

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return self.items.checksums()

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return self.items.history()

    def append(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that appends the
            item.
        """
        assert isinstance(item, DataWrapperProtocol), 'item must be DataWrapperProtocol'
        assert type(writer) is int, 'writer must be int'

        ts = self.clock.wrap_ts(self.clock.read())
        state_update = self.items.observe(RGATupleWrapper((item, (ts, writer))))

        self.update(state_update)

        return state_update

    def delete(self, item: RGATupleWrapper) -> StateUpdate:
        """Creates, applies, and returns a StateUpdate that deletes the
            specified item.
        """
        assert isinstance(item, RGATupleWrapper), 'item must be RGATupleWrapper'

        state_update = self.items.remove(item)

        self.update(state_update)

        return state_update

    def calculate_cache(self) -> None:
        """Reads the items from the underlying ORSet, orders them, then
            sets the cache_full list. Resets the cache.
        """
        # create sorted list of all items
        # sorted by ((timestamp, writer), wrapper class name, wrapped value)
        items = list(self.items.observed)
        items.sort(key=lambda item: (item.value[1], item.value[0].__class__.__name__, item.value[0].value))

        # set instance values
        self.cache_full = items
        self.cache = None

    def update_cache(self, item: RGATupleWrapper, visible: bool) -> None:
        """Updates the cache by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets the cache.
        """
        assert isinstance(item, RGATupleWrapper), 'item must be RGATupleWrapper'
        assert type(visible) is bool, 'visible must be bool'

        if self.cache_full is None:
            self.calculate_cache()

        if visible:
            if item not in self.cache_full:
                # find correct insertion index
                # sorted by ((timestamp, writer), wrapper class name, wrapped value)
                index = bisect(
                    self.cache_full,
                    (item.value[1], item.value[0].__class__.__name__, item.value[0].value),
                    key=lambda a: (a.value[1], a.value[0].__class__.__name__, a.value[0].value)
                )
                self.cache_full.insert(index, item)
        else:
            if item in self.cache_full:
                # remove the item
                self.cache_full.remove(item)

        self.cache = None
