from __future__ import annotations
from dataclasses import dataclass, field, is_dataclass
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestCounterSet(unittest.TestCase):
    def test_CounterSet_implements_CRDTProtocol(self):
        assert isinstance(classes.CounterSet(), interfaces.CRDTProtocol)

    def test_CounterSet_read_returns_int_positve_minus_negative(self):
        counterset = classes.CounterSet()
        assert type(counterset.read()) is int
        assert counterset.read() == 0
        counterset.counters[b''] = classes.PNCounter()
        counterset.counters[b''].positive = 3
        counterset.counters[b''].negative = 1
        assert counterset.read() == 2

    def test_CounterSet_increase_and_decrease_return_state_update(self):
        counterset = classes.CounterSet()
        update = counterset.increase(b'hello world')
        assert isinstance(update, classes.StateUpdate)
        update = counterset.decrease(b'foobar')
        assert isinstance(update, classes.StateUpdate)

    def test_CounterSet_history_returns_tuple_of_StateUpdate(self):
        counterset = classes.CounterSet()
        counterset.increase(b'123')
        counterset.increase(b'123')
        counterset.decrease(b'abc')
        history = counterset.history()
        assert type(history) is tuple
        for update in history:
            assert type(update) is classes.StateUpdate

    def test_CounterSet_read_returns_int_with_correct_value(self):
        counterset = classes.CounterSet()
        view1 = counterset.read()
        assert type(view1) is int
        assert view1 == 0
        counterset.increase(b'123')
        assert counterset.read() == 1
        counterset.increase(b'321')
        assert counterset.read() == 2
        counterset.decrease(b'321')
        assert counterset.read() == 1

    def test_CounterSet_checksums_returns_tuple_of_int(self):
        counterset = classes.CounterSet()
        counterset.increase(b'123')
        checksum = counterset.checksums()
        assert type(checksum) is tuple
        for item in checksum:
            assert type(item) is int

    def test_CounterSet_checksums_change_after_update(self):
        counterset = classes.CounterSet()
        checksums1 = counterset.checksums()
        counterset.increase(b'123')
        checksums2 = counterset.checksums()
        assert checksums1 != checksums2
        counterset.decrease(b'321')
        checksums3 = counterset.checksums()
        assert checksums3 not in (checksums1, checksums2)

    def test_CounterSet_update_is_idempotent(self):
        counterset1 = classes.CounterSet()
        counterset2 = classes.CounterSet(clock=classes.ScalarClock(0, counterset1.clock.uuid))
        update = counterset1.increase('abc')
        view1 = counterset1.read()
        counterset1.update(update)
        assert counterset1.read() == view1
        counterset2.update(update)
        view2 = counterset2.read()
        counterset2.update(update)
        assert counterset2.read() == view2 == view1

        update = counterset1.decrease('abc', 2)
        view1 = counterset1.read()
        counterset1.update(update)
        assert counterset1.read() == view1
        counterset2.update(update)
        view2 = counterset2.read()
        counterset2.update(update)
        assert counterset2.read() == view2 == view1

    def test_CounterSet_update_from_history_converges(self):
        counterset1 = classes.CounterSet()
        counterset2 = classes.CounterSet(clock=classes.ScalarClock(0, counterset1.clock.uuid))
        counterset1.increase()
        counterset1.increase()

        for update in counterset1.history():
            counterset2.update(update)

        assert counterset1.read() == counterset2.read()
        assert counterset1.checksums() == counterset2.checksums()

    def test_CounterSet_pack_unpack_e2e(self):
        counterset1 = classes.CounterSet()
        counterset1.increase('abc')
        counterset1.increase('cba')
        packed = counterset1.pack()
        counterset2 = classes.CounterSet.unpack(packed)

        assert counterset1.clock.uuid == counterset2.clock.uuid
        assert counterset1.read() == counterset2.read()
        assert counterset1.checksums() == counterset2.checksums()
        h1 = set([u.pack() for u in counterset1.history()])
        h2 = set([u.pack() for u in counterset2.history()])
        assert h1 == h2

    def test_CounterSet_pack_unpack_e2e_with_injected_clock(self):
        counterset = classes.CounterSet(clock=StrClock())
        counterset.increase()
        packed = counterset.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.CounterSet.unpack(packed)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.CounterSet.unpack(packed, inject={'StrClock': StrClock})

        assert unpacked.clock == counterset.clock
        assert unpacked.read() == counterset.read()

    def test_CounterSet_e2e_with_injected_StateUpdateProtocol_class(self):
        counterset = classes.CounterSet()
        update = counterset.increase(update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(counterset.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_CounterSet_history_return_value_determined_by_from_ts_and_until_ts(self):
        counterset = classes.CounterSet()
        counterset.increase()
        counterset.increase()
        counterset.decrease()

        # from_ts in future of last update, history should return nothing
        assert len(counterset.history(from_ts=99)) == 0

        # until_ts in past of last update, history should return nothing
        assert len(counterset.history(until_ts=0)) == 0

        # from_ts in past, until_ts in future: history should return update
        assert len(counterset.history(from_ts=0, until_ts=99)) > 0

    def test_CounterSet_merkle_history_e2e(self):
        pnc1 = classes.CounterSet()
        pnc2 = classes.CounterSet(clock=classes.ScalarClock(0, pnc1.clock.uuid))
        pnc1.increase('123')
        pnc1.increase('123')
        pnc2.decrease('321')

        history1 = pnc1.get_merkle_history()
        assert type(history1) in (list, tuple), \
            'history must be [[bytes, ], bytes, dict[bytes, bytes]]'
        assert len(history1) == 3, \
            'history must be [[bytes, ], bytes, dict[bytes, bytes]]'
        assert all([type(leaf) is bytes for leaf in history1[1]]), \
            'history must be [[bytes, ], bytes, dict[bytes, bytes]]'
        assert all([
            type(leaf_id) is type(leaf) is bytes
            for leaf_id, leaf in history1[2].items()
        ]), 'history must be [[bytes, ], bytes, dict[bytes, bytes]]'
        assert all([leaf_id in history1[2] for leaf_id in history1[1]]), \
            'history[2] dict must have all keys in history[1] list'

        history2 = pnc2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        diff1 = pnc1.resolve_merkle_histories(history2)
        diff2 = pnc2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 1
        assert len(diff2) == 1
        assert diff1[0] == history2[1][0]
        assert diff2[0] == history1[1][0]


if __name__ == '__main__':
    unittest.main()
