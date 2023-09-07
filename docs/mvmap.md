# Multi-Value Map

The Multi-Value Map (MVMap) is a CRDT that maintains a map of serializable
values to MVRegisters that maintain serializable values.

The MVMap is a composition of the Observed-Removed Set (ORSet) and MVRegisters.
The ORSet tracks which map keys have been added and removed. Each key has an
assigned MVRegister for tracking the associated value(s).

## Usage

To use the MVMap, import it from the crdts library as well as at least one
class implementing the `DataWrapperProtocol` interface. For example:

```python
from crdts import MVMap, StrWrapper

mvmap = MVMap()
mvmap.set(StrWrapper('key'), StrWrapper('value'))
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
mvmap = MVMap(clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import MVMap, StrWrapper, IntWrapper

mvmap = MVMap()
mvmap.set(StrWrapper('key1'), StrWrapper('value'))
mvmap.set(StrWrapper('key2'), IntWrapper(420))

# create a replica
mvmap2 = MVMap()
mvmap2.clock.uuid = mvmap.clock.uuid

# make a concurrent update
mvmap2.set(IntWrapper(69), StrWrapper('nice'))
mvmap2.unset(StrWrapper('key1'))

# synchronize
for update in mvmap.history():
    mvmap2.update(update)

for update in mvmap2.history():
    mvmap.update(update)

# prove they have the same state
assert mvmap.read() == mvmap2.read()
```

### Properties

- names: ORSet
- registers: dict[DataWrapperProtocol, MVRegister]
- clock: ClockProtocol

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> MVMap:`

Unpack the data bytes string into an instance.

#### `read() -> dict:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol) -> MVMap:`

Apply an update and return self (monad pattern).

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdateProtocols that will converge to the
underlying data. Useful for resynchronization by replaying updates from
divergent nodes.

#### `set(name: DataWrapperProtocol, value: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Extends the dict with name: value. Returns an update_class (StateUpdate by
default) that should be propagated to all nodes.

#### `unset(name: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Removes the key name from the dict. Returns a StateUpdate.

#### `__init__(names: ORSet = None, registers: dict = None, clock: ClockProtocol = None) -> None:`

Initialize an MVMap from an ORSet of names, a list of MVRegisters, and a shared
clock.
