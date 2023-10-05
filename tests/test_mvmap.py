from __future__ import annotations
from dataclasses import dataclass, field
from itertools import permutations
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestMVMap(unittest.TestCase):
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

    def test_MVMap_implements_CRDTProtocol(self):
        assert isinstance(classes.MVMap(), interfaces.CRDTProtocol)

    def test_MVMap_read_returns_dict(self):
        mvmap = classes.MVMap()
        view = mvmap.read()
        assert isinstance(view, dict)

    def test_MVMap_extend_returns_StateUpdateProtocol(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        update = mvmap.set(name, value)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_MVMap_read_after_extend_is_correct(self):
        mvmap = classes.MVMap()
        view1 = mvmap.read()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        mvmap.set(name, value)
        view2 = mvmap.read()
        assert isinstance(view2, dict)
        assert view1 != view2
        assert name in view2
        assert view2[name] == (value,)

    def test_MVMap_unset_returns_StateUpdateProtocol(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        update = mvmap.unset(name)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_MVMap_read_after_unset_is_correct(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        mvmap.set(name, value)
        view1 = mvmap.read()
        mvmap.unset(name)
        view2 = mvmap.read()
        assert name in view1
        assert name not in view2

    def test_MVMap_history_returns_tuple_of_StateUpdateProtocol(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        mvmap.set(name, value)
        mvmap.set(value, name)
        history = mvmap.history()
        assert type(history) is tuple
        for update in history:
            assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_MVMap_concurrent_writes_preserve_all_values(self):
        mvmap = classes.MVMap()
        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap.clock.uuid
        name = datawrappers.StrWrapper('foo')
        value1 = datawrappers.StrWrapper('bar')
        value2 = datawrappers.StrWrapper('test')
        update1 = mvmap.set(name, value1)
        update2 = mvmap2.set(name, value2)
        mvmap.update(update2)
        mvmap2.update(update1)

        assert mvmap.read()[name] == (value1, value2)
        assert mvmap.checksums() == mvmap2.checksums()

    def test_MVMap_checksums_returns_tuple_of_int(self):
        mvmap = classes.MVMap()
        mvmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        checksums = mvmap.checksums()

        assert type(checksums) is tuple
        for item in checksums:
            assert type(item) is int

    def test_MVMap_checksums_change_after_update(self):
        mvmap = classes.MVMap()
        mvmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        checksums1 = mvmap.checksums()
        mvmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'))
        checksums2 = mvmap.checksums()
        mvmap.set(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'))
        checksums3 = mvmap.checksums()

        assert checksums1 != checksums2
        assert checksums1 != checksums3
        assert checksums2 != checksums3

    def test_MVMap_update_is_idempotent(self):
        mvmap = classes.MVMap()
        update = mvmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        checksums1 = mvmap.checksums()
        view1 = mvmap.read()
        mvmap.update(update)
        checksums2 = mvmap.checksums()
        view2 = mvmap.read()

        assert checksums1 == checksums2
        assert view1 == view2

    def test_MVMap_updates_are_commutative(self):
        mvmap1 = classes.MVMap()
        mvmap2 = classes.MVMap(clock=classes.ScalarClock(uuid=mvmap1.clock.uuid))
        update1 = mvmap1.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        update2 = mvmap1.unset(datawrappers.StrWrapper('foo'))

        mvmap2.update(update2)
        mvmap2.update(update1)

        assert mvmap2.read() == mvmap1.read()

    def test_MVMap_updates_from_history_converge(self):
        mvmap1 = classes.MVMap()
        mvmap2 = classes.MVMap(clock=classes.ScalarClock(0, mvmap1.clock.uuid))
        mvmap1.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        mvmap1.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'))
        mvmap1.set(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'))

        for update in mvmap1.history():
            mvmap2.update(update)

        assert mvmap1.checksums() == mvmap2.checksums()

        histories = permutations(mvmap1.history())
        for history in histories:
            mvmap2 = classes.MVMap(clock=classes.ScalarClock(0, mvmap1.clock.uuid))
            for update in history:
                mvmap2.update(update)
            assert mvmap2.read() == mvmap1.read()

    def test_MVMap_pack_unpack_e2e(self):
        mvmap = classes.MVMap()
        mvmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        mvmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'))
        mvmap.set(datawrappers.StrWrapper('floof'), datawrappers.StrWrapper('bruf'))
        mvmap.unset(datawrappers.StrWrapper('floof'))
        mvmap.set(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'))
        packed = mvmap.pack()
        unpacked = classes.MVMap.unpack(packed, inject=self.inject)

        assert unpacked.checksums() == mvmap.checksums()

    def test_MVMap_pack_unpack_e2e_with_injected_clock(self):
        mvm = classes.MVMap(clock=StrClock())
        mvm.set(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
        )
        mvm.set(
            datawrappers.StrWrapper('second name'),
            datawrappers.StrWrapper('second value'),
        )
        packed = mvm.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.MVMap.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.MVMap.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock == mvm.clock
        assert unpacked.read() == mvm.read()

    def test_MVMap_with_injected_StateUpdateProtocol_class(self):
        mvm = classes.MVMap()
        update = mvm.set(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
            update_class=CustomStateUpdate
        )
        assert type(update) is CustomStateUpdate
        assert type(mvm.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_MVMap_convergence_from_ts(self):
        mvmap1 = classes.MVMap()
        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap1.clock.uuid
        for i in range(10):
            update = mvmap1.set(
                datawrappers.IntWrapper(i),
                datawrappers.IntWrapper(i),
            )
            mvmap2.update(update)
        assert mvmap1.checksums() == mvmap2.checksums()

        mvmap1.set(datawrappers.IntWrapper(69420), datawrappers.IntWrapper(69420))
        mvmap1.set(datawrappers.IntWrapper(42096), datawrappers.IntWrapper(42096))
        mvmap2.set(datawrappers.IntWrapper(23878), datawrappers.IntWrapper(23878))

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = mvmap1.clock.read()
        chksm1 = mvmap1.checksums(from_ts=from_ts, until_ts=until_ts)
        chksm2 = mvmap2.checksums(from_ts=from_ts, until_ts=until_ts)
        while chksm1 != chksm2 and until_ts > 0:
            until_ts -= 1
            chksm1 = mvmap1.checksums(from_ts=from_ts, until_ts=until_ts)
            chksm2 = mvmap2.checksums(from_ts=from_ts, until_ts=until_ts)
        from_ts = until_ts
        assert from_ts > 0

        for update in mvmap1.history(from_ts=from_ts):
            mvmap2.update(update)
        for update in mvmap2.history(from_ts=from_ts):
            mvmap1.update(update)

        assert mvmap1.checksums() == mvmap2.checksums()

        # prove it does not converge from bad ts parameters
        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap1.clock.uuid
        for update in mvmap1.history(until_ts=0):
            mvmap2.update(update)
        assert mvmap1.checksums() != mvmap2.checksums()

        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap1.clock.uuid
        for update in mvmap1.history(from_ts=99):
            mvmap2.update(update)
        assert mvmap1.checksums() != mvmap2.checksums()

    def test_MVMap_merkle_history_e2e(self):
        mvm1 = classes.MVMap()
        mvm2 = classes.MVMap(clock=classes.ScalarClock(0, mvm1.clock.uuid))
        mvm2.update(mvm1.set(
            datawrappers.StrWrapper('hello world'),
            datawrappers.IntWrapper(1),
        ))
        mvm2.update(mvm1.set(
            datawrappers.BytesWrapper(b'hello world'),
            datawrappers.IntWrapper(2),
        ))
        mvm1.unset(datawrappers.StrWrapper('hello world'))
        mvm1.set(
            datawrappers.StrWrapper('not the lipsum'),
            datawrappers.IntWrapper(420),
        )
        mvm2.set(
            datawrappers.StrWrapper('not the lipsum'),
            datawrappers.BytesWrapper(b'yellow submarine'),
        )

        history1 = mvm1.get_merkle_history()
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

        history2 = mvm2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = mvm1.resolve_merkle_histories(history2)
        diff2 = mvm2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 2, [d.hex() for d in diff1]
        assert len(diff2) == 2, [d.hex() for d in diff2]

        # synchronize
        for cid in diff1:
            mvm1.update(classes.StateUpdate.unpack(cidmap2[cid], inject=self.inject))
        for cid in diff2:
            mvm2.update(classes.StateUpdate.unpack(cidmap1[cid], inject=self.inject))

        assert mvm1.checksums() == mvm2.checksums()
        assert mvm1.get_merkle_history() == mvm2.get_merkle_history()


if __name__ == '__main__':
    unittest.main()
