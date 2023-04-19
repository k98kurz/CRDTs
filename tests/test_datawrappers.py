from __future__ import annotations
from context import interfaces, datawrappers
from decimal import Decimal
import struct
import unittest


class TestDataWrappers(unittest.TestCase):
    # StrWrapper tests
    def test_StrWrapper_implements_DataWrapperProtocol(self):
        assert isinstance(datawrappers.StrWrapper(''), interfaces.DataWrapperProtocol)

    def test_StrWrapper_value_is_str_type(self):
        dw = datawrappers.StrWrapper('test')
        assert type(dw.value) is str

    def test_StrWrapper_pack_returns_bytes(self):
        dw = datawrappers.StrWrapper('test')
        assert type(dw.pack()) is bytes

    def test_StrWrapper_unpack_returns_instance(self):
        data = struct.pack('!4s', bytes('test', 'utf-8'))
        unpacked = datawrappers.StrWrapper.unpack(data)
        assert type(unpacked) is datawrappers.StrWrapper

    def test_StrWrapper_pack_unpack_e2e(self):
        dw = datawrappers.StrWrapper('test')
        packed = dw.pack()
        unpacked = datawrappers.StrWrapper.unpack(packed)
        assert dw == unpacked

    # BytesWrapper tests
    def test_BytesWrapper_implements_DataWrapperProtocol(self):
        assert isinstance(datawrappers.BytesWrapper(b''), interfaces.DataWrapperProtocol)

    def test_BytesWrapper_value_is_bytes_type(self):
        dw = datawrappers.BytesWrapper(b'test')
        assert type(dw.value) is bytes

    def test_BytesWrapper_pack_returns_bytes(self):
        dw = datawrappers.BytesWrapper(b'test')
        assert type(dw.pack()) is bytes

    def test_BytesWrapper_unpack_returns_instance(self):
        data = struct.pack('!4s', b'test')
        unpacked = datawrappers.BytesWrapper.unpack(data)
        assert type(unpacked) is datawrappers.BytesWrapper

    def test_BytesWrapper_pack_unpack_e2e(self):
        dw = datawrappers.BytesWrapper(b'test')
        packed = dw.pack()
        unpacked = datawrappers.BytesWrapper.unpack(packed)
        assert dw == unpacked

    # DecimalWrapper tests
    def test_DecimalWrapper_implements_DataWrapperProtocol(self):
        assert isinstance(datawrappers.DecimalWrapper(Decimal(0)), interfaces.DataWrapperProtocol)

    def test_DecimalWrapper_value_is_Decimal_type(self):
        dw = datawrappers.DecimalWrapper(Decimal(0))
        assert type(dw.value) is Decimal

    def test_DecimalWrapper_pack_returns_bytes(self):
        dw = datawrappers.DecimalWrapper(Decimal(0))
        assert type(dw.pack()) is bytes

    def test_DecimalWrapper_unpack_returns_instance(self):
        data = struct.pack('!1s', b'0')
        unpacked = datawrappers.DecimalWrapper.unpack(data)
        assert type(unpacked) is datawrappers.DecimalWrapper

    def test_DecimalWrapper_pack_unpack_e2e(self):
        dw = datawrappers.DecimalWrapper(Decimal(0))
        packed = dw.pack()
        unpacked = datawrappers.DecimalWrapper.unpack(packed)
        assert dw == unpacked


if __name__ == '__main__':
    unittest.main()
