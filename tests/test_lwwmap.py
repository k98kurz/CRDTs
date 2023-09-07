from __future__ import annotations
from dataclasses import dataclass, field
from itertools import permutations
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

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.LWWMap.unpack(packed, inject=self.inject)
        assert str(e.exception) == 'cannot find StrClock'

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


if __name__ == '__main__':
    unittest.main()
