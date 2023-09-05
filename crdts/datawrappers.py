from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from .errors import tressa
from .interfaces import DataWrapperProtocol
from .serialization import serialize_part, deserialize_part
from types import NoneType
from typing import Any
import struct


SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType

@dataclass
class StrWrapper:
    value: str

    def __to_tuple__(self) -> tuple:
        return (self.__class__.__name__, self.value)

    def __hash__(self) -> int:
        return hash(self.__to_tuple__())

    def __eq__(self, other: DataWrapperProtocol) -> bool:
        return type(self) == type(other) and hash(self) == hash(other)

    def __ne__(self, other: DataWrapperProtocol) -> bool:
        return not self.__eq__(other)

    def __gt__(self, other: DataWrapperProtocol) -> bool:
        return self.value > other.value

    def __ge__(self, other: DataWrapperProtocol) -> bool:
        return self.value >= other.value

    def __lt__(self, other: DataWrapperProtocol) -> bool:
        return other.value > self.value

    def __le__(self, other: DataWrapperProtocol) -> bool:
        return other.value >= self.value

    def pack(self) -> bytes:
        data = bytes(self.value, 'utf-8')
        return struct.pack(f'!{len(data)}s', data)

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> StrWrapper:
        return cls(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8'))


class BytesWrapper(StrWrapper):
    value: bytes

    def __init__(self, value: bytes) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"BytesWrapper(value={self.value.hex()})"

    def pack(self) -> bytes:
        return struct.pack(f'!{len(self.value)}s', self.value)

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> BytesWrapper:
        return cls(struct.unpack(f'!{len(data)}s', data)[0])


class CTDataWrapper:
    value: SerializableType
    uuid: bytes
    parent_uuid: bytes
    visible: bool

    def __init__(self, value: SerializableType, uuid: bytes, parent_uuid: bytes,
                 visible: bool = True) -> None:
        tressa(isinstance(value, SerializableType),
               'value must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')
        tressa(type(uuid) is bytes, 'uuid must be bytes')
        tressa(type(parent_uuid) is bytes, 'parent_uuid must be bytes')
        tressa(type(visible) is bool, 'visible must be bool')

        self.value = value
        self.uuid = uuid
        self.parent_uuid = parent_uuid
        self.visible = visible

    def __to_tuple__(self) -> tuple:
        return (self.__class__.__name__, self.value, self.uuid, self.parent_uuid, self.visible)

    def __repr__(self) -> str:
        return f"CTDataWrapper(value={self.value}, uuid={self.uuid.hex()}, " + \
            f"parent_uuid={self.parent_uuid.hex()}, visible={self.visible})"

    def __hash__(self) -> int:
        return hash(self.__to_tuple__())

    def __eq__(self, other: CTDataWrapper) -> bool:
        return type(self) == type(other) and hash(self) == hash(other)

    def __ne__(self, other: CTDataWrapper) -> bool:
        return not self.__eq__(other)

    def __gt__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() > other.__to_tuple__()

    def __ge__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() >= other.__to_tuple__()

    def __lt__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() < other.__to_tuple__()

    def __le__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() <= other.__to_tuple__()

    def children(self) -> set[CTDataWrapper]:
        if hasattr(self, '_children'):
            return self._children
        return set()

    def add_child(self, child: CTDataWrapper):
        tressa(isinstance(child, CTDataWrapper), 'child must be CTDataWrapper')
        if not hasattr(self, '_children'):
            self._children = set()
        self._children.add(child)
        if child.parent_uuid != self.uuid:
            child.parent_uuid = self.uuid

    def parent(self) -> CTDataWrapper|None:
        if hasattr(self, '_parent'):
            return self._parent

    def set_parent(self, parent: CTDataWrapper):
        tressa(isinstance(parent, CTDataWrapper), 'parent must be CTDataWrapper')
        self._parent = parent
        if self.parent_uuid != parent.uuid:
            self.parent_uuid = parent.uuid

    def pack(self) -> bytes:
        return serialize_part([
            self.value,
            self.uuid,
            self.parent_uuid,
            int(self.visible)
        ])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> CTDataWrapper:
        dependencies = {**globals(), **inject}
        value, uuid, parent_uuid, visible = deserialize_part(data, inject=dependencies)
        return cls(
            value=value,
            uuid=uuid,
            parent_uuid=parent_uuid,
            visible=bool(visible)
        )


class DecimalWrapper(StrWrapper):
    value: Decimal

    def __init__(self, value: Decimal) -> None:
        self.value = value

    def pack(self) -> bytes:
        return struct.pack(f'!{len(str(self.value))}s', bytes(str(self.value), 'utf-8'))

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> DecimalWrapper:
        return cls(Decimal(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8')))


class IntWrapper(DecimalWrapper):
    value: int

    def __init__(self, value: int) -> None:
        tressa(type(value) is int, 'value must be int')
        self.value = value

    def pack(self) -> bytes:
        return struct.pack('!i', self.value)

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> IntWrapper:
        return cls(struct.unpack('!i', data)[0])


class RGAItemWrapper(StrWrapper):
    value: DataWrapperProtocol
    ts: DataWrapperProtocol
    writer: int

    def __init__(self, value: DataWrapperProtocol, ts: DataWrapperProtocol,
                 writer: int) -> None:
        tressa(isinstance(value, DataWrapperProtocol), 'value must be DataWrapperProtocol')
        tressa(isinstance(ts, DataWrapperProtocol), 'ts must be DataWrapperProtocol')
        tressa(type(writer) is int, 'writer must be int')

        self.value = value
        self.ts = ts
        self.writer = writer

    def pack(self) -> bytes:
        packed_val = bytes(self.value.__class__.__name__, 'utf-8').hex() + '_'
        packed_val = bytes(packed_val, 'utf-8') + self.value.pack()
        packed_ts = bytes(self.ts.__class__.__name__, 'utf-8').hex() + '_'
        packed_ts = bytes(packed_ts, 'utf-8') + self.ts.pack()
        return struct.pack(
            f'!II{len(packed_val)}s{len(packed_ts)}sI',
            len(packed_val),
            len(packed_ts),
            packed_val,
            packed_ts,
            self.writer
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> RGAItemWrapper:
        dependencies = {**globals(), **inject}
        packed_len, ts_len, _ = struct.unpack(f'!II{len(data)-8}s', data)
        _, packed, ts, writer = struct.unpack(f'!8s{packed_len}s{ts_len}sI', data)

        # parse item value
        classname, _, packed = packed.partition(b'_')
        classname = str(bytes.fromhex(str(classname, 'utf-8')), 'utf-8')
        tressa(classname in dependencies,
               f'{classname} must be accessible from globals() or injected')
        tressa(hasattr(dependencies[classname], 'unpack'),
            f'{classname} missing unpack method')
        item = dependencies[classname].unpack(packed)

        # parse ts
        classname, _, ts = ts.partition(b'_')
        classname = str(bytes.fromhex(str(classname, 'utf-8')), 'utf-8')
        tressa(classname in dependencies,
               f'{classname} must be accessible from globals() or injected')
        tressa(hasattr(dependencies[classname], 'unpack'),
            f'{classname} missing unpack method')
        ts = dependencies[classname].unpack(ts)

        return cls(item, ts, writer)


@dataclass
class NoneWrapper:
    """Implementation of DataWrapperProtocol for use in removing
        registers from the LWWMap by setting them to a None value.
    """
    value: NoneType = field(default=None)

    def __hash__(self) -> int:
        return hash(None)

    def __eq__(self, other) -> bool:
        return type(self) == type(other)

    def __gt__(self, other) -> bool:
        return False

    def __ge__(self, other) -> bool:
        return False

    def __lt__(self, other) -> bool:
        return False

    def __le__(self, other) -> bool:
        return False

    def pack(self) -> bytes:
        return b''

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> NoneWrapper:
        return cls()
