from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    CTDataWrapper,
    DecimalWrapper,
    IntWrapper,
    NoneWrapper,
    RGAItemWrapper,
    StrWrapper,
)
from .errors import tert, vert
from .interfaces import (
    ClockProtocol,
    StateUpdateProtocol,
)
from .merkle import get_merkle_history, resolve_merkle_histories
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from packify import SerializableType, pack, unpack
from typing import Any, Callable, Type


class MVRegister:
    """Implements the Multi-Value Register CRDT."""
    name: SerializableType
    values: list[SerializableType]
    clock: ClockProtocol
    last_update: Any
    listeners: list[Callable]

    def __init__(self, name: SerializableType,
                 values: list[SerializableType] = [],
                 clock: ClockProtocol = None,
                 last_update: Any = None,
                 listeners: list[Callable] = None) -> None:
        """Initialize an MVRegister instance from name, values, clock,
            and last_update (all but the first are optional). Raises
            TypeError for invalid name, values, or clock.
        """
        if clock is None:
            clock = ScalarClock()
        if last_update is None:
            last_update = clock.default_ts

        tert(isinstance(name, SerializableType), f'name must be {SerializableType}')
        tert(isinstance(values, list), f'values must be list[{SerializableType}]')
        tert(isinstance(clock, ClockProtocol), 'clock must be ClockProtocol or None')
        tert(all([isinstance(v, SerializableType) for v in values]),
             f'values must be list[{SerializableType}]')
        if listeners is None:
            listeners = []
        tert(type(listeners) is list,
             "listeners must be list[Callable[[StateUpdateProtocol], None]]")
        for listener in listeners:
            tert(callable(listener),
                 "listeners must be list[Callable[[StateUpdateProtocol], None]]")

        self.name = name
        self.values = values
        self.clock = clock
        self.last_update = last_update
        self.listeners = listeners

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return pack([
            self.name,
            self.clock,
            self.last_update,
            self.values
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> MVRegister:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        name, clock, last_update, values = unpack(
            data, inject={**globals(), **inject}
        )
        return cls(name, values, clock, last_update)

    def read(self, inject: dict = {}) -> tuple[SerializableType]:
        """Return the eventually consistent data view."""
        return tuple([
            unpack(
                pack(value), inject={**globals(), **inject}
            )
            for value in self.values
        ])

    @classmethod
    def compare_values(cls, value1: SerializableType,
                       value2: SerializableType) -> bool:
        """Return True if value1 is greater than value2, else False."""
        return pack(value1) > pack(value2)

    def update(self, state_update: StateUpdateProtocol) -> MVRegister:
        """Apply an update and return self (monad pattern). Raises
            TypeError or ValueError for invalid state_update,
            state_update.clock_uuid, or state_update.data.
        """
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(isinstance(state_update.data, SerializableType),
            f'state_update.data must be SerializableType ({SerializableType})')

        self.invoke_listeners(state_update)

        # set the value if the update happens after current state
        if self.clock.is_later(state_update.ts, self.last_update):
            self.last_update = state_update.ts
            self.values = [state_update.data]

        if self.clock.are_concurrent(state_update.ts, self.last_update):
            # preserve all concurrent updates
            if state_update.data not in self.values:
                self.values.append(state_update.data)
                self.values.sort(key=lambda item: pack(item))

        self.clock.update(state_update.ts)

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        return (
            crc32(pack(self.last_update)),
            sum([crc32(pack(v)) for v in self.values]) % 2**32,
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: Type[StateUpdateProtocol] = StateUpdate
                ) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of update_class (StateUpdate by
            default) that will converge to the underlying data. Useful
            for resynchronization by replaying updates from divergent
            nodes.
        """
        if from_ts is not None and self.clock.is_later(from_ts, self.last_update):
            return tuple()
        if until_ts is not None and self.clock.is_later(self.last_update, until_ts):
            return tuple()

        return tuple([
            update_class(clock_uuid=self.clock.uuid, ts=self.last_update, data=v)
            for v in self.values
        ])

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

    def write(self, value: SerializableType, /, *,
              update_class: Type[StateUpdateProtocol] = StateUpdate
              ) -> StateUpdateProtocol:
        """Writes the new value to the register and returns an
            update_class (StateUpdate by default). Raises TypeError for
            invalid value.
        """
        tert(isinstance(value, SerializableType),
            f'value must be SerializableType ({SerializableType})')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=value
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
