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
from typing import Any, Hashable, Optional
import json
import struct


@dataclass
class ORSet:
    """Implements the Observed Removed Set (ORSet) CRDT. Comprised of
        two Sets with a read method that removes the removed set members
        from the observed set. Add-biased. Note that int members are
        converted to str for json compatibility.
    """
    observed: set = field(default_factory=set)
    observed_metadata: dict = field(default_factory=dict)
    removed: set = field(default_factory=set)
    removed_metadata: dict = field(default_factory=dict)
    clock: ClockProtocol = field(default_factory=ScalarClock)
    cache: Optional[tuple] = field(default=None)

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        clock = bytes(bytes(self.clock.__class__.__name__, 'utf-8').hex(), 'utf-8')
        clock += b'_' + self.clock.pack()
        clock_size = len(clock)
        observed_metadata = {}
        removed_metadata = {}

        for member in self.observed_metadata:
            if isinstance(member, DataWrapperProtocol):
                key = member.__class__.__name__ + '_' + member.pack().hex()
            else:
                key = member
            observed_metadata[key] = self.observed_metadata[member]

        for member in self.removed_metadata:
            if isinstance(member, DataWrapperProtocol):
                key = member.__class__.__name__ + '_' + member.pack().hex()
            else:
                key = member
            removed_metadata[key] = self.removed_metadata[member]

        data = bytes(json.dumps(
            {
                'o': observed_metadata,
                'r': removed_metadata
            },
            separators=(',', ':'),
            sort_keys=True
        ), 'utf-8')

        return struct.pack(
            f'!I{clock_size}s{len(data)}s',
            clock_size,
            clock,
            data
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> ORSet:
        """Unpack the data bytes string into an instance."""
        tressa(type(data) is bytes, 'data must be bytes')
        tressa(len(data) > 19, 'data must be more than 19 bytes')
        dependencies = {**globals(), **inject}

        clock_size, _ = struct.unpack(f'!I{len(data)-4}s', data)
        _, clock, sets = struct.unpack(
            f'!I{clock_size}s{len(data)-4-clock_size}s',
            data
        )

        # parse clock
        clock_class, _, clock = clock.partition(b'_')
        clock_class = str(bytes.fromhex(str(clock_class, 'utf-8')), 'utf-8')
        tressa(clock_class in dependencies, f'cannot find {clock_class}')
        tressa(hasattr(dependencies[clock_class], 'unpack'),
            f'{clock_class} missing unpack method')
        clock = dependencies[clock_class].unpack(clock)

        # parse sets
        sets = json.loads(str(sets, 'utf-8'))
        observed_metadata = {}
        removed_metadata = {}
        o_metadata = sets['o']
        r_metadata = sets['r']

        for member in o_metadata:
            if len(member.split('_')) == 2 and member.split('_')[0] in dependencies:
                member_class, member_hex = member.split('_')
                key = dependencies[member_class].unpack(bytes.fromhex(member_hex))
                observed_metadata[key] = o_metadata[member]
            else:
                observed_metadata[member] = o_metadata[member]

        for member in r_metadata:
            if len(member.split('_')) == 2 and member.split('_')[0] in dependencies:
                member_class, member_hex = member.split('_')
                key = dependencies[member_class].unpack(bytes.fromhex(member_hex))
                removed_metadata[key] = r_metadata[member]
            else:
                removed_metadata[member] = r_metadata[member]

        observed = set(observed_metadata.keys())
        removed = set(removed_metadata.keys())

        return cls(observed, observed_metadata, removed, removed_metadata, clock)

    def read(self) -> set:
        """Return the eventually consistent data view."""
        if self.cache is not None:
            if self.cache[0] == self.clock.read():
                return self.cache[1]

        difference = self.observed.difference(self.removed)
        self.cache = (self.clock.read(), difference)

        return difference

    def update(self, state_update: StateUpdateProtocol) -> ORSet:
        """Apply an update and return self (monad pattern)."""
        tressa(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        tressa(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tressa(type(state_update.data) is tuple,
            'state_update.data must be tuple')
        tressa(len(state_update.data) == 2,
            'state_update.data must be 2 long')
        tressa(state_update.data[0] in ('o', 'r'),
            'state_update.data[0] must be in (\'o\', \'r\')')
        tressa(type(hash(state_update.data[1])) is int,
            'state_update.data[1] must be hashable')

        op, member = state_update.data
        member = member.hex() if type(member) is bytes else member
        ts = state_update.ts

        if op == 'o':
            # add to observed
            if member not in self.removed or (
                member in self.removed_metadata and
                not self.clock.is_later(self.removed_metadata[member], ts)
            ):
                self.observed.add(member)
                oldts = self.observed_metadata[member] if member in self.observed_metadata else self.clock.default_ts
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
                oldts = self.removed_metadata[member] if member in self.removed_metadata else self.clock.default_ts
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
        observed, removed = [], []
        for member, ts in self.observed_metadata.items():
            if from_ts is not None and until_ts is not None:
                if self.clock.is_later(from_ts, ts) or self.clock.is_later(ts, until_ts):
                    continue
            elif from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            elif until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue
            observed.append(member)

        for member, ts in self.removed_metadata.items():
            if from_ts is not None and until_ts is not None:
                if self.clock.is_later(from_ts, ts) or self.clock.is_later(ts, until_ts):
                    continue
            elif from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            elif until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue
            removed.append(member)

        total_observed_crc32 = 0
        for o in observed:
            if type(o) is str:
                total_observed_crc32 += crc32(bytes(o, 'utf-8'))
            else:
                total_observed_crc32 += crc32(bytes(str(o), 'utf-8'))

        total_removed_crc32 = 0
        for r in removed:
            if type(r) is str:
                total_removed_crc32 += crc32(bytes(r, 'utf-8'))
            else:
                total_removed_crc32 += crc32(bytes(str(r), 'utf-8'))

        return (
            len(observed),
            len(removed),
            total_observed_crc32 % 2**32,
            total_removed_crc32 % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying updates from divergent
            nodes.
        """
        updates = []

        for o in self.observed:
            updates.append(
                update_class(
                    clock_uuid=self.clock.uuid,
                    ts=self.observed_metadata[o],
                    data=('o', o)
                )
            )

        for r in self.removed:
            updates.append(
                update_class(
                    clock_uuid=self.clock.uuid,
                    ts=self.removed_metadata[r],
                    data=('r', r)
                )
            )

        return tuple(updates)

    def observe(self, member: Hashable, /, *,
                update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Adds the given member to the observed set."""
        tressa(type(hash(member)) is int, 'member must be Hashable')

        member = str(member) if type(member) is int else member
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('o', member)
        )

        self.update(state_update)

        return state_update

    def remove(self, member: Hashable, /, *,
               update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Adds the given member to the removed set."""
        tressa(type(hash(member)) is int, 'member must be Hashable')

        member = str(member) if type(member) is int else member
        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('r', member)
        )

        self.update(state_update)

        return state_update
