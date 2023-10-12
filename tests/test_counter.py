from __future__ import annotations
from context import classes, interfaces, datawrappers, errors, StrClock, CustomStateUpdate
import packify
import unittest


class TestCounter(unittest.TestCase):
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

    def test_Counter_implements_CRDTProtocol(self):
        assert isinstance(classes.Counter(), interfaces.CRDTProtocol)

    def test_Counter_read_returns_int_counter(self):
        counter = classes.Counter()
        assert type(counter.read()) is int
        assert counter.read() == 0
        counter.counter = 1
        assert counter.read() == 1

    def test_Counter_increase_returns_state_update(self):
        counter = classes.Counter()
        update = counter.increase()
        assert isinstance(update, classes.StateUpdate)

    def test_Counter_history_returns_tuple_of_StateUpdate(self):
        counter = classes.Counter()
        counter.increase()
        counter.increase()
        history = counter.history()
        assert type(history) is tuple
        for update in history:
            assert type(update) is classes.StateUpdate

    def test_Counter_read_returns_int_with_correct_value(self):
        counter = classes.Counter()
        view1 = counter.read()
        assert type(view1) is int
        assert view1 == 0
        counter.increase()
        view2 = counter.read()
        assert view2 == 1

    def test_Counter_increase_changes_view(self):
        counter = classes.Counter()
        view1 = counter.read()
        counter.increase()
        view2 = counter.read()
        counter.increase()
        view3 = counter.read()
        assert view1 != view2
        assert view2 != view3
        assert view3 != view1

    def test_Counter_checksums_returns_tuple_of_int(self):
        counter = classes.Counter()
        checksum = counter.checksums()
        assert type(checksum) is tuple
        for item in checksum:
            assert type(item) is int

    def test_Counter_checksums_change_after_update(self):
        counter = classes.Counter()
        checksums1 = counter.checksums()
        counter.increase()
        checksums2 = counter.checksums()
        assert checksums1 != checksums2

    def test_Counter_update_is_idempotent(self):
        counter1 = classes.Counter()
        counter2 = classes.Counter(0, classes.ScalarClock(0, counter1.clock.uuid))
        update = counter1.increase()
        view1 = counter1.read()
        counter1.update(update)
        assert counter1.read() == view1
        counter2.update(update)
        view2 = counter2.read()
        counter2.update(update)
        assert counter2.read() == view2 == view1

    def test_Counter_update_from_history_converges(self):
        counter1 = classes.Counter()
        counter2 = classes.Counter(0, classes.ScalarClock(0, counter1.clock.uuid))
        counter1.increase()
        counter1.increase()

        for update in counter1.history():
            counter2.update(update)

        assert counter1.read() == counter2.read()
        assert counter1.checksums() == counter2.checksums()

    def test_Counter_pack_unpack_e2e(self):
        counter1 = classes.Counter()
        counter1.increase()
        counter1.increase()
        packed = counter1.pack()
        counter2 = classes.Counter.unpack(packed, inject=self.inject)

        assert counter1.clock.uuid == counter2.clock.uuid
        assert counter1.read() == counter2.read()
        assert counter1.checksums() == counter2.checksums()
        assert counter1.history() == counter2.history()

    def test_Counter_pack_unpack_e2e_with_injected_clock(self):
        ctr = classes.Counter(clock=StrClock())
        ctr.increase()
        packed = ctr.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.Counter.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.Counter.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock == ctr.clock
        assert unpacked.read() == ctr.read()

    def test_Counter_e2e_with_injected_StateUpdateProtocol_class(self):
        ctr = classes.Counter()
        update = ctr.increase(update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(ctr.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

        packed = ctr.pack()
        unpacked = classes.Counter.unpack(packed, inject=self.inject)

        assert unpacked.clock == ctr.clock
        assert unpacked.read() == ctr.read()

    def test_Counter_history_return_value_determined_by_from_ts_and_until_ts(self):
        counter = classes.Counter()
        counter.increase()
        counter.increase()
        counter.increase()

        # from_ts in future of last update, history should return nothing
        assert len(counter.history(from_ts=99)) == 0

        # until_ts in past of last update, history should return nothing
        assert len(counter.history(until_ts=0)) == 0

        # from_ts in past, until_ts in future: history should return update
        assert len(counter.history(from_ts=0, until_ts=99)) > 0

    def test_Counter_merkle_history_e2e(self):
        counter1 = classes.Counter()
        counter2 = classes.Counter(0, classes.ScalarClock(0, counter1.clock.uuid))
        counter1.increase()
        counter1.increase()
        counter2.increase()

        history1 = counter1.get_merkle_history()
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

        history2 = counter2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        diff1 = counter1.resolve_merkle_histories(history2)
        diff2 = counter2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 1
        assert len(diff2) == 1
        assert diff1[0] == history2[1][0]
        assert diff2[0] == history1[1][0]

    def test_Counter_event_listeners_e2e(self):
        counter = classes.Counter()
        logs = []
        def add_log(update: interfaces.StateUpdateProtocol):
            logs.append(update)

        assert len(logs) == 0
        counter.increase()
        assert len(logs) == 0
        counter.add_listener(add_log)
        counter.increase()
        assert len(logs) == 1
        counter.remove_listener(add_log)
        counter.increase()
        assert len(logs) == 1


if __name__ == '__main__':
    unittest.main()
