from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    StrWrapper,
    IntWrapper,
    DecimalWrapper,
    CTDataWrapper,
    NoneWrapper,
)
from .errors import tressa
from .interfaces import (
    ClockProtocol,
    StateUpdateProtocol,
    SerializableType,
)
from .lwwmap import LWWMap
from .scalarclock import ScalarClock
from .serialization import serialize_part, deserialize_part
from .stateupdate import StateUpdate
from typing import Any
from uuid import uuid4


class CausalTree:
    """Implements a Causal Tree CRDT."""
    positions: LWWMap
    clock: ClockProtocol
    cache: list[CTDataWrapper]

    def __init__(self, positions: LWWMap = None, clock: ClockProtocol = None) -> None:
        """Initialize a CausalTree from an LWWMap of item positions and a
            shared clock.
        """
        tressa(type(positions) is LWWMap or positions is None,
            'positions must be an LWWMap or None')
        tressa(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')

        clock = ScalarClock() if clock is None else clock
        positions = LWWMap(clock=clock) if positions is None else positions

        self.positions = positions
        self.clock = clock
        self.cache = None

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return self.positions.pack()

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> CausalTree:
        """Unpack the data bytes string into an instance."""
        positions = LWWMap.unpack(data, inject=inject)
        return cls(positions=positions, clock=positions.clock)

    def read(self, /, *, inject: dict = {}) -> tuple[SerializableType]:
        """Return the eventually consistent data view. Cannot be used for
            preparing deletion updates.
        """
        if self.cache is None:
            self.calculate_cache(inject=inject)

        return tuple([
            deserialize_part(serialize_part(item.value), {**globals(), **inject})
            for item in self.cache
            if item.visible
        ])

    def read_full(self, /, *, inject: dict = {}) -> tuple[CTDataWrapper]:
        """Return the full, eventually consistent list of items with
            tombstones and complete DataWrapperProtocols rather than the
            underlying values. Use this for preparing deletion updates --
            only a CTDataWrapper can be used for delete.
        """
        if self.cache is None:
            self.calculate_cache(inject=inject)

        return tuple(self.cache)

    def read_excluded(self, /, *, inject: dict = {}) -> list[CTDataWrapper]:
        """Returns a list of CTDataWrapper items that are excluded from
            the views returned by read() and read_full() due to circular
            references (i.e. where an item is its own descendant).
        """
        if self.cache is None:
            self.calculate_cache(inject=inject)
        return [
            r.value
            for _, r in self.positions.registers.items()
            if r.value not in self.cache
        ]

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> CausalTree:
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
        tressa(type(state_update.data[3]) is CTDataWrapper,
            'state_update.data[3] must be CTDataWrapper')

        inject = {**globals(), **inject}
        state_update.data[3].visible = state_update.data[0] == 'o'
        self.positions.update(state_update, inject=inject)
        self.update_cache(state_update.data[3], inject=inject)

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
            update_class=update_class
        )

    def put(self, item: SerializableType, writer: int, uuid: bytes,
            parent_uuid: bytes = b'', /, *,
            update_class: type[StateUpdateProtocol] = StateUpdate,
            inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns a update_class (StateUpdate by
            default) that puts the item after the parent.
        """
        tressa(isinstance(item, SerializableType),
               'item must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')
        tressa(type(uuid) is bytes, "uuid must be bytes")
        tressa(type(parent_uuid) is bytes, "parent_uuid must be bytes")
        inject = {**globals(), **inject}
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'o',
                BytesWrapper(uuid),
                writer,
                CTDataWrapper(item, uuid, parent_uuid)
            )
        )
        self.update(state_update, inject=inject)
        return update_class.unpack(state_update.pack(), inject=inject)

    def put_after(self, item: SerializableType, writer: int,
                  parent_uuid: bytes, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class that puts the item
            after the parent item.
        """
        uuid = uuid4().bytes

        return self.put(item, writer, uuid, parent_uuid, update_class=update_class)

    def put_first(self, item: SerializableType, writer: int, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> tuple[StateUpdateProtocol]:
        """Creates, applies, and returns at least one update_class
            (StateUpdate by default) that puts the item as the first
            item. Any ties for first place will be resolved by making
            the new item the parent of those other first items, and
            those update_class instances will also be created, applied,
            and returned.
        """
        updates: list[StateUpdateProtocol] = []
        updates.append(self.put(item, writer, uuid4().bytes, b'',
                                update_class=update_class, inject=inject))
        ct_item: CTDataWrapper = updates[0].data[3]
        heads = [item for item in self.cache if item.parent_uuid == b'']

        while len(heads) > 1:
            ct_idx = heads.index(ct_item)
            first = heads[0] if ct_idx > 0 else heads[1]
            heads.remove(first)
            updates.append(self.move_item(first, writer, ct_item.uuid,
                                          update_class=update_class, inject=inject))

        return tuple(updates)

    def move_item(self, item: CTDataWrapper, writer: int,
                  parent_uuid: bytes = b'', /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that moves the item to after the new parent.
        """
        tressa(isinstance(item, CTDataWrapper), "item must be CTDataWrapper")

        item.parent_uuid = parent_uuid

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'o',
                BytesWrapper(item.uuid),
                writer,
                item.unpack(item.pack(), inject={**globals(), **inject})
            )
        )
        self.update(state_update, inject=inject)
        return state_update

    def delete(self, ctdw: CTDataWrapper, writer: int, /, *,
               update_class: type[StateUpdateProtocol] = StateUpdate,
               inject: dict = {}) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that deletes the item specified by ctdw.
        """
        tressa(ctdw.value in self.positions.registers)

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(
                'r',
                BytesWrapper(ctdw.uuid),
                writer,
                CTDataWrapper(None, ctdw.uuid, ctdw.parent_uuid, False)
            )
        )

        self.update(state_update, inject=inject)

        return state_update

    def calculate_cache(self, /, *, inject: dict = {}) -> None:
        """Reads the items from the underlying LWWMap, orders them, then
            sets the cache list.
        """
        # create list of all items
        positions = self.positions.read(inject={**globals(), **inject})

        # function for getting sorted list of children
        def get_children(parent_uuid: bytes) -> list[CTDataWrapper]:
            children = [v for _, v in positions.items() if v.parent_uuid == parent_uuid]
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

    def update_cache(self, item: CTDataWrapper, /, *, inject: dict = {}) -> None:
        """Updates the cache by finding the correct insertion index for
            the given item, then inserting it there or removing it. Uses
            the bisect algorithm if necessary. Resets the cache.
        """
        tressa(isinstance(item, CTDataWrapper), 'item must be CTDataWrapper')

        positions = self.positions.read(inject=inject)

        if BytesWrapper(item.uuid) not in positions:
            return

        if self.cache is None:
            self.calculate_cache(inject=inject)
            return

        def remove_children(
                ctdw: CTDataWrapper,
                total: list[CTDataWrapper] = []
        ) -> list[CTDataWrapper]:
            children = [c for c in self.cache if c.parent_uuid == ctdw.uuid]
            if len(children) == 0:
                return total
            for child in children:
                if child in total:
                    continue
                total.append(child)
                if child in self.cache:
                    self.cache.remove(child)
                remove_children(child, total)
            return total

        for i in range(len((self.cache))):
            ctdw = self.cache[i]
            if ctdw.uuid != item.uuid:
                continue
            del self.cache[i]
            ctdw.visible = item.visible
            children = remove_children(ctdw)
            for child in children:
                self.update_cache(child)
            break

        def walk(item: CTDataWrapper) -> CTDataWrapper:
            children = [c for c in self.cache if c.parent_uuid == item.uuid]
            if len(children) == 0:
                return item
            children = sorted(children, key=lambda c: c.uuid)
            return walk(children[-1])

        def add_orphans():
            potential_orphans = self.read_excluded()
            for ctdw in potential_orphans:
                if ctdw.parent_uuid == item.uuid:
                    self.update_cache(ctdw)

        if item.parent_uuid == b'':
            heads = [ctdw for ctdw in self.cache if ctdw.parent_uuid == b'']
            heads.append(item)
            heads.sort(key=lambda ctdw: ctdw.uuid)
            index = heads.index(item)
            if index != 0:
                descendant = walk(heads[index-1])
                while descendant not in self.cache:
                    descendant = [
                        c for c in self.cache
                        if c.uuid == descendant.parent_uuid
                    ][0]
                index = self.cache.index(descendant) + 1
            self.cache.insert(index, item)
            add_orphans()
            return

        for i in range(len(self.cache)):
            ctdw = self.cache[i]
            if ctdw.uuid == item.parent_uuid:
                children = [c for c in self.cache if c.parent_uuid == ctdw.uuid]
                children.sort(key=lambda c: c.uuid)
                if len(children) > 0:
                    children.append(item)
                    children.sort(key=lambda c: c.uuid)
                    if children.index(item) == 0:
                        index = i + 1
                    else:
                        before = children[children.index(item) - 1]
                        index = self.cache.index(walk(before)) + 1
                else:
                    index = i + 1
                self.cache.insert(index, item)
                add_orphans()
                return
