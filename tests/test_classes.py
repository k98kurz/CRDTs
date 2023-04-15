from __future__ import annotations
from dataclasses import dataclass, is_dataclass
from context import classes, interfaces
import struct
import unittest


@dataclass
class StrDataWrapper:
    value: str

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other) -> bool:
        return type(self) == type(other) and self.value == other.value

    def pack(self) -> bytes:
        data = bytes(self.value, 'utf-8')
        return struct.pack(f'!{len(data)}s', data)

    @classmethod
    def unpack(cls, data: bytes) -> StrDataWrapper:
        return cls(str(struct.unpack(f'!{len(data)}s', data)[0], 'utf-8'))


class BytesDataWrapper(StrDataWrapper):
    value: bytes

    def pack(self) -> bytes:
        return struct.pack(f'!{len(self.value)}s', self.value)

    @classmethod
    def unpack(cls, data: bytes) -> BytesDataWrapper:
        return cls(struct.unpack(f'!{len(data)}s', data)[0])


# inject StrDataWrapper class for testing unpack in e.g. LWWRegister
classes.StrDataWrapper = StrDataWrapper
classes.BytesDataWrapper = BytesDataWrapper


class TestCRDTs(unittest.TestCase):
    # StrDataWrapper test
    def test_StrDataWrapper_implements_DataWrapperProtocol(self):
        assert isinstance(classes.StrDataWrapper(''), interfaces.DataWrapperProtocol)

    # StateUpdate test
    def test_StateUpdate_is_dataclass_with_attributes(self):
        update = classes.StateUpdate(b'123', 123, 321)
        assert is_dataclass(update)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    # ScalarClock tests
    def test_ScalarClock_implements_ClockProtocol(self):
        assert isinstance(classes.ScalarClock(), classes.ClockProtocol)

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

    # GSet tests
    def test_GSet_implements_CRDTProtocol(self):
        assert isinstance(classes.GSet(), interfaces.CRDTProtocol)

    def test_GSet_read_returns_members(self):
        gset = classes.GSet()
        assert gset.read() == gset.members
        gset.members.add(1)
        assert gset.read() == gset.members

    def test_GSet_add_returns_state_update(self):
        gset = classes.GSet()
        update = gset.add(1)
        assert isinstance(update, classes.StateUpdate)

    def test_GSet_history_returns_tuple_of_StateUpdate(self):
        gset = classes.GSet()
        gset.add(1)
        gset.add(2)
        history = gset.history()
        assert type(history) is tuple
        for update in history:
            assert type(update) is classes.StateUpdate

    def test_GSet_read_returns_set_with_correct_values(self):
        gset = classes.GSet()
        view1 = gset.read()
        assert type(view1) is set
        assert len(view1) == 0
        gset.add(1)
        view2 = gset.read()
        assert len(view2) == 1
        assert [*view2][0] == 1

    def test_GSet_add_new_member_changes_view(self):
        gset = classes.GSet()
        view1 = gset.read()
        gset.add(1)
        view2 = gset.read()
        gset.add(2)
        view3 = gset.read()
        assert view1 != view2
        assert view2 != view3
        assert view3 != view1

    def test_GSet_add_same_member_does_not_change_view(self):
        gset = classes.GSet()
        gset.add(1)
        view1 = gset.read()
        gset.add(1)
        view2 = gset.read()
        assert view1 == view2

    def test_GSet_checksums_returns_tuple_of_int(self):
        gset = classes.GSet()
        checksum = gset.checksums()
        assert type(checksum) is tuple
        for item in checksum:
            assert type(item) is int

    def test_GSet_checksums_change_after_update(self):
        gset = classes.GSet()
        checksums1 = gset.checksums()
        gset.add(1)
        checksums2 = gset.checksums()
        assert checksums1 != checksums2

    def test_GSet_update_is_idempotent(self):
        gset1 = classes.GSet()
        gset2 = classes.GSet(set(), classes.ScalarClock(0, gset1.clock.uuid))
        update = gset1.add(2)
        view1 = gset1.read()
        gset1.update(update)
        assert gset1.read() == view1
        gset2.update(update)
        view2 = gset2.read()
        gset2.update(update)
        assert gset2.read() == view2 == view1

    def test_GSet_update_from_history_converges(self):
        gset1 = classes.GSet()
        gset2 = classes.GSet(set(), classes.ScalarClock(0, gset1.clock.uuid))
        gset1.add(1)
        gset1.add(2)

        for update in gset1.history():
            gset2.update(update)

        assert gset1.read() == gset2.read()
        assert gset1.checksums() == gset2.checksums()

    def test_GSet_pack_unpack_e2e(self):
        gset1 = classes.GSet()
        gset1.add(1)
        gset1.add(2)
        packed = gset1.pack()
        gset2 = classes.GSet.unpack(packed)

        assert gset1.clock.uuid == gset2.clock.uuid
        assert gset1.read() == gset2.read()
        assert gset1.checksums() == gset2.checksums()
        assert gset1.history() == gset2.history()

    # Counter tests
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
        counter2 = classes.Counter.unpack(packed)

        assert counter1.clock.uuid == counter2.clock.uuid
        assert counter1.read() == counter2.read()
        assert counter1.checksums() == counter2.checksums()
        assert counter1.history() == counter2.history()

    # ORSet tests
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

    def test_ORSet_update_from_history_converges(self):
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
        orset1.remove(2)
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

    # PNCounter tests
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

    # FIArray tests

    # RGArray tests

    # LWWRegister tests
    def test_LWWRegister_implements_CRDTProtocol(self):
        assert isinstance(classes.LWWRegister('test'), interfaces.CRDTProtocol)

    def test_LWWRegister_read_returns_DataWrapperProtocol(self):
        lwwregister = classes.LWWRegister('test', StrDataWrapper('foobar'))
        assert isinstance(lwwregister.read(), classes.DataWrapperProtocol)
        assert lwwregister.read().value == 'foobar'

    def test_LWWRegister_write_returns_StateUpdate_and_sets_value(self):
        # lwwregister = classes.LWWRegister('test', StrDataWrapper('foobar'))
        lwwregister = classes.LWWRegister('test', BytesDataWrapper(b'foobar'))
        # update = lwwregister.write(StrDataWrapper('barfoo'), 1)
        update = lwwregister.write(BytesDataWrapper(b'barfoo'), 1)
        assert isinstance(update, classes.StateUpdate)
        assert lwwregister.read().value == b'barfoo'

    def test_LWWRegister_history_returns_tuple_of_StateUpdate(self):
        lwwregister = classes.LWWRegister('test', StrDataWrapper('foobar'))
        lwwregister.write(StrDataWrapper('sdsd'), 2)
        lwwregister.write(StrDataWrapper('barfoo'), 1)
        history = lwwregister.history()

        assert type(history) is tuple
        for item in history:
            assert isinstance(item, classes.StateUpdate)

    def test_LWWRegister_concurrent_writes_bias_to_higher_writer(self):
        lwwregister1 = classes.LWWRegister('test')
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister('test', clock=clock)

        update1 = lwwregister1.write(StrDataWrapper('foobar'), 1)
        update2 = lwwregister2.write(StrDataWrapper('barfoo'), 2)
        lwwregister1.update(update2)
        lwwregister2.update(update1)

        assert lwwregister1.read().value == lwwregister2.read().value
        assert lwwregister1.read().value == 'barfoo'

    def test_LWWRegister_checksums_returns_tuple_of_int(self):
        lwwregister = classes.LWWRegister('test', StrDataWrapper('thing'))
        assert type(lwwregister.checksums()) is tuple
        for item in lwwregister.checksums():
            assert type(item) is int

    def test_LWWRegister_checksums_change_after_update(self):
        lwwregister1 = classes.LWWRegister('test', StrDataWrapper(''))
        clock = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister('test', StrDataWrapper(''), clock=clock)
        checksums1 = lwwregister1.checksums()

        assert lwwregister2.checksums() == checksums1

        lwwregister1.write(StrDataWrapper('thing'), 1)
        lwwregister2.write(StrDataWrapper('stuff'), 2)

        assert lwwregister1.checksums() != checksums1
        assert lwwregister2.checksums() != checksums1
        assert lwwregister1.checksums() != lwwregister2.checksums()

    def test_LWWRegister_update_is_idempotent(self):
        lwwregister1 = classes.LWWRegister('test')
        clock1 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister('test', clock=clock1)

        update = lwwregister1.write(StrDataWrapper('foo1'), 1)
        view1 = lwwregister1.read()
        lwwregister1.update(update)
        assert lwwregister1.read() == view1
        lwwregister2.update(update)
        view2 = lwwregister2.read()
        lwwregister2.update(update)
        assert lwwregister2.read() == view2

        update = lwwregister2.write(StrDataWrapper('bar'), 2)
        lwwregister1.update(update)
        view1 = lwwregister1.read()
        lwwregister1.update(update)
        assert lwwregister1.read() == view1
        lwwregister2.update(update)
        view2 = lwwregister2.read()
        lwwregister2.update(update)
        assert lwwregister2.read() == view2

    def test_LWWRegister_update_from_history_converges(self):
        lwwregister1 = classes.LWWRegister('test')
        clock1 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        clock2 = classes.ScalarClock.unpack(lwwregister1.clock.pack())
        lwwregister2 = classes.LWWRegister('test', clock=clock1)
        lwwregister3 = classes.LWWRegister('test', clock=clock2)

        update = lwwregister1.write(StrDataWrapper('foo1'), 1)
        lwwregister2.update(update)
        lwwregister2.write(StrDataWrapper('bar'), 2)

        for item in lwwregister2.history():
            lwwregister1.update(item)
            lwwregister3.update(item)

        assert lwwregister1.read().value == lwwregister2.read().value
        assert lwwregister1.read().value == lwwregister3.read().value
        assert lwwregister1.checksums() == lwwregister2.checksums()
        assert lwwregister1.checksums() == lwwregister3.checksums()

    def test_LWWRegister_pack_unpack_e2e(self):
        lwwregister = classes.LWWRegister('test', StrDataWrapper(''))
        packed = lwwregister.pack()
        unpacked = classes.LWWRegister.unpack(packed)

        assert isinstance(unpacked, classes.LWWRegister)
        assert unpacked.clock == lwwregister.clock
        assert unpacked.read() == lwwregister.read()

    # LWWMap tests
    def test_LWWMap_implements_CRDTProtocol(self):
        assert isinstance(classes.LWWMap(), interfaces.CRDTProtocol)

    def test_LWWMap_read_returns_dict(self):
        lwwmap = classes.LWWMap()
        view = lwwmap.read()
        assert isinstance(view, dict)

    def test_LWWMap_extend_returns_StateUpdateProtocol(self):
        lwwmap = classes.LWWMap()
        name = StrDataWrapper('foo')
        value = StrDataWrapper('bar')
        update = lwwmap.extend(name, value, 1)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_LWWMap_read_after_extend_is_correct(self):
        lwwmap = classes.LWWMap()
        view1 = lwwmap.read()
        name = StrDataWrapper('foo')
        value = StrDataWrapper('bar')
        lwwmap.extend(name, value, 1)
        view2 = lwwmap.read()
        assert isinstance(view2, dict)
        assert view1 != view2
        assert name in view2
        assert view2[name] == value

    def test_LWWMap_unset_returns_StateUpdateProtocol(self):
        lwwmap = classes.LWWMap()
        name = StrDataWrapper('foo')
        update = lwwmap.unset(name, 1)
        assert isinstance(update, interfaces.StateUpdateProtocol)

    def test_LWWMap_read_after_unset_is_correct(self):
        lwwmap = classes.LWWMap()
        name = StrDataWrapper('foo')
        value = StrDataWrapper('bar')
        lwwmap.extend(name, value, 1)
        view1 = lwwmap.read()
        lwwmap.unset(name, 1)
        view2 = lwwmap.read()
        assert name in view1
        assert name not in view2

    # def test_LWWMap_


if __name__ == '__main__':
    unittest.main()
