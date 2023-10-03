from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import permutations
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


class TestCausalTree(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        self.inject = {
            'BytesWrapper': datawrappers.BytesWrapper,
            'StrWrapper': datawrappers.StrWrapper,
            'IntWrapper': datawrappers.IntWrapper,
            'DecimalWrapper': datawrappers.DecimalWrapper,
            'CTDataWrapper': datawrappers.CTDataWrapper,
            'RGAItemWrapper': datawrappers.RGAItemWrapper,
            'NoneWrapper': datawrappers.NoneWrapper,
            'ScalarClock': classes.ScalarClock,
        }
        super().__init__(methodName)

    def test_CausalTree_implements_CRDTProtocol(self):
        assert isinstance(classes.CausalTree(), interfaces.CRDTProtocol)

    def test_CausalTree_read_returns_tuple_of_underlying_items(self):
        causaltree = classes.CausalTree()
        causaltree.positions.set(
            datawrappers.BytesWrapper(b'first'),
            datawrappers.CTDataWrapper(
                'first',
                b'first',
                b''
            ),
            1
        )
        causaltree.positions.set(
            datawrappers.BytesWrapper(b'second'),
            datawrappers.CTDataWrapper(
                b'second',
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
        causaltree.positions.set(
            datawrappers.BytesWrapper(b'first'),
            datawrappers.CTDataWrapper(
                datawrappers.StrWrapper('first'),
                b'first',
                b''
            ),
            1
        )
        causaltree.positions.set(
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
            "first",
            1,
            b'first'
        )
        assert type(su) is classes.StateUpdate
        view2 = causaltree.read()

        su = causaltree.put(
            "third",
            1,
            b'third',
            b'first'
        )
        assert type(su) is classes.StateUpdate
        view3 = causaltree.read()

        su = causaltree.put(
            "second",
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

        sus = causaltree.put_first(
            "first",
            1,
        )
        assert type(sus) is tuple
        for su in sus:
            assert type(su) is classes.StateUpdate
        view2 = causaltree.read()

        parent = causaltree.read_full()[0]
        assert type(parent) is datawrappers.CTDataWrapper

        su = causaltree.put_after(
            "second",
            1,
            parent.uuid
        )
        assert type(su) is classes.StateUpdate
        view3 = causaltree.read()

        assert view1 == tuple()
        assert view2 == ('first',)
        assert view3 == ('first', 'second')

    def test_CausalTree_delete_removes_item(self):
        causaltree = classes.CausalTree()
        causaltree.put_first(b'first', 1)
        assert b'first' in causaltree.read()
        first = causaltree.read_full()[0]
        causaltree.delete(first, 1)
        assert b'first' not in causaltree.read(), causaltree.read_full()

    def test_CausalTree_move_item_changes_view_and_results_in_correct_ordering(self):
        causaltree = classes.CausalTree()

        causaltree.put_first(
            "second",
            1,
        )
        parent = causaltree.read_full()[0]
        causaltree.put_after(
            "first",
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
        assert view2 == ('first', 'second'), \
            f"\nexpected=('first', 'second')\nobserved={view2}"

        ct2 = classes.CausalTree()
        ct2.clock.uuid = causaltree.clock.uuid

        for state_update in causaltree.history():
            ct2.update(state_update)

        view3 = ct2.read()
        assert view2 == view3

    def test_CausalTree_circular_references_are_kept_in_separate_view(self):
        causaltree = classes.CausalTree()

        causaltree.put_first(
            "item1",
            1,
        )
        parent = causaltree.read_full()[0]
        causaltree.put_after(
            "item2",
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
        causaltree.put_first('first', 1)
        first = causaltree.read_full()[0]
        causaltree.put_after('second', 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after('third', 1, second.uuid)
        causaltree.put_first('alt_first', 1)
        expected = causaltree.read()

        history = causaltree.history()
        assert type(history) is tuple
        for update in history:
            assert isinstance(update, interfaces.StateUpdateProtocol)

        histories = permutations(history)

        for history in histories:
            ct2 = classes.CausalTree()
            ct2.clock.uuid = causaltree.clock.uuid
            for update in history:
                ct2.update(update)

            assert ct2.checksums() == causaltree.checksums()
            view = ct2.read()
            assert view == expected, self.debug_info(causaltree, ct2, history)

    def test_CausalTree_history_convergence_Heisenbug_1(self):
        causaltree = classes.CausalTree()
        causaltree.put_first(datawrappers.StrWrapper('first'), 1)
        first = causaltree.read_full()[0]
        causaltree.put_after(datawrappers.StrWrapper('second'), 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after(datawrappers.StrWrapper('third'), 1, second.uuid)
        causaltree.put(datawrappers.StrWrapper('alt_first'), 1, first.uuid + b'f')
        expected = causaltree.read()

        # first Heisenbug encountered: updates applied in order 1,2,4,3
        history = causaltree.history()
        updates = []
        updates.append([update for update in history if update.ts == 1][0])
        updates.append([update for update in history if update.ts == 2][0])
        updates.append([update for update in history if update.ts == 4][0])
        updates.append([update for update in history if update.ts == 3][0])

        ct2 = classes.CausalTree()
        ct2.clock.uuid = causaltree.clock.uuid
        for update in updates:
            ct2.update(update)

        assert ct2.checksums() == causaltree.checksums()
        view = ct2.read()
        assert view == expected, f'{expected} != {view}'

    def test_CausalTree_history_convergence_Heisenbug_2(self):
        causaltree = classes.CausalTree()
        causaltree.put_first(datawrappers.StrWrapper('first'), 1)
        first = causaltree.read_full()[0]
        causaltree.put_after(datawrappers.StrWrapper('second'), 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after(datawrappers.StrWrapper('third'), 1, second.uuid)
        causaltree.put(datawrappers.StrWrapper('alt_first'), 1, first.uuid + b'f')
        expected = causaltree.read()

        # second Heisenbug encountered: updates applied in order 2,1,4,3
        history = causaltree.history()
        updates = []
        updates.append([update for update in history if update.ts == 2][0])
        updates.append([update for update in history if update.ts == 1][0])
        updates.append([update for update in history if update.ts == 4][0])
        updates.append([update for update in history if update.ts == 3][0])

        ct2 = classes.CausalTree()
        ct2.clock.uuid = causaltree.clock.uuid
        for update in updates:
            ct2.update(update)

        assert ct2.checksums() == causaltree.checksums()
        view = ct2.read()
        assert view == expected, f'\n{expected=}\n{view=}'

    def test_CausalTree_concurrent_updates_converge(self):
        ct1 = classes.CausalTree()
        ct2 = classes.CausalTree()
        ct2.clock.uuid = ct1.clock.uuid
        ct2.positions.clock.uuid = ct1.positions.clock.uuid

        first = ct1.put_first(datawrappers.StrWrapper('first'), 1)[0].data[3]
        ct1.put_after(datawrappers.StrWrapper('second'), 1, first.uuid)
        alt_first = ct2.put_first(datawrappers.StrWrapper('other first'), 1)[0].data[3]
        ct2.put_after(datawrappers.StrWrapper('other second'), 1, alt_first.uuid)

        for update in ct1.history():
            ct2.update(update)
        for update in ct2.history():
            ct1.update(update)

        view1 = ct1.read()
        view2 = ct2.read()
        assert view1 == view2, f"\nexpected={view1}\nobserved={view2}"

    def test_CausalTree_pack_unpack_e2e(self):
        causaltree = classes.CausalTree()
        causaltree.put_first(datawrappers.StrWrapper('first'), 1)
        first = causaltree.read_full()[0]
        causaltree.put_after(datawrappers.BytesWrapper(b'second'), 1, first.uuid)
        second = causaltree.read_full()[1]
        causaltree.put_after(datawrappers.IntWrapper(3), 1, second.uuid)
        causaltree.put_first(datawrappers.DecimalWrapper(Decimal('21.012')), 1)
        packed = causaltree.pack()
        unpacked = classes.CausalTree.unpack(packed, inject=self.inject)

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
        unpacked = classes.CausalTree.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock.uuid == causaltree.clock.uuid
        assert unpacked.read() == causaltree.read()
        assert unpacked.read_full() == causaltree.read_full()

    def test_CausalTree_with_injected_StateUpdateProtocol_class(self):
        causaltree = classes.CausalTree(clock=StrClock())
        update = causaltree.put_first(
            b'first',
            1,
            update_class=CustomStateUpdate,
            inject=self.inject
        )[0]
        assert type(update) is CustomStateUpdate
        assert type(causaltree.history(update_class=CustomStateUpdate)[0] is CustomStateUpdate)
        assert causaltree.read() == (b'first',)

    def test_CausalTree_convergence_from_ts(self):
        causaltree1 = classes.CausalTree()
        causaltree2 = classes.CausalTree()
        causaltree2.clock.uuid = causaltree1.clock.uuid
        update = causaltree1.put_first(datawrappers.StrWrapper('first'), 1)[0]
        causaltree2.update(update)
        parent = update.data[3]
        for i in range(5):
            update = causaltree2.put_after(datawrappers.IntWrapper(i), 1, parent.uuid)
            causaltree1.update(update)
            parent = update.data[3]
        assert causaltree1.checksums() == causaltree2.checksums()

        causaltree1.put_first(datawrappers.IntWrapper(69420), 1)
        causaltree1.put_first(datawrappers.IntWrapper(42069), 1)
        causaltree2.put_first(datawrappers.IntWrapper(23212), 2)

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = causaltree1.clock.read()
        while causaltree1.checksums(from_ts=from_ts, until_ts=until_ts) != \
            causaltree2.checksums(from_ts=from_ts, until_ts=until_ts) \
            and until_ts > 0:
            until_ts -= 1
        from_ts = until_ts
        assert from_ts > 0

        for update in causaltree1.history(from_ts=from_ts):
            causaltree2.update(update)
        for update in causaltree2.history(from_ts=from_ts):
            causaltree1.update(update)

        assert causaltree1.checksums() == causaltree2.checksums()

        # prove it does not converge from bad ts parameters
        causaltree2 = classes.CausalTree()
        causaltree2.clock.uuid = causaltree1.clock.uuid
        for update in causaltree1.history(until_ts=0):
            causaltree2.update(update)
        assert causaltree1.checksums() != causaltree2.checksums()

        causaltree2 = classes.CausalTree()
        causaltree2.clock.uuid = causaltree1.clock.uuid
        for update in causaltree1.history(from_ts=99):
            causaltree2.update(update)
        assert causaltree1.checksums() != causaltree2.checksums()

    def test_CausalTree_edge_case(self):
        # example from documentation
        writer_id = 1
        causaltree = classes.CausalTree()
        first = causaltree.put_first('first', writer_id)[0].data[3]
        causaltree.put_after('second', writer_id, first.uuid)
        second = causaltree.read_full()[1]

        # replicate
        writer_id2 = 2
        ct2 = classes.CausalTree.unpack(causaltree.pack())

        # make concurrent updates
        divergence_ts = causaltree.clock.read()-1
        causaltree.put_after('third', writer_id, second.uuid)
        ct2.put_after('alternate third', writer_id2, second.uuid)

        # synchronize
        history1 = causaltree.history(from_ts=divergence_ts)
        history2 = ct2.history(from_ts=divergence_ts)
        for update in history1:
            ct2.update(update)

        for update in history2:
            causaltree.update(update)

        # prove they have resynchronized and have the same state
        view1, view1f = causaltree.read(), causaltree.read_full()
        view2, view2f = ct2.read(), ct2.read_full()
        assert view1 == view2, f"\n{view1}\n=\n{view2}\n\n{view1f}\n=\n{view2f}"

    def test_CausalTree_merkle_history_e2e(self):
        ct1 = classes.CausalTree()
        ct2 = classes.CausalTree(clock=classes.ScalarClock(0, ct1.clock.uuid))
        for update in ct1.put_first('hello world', 1):
            ct2.update(update)
        ct2.update(ct1.put_after(
            b'hello world',
            1,
            ct1.read_full()[-1].uuid,
        ))
        first = ct1.read_full()[0]
        ct1.delete(first, 1)
        ct1.put_after(
            'not the lipsum',
            1,
            ct1.read_full()[-1].uuid,
        )
        ct2.put_after(
            b'yellow submarine',
            2,
            ct2.read_full()[-1].uuid,
        )

        history1 = ct1.get_merkle_history()
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

        history2 = ct2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = ct1.resolve_merkle_histories(history2)
        diff2 = ct2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 2, [d.hex() for d in diff1]
        assert len(diff2) == 2, [d.hex() for d in diff2]

        # print('')
        # print(ct1.read_full())
        # print(ct2.read_full())
        # print('')

        # synchronize
        for cid in diff1:
            update = classes.StateUpdate.unpack(cidmap2[cid], inject=self.inject)
            # print(update)
            ct1.update(update)
        # print('')
        for cid in diff2:
            update = classes.StateUpdate.unpack(cidmap1[cid], inject=self.inject)
            # print(update)
            ct2.update(update)

        # print('')
        # print(ct1.read_full())
        # print(ct2.read_full())
        chk1 = ct1.checksums()
        chk2 = ct2.checksums()
        chk1 = ct1.checksums()
        chk2 = ct2.checksums()
        assert chk1 == chk2, f"\n{ct1.positions.read()}\n{ct2.positions.read()}"

    def debug_info(self, ct1: classes.CausalTree, ct2: classes.CausalTree, history) -> str:
        result = f'expected {ct1.read()} but encountered {ct2.read()}\n\n'
        for item in ct1.read_full():
            result += f'{item}\n'
            if len(item.children()):
                result += f'children={item.children()}\n'
        result += '\nvs\n\n'
        for item in ct2.read_full():
            result += f'{item}\n'
            if len(item.children()):
                result += f'children={item.children()}\n'
        result += '\nupdates:\n'
        for update in history:
            result += f'{update}\n'
        return result


if __name__ == '__main__':
    unittest.main()
