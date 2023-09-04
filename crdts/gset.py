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
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from dataclasses import dataclass, field
from typing import Any, Hashable
import json
import struct


@dataclass
class GSet:
    """Implements the Grow-only Set (GSet) CRDT."""
    members: set[DataWrapperProtocol] = field(default_factory=set)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    update_history: dict[DataWrapperProtocol, StateUpdateProtocol] = field(default_factory=dict)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        members = [m.__class__.__name__ + '_' + m.pack().hex() for m in self.members]
        members = bytes(json.dumps(members, separators=(',', ':')), 'utf-8')
        clock_size, set_size = len(clock), len(members)
        history = bytes(json.dumps({
            k.__class__.__name__ + '_' + k.pack().hex(): v.__class__.__name__ + '_' + v.pack().hex()
            for k,v in self.update_history.items()
        }), 'utf-8')
        history_size = len(history)

        return struct.pack(
            f'!III{clock_size}s{set_size}s{history_size}s',
            clock_size,
            set_size,
            history_size,
            clock,
            members,
            history
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> GSet:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 8, 'data must be more than 8 bytes')
        dependencies = {**globals(), **inject}

        clock_size, set_size, history_size, data = struct.unpack(
            f'!III{len(data)-12}s',
            data
        )
        clock, set_bytes, history_bytes = struct.unpack(
            f'!{clock_size}s{set_size}s{history_size}s',
            data
        )

        # parse clock and members
        clock_class, _, clock = clock.partition(b'_')
        clock_class = str(bytes.fromhex(str(clock_class, 'utf-8')), 'utf-8')
        tressa(clock_class in dependencies, f'cannot find {clock_class}')
        tressa(hasattr(dependencies[clock_class], 'unpack'),
            f'{clock_class} missing unpack method')
        clock = dependencies[clock_class].unpack(clock)
        _members: list[str] = json.loads(str(set_bytes, 'utf-8'))
        members = []
        for m in _members:
            class_name, data = m.split('_')
            tressa(class_name in dependencies, f'{class_name} not found')
            members.append(dependencies[class_name].unpack(bytes.fromhex(data)))

        # parse history
        _history = json.loads(history_bytes)
        history = {}
        for k,v in _history.items():
            class_name, data = k.split('_')
            tressa(class_name in dependencies, f'{class_name} not found')
            key = dependencies[class_name].unpack(bytes.fromhex(data))
            update_class_name, data = v.split('_')
            tressa(update_class_name in dependencies, f'{update_class_name} not found')
            history[key] = dependencies[update_class_name].unpack(bytes.fromhex(data))

        return cls(members=set(members), clock=clock, update_history=history)

    def read(self) -> set:
        """Return the eventually consistent data view."""
        return self.members.copy()

    def update(self, state_update: StateUpdateProtocol) -> GSet:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(isinstance(state_update.data, DataWrapperProtocol),
            'state_update.data must be instance implementing DataWrapperProtocol')

        if state_update.data not in self.members:
            self.members.add(state_update.data)

        self.clock.update(state_update.ts)
        self.update_history[state_update.data] = state_update

        return self

    def checksums(self, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure. If from_ts and/or
            until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        total_crc32 = 0
        updates = []
        for member, state_update in self.update_history.items():
            if from_ts is not None and until_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts) or \
                    self.clock.is_later(state_update.ts, until_ts):
                    continue
            elif from_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts):
                    continue
            elif until_ts is not None:
                if self.clock.is_later(state_update.ts, until_ts):
                    continue
            updates.append(member)

        for member in updates:
            total_crc32 += crc32(member.pack())

        return (
            self.clock.read() if until_ts is None else until_ts,
            len(updates),
            total_crc32 % 2**32,
        )

    def history(self, from_ts: Any = None, until_ts: Any = None) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes. If from_ts and/
            or until_ts are supplied, only those updates that are not
            outside of these temporal constraints will be included.
        """
        updates = []

        for member in self.members:
            state_update = self.update_history[member]
            if from_ts is not None and until_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts) or \
                    self.clock.is_later(state_update.ts, until_ts):
                    continue
            elif from_ts is not None:
                if self.clock.is_later(from_ts, state_update.ts):
                    continue
            elif until_ts is not None:
                if self.clock.is_later(state_update.ts, until_ts):
                    continue
            updates.append(state_update)

        return tuple(updates)

    def add(self, member: Hashable,
            update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Create, apply, and return a StateUpdate adding member to the set."""
        tressa(type(hash(member)) is int, 'member must be hashable')
        tressa(isinstance(member, DataWrapperProtocol),
            'member must be instance implementing DataWrapperProtocol')

        ts = self.clock.read()
        state_update = update_class(clock_uuid=self.clock.uuid, ts=ts, data=member)
        self.update(state_update)

        return state_update
