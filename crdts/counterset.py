from __future__ import annotations
from .errors import tressa, tert, vert
from .interfaces import ClockProtocol, StateUpdateProtocol
from .merkle import get_merkle_history, resolve_merkle_histories
from .gset import GSet
from .pncounter import PNCounter
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from packify import SerializableType, pack, unpack
from typing import Any, Hashable
from uuid import uuid4



class CounterSet:
    """A CRDT for computing a composite Counter. Use with multiple
        replicas where each replica has a single counter_id.
    """
    clock: ClockProtocol
    counter_ids: GSet
    counters: dict[SerializableType, PNCounter]

    def __init__(self, uuid: bytes = None, clock: ClockProtocol = None,
                 counter_ids: GSet = None,
                 counters: dict[SerializableType, PNCounter] = None) -> None:
        """Initialize a CounterSet from a uuid, a clock, a GSet, and a
            dict mapping names to PNCounters (all parameters optional).
        """
        if uuid is None or not isinstance(uuid, bytes):
            uuid = uuid4().bytes
        if clock is None or not isinstance(clock, ClockProtocol):
            clock = ScalarClock(uuid=uuid)
        if counter_ids is None or not isinstance(counter_ids, GSet):
            counter_ids = GSet(clock=clock)
        if not isinstance(counters, dict):
            counters = {}
        for k, v in counters.items():
            tert(isinstance(k, SerializableType),
                   'counters must be dict[SerializableType, PNCounter]')
            tert(isinstance(v, PNCounter),
                   'counters must be dict[SerializableType, PNCounter]')

        self.clock = clock
        self.counter_ids = counter_ids
        self.counters = counters

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return pack([
            self.clock,
            self.counter_ids,
            self.counters
        ])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> CounterSet:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        clock, counter_ids, counters = unpack(data, inject={**globals(), **inject})
        return cls(
            clock=clock,
            counter_ids=counter_ids,
            counters=counters,
        )

    def read(self, /, *, inject: dict = {}) -> int:
        """Return the eventually consistent data view. Cannot be used for
            preparing remove updates.
        """
        total = 0
        for _, counter in self.counters.items():
            total += counter.read()
        return total

    def read_full(self, /, *, inject: dict = {}) -> dict[SerializableType, int]:
        """Return the full, eventually consistent dict mapping the
            counter ids to their int states.
        """
        return {
            k: v.read()
            for k,v in self.counters.items()
            if k in self.counter_ids.read(inject=inject)
        }

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> CounterSet:
        """Apply an update and return self (monad pattern). Raises
            TypeError or ValueError for invalid state_update.clock_uuid
            or state_update.data.
        """
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(type(state_update.data) is tuple,
            'state_update.data must be tuple of [Hashable and SerializableType, int, int]')
        vert(len(state_update.data) == 3,
            'state_update.data must be tuple of [Hashable and SerializableType, int, int]')
        tert(isinstance(state_update.data[0], Hashable),
            'state_update.data must be tuple of [Hashable and SerializableType, int, int]')
        tert(isinstance(state_update.data[0], SerializableType),
            'state_update.data must be tuple of [Hashable and SerializableType, int, int]')
        tert(type(state_update.data[1]) is int,
            'state_update.data must be tuple of [Hashable and SerializableType, int, int]')
        tert(type(state_update.data[2]) is int,
            'state_update.data must be tuple of [Hashable and SerializableType, int, int]')

        counter_id, positive, negative = state_update.data

        self.counter_ids.update(state_update.__class__(
            clock_uuid=state_update.clock_uuid,
            ts=state_update.ts,
            data=counter_id,
        ))

        if counter_id not in self.counters:
            self.counters[counter_id] = PNCounter(clock=self.clock)

        self.counters[counter_id].update(state_update.__class__(
            clock_uuid=state_update.clock_uuid,
            ts=state_update.ts,
            data=(positive, negative)
        ))

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

        updates = []

        for counter_id in self.counter_ids.members:
            positive, negative = 0, 0
            if counter_id in self.counters:
                positive = self.counters[counter_id].positive
                negative = self.counters[counter_id].negative
            updates.append(update_class(
                clock_uuid=self.clock.uuid,
                ts=self.counter_ids.metadata[counter_id],
                data=(counter_id, positive, negative)
            ))

        return tuple(updates)

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[Any]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        checksums = list(self.counter_ids.checksums())
        for counter_id in self.counters:
            checksums.extend(self.counters[counter_id].checksums())

        return tuple(checksums)

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
            synchronization. Raises TypeError or ValueError for invalid
            input.
        """
        return resolve_merkle_histories(self, history=history)

    def increase(self, counter_id: Hashable = b'', amount: int = 1, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        """Increase the PNCounter with the given counter_id by the given
            amount. Returns the update_class (StateUpdate by default)
            that should be propagated to the network. Raises TypeError
            or ValueError on invalid amount or counter_id.
        """
        tert(isinstance(counter_id, Hashable), 'counter_id must be Hashable')
        tert(isinstance(counter_id, SerializableType), 'counter_id must be Hashable')
        tert(type(amount) is int, 'amount must be int > 0')
        vert(amount > 0, 'amount must be int > 0')

        counter = self.counters.get(counter_id, None)
        if not counter:
            counter = PNCounter()
            counter.clock.uuid = self.clock.uuid

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(counter_id, counter.positive + amount, counter.negative)
        )
        self.update(state_update)
        return state_update

    def decrease(self, counter_id: Hashable = b'', amount: int = 1, /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        """Decrease the PNCounter with the given counter_id by the given
            amount. Returns the update_class (StateUpdate by default)
            that should be propagated to the network. Raises TypeError
            or ValueError on invalid amount or counter_id.
        """
        tert(isinstance(counter_id, Hashable), 'counter_id must be Hashable')
        tert(isinstance(counter_id, SerializableType), 'counter_id must be Hashable')
        tert(type(amount) is int, 'amount must be int > 0')
        vert(amount > 0, 'amount must be int > 0')

        counter = self.counters.get(counter_id, None)
        if not counter:
            counter = PNCounter()
            counter.clock.uuid = self.clock.uuid

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=(counter_id, counter.positive, counter.negative + amount)
        )
        self.update(state_update)
        return state_update
