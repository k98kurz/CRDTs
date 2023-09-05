from __future__ import annotations
import struct
from context import datawrappers, interfaces, serialization
import unittest


class PackableMapEntry:
    key: interfaces.PackableProtocol
    value: interfaces.PackableProtocol

    def __init__(self, key: interfaces.PackableProtocol,
                 value: interfaces.PackableProtocol) -> None:
        self.key = key
        self.value = value

    def __hash__(self) -> int:
        return hash((self.key, self.value))

    def __eq__(self, other: PackableMapEntry) -> bool:
        return type(other) is type(self) and other.key == self.key and \
            other.value == self.value

    def pack(self) -> bytes:
        key = bytes(self.key.__class__.__name__, 'utf-8').hex()
        key = bytes(key, 'utf-8') + b'_' + self.key.pack()
        value = bytes(self.value.__class__.__name__, 'utf-8').hex()
        value = bytes(value, 'utf-8') + b'_' + self.value.pack()
        return struct.pack(
            f'!HH{len(key)}s{len(value)}s',
            len(key),
            len(value),
            key,
            value
        )

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> PackableMapEntry:
        key_len, value_len, data = struct.unpack(f'!HH{len(data)-4}s', data)
        key_data, value_data = struct.unpack(f'{key_len}s{value_len}s', data)

        assert type(key_data) is bytes
        key_class, key_data = key_data.split(b'_', 1)
        key_class = str(bytes.fromhex(str(key_class, 'utf-8')), 'utf-8')
        key = getattr(datawrappers, key_class).unpack(key_data, inject=inject)

        assert type(value_data) is bytes
        value_class, value_data = value_data.split(b'_', 1)
        value_class = str(bytes.fromhex(str(value_class, 'utf-8')), 'utf-8')
        value = getattr(datawrappers, value_class).unpack(value_data, inject=inject)

        return cls(key, value)


class TestSerialization(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        self.inject = {
            'BytesWrapper': datawrappers.BytesWrapper,
            'StrWrapper': datawrappers.StrWrapper,
            'IntWrapper': datawrappers.IntWrapper,
            'DecimalWrapper': datawrappers.DecimalWrapper,
            'CTDataWrapper': datawrappers.CTDataWrapper,
            'RGAItemWrapper': datawrappers.RGAItemWrapper,
            'NoneWrapper': datawrappers.NoneWrapper,
        }
        super().__init__(methodName)

    def test_serialize_and_deserialize_list_e2e(self):
        data = [
            datawrappers.StrWrapper("hello world"),
            "hello world",
            datawrappers.BytesWrapper(b"hello world"),
            b'hello world',
            bytearray(b'hello world'),
            datawrappers.IntWrapper(1234),
            1234,
            123.456,
            datawrappers.RGAItemWrapper(
                datawrappers.StrWrapper("first"),
                datawrappers.StrWrapper("second"),
                123
            ),
            PackableMapEntry(
                datawrappers.StrWrapper("some key"),
                datawrappers.BytesWrapper(b"some value"),
            ),
            None
        ]
        serialized = serialization.serialize_part(data)
        deserialized = serialization.deserialize_part(
            serialized,
            inject={**self.inject, "PackableMapEntry": PackableMapEntry}
        )

        # compare all parts
        assert len(data) == len(deserialized)
        assert type(data) == type(deserialized)
        for i in range(len(data)):
            assert type(data[i]) == type(deserialized[i])
            if type(data[i]) is float:
                p1 = serialization.serialize_part(data[i])
                p2 = serialization.serialize_part(deserialized[i])
                assert p1 == p2
            else:
                assert data[i] == deserialized[i]

    def test_serialize_and_deserialize_set_e2e(self):
        data = set([
            123, 4321, "abc", "cba", b"abc", b"cba",
            PackableMapEntry(datawrappers.StrWrapper("123"), datawrappers.IntWrapper(321)),
            None
        ])
        serialized = serialization.serialize_part(data)
        deserialized = serialization.deserialize_part(
            serialized,
            inject={"PackableMapEntry": PackableMapEntry}
        )

        # compare all parts
        assert len(data) == len(deserialized)
        assert type(data) == type(deserialized)
        for item in data:
            assert item in deserialized

    def test_serialize_and_deserialize_tuple_e2e(self):
        data = tuple([
            123, 4321, "abc", "cba", b"abc", b"cba",
            PackableMapEntry(datawrappers.StrWrapper("123"), datawrappers.IntWrapper(321)),
            None
        ])
        serialized = serialization.serialize_part(data)
        deserialized = serialization.deserialize_part(
            serialized,
            inject={"PackableMapEntry": PackableMapEntry}
        )

        # compare all parts
        assert len(data) == len(deserialized)
        assert type(data) == type(deserialized)
        for item in data:
            assert item in deserialized


if __name__ == '__main__':
    unittest.main()
