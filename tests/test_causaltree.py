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


class TestCausalTree(unittest.TestCase):
    def test_CausalTree_implements_CRDTProtocol(self):
        assert isinstance(classes.CausalTree(), interfaces.CRDTProtocol)

    def test_CausalTree_read_returns_tuple_of_underlying_items(self):
        causaltree = classes.CausalTree()
        causaltree.positions.extend(
            datawrappers.BytesWrapper(b'first'),
            datawrappers.CTDataWrapper(
                datawrappers.StrWrapper('first'),
                b'first',
                b''
            ),
            1
        )
        causaltree.positions.extend(
            datawrappers.BytesWrapper(b'second'),
            datawrappers.CTDataWrapper(
                datawrappers.BytesWrapper(b'second'),
                b'second',
                b'first'
            ),
            1
        )
        view = causaltree.read()
        assert isinstance(view, tuple)
        assert view == ('first', b'second')

    def test_CausalTree_read_full_returns_tuple_of_DataWrapperProtocol(self):
        causaltree = classes.CausalTree()
        causaltree.positions.extend(
            datawrappers.BytesWrapper(b'first'),
            datawrappers.CTDataWrapper(
                datawrappers.StrWrapper('first'),
                b'first',
                b''
            ),
            1
        )
        causaltree.positions.extend(
            datawrappers.BytesWrapper(b'second'),
            datawrappers.CTDataWrapper(
                datawrappers.BytesWrapper(b'second'),
                b'second',
                b'first'
            ),
            1
        )
        view = causaltree.read_full()

        assert isinstance(view, tuple)
        assert len(view) == 2

        for item in view:
            assert isinstance(item, datawrappers.CTDataWrapper)

        assert view[0].value.value == 'first'
        assert view[1].value.value == b'second'

    def test_CausalTree_put_changes_view_and_results_in_correct_ordering(self):
        causaltree = classes.CausalTree()
        view1 = causaltree.read()

        su = causaltree.put(
            datawrappers.StrWrapper("first"),
            1,
            b'first'
        )
        assert type(su) is classes.StateUpdate
        view2 = causaltree.read()

        su = causaltree.put(
            datawrappers.StrWrapper("third"),
            1,
            b'third',
            b'first'
        )
        assert type(su) is classes.StateUpdate
        view3 = causaltree.read()

        su = causaltree.put(
            datawrappers.StrWrapper("second"),
            1,
            b'second',
            b'first'
        )
        assert type(su) is classes.StateUpdate
        view4 = causaltree.read()

        assert view1 == tuple()
        assert view2 == ('first',)
        assert view3 == ('first', 'third')
        assert view4 == ('first', 'second', 'third')

    def test_CausalTree_put_first_and_put_after_change_view_and_results_in_correct_ordering(self):
        causaltree = classes.CausalTree()
        view1 = causaltree.read()

        su = causaltree.put_first(
            datawrappers.StrWrapper("first"),
            1,
        )
        assert type(su) is classes.StateUpdate
        view2 = causaltree.read()

        parent = causaltree.read_full()[0]
        assert type(parent) is datawrappers.CTDataWrapper

        su = causaltree.put_after(
            datawrappers.StrWrapper("second"),
            1,
            parent.uuid
        )
        assert type(su) is classes.StateUpdate
        view3 = causaltree.read()

        assert view1 == tuple()
        assert view2 == ('first',)
        assert view3 == ('first', 'second')

    def test_CausalTree_move_item_changes_view_and_results_in_correct_ordering(self):
        causaltree = classes.CausalTree()

        causaltree.put_first(
            datawrappers.StrWrapper("second"),
            1,
        )
        parent = causaltree.read_full()[0]
        causaltree.put_after(
            datawrappers.StrWrapper("first"),
            1,
            parent.uuid
        )
        view1 = causaltree.read()
        assert view1 == ('second', 'first')

        second_item = causaltree.read_full()[0]
        first_item = causaltree.read_full()[1]
        causaltree.move_item(first_item, 1)
        causaltree.move_item(second_item, 1, first_item.uuid)
        view2 = causaltree.read()

        ct2 = classes.CausalTree()
        ct2.clock.uuid = causaltree.clock.uuid

        for state_update in causaltree.history():
            ct2.update(state_update)

        assert view2 == ('first', 'second')

    def test_CausalTree_circular_references_are_kept_in_separate_view(self):
        causaltree = classes.CausalTree()

        causaltree.put_first(
            datawrappers.StrWrapper("item1"),
            1,
        )
        parent = causaltree.read_full()[0]
        causaltree.put_after(
            datawrappers.StrWrapper("item2"),
            1,
            parent.uuid
        )
        view1 = causaltree.read()
        assert view1 == ('item1', 'item2')

        item1 = causaltree.read_full()[0]
        item2 = causaltree.read_full()[1]
        assert item1.parent_uuid == b''
        assert item2.parent_uuid == item1.uuid
        causaltree.move_item(item1, 1, item2.uuid)
        items: list[datawrappers.CTDataWrapper] = [
            v.value for _, v in causaltree.positions.registers.items()
        ]
        assert items[0].parent_uuid == items[1].uuid
        assert items[1].parent_uuid == items[0].uuid
        full2 = causaltree.read_full()
        view2 = causaltree.read()
        assert len(full2) == 0
        assert len(view2) == 0

        assert hasattr(causaltree, 'read_excluded') and callable(causaltree.read_excluded)
        excluded = causaltree.read_excluded()
        assert type(excluded) is list
        assert items[0] in excluded
        assert items[1] in excluded
        for item in excluded:
            assert item in items

    def test_CausalTree_history_returns_tuple_of_StateUpdateProtocol_that_converge(self):
        causaltree = classes.CausalTree()
        causaltree.put_first(datawrappers.StrWrapper('first'), 1)
        first = causaltree.read_full()[0]
        causaltree.put_after(datawrappers.StrWrapper('second'), 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after(datawrappers.StrWrapper('third'), 1, second.uuid)
        causaltree.put_first(datawrappers.StrWrapper('alt_first'), 1)
        expected = causaltree.read()

        history = causaltree.history()
        assert type(history) is tuple
        for update in history:
            assert isinstance(update, interfaces.StateUpdateProtocol)

        for _ in range(5):
            ct2 = classes.CausalTree()
            ct2.clock.uuid = causaltree.clock.uuid
            for update in history:
                ct2.update(update)

            assert ct2.checksums() == causaltree.checksums()
            view = ct2.read()
            assert view == expected, f'expected {expected} but encountered {view}'

    def test_CausalTree_concurrent_updates_converge(self):
        ct1 = classes.CausalTree()
        ct2 = classes.CausalTree()
        ct2.clock.uuid = ct1.clock.uuid
        ct2.positions.clock.uuid = ct1.positions.clock.uuid

        first = ct1.put_first(datawrappers.StrWrapper('first'), 1).data[3]
        ct1.put_after(datawrappers.StrWrapper('second'), 1, first.uuid)
        alt_first = ct2.put_first(datawrappers.StrWrapper('other first'), 1).data[3]
        ct2.put_after(datawrappers.StrWrapper('other second'), 1, alt_first.uuid)

        for update in ct1.history():
            ct2.update(update)
            ct2.update(update)
        for update in ct2.history():
            ct1.update(update)
            ct1.update(update)

        assert ct1.read() == ct2.read()

    def test_CausalTree_pack_unpack_e2e(self):
        causaltree = classes.CausalTree()
        causaltree.put_first(datawrappers.StrWrapper('first'), 1)
        first = causaltree.read_full()[0]
        causaltree.put_after(datawrappers.BytesWrapper(b'second'), 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after(datawrappers.IntWrapper(3), 1, second.uuid)
        causaltree.put_first(datawrappers.DecimalWrapper(Decimal('21.012')), 1)
        packed = causaltree.pack()
        unpacked = classes.CausalTree.unpack(packed)

        assert unpacked.clock.uuid == causaltree.clock.uuid
        assert unpacked.read() == causaltree.read()
        assert unpacked.read_full() == causaltree.read_full()

    def test_CausalTree_pack_unpack_e2e_with_injected_clock(self):
        causaltree = classes.CausalTree(clock=StrClock())
        causaltree.put_first(datawrappers.StrWrapper('first'), 1)
        first = causaltree.read_full()[0]
        causaltree.put_after(datawrappers.BytesWrapper(b'second'), 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after(datawrappers.IntWrapper(3), 1, second.uuid)
        causaltree.put_first(datawrappers.DecimalWrapper(Decimal('21.012')), 1)

        packed = causaltree.pack()
        unpacked = classes.CausalTree.unpack(packed, {'StrClock': StrClock})

        assert unpacked.clock.uuid == causaltree.clock.uuid
        assert unpacked.read() == causaltree.read()
        assert unpacked.read_full() == causaltree.read_full()

    def test_CausalTree_with_injected_StateUpdateProtocol_class(self):
        causaltree = classes.CausalTree(clock=StrClock())
        update = causaltree.put_first(
            datawrappers.BytesWrapper(b'first'),
            1,
            update_class=CustomStateUpdate
        )
        assert type(update) is CustomStateUpdate
        assert type(causaltree.history(update_class=CustomStateUpdate)[0] is CustomStateUpdate)
        assert causaltree.read() == (b'first',)


if __name__ == '__main__':
    unittest.main()
