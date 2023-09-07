# Grow-only Set

The Grow-only Set (GSet) is a CRDT that encodes a set of items
that can only increase in membership over time.

## Mathematics

The state of the GSet is composed of the following:
- `members: set[SerializableType]` - the members of the GSet
- `clock: ClockProtocol` - the clock used for synchronization
- `update_history: dict[SerializableType, StateUpdateProtocol]` - a map
containing the state update for each member

This is one of the simplest CRDTs. Since it uses a set, each item can be added
multiple times but will appear in the data structure only once. The only
operation available is `add`. As it is a set, order of items is not maintained.

## Usage

To use the GSet, import it from the crdts library.

```python
from crdts import GSet

gset = GSet()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
gset = GSet(clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ScalarClock, GSet, StrWrapper, IntWrapper

gset = GSet()
gset.add("string 1")
gset.add("string 2")
gset.add("string 1")

view = gset.read() # should be set(["string 1", "string 2"])

# simulate replica
gset2 = GSet.unpack(gset.pack())

# make concurrent updates
gset.add(123)
gset2.add(321)
gset2.add(b'yellow submarine')

# resynchronize
history1 = gset.history()
history2 = gset2.history()

for update in history1:
    gset2.update(update)

for update in history2:
    gset.update(update)

# prove they have synchronized and have the same state
assert gset.read() == gset2.read()
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, inject: dict) -> GSet:`

Unpack the data bytes string into an instance.

#### `read() -> set:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol) -> GSet:`

Apply an update and return self (monad pattern).

#### `checksums(from_ts: Any, until_ts: Any) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure. If from_ts and/or until_ts are supplied, only those updates
that are not outside of these temporal constraints will be included.

#### `history(from_ts: Any, until_ts: Any) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes. If from_ts and/ or until_ts are supplied, only those updates that are not
outside of these temporal constraints will be included.

#### `add(member: DataWrapperProtocol, update_class: type[StateUpdateProtocol]) -> StateUpdateProtocol:`

Create, apply, and return a StateUpdate adding member to the set.
