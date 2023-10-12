from __future__ import annotations
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestPNCounter(unittest.TestCase):
    def test_PNCounter_implements_CRDTProtocol(self):
        assert isinstance(classes.PNCounter(), interfaces.CRDTProtocol)

    def test_PNCounter_read_returns_int_positve_minus_negative(self):
        pncounter = classes.PNCounter()
        assert type(pncounter.read()) is int
        assert pncounter.read() == 0
        pncounter.positive = 3
        pncounter.negative = 1
        assert pncounter.read() == 2

    def test_PNCounter_increase_and_decrease_return_state_update(self):
        pncounter = classes.PNCounter()
        update = pncounter.increase()
        assert isinstance(update, classes.StateUpdate)
        update = pncounter.decrease()
        assert isinstance(update, classes.StateUpdate)

    def test_PNCounter_history_returns_tuple_of_StateUpdate(self):
        pncounter = classes.PNCounter()
        pncounter.increase()
        pncounter.increase()
        pncounter.decrease()
        history = pncounter.history()
        assert type(history) is tuple
        for update in history:
            assert type(update) is classes.StateUpdate

    def test_PNCounter_read_returns_int_with_correct_value(self):
        pncounter = classes.PNCounter()
        view1 = pncounter.read()
        assert type(view1) is int
        assert view1 == 0
        pncounter.increase()
        assert pncounter.read() == 1
        pncounter.increase()
        assert pncounter.read() == 2
        pncounter.decrease()
        assert pncounter.read() == 1

    def test_PNCounter_checksums_returns_tuple_of_int(self):
        pncounter = classes.PNCounter()
        checksum = pncounter.checksums()
        assert type(checksum) is tuple
        for item in checksum:
            assert type(item) is int

    def test_PNCounter_checksums_change_after_update(self):
        pncounter = classes.PNCounter()
        checksums1 = pncounter.checksums()
        pncounter.increase()
        checksums2 = pncounter.checksums()
        assert checksums1 != checksums2
        pncounter.decrease()
        checksums3 = pncounter.checksums()
        assert checksums3 not in (checksums1, checksums2)

    def test_PNCounter_update_is_idempotent(self):
        pncounter1 = classes.PNCounter()
        pncounter2 = classes.PNCounter(clock=classes.ScalarClock(0, pncounter1.clock.uuid))
        update = pncounter1.increase()
        view1 = pncounter1.read()
        pncounter1.update(update)
        assert pncounter1.read() == view1
        pncounter2.update(update)
        view2 = pncounter2.read()
        pncounter2.update(update)
        assert pncounter2.read() == view2 == view1

        update = pncounter1.decrease(2)
        view1 = pncounter1.read()
        pncounter1.update(update)
        assert pncounter1.read() == view1
        pncounter2.update(update)
        view2 = pncounter2.read()
        pncounter2.update(update)
        assert pncounter2.read() == view2 == view1

    def test_PNCounter_update_from_history_converges(self):
        pncounter1 = classes.PNCounter()
        pncounter2 = classes.PNCounter(clock=classes.ScalarClock(0, pncounter1.clock.uuid))
        pncounter1.increase()
        pncounter1.increase()

        for update in pncounter1.history():
            pncounter2.update(update)

        assert pncounter1.read() == pncounter2.read()
        assert pncounter1.checksums() == pncounter2.checksums()

    def test_PNCounter_pack_unpack_e2e(self):
        pncounter1 = classes.PNCounter()
        pncounter1.increase()
        pncounter1.increase()
        packed = pncounter1.pack()
        pncounter2 = classes.PNCounter.unpack(packed)

        assert pncounter1.clock.uuid == pncounter2.clock.uuid
        assert pncounter1.read() == pncounter2.read()
        assert pncounter1.checksums() == pncounter2.checksums()
        assert pncounter1.history() == pncounter2.history()

    def test_PNCounter_pack_unpack_e2e_with_injected_clock(self):
        pnc = classes.PNCounter(clock=StrClock())
        pnc.increase()
        packed = pnc.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.PNCounter.unpack(packed)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.PNCounter.unpack(packed, inject={'StrClock': StrClock})

        assert unpacked.clock == pnc.clock
        assert unpacked.read() == pnc.read()

    def test_PNCounter_e2e_with_injected_StateUpdateProtocol_class(self):
        pnc = classes.PNCounter()
        update = pnc.increase(update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(pnc.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_PNCounter_history_return_value_determined_by_from_ts_and_until_ts(self):
        pnc = classes.PNCounter()
        pnc.increase()
        pnc.increase()
        pnc.decrease()

        # from_ts in future of last update, history should return nothing
        assert len(pnc.history(from_ts=99)) == 0

        # until_ts in past of last update, history should return nothing
        assert len(pnc.history(until_ts=0)) == 0

        # from_ts in past, until_ts in future: history should return update
        assert len(pnc.history(from_ts=0, until_ts=99)) > 0

    def test_PNCounter_merkle_history_e2e(self):
        pnc1 = classes.PNCounter()
        pnc2 = classes.PNCounter(clock=classes.ScalarClock(0, pnc1.clock.uuid))
        pnc1.increase()
        pnc1.increase()
        pnc2.decrease()

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

    def test_PNCounter_event_listeners_e2e(self):
        pnc = classes.PNCounter()
        logs = []
        def add_log(update: interfaces.StateUpdateProtocol):
            logs.append(update)

        assert len(logs) == 0
        pnc.increase()
        assert len(logs) == 0
        pnc.decrease()
        assert len(logs) == 0
        pnc.add_listener(add_log)
        pnc.increase()
        assert len(logs) == 1
        pnc.decrease()
        assert len(logs) == 2
        pnc.remove_listener(add_log)
        pnc.increase()
        assert len(logs) == 2
        pnc.decrease()
        assert len(logs) == 2


if __name__ == '__main__':
    unittest.main()
