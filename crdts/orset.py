from __future__ import annotations
from .errors import tert, vert
from .interfaces import (
    ClockProtocol,
    StateUpdateProtocol,
)
from .merkle import get_merkle_history, resolve_merkle_histories
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from dataclasses import dataclass, field
from packify import SerializableType, pack, unpack
from typing import Any, Callable, Optional, Type


@dataclass
class ORSet:
    """Implements the Observed Removed Set (ORSet) CRDT. Comprised of
        two Sets with a read method that removes the removed set members
        from the observed set. Add-biased.
    """
    observed: set[SerializableType] = field(default_factory=set)
    observed_metadata: dict[SerializableType, StateUpdateProtocol] = field(default_factory=dict)
    removed: set[SerializableType] = field(default_factory=set)
    removed_metadata: dict[SerializableType, StateUpdateProtocol] = field(default_factory=dict)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    cache: Optional[tuple] = field(default=None)
    listeners: list[Callable] = field(default_factory=list)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return pack([
            self.observed,
            self.observed_metadata,
            self.removed,
            self.removed_metadata,
            self.clock,
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> ORSet:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        observed, observed_metadata, removed, removed_metadata, clock = unpack(
            data,
            inject={**globals(), **inject}
        )
        return cls(observed, observed_metadata, removed, removed_metadata, clock)

    def read(self, /, *, inject: dict = {}) -> set[SerializableType]:
        """Return the eventually consistent data view."""
        if self.cache is not None:
            if self.cache[0] == self.clock.read():
                return self.cache[1]

        difference = self.observed.difference(self.removed)
        self.cache = (self.clock.read(), difference)

        return difference

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> ORSet:
        """Apply an update and return self (monad pattern)."""
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(type(state_update.data) is tuple,
            'state_update.data must be tuple')
        vert(len(state_update.data) == 2,
            'state_update.data must be 2 long')
        vert(state_update.data[0] in ('o', 'r'),
            'state_update.data[0] must be in (\'o\', \'r\')')
        tert(isinstance(state_update.data[1], SerializableType),
            f'state_update.data[1] must be SerializableType ({SerializableType})')

        self.invoke_listeners(state_update)
        op, member = state_update.data
        ts = state_update.ts

        if op == 'o':
            # add to observed
            if member not in self.removed or (
                member in self.removed_metadata and
                not self.clock.is_later(self.removed_metadata[member], ts)
            ):
                self.observed.add(member)
                if member in self.observed_metadata:
                    oldts = self.observed_metadata[member]
                else:
                    oldts = self.clock.default_ts
                if self.clock.is_later(ts, oldts):
                    self.observed_metadata[member] = ts

                # remove from removed
                if member in self.removed:
                    self.removed.remove(member)
                    del self.removed_metadata[member]

                # invalidate cache
                self.cache = None

        if op == 'r':
            # add to removed
            if member not in self.observed or (
                member in self.observed_metadata and
                self.clock.is_later(ts, self.observed_metadata[member])
            ):
                self.removed.add(member)
                if member in self.removed_metadata:
                    oldts = self.removed_metadata[member]
                else:
                    oldts = self.clock.default_ts
                if self.clock.is_later(ts, oldts):
                    self.removed_metadata[member] = ts

                # remove from observed
                if member in self.observed:
                    self.observed.remove(member)
                    del self.observed_metadata[member]

                # invalidate cache
                self.cache = None

        self.clock.update(ts)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        observed, removed = 0, 0
        total_observed_crc32 = 0
        total_removed_crc32 = 0
        for member, ts in self.observed_metadata.items():
            if from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue

            observed += 1
            total_observed_crc32 += crc32(pack(member))

        for member, ts in self.removed_metadata.items():
            if from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue

            removed += 1
            total_removed_crc32 += crc32(pack(member))

        return (
            observed,
            removed,
            total_observed_crc32 % 2**32,
            total_removed_crc32 % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: Type[StateUpdateProtocol] = StateUpdate
                ) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying updates from divergent
            nodes.
        """
        updates = []

        for o in self.observed:
            if from_ts is not None and \
                self.clock.is_later(from_ts, self.observed_metadata[o]):
                continue
            if until_ts is not None and \
                self.clock.is_later(self.observed_metadata[o], until_ts):
                continue
            updates.append(
                update_class(
                    clock_uuid=self.clock.uuid,
                    ts=self.observed_metadata[o],
                    data=('o', o)
                )
            )

        for r in self.removed:
            if from_ts is not None and \
                self.clock.is_later(from_ts, self.removed_metadata[r]):
                continue
            if until_ts is not None and \
                self.clock.is_later(self.removed_metadata[r], until_ts):
                continue
            updates.append(
                update_class(
                    clock_uuid=self.clock.uuid,
                    ts=self.removed_metadata[r],
                    data=('r', r)
                )
            )

        return tuple(updates)

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

    def resolve_merkle_histories(self, history: list[bytes, list[bytes]]
                                 ) -> list[bytes]:
        """Accept a history of form [root, leaves] from another node.
            Return the leaves that need to be resolved and merged for
            synchronization. Raises TypeError or ValueError for invalid
            input.
        """
        return resolve_merkle_histories(self, history=history)

    def observe(self, member: SerializableType, /, *,
                update_class: Type[StateUpdateProtocol] = StateUpdate
                ) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that adds the given member to the observed set. The
            member will be in the data attribute at index 1. Raises
            TypeError for invalid member (must be SerializableType that
            is also Hashable).
        """
        tert(isinstance(member, SerializableType),
               f'member must be SerializableType ({SerializableType})')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('o', member)
        )

        self.update(state_update)

        return state_update

    def remove(self, member: SerializableType, /, *,
               update_class: Type[StateUpdateProtocol] = StateUpdate
               ) -> StateUpdateProtocol:
        """Creates, applies, and returns an update_class (StateUpdate by
            default) that adds the given member to the removed set.
            Raises TypeError for invalid member (must be
            SerializableType that is also Hashable).
        """
        tert(isinstance(member, SerializableType),
               f'member must be SerializableType ({SerializableType})')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('r', member)
        )

        self.update(state_update)

        return state_update

    def add_listener(self, listener: Callable[[StateUpdateProtocol], None]) -> None:
        """Adds a listener that is called on each update."""
        tert(callable(listener),
             "listener must be Callable[[StateUpdateProtocol], None]")
        self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[StateUpdateProtocol], None]) -> None:
        """Removes a listener if it was previously added."""
        self.listeners.remove(listener)

    def invoke_listeners(self, state_update: StateUpdateProtocol) -> None:
        """Invokes all event listeners, passing them the state_update."""
        for listener in self.listeners:
            listener(state_update)
