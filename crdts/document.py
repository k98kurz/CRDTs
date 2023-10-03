from __future__ import annotations
from .causaltree import CausalTree, CTDataWrapper
from .counter import Counter
from .errors import tressa
from .fiarray import FIArray, FIAItemWrapper
from .gset import GSet
from .interfaces import (
    ClockProtocol,
    CRDTProtocol,
    StateUpdateProtocol,
    SerializableType,
)
from .lwwmap import LWWMap, LWWRegister, ORSet
from .mvmap import MVMap, MVRegister
from .pncounter import PNCounter
from .rgarray import RGArray, RGAItemWrapper
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from dataclasses import dataclass, field
from enum import Enum
from packify import pack, unpack
from types import NoneType
from typing import Any
from uuid import uuid4


class CRDT(Enum):
    Counter = b'c'
    PNCounter = b'C'
    GSet = b's'
    ORSet = b'S'
    CounterSet = b'k'
    LWWRegister = b'l'
    LWWMap = b'L'
    MVRegister = b'm'
    MVMap = b'M'
    RGArray = b'R'
    FIArray = b'F'
    CausalTree = b'T'


@dataclass
class Identifier:
    uuid: bytes = field()
    type_id: bytes = field()
    previous: Identifier = field(default=None)

    def pack(self) -> bytes:
        return pack([
            self.type_id,
            self.uuid,
            self.previous
        ])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> Identifier:
        type_id, uuid, previous = unpack(
            data, inject={**globals(), **inject}
        )
        return cls(type_id=type_id, uuid=uuid, previous=previous)

    def __hash__(self) -> int:
        return hash((self.uuid, self.type_id, self.previous))

    def __eq__(self, other: Identifier) -> bool:
        return type(self) == type(other) and self.uuid == other.uuid and \
              self.type_id == other.type_id and self.previous == other.previous


class Document:
    clock: ClockProtocol
    elements: ORSet
    parts: dict[Identifier, CRDTProtocol]

    def __init__(self, uuid: bytes = None, clock: ClockProtocol = None,
                 elements: ORSet = None,
                 parts: dict[Identifier, CRDTProtocol] = {}) -> None:
        if uuid is None or not isinstance(uuid, bytes):
            uuid = uuid4()
        if clock is None or not isinstance(clock, ClockProtocol):
            clock = ScalarClock(uuid=uuid)
        if elements is None or not isinstance(elements, ORSet):
            elements = ORSet(clock=clock)
        if not isinstance(parts, dict):
            parts = {}
        for k, v in parts.items():
            tressa(isinstance(k, Identifier),
                   'parts must be dict[Identifier, CRDTProtocol]')
            tressa(isinstance(v, CRDTProtocol),
                   'parts must be dict[Identifier, CRDTProtocol]')

        self.clock = clock
        self.elements = elements
        self.parts = parts

    def pack(self) -> bytes:
        ...

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> Document:
        ...

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> Document:
        ...

    def update_part(self, part: Identifier, update: StateUpdateProtocol, /, *,
                    update_class: type[StateUpdateProtocol] = StateUpdate,
                    inject: dict = {}) -> StateUpdateProtocol:
        ...

    def history(self) -> tuple[StateUpdateProtocol]:
        ...
