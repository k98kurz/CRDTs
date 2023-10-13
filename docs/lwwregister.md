# Last-Writer-Wins Register

The Last-Writer-Wins Register (`LWWRegister`) is a CRDT that tracks a single
named register. Each subsequent write to the register overwrites the value
stored in it, and concurrent writes are handled by a tie-breaker process using
the writer id integer and then value itself if necessary.

## Mathematics

The mutable state of the `LWWRegister` is composed of the following:
- `value: DataWrapperProtocol` - the current value at the local replica
- `clock: ClockProtocol` - the clock used for synchronization
- `last_update: Any` - the timestamp of the last update
- `last_writer: int` - the ID of the source of the most recent write/overwrite
of the `value`

The mathematics of the `LWWRegister` are simple: given two concurrent updates,
the resultant `value` will be determined by the update with the highest writer
ID; given two concurrent updates with identical writer ID, the resultant `value`
will be determined by which value has the higher byte value when serialized.

## Usage

To use the `LWWRegister`, import it from the crdts library.

```python
from crdts import LWWRegister

lwwr = LWWRegister(name='some name')
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
name = 'some name'
lwwr = LWWRegister(name=name, clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

The register can then be written to with the `write` method:

```python
writer_id = 1
lrrw.write('value1', writer_id)
lrrw.write('value2', writer_id)
```

Note that values must meet the `packify.SerializableType` type alias to work properly:

`packify.interface.Packable | dict | list | set | tuple | int | float | decimal.Decimal | str | bytes | bytearray | None`

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ScalarClock, LWWRegister

writer_id = 1
lwwr = LWWRegister(name='some name')
lwwr.write('some value', writer_id)

view = lwwr.read() # should be "some value"

# create a replica
writer_id2 = 2
lwwr2 = LWWRegister.unpack(lwwr.pack())
divergence_ts = lwwr.clock.read()

# make concurrent updates
lwwr.write('foo', writer_id)
lwwr2.write('bar', writer_id2)

# resynchronize
history1 = lwwr.history(from_ts=divergence_ts)
history2 = lwwr2.history(from_ts=divergence_ts)

for update in history1:
    lwwr2.update(update)

for update in history2:
    lwwr.update(update)

# prove they resynchronized and have the same state
assert lwwr.read() == lwwr2.read()
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `__init__(name: SerializableType, value: SerializableType = None, clock: ClockProtocol = None, last_update: Any = None, last_writer: SerializableType = None, listeners: list[Callable] = None) -> None:`

Initialize an LWWRegister from a name, a value, and a shared clock. Raises
TypeError for invalid parameters.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWRegister:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(/, *, inject: dict = {}) -> SerializableType:`

Return the eventually consistent data view.

#### `@classmethod compare_values(value1: SerializableType, value2: SerializableType) -> bool:`

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> LWWRegister:`

Apply an update and return self (monad pattern). Raises TypeError, ValueError,
or UsageError for invalid state_update.

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

#### `write(value: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Writes the new value to the register and returns an update_class (StateUpdate by
default). Requires a SerializableType writer id for tie breaking. Raises
TypeError for invalid value or writer.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
