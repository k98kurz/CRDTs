# Grow-only Set

The Grow-only Set (`GSet`) is a CRDT that encodes a set of items that can only
increase in membership over time.

## Mathematics

The state of the `GSet` is composed of the following:
- `members: set[SerializableType]` - the members of the `GSet`
- `clock: ClockProtocol` - the clock used for synchronization
- `update_history: dict[SerializableType, StateUpdateProtocol]` - a map
containing the state update for each member

This is one of the simplest CRDTs. Since it uses a set, each item can be added
multiple times but will appear in the data structure only once. The only
operation available is `add`. As it is a set, order of items is not maintained.

## Usage

To use the `GSet`, import it from the crdts library.

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

Items can then be added using the `add` method:

```python
gset.add("item")
gset.add(123)
gset.add(b'yellow submarine')
gset.add([1, 2, 3])
```

Note that items must meet the `packify.SerializableType` type alias to work properly:

`packify.interface.Packable | dict | list | set | tuple | int | float | decimal.Decimal | str | bytes | bytearray | None`

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import GSet

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

#### `__init__(members: set[SerializableType] = <factory>, clock: ClockProtocol = <factory>, metadata: dict[SerializableType, Any] = <factory>, listeners: list[Callable] = <factory>):`

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> GSet:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(inject: dict = {}) -> set[SerializableType]:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> GSet:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure. If from_ts and/or until_ts are supplied, only those updates
that are not outside of these temporal constraints will be included.

#### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes. If from_ts and/ or until_ts are supplied, only those updates that are not
outside of these temporal constraints will be included.

#### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

#### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

#### `add(member: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Create, apply, and return a StateUpdate adding member to the set.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
