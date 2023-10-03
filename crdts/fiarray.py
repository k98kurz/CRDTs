from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    StrWrapper,
    IntWrapper,
    DecimalWrapper,
    NoneWrapper,
    FIAItemWrapper
)
from .errors import tressa, tert, vert
from .interfaces import (
    ClockProtocol,
    StateUpdateProtocol,
    SerializableType,
)
from .lwwmap import LWWMap
from .scalarclock import ScalarClock
from .serialization import serialize_part, deserialize_part
from .stateupdate import StateUpdate
from bisect import bisect
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import uuid4


class FIArray:
    """Implements a fractionally-indexed array CRDT."""
    positions: LWWMap
    clock: ClockProtocol
    cache_full: list[FIAItemWrapper]
    cache: list[SerializableType]

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
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> FIArray:
        """Unpack the data bytes string into an instance."""
        positions = LWWMap.unpack(data, inject)
        return cls(positions=positions, clock=positions.clock)

    def read(self, /, *, inject: dict = {}) -> tuple[Any]:
        """Return the eventually consistent data view. Cannot be used for
            preparing deletion updates.
        """
        if self.cache is None:
            if self.cache_full is None:
                self.calculate_cache(inject=inject)
            self.cache = [item.value for item in self.cache_full]

        return tuple(self.cache)

    def read_full(self, /, *, inject: dict = {}) -> tuple[FIAItemWrapper]:
        """Return the full, eventually consistent list of items without
            tombstones but with complete FIAItemWrappers rather than the
            underlying SerializableType values. Use the resulting
            FIAItemWrapper(s) for calling delete and move_item. (The
            FIAItemWrapper containing a value put into the list will be
            index 3 of the StateUpdate returned by a put method.)
        """
        if self.cache_full is None:
            self.calculate_cache(inject=inject)

        return tuple(self.cache_full)

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> FIArray:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple')
        tressa(state_update.data[0] in ('o', 'r'),
            'state_update.data[0] must be in (\'o\', \'r\')')
        tressa(isinstance(state_update.data[1], SerializableType),
            'state_update.data[1] must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')
        tressa(type(state_update.data[2]) is int,
            'state_update.data[2] must be writer int')
        tressa(isinstance(state_update.data[3], FIAItemWrapper) or
               isinstance(state_update.data[3], NoneWrapper),
            'state_update.data[3] must be FIAItemWrapper|NoneWrapper')

        self.positions.update(state_update)
        self.update_cache(state_update.data[1], state_update.data[3], state_update.data[0] == 'o',
                          inject=inject)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns checksums for the underlying data to detect
            desynchronization due to network partition.
        """
        return self.positions.checksums(from_ts=from_ts, until_ts=until_ts)

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return self.positions.history(
            from_ts=from_ts,
            until_ts=until_ts,
            update_class=update_class,
        )

    @classmethod
    def index_between(cls, first: Decimal, second: Decimal) -> Decimal:
        """Return an index between first and second with a random offset."""
        tressa(type(first) is Decimal, 'first must be a Decimal')
        tressa(type(second) is Decimal, 'second must be a Decimal')

        return Decimal(first + second)/Decimal(2)

    def put(self, item: SerializableType, writer: int, index: Decimal, /, *,
            update_class: type[StateUpdateProtocol] = StateUpdate,
            inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at the index. The FIAItemWrapper
            will be at index 3 of the data attribute of the returned
            update_class instance.
        """
        fia_item = FIAItemWrapper(
            value=item,
            index=index,
            uuid=uuid4().bytes
        )
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'o',
                BytesWrapper(fia_item.uuid),
                writer,
                fia_item
            )
        )

        self.update(state_update, inject=inject)

        return state_update

    def put_between(self, item: SerializableType, writer: int,
                    first: FIAItemWrapper, second: FIAItemWrapper, /, *,
                    update_class: type[StateUpdateProtocol] = StateUpdate,
                    inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at an index between first and
            second. The FIAItemWrapper will be at index 3 of the data
            attribute of the returned update_class instance.
        """
        first_index = first.index.value
        second_index = second.index.value
        index = self.index_between(first_index, second_index)

        return self.put(item, writer, index, update_class=update_class,
                        inject=inject)

    def put_before(self, item: SerializableType, writer: int,
                   other: FIAItemWrapper, /, *,
                   update_class: type[StateUpdateProtocol] = StateUpdate,
                   inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item before the other item. The
            FIAItemWrapper will be at index 3 of the data attribute of
            the returned update_class instance.
        """
        tressa(other in self.read_full(inject=inject),
               'other must already be assigned a position')

        before_index = other.index.value
        first_index = self.read_full(inject=inject).index(other)

        if first_index > 0:
            prior = self.read_full(inject=inject)[first_index-1]
            prior_index = prior.index.value
        else:
            prior_index = Decimal(0)

        index = self.index_between(before_index, prior_index)

        return self.put(item, writer, index, update_class=update_class, inject=inject)

    def put_after(self, item: SerializableType, writer: int,
                  other: FIAItemWrapper, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item after the other item. The
            FIAItemWrapper will be at index 3 of the data attribute of
            the returned update_class instance.
        """
        tressa(other in self.read_full(inject=inject), 'other must already be assigned a position')

        after_index = other.index.value
        first_index = self.read_full(inject=inject).index(other)

        if len(self.read_full(inject=inject)) > first_index+1:
            next = self.read_full(inject=inject)[first_index+1]
            next_index = next.index
        else:
            next_index = Decimal(1)

        index = self.index_between(after_index, next_index)

        return self.put(item, writer, index, update_class=update_class, inject=inject)

    def put_first(self, item: SerializableType, writer: int, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at an index between 0 and the
            first item. The FIAItemWrapper will be at index 3 of the
            data attribute of the returned update_class instance.
        """
        if len(self.read_full(inject=inject)) > 0:
            first = self.read_full(inject=inject)[0]
            first_index = first.index.value
            # average between 0 and first index
            index = Decimal(Decimal(0) + first_index)/Decimal(2)
        else:
            # average between 0 and 1
            index = Decimal('0.5')

        return self.put(item, writer, index, update_class=update_class, inject=inject)

    def put_last(self, item: SerializableType, writer: int, /, *,
                 update_class: type[StateUpdateProtocol] = StateUpdate,
                 inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at an index between the last
            item and 1. The FIAItemWrapper will be at index 3 of the
            data attribute of the returned update_class instance.
        """
        if len(self.read_full(inject=inject)) > 0:
            last = self.read_full(inject=inject)[-1]
            last_index = last.index.value
            # average between last index and 1
            index = Decimal(last_index + Decimal(1))/Decimal(2)
        else:
            # average between 0 and 1
            index = Decimal('0.5')

        return self.put(item, writer, index, update_class=update_class)

    def move_item(self, item: FIAItemWrapper, writer: int, /, *,
                  new_index: Decimal = None, after: FIAItemWrapper = None,
                  before: FIAItemWrapper = None,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item at the new index, or directly
            before the before, or directly after the after, or
            halfway between before and after. The FIAItemWrapper will be
            at index 3 of the data attribute of the returned
            update_class instance.
        """
        tressa(new_index is not None or before is not None or
               after is not None,
               'at least one must be specified: new_index, before, or after')
        tressa(new_index is None or type(new_index) is Decimal,
               'new_index must be Decimal|NoneType')
        tressa(before is None or isinstance(before, FIAItemWrapper),
               'before must be FIAItemWrapper|NoneType')
        tressa(after is None or isinstance(after, FIAItemWrapper),
               'after must be FIAItemWrapper|NoneType')

        if item in self.cache_full:
            self.cache_full.remove(item)

        if new_index is None:
            if before and after:
                new_index = self.index_between(after.index.value,
                                               before.index.value)
            elif before:
                bfidx = self.cache_full.index(before)
                if bfidx == 0:
                    new_index = self.index_between(Decimal("0"),
                                                   before.index.value)
                else:
                    after = self.cache_full[bfidx-1]
                    new_index = self.index_between(after.index.value,
                                                   before.index.value)
            elif after:
                afidx = self.cache_full.index(after)
                if afidx == len(self.cache_full)-1:
                    new_index = self.index_between(after.index.value,
                                                   Decimal("1"))
                else:
                    before = self.cache_full[afidx+1]
                    new_index = self.index_between(after.index,
                                                   before.index.value)

        item.index.value = new_index

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'o',
                BytesWrapper(item.uuid),
                writer,
                item
            )
        )

        self.update(state_update, inject=inject)

        return state_update

    def normalize(self, writer: int, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> tuple[StateUpdateProtocol]:
        """Evenly distribute the item indices. Returns tuple of
            update_class (StateUpdate by default) that encode the index
            updates.
        """
        index_space = Decimal("1")/Decimal(len(self.read()) + 1)
        updates = []
        items = self.read_full()
        for i in range(len(items)):
            item = items[i]
            updates.append(self.move_item(
                item, writer, new_index=index_space*Decimal(i),
                update_class=update_class, inject=inject
            ))
        return tuple(updates)

    def get_merkle_history(self, /, *,
                           update_class: type[StateUpdateProtocol] = StateUpdate
                           ) -> list[list[bytes], bytes, dict[bytes, bytes]]:
        """Get a Merklized history for the StateUpdates of the form
            [[content_id for update in self.history()], root, {
            content_id: packed for update in self.history()}] where
            packed is the result of update.pack() and content_id is the
            sha256 of the packed update.
        """
        history = self.history(update_class=update_class)
        leaves = [
            update.pack()
            for update in history
        ]
        leaf_ids = [
            sha256(leaf).digest()
            for leaf in leaves
        ]
        leaf_ids.sort()
        history = {
            leaf_id: leaf
            for leaf_id, leaf in zip(leaf_ids, leaves)
        }
        root = sha256(b''.join(leaf_ids)).digest()
        return [leaf_ids, root, history]

    def resolve_merkle_histories(self, history: list[list[bytes], bytes]) -> list[bytes]:
        """Accept a history of form [leaves, root] from another node.
            Return the leaves that need to be resolved and merged for
            synchronization.
        """
        tert(type(history) in (list, tuple), 'history must be [[bytes, ], bytes]')
        vert(len(history) >= 2, 'history must be [[bytes, ], bytes]')
        tert(all([type(leaf) is bytes for leaf in history[0]]),
             'history must be [[bytes, ], bytes]')
        local_history = self.get_merkle_history()
        if local_history[1] == history[1]:
            return []
        return [
            leaf for leaf in history[0]
            if leaf not in local_history[0]
        ]

    def delete(self, item: FIAItemWrapper, writer: int, /, *,
               update_class: type[StateUpdateProtocol] = StateUpdate,
               inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that deletes the item. Index 3 of the data
            attribute of the returned update_class instance will be the
            NoneWrapper tombstone.
        """
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'r',
                BytesWrapper(item.uuid),
                writer,
                NoneWrapper(),
            )
        )

        self.update(state_update, inject=inject)

        return state_update

    def calculate_cache(self, inject: dict = {}) -> None:
        """Reads the items from the underlying LWWMap, orders them, then
            sets the cache_full list. Resets the cache.
        """
        # create list of all items
        positions = self.positions.read(inject={**globals(), **inject})
        items: list[FIAItemWrapper] = [v for k, v in positions.items()]
        # sort by (index, serialized value)
        items.sort(key=lambda item: (item.index, serialize_part(item.value)))

        # set instance values
        self.cache_full = items
        self.cache = None

    def update_cache(self, uuid: BytesWrapper, item: FIAItemWrapper|NoneWrapper,
                     visible: bool, /, *, inject: dict = {}) -> None:
        """Updates cache_full by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets cache.
        """
        tressa(isinstance(item, FIAItemWrapper) or isinstance(item, NoneWrapper),
               'item must be FIAItemWrapper|NoneWrapper')
        tressa(type(visible) is bool, 'visible must be bool')

        positions = self.positions.read(inject={**globals(), **inject})

        if self.cache_full is None:
            self.calculate_cache(inject=inject)

        uuids = [fiaitem.uuid for fiaitem in self.cache_full]
        try:
            index = uuids.index(uuid.value)
            del self.cache_full[index]
        except BaseException:
            pass

        if visible and BytesWrapper(item.uuid) in positions:
            # find correct insertion index
            # sort by (index, serialized value)
            index = bisect(
                self.cache_full,
                (item.index, serialize_part(item.value)),
                key=lambda a: (a.index, serialize_part(a.value))
            )
            self.cache_full.insert(index, item)

        self.cache = None
