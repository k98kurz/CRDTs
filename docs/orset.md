# Observed-Removed Set

The Observed-Removed Set (ORSet) is a CRDT that tracks a set with dynamic
membership.

## Mathematics

The ORSet maintains two sets, the observed set and the removed set, and the
state of the CRDT is the observed set less the removed set.

## Usage

To use the ORSet, import it from the crdts library.

```python
from crdts import ORSet

orset = ORSet()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
orset = ORSet(clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

Note that items must meet the following type alias to work properly.

```python
SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType
```

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ORSet, DecimalWrapper
from decimal import Decimal

orset = ORSet()
orset.observe('a string item')
orset.remove('pre-emptive removals are ok')
orset.remove('hello world')
orset.observe(DecimalWrapper(Decimal('0.5')))

# simulate a replica
orset2 = ORSet()
orset2.clock.uuid = orset.clock.uuid

# create some concurrent updates
orset2.observe('hello world')
orset2.observe(DecimalWrapper(Decimal('420.69')))

# synchronize
for update in orset.history():
    orset2.update(update)

for update in orset2.history():
    orset.update(update)

# prove they have the same state
assert orset.read() == orset2.read()
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> ORSet:`

Unpack the data bytes string into an instance.

#### `read(/, *, inject: dict = {}) -> set[SerializableType]:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> ORSet:`

Apply an update and return self (monad pattern).

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

#### `observe(member: SerializableType, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that adds
the given member to the observed set. The member will be in the data attribute
at index 1.

#### `remove(member: SerializableType, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Adds the given member to the removed set.

#### `__init__(observed: set[SerializableType] = <factory>, observed_metadata: dict[SerializableType, StateUpdateProtocol] = <factory>, removed: set[SerializableType] = <factory>, removed_metadata: dict[SerializableType, StateUpdateProtocol] = <factory>, clock: ClockProtocol = <factory>, cache: Optional[tuple] = None):`

#### `__repr__():`

#### `__eq__():`
