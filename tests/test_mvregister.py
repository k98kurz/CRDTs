from __future__ import annotations
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestMVRegister(unittest.TestCase):
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

    def test_MVRegister_implements_CRDTProtocol(self):
        assert isinstance(
            classes.MVRegister(datawrappers.StrWrapper('test')),
            interfaces.CRDTProtocol
        )

    def test_MVRegister_read_returns_set_of_values(self):
        mvregister = classes.MVRegister(
            datawrappers.StrWrapper('test'),
            [datawrappers.StrWrapper('foobar')]
        )
        assert type(mvregister.read()) is tuple
        assert len(mvregister.read()) == 1
        assert isinstance(mvregister.read()[0], datawrappers.StrWrapper)
        assert mvregister.read()[0].value == 'foobar'

        mvregister = classes.MVRegister('test', ['foobar'])
        assert type(mvregister.read()) is tuple
        assert len(mvregister.read()) == 1
        assert type(mvregister.read()[0]) is str
        assert mvregister.read()[0] == 'foobar'

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
        unpacked = classes.MVRegister.unpack(packed, inject=self.inject)

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

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.MVRegister.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.MVRegister.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock == mvregister.clock
        assert unpacked.read() == mvregister.read()

    def test_MVRegister_with_injected_StateUpdateProtocol_class(self):
        mvregister = classes.MVRegister(
            name=datawrappers.StrWrapper('test register')
        )
        update = mvregister.write(datawrappers.StrWrapper('first'), update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(mvregister.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_MVRegister_history_return_value_determined_by_from_ts_and_until_ts(self):
        mvregister = classes.MVRegister(
            name=datawrappers.StrWrapper('test register')
        )
        mvregister.write(datawrappers.StrWrapper('first'))
        mvregister.write(datawrappers.StrWrapper('second'))

        # from_ts in future of last update, history should return nothing
        assert len(mvregister.history(from_ts=99)) == 0

        # until_ts in past of last update, history should return nothing
        assert len(mvregister.history(until_ts=0)) == 0

        # from_ts in past, until_ts in future: history should return update
        assert len(mvregister.history(from_ts=0, until_ts=99)) == 1

    def test_MVRegister_merkle_history_e2e(self):
        mvr1 = classes.MVRegister('test')
        mvr2 = classes.MVRegister('test', clock=classes.ScalarClock(0, mvr1.clock.uuid))
        mvr2.update(mvr1.write('hello world'))
        mvr2.update(mvr1.write(b'hello world'))
        mvr1.write('hello world')
        mvr2.write(b'yellow submarine')

        history1 = mvr1.get_merkle_history()
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

        history2 = mvr2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = mvr1.resolve_merkle_histories(history2)
        diff2 = mvr2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 1, [d.hex() for d in diff1]
        assert len(diff2) == 1, [d.hex() for d in diff2]

        # synchronize
        for cid in diff1:
            mvr1.update(classes.StateUpdate.unpack(cidmap2[cid]))
        for cid in diff2:
            mvr2.update(classes.StateUpdate.unpack(cidmap1[cid]))

        assert mvr1.checksums() == mvr2.checksums()

    def test_MVRegister_event_listeners_e2e(self):
        mvr = classes.MVRegister('test')
        logs = []
        def add_log(update: interfaces.StateUpdateProtocol):
            logs.append(update)

        assert len(logs) == 0
        mvr.write('value')
        assert len(logs) == 0
        mvr.add_listener(add_log)
        mvr.write('value')
        assert len(logs) == 1
        mvr.remove_listener(add_log)
        mvr.write('value')
        assert len(logs) == 1


if __name__ == '__main__':
    unittest.main()
