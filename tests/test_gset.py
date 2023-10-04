from __future__ import annotations
from dataclasses import dataclass, field
from itertools import permutations
from context import classes, interfaces, datawrappers, errors
import packify
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


class TestGSet(unittest.TestCase):
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

    def test_GSet_implements_CRDTProtocol(self):
        assert isinstance(classes.GSet(), interfaces.CRDTProtocol)

    def test_GSet_read_returns_members(self):
        gset = classes.GSet()
        assert gset.read() == gset.members
        gset.members.add(datawrappers.IntWrapper(1))
        assert gset.read() == gset.members

    def test_GSet_add_errors_on_incorrect_type(self):
        gset = classes.GSet()
        with self.assertRaises(TypeError):
            gset.add(gset)

    def test_GSet_add_returns_state_update(self):
        gset = classes.GSet()
        update = gset.add(datawrappers.IntWrapper(1))
        assert isinstance(update, classes.StateUpdate)

    def test_GSet_history_returns_tuple_of_StateUpdate(self):
        gset = classes.GSet()
        gset.add(datawrappers.IntWrapper(1))
        gset.add(datawrappers.IntWrapper(2))
        history = gset.history()
        assert type(history) is tuple
        for update in history:
            assert type(update) is classes.StateUpdate

    def test_GSet_read_returns_set_with_correct_values(self):
        gset = classes.GSet()
        view1 = gset.read()
        assert type(view1) is set
        assert len(view1) == 0
        gset.add(datawrappers.IntWrapper(1))
        view2 = gset.read()
        assert len(view2) == 1
        assert [*view2][0] == datawrappers.IntWrapper(1)

    def test_GSet_add_new_member_changes_view(self):
        gset = classes.GSet()
        view1 = gset.read()
        gset.add(datawrappers.IntWrapper(1))
        view2 = gset.read()
        gset.add(datawrappers.IntWrapper(2))
        view3 = gset.read()
        assert view1 != view2
        assert view2 != view3
        assert view3 != view1

    def test_GSet_add_same_member_does_not_change_view(self):
        gset = classes.GSet()
        gset.add(datawrappers.IntWrapper(1))
        view1 = gset.read()
        gset.add(datawrappers.IntWrapper(1))
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
        gset.add(datawrappers.IntWrapper(1))
        checksums2 = gset.checksums()
        assert checksums1 != checksums2

    def test_GSet_update_is_idempotent(self):
        gset1 = classes.GSet()
        gset2 = classes.GSet(set(), classes.ScalarClock(0, gset1.clock.uuid))
        update = gset1.add(datawrappers.IntWrapper(2))
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
        gset1.add(datawrappers.IntWrapper(1))
        gset1.add(datawrappers.IntWrapper(2))
        gset1.add(datawrappers.IntWrapper(3))

        for update in gset1.history():
            gset2.update(update)

        assert gset1.read() == gset2.read()
        assert gset1.checksums() == gset2.checksums()

        histories = permutations(gset1.history())
        for history in histories:
            gset3 = classes.GSet(clock=classes.ScalarClock(0, gset1.clock.uuid))
            for update in history:
                gset3.update(update)
            assert gset3.read() == gset1.read()

    def test_GSet_pack_unpack_e2e(self):
        gset1 = classes.GSet()
        gset1.add(datawrappers.IntWrapper(1))
        gset1.add(datawrappers.IntWrapper(2))
        packed = gset1.pack()
        gset2 = classes.GSet.unpack(packed, inject=self.inject)

        assert gset1.clock.uuid == gset2.clock.uuid
        assert gset1.read() == gset2.read()
        assert gset1.checksums() == gset2.checksums()
        assert gset1.history() == gset2.history()

    def test_GSet_pack_unpack_e2e_with_injected_clock(self):
        gset = classes.GSet(clock=StrClock())
        gset.add(datawrappers.StrWrapper('test'))
        packed = gset.pack()

        with self.assertRaises(packify.UsageError) as e:
            unpacked = classes.GSet.unpack(packed, inject=self.inject)
        assert 'StrClock' in str(e.exception)

        # inject and repeat
        unpacked = classes.GSet.unpack(packed, inject={**self.inject, 'StrClock': StrClock})

        assert unpacked.clock == gset.clock
        assert unpacked.read() == gset.read()

    def test_GSet_e2e_injected_StateUpdateProtocol_class(self):
        gset = classes.GSet()
        update = gset.add(datawrappers.StrWrapper('test'), update_class=CustomStateUpdate)
        assert type(update) is CustomStateUpdate
        assert type(gset.history(update_class=CustomStateUpdate)[0]) is CustomStateUpdate

        packed = gset.pack()

        unpacked = classes.GSet.unpack(packed, inject=self.inject)

        assert unpacked.clock == gset.clock
        assert unpacked.read() == gset.read()

    def test_GSet_convergence_from_ts(self):
        gset1 = classes.GSet()
        gset2 = classes.GSet(set(), classes.ScalarClock(0, gset1.clock.uuid))
        for i in range(10):
            update = gset1.add(datawrappers.IntWrapper(i))
            gset2.update(update)
        assert gset1.checksums() == gset2.checksums()

        gset1.add(datawrappers.IntWrapper(69420))
        gset2.add(datawrappers.IntWrapper(42069))
        assert gset1.checksums() != gset2.checksums()

        # not the most efficient algorithm, but it demonstrates the concept
        from_ts = 0
        until_ts = gset1.clock.read()
        while gset1.checksums(from_ts=from_ts, until_ts=until_ts) != \
            gset2.checksums(from_ts=from_ts, until_ts=until_ts) \
            and until_ts > 0:
            until_ts -= 1
        from_ts = until_ts
        assert from_ts > 0

        for update in gset1.history(from_ts=from_ts):
            gset2.update(update)
        for update in gset2.history(from_ts=from_ts):
            gset1.update(update)

        assert gset1.checksums() == gset2.checksums()

        # prove it does not converge from bad ts parameters
        gset2 = classes.GSet()
        gset2.clock.uuid = gset1.clock.uuid
        for update in gset1.history(until_ts=0):
            gset2.update(update)
        assert gset1.checksums() != gset2.checksums()

        gset2 = classes.GSet()
        gset2.clock.uuid = gset1.clock.uuid
        for update in gset1.history(from_ts=99):
            gset2.update(update)
        assert gset1.checksums() != gset2.checksums()

    def test_GSet_merkle_history_e2e(self):
        gset1 = classes.GSet()
        gset2 = classes.GSet(clock=classes.ScalarClock(0, gset1.clock.uuid))
        gset2.update(gset1.add('hello world'))
        gset2.update(gset1.add(b'hello world'))
        gset1.add('not the lipsum')
        gset2.add(b'yellow submarine')

        history1 = gset1.get_merkle_history()
        assert type(history1) in (list, tuple), \
            'history must be [bytes, [bytes, ], dict]'
        assert len(history1) == 3, \
            'history must be [bytes, [bytes, ], dict]'
        assert all([type(leaf) is bytes for leaf in history1[1]]), \
            'history must be [bytes, [bytes, ], dict]'
        assert all([
            type(leaf_id) is type(leaf) is bytes
            for leaf_id, leaf in history1[2].items()
        ]), 'history must be [[bytes, ], bytes, dict[bytes, bytes]]'
        assert all([leaf_id in history1[2] for leaf_id in history1[1]]), \
            'history[2] dict must have all keys in history[1] list'

        history2 = gset2.get_merkle_history()
        assert all([leaf_id in history2[2] for leaf_id in history2[1]]), \
            'history[2] dict must have all keys in history[1] list'
        cidmap1 = history1[2]
        cidmap2 = history2[2]

        diff1 = gset1.resolve_merkle_histories(history2)
        diff2 = gset2.resolve_merkle_histories(history1)
        assert type(diff1) in (list, tuple)
        assert all([type(d) is bytes for d in diff1])
        assert len(diff1) == 1, [d.hex() for d in diff1]
        assert len(diff2) == 1, [d.hex() for d in diff2]

        # synchronize
        for cid in diff1:
            gset1.update(classes.StateUpdate.unpack(cidmap2[cid]))
        for cid in diff2:
            gset2.update(classes.StateUpdate.unpack(cidmap1[cid]))

        assert gset1.checksums() == gset2.checksums()


if __name__ == '__main__':
    unittest.main()
