from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from types import NoneType
import struct


@dataclass
class StrWrapper:
    value: str

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.value))

    def __eq__(self, other) -> bool:
        return type(self) == type(other) and self.value == other.value

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

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


class DecimalWrapper(StrWrapper):
    value: Decimal

    def __init__(self, value: Decimal) -> None:
        self.value = value

    def __gt__(self, other: DecimalWrapper) -> bool:
        return self.value > other.value

    def __ge__(self, other: DecimalWrapper) -> bool:
        return self.value >= other.value

    def __lt__(self, other: DecimalWrapper) -> bool:
        return other.value > self.value

    def __le__(self, other: DecimalWrapper) -> bool:
        return other.value >= self.value

    def pack(self) -> bytes:
        return struct.pack(f'!{len(str(self.value))}s', bytes(str(self.value), 'utf-8'))

    @classmethod
    def unpack(cls, data: bytes) -> DecimalWrapper:
        return cls(Decimal(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8')))


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
