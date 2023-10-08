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
from .lwwregister import LWWRegister
from .merkle import get_merkle_history, resolve_merkle_histories
from .orset import ORSet
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from binascii import crc32
from packify import SerializableType, pack, unpack
from typing import Any, Hashable, Type


class LWWMap:
    """Implements the Last Writer Wins Map CRDT.
        https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-l-w-w-map/index.html
    """
    names: ORSet
    registers: dict[SerializableType, LWWRegister]
    clock: ClockProtocol

    def __init__(self, names: ORSet = None, registers: dict = None,
                clock: ClockProtocol = None
    ) -> None:
        """Initialize an LWWMap from an ORSet of names, a list of
            LWWRegisters, and a shared clock. Raises TypeError or
            UsageError for invalid parameters.
        """
        tert(type(names) is ORSet or names is None,
            'names must be an ORSet or None')
        tert(type(registers) is dict or registers is None,
            'registers must be a dict mapping names to LWWRegisters or None')
        tert(isinstance(clock, ClockProtocol) or clock is None,
            'clock must be a ClockProtocol or None')

        names = ORSet() if names is None else names
        registers = {} if registers is None else registers
        clock = ScalarClock() if clock is None else clock

        names.clock = clock

        for name in registers:
            tressa(name in names.observed or name in names.removed,
                'each register name must be in the names ORSet')
            tert(type(registers[name]) is LWWRegister,
                'each element of registers must be an LWWRegister')
            registers[name].clock = clock

        self.names = names
        self.registers = registers
        self.clock = clock

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string. Raises
            packify.UsageError on failure.
        """
        return pack([
            self.clock,
            self.names,
            self.registers,
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> LWWMap:
        """Unpack the data bytes string into an instance. Raises
            packify.UsageError or ValueError on failure.
        """
        clock, names, registers = unpack(data, inject={**globals(), **inject})
        return cls(names, registers, clock)

    def read(self, inject: dict = {}) -> dict:
        """Return the eventually consistent data view."""
        result = {}

        for name in self.names.read():
            result[name] = self.registers[name].read(inject=inject)

        return result

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> LWWMap:
        """Apply an update and return self (monad pattern). Raises
            TypeError or ValueError for invalid state_update.
        """
        tert(isinstance(state_update, StateUpdateProtocol),
            'state_update must be instance implementing StateUpdateProtocol')
        vert(state_update.clock_uuid == self.clock.uuid,
            'state_update.clock_uuid must equal CRDT.clock.uuid')
        tert(type(state_update.data) is tuple,
            'state_update.data must be tuple of (str, Hashable, int, SerializableType)')
        vert(len(state_update.data) == 4,
            'state_update.data must be tuple of (str, Hashable, int, SerializableType)')

        op, name, writer, value = state_update.data
        tert(type(op) is str and op in ('o', 'r'),
            "state_update.data[0] must be str op one of ('o', 'r')")
        tert(isinstance(name, Hashable),
            'state_update.data[1] must be Hashable name')
        tert(isinstance(name, SerializableType),
            'state_update.data[1] must be SerializableType name')
        tert(isinstance(writer, SerializableType),
            f'state_update.data[2] must be writer SerializableType ({SerializableType})')
        tert(isinstance(value, SerializableType),
            'state_update.data[3] must be SerializableType value')

        ts = state_update.ts
        update_class = state_update.__class__

        if op == 'o':
            # try to add to the names ORSet
            self.names.update(update_class(self.clock.uuid, ts, ('o', name)))

            # if register missing and name added successfully, create register
            if name not in self.registers and name in self.names.read():
                self.registers[name] = LWWRegister(name, value, self.clock, ts, writer)

        if op == 'r':
            # try to remove from the names ORSet
            self.names.update(update_class(self.clock.uuid, ts, ('r', name)))

            if name not in self.names.read() and name in self.registers:
                del self.registers[name]

        # if the register exists, update it
        if name in self.registers:
            self.registers[name].update(update_class(self.clock.uuid, ts, (writer, value)))

        return self

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[int]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        names_checksums = self.names.checksums(from_ts=from_ts, until_ts=until_ts)
        total_last_update = 0
        total_last_writer = 0
        total_register_crc32 = 0

        for name in self.registers:
            ts = self.registers[name].last_update
            if from_ts is not None:
                if self.clock.is_later(from_ts, ts):
                    continue
            if until_ts is not None:
                if self.clock.is_later(ts, until_ts):
                    continue
            total_register_crc32 += crc32(
                pack(self.registers[name].name) + pack(self.registers[name].value)
            )
            total_last_update += crc32(pack(self.registers[name].last_update))
            total_last_writer += crc32(pack(self.registers[name].last_writer))

        return (
            total_last_update % 2**32,
            total_last_writer % 2**32,
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
                    data=(update.data[0], name, register_update.data[0], register_update.data[1])
                ))
            else:
                history.append(update_class(
                    clock_uuid=update.clock_uuid,
                    ts=update.ts,
                    data=(update.data[0], name, 0, None)
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

    def set(self, name: Hashable, value: SerializableType,
                writer: SerializableType, /, *,
                update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Extends the dict with name: value. Returns an update_class
            (StateUpdate by default) that should be propagated to all
            nodes. Raises TypeError for invalid name, value, or writer.
        """
        tert(isinstance(name, Hashable),
            'name must be a Hashable')
        tert(isinstance(name, SerializableType),
            f'name must be a SerializableType ({SerializableType})')
        tert(isinstance(value, SerializableType),
            f'value must be a SerializableType ({SerializableType})')
        tert(isinstance(writer, SerializableType),
               f'writer must be a SerializableType ({SerializableType})')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('o', name, writer, value)
        )
        self.update(state_update)

        return state_update

    def unset(self, name: Hashable, writer: SerializableType, /, *,
              update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:
        """Removes the key name from the dict. Returns a StateUpdate.
            Raises TypeError for invalid name or writer.
        """
        tert(isinstance(name, Hashable),
            'name must be a Hashable')
        tert(isinstance(name, SerializableType),
            f'name must be a SerializableType ({SerializableType})')
        tert(isinstance(writer, SerializableType),
               f'writer must be a SerializableType ({SerializableType})')

        state_update = update_class(
            clock_uuid=self.clock.uuid,
            ts=self.clock.read(),
            data=('r', name, writer, None)
        )
        self.update(state_update)

        return state_update
