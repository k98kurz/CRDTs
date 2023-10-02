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
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> StrClock:
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

        with self.assertRaises(errors.UsageError) as e:
            unpacked = classes.PNCounter.unpack(packed)
        assert 'StrClock not found' in str(e.exception)

        # inject and repeat
        unpacked = classes.PNCounter.unpack(packed, {'StrClock': StrClock})

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


if __name__ == '__main__':
    unittest.main()
