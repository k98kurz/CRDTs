from __future__ import annotations
from .datawrappers import BytesWrapper, CTDataWrapper, NoneWrapper
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .lwwmap import LWWMap
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from typing import Any
from uuid import uuid1


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

    def history(self, update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return self.positions.history(update_class)

    def put(self, item: DataWrapperProtocol, writer: int, uuid: bytes,
            parent: bytes = b'',
            update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns a update_class (StateUpdate by
            default) that puts the item after the parent.
        """
        assert type(uuid) is bytes, "uuid must be bytes"
        assert type(parent) is bytes, "parent must be bytes"
        state_update = update_class(
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
        parent: CTDataWrapper,
        update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class that puts the item
            after the parent item.
        """
        assert parent in [item.value for item in self.read_full()], \
            'parent must already be assigned a position'

        uuid = uuid1().bytes
        parent = self.positions.registers[parent].value.uuid

        return self.put(item, writer, uuid, parent, update_class)

    def put_first(self, item: DataWrapperProtocol, writer: int,
                  update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that puts the item as the first item. Note that if
            another item was already put first, this might be put second
            due to tie breaking; in such a case, update the other item's
            parent_uuid to move it to the right index.
        """
        return self.put(item, writer, uuid1().bytes, b'', update_class)

    def delete(self, ctdw: CTDataWrapper, writer: int,
               update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that deletes the item specified by ctdw.
        """
        assert ctdw.value in self.positions.registers

        state_update = update_class(
            self.clock.uuid,
            self.clock.read(),
            (
                'r',
                BytesWrapper(ctdw.uuid),
                writer,
                CTDataWrapper(NoneWrapper(), ctdw.uuid, ctdw.parent_uuid, False)
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
