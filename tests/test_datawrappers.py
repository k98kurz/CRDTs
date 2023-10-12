from __future__ import annotations
from context import interfaces, datawrappers, errors
from decimal import Decimal
import packify
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

    # RGAItemWrapper tests
    def test_RGAItemWrapper_implements_DataWrapperProtocol(self):
        rgatw = datawrappers.RGAItemWrapper(
            datawrappers.BytesWrapper(b'123'),
            datawrappers.IntWrapper(1),
            1
        )
        assert isinstance(rgatw, interfaces.DataWrapperProtocol)

    def test_RGAItemWrapper_values_are_correct_types(self):
        rgatw = datawrappers.RGAItemWrapper(
            datawrappers.BytesWrapper(b'123'),
            datawrappers.IntWrapper(1),
            1
        )
        assert isinstance(rgatw.value, interfaces.DataWrapperProtocol)
        assert isinstance(rgatw.ts, interfaces.DataWrapperProtocol)
        assert type(rgatw.writer) is int

    def test_RGAItemWrapper_raises_UsageError_for_bad_value(self):
        with self.assertRaises(errors.UsageError) as e:
            datawrappers.RGAItemWrapper(
                datawrappers.BytesWrapper(b'123'),
                datawrappers.BytesWrapper(b'321'),
                lambda: "not a packify.SerializableType"
            )
        assert str(e.exception) == 'writer must be SerializableType'

    def test_RGAItemWrapper_pack_returns_bytes(self):
        rgatw = datawrappers.RGAItemWrapper(
            datawrappers.BytesWrapper(b'123'),
            datawrappers.IntWrapper(1),
            1
        )
        packed = rgatw.pack()
        assert type(packed) is bytes

    def test_RGAItemWrapper_unpack_returns_instance(Self):
        bts = b'123'
        ts = 1
        data = packify.pack([
            bts,
            ts,
            1
        ])
        unpacked = datawrappers.RGAItemWrapper.unpack(data)
        assert type(unpacked) is datawrappers.RGAItemWrapper

    def test_RGAItemWrapper_pack_unpack_e2e(self):
        rgatw = datawrappers.RGAItemWrapper(
            datawrappers.BytesWrapper(b'123'),
            datawrappers.BytesWrapper(b'adfsf'),
            1
        )
        packed = rgatw.pack()
        unpacked = datawrappers.RGAItemWrapper.unpack(packed)
        assert rgatw == unpacked

    # CTDataWrapper
    def test_CTDataWrapper_implements_DataWrapperProtocol(self):
        ctw = datawrappers.CTDataWrapper(
            datawrappers.BytesWrapper(b'123'),
            b'321',
            b'123'
        )
        assert isinstance(ctw, interfaces.DataWrapperProtocol)

    def test_CTDataWrapper_properties_are_correct_types(self):
        ctw = datawrappers.CTDataWrapper(
            datawrappers.BytesWrapper(b'123'),
            b'321',
            b'123'
        )
        assert isinstance(ctw.value, interfaces.DataWrapperProtocol)
        assert type(ctw.uuid) is bytes
        assert type(ctw.parent_uuid) is bytes

    def test_CTDataWrapper_raises_UsageError_for_bad_value(self):
        with self.assertRaises(errors.UsageError) as e:
            datawrappers.CTDataWrapper(datawrappers.BytesWrapper(b'123'), '321', b'123')
        assert str(e.exception) == 'uuid must be bytes'

        with self.assertRaises(errors.UsageError) as e:
            datawrappers.CTDataWrapper(datawrappers.BytesWrapper(b'123'), b'123', 123)
        assert str(e.exception) == 'parent_uuid must be bytes'

        with self.assertRaises(errors.UsageError) as e:
            datawrappers.CTDataWrapper(datawrappers.BytesWrapper(b'1'), b'1', b'1', 'f')
        assert str(e.exception) == 'visible must be bool'

    def test_CTDataWrapper_pack_returns_bytes(self):
        ctw = datawrappers.CTDataWrapper(
            datawrappers.BytesWrapper(b'123'),
            b'321',
            b'123'
        )
        packed = ctw.pack()
        assert type(packed) is bytes

    def test_CTDataWrapper_unpack_returns_instance(Self):
        value = datawrappers.BytesWrapper(b'123')
        uuid = b'321'
        parent = b'123'
        data = packify.pack([
            value,
            uuid,
            parent,
            0
        ])
        unpacked = datawrappers.CTDataWrapper.unpack(data)
        assert type(unpacked) is datawrappers.CTDataWrapper

    def test_CTDataWrapper_pack_unpack_e2e(self):
        ctw = datawrappers.CTDataWrapper(
            datawrappers.BytesWrapper(b'123'),
            b'321',
            b'123'
        )
        packed = ctw.pack()
        unpacked = datawrappers.CTDataWrapper.unpack(packed)
        assert ctw == unpacked

    def test_CTDataWrapper_comparisons(self):
        ctw1 = datawrappers.CTDataWrapper(
            datawrappers.BytesWrapper(b'123'),
            b'321',
            b'123'
        )
        ctw2 = datawrappers.CTDataWrapper(
            datawrappers.BytesWrapper(b'123'),
            b'321',
            b'123',
            False
        )
        assert ctw1 != ctw2
        assert hash(ctw1) != hash(ctw2)

    # NoneWrapper tests
    def test_NoneWrapper_implements_DataWrapperProtocil(self):
        assert isinstance(datawrappers.NoneWrapper, interfaces.DataWrapperProtocol)


if __name__ == '__main__':
    unittest.main()
