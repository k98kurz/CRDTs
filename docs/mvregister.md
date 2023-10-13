# Multi-Value Register

The Multi-Value Register (`MVRegister`) is a CRDT that tracks a single named
register. Each subsequent write to the register overwrites the value stored in
it, and concurrent writes are preserved, hence the name.

## Mathematics

The mutable state of the `MVRegister` is composed of the following:
- `value: DataWrapperProtocol` - the current value at the local replica
- `clock: ClockProtocol` - the clock used for synchronization
- `last_update: Any` - the timestamp of the last update

The mathematics of the `MVRegister` are simple: given N concurrent updates, all
N values will be preserved, and their order in the `MVRegister` will be
determined by their serialized form.

## Usage

To use the `MVRegister`, import it from the crdts library.

```python
from crdts import MVRegister

mvr = MVRegister(name='some name')
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
name = 'some name'
mvr = MVRegister(name=name, clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

The register can then be written to with the `write` method:

```python
mvr.write('value1')
mvr.write('value2')
```

Note that values must meet the `packify.SerializableType` type alias to work properly:

`packify.interface.Packable | dict | list | set | tuple | int | float | decimal.Decimal | str | bytes | bytearray | None`

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ScalarClock, MVRegister

mvr = MVRegister(name='some name')
mvr.write('some value')

view = mvr.read() # should be "some value"

# create a replica
mvr2 = MVRegister.unpack(mvr.pack())
divergence_ts = mvr.clock.read()

# make concurrent updates
mvr.write('foo')
mvr2.write('bar')

# resynchronize
history1 = mvr.history(from_ts=divergence_ts)
history2 = mvr2.history(from_ts=divergence_ts)

for update in history1:
    mvr2.update(update)

for update in history2:
    mvr.update(update)

# prove they resynchronized and have the same state
assert mvr.read() == mvr2.read()

# mvr.read() will be ('bar', 'foo')
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `__init__(name: SerializableType, values: list[SerializableType] = [], clock: ClockProtocol = None, last_update: Any = None, listeners: list[Callable] = None) -> None:`

Initialize an MVRegister instance from name, values, clock, and last_update (all
but the first are optional). Raises TypeError for invalid name, values, or
clock.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> MVRegister:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view.

#### `@classmethod compare_values(value1: SerializableType, value2: SerializableType) -> bool:`

Return True if value1 is greater than value2, else False.

#### `update(state_update: StateUpdateProtocol) -> MVRegister:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update, state_update.clock_uuid, or state_update.data.

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

#### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

#### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

#### `write(value: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Writes the new value to the register and returns an update_class (StateUpdate by
default). Raises TypeError for invalid value.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
