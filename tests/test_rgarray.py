from __future__ import annotations
from dataclasses import dataclass, field
from itertools import permutations
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestRGArray(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        self.inject = {
            'BytesWrapper': datawrappers.BytesWrapper,
            'StrWrapper': datawrappers.StrWrapper,
            'IntWrapper': datawrappers.IntWrapper,
            'DecimalWrapper': datawrappers.DecimalWrapper,
            'RGAItemWrapper': datawrappers.RGAItemWrapper,
            'NoneWrapper': datawrappers.NoneWrapper,
            'ScalarClock': classes.ScalarClock,
        }
        super().__init__(methodName)

    def test_RGArray_implements_CRDTProtocol(self):
        assert isinstance(classes.RGArray(), interfaces.CRDTProtocol)

    def test_RGArray_implements_ListProtocol(self):
        assert isinstance(classes.RGArray(), interfaces.ListProtocol)

    def test_RGArray_read_returns_tuple(self):
        rga = classes.RGArray()
        assert type(rga.read()) is tuple

    def test_RGArray_append_returns_tuple_StateUpdateProtocol_and_changes_read(self):
        rga = classes.RGArray()
        view1 = rga.read()

        item = datawrappers.BytesWrapper(b'hello')
        state_updates = rga.append(item, 1)
        assert isinstance(state_updates, tuple)
        assert all([isinstance(su, interfaces.StateUpdateProtocol) for su in state_updates])

        view2 = rga.read()
        assert view1 != view2
        assert view2[0] == item

    def test_RGArray_index_returns_int(self):
        rga = classes.RGArray()
        rga.append('item1', 123)
        rga.append('item2', 123)
        assert rga.index('item1') == 0
        assert rga.index('item2') == 1

    def test_RGArray_remove_returns_tuple_StateUpdateProtocol_and_changes_read(self):
        rga = classes.RGArray()
        rga.append('item1', 123)
        rga.append('item2', 123)
        view = rga.read()
        assert 'item1' in view
        index = rga.index('item1')
        updates = rga.remove(index)
        assert isinstance(updates, tuple)
        assert all([isinstance(u, interfaces.StateUpdateProtocol) for u in updates])
        assert rga.read() != view
        assert 'item1' not in rga.read()

    def test_RGArray_delete_returns_StateUpdateProtocol_and_changes_read(self):
        rga = classes.RGArray()
        rga.append(datawrappers.StrWrapper('item'), 1)

        item = rga.read_full()[0]
        assert item.value in rga.read()

        state_update = rga.delete(item)
        assert isinstance(state_update, interfaces.StateUpdateProtocol)

        assert item.value not in rga.read()
        assert item not in rga.read_full()

    def test_RGArray_read_full_returns_tuple_of_RGAItemWrapper(self):
        rga = classes.RGArray()
        rga.append(datawrappers.BytesWrapper(b'hello'), 1)
        view = rga.read_full()

        assert type(view) is tuple
        for item in view:
            assert isinstance(item, datawrappers.RGAItemWrapper)

    def test_RGArray_history_returns_tuple_of_StateUpdateProtocol(self):
        rga = classes.RGArray()
        rga.append(datawrappers.BytesWrapper(b'item'), 1)
        rga.append(datawrappers.StrWrapper('item2'), 1)
        rga.delete(rga.read_full()[0])
        history = rga.history()

        assert type(history) is tuple
        for item in history:
            assert isinstance(item, interfaces.StateUpdateProtocol)

    def test_RGArray_concurrent_appends_order_by_writer_ascending(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(uuid=rga1.clock.uuid))

        update1 = rga1.append(datawrappers.StrWrapper('item1'), 1)[0]
        update2 = rga2.append(datawrappers.DecimalWrapper(Decimal('0.1')), 2)[0]
        rga1.update(update2)
        rga2.update(update1)

        assert rga1.read() == rga2.read()
        assert rga1.read() == (datawrappers.StrWrapper('item1'),
                               datawrappers.DecimalWrapper(Decimal('0.1')))

    def test_RGArray_concurrent_appends_with_same_writer_order_identically(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(uuid=rga1.clock.uuid))

        # order alphabetically by wrapper class name as tie breaker
        update1 = rga1.append(datawrappers.StrWrapper('item1'), 1)[0]
        update2 = rga2.append(datawrappers.DecimalWrapper(Decimal('0.1')), 1)[0]
        rga1.update(update2)
        rga2.update(update1)

        assert rga1.read() == rga2.read()
        assert rga1.read() == (
            datawrappers.StrWrapper('item1'),
            datawrappers.DecimalWrapper(Decimal('0.1')),
        )

        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(uuid=rga1.clock.uuid))

        # order by wrapped value ascending as final tie breaker
        update1 = rga1.append(datawrappers.StrWrapper('item0'), 1)[0]
        update2 = rga2.append(datawrappers.StrWrapper('item1'), 1)[0]
        rga1.update(update2)
        rga2.update(update1)

        assert rga1.read() == rga2.read()
        assert rga1.read() == (datawrappers.StrWrapper('item0'),
                               datawrappers.StrWrapper('item1'))

    def test_RGArray_checksums_returns_tuple_of_int(self):
        rga = classes.RGArray()
        checksums = rga.checksums()

        assert type(checksums) is tuple
        for item in checksums:
            assert type(item) is int

    def test_RGArray_checksums_change_after_update(self):
        rga = classes.RGArray()
        checksums1 = rga.checksums()
        rga.append(datawrappers.BytesWrapper(b'item'), 1)
        checksums2 = rga.checksums()

        assert checksums1 != checksums2

    def test_RGArray_update_is_idempotent(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(0, rga1.clock.uuid))

        update = rga1.append(datawrappers.StrWrapper('item'), 1)[0]
        view = rga1.read_full()
        rga2.update(update)

        assert rga1.read_full() == view
        assert rga2.read_full() == view

        rga2.update(update)
        rga1.update(update)
        assert rga1.read_full() == rga2.read_full() == view

        update = rga2.delete(rga2.read_full()[0])
        rga1.update(update)
        view = rga1.read_full()

        assert rga2.read_full() == view

        rga1.update(update)
        rga2.update(update)
        assert rga1.read_full() == rga2.read_full() == view

    def test_RGArray_updates_are_commutative(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(0, rga1.clock.uuid))

        update1 = rga1.append(datawrappers.BytesWrapper(b'item1'), 1)[0]
        update2 = rga1.append(datawrappers.IntWrapper(321), 1)[0]
        rga2.update(update2)
        rga2.update(update1)

        assert rga1.read() == rga2.read()

    def test_RGArray_update_from_history_converges(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(0, rga1.clock.uuid))

        rga1.append(datawrappers.BytesWrapper(b'item1'), 1)
        rga1.append(datawrappers.StrWrapper('item2'), 1)
        rga1.delete(rga1.read_full()[0])
        rga1.append(datawrappers.IntWrapper(3), 1)

        for update in rga1.history():
            rga2.update(update)

        assert rga1.read() == rga2.read()

        histories = permutations(rga1.history())
        for history in histories:
            rga2 = classes.RGArray(clock=classes.ScalarClock(0, rga1.clock.uuid))
            for update in history:
                rga2.update(update)
            assert rga2.read() == rga1.read()
            assert rga2.checksums() == rga1.checksums()

    def test_RGArray_pack_unpack_e2e(self):
        rga = classes.RGArray()
        rga.append(datawrappers.BytesWrapper(b'item1'), 1)
        rga.append(datawrappers.StrWrapper('item2'), 1)
        rga.append(datawrappers.IntWrapper(3), 1)
        rga.append(datawrappers.DecimalWrapper(Decimal('4.44')), 1)
        rga.delete(rga.read_full()[0])
        rga.append(datawrappers.BytesWrapper(b'item3'), 1)

        packed = rga.pack()
        assert type(packed) is bytes
        unpacked = classes.RGArray.unpack(packed, inject=self.inject)
        assert isinstance(unpacked, classes.RGArray)

        assert unpacked.clock == rga.clock
        assert unpacked.read_full() == rga.read_full()
        assert unpacked.checksums() == rga.checksums()

    def test_RGArray_pack_unpack_e2e_with_injected_clock(self):
        rga = classes.RGArray(clock=StrClock())
        rga.append(datawrappers.StrWrapper('first'), 1)
        rga.append(datawrappers.StrWrapper('second'), 1)
        packed = rga.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.RGArray.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.RGArray.unpack(packed, inject={**self.inject, 'StrClock': StrClock})

        assert unpacked.clock == rga.clock
        assert unpacked.read() == rga.read()

    def test_RGArray_with_injected_StateUpdateProtocol_class(self):
        rga = classes.RGArray()
        update = rga.append(datawrappers.StrWrapper('first'), 1, update_class=CustomStateUpdate)[0]
        assert type(update) is CustomStateUpdate
        assert type(rga.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_RGArray_convergence_from_ts(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray()
        rga2.clock.uuid = rga1.clock.uuid
        for i in range(10):
            update = rga1.append(datawrappers.IntWrapper(i), i)[0]
            rga2.update(update)
        assert rga1.checksums() == rga2.checksums()

        rga1.append(datawrappers.IntWrapper(69420), 1)
        rga1.append(datawrappers.IntWrapper(42096), 1)
        rga2.append(datawrappers.IntWrapper(23878), 2)

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = rga1.clock.read()
        while rga1.checksums(from_ts=from_ts, until_ts=until_ts) != \
            rga2.checksums(from_ts=from_ts, until_ts=until_ts) \
            and until_ts > 0:
            until_ts -= 1
        from_ts = until_ts
        assert from_ts > 0

        for update in rga1.history(from_ts=from_ts):
            rga2.update(update)
        for update in rga2.history(from_ts=from_ts):
            rga1.update(update)

        assert rga1.checksums() == rga2.checksums()

        # prove it does not converge from bad ts parameters
        rga2 = classes.RGArray()
        rga2.clock.uuid = rga1.clock.uuid
        for update in rga1.history(until_ts=0):
            rga2.update(update)
        assert rga1.checksums() != rga2.checksums()

        rga2 = classes.RGArray()
        rga2.clock.uuid = rga1.clock.uuid
        for update in rga1.history(from_ts=99):
            rga2.update(update)
        assert rga1.checksums() != rga2.checksums()

    def test_RGArray_merkle_history_e2e(self):
        rga1 = classes.RGArray()
        rga2 = classes.RGArray(clock=classes.ScalarClock(0, rga1.clock.uuid))
        rga2.update(rga1.append('hello world', 1)[0])
        rga2.update(rga1.append(b'hello world', 1)[0])
        rga1.delete(rga1.read_full()[0])
        rga1.append('not the lipsum', 1)
        rga2.append(b'yellow submarine', 2)

        history1 = rga1.get_merkle_history()
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

        history2 = rga2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = rga1.resolve_merkle_histories(history2)
        diff2 = rga2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 2, [d.hex() for d in diff1]
        assert len(diff2) == 2, [d.hex() for d in diff2]

        # print('')
        # print(rga1.read_full())
        # print(rga2.read_full())
        # print('')

        # synchronize
        for cid in diff1:
            update = classes.StateUpdate.unpack(cidmap2[cid], inject=self.inject)
            # print(update)
            rga1.update(update)
        # print('')
        for cid in diff2:
            update = classes.StateUpdate.unpack(cidmap1[cid], inject=self.inject)
            # print(update)
            rga2.update(update)

        # print('')
        # print(rga1.read_full())
        # print(rga2.read_full())
        assert rga1.checksums() == rga2.checksums(), f"\n{rga1.read_full()}\n{rga2.read_full()}"


if __name__ == '__main__':
    unittest.main()
