from __future__ import annotations
from .datawrappers import RGAItemWrapper
from .errors import tressa
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .orset import ORSet
from .stateupdate import StateUpdate
from bisect import bisect
from types import NoneType
from typing import Any


SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType

class RGArray:
    """Implements the Replicated Growable Array CRDT. This uses the ORSet
        to handle CRDT logic and provides a logical view over top of it.
    """
    items: ORSet
    clock: ClockProtocol
    cache_full: list[RGAItemWrapper]
    cache: tuple[Any]

    def __init__(self, items: ORSet = None, clock: ClockProtocol = None) -> None:
        """Initialize an RGA from an ORSet of items and a shared clock."""
        tressa(type(items) in (ORSet, NoneType),
            'items must be ORSet or None')
        tressa(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')

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
        items = ORSet.unpack(data, inject=inject)
        return cls(items=items, clock=items.clock)

    def read(self, /, *, inject: dict = {}) -> tuple[SerializableType]:
        """Return the eventually consistent data view. Cannot be used for
            preparing deletion updates.
        """
        if self.cache_full is None:
            self.calculate_cache()

        if self.cache is None:
            self.cache = tuple([item.value for item in self.cache_full])

        return self.cache

    def read_full(self, /, *, inject: dict = {}) -> tuple[RGAItemWrapper]:
        """Return the full, eventually consistent list of items without
            tombstones but with complete RGAItemWrappers rather than the
            underlying values. Use this for preparing deletion updates --
            only a RGAItemWrapper can be used for delete.
        """
        if self.cache_full is None:
            self.calculate_cache()

        return tuple(self.cache_full)

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> RGArray:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')

        tressa(isinstance(state_update.data[1], RGAItemWrapper), 'item must be RGAItemWrapper')

        self.items.update(state_update)
        self.update_cache(state_update.data[1], state_update.data[1] in self.items.read())

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return self.items.checksums(from_ts=from_ts, until_ts=until_ts)

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying all updates from
            divergent nodes.
        """
        return self.items.history(
            from_ts=from_ts,
            until_ts=until_ts,
            update_class=update_class,
        )

    def append(self, item: SerializableType, writer: int, /, *,
               update_class: type[StateUpdateProtocol] = StateUpdate,
               inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that appends the item.
        """
        tressa(isinstance(item, SerializableType),
               'item must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')
        tressa(type(writer) is int, 'writer must be int')

        ts = self.clock.wrap_ts(self.clock.read())
        state_update = self.items.observe(
            RGAItemWrapper(item, ts, writer),
            update_class=update_class
        )

        self.update(state_update, inject=inject)

        return state_update

    def delete(self, item: RGAItemWrapper, /, *,
               update_class: type[StateUpdateProtocol] = StateUpdate,
               inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that deletes the specified item.
        """
        tressa(isinstance(item, RGAItemWrapper), 'item must be RGAItemWrapper')

        state_update = self.items.remove(item, update_class=update_class)

        self.update(state_update, inject=inject)

        return state_update

    def calculate_cache(self) -> None:
        """Reads the items from the underlying ORSet, orders them, then
            sets the cache_full list. Resets the cache.
        """
        # create sorted list of all items
        # sorted by (timestamp, writer, wrapper class name, packed value)
        items = list(self.items.observed)
        items.sort(key=lambda item: (
            item.ts, item.writer, item.value.__class__.__name__,
            item.value.pack())
        )

        # set instance values
        self.cache_full = items
        self.cache = None

    def update_cache(self, item: RGAItemWrapper, visible: bool) -> None:
        """Updates the cache by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets the cache.
        """
        tressa(isinstance(item, RGAItemWrapper), 'item must be RGAItemWrapper')
        tressa(type(visible) is bool, 'visible must be bool')

        if self.cache_full is None:
            self.calculate_cache()

        if visible:
            if item not in self.cache_full:
                # find correct insertion index
                # sorted by (timestamp, writer, wrapper class name, packed value)
                index = bisect(
                    self.cache_full,
                    (item.ts, item.writer, item.value.__class__.__name__, item.value.pack()),
                    key=lambda a: (a.ts, a.writer, a.value.__class__.__name__, a.value.pack())
                )
                self.cache_full.insert(index, item)
        else:
            if item in self.cache_full:
                # remove the item
                self.cache_full.remove(item)

        self.cache = None
