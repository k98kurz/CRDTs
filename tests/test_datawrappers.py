from __future__ import annotations
from context import interfaces, datawrappers, errors
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
        rgatw = datawrappers.RGATupleWrapper((
            datawrappers.BytesWrapper(b'123'),
            (datawrappers.IntWrapper(1), 1)
        ))
        assert isinstance(rgatw, interfaces.DataWrapperProtocol)

    def test_RGATupleWrapper_value_is_tuple_of_bytes_tuple_ints(self):
        rgatw = datawrappers.RGATupleWrapper((
            datawrappers.BytesWrapper(b'123'),
            (datawrappers.IntWrapper(1), 1)
        ))
        assert type(rgatw.value) is tuple
        assert len(rgatw.value) == 2
        assert isinstance(rgatw.value[0], interfaces.DataWrapperProtocol)
        assert type(rgatw.value[1]) is tuple
        assert len(rgatw.value[1]) == 2
        assert isinstance(rgatw.value[1][0], datawrappers.IntWrapper)
        assert type(rgatw.value[1][1]) is int

    def test_RGATupleWrapper_raises_UsagePreconditionError_for_bad_value(self):
        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.RGATupleWrapper(b'123')
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'

        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.RGATupleWrapper((b'123',))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'

        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.RGATupleWrapper((b'123', 1))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'

        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.RGATupleWrapper((b'123', (1, b'123')))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'

        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.RGATupleWrapper((datawrappers.BytesWrapper(b'123'), (1, 123)))
        assert str(e.exception) == 'value must be of form tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]'

    def test_RGATupleWrapper_pack_returns_bytes(self):
        rgatw = datawrappers.RGATupleWrapper((
            datawrappers.BytesWrapper(b'123'),
            (datawrappers.IntWrapper(1), 1)
        ))
        packed = rgatw.pack()
        assert type(packed) is bytes

    def test_RGATupleWrapper_unpack_returns_instance(Self):
        bts = datawrappers.BytesWrapper(b'123')
        data = bytes(bts.__class__.__name__, 'utf-8')
        data = bytes(data.hex() + '_', 'utf-8') + bts.pack()
        intw = datawrappers.IntWrapper(1)
        ts = bytes(intw.__class__.__name__, 'utf-8')
        ts = bytes(ts.hex() + '_', 'utf-8') + intw.pack()
        data = struct.pack(
            f'!II{len(data)}s{len(ts)}sI',
            len(data),
            len(ts),
            data,
            ts,
            1,
        )
        unpacked = datawrappers.RGATupleWrapper.unpack(data)
        assert type(unpacked) is datawrappers.RGATupleWrapper

    def test_RGATupleWrapper_pack_unpack_e2e(self):
        rgatw = datawrappers.RGATupleWrapper((
            datawrappers.BytesWrapper(b'123'),
            (datawrappers.BytesWrapper(b'adfsf'), 1)
        ))
        packed = rgatw.pack()
        unpacked = datawrappers.RGATupleWrapper.unpack(packed)
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

    def test_CTDataWrapper_raises_UsagePreconditionError_for_bad_value(self):
        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.CTDataWrapper(b'123', b'str', b'132')
        assert str(e.exception) == 'value must be DataWrapperProtocol'

        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.CTDataWrapper(datawrappers.BytesWrapper(b'123'), '321', b'123')
        assert str(e.exception) == 'uuid must be bytes'

        with self.assertRaises(errors.UsagePreconditionError) as e:
            datawrappers.CTDataWrapper(datawrappers.BytesWrapper(b'123'), b'123', 123)
        assert str(e.exception) == 'parent_uuid must be bytes'

        with self.assertRaises(errors.UsagePreconditionError) as e:
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
        value_type = bytes(value.__class__.__name__, 'utf-8')
        value_packed = value.pack()
        data = struct.pack(
            f'!IIII{len(value_type)}s{len(value_packed)}s{len(uuid)}s' +
            f'{len(parent)}s?',
            len(value_type),
            len(value_packed),
            len(uuid),
            len(parent),
            value_type,
            value_packed,
            uuid,
            parent,
            False,
        )
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
