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


class TestLWWMap(unittest.TestCase):
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
        update = lwwmap.extend(name, value, 1)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_LWWMap_read_after_extend_is_correct(self):
        lwwmap = classes.LWWMap()
        view1 = lwwmap.read()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        lwwmap.extend(name, value, 1)
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
        lwwmap.extend(name, value, 1)
        view1 = lwwmap.read()
        lwwmap.unset(name, 1)
        view2 = lwwmap.read()
        assert name in view1
        assert name not in view2

    def test_LWWMap_history_returns_tuple_of_StateUpdateProtocol(self):
        lwwmap = classes.LWWMap()
        name = datawrappers.StrWrapper('foo')
        value = datawrappers.StrWrapper('bar')
        lwwmap.extend(name, value, 1)
        lwwmap.extend(value, name, 1)
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
        update1 = lwwmap.extend(name, value1, 1)
        update2 = lwwmap2.extend(name, value2, 3)
        lwwmap.update(update2)
        lwwmap2.update(update1)

        assert lwwmap.checksums() == lwwmap2.checksums()
        assert lwwmap.read()[name] == value2
        assert lwwmap2.read()[name] == value2

    def test_LWWMap_checksums_returns_tuple_of_int(self):
        lwwmap = classes.LWWMap()
        lwwmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        checksums = lwwmap.checksums()

        assert type(checksums) is tuple
        for item in checksums:
            assert type(item) is int

    def test_LWWMap_checksums_change_after_update(self):
        lwwmap = classes.LWWMap()
        lwwmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        checksums1 = lwwmap.checksums()
        lwwmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'), 1)
        checksums2 = lwwmap.checksums()
        lwwmap.extend(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'), 1)
        checksums3 = lwwmap.checksums()

        assert checksums1 != checksums2
        assert checksums1 != checksums3
        assert checksums2 != checksums3

    def test_LWWMap_update_is_idempotent(self):
        lwwmap = classes.LWWMap()
        update = lwwmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
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
        update1 = lwwmap1.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        update2 = lwwmap1.unset(datawrappers.StrWrapper('foo'), 1)

        lwwmap2.update(update2)
        lwwmap2.update(update1)

        assert lwwmap2.read() == lwwmap1.read()

    def test_LWWMap_updates_from_history_converge(self):
        lwwmap1 = classes.LWWMap()
        lwwmap2 = classes.LWWMap()
        lwwmap2.clock.uuid = lwwmap1.clock.uuid
        lwwmap1.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        lwwmap1.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'), 1)
        lwwmap1.extend(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'), 1)

        for update in lwwmap1.history():
            lwwmap2.update(update)

        assert lwwmap1.checksums() == lwwmap2.checksums()

    def test_LWWMap_pack_unpack_e2e(self):
        lwwmap = classes.LWWMap()
        lwwmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bar'), 1)
        lwwmap.extend(datawrappers.StrWrapper('foo'), datawrappers.StrWrapper('bruf'), 1)
        lwwmap.extend(datawrappers.StrWrapper('floof'), datawrappers.StrWrapper('bruf'), 1)
        lwwmap.unset(datawrappers.StrWrapper('floof'), 1)
        lwwmap.extend(datawrappers.StrWrapper('oof'), datawrappers.StrWrapper('bruf'), 1)
        packed = lwwmap.pack()
        unpacked = classes.LWWMap.unpack(packed)

        assert unpacked.checksums() == lwwmap.checksums()

    def test_LWWMap_pack_unpack_e2e_with_injected_clock(self):
        lwwm = classes.LWWMap(clock=StrClock())
        lwwm.extend(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
            1
        )
        lwwm.extend(
            datawrappers.StrWrapper('second name'),
            datawrappers.StrWrapper('second value'),
            1
        )
        packed = lwwm.pack()

        with self.assertRaises(errors.UsagePreconditionError) as e:
            unpacked = classes.LWWMap.unpack(packed)
        assert str(e.exception) == 'cannot find StrClock'

        # inject and repeat
        unpacked = classes.LWWMap.unpack(packed, {'StrClock': StrClock})

        assert unpacked.clock == lwwm.clock
        assert unpacked.read() == lwwm.read()

    def test_LWWMap_with_injected_StateUpdateProtocol_class(self):
        lwwm = classes.LWWMap()
        update = lwwm.extend(
            datawrappers.StrWrapper('first name'),
            datawrappers.StrWrapper('first value'),
            1,
            update_class=CustomStateUpdate
        )
        assert type(update) is CustomStateUpdate
        assert type(lwwm.history(CustomStateUpdate)[0]) is CustomStateUpdate


if __name__ == '__main__':
    unittest.main()
