from __future__ import annotations
from dataclasses import dataclass, field
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
from .stateupdate import StateUpdate
import struct


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
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        clock_size = len(clock)

        return struct.pack(
            f'!I{clock_size}sII',
            clock_size,
            clock,
            self.positive,
            self.negative,
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> PNCounter:
        """Unpack the data bytes string into an instance."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) > 20, 'data must be more than 20 bytes'
        dependencies = {**globals(), **inject}

        clock_size, _ = struct.unpack(f'!I{len(data)-4}s', data)
        _, clock, positive, negative = struct.unpack(
            f'!I{clock_size}sII',
            data
        )
        clock_class, _, clock = clock.partition(b'_')
        clock_class = str(bytes.fromhex(str(clock_class, 'utf-8')), 'utf-8')
        assert clock_class in dependencies, f'cannot find {clock_class}'
        assert hasattr(dependencies[clock_class], 'unpack'), \
            f'{clock_class} missing unpack method'
        clock = dependencies[clock_class].unpack(clock)

        return cls(positive, negative, clock)

    def read(self) -> int:
        """Return the eventually consistent data view."""
        return self.positive - self.negative

    def update(self, state_update: StateUpdateProtocol) -> PNCounter:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple of 2 ints'
        assert len(state_update.data) == 2, \
            'state_update.data must be tuple of 2 ints'
        assert type(state_update.data[0]) is int, \
            'state_update.data must be tuple of 2 ints'
        assert type(state_update.data[1]) is int, \
            'state_update.data must be tuple of 2 ints'

        self.positive = max([self.positive, state_update.data[0]])
        self.negative = max([self.negative, state_update.data[1]])
        self.clock.update(state_update.ts)

        return self

    def checksums(self) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            self.clock.read(),
            self.positive,
            self.negative,
        )

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        return (StateUpdate(self.clock.uuid, self.clock.read()-1, (self.positive, self.negative)),)

    def increase(self, amount: int = 1) -> StateUpdate:
        """Increase the counter by the given amount (default 1). Returns
            the StateUpdate that should be propagated to the network.
        """
        assert type(amount) is int, 'amount must be int'
        assert amount > 0, 'amount must be positive'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (self.positive + amount, self.negative)
        )
        self.update(state_update)

        return state_update

    def decrease(self, amount: int = 1) -> StateUpdate:
        """Decrease the counter by the given amount (default 1). Returns
            the StateUpdate that should be propagated to the network.
        """
        assert type(amount) is int, 'amount must be int'
        assert amount > 0, 'amount must be positive'

        state_update = StateUpdate(
            self.clock.uuid,
            self.clock.read(),
            (self.positive, self.negative + amount)
        )
        self.update(state_update)

        return state_update