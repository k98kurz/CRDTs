from __future__ import annotations
from .causaltree import CausalTree
from .counter import Counter
from .fiarray import FIArray
from .gset import GSet
from .interfaces import (
    ClockProtocol,
    CRDTProtocol,
    DataWrapperProtocol,
    PackableProtocol,
    StateUpdateProtocol,
)
from .lwwmap import LWWMap
from .lwwregister import LWWRegister
from .orset import ORSet
from .pncounter import PNCounter
from .rgarray import RGArray
from .scalarclock import ScalarClock
from .stateupdate import StateUpdate
from enum import Enum
from types import NoneType


class ValidCRDTs(Enum):
    gs = GSet
    ors = ORSet
    c = Counter
    pnc = PNCounter
    rga = RGArray
    lwwr = LWWRegister
    lwwm = LWWMap
    tombstone = NoneType


class CompositeCRDT:
    component_names: ORSet
    component_data: dict[bytes, CRDTProtocol]
    clock: ClockProtocol

    def __init__(self, component_names: ORSet = None,
                component_data: dict = None, clock: ClockProtocol = None
    ) -> None:
        """Initialize a CompositeCRDT from components and a shared clock."""
        assert isinstance(component_names, ORSet) or component_names is None, 'component_names must be an ORSet or None'
        assert type(component_data) is dict or component_data is None, 'component_data must be a dict or None'
        assert isinstance(clock, ClockProtocol) or clock is None, 'clock must be a ClockProtocol or None'

        component_names = component_names if isinstance(component_names, ORSet) else ORSet()
        component_data = component_data if type(component_data) is dict else {}
        clock = clock if isinstance(clock, ClockProtocol) else ScalarClock()

        component_names.clock = self.clock

        for name in component_data:
            assert isinstance(component_data[name], CRDTProtocol), 'each component must be a CRDT'
            assert name in component_names.observed or name in component_names.removed, \
                'each component name must be referenced in the ORSet'
            component_data[name].clock = clock

        self.component_names = component_names
        self.component_data = component_data
        self.clock = clock

    """Implements the Replicated Growable Array CRDT."""
    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        ...

    @classmethod
    def unpack(cls, data: bytes, inject: dict[str, PackableProtocol]) -> CompositeCRDT:
        """Unpack the data bytes string into an instance."""
        ...

    def read(self):
        """Return the eventually consistent data view."""
        view = {}

        for name in self.component_names.read():
            view[name] = self.component_data[name].read()

        return view

    def update(self, state_update: StateUpdateProtocol) -> CompositeCRDT:
        """Apply an update and return self (monad pattern)."""
        assert isinstance(state_update, StateUpdateProtocol), \
            'state_update must be instance implementing StateUpdateProtocol'
        assert state_update.clock_uuid == self.clock.uuid, \
            'state_update.clock_uuid must equal CRDT.clock.uuid'
        assert type(state_update.data) is tuple, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert len(state_update.data) == 4, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[0]) is str, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[1]) is str, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[2]) is str, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert type(state_update.data[3]) is StateUpdate or state_update.data[3] is None, \
            'state_update.data must be tuple of (str, str, str, StateUpdate|None)'
        assert state_update.data[0] in ('o', 'r'), \
            'state_update.data[0] must be one of (\'o\', \'r\')'
        assert state_update.data[1] in ValidCRDTs.__members__, \
            'state_update.data[1] must name a member of ValidCRDTs enum'

        # parse data
        ts = state_update.ts
        op, crdt_type_name, name, state_update = state_update.data
        crdt_type = ValidCRDTs[crdt_type_name].value

        # observe a component
        if op == 'o':
            # observe the new component
            if name not in self.component_names.observed or name in self.component_names.removed:
                self.component_names.update(StateUpdate(self.clock.uuid, ts, ('o', name)))

            # create an empty instance of the crdt
            if name not in self.component_data:
                crdt = crdt_type()
                crdt.clock = self.clock
                self.component_data[name] = crdt

            # apply the update
            if state_update is not None:
                self.component_data[name].update(state_update)

        # remove a component
        if op == 'r':
            # remove the component
            if name not in self.component_names.removed or name in self.component_names.observed:
                self.component_names.update(StateUpdate(self.clock.uuid, ts, ('r', name)))

            if state_update is not None:
                # create an empty instance of the crdt
                if name not in self.component_data:
                    crdt = crdt_type()
                    crdt.clock = self.clock
                    self.component_data[name] = crdt

                # apply the update
                self.component_data[name].update(state_update)

        return self

    def checksums(self) -> tuple[tuple[str, tuple]]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        checksums = []

        checksums.append(('component_names', self.component_names.checksums()))

        for name in self.component_names.read():
            checksums.append((name, self.component_data[name].checksums()))

        return tuple(checksums)

    def history(self) -> tuple[StateUpdate]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        updates = []

        # compile concise list of updates for each component
        for name in self.component_names.read():
            history = self.component_data[name].history()
            classname = ValidCRDTs(self.component_data[name].__class__).name

            for event in history:
                updates.append(StateUpdate(
                    self.clock.uuid,
                    event.ts,
                    ('o', classname, name, event.data)
                ))

        # compile concise list of updates for each tombstone
        for name in self.component_names.removed:
            ts = self.component_names.removed_metadata[name]
            if name in self.component_data:
                classname = ValidCRDTs(self.component_data[name].__class__).name
            else:
                classname = ValidCRDTs.tombstone.name

            updates.append(StateUpdate(
                self.clock.uuid,
                ts,
                ('r', classname, name, None)
            ))

        return tuple(updates)
