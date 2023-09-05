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
    def unpack(cls, data: bytes, inject: dict = {}) -> StrClock:
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

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.Counter.unpack(packed, inject=self.inject)
        assert 'not found' in str(e.exception)

        # inject and repeat
        unpacked = classes.Counter.unpack(packed, {'StrClock': StrClock})

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


if __name__ == '__main__':
    unittest.main()
