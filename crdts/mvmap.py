from __future__ import annotations
from .datawrappers import (
    BytesWrapper,
    StrWrapper,
    IntWrapper,
    DecimalWrapper,
    CTDataWrapper,
    NoneWrapper,
)
from .errors import tressa, tert, vert
from .interfaces import ClockProtocol, StateUpdateProtocol
from .merkle import get_merkle_history, resolve_merkle_histories
from .mvregister import MVRegister
from .orset import ORSet
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from packify import pack, unpack, SerializableType
from typing import Any, Callable, Type


class MVMap:
    """Implements a Map CRDT using Multi-Value Registers.
        https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-m-v-map/index.html
    """
    names: ORSet
    registers: dict[SerializableType, MVRegister]
    clock: ClockProtocol
    listeners: list[Callable]

    def __init__(self, names: ORSet = None, registers: dict = None,
                clock: ClockProtocol = None, listeners: list[Callable] = None
    ) -> None:
        """Initialize an MVMap from an ORSet of names, a list of
            MVRegisters, and a shared clock. Raises TypeError or
            UsageError for invalid arguments.
        """
        tert(type(names) is ORSet or names is None,
            'names must be an ORSet or None')
        tert(type(registers) is dict or registers is None,
            'registers must be a dict mapping names to MVRegisters or None')
        tert(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')
        if listeners is None:
            listeners = []
        tert(type(listeners) is list,
             "listeners must be list[Callable[[StateUpdateProtocol], None]]")
        for listener in listeners:
            tert(callable(listener),
                 "listeners must be list[Callable[[StateUpdateProtocol], None]]")

        names = ORSet() if names is None else names
        registers = {} if registers is None else registers
        clock = ScalarClock() if clock is None else clock

        names.clock = clock

        for name in registers:
            tressa(name in names.observed or name in names.removed,
                'each register name must be in the names ORSet')
            tert(type(registers[name]) is MVRegister,
                'each element of registers must be an MVRegister')
            registers[name].clock = clock

        self.names = names
        self.registers = registers
        self.clock = clock
        self.listeners = listeners

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return pack([
            self.clock,
            self.names,
            self.registers
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> MVMap:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        dependencies = {**globals(), **inject}
        clock, names, registers = unpack(data, inject=dependencies)
        return cls(names, registers, clock)

    def read(self) -> dict:
        """Return the eventually consistent data view."""
        result = {}

        for name in self.names.read():
            result[name] = self.registers[name].read()

        return result

    def update(self, state_update: StateUpdateProtocol) -> MVMap:
        """Apply an update and return self (monad pattern). Raises
            TypeError or ValueError for invalid state_update.clock_uuid
            or state_update.data.
        """
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(type(state_update.data) is tuple,
            f'state_update.data must be tuple of (str, SerializableType ({SerializableType}), SerializableType ({SerializableType}))')
        vert(len(state_update.data) == 3,
            f'state_update.data must be tuple of (str, SerializableType ({SerializableType}), SerializableType ({SerializableType}))')

        op, name, value = state_update.data
        vert(op in ('o', 'r'),
            'state_update.data[0] must be str op one of (\'o\', \'r\')')
        tert(isinstance(name, SerializableType),
            f'state_update.data[1] must be SerializableType ({SerializableType}) name')
        tert(isinstance(value, SerializableType),
            f'state_update.data[2] must be SerializableType ({SerializableType}) value')

        self.invoke_listeners(state_update)
        ts = state_update.ts

        if op == 'o':
            # try to add to the names ORSet
            self.names.update(StateUpdate(self.clock.uuid, ts, ('o', name)))

            # if register missing and name added successfully, create register
            if name not in self.registers and name in self.names.read():
                self.registers[name] = MVRegister(name, [value], self.clock, ts)

        if op == 'r':
            # try to remove from the names ORSet
            self.names.update(StateUpdate(self.clock.uuid, ts, ('r', name)))

            if name not in self.names.read() and name in self.registers:
                del self.registers[name]

        # if the register exists, update it
        if name in self.registers:
            self.registers[name].update(StateUpdate(self.clock.uuid, ts, value))

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        names_checksums = self.names.checksums(from_ts=from_ts, until_ts=until_ts)
        total_last_update = 0
        total_register_crc32 = 0

        for name in self.registers:
            ts = self.registers[name].last_update
            if from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue

            packed = pack(self.registers[name].name)
            packed += pack([v for v in self.registers[name].values])
            total_register_crc32 += crc32(packed)
            total_last_update += crc32(pack(self.registers[name].last_update))

        return (
            total_last_update % 2**32,
            total_register_crc32 % 2**32,
            *names_checksums
        )

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdateProtocols that will
            converge to the underlying data. Useful for
            resynchronization by replaying updates from divergent nodes.
        """
        registers_history: dict[SerializableType, tuple[StateUpdateProtocol]] = {}
        orset_history = self.names.history(
            from_ts=from_ts,
            until_ts=until_ts,
            update_class=update_class,
        )
        history = []

        for name in self.registers:
            registers_history[name] = self.registers[name].history(
                from_ts=from_ts,
                until_ts=until_ts,
                update_class=update_class,
            )

        for update in orset_history:
            name = update.data[1]
            if name in registers_history:
                register_update = registers_history[name][0]
                update_class = register_update.__class__
                history.append(update_class(
                    clock_uuid=update.clock_uuid,
                    ts=register_update.ts,
                    data=(update.data[0], name, register_update.data)
                ))
            else:
                history.append(update_class(
                    clock_uuid=update.clock_uuid,
                    ts=update.ts,
                    data=(update.data[0], name, NoneWrapper())
                ))

        return tuple(history)

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

    def resolve_merkle_histories(self, history: list[bytes, list[bytes]]) -> list[bytes]:
        """Accept a history of form [root, leaves] from another node.
            Return the leaves that need to be resolved and merged for
            synchronization. Raises TypeError or ValueError for invalid
            input.
        """
        return resolve_merkle_histories(self, history=history)

    def set(self, name: SerializableType, value: SerializableType, /,
                *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Extends the dict with name: value. Returns an update_class
            (StateUpdate by default) that should be propagated to all
            nodes. Raises TypeError for invalid name or value.
        """
        tert(isinstance(name, SerializableType),
            f'name must be a SerializableType ({SerializableType})')
        tert(isinstance(value, SerializableType),
            f'value must be a SerializableType ({SerializableType}) or None')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('o', name, value)
        )
        self.update(state_update)

        return state_update

    def unset(self, name: SerializableType, /, *,
              update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Removes the key name from the dict. Returns a StateUpdate.
            Raises TypeError for invalid name.
        """
        tert(isinstance(name, SerializableType),
            f'name must be a SerializableType ({SerializableType})')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('r', name, NoneWrapper())
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
