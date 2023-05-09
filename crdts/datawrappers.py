from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from .interfaces import DataWrapperProtocol
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
    def unpack(cls, data: bytes) -> StrWrapper:
        return cls(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8'))


class BytesWrapper(StrWrapper):
    value: bytes

    def __init__(self, value: bytes) -> None:
        self.value = value

    def pack(self) -> bytes:
        return struct.pack(f'!{len(self.value)}s', self.value)

    @classmethod
    def unpack(cls, data: bytes) -> BytesWrapper:
        return cls(struct.unpack(f'!{len(data)}s', data)[0])


class CTDataWrapper(StrWrapper):
    value: DataWrapperProtocol
    uuid: bytes
    parent: bytes
    visible: bool

    def __init__(self, value: DataWrapperProtocol, uuid: bytes, parent: bytes,
                 visible: bool = True) -> None:
        assert isinstance(value, DataWrapperProtocol), 'value must be DataWrapperProtocol'
        assert type(uuid) is bytes, 'uuid must be bytes'
        assert type(parent) is bytes, 'parent must be bytes'
        assert type(visible) is bool, 'visible must be bool'

        self.value = value
        self.uuid = uuid
        self.parent = parent
        self.visible = visible

    def __to_tuple__(self) -> tuple:
        return (self.__class__.__name__, self.value, self.uuid, self.parent, self.visible)

    def __gt__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() > other.__to_tuple__()

    def __ge__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() >= other.__to_tuple__()

    def __lt__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() < other.__to_tuple__()

    def __le__(self, other: CTDataWrapper) -> bool:
        return self.__to_tuple__() <= other.__to_tuple__()

    def pack(self) -> bytes:
        value_type = bytes(self.value.__class__.__name__, 'utf-8')
        value_packed = self.value.pack()

        return struct.pack(
            f'!IIII{len(value_type)}s{len(value_packed)}s' +
            f'{len(self.uuid)}s{len(self.parent)}s?',
            len(value_type),
            len(value_packed),
            len(self.uuid),
            len(self.parent),
            value_type,
            value_packed,
            self.uuid,
            self.parent,
            self.visible,
        )

    @classmethod
    def unpack(cls, data: bytes) -> CTDataWrapper:
        value_type_len, value_len, uuid_len, parent_len, _ = struct.unpack(
            f'!IIII{len(data)-16}s',
            data
        )
        _, value_type, value_packed, uuid, parent, visible = struct.unpack(
            f'!16s{value_type_len}s{value_len}s{uuid_len}s{parent_len}s?',
            data
        )

        # parse value
        value_type = str(value_type, 'utf-8')
        assert value_type in globals(), f'{value_type} must be accessible from globals()'
        assert hasattr(globals()[value_type], 'unpack'), \
            f'{value_type} missing unpack method'
        value = globals()[value_type].unpack(value_packed)

        return cls(value, uuid, parent, visible)


class DecimalWrapper(StrWrapper):
    value: Decimal

    def __init__(self, value: Decimal) -> None:
        self.value = value

    def pack(self) -> bytes:
        return struct.pack(f'!{len(str(self.value))}s', bytes(str(self.value), 'utf-8'))

    @classmethod
    def unpack(cls, data: bytes) -> DecimalWrapper:
        return cls(Decimal(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8')))


class IntWrapper(DecimalWrapper):
    value: int

    def __init__(self, value: int) -> None:
        assert type(value) is int, 'value must be int'
        self.value = value

    def pack(self) -> bytes:
        return struct.pack('!i', self.value)

    @classmethod
    def unpack(cls, data: bytes) -> IntWrapper:
        return cls(struct.unpack('!i', data)[0])


class RGATupleWrapper(StrWrapper):
    value: tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]

    def __init__(self, value: tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]) -> None:
        assert type(value) is tuple, \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'
        assert len(value) == 2, \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'
        assert isinstance(value[0], DataWrapperProtocol), \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'
        assert type(value[1]) is tuple, \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'
        assert len(value[1]) == 2, \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'
        assert isinstance(value[1][0], DataWrapperProtocol), \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'
        assert type(value[1][1]) is int, \
            'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'

        self.value = value

    def pack(self) -> bytes:
        packed_val = bytes(self.value[0].__class__.__name__, 'utf-8').hex() + '_'
        packed_val = bytes(packed_val, 'utf-8') + self.value[0].pack()
        packed_ts = bytes(self.value[1][0].__class__.__name__, 'utf-8').hex() + '_'
        packed_ts = bytes(packed_ts, 'utf-8') + self.value[1][0].pack()
        return struct.pack(
            f'!II{len(packed_val)}s{len(packed_ts)}sI',
            len(packed_val),
            len(packed_ts),
            packed_val,
            packed_ts,
            self.value[1][1]
        )

    @classmethod
    def unpack(cls, data: bytes) -> RGATupleWrapper:
        packed_len, ts_len, _ = struct.unpack(f'!II{len(data)-8}s', data)
        _, packed, ts, writer = struct.unpack(f'!8s{packed_len}s{ts_len}sI', data)

        # parse item value
        classname, _, packed = packed.partition(b'_')
        classname = str(bytes.fromhex(str(classname, 'utf-8')), 'utf-8')
        item = globals()[classname].unpack(packed)

        # parse ts
        classname, _, ts = ts.partition(b'_')
        classname = str(bytes.fromhex(str(classname, 'utf-8')), 'utf-8')
        ts = globals()[classname].unpack(ts)

        return cls((item, (ts, writer)))


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

    def pack(self) -> bytes:
        return b''

    @classmethod
    def unpack(cls, data: bytes) -> NoneWrapper:
        return cls()
