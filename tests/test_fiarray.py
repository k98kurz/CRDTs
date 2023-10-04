from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import permutations
from uuid import uuid4
from context import classes, interfaces, datawrappers, errors
import packify
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


class TestFIArray(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        self.inject = {
            'BytesWrapper': datawrappers.BytesWrapper,
            'StrWrapper': datawrappers.StrWrapper,
            'IntWrapper': datawrappers.IntWrapper,
            'DecimalWrapper': datawrappers.DecimalWrapper,
            'CTDataWrapper': datawrappers.CTDataWrapper,
            'RGAItemWrapper': datawrappers.RGAItemWrapper,
            'FIAItemWrapper': datawrappers.FIAItemWrapper,
            'NoneWrapper': datawrappers.NoneWrapper,
            'ScalarClock': classes.ScalarClock,
        }
        super().__init__(methodName)

    def test_FIArray_implements_CRDTProtocol(self):
        assert isinstance(classes.FIArray(), interfaces.CRDTProtocol)

    def test_FIArray_read_returns_tuple_of_underlying_items(self):
        fiarray = classes.FIArray()
        first = datawrappers.FIAItemWrapper(
            value='first',
            index=Decimal('0.1'),
            uuid=uuid4().bytes,
        )
        second = datawrappers.FIAItemWrapper(
            value=b'second',
            index=Decimal('0.2'),
            uuid=uuid4().bytes,
        )
        fiarray.positions.set(
            datawrappers.BytesWrapper(first.uuid),
            first,
            1
        )
        fiarray.positions.set(
            datawrappers.BytesWrapper(second.uuid),
            second,
            1
        )
        view = fiarray.read()
        assert isinstance(view, tuple)
        assert view == ('first', b'second')

    def test_FIArray_read_full_returns_tuple_of_FIAItemWrapper(self):
        fiarray = classes.FIArray()
        first = datawrappers.FIAItemWrapper(
            value='first',
            index=Decimal('0.1'),
            uuid=uuid4().bytes,
        )
        second = datawrappers.FIAItemWrapper(
            value=b'second',
            index=Decimal('0.2'),
            uuid=uuid4().bytes,
        )
        fiarray.positions.set(
            datawrappers.BytesWrapper(first.uuid),
            first,
            1
        )
        fiarray.positions.set(
            datawrappers.BytesWrapper(second.uuid),
            second,
            1
        )
        view = fiarray.read_full()

        assert isinstance(view, tuple)
        assert len(view) == 2

        for item in view:
            assert isinstance(item, datawrappers.FIAItemWrapper)

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
        update = fiarray.put(
            datawrappers.StrWrapper('test'), 1, Decimal('0.5')
        )

        assert isinstance(update, classes.StateUpdate)
        assert type(update.data) is tuple
        assert len(update.data) == 4
        assert update.data[0] == 'o'
        assert isinstance(update.data[1], datawrappers.BytesWrapper)
        assert update.data[2] == 1
        assert isinstance(update.data[3], datawrappers.FIAItemWrapper)
        assert update.data[3].index.value == Decimal('0.5')

    def test_FIArray_put_changes_view(self):
        fiarray = classes.FIArray()
        view1 = fiarray.read(inject=self.inject)
        fiarray.put(datawrappers.StrWrapper('test'), 1, Decimal('0.5'))
        view2 = fiarray.read(inject=self.inject)

        assert view1 != view2

    def test_FIArray_put_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(('test'), 1, Decimal('0.5'))
        fiarray.put(('foo'), 1, Decimal('0.25'))
        update = fiarray.put(('bar'), 1, Decimal('0.375'))
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'foo'
        assert view[1] == 'bar'
        assert view[2] == 'test'

    def test_FIArray_put_between_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        first = fiarray.put(('first'), 1, Decimal('0.5')).data[3]
        last = fiarray.put(('last'), 1, Decimal('0.75')).data[3]
        update = fiarray.put_between(('middle'), 1, first, last)
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'first'
        assert view[1] == 'middle'
        assert view[2] == 'last'

    def test_FIArray_put_before_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(('last'), 1, Decimal('0.5'))
        middle = fiarray.put(('middle'), 1, Decimal('0.25')).data[3]
        update = fiarray.put_before('first', 1, middle)
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'first'
        assert view[1] == 'middle'
        assert view[2] == 'last'

    def test_FIArray_put_after_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put(('first'), 1, Decimal('0.5'))
        middle = fiarray.put(('middle'), 1, Decimal('0.75')).data[3]
        update = fiarray.put_after(('last'), 1, middle)
        view = fiarray.read()

        assert type(update) is classes.StateUpdate
        assert len(view) == 3
        assert view[0] == 'first'
        assert view[1] == 'middle'
        assert view[2] == 'last'

    def test_FIArray_put_first_results_in_correct_order_read(self):
        fiarray = classes.FIArray()
        fiarray.put_first(('test'), 1)
        fiarray.put_first(('bar'), 1)
        update = fiarray.put_first(('foo'), 1)
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
        assert view[0].value == datawrappers.StrWrapper('foo')
        assert view[1].value == datawrappers.StrWrapper('bar')
        assert view[2].value == datawrappers.StrWrapper('test')

    def test_FIArray_delete_returns_StateUpdate_with_tuple(self):
        fiarray = classes.FIArray()
        first = fiarray.put_first('test', 1).data[3]
        update = fiarray.delete(first, 1)

        assert type(update) is classes.StateUpdate
        assert type(update.data) is tuple
        assert len(update.data) == 4
        assert update.data[0] == 'r'
        assert isinstance(update.data[1], datawrappers.BytesWrapper)
        assert update.data[2] == 1
        assert update.data[3]== datawrappers.NoneWrapper()

    def test_FIArray_delete_removes_item(self):
        fiarray = classes.FIArray()
        first = fiarray.put_first(('test'), 1).data[3]

        assert fiarray.read()[0] == 'test'
        fiarray.delete(first, 1)
        assert fiarray.read() == tuple()

    def test_FIArray_move_item_returns_StateUpdate_and_moves_item_to_new_index(self):
        fiarray = classes.FIArray()
        second = fiarray.put('second', 1, Decimal('0.5')).data[3]
        first = fiarray.put_after('first', 1, second).data[3]
        third = fiarray.put_first('third', 1).data[3]
        assert fiarray.read() == ('third', 'second', 'first')

        update = fiarray.move_item(first, 1, before=third)
        assert isinstance(update, interfaces.StateUpdateProtocol)
        assert fiarray.read() == ('first', 'third', 'second')

        fiarray.move_item(first, 1, after=second)
        assert fiarray.read() == ('third', 'second', 'first')

        fiarray.move_item(first, 1, new_index=Decimal("0.1"))
        assert fiarray.read() == ('first', 'third', 'second')

        fiarray.move_item(second, 1, after=first, before=third)
        assert fiarray.read() == ('first', 'second', 'third')

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
        update2 = fiarray2.put(('test'), 2, Decimal('0.25'))
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
        item = fiarray1.put(datawrappers.StrWrapper('test'), 1, Decimal('0.15')).data[3]
        fiarray1.put(datawrappers.StrWrapper('bar'), 1, Decimal('0.5'))

        for state_update in fiarray2.history():
            fiarray1.update(state_update)
        for state_update in fiarray1.history():
            fiarray2.update(state_update)

        fiarray2.delete(item, 1)
        fiarray2.put(datawrappers.StrWrapper('something'), 2, Decimal('0.333'))
        fiarray2.put(datawrappers.StrWrapper('something else'), 2, Decimal('0.777'))

        for state_update in fiarray1.history():
            fiarray2.update(state_update)
        for state_update in fiarray2.history():
            fiarray1.update(state_update)

        view1 = fiarray1.read()
        view2 = fiarray2.read()
        assert view1 == view2, f'{view1} != {view2}'

        histories = permutations(fiarray1.history())
        for history in histories:
            fiarray3 = classes.FIArray(clock=classes.ScalarClock(0, fiarray1.clock.uuid))
            for update in history:
                fiarray3.update(update)
            view3 = fiarray3.read()
            assert view3 == view1, f'{view3} != {view1}'

    def test_FIArray_pack_unpack_e2e(self):
        fiarray = classes.FIArray()
        fiarray.put_first(datawrappers.StrWrapper('test'), 1)
        fiarray.put_last(datawrappers.BytesWrapper(b'test'), 1)
        packed = fiarray.pack()
        unpacked = classes.FIArray.unpack(packed, inject=self.inject)

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

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.FIArray.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.FIArray.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock == fia.clock
        assert unpacked.read() == fia.read()

    def test_FIArray_with_injected_StateUpdateProtocol_class(self):
        fia = classes.FIArray()
        update = fia.put_first(datawrappers.StrWrapper('first'), 1, update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(fia.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_FIArray_convergence_from_ts(self):
        fiarray1 = classes.FIArray()
        fiarray2 = classes.FIArray()
        fiarray2.clock.uuid = fiarray1.clock.uuid
        for i in range(5):
            update = fiarray2.put_first(datawrappers.IntWrapper(i), i)
            fiarray1.update(update)
        assert fiarray1.checksums() == fiarray2.checksums()

        fiarray1.put_last(datawrappers.IntWrapper(69420), 1)
        fiarray1.put_last(datawrappers.IntWrapper(42069), 1)
        fiarray2.put_last(datawrappers.IntWrapper(23212), 2)

       # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = fiarray1.clock.read()
        while fiarray1.checksums(from_ts=from_ts, until_ts=until_ts) != \
            fiarray2.checksums(from_ts=from_ts, until_ts=until_ts) \
            and until_ts > 0:
            until_ts -= 1
        from_ts = until_ts
        assert from_ts > 0

        for update in fiarray1.history(from_ts=from_ts):
            fiarray2.update(update)
        for update in fiarray2.history(from_ts=from_ts):
            fiarray1.update(update)

        assert fiarray1.checksums() == fiarray2.checksums()

        # prove it does not converge from bad ts parameters
        fiarray2 = classes.FIArray()
        fiarray2.clock.uuid = fiarray1.clock.uuid
        for update in fiarray1.history(until_ts=0):
            fiarray2.update(update)
        assert fiarray1.checksums() != fiarray2.checksums()

        fiarray2 = classes.FIArray()
        fiarray2.clock.uuid = fiarray1.clock.uuid
        for update in fiarray1.history(from_ts=99):
            fiarray2.update(update)
        assert fiarray1.checksums() != fiarray2.checksums()

    def test_FIArray_normalize_evenly_spaces_existing_items(self):
        fia = classes.FIArray()
        fia.put('first', 1, Decimal('0.9'))
        fia.put('second', 1, Decimal('0.91'))
        fia.put('third', 1, Decimal('0.92'))
        assert fia.read() == ('first', 'second', 'third')

        sus = fia.normalize(1)
        assert type(sus) is tuple
        for su in sus:
            assert isinstance(su, interfaces.StateUpdateProtocol)

        assert fia.read() == ('first', 'second', 'third')
        indices = [f.index.value for f in fia.read_full()]
        index_space = Decimal("1")/Decimal("4")

        for i in range(len(indices)):
            assert indices[i] == index_space*Decimal(i)

    def test_FIArray_merkle_history_e2e(self):
        fia1 = classes.FIArray()
        fia2 = classes.FIArray(clock=classes.ScalarClock(0, fia1.clock.uuid))
        fia2.update(fia1.put_first('hello world', 1))
        fia2.update(fia1.put_last(b'hello world', 1))
        fia1.delete(fia1.read_full()[0], 1)
        fia1.put_last('not the lipsum', 1)
        fia2.put_last(b'yellow submarine', 2)

        history1 = fia1.get_merkle_history()
        assert type(history1) in (list, tuple), \
            'history must be [bytes, [bytes, ], dict]'
        assert len(history1) == 3, \
            'history must be [bytes, [bytes, ], dict]'
        assert all([type(leaf) is bytes for leaf in history1[1]]), \
            'history must be [bytes, [bytes, ], dict]'
        assert all([
            type(leaf_id) is type(leaf) is bytes
            for leaf_id, leaf in history1[2].items()
        ]), 'history must be [[bytes, ], bytes, dict[bytes, bytes]]'
        assert all([leaf_id in history1[2] for leaf_id in history1[1]]), \
            'history[2] dict must have all keys in history[1] list'

        history2 = fia2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = fia1.resolve_merkle_histories(history2)
        diff2 = fia2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 2, [d.hex() for d in diff1]
        assert len(diff2) == 2, [d.hex() for d in diff2]

        # print('')
        # print(fia1.read_full())
        # print(fia2.read_full())
        # print('')

        # synchronize
        for cid in diff1:
            update = classes.StateUpdate.unpack(cidmap2[cid], inject=self.inject)
            # print(update)
            fia1.update(update)
        # print('')
        for cid in diff2:
            update = classes.StateUpdate.unpack(cidmap1[cid], inject=self.inject)
            # print(update)
            fia2.update(update)

        # print('')
        # print(fia1.read_full())
        # print(fia2.read_full())
        assert fia1.checksums() == fia2.checksums(), f"\n{fia1.read_full()}\n{fia2.read_full()}"


if __name__ == '__main__':
    unittest.main()
