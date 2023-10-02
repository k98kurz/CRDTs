from __future__ import annotations
from .errors import tressa, tert, vert
from .interfaces import ClockProtocol, StateUpdateProtocol
from .scalarclock import ScalarClock
from .serialization import serialize_part, deserialize_part
from .stateupdate import StateUpdate
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any


@dataclass
class Counter:
    """Implements the Counter CRDT."""
    counter: int = field(default=0)
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        return serialize_part([self.counter, self.clock])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> Counter:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 8, 'data must be more than 8 bytes')
        counter, clock = deserialize_part(data, inject={**globals(), **inject})
        return cls(counter, clock)

    def read(self, /, *, inject: dict = {}) -> int:
        """Return the eventually consistent data view."""
        return self.counter

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> Counter:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is int, 'state_update.data must be an int')

        self.counter = max([self.counter, state_update.data])
        self.clock.update(state_update.ts)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.counter,
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
            data=self.counter),
        )

    def get_merkle_history(self, /, *,
                           update_class: type[StateUpdateProtocol] = StateUpdate) -> list[list[bytes], bytes, dict[bytes, bytes]]:
        """Get a Merkle-DAG history for the StateUpdates of the form
            [[sha256(update.pack()) for update in self.history()], root,
            self.history()].
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

    def increase(self, amount: int = 1, /, *,
                 update_class: type[StateUpdateProtocol] = StateUpdate,
                 inject: dict = {}) -> StateUpdateProtocol:
        """Increase the counter by the given amount (default 1). Returns
            the update_class (StateUpdate by default) that should be
            propagated to the network.
        """
        tressa(type(amount) is int, 'amount must be int')
        tressa(amount > 0, 'amount must be positive')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=self.counter + amount
        )
        self.update(state_update, inject=inject)

        return state_update
