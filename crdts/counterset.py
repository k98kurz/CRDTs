from __future__ import annotations
from .errors import tressa
from .interfaces import ClockProtocol, DataWrapperProtocol, StateUpdateProtocol
from .orset import ORSet
from .pncounter import PNCounter
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from types import NoneType
from typing import Any
from uuid import uuid4


SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType

class CounterSet:
    clock: ClockProtocol
    counter_ids: ORSet
    counters: dict[SerializableType, PNCounter]

    def __init__(self, uuid: bytes = None, clock: ClockProtocol = None,
                 counter_ids: ORSet = None,
                 counters: dict[SerializableType, PNCounter] = None) -> None:
        if uuid is None or not isinstance(uuid, bytes):
            uuid = uuid4()
        if clock is None or not isinstance(clock, ClockProtocol):
            clock = ScalarClock(uuid=uuid)
        if counter_ids is None or not isinstance(counter_ids, ORSet):
            counter_ids = ORSet(clock=clock)
        if not isinstance(counters, dict):
            counters = {}
        for k, v in counters.items():
            tressa(isinstance(k, SerializableType),
                   'counters must be dict[SerializableType, PNCounter]')
            tressa(isinstance(v, PNCounter),
                   'counters must be dict[SerializableType, PNCounter]')

        self.clock = clock
        self.counter_ids = counter_ids
        self.counters = counters

    def pack(self) -> bytes:
        ...

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> CounterSet:
        ...

    def read(self, /, *, inject: dict = {}) -> int:
        total = 0
        for _, counter in self.counters.items():
            total += counter.read()
        return total

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> CounterSet:
        ...

    def history(self) -> tuple[StateUpdateProtocol]:
        ...

    def increase(self, amount: int = 1, counter_id: bytes = b'', /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        ...

    def decrease(self, amount: int = 1, counter_id: bytes = b'', /, *,
                  update_class: type[StateUpdateProtocol] = StateUpdate,
                  inject: dict = {}) -> StateUpdateProtocol:
        ...
