from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    CTDataWrapper,
    DecimalWrapper,
    IntWrapper,
    NoneWrapper,
    RGATupleWrapper,
    StrWrapper,
)
from .errors import tressa
from .interfaces import ClockProtocol, StateUpdateProtocol
from .scalarclock import ScalarClock
from .serialization import serialize_part, deserialize_part
from .stateupdate import StateUpdate
from dataclasses import dataclass, field
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
    def unpack(cls, data: bytes, inject: dict = {}) -> Counter:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 8, 'data must be more than 8 bytes')
        counter, clock = deserialize_part(data, inject=inject)
        return cls(counter, clock)

    def read(self) -> int:
        """Return the eventually consistent data view."""
        return self.counter

    def update(self, state_update: StateUpdateProtocol) -> Counter:
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
        return (update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read()-1,
            data=self.counter),
        )

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
            data=self.counter + amount
        )
        self.update(state_update)

        return state_update
