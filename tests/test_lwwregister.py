from __future__ import annotations
from dataclasses import dataclass, field, is_dataclass
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
    def unpack(cls, data: bytes, inject: dict = {}) -> StrClock:
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


class TestLWWRegister(unittest.TestCase):
    def test_LWWRegister_implements_CRDTProtocol(self):
        assert isinstance(classes.LWWRegister(datawrappers.StrWrapper('test')), interfaces.CRDTProtocol)

    def test_LWWRegister_read_returns_DataWrapperProtocol(self):
        lwwregister = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper('foobar'))
        assert isinstance(lwwregister.read(), classes.DataWrapperProtocol)
        assert lwwregister.read().value == 'foobar'

    def test_LWWRegister_write_returns_StateUpdate_and_sets_value(self):
        lwwregister = classes.LWWRegister(datawrappers.BytesWrapper(b'test'), datawrappers.BytesWrapper(b'foobar'))
        update = lwwregister.write(datawrappers.BytesWrapper(b'barfoo'), 1)
        assert isinstance(update, classes.StateUpdate)
        assert lwwregister.read().value == b'barfoo'

    def test_LWWRegister_history_returns_tuple_of_StateUpdate(self):
        lwwregister = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper('foobar'))
        lwwregister.write(datawrappers.StrWrapper('sdsd'), 2)
        lwwregister.write(datawrappers.StrWrapper('barfoo'), 1)
        history = lwwregister.history()

        assert type(history) is tuple
        for item in history:
            assert isinstance(item, classes.StateUpdate)

    def test_LWWRegister_concurrent_writes_bias_to_higher_writer(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock)

        update1 = lwwregister1.write(datawrappers.StrWrapper('foobar'), 1)
        update2 = lwwregister2.write(datawrappers.StrWrapper('barfoo'), 2)
        lwwregister1.update(update2)
        lwwregister2.update(update1)

        assert lwwregister1.read() == lwwregister2.read()
        assert lwwregister1.read().value == 'barfoo'

    def test_LWWRegister_concurrent_writes_bias_to_one_value(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock)

        update1 = lwwregister1.write(datawrappers.StrWrapper('foobar'), 1)
        update2 = lwwregister2.write(datawrappers.StrWrapper('barfoo'), 1)
        lwwregister1.update(update2)
        lwwregister2.update(update1)

        assert lwwregister1.read() == lwwregister2.read()
        assert lwwregister1.read().value == 'foobar'

    def test_LWWRegister_checksums_returns_tuple_of_int(self):
        lwwregister = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper('thing'))
        assert type(lwwregister.checksums()) is tuple
        for item in lwwregister.checksums():
            assert type(item) is int

    def test_LWWRegister_checksums_change_after_update(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper(''))
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper(''), clock=clock)
        checksums1 = lwwregister1.checksums()

        assert lwwregister2.checksums() == checksums1

        lwwregister1.write(datawrappers.StrWrapper('thing'), 1)
        lwwregister2.write(datawrappers.StrWrapper('stuff'), 2)

        assert lwwregister1.checksums() != checksums1
        assert lwwregister2.checksums() != checksums1
        assert lwwregister1.checksums() != lwwregister2.checksums()

    def test_LWWRegister_update_is_idempotent(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock1 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock1)

        update = lwwregister1.write(datawrappers.StrWrapper('foo1'), 1)
        view1 = lwwregister1.read()
        lwwregister1.update(update)
        assert lwwregister1.read() == view1
        lwwregister2.update(update)
        view2 = lwwregister2.read()
        lwwregister2.update(update)
        assert lwwregister2.read() == view2

        update = lwwregister2.write(datawrappers.StrWrapper('bar'), 2)
        lwwregister1.update(update)
        view1 = lwwregister1.read()
        lwwregister1.update(update)
        assert lwwregister1.read() == view1
        lwwregister2.update(update)
        view2 = lwwregister2.read()
        lwwregister2.update(update)
        assert lwwregister2.read() == view2

    def test_LWWRegister_updates_are_commutative(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock1 = classes.ScalarClock(uuid=lwwregister1.clock.uuid)
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock1)

        update1 = lwwregister1.write(datawrappers.StrWrapper('foo1'), 1)
        update2 = lwwregister1.write(datawrappers.StrWrapper('foo2'), 1)
        lwwregister2.update(update2)
        lwwregister2.update(update1)

        assert lwwregister1.read() == lwwregister2.read()

    def test_LWWRegister_update_from_history_converges(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock1 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        clock2 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock1)
        lwwregister3 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock2)

        update = lwwregister1.write(datawrappers.StrWrapper('foo1'), 1)
        lwwregister2.update(update)
        lwwregister2.write(datawrappers.StrWrapper('bar'), 2)

        for item in lwwregister2.history():
            lwwregister1.update(item)
            lwwregister3.update(item)

        assert lwwregister1.read().value == lwwregister2.read().value
        assert lwwregister1.read().value == lwwregister3.read().value
        assert lwwregister1.checksums() == lwwregister2.checksums()
        assert lwwregister1.checksums() == lwwregister3.checksums()

    def test_LWWRegister_pack_unpack_e2e(self):
        lwwregister = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper(''))
        packed = lwwregister.pack()
        unpacked = classes.LWWRegister.unpack(packed)

        assert isinstance(unpacked, classes.LWWRegister)
        assert unpacked.clock == lwwregister.clock
        assert unpacked.read() == lwwregister.read()

    def test_LWWRegister_pack_unpack_e2e_with_injected_clock(self):
        lwwr = classes.LWWRegister(
            name=datawrappers.StrWrapper('test register'),
            clock=StrClock()
        )
        lwwr.write(datawrappers.StrWrapper('first'), 1)
        lwwr.write(datawrappers.StrWrapper('second'), 1)
        packed = lwwr.pack()

        with self.assertRaises(errors.UsageError) as e:
            unpacked = classes.LWWRegister.unpack(packed)
        assert 'StrClock not found' in str(e.exception)

        # inject and repeat
        unpacked = classes.LWWRegister.unpack(packed, {'StrClock': StrClock})

        assert unpacked.clock == lwwr.clock
        assert unpacked.read() == lwwr.read()

    def test_LWWRegister_with_injected_StateUpdateProtocol_class(self):
        lwwr = classes.LWWRegister(
            name=datawrappers.StrWrapper('test register')
        )
        update = lwwr.write(datawrappers.StrWrapper('first'), 1, update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(lwwr.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_LWWRegister_history_return_value_determined_by_from_ts_and_until_ts(self):
        lwwr = classes.LWWRegister(
            name=datawrappers.StrWrapper('test register')
        )
        lwwr.write(datawrappers.StrWrapper('first'), 1)
        lwwr.write(datawrappers.StrWrapper('second'), 1)

        # from_ts in future of last update, history should return nothing
        assert len(lwwr.history(from_ts=99)) == 0

        # until_ts in past of last update, history should return nothing
        assert len(lwwr.history(until_ts=0)) == 0

        # from_ts in past, until_ts in future: history should return update
        assert len(lwwr.history(from_ts=0, until_ts=99)) == 1


if __name__ == '__main__':
    unittest.main()
