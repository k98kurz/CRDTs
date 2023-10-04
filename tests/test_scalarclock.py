from __future__ import annotations
from dataclasses import dataclass, field, is_dataclass
from decimal import Decimal
from context import classes, interfaces, datawrappers, errors
import unittest


class TestScalarClock(unittest.TestCase):
    def test_ScalarClock_implements_ClockProtocol(self):
        assert isinstance(classes.ScalarClock(), interfaces.ClockProtocol)

    def test_ScalarClock_instance_has_counter_and_uuid(self):
        clock = classes.ScalarClock()
        assert hasattr(clock, 'counter')
        assert type(clock.counter) is int
        assert hasattr(clock, 'uuid')
        assert type(clock.uuid) is bytes

    def test_ScalarClock_read_returns_int(self):
        clock = classes.ScalarClock()
        assert type(clock.read()) is int

    def test_ScalarClock_read_changes_only_after_update(self):
        clock = classes.ScalarClock()
        t0 = clock.read()
        assert t0 == clock.read()
        clock.update(t0)
        assert clock.read() > t0

    def test_ScalarClock_is_later_returns_correct_bools(self):
        assert type(classes.ScalarClock.is_later(1, 0)) is bool
        assert classes.ScalarClock.is_later(1, 0)
        assert not classes.ScalarClock.is_later(0, 0)
        assert not classes.ScalarClock.is_later(0, 1)

    def test_ScalarClock_are_concurrent_returns_correct_bools(Self):
        assert type(classes.ScalarClock.are_concurrent(0, 0)) is bool
        assert classes.ScalarClock.are_concurrent(0, 0)
        assert not classes.ScalarClock.are_concurrent(1, 0)
        assert not classes.ScalarClock.are_concurrent(1, 2)

    def test_ScalarClock_compare_returns_correct_int(self):
        assert type(classes.ScalarClock.compare(0, 0)) is int
        assert classes.ScalarClock.compare(0, 0) == 0
        assert classes.ScalarClock.compare(1, 0) == 1
        assert classes.ScalarClock.compare(1, 2) == -1

    def test_ScalarClock_pack_returns_bytes(self):
        clock = classes.ScalarClock()
        assert type(clock.pack()) is bytes

    def test_ScalarClock_unpack_returns_same_clock(self):
        clock = classes.ScalarClock()
        clock2 = classes.ScalarClock.unpack(clock.pack())
        assert clock == clock2
        assert clock.uuid == clock2.uuid
        assert clock.counter == clock2.counter


if __name__ == '__main__':
    unittest.main()
