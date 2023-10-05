from __future__ import annotations
from dataclasses import dataclass, field
from itertools import permutations
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestLWWMap(unittest.TestCase):
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

    def test_LWWMap_implements_CRDTProtocol(self):
        assert isinstance(classes.LWWMap(), interfaces.CRDTProtocol)

    def test_LWWMap_read_returns_dict(self):
        lwwmap = classes.LWWMap()
        view = lwwmap.read()
        assert isinstance(view, dict)

    def test_LWWMap_extend_returns_StateUpdateProtocol(self):
        lwwmap = classes.LWWMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        update = lwwmap.set(name, value, 1)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_LWWMap_read_after_extend_is_correct(self):
        lwwmap = classes.LWWMap()
        view1 = lwwmap.read()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        lwwmap.set(name, value, 1)
        view2 = lwwmap.read()
        assert isinstance(view2, dict)
        assert view1 != view2
        assert name in view2
        assert view2[name] == value

    def test_LWWMap_unset_returns_StateUpdateProtocol(self):
        lwwmap = classes.LWWMap()
        name = datawrappers.StrWrapper('foo')
        update = lwwmap.unset(name, 1)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_LWWMap_read_after_unset_is_correct(self):
        lwwmap = classes.LWWMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        lwwmap.set(name, value, 1)
        view1 = lwwmap.read()
        lwwmap.unset(name, 1)
        view2 = lwwmap.read()
        assert name in view1
        assert name not in view2

    def test_LWWMap_history_returns_tuple_of_StateUpdateProtocol(self):
        lwwmap = classes.LWWMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        lwwmap.set(name, value, 1)
        lwwmap.set(value, name, 1)
        history = lwwmap.history()
        assert type(history) is tuple
        for update in history:
            assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_LWWMap_concurrent_writes_bias_to_higher_writer(self):
        lwwmap = classes.LWWMap()
        lwwmap2 = classes.LWWMap()
        lwwmap2.clock.uuid = lwwmap.clock.uuid
        name = datawrappers.StrWrapper('foo')
        value1 = datawrappers.StrWrapper('bar')
        value2 = datawrappers.StrWrapper('test')
        update1 = lwwmap.set(name, value1, 1)
        update2 = lwwmap2.set(name, value2, 3)
        lwwmap.update(update2)
        lwwmap2.update(update1)

        assert lwwmap.checksums() == lwwmap2.checksums()
        assert lwwmap.read()[name] == value2
        assert lwwmap2.read()[name] == value2

    def test_LWWMap_checksums_returns_tuple_of_int(self):
        lwwmap = classes.LWWMap()
        lwwmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        checksums = lwwmap.checksums()

        assert type(checksums) is tuple
        for item in checksums:
            assert type(item) is int

    def test_LWWMap_checksums_change_after_update(self):
        lwwmap = classes.LWWMap()
        lwwmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        checksums1 = lwwmap.checksums()
        lwwmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'), 1)
        checksums2 = lwwmap.checksums()
        lwwmap.set(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'), 1)
        checksums3 = lwwmap.checksums()

        assert checksums1 != checksums2
        assert checksums1 != checksums3
        assert checksums2 != checksums3

    def test_LWWMap_update_is_idempotent(self):
        lwwmap = classes.LWWMap()
        update = lwwmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        checksums1 = lwwmap.checksums()
        view1 = lwwmap.read()
        lwwmap.update(update)
        checksums2 = lwwmap.checksums()
        view2 = lwwmap.read()

        assert checksums1 == checksums2
        assert view1 == view2

    def test_LWWMap_updates_are_commutative(self):
        lwwmap1 = classes.LWWMap()
        lwwmap2 = classes.LWWMap(clock=classes.ScalarClock(uuid=lwwmap1.clock.uuid))
        update1 = lwwmap1.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        update2 = lwwmap1.unset(datawrappers.StrWrapper('foo'), 1)

        lwwmap2.update(update2)
        lwwmap2.update(update1)

        assert lwwmap2.read() == lwwmap1.read()

    def test_LWWMap_updates_from_history_converge(self):
        lwwmap1 = classes.LWWMap()
        lwwmap2 = classes.LWWMap(clock=classes.ScalarClock(0, lwwmap1.clock.uuid))
        lwwmap1.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        lwwmap1.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'), 1)
        lwwmap1.set(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'), 1)

        for update in lwwmap1.history():
            lwwmap2.update(update)

        assert lwwmap1.checksums() == lwwmap2.checksums()

        histories = permutations(lwwmap1.history())
        for history in histories:
            lwwmap2 = classes.LWWMap(clock=classes.ScalarClock(0, lwwmap1.clock.uuid))
            for update in history:
                lwwmap2.update(update)
            assert lwwmap2.read() == lwwmap1.read()

    def test_LWWMap_pack_unpack_e2e(self):
        lwwmap = classes.LWWMap()
        lwwmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        lwwmap.set(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'), 1)
        lwwmap.set(datawrappers.StrWrapper('floof'), datawrappers.StrWrapper('bruf'), 1)
        lwwmap.unset(datawrappers.StrWrapper('floof'), 1)
        lwwmap.set(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'), 1)
        packed = lwwmap.pack()
        unpacked = classes.LWWMap.unpack(packed, inject=self.inject)

        assert unpacked.checksums() == lwwmap.checksums()

    def test_LWWMap_pack_unpack_e2e_with_injected_clock(self):
        lwwm = classes.LWWMap(clock=StrClock())
        lwwm.set(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
            1
        )
        lwwm.set(
            datawrappers.StrWrapper('second name'),
            datawrappers.StrWrapper('second value'),
            1
        )
        packed = lwwm.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.LWWMap.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.LWWMap.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock == lwwm.clock
        assert unpacked.read() == lwwm.read()

    def test_LWWMap_with_injected_StateUpdateProtocol_class(self):
        lwwm = classes.LWWMap()
        update = lwwm.set(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
            1,
            update_class=CustomStateUpdate
        )
        assert type(update) is CustomStateUpdate
        assert type(lwwm.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_LWWMap_convergence_from_ts(self):
        lwwmap1 = classes.LWWMap()
        lwwmap2 = classes.LWWMap()
        lwwmap2.clock.uuid = lwwmap1.clock.uuid
        for i in range(10):
            update = lwwmap1.set(
                datawrappers.IntWrapper(i),
                datawrappers.IntWrapper(i),
                1
            )
            lwwmap2.update(update)
        assert lwwmap1.checksums() == lwwmap2.checksums()

        lwwmap1.set(datawrappers.IntWrapper(69420), datawrappers.IntWrapper(69420), 1)
        lwwmap1.set(datawrappers.IntWrapper(42096), datawrappers.IntWrapper(42096), 1)
        lwwmap2.set(datawrappers.IntWrapper(23878), datawrappers.IntWrapper(23878), 2)

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = lwwmap1.clock.read()
        chksm1 = lwwmap1.checksums(from_ts=from_ts, until_ts=until_ts)
        chksm2 = lwwmap2.checksums(from_ts=from_ts, until_ts=until_ts)
        while chksm1 != chksm2 and until_ts > 0:
            until_ts -= 1
            chksm1 = lwwmap1.checksums(from_ts=from_ts, until_ts=until_ts)
            chksm2 = lwwmap2.checksums(from_ts=from_ts, until_ts=until_ts)
        from_ts = until_ts
        assert from_ts > 0

        for update in lwwmap1.history(from_ts=from_ts):
            lwwmap2.update(update)
        for update in lwwmap2.history(from_ts=from_ts):
            lwwmap1.update(update)

        assert lwwmap1.checksums() == lwwmap2.checksums()

        # prove it does not converge from bad ts parameters
        lwwmap2 = classes.LWWMap()
        lwwmap2.clock.uuid = lwwmap1.clock.uuid
        for update in lwwmap1.history(until_ts=0):
            lwwmap2.update(update)
        assert lwwmap1.checksums() != lwwmap2.checksums()

        lwwmap2 = classes.LWWMap()
        lwwmap2.clock.uuid = lwwmap1.clock.uuid
        for update in lwwmap1.history(from_ts=99):
            lwwmap2.update(update)
        assert lwwmap1.checksums() != lwwmap2.checksums()

    def test_LWWMap_merkle_history_e2e(self):
        lwwm1 = classes.LWWMap()
        lwwm2 = classes.LWWMap(clock=classes.ScalarClock(0, lwwm1.clock.uuid))
        lwwm2.update(lwwm1.set(
            'hello world',
            1,
            1,
        ))
        lwwm2.update(lwwm1.set(
            b'hello world',
            2,
            1,
        ))
        lwwm1.unset('hello world', 1)
        lwwm1.set(
            'not the lipsum',
            420,
            1,
        )
        lwwm2.set(
            'not the lipsum',
            b'yellow submarine',
            2,
        )

        history1 = lwwm1.get_merkle_history()
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

        history2 = lwwm2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = lwwm1.resolve_merkle_histories(history2)
        diff2 = lwwm2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 2, [d.hex() for d in diff1]
        assert len(diff2) == 2, [d.hex() for d in diff2]

        # synchronize
        for cid in diff1:
            update = cidmap2[cid]
            lwwm1.update(classes.StateUpdate.unpack(update, inject=self.inject))
        for cid in diff2:
            update = cidmap1[cid]
            lwwm2.update(classes.StateUpdate.unpack(update, inject=self.inject))

        assert lwwm1.checksums() == lwwm2.checksums()
        assert lwwm1.get_merkle_history() == lwwm2.get_merkle_history()


if __name__ == '__main__':
    unittest.main()
