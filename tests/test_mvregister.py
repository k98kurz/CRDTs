from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors
import unittest


@dataclass
class StrClock:
    """Implements a logical clock using strs."""
    counter: str = field(default='0')
    uuid: bytes = field(default=b'1234567890')
    default_ts: str = field(default='')

    def read(self) -> str:
        """Return the current timestamp."""
        return self.counter

    def update(self, data: str) -> str:
        """Update the clock and return the current time stamp."""
        assert type(data) is str, 'data must be str'

        if len(data) >= len(self.counter):
            self.counter = data + '1'

        return self.counter

    @staticmethod
    def is_later(ts1: str, ts2: str) -> bool:
        """Return True iff len(ts1) > len(ts2)."""
        assert type(ts1) is str, 'ts1 must be str'
        assert type(ts2) is str, 'ts2 must be str'

        if len(ts1) > len(ts2):
            return True
        return False

    @staticmethod
    def are_concurrent(ts1: str, ts2: str) -> bool:
        """Return True if len(ts1) == len(ts2)."""
        assert type(ts1) is str, 'ts1 must be str'
        assert type(ts2) is str, 'ts2 must be str'

        return len(ts1) == len(ts2)

    @staticmethod
    def compare(ts1: str, ts2: str) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable.
        """
        assert type(ts1) is str, 'ts1 must be str'
        assert type(ts2) is str, 'ts2 must be str'

        if len(ts1) > len(ts2):
            return 1
        elif len(ts2) > len(ts1):
            return -1
        return 0

    def pack(self) -> bytes:
        """Packs the clock into bytes."""
        return bytes(self.counter, 'utf-8') + b'_' + self.uuid

    @classmethod
    def unpack(cls, data: bytes) -> StrClock:
        """Unpacks a clock from bytes."""
        assert type(data) is bytes, 'data must be bytes'
        assert len(data) >= 5, 'data must be at least 5 bytes'

        counter, _, uuid = data.partition(b'_')

        return cls(counter=str(counter, 'utf-8'), uuid=uuid)

    @classmethod
    def wrap_ts(cls, ts: str) -> datawrappers.StrWrapper:
        return datawrappers.StrWrapper(ts)


class CustomStateUpdate(classes.StateUpdate):
    pass


class TestMVRegister(unittest.TestCase):
    def test_MVRegister_implements_CRDTProtocol(self):
        assert isinstance(
            classes.MVRegister(datawrappers.StrWrapper('test')),
            interfaces.CRDTProtocol
        )

    def test_MVRegister_read_returns_set_of_DataWrapperProtocol(self):
        mvregister = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )
        assert type(mvregister.read()) is tuple
        assert len(mvregister.read()) == 1
        assert isinstance(mvregister.read()[0], classes.DataWrapperProtocol)
        assert mvregister.read()[0].value == 'foobar'

    def test_MVRegister_write_returns_StateUpdate_and_sets_values(self):
        mvregister = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.DecimalWrapper(Decimal('0.123'))]
        )
        update = mvregister.write(datawrappers.BytesWrapper(b'barfoo'))
        assert isinstance(update, classes.StateUpdate)
        assert list(mvregister.read())[0].value == b'barfoo'

    def test_MVRegister_history_returns_tuple_of_StateUpdate(self):
        mvregister = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )
        mvregister.write(datawrappers.StrWrapper('sdsd'))
        mvregister.write(datawrappers.StrWrapper('barfoo'))
        history = mvregister.history()

        assert type(history) is tuple
        for item in history:
            assert isinstance(item, classes.StateUpdate)

    def test_MVRegister_concurrent_writes_retain_all_values(self):
        mvregister1 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2.clock.uuid = mvregister1.clock.uuid

        update1 = mvregister1.write(datawrappers.StrWrapper('foobar'))
        update2 = mvregister2.write(datawrappers.StrWrapper('barfoo'))
        mvregister1.update(update2)
        mvregister2.update(update1)
        expected = (datawrappers.StrWrapper('barfoo'), datawrappers.StrWrapper('foobar'))

        assert mvregister1.read() == mvregister2.read()
        assert mvregister1.read() == expected

    def test_MVRegister_checksums_returns_tuple_of_int(self):
        mvregister = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )
        assert type(mvregister.checksums()) is tuple
        for item in mvregister.checksums():
            assert type(item) is int

    def test_MVRegister_checksums_change_after_update(self):
        mvregister1 = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )
        mvregister2 = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )
        mvregister2.clock.uuid = mvregister1.clock.uuid
        checksums1 = mvregister1.checksums()

        assert mvregister2.checksums() == checksums1

        mvregister1.write(datawrappers.StrWrapper('thing'))
        mvregister2.write(datawrappers.StrWrapper('stuff'))

        assert mvregister1.checksums() != checksums1
        assert mvregister2.checksums() != checksums1
        assert mvregister1.checksums() != mvregister2.checksums()

    def test_MVRegister_update_is_idempotent(self):
        mvregister1 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2.clock.uuid = mvregister1.clock.uuid

        update = mvregister1.write(datawrappers.StrWrapper('foo1'))
        view1 = mvregister1.read()
        mvregister1.update(update)
        assert mvregister1.read() == view1
        mvregister2.update(update)
        view2 = mvregister2.read()
        mvregister2.update(update)
        assert mvregister2.read() == view2

        update = mvregister2.write(datawrappers.StrWrapper('bar'))
        mvregister1.update(update)
        view1 = mvregister1.read()
        mvregister1.update(update)
        assert mvregister1.read() == view1
        mvregister2.update(update)
        view2 = mvregister2.read()
        mvregister2.update(update)
        assert mvregister2.read() == view2

    def test_MVRegister_updates_are_commutative(self):
        mvregister1 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2.clock.uuid = mvregister1.clock.uuid

        update1 = mvregister1.write(datawrappers.StrWrapper('foo1'))
        update2 = mvregister1.write(datawrappers.StrWrapper('foo2'))
        mvregister2.update(update2)
        mvregister2.update(update1)

        assert mvregister1.read() == mvregister2.read()

    def test_MVRegister_update_from_history_converges(self):
        mvregister1 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister2.clock.uuid = mvregister1.clock.uuid
        mvregister3 = classes.MVRegister(datawrappers.StrWrapper('test'))
        mvregister3.clock.uuid = mvregister1.clock.uuid

        update = mvregister1.write(datawrappers.StrWrapper('foo1'))
        mvregister2.update(update)
        mvregister2.write(datawrappers.StrWrapper('bar'))

        for item in mvregister2.history():
            mvregister1.update(item)
            mvregister3.update(item)

        assert mvregister1.read() == mvregister2.read()
        assert mvregister1.read() == mvregister3.read()
        assert mvregister1.checksums() == mvregister2.checksums()
        assert mvregister1.checksums() == mvregister3.checksums()

    def test_MVRegister_pack_unpack_e2e(self):
        mvregister = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )

        packed = mvregister.pack()
        unpacked = classes.MVRegister.unpack(packed)

        assert isinstance(unpacked, classes.MVRegister)
        assert unpacked.clock == mvregister.clock
        assert unpacked.read() == mvregister.read()

    def test_MVRegister_pack_unpack_e2e_with_injected_clock(self):
        mvregister = classes.MVRegister(
            name=datawrappers.StrWrapper('test register'),
            clock=StrClock()
        )
        mvregister.write(datawrappers.StrWrapper('first'))
        mvregister.write(datawrappers.StrWrapper('second'))
        packed = mvregister.pack()

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.MVRegister.unpack(packed)
        assert str(e.exception) == 'cannot find StrClock'

        # inject and repeat
        unpacked = classes.MVRegister.unpack(packed, {'StrClock': StrClock})

        assert unpacked.clock == mvregister.clock
        assert unpacked.read() == mvregister.read()

    def test_MVRegister_with_injected_StateUpdateProtocol_class(self):
        mvregister = classes.MVRegister(
            name=datawrappers.StrWrapper('test register')
        )
        update = mvregister.write(datawrappers.StrWrapper('first'), update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(mvregister.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate


if __name__ == '__main__':
    unittest.main()
