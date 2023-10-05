from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from .errors import tressa
from .interfaces import DataWrapperProtocol
from packify import SerializableType, pack, unpack
from types import NoneType
from typing import Any
import struct


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
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> StrWrapper:
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
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> BytesWrapper:
        return cls(struct.unpack(f'!{len(data)}s', data)[0])


class CTDataWrapper:
    value: SerializableType
    uuid: bytes
    parent_uuid: bytes
    visible: bool

    def __init__(self, value: SerializableType, uuid: bytes, parent_uuid: bytes,
                 visible: bool = True) -> None:
        tressa(isinstance(value, SerializableType),
               f'value must be SerializableType ({SerializableType})')
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

    def pack(self) -> bytes:
        return pack([
            self.value,
            self.uuid,
            self.parent_uuid,
            int(self.visible)
        ])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> CTDataWrapper:
        dependencies = {**globals(), **inject}
        value, uuid, parent_uuid, visible = unpack(data, inject=dependencies)
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
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> DecimalWrapper:
        return cls(Decimal(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8')))


class FIAItemWrapper:
    value: SerializableType
    index: DecimalWrapper
    uuid: bytes

    def __init__(self, value: SerializableType, index: Decimal|DecimalWrapper,
                 uuid: bytes) -> None:
        tressa(isinstance(value, SerializableType),
               'value must be DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType')
        tressa(isinstance(index, Decimal) or isinstance(index, DecimalWrapper),
               'index must be Decimal|DecimalWrapper')
        tressa(type(uuid) is bytes, 'uuid must be bytes')
        self.value = value
        self.index = index if isinstance(index, DecimalWrapper) else DecimalWrapper(index)
        self.uuid = uuid

    def __hash__(self) -> int:
        return hash((self.value, self.index, self.uuid))

    def __repr__(self) -> str:
        return f'FIAItemWrapper(value={self.value}, index={self.index.value}, uuid={self.uuid.hex()}'

    def __eq__(self, other) -> bool:
        return type(other) == type(self) and hash(self) == hash(other)

    def __ne__(self, other) -> bool:
        return not (self == other)

    def __gt__(self, other) -> bool:
        return (self.value, self.index, self.uuid) > (other.value, other.index, other.uuid)

    def __ge__(self, other) -> bool:
        return (self.value, self.index, self.uuid) >= (other.value, other.index, other.uuid)

    def __lt__(self, other) -> bool:
        return (self.value, self.index, self.uuid) < (other.value, other.index, other.uuid)

    def __le__(self, other) -> bool:
        return (self.value, self.index, self.uuid) <= (other.value, other.index, other.uuid)

    def pack(self) -> bytes:
        return pack([
            self.value,
            self.index,
            self.uuid
        ])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> FIAItemWrapper:
        value, index, uuid = unpack(data, inject={**globals(), **inject})
        return cls(
            value=value,
            index=index,
            uuid=uuid,
        )


class IntWrapper(DecimalWrapper):
    value: int

    def __init__(self, value: int) -> None:
        tressa(type(value) is int, 'value must be int')
        self.value = value

    def pack(self) -> bytes:
        return struct.pack('!i', self.value)

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> IntWrapper:
        return cls(struct.unpack('!i', data)[0])


class RGAItemWrapper(StrWrapper):
    value: SerializableType
    ts: SerializableType
    writer: SerializableType

    def __init__(self, value: SerializableType, ts: SerializableType,
                 writer: SerializableType) -> None:
        tressa(isinstance(value, SerializableType), 'value must be SerializableType')
        tressa(isinstance(ts, SerializableType), 'ts must be SerializableType')
        tressa(type(writer) is int, 'writer must be int')

        self.value = value
        self.ts = ts
        self.writer = writer

    def pack(self) -> bytes:
        """Pack instance to bytes."""
        return pack([
            self.value,
            self.ts,
            self.writer
        ])

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> RGAItemWrapper:
        dependencies = {**globals(), **inject}
        value, ts, writer = unpack(data, inject=dependencies)
        return cls(
            value=value,
            ts=ts,
            writer=writer,
        )

    def __repr__(self) -> str:
        return f'RGAItemWrapper(value={self.value}, ts={self.ts}, writer={self.writer})'


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

    def __ne__(self, other) -> bool:
        return not (self == other)

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
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> NoneWrapper:
        return cls()
