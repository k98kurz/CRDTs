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


class TestMVMap(unittest.TestCase):
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

    def test_MVMap_implements_CRDTProtocol(self):
        assert isinstance(classes.MVMap(), interfaces.CRDTProtocol)

    def test_MVMap_read_returns_dict(self):
        mvmap = classes.MVMap()
        view = mvmap.read()
        assert isinstance(view, dict)

    def test_MVMap_extend_returns_StateUpdateProtocol(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        update = mvmap.extend(name, value)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_MVMap_read_after_extend_is_correct(self):
        mvmap = classes.MVMap()
        view1 = mvmap.read()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        mvmap.extend(name, value)
        view2 = mvmap.read()
        assert isinstance(view2, dict)
        assert view1 != view2
        assert name in view2
        assert view2[name] == (value,)

    def test_MVMap_unset_returns_StateUpdateProtocol(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        update = mvmap.unset(name)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_MVMap_read_after_unset_is_correct(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        mvmap.extend(name, value)
        view1 = mvmap.read()
        mvmap.unset(name)
        view2 = mvmap.read()
        assert name in view1
        assert name not in view2

    def test_MVMap_history_returns_tuple_of_StateUpdateProtocol(self):
        mvmap = classes.MVMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        mvmap.extend(name, value)
        mvmap.extend(value, name)
        history = mvmap.history()
        assert type(history) is tuple
        for update in history:
            assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_MVMap_concurrent_writes_preserve_all_values(self):
        mvmap = classes.MVMap()
        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap.clock.uuid
        name = datawrappers.StrWrapper('foo')
        value1 = datawrappers.StrWrapper('bar')
        value2 = datawrappers.StrWrapper('test')
        update1 = mvmap.extend(name, value1)
        update2 = mvmap2.extend(name, value2)
        mvmap.update(update2)
        mvmap2.update(update1)

        assert mvmap.read()[name] == (value1, value2)
        assert mvmap.checksums() == mvmap2.checksums()

    def test_MVMap_checksums_returns_tuple_of_int(self):
        mvmap = classes.MVMap()
        mvmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        checksums = mvmap.checksums()

        assert type(checksums) is tuple
        for item in checksums:
            assert type(item) is int

    def test_MVMap_checksums_change_after_update(self):
        mvmap = classes.MVMap()
        mvmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        checksums1 = mvmap.checksums()
        mvmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'))
        checksums2 = mvmap.checksums()
        mvmap.extend(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'))
        checksums3 = mvmap.checksums()

        assert checksums1 != checksums2
        assert checksums1 != checksums3
        assert checksums2 != checksums3

    def test_MVMap_update_is_idempotent(self):
        mvmap = classes.MVMap()
        update = mvmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        checksums1 = mvmap.checksums()
        view1 = mvmap.read()
        mvmap.update(update)
        checksums2 = mvmap.checksums()
        view2 = mvmap.read()

        assert checksums1 == checksums2
        assert view1 == view2

    def test_MVMap_updates_are_commutative(self):
        mvmap1 = classes.MVMap()
        mvmap2 = classes.MVMap(clock=classes.ScalarClock(uuid=mvmap1.clock.uuid))
        update1 = mvmap1.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        update2 = mvmap1.unset(datawrappers.StrWrapper('foo'))

        mvmap2.update(update2)
        mvmap2.update(update1)

        assert mvmap2.read() == mvmap1.read()

    def test_MVMap_updates_from_history_converge(self):
        mvmap1 = classes.MVMap()
        mvmap2 = classes.MVMap(clock=classes.ScalarClock(0, mvmap1.clock.uuid))
        mvmap1.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        mvmap1.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'))
        mvmap1.extend(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'))

        for update in mvmap1.history():
            mvmap2.update(update)

        assert mvmap1.checksums() == mvmap2.checksums()

        histories = permutations(mvmap1.history())
        for history in histories:
            mvmap2 = classes.MVMap(clock=classes.ScalarClock(0, mvmap1.clock.uuid))
            for update in history:
                mvmap2.update(update)
            assert mvmap2.read() == mvmap1.read()

    def test_MVMap_pack_unpack_e2e(self):
        mvmap = classes.MVMap()
        mvmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'))
        mvmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'))
        mvmap.extend(datawrappers.StrWrapper('floof'), datawrappers.StrWrapper('bruf'))
        mvmap.unset(datawrappers.StrWrapper('floof'))
        mvmap.extend(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'))
        packed = mvmap.pack()
        unpacked = classes.MVMap.unpack(packed, inject=self.inject)

        assert unpacked.checksums() == mvmap.checksums()

    def test_MVMap_pack_unpack_e2e_with_injected_clock(self):
        mvm = classes.MVMap(clock=StrClock())
        mvm.extend(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
        )
        mvm.extend(
            datawrappers.StrWrapper('second name'),
            datawrappers.StrWrapper('second value'),
        )
        packed = mvm.pack()

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.MVMap.unpack(packed, inject=self.inject)
        assert str(e.exception) == 'cannot find StrClock'

        # inject and repeat
        unpacked = classes.MVMap.unpack(
            packed, inject={**self.inject, 'StrClock': StrClock}
        )

        assert unpacked.clock == mvm.clock
        assert unpacked.read() == mvm.read()

    def test_MVMap_with_injected_StateUpdateProtocol_class(self):
        mvm = classes.MVMap()
        update = mvm.extend(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
            update_class=CustomStateUpdate
        )
        assert type(update) is CustomStateUpdate
        assert type(mvm.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

    def test_MVMap_convergence_from_ts(self):
        mvmap1 = classes.MVMap()
        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap1.clock.uuid
        for i in range(10):
            update = mvmap1.extend(
                datawrappers.IntWrapper(i),
                datawrappers.IntWrapper(i),
            )
            mvmap2.update(update)
        assert mvmap1.checksums() == mvmap2.checksums()

        mvmap1.extend(datawrappers.IntWrapper(69420), datawrappers.IntWrapper(69420))
        mvmap1.extend(datawrappers.IntWrapper(42096), datawrappers.IntWrapper(42096))
        mvmap2.extend(datawrappers.IntWrapper(23878), datawrappers.IntWrapper(23878))

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = mvmap1.clock.read()
        chksm1 = mvmap1.checksums(from_ts=from_ts, until_ts=until_ts)
        chksm2 = mvmap2.checksums(from_ts=from_ts, until_ts=until_ts)
        while chksm1 != chksm2 and until_ts > 0:
            until_ts -= 1
            chksm1 = mvmap1.checksums(from_ts=from_ts, until_ts=until_ts)
            chksm2 = mvmap2.checksums(from_ts=from_ts, until_ts=until_ts)
        from_ts = until_ts
        assert from_ts > 0

        for update in mvmap1.history(from_ts=from_ts):
            mvmap2.update(update)
        for update in mvmap2.history(from_ts=from_ts):
            mvmap1.update(update)

        assert mvmap1.checksums() == mvmap2.checksums()

        # prove it does not converge from bad ts parameters
        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap1.clock.uuid
        for update in mvmap1.history(until_ts=0):
            mvmap2.update(update)
        assert mvmap1.checksums() != mvmap2.checksums()

        mvmap2 = classes.MVMap()
        mvmap2.clock.uuid = mvmap1.clock.uuid
        for update in mvmap1.history(from_ts=99):
            mvmap2.update(update)
        assert mvmap1.checksums() != mvmap2.checksums()


if __name__ == '__main__':
    unittest.main()
