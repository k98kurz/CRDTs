# Last-Writer-Wins Map

The Last-Writer-Wins Map (`LWWMap`) is a CRDT that maintains a map of
serializable keys to `LWWRegister`s that maintain serializable values.

The `LWWMap` is a composition of the Observed-Removed Set (`ORSet`) and
`LWWRegister`s. The `ORSet` tracks which map keys have been added and removed.
Each key has an assigned `LWWRegister` for tracking the associated value.

## Usage

To use the `LWWMap`, import it from the crdts library as well as at least one
class implementing the `DataWrapperProtocol` interface. For example:

```python
from crdts import LWWMap, StrWrapper

writer_id = 1
lwwmap = LWWMap()
lwwmap.set(StrWrapper('key'), StrWrapper('value'), writer_id)
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
lwwmap = LWWMap(clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import LWWMap, StrWrapper, IntWrapper

writer_id = 1
lwwmap = LWWMap()
lwwmap.set(StrWrapper('key1'), StrWrapper('value'), writer_id)
lwwmap.set(StrWrapper('key2'), IntWrapper(420), writer_id)

# create a replica
writer_id = 2
lwwmap2 = LWWMap()
lwwmap2.clock.uuid = lwwmap.clock.uuid

# make a concurrent update
lwwmap2.set(IntWrapper(69), StrWrapper('nice'), writer_id)
lwwmap2.unset(StrWrapper('key1'), writer_id)

# synchronize
for update in lwwmap.history():
    lwwmap2.update(update)

for update in lwwmap2.history():
    lwwmap.update(update)

# prove they have the same state
assert lwwmap.read() == lwwmap2.read()
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWMap:`

Unpack the data bytes string into an instance.

#### `read(inject: dict = {}) -> dict:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> LWWMap:`

Apply an update and return self (monad pattern).

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdateProtocols that will converge to the
underlying data. Useful for resynchronization by replaying updates from
divergent nodes.

#### `set(name: DataWrapperProtocol, value: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Extends the dict with name: value. Returns an update_class (StateUpdate by
default) that should be propagated to all nodes.

#### `unset(name: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Removes the key name from the dict. Returns a StateUpdate.

#### `__init__(names: ORSet = None, registers: dict = None, clock: ClockProtocol = None) -> None:`

Initialize an LWWMap from an ORSet of names, a list of LWWRegisters, and a
shared clock.
