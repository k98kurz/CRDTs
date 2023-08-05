from __future__ import annotations
from dataclasses import dataclass, field
import struct

from crdts.stateupdate import StateUpdate

from .datawrappers import (
    BytesWrapper,
    CTDataWrapper,
    DecimalWrapper,
    IntWrapper,
    NoneWrapper,
    RGATupleWrapper,
    StrWrapper,
)
from .interfaces import ClockProtocol, StateUpdateProtocol
from .scalarclock import ScalarClock


@dataclass
class Counter:
    """Implements the Counter CRDT."""
    counter: int = field(default=0)
    clock: ClockProtocol = field(default_factory=ScalarClock)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        clock_size = len(clock)

        return struct.pack(
            f'!I{clock_size}sI',
            clock_size,
            clock,
            self.counter
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> Counter:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 8, 'data must be more than 8 bytes'
        dependencies = {**globals(), **inject}

        clock_size, _ = struct.unpack(f'!I{len(data)-4}s', data)
        _, clock, counter = struct.unpack(f'!I{clock_size}sI', data)
        clock_class, _, clock = clock.partition(b'_')
        clock_class = str(bytes.fromhex(str(clock_class, 'utf-8')), 'utf-8')
        assert clock_class in dependencies, f'cannot find {clock_class}'
        assert hasattr(dependencies[clock_class], 'unpack'), \
            f'{clock_class} missing unpack method'
        clock = dependencies[clock_class].unpack(clock)

        return cls(counter=counter, clock=clock)

    def read(self) -> int:
        """Return the eventually consistent data view."""
        return self.counter

    def update(self, state_update: StateUpdateProtocol) -> Counter:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is int, 'state_update.data must be an int'

        self.counter = max([self.counter, state_update.data])
        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.counter,
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return (StateUpdate(self.clock.uuid, self.clock.read()-1, self.counter),)

    def increase(self, amount: int = 1) -> StateUpdate:
        """Increase the counter by the given amount (default 1). Returns
            the StateUpdate that should be propagated to the network.
        """
        assert type(amount) is int, 'amount must be int'
        assert amount > 0, 'amount must be positive'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            self.counter + amount
        )
        self.update(state_update)

        return state_update
