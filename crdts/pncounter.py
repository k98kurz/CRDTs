from __future__ import annotations
from .errors import tressa
from .interfaces import ClockProtocol, StateUpdateProtocol
from .merkle import get_merkle_history, resolve_merkle_histories
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from dataclasses import dataclass, field
from packify import pack, unpack
from typing import Any


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
        return pack([
            self.positive,
            self.negative,
            self.clock
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> PNCounter:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 20, 'data must be more than 20 bytes')
        dependencies = {**globals(), **inject}
        positive, negative, clock = unpack(data, inject=dependencies)
        return cls(
            positive=positive,
            negative=negative,
            clock=clock,
        )

    def read(self) -> int:
        """Return the eventually consistent data view."""
        return self.positive - self.negative

    def update(self, state_update: StateUpdateProtocol) -> PNCounter:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple of 2 ints')
        tressa(len(state_update.data) == 2,
            'state_update.data must be tuple of 2 ints')
        tressa(type(state_update.data[0]) is int,
            'state_update.data must be tuple of 2 ints')
        tressa(type(state_update.data[1]) is int,
            'state_update.data must be tuple of 2 ints')

        self.positive = max([self.positive, state_update.data[0]])
        self.negative = max([self.negative, state_update.data[1]])
        self.clock.update(state_update.ts)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.clock.read(),
            self.positive,
            self.negative,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying updates from divergent
            nodes.
        """
        if from_ts is not None and self.clock.is_later(from_ts, self.clock.read()-1):
            return tuple()
        if until_ts is not None and self.clock.is_later(self.clock.read()-1, until_ts):
            return tuple()

        return (update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read()-1,
            data=(self.positive, self.negative)
        ),)

    def get_merkle_history(self, /, *,
                           update_class: type[StateUpdateProtocol] = StateUpdate
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
            synchronization.
        """
        return resolve_merkle_histories(self, history=history)

    def increase(self, amount: int = 1, /, *,
                 update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Increase the counter by the given amount (default 1). Returns
            the update_class (StateUpdate by default) that should be
            propagated to the network.
        """
        tressa(type(amount) is int, 'amount must be int')
        tressa(amount > 0, 'amount must be positive')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(self.positive + amount, self.negative)
        )
        self.update(state_update)

        return state_update

    def decrease(self, amount: int = 1, /, *,
                 update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Decrease the counter by the given amount (default 1). Returns
            the update_class (StateUpdate by default) that should be
            propagated to the network.
        """
        tressa(type(amount) is int, 'amount must be int')
        tressa(amount > 0, 'amount must be positive')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(self.positive, self.negative + amount)
        )
        self.update(state_update)

        return state_update
