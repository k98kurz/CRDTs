from __future__ import annotations
from dataclasses import dataclass, field, is_dataclass
from decimal import Decimal
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
    def unpack(cls, data: bytes) -> StrClock:
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


class TestORSet(unittest.TestCase):
    def test_ORSet_implements_CRDTProtocol(self):
        assert isinstance(classes.ORSet(), interfaces.CRDTProtocol)

    def test_ORSet_read_returns_add_biased_set_difference(self):
        orset = classes.ORSet()
        assert orset.read() == set()
        orset.observe(1)
        orset.observe(2)
        assert orset.read() == set(['1', '2'])
        orset.remove(1)
        assert orset.read() == set(['2'])

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
        assert [*view2][0] == '1'
        orset.observe(2)
        view3 = orset.read()
        assert len(view3) == 2
        assert '1' in view3
        assert '2' in view3
        orset.remove(1)
        view4 = orset.read()
        assert len(view4) == 1
        assert '2' in view4

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

        for update in orset1.history():
            orset2.update(update)

        assert orset1.read() == orset2.read()
        assert orset1.checksums() == orset2.checksums()

    def test_ORSet_pack_unpack_e2e(self):
        orset1 = classes.ORSet()
        orset1.observe(1)
        orset1.observe(datawrappers.StrWrapper('hello'))
        orset1.remove(2)
        orset1.remove(datawrappers.BytesWrapper(b'hello'))
        packed = orset1.pack()
        orset2 = classes.ORSet.unpack(packed)

        assert orset1.clock.uuid == orset2.clock.uuid
        assert orset1.read() == orset2.read()
        assert orset1.checksums() == orset2.checksums()
        assert orset1.history() == orset2.history()

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

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.ORSet.unpack(packed)
        assert str(e.exception) == 'cannot find StrClock'

        # inject and repeat
        unpacked = classes.ORSet.unpack(packed, {'StrClock': StrClock})

        assert unpacked.clock == ors.clock
        assert unpacked.read() == ors.read()

    def test_ORSet_pack_unpack_e2e_with_injected_StateUpdateProtocol_class(self):
        ors = classes.ORSet()
        update = ors.observe('test', update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(ors.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate


if __name__ == '__main__':
    unittest.main()
