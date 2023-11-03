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
from crdts import LWWMap

writer_id = 1
lwwmap = LWWMap()
lwwmap.set('key', 'value', writer_id)
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

Key-value pairs can then be set and unset with the corresponding methods:

```python
writer_id = 1
lwwmap.set('key', 'value', writer_id)
lwwmap.unset('key', writer_id)
```

Note that names and values must meet the `packify.SerializableType` type alias
to work properly:

`packify.interface.Packable | dict | list | set | tuple | int | float | decimal.Decimal | str | bytes | bytearray | None`

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import LWWMap

writer_id = 1
lwwmap = LWWMap()
lwwmap.set('key1', 'value', writer_id)
lwwmap.set('key2', 420, writer_id)

# create a replica
writer_id = 2
lwwmap2 = LWWMap()
lwwmap2.clock.uuid = lwwmap.clock.uuid

# make a concurrent update
lwwmap2.set(69, 'nice', writer_id)
lwwmap2.unset('key1', writer_id)

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

#### `__init__(names: ORSet = None, registers: dict = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize an LWWMap from an ORSet of names, a dict mapping names to
LWWRegisters, and a shared clock. Raises TypeError or UsageError for invalid
parameters.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWMap:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(inject: dict = {}) -> dict:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> LWWMap:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdateProtocols that will converge to the
underlying data. Useful for resynchronization by replaying updates from
divergent nodes.

#### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

#### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

#### `set(name: Hashable, value: SerializableType, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Extends the dict with name: value. Returns an update_class (StateUpdate by
default) that should be propagated to all nodes. Raises TypeError for invalid
name, value, or writer.

#### `unset(name: Hashable, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Removes the key name from the dict. Returns a StateUpdate. Raises TypeError for
invalid name or writer.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
