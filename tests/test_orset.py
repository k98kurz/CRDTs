from __future__ import annotations
from itertools import permutations
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestORSet(unittest.TestCase):
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

    def test_ORSet_implements_CRDTProtocol(self):
        assert isinstance(classes.ORSet(), interfaces.CRDTProtocol)

    def test_ORSet_read_returns_add_biased_set_difference(self):
        orset = classes.ORSet()
        assert orset.read() == set()
        orset.observe(1)
        orset.observe(2)
        assert orset.read() == set([1, 2])
        orset.remove(1)
        assert orset.read() == set([2])

    def test_ORSet_observe_and_remove_return_state_update(self):
        orset = classes.ORSet()
        update = orset.observe(1)
        assert isinstance(update, classes.StateUpdate)
        update = orset.remove(1)
        assert isinstance(update, classes.StateUpdate)

    def test_ORSet_history_returns_tuple_of_StateUpdate(self):
        orset = classes.ORSet()
        orset.observe(1)
        orset.observe(2)
        history = orset.history()
        assert type(history) is tuple
        for update in history:
            assert type(update) is classes.StateUpdate

    def test_ORSet_read_returns_set_with_correct_values(self):
        orset = classes.ORSet()
        view1 = orset.read()
        assert type(view1) is set
        assert len(view1) == 0
        orset.observe(1)
        view2 = orset.read()
        assert len(view2) == 1
        assert [*view2][0] == 1
        orset.observe(2)
        view3 = orset.read()
        assert len(view3) == 2
        assert 1 in view3
        assert 2 in view3
        orset.remove(1)
        view4 = orset.read()
        assert len(view4) == 1
        assert 2 in view4

    def test_ORSet_observe_and_remove_change_view(self):
        orset = classes.ORSet()
        view1 = orset.read()
        orset.observe(1)
        view2 = orset.read()
        orset.observe(2)
        view3 = orset.read()
        orset.remove(1)
        view4 = orset.read()
        orset.remove(5)
        view5 = orset.read()
        assert view1 not in (view2, view3, view4, view5)
        assert view2 not in (view1, view3, view4, view5)
        assert view3 not in (view1, view2, view4, view5)
        assert view4 not in (view1, view2, view3)
        assert view4 == view5

    def test_ORSet_observe_and_remove_same_member_does_not_change_view(self):
        orset = classes.ORSet()
        orset.observe(1)
        view1 = orset.read()
        orset.observe(1)
        view2 = orset.read()
        assert view1 == view2
        orset.observe(2)
        orset.remove(1)
        view3 = orset.read()
        orset.remove(1)
        view4 = orset.read()
        assert view3 == view4

    def test_ORSet_checksums_returns_tuple_of_int(self):
        orset = classes.ORSet()
        checksum = orset.checksums()
        assert type(checksum) is tuple
        for item in checksum:
            assert type(item) is int

    def test_ORSet_checksums_change_after_update(self):
        orset = classes.ORSet()
        checksums1 = orset.checksums()
        orset.observe(1)
        checksums2 = orset.checksums()
        orset.remove(1)
        checksums3 = orset.checksums()
        assert checksums1 != checksums2
        assert checksums2 != checksums3
        assert checksums3 != checksums1

    def test_ORSet_update_is_idempotent(self):
        orset1 = classes.ORSet()
        orset2 = classes.ORSet(clock=classes.ScalarClock(0, orset1.clock.uuid))
        update = orset1.observe(2)
        view1 = orset1.read()
        orset1.update(update)
        assert orset1.read() == view1
        orset2.update(update)
        view2 = orset2.read()
        orset2.update(update)
        assert orset2.read() == view2 == view1

        update = orset1.remove(2)
        view1 = orset1.read()
        orset1.update(update)
        assert orset1.read() == view1
        orset2.update(update)
        view2 = orset2.read()
        orset2.update(update)
        assert orset2.read() == view2 == view1

    def test_ORSet_updates_from_history_converge(self):
        orset1 = classes.ORSet()
        orset2 = classes.ORSet(clock=classes.ScalarClock(0, orset1.clock.uuid))
        orset1.observe(1)
        orset1.remove(2)
        orset1.observe(3)

        for update in orset1.history():
            orset2.update(update)

        assert orset1.read() == orset2.read()
        assert orset1.checksums() == orset2.checksums()

        histories = permutations(orset1.history())
        for history in histories:
            orset2 = classes.ORSet(clock=classes.ScalarClock(0, orset1.clock.uuid))
            for update in history:
                orset2.update(update)
            assert orset2.read() == orset1.read()
            assert orset2.checksums() == orset1.checksums()

    def test_ORSet_pack_unpack_e2e(self):
        orset1 = classes.ORSet()
        orset1.observe(1)
        orset1.observe(datawrappers.StrWrapper('hello'))
        orset1.remove(2)
        orset1.remove(datawrappers.BytesWrapper(b'hello'))
        packed = orset1.pack()
        orset2 = classes.ORSet.unpack(packed, inject=self.inject)

        assert orset1.clock.uuid == orset2.clock.uuid
        assert orset1.read() == orset2.read()
        assert orset1.checksums() == orset2.checksums()
        assert orset1.history() in permutations(orset2.history())

    def test_ORSet_cache_is_set_upon_first_read(self):
        orset = classes.ORSet()
        orset.observe(1)
        assert orset.cache is None
        orset.read()
        assert orset.cache is not None

    def test_ORSet_pack_unpack_e2e_with_injected_clock(self):
        ors = classes.ORSet(clock=StrClock())
        ors.observe('test')
        packed = ors.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.ORSet.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.ORSet.unpack(packed, inject={**self.inject, 'StrClock': StrClock})

        assert unpacked.clock == ors.clock
        assert unpacked.read() == ors.read()

    def test_ORSet_pack_unpack_e2e_with_injected_StateUpdateProtocol_class(self):
        ors = classes.ORSet()
        update = ors.observe('test', update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(ors.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_ORSet_convergence_from_ts(self):
        orset1 = classes.ORSet()
        orset2 = classes.ORSet()
        orset2.clock.uuid = orset1.clock.uuid
        for i in range(10):
            update = orset1.observe(datawrappers.IntWrapper(i))
            orset2.update(update)
        assert orset1.checksums() == orset2.checksums()
        for i in range(5):
            update = orset2.remove(datawrappers.IntWrapper(i))
            orset1.update(update)
        assert orset1.checksums() == orset2.checksums()

        orset1.observe(datawrappers.IntWrapper(69420))
        orset1.observe(datawrappers.IntWrapper(42096))
        orset2.observe(datawrappers.IntWrapper(23878))

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = orset1.clock.read()
        while orset1.checksums(from_ts=from_ts, until_ts=until_ts) != \
            orset2.checksums(from_ts=from_ts, until_ts=until_ts) \
            and until_ts > 0:
            until_ts -= 1
        from_ts = until_ts
        assert from_ts > 0

        for update in orset1.history(from_ts=from_ts):
            orset2.update(update)
        for update in orset2.history(from_ts=from_ts):
            orset1.update(update)

        assert orset1.checksums() == orset2.checksums()

        # prove it does not converge from bad ts parameters
        orset2 = classes.ORSet()
        orset2.clock.uuid = orset1.clock.uuid
        for update in orset1.history(until_ts=0):
            orset2.update(update)
        assert orset1.checksums() != orset2.checksums()

        orset2 = classes.ORSet()
        orset2.clock.uuid = orset1.clock.uuid
        for update in orset1.history(from_ts=99):
            orset2.update(update)
        assert orset1.checksums() != orset2.checksums()

    def test_ORSet_merkle_history_e2e(self):
        ors1 = classes.ORSet()
        ors2 = classes.ORSet(clock=classes.ScalarClock(0, ors1.clock.uuid))
        ors2.update(ors1.observe('hello world'))
        ors2.update(ors1.observe(b'hello world'))
        ors1.remove('hello world')
        ors1.observe('not the lipsum')
        ors2.observe(b'yellow submarine')

        history1 = ors1.get_merkle_history()
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

        history2 = ors2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = ors1.resolve_merkle_histories(history2)
        diff2 = ors2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 2, [d.hex() for d in diff1]
        assert len(diff2) == 2, [d.hex() for d in diff2]

        # synchronize
        for cid in diff1:
            update = classes.StateUpdate.unpack(cidmap2[cid])
            ors1.update(update)
        for cid in diff2:
            update = classes.StateUpdate.unpack(cidmap1[cid])
            ors2.update(update)

        assert ors1.get_merkle_history() == ors2.get_merkle_history()
        assert ors1.checksums() == ors2.checksums()

    def test_ORSet_event_listeners_e2e(self):
        orset = classes.ORSet()
        logs = []
        def add_log(update: interfaces.StateUpdateProtocol):
            logs.append(update)

        assert len(logs) == 0
        orset.observe('item')
        assert len(logs) == 0
        orset.remove('item')
        assert len(logs) == 0
        orset.add_listener(add_log)
        orset.observe('item')
        assert len(logs) == 1
        orset.remove('item')
        assert len(logs) == 2
        orset.remove_listener(add_log)
        orset.observe('item')
        assert len(logs) == 2
        orset.remove('item')
        assert len(logs) == 2


if __name__ == '__main__':
    unittest.main()
