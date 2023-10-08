from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    StrWrapper,
    IntWrapper,
    DecimalWrapper,
    CTDataWrapper,
    NoneWrapper,
    RGAItemWrapper,
)
from .errors import tert, vert
from .interfaces import (
    ClockProtocol,
    StateUpdateProtocol,
)
from .merkle import get_merkle_history, resolve_merkle_histories
from .orset import ORSet
from .stateupdate import StateUpdate
from bisect import bisect
from packify import SerializableType, pack
from types import NoneType
from typing import Any, Type


class RGArray:
    """Implements the Replicated Growable Array CRDT. This uses the
        ORSet to handle CRDT logic and provides a logical view over top
        of it.
    """
    items: ORSet
    clock: ClockProtocol
    cache_full: list[RGAItemWrapper]
    cache: tuple[Any]

    def __init__(self, items: ORSet = None, clock: ClockProtocol = None) -> None:
        """Initialize an RGA from an ORSet of items and a shared clock.
            Raises TypeError for invalid items or clock.
        """
        tert(type(items) in (ORSet, NoneType),
            'items must be ORSet or None')
        tert(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')

        items = ORSet() if items is None else items
        clock = items.clock if clock is None else clock
        items.clock = clock

        self.items = items
        self.clock = clock

        self.calculate_cache()

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return self.items.pack()

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> RGArray:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        items = ORSet.unpack(data, inject={**globals(), **inject})
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
        """Apply an update and return self (monad pattern).  Raises
            TypeError or ValueError for invalid amount or update_class.
        """
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(isinstance(state_update.data[1], RGAItemWrapper),
             'item must be RGAItemWrapper')

        self.items.update(state_update)
        self.update_cache(state_update.data[1], state_update.data[1] in self.items.read())

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return self.items.checksums(from_ts=from_ts, until_ts=until_ts)

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: Type[StateUpdateProtocol] = StateUpdate
                ) -> tuple[StateUpdateProtocol]:
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

    def get_merkle_history(self, /, *,
                           update_class: Type[StateUpdateProtocol] = StateUpdate
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
            synchronization. Raises TypeError or ValueError for invalid
            input.
        """
        return resolve_merkle_histories(self, history=history)

    def index(self, item: SerializableType, _start: int = 0, _stop: int = None) -> int:
        """Returns the int index of the item in the list returned by
            read(). Raises ValueError if the item is not present.
        """
        if _stop:
            return self.read().index(item, _start, _stop)
        return self.read().index(item, _start)

    def append(self, item: SerializableType, writer: SerializableType, /, *,
               update_class: Type[StateUpdateProtocol] = StateUpdate,
               inject: dict = {}) -> tuple[StateUpdateProtocol]:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that appends the item. The RGAItemWrapper will be
            in the data attribute at index 1. Raises TypeError for
            invalid item, writer, or update_class. Note that this will
            always return a tuple with only one update_class, but it is
            a tuple for consistency with the ListProtocol.
        """
        tert(isinstance(item, SerializableType),
               f'item must be SerializableType ({SerializableType})')
        tert(isinstance(writer, SerializableType),
               f'writer must be SerializableType ({SerializableType})')

        ts = self.clock.read()
        state_update = self.items.observe(
            RGAItemWrapper(item, ts, writer),
            update_class=update_class
        )

        tert(isinstance(state_update, StateUpdateProtocol),
             'update_class must implement StateUpdateProtocol')

        self.update(state_update, inject=inject)

        return (state_update,)

    def remove(self, index: int, /, *,
               update_class: Type[StateUpdateProtocol] = StateUpdate
               ) -> tuple[StateUpdateProtocol]:
        """Creates, applies, and returns an update_class that removes
            the item at the index in the list returned by read().
        """
        items = self.read_full()
        tert(type(index) is int, f"index must be int between 0 and {len(items)-1}")
        vert(0 <= index < len(items), f"index must be int between 0 and {len(items)-1}")
        item = items[index]
        return (self.delete(item, update_class=update_class),)

    def delete(self, item: RGAItemWrapper, /, *,
               update_class: Type[StateUpdateProtocol] = StateUpdate,
               inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that deletes the specified item. Raises TypeError
            for invalid item or update_class.
        """
        tert(isinstance(item, RGAItemWrapper), 'item must be RGAItemWrapper')

        state_update = self.items.remove(item, update_class=update_class)

        self.update(state_update, inject=inject)

        return state_update

    def calculate_cache(self) -> None:
        """Reads the items from the underlying ORSet, orders them, then
            sets the cache_full list. Resets the cache.
        """
        # create sorted list of all items
        # sorted by (timestamp, writer, serialized value)
        items = list(self.items.observed)
        items.sort(key=lambda item: (item.ts, item.writer, pack(item.value)))

        # set instance values
        self.cache_full = items
        self.cache = None

    def update_cache(self, item: RGAItemWrapper, visible: bool) -> None:
        """Updates the cache by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets the cache. Raises
            TypeError for invalid item or visible.
        """
        tert(isinstance(item, RGAItemWrapper), 'item must be RGAItemWrapper')
        tert(type(visible) is bool, 'visible must be bool')

        if self.cache_full is None:
            self.calculate_cache()

        if visible:
            if item not in self.cache_full:
                # find correct insertion index
                # sorted by (timestamp, writer, serialized value)
                index = bisect(
                    self.cache_full,
                    (item.ts, item.writer, pack(item.value)),
                    key=lambda a: (a.ts, a.writer, pack(a.value))
                )
                self.cache_full.insert(index, item)
        else:
            if item in self.cache_full:
                # remove the item
                self.cache_full.remove(item)

        self.cache = None
