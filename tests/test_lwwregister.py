from __future__ import annotations
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestLWWRegister(unittest.TestCase):
    def test_LWWRegister_implements_CRDTProtocol(self):
        assert isinstance(classes.LWWRegister(datawrappers.StrWrapper('test')), interfaces.CRDTProtocol)

    def test_LWWRegister_read_returns_value(self):
        lwwregister = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper('foobar'))
        assert isinstance(lwwregister.read(), datawrappers.StrWrapper)
        assert lwwregister.read().value == 'foobar'
        lwwregister = classes.LWWRegister('test', 'foobar')
        assert type(lwwregister.read()) is str
        assert lwwregister.read() == 'foobar'

    def test_LWWRegister_write_returns_StateUpdate_and_sets_value(self):
        lwwregister = classes.LWWRegister(datawrappers.BytesWrapper(b'test'), datawrappers.BytesWrapper(b'foobar'))
        update = lwwregister.write(datawrappers.BytesWrapper(b'barfoo'), 1)
        assert isinstance(update, classes.StateUpdate)
        assert lwwregister.read().value == b'barfoo'

    def test_LWWRegister_history_returns_tuple_of_StateUpdate(self):
        lwwregister = classes.LWWRegister(datawrappers.StrWrapper('test'), datawrappers.StrWrapper('foobar'))
        lwwregister.write(datawrappers.StrWrapper('sdsd'), b'2')
        lwwregister.write(datawrappers.StrWrapper('barfoo'), b'1')
        history = lwwregister.history()

        assert type(history) is tuple
        for item in history:
            assert isinstance(item, classes.StateUpdate)

    def test_LWWRegister_concurrent_writes_bias_to_higher_writer(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock)

        update1 = lwwregister1.write(datawrappers.StrWrapper('foobar'), b'1')
        update2 = lwwregister2.write(datawrappers.StrWrapper('barfoo'), b'2')
        lwwregister1.update(update2)
        lwwregister2.update(update1)

        assert lwwregister1.read() == lwwregister2.read()
        assert lwwregister1.read().value == 'barfoo'

    def test_LWWRegister_concurrent_writes_bias_to_one_value(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock)

        update1 = lwwregister1.write(datawrappers.StrWrapper('foobar'), [b'1', 2, '3'])
        update2 = lwwregister2.write(datawrappers.StrWrapper('barfoo'), [b'1', 2, '2'])
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

        lwwregister1.write(datawrappers.StrWrapper('thing'), b'1')
        lwwregister2.write(datawrappers.StrWrapper('stuff'), b'2')

        assert lwwregister1.checksums() != checksums1
        assert lwwregister2.checksums() != checksums1
        assert lwwregister1.checksums() != lwwregister2.checksums()

    def test_LWWRegister_update_is_idempotent(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock1 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock1)

        update = lwwregister1.write(datawrappers.StrWrapper('foo1'), b'1')
        view1 = lwwregister1.read()
        lwwregister1.update(update)
        assert lwwregister1.read() == view1
        lwwregister2.update(update)
        view2 = lwwregister2.read()
        lwwregister2.update(update)
        assert lwwregister2.read() == view2

        update = lwwregister2.write(datawrappers.StrWrapper('bar'), b'2')
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

        update1 = lwwregister1.write(datawrappers.StrWrapper('foo1'), b'1')
        update2 = lwwregister1.write(datawrappers.StrWrapper('foo2'), b'1')
        lwwregister2.update(update2)
        lwwregister2.update(update1)

        assert lwwregister1.read() == lwwregister2.read()

    def test_LWWRegister_update_from_history_converges(self):
        lwwregister1 = classes.LWWRegister(datawrappers.StrWrapper('test'))
        clock1 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        clock2 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock1)
        lwwregister3 = classes.LWWRegister(datawrappers.StrWrapper('test'), clock=clock2)

        update = lwwregister1.write(datawrappers.StrWrapper('foo1'), b'1')
        lwwregister2.update(update)
        lwwregister2.write(datawrappers.StrWrapper('bar'), b'2')

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
        lwwr.write(datawrappers.StrWrapper('first'), b'1')
        lwwr.write(datawrappers.StrWrapper('second'), b'1')
        packed = lwwr.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.LWWRegister.unpack(packed)
        assert 'StrClock' in str(e.exception)

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

    def test_LWWRegister_merkle_history_e2e(self):
        lwwr1 = classes.LWWRegister('test')
        lwwr2 = classes.LWWRegister('test', clock=classes.ScalarClock(0, lwwr1.clock.uuid))
        lwwr2.update(lwwr1.write('hello world', 1))
        lwwr2.update(lwwr1.write(b'hello world', 1))
        lwwr1.write('hello world', 1)
        lwwr1.write('not the lipsum', 1)
        lwwr2.write(b'yellow submarine', 2)

        history1 = lwwr1.get_merkle_history()
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

        history2 = lwwr2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = lwwr1.resolve_merkle_histories(history2)
        diff2 = lwwr2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 1, [d.hex() for d in diff1]
        assert len(diff2) == 1, [d.hex() for d in diff2]

        # synchronize
        for cid in diff1:
            lwwr1.update(classes.StateUpdate.unpack(cidmap2[cid]))
        for cid in diff2:
            lwwr2.update(classes.StateUpdate.unpack(cidmap1[cid]))

        assert lwwr1.checksums() == lwwr2.checksums()


if __name__ == '__main__':
    unittest.main()
