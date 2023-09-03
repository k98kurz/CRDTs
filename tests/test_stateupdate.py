from __future__ import annotations
from dataclasses import dataclass, field, is_dataclass
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors
import unittest


class TestStateUpdate(unittest.TestCase):
    def test_StateUpdate_is_dataclass_with_attributes(self):
        update = classes.StateUpdate(b'123', 123, 321)
        assert is_dataclass(update)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_StateUpdate_pack_returns_bytes(self):
        update = classes.StateUpdate(b'123', 123, 321)
        assert type(update.pack()) is bytes
        # print(f'{update.pack().hex()=}')

    def test_StateUpdate_unpack_returns_StateUpdate(self):
        data = bytes.fromhex('000000080000000900000009000000046231323300000005690000007b000000056900000141')
        update = classes.StateUpdate.unpack(data)
        assert isinstance(update, classes.StateUpdate)

    def test_StateUpdate_pack_unpack_e2e(self):
        # GSet StateUpdate e2e test
        update = classes.StateUpdate(b'uuid', 123, [321, '123', b'321'])
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # Counter StateUpdate e2e test
        update = classes.StateUpdate(b'uuid', 123, 321)
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # ORSet StateUpdate e2e test
        update = classes.StateUpdate(b'uuid', 123, ('o', (321, '123')))
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # PNCounter StateUpdate e2e test
        update = classes.StateUpdate(b'uuid', 123, (321, 123))
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # RGArray StateUpdate e2e test
        update = classes.StateUpdate(
            b'uuid',
            123,
            datawrappers.RGATupleWrapper((
                datawrappers.StrWrapper('hello'),
                (datawrappers.IntWrapper(123), 321)
            ))
        )
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # LWWRegister StateUpdate e2e test
        update = classes.StateUpdate(
            b'uuid',
            123,
            (1, datawrappers.BytesWrapper(b'example'))
        )
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # LWWMap StateUpdate e2e test
        update = classes.StateUpdate(
            b'uuid',
            123,
            (
                'o',
                datawrappers.StrWrapper('name'),
                1,
                datawrappers.BytesWrapper(b'value')
            )
        )
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # FIArray StateUpdate e2e test
        update = classes.StateUpdate(
            b'uuid',
            123,
            (
                'o',
                datawrappers.IntWrapper(3),
                1,
                datawrappers.DecimalWrapper(Decimal('0.253'))
            )
        )
        packed = update.pack()
        unpacked = classes.StateUpdate.unpack(packed)
        assert unpacked == update

        # CausalTree StateUpdate e2e test
        # @todo once CausalTree implemented


if __name__ == '__main__':
    unittest.main()
