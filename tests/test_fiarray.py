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


class TestFIArray(unittest.TestCase):
    def test_FIArray_implements_CRDTProtocol(self):
        assert isinstance(classes.FIArray(), interfaces.CRDTProtocol)

    def test_FIArray_read_returns_tuple_of_underlying_items(self):
        fiarray = classes.FIArray()
        fiarray.positions.extend(
            datawrappers.StrWrapper('first'),
            datawrappers.DecimalWrapper(Decimal('0.1')),
            1
        )
        fiarray.positions.extend(
            datawrappers.BytesWrapper(b'second'),
            datawrappers.DecimalWrapper(Decimal('0.2')),
            1
        )
        view = fiarray.read()
        assert isinstance(view, tuple)
        assert view == ('first', b'second')

    def test_FIArray_read_full_returns_tuple_of_DataWrapperProtocol(self):
        fiarray = classes.FIArray()
        fiarray.positions.extend(
            datawrappers.StrWrapper('first'),
            datawrappers.DecimalWrapper(Decimal('0.1')),
            1
        )
        fiarray.positions.extend(
            datawrappers.BytesWrapper(b'second'),
            datawrappers.DecimalWrapper(Decimal('0.2')),
            1
        )
        view = fiarray.read_full()

        assert isinstance(view, tuple)
        assert len(view) == 2

        for item in view:
            assert isinstance(item, interfaces.DataWrapperProtocol)

        assert view[0].value == 'first'
        assert view[1].value == b'second'

    def test_FIArray_index_between_returns_Decimal_between_first_and_second(self):
        first =  Decimal('0.10001')
        second = Decimal('0.10002')
        index = classes.FIArray.index_between(first, second)

        assert index > first
        assert index < second

    def test_FIArray_put_returns_StateUpdate_with_tuple(self):
        fiarray = classes.FIArray()
        update = fiarray.put(datawrappers.StrWrapper('test'), 1, Decimal('0.5'))

        assert isinstance(update, classes.StateUpdate)
        assert type(update.data) is tuple
        assert len(update.data) == 4
        assert update.data[0] == 'o'
        assert update.data[1] == datawrappers.StrWrapper('test')
        assert update.data[2] == 1
        assert update.data[3] == datawrappers.DecimalWrapper(Decimal('0.5'))

    def test_FIArray_put_changes_view(self):
        fiarray = classes.FIArray()
        view1 = fiarray.read()
        fiarray.put(datawrappers.StrWrapper('test'), 1, Decimal('0.5'))
        view2 = fiarray.read()

        assert view1 != view2

    def test_FIArray_put_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(datawrappers.StrWrapper('test'), 1, Decimal('0.5'))
        fiarray.put(datawrappers.StrWrapper('foo'), 1, Decimal('0.25'))
        update = fiarray.put(datawrappers.StrWrapper('bar'), 1, Decimal('0.375'))
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'foo'
        assert view[1] == 'bar'
        assert view[2] == 'test'

    def test_FIArray_put_between_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(datawrappers.StrWrapper('first'), 1, Decimal('0.5'))
        fiarray.put(datawrappers.StrWrapper('last'), 1, Decimal('0.75'))
        update = fiarray.put_between(datawrappers.StrWrapper('middle'), 1,
            datawrappers.StrWrapper('first'), datawrappers.StrWrapper('last'))
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'first'
        assert view[1] == 'middle'
        assert view[2] == 'last'

    def test_FIArray_put_before_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(datawrappers.StrWrapper('last'), 1, Decimal('0.5'))
        fiarray.put(datawrappers.StrWrapper('middle'), 1, Decimal('0.25'))
        update = fiarray.put_before(datawrappers.StrWrapper('first'), 1, datawrappers.StrWrapper('middle'))
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'first'
        assert view[1] == 'middle'
        assert view[2] == 'last'

    def test_FIArray_put_after_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(datawrappers.StrWrapper('first'), 1, Decimal('0.5'))
        fiarray.put(datawrappers.StrWrapper('middle'), 1, Decimal('0.75'))
        update = fiarray.put_after(datawrappers.StrWrapper('last'), 1, datawrappers.StrWrapper('middle'))
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'first'
        assert view[1] == 'middle'
        assert view[2] == 'last'

    def test_FIArray_put_first_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put_first(datawrappers.StrWrapper('test'), 1)
        fiarray.put_first(datawrappers.StrWrapper('bar'), 1)
        update = fiarray.put_first(datawrappers.StrWrapper('foo'), 1)
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'foo'
        assert view[1] == 'bar'
        assert view[2] == 'test'

    def test_FIArray_put_last_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put_last(datawrappers.StrWrapper('foo'), 1)
        fiarray.put_last(datawrappers.StrWrapper('bar'), 1)
        fiarray.put_last(datawrappers.StrWrapper('test'), 1)
        view = fiarray.read_full()

        assert len(view) == 3
        assert view[0] == datawrappers.StrWrapper('foo')
        assert view[1] == datawrappers.StrWrapper('bar')
        assert view[2] == datawrappers.StrWrapper('test')

    def test_FIArray_delete_returns_StateUpdate_with_tuple(self):
        fiarray = classes.FIArray()
        update = fiarray.delete(datawrappers.StrWrapper('test'), 1)

        assert type(update) is classes.StateUpdate
        assert type(update.data) is tuple
        assert len(update.data) == 4
        assert update.data[0] == 'r'
        assert update.data[1] == datawrappers.StrWrapper('test')
        assert update.data[2] == 1
        assert update.data[3] == datawrappers.NoneWrapper()

    def test_FIArray_delete_removes_item(self):
        fiarray = classes.FIArray()
        fiarray.put_first(datawrappers.StrWrapper('test'), 1)

        assert fiarray.read()[0] == 'test'
        fiarray.delete(datawrappers.StrWrapper('test'), 1)
        assert fiarray.read() == tuple()

    def test_FIArray_history_returns_tuple_of_StateUpdateProtocol(self):
        fiarray = classes.FIArray()
        fiarray.put_first(datawrappers.StrWrapper('test'), 1)
        fiarray.put_first(datawrappers.StrWrapper('fdfdf'), 1)
        history = fiarray.history()

        assert type(history) is tuple
        for update in history:
            assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_FIArray_concurrent_puts_bias_to_higher_writer(self):
        fiarray1 = classes.FIArray()
        fiarray2 = classes.FIArray(clock=classes.ScalarClock(uuid=fiarray1.clock.uuid))
        update1 = fiarray1.put(datawrappers.StrWrapper('test'), 1, Decimal('0.75'))
        update2 = fiarray2.put(datawrappers.StrWrapper('test'), 2, Decimal('0.25'))
        update3 = fiarray1.put(datawrappers.StrWrapper('middle'), 1, Decimal('0.5'))
        fiarray1.update(update2)
        fiarray2.update(update1)
        fiarray2.update(update3)

        assert fiarray1.checksums() == fiarray2.checksums()
        assert fiarray1.read()[0] == 'test'

    def test_FIArray_checksums_returns_tuple_of_int(self):
        fiarray = classes.FIArray()
        fiarray.put(datawrappers.StrWrapper('foo'), 1, Decimal('0.25'))
        checksums = fiarray.checksums()

        assert type(checksums) is tuple
        for item in checksums:
            assert type(item) is int

    def test_FIArray_checksums_change_after_update(self):
        fiarray = classes.FIArray()
        fiarray.put(datawrappers.StrWrapper('foo'), 1, Decimal('0.25'))
        checksums1 = fiarray.checksums()
        fiarray.put(datawrappers.StrWrapper('foo'), 1, Decimal('0.5'))
        checksums2 = fiarray.checksums()
        fiarray.put(datawrappers.StrWrapper('oof'), 1, Decimal('0.35'))
        checksums3 = fiarray.checksums()

        assert checksums1 != checksums2
        assert checksums1 != checksums3
        assert checksums2 != checksums3

    def test_FIArray_update_is_idempotent(self):
        fiarray = classes.FIArray()
        update = fiarray.put(datawrappers.StrWrapper('foo'), 1, Decimal('0.25'))
        checksums1 = fiarray.checksums()
        view1 = fiarray.read()
        fiarray.update(update)
        checksums2 = fiarray.checksums()
        view2 = fiarray.read()

        assert checksums1 == checksums2
        assert view1 == view2

    def test_FIArray_updates_are_commutative(self):
        fiarray1 = classes.FIArray()
        fiarray2 = classes.FIArray(clock=classes.ScalarClock(0, fiarray1.clock.uuid))
        fiarray3 = classes.FIArray(clock=classes.ScalarClock(0, fiarray1.clock.uuid))
        update1 = fiarray1.put(datawrappers.StrWrapper('test'), 1, Decimal('0.75'))
        update2 = fiarray1.put(datawrappers.StrWrapper('test'), 2, Decimal('0.25'))
        update3 = fiarray1.put(datawrappers.StrWrapper('middle'), 1, Decimal('0.5'))

        fiarray2.update(update1)
        fiarray2.update(update2)
        fiarray2.update(update3)
        fiarray3.update(update3)
        fiarray3.update(update2)
        fiarray3.update(update1)

        assert fiarray1.read() == fiarray2.read() == fiarray3.read()

    def test_FIArray_converges_from_history(self):
        fiarray1 = classes.FIArray()
        fiarray2 = classes.FIArray(clock=classes.ScalarClock(0, fiarray1.clock.uuid))
        fiarray1.put(datawrappers.StrWrapper('foo'), 1, Decimal('0.25'))
        fiarray1.put(datawrappers.StrWrapper('test'), 1, Decimal('0.15'))
        fiarray1.put(datawrappers.StrWrapper('bar'), 1, Decimal('0.5'))

        for state_update in fiarray2.history():
            fiarray1.update(state_update)
        for state_update in fiarray1.history():
            fiarray2.update(state_update)

        fiarray2.delete(datawrappers.StrWrapper('test'), 1)
        fiarray2.put(datawrappers.StrWrapper('something'), 2, Decimal('0.333'))
        fiarray2.put(datawrappers.StrWrapper('something else'), 2, Decimal('0.777'))

        for state_update in fiarray1.history():
            fiarray2.update(state_update)
        for state_update in fiarray2.history():
            fiarray1.update(state_update)

        assert fiarray1.read() == fiarray2.read()

    def test_FIArray_pack_unpack_e2e(self):
        fiarray = classes.FIArray()
        fiarray.put_first(datawrappers.StrWrapper('test'), 1)
        fiarray.put_last(datawrappers.BytesWrapper(b'test'), 1)
        packed = fiarray.pack()
        unpacked = classes.FIArray.unpack(packed)

        assert fiarray.checksums() == unpacked.checksums()
        assert fiarray.read() == unpacked.read()

        update = unpacked.put_last(datawrappers.StrWrapper('middle'), 2)
        fiarray.update(update)

        assert fiarray.checksums() == unpacked.checksums()
        assert fiarray.read() == unpacked.read()

    def test_FIArray_pack_unpack_e2e_with_injected_clock(self):
        fia = classes.FIArray(clock=StrClock())
        fia.put_first(datawrappers.StrWrapper('first'), 1)
        fia.put_last(datawrappers.StrWrapper('last'), 1)
        packed = fia.pack()

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.FIArray.unpack(packed)
        assert str(e.exception) == 'cannot find StrClock'

        # inject and repeat
        unpacked = classes.FIArray.unpack(packed, {'StrClock': StrClock})

        assert unpacked.clock == fia.clock
        assert unpacked.read() == fia.read()

    def test_FIArray_with_injected_StateUpdateProtocol_class(self):
        fia = classes.FIArray()
        update = fia.put_first(datawrappers.StrWrapper('first'), 1, update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(fia.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate


if __name__ == '__main__':
    unittest.main()
