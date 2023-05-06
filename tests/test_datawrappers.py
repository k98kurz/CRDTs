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

    def test_DecimalWrapper_comparisons(self):
        dw0 = datawrappers.DecimalWrapper(Decimal(0))
        dw1 = datawrappers.DecimalWrapper(Decimal(1))

        assert dw0 == dw0
        assert dw1 > dw0
        assert dw1 >= dw0
        assert dw0 < dw1
        assert dw0 <= dw1

    # IntWrapper tests
    def test_IntWrapper_implements_DataWrapperProtocol(self):
        assert isinstance(datawrappers.IntWrapper(1), interfaces.DataWrapperProtocol)

    def test_IntWrapper_value_is_int_type(self):
        dw = datawrappers.IntWrapper(1)
        assert type(dw.value) is int

    def test_IntWrapper_pack_returns_bytes(self):
        dw = datawrappers.IntWrapper(1)
        assert type(dw.pack()) is bytes

    def test_IntWrapper_unpack_returns_instance(self):
        data = struct.pack('!i', 123)
        unpacked = datawrappers.IntWrapper.unpack(data)
        assert type(unpacked) is datawrappers.IntWrapper

    def test_IntWrapper_pack_unpack_e2e(self):
        dw = datawrappers.IntWrapper(321)
        packed = dw.pack()
        unpacked = datawrappers.IntWrapper.unpack(packed)
        assert dw == unpacked

    def test_IntWrapper_comparisons(self):
        dw0 = datawrappers.IntWrapper(123)
        dw1 = datawrappers.IntWrapper(321)

        assert dw0 == dw0
        assert dw1 > dw0
        assert dw1 >= dw0
        assert dw0 < dw1
        assert dw0 <= dw1

    # RGATupleWrapper tests
    def test_RGATupleWrapper_implements_DataWrapperProtocol(self):
        rgatw = datawrappers.RGATupleWrapper((datawrappers.BytesWrapper(b'123'), (1, 1)))
        assert isinstance(rgatw, interfaces.DataWrapperProtocol)

    def test_RGATupleWrapper_value_is_tuple_of_bytes_tuple_ints(self):
        rgatw = datawrappers.RGATupleWrapper((datawrappers.BytesWrapper(b'123'), (1, 1)))
        assert type(rgatw.value) is tuple
        assert len(rgatw.value) == 2
        assert isinstance(rgatw.value[0], interfaces.DataWrapperProtocol)
        assert type(rgatw.value[1]) is tuple
        assert len(rgatw.value[1]) == 2
        assert type(rgatw.value[1][0]) is int
        assert type(rgatw.value[1][1]) is int

    def test_RGATupleWrapper_raises_AssertionError_for_bad_value(self):
        with self.assertRaises(AssertionError) as e:
            datawrappers.RGATupleWrapper(b'123')
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[int, int]]'

        with self.assertRaises(AssertionError) as e:
            datawrappers.RGATupleWrapper((b'123',))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[int, int]]'

        with self.assertRaises(AssertionError) as e:
            datawrappers.RGATupleWrapper((b'123', 1))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[int, int]]'

        with self.assertRaises(AssertionError) as e:
            datawrappers.RGATupleWrapper((b'123', (1, b'123')))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[int, int]]'

        with self.assertRaises(AssertionError) as e:
            datawrappers.RGATupleWrapper((datawrappers.BytesWrapper(b'123'), (1, b'123')))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[int, int]]'

    def test_RGATupleWrapper_pack_returns_bytes(self):
        rgatw = datawrappers.RGATupleWrapper((datawrappers.BytesWrapper(b'123'), (1, 1)))
        packed = rgatw.pack()
        assert type(packed) is bytes

    def test_RGATupleWrapper_unpack_returns_instance(Self):
        bts = datawrappers.BytesWrapper(b'123')
        data = bytes(f'{bts.__class__.__name__}_{bts.pack().hex()}', 'utf-8')
        data = struct.pack(
            f'!i{len(data)}sii',
            len(data),
            data,
            1,
            2
        )
        unpacked = datawrappers.RGATupleWrapper.unpack(data)
        assert type(unpacked) is datawrappers.RGATupleWrapper

    def test_RGATupleWrapper_pack_unpack_e2e(self):
        rgatw = datawrappers.RGATupleWrapper((datawrappers.BytesWrapper(b'123'), (1, 1)))
        packed = rgatw.pack()
        unpacked = datawrappers.RGATupleWrapper.unpack(packed)
        assert rgatw == unpacked


if __name__ == '__main__':
    unittest.main()
