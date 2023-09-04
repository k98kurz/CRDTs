# Last-Writer-Wins Register

The Last-Writer-Wins Register (LWWRegister) is a CRDT that tracks a single named
register. Each subsequent write to the register overwrites the value stored in
it, and concurrent writes are handled by a tie-breaker process using the writer
id integer and then value itself if necessary.

## Mathematics

The mutable state of the LWWRegister is composed of the following:
- `value: DataWrapperProtocol` - the current value at the local replica
- `clock: ClockProtocol` - the clock used for synchronization
- `last_update: Any` - the timestamp of the last update
- `last_writer: int` - the ID of the source of the most recent write/overwrite
of the `value`

The mathematics of the LWWRegister are simple: given two concurrent updates, the
resultant `value` will be determined by the update with the highest writer ID;
given two concurrent updates with identical writer ID, the resultant `value`
will be determined by which value has the higher byte value when serialized.

## Usage

To use the LWWRegister, import it from the crdts library as well as at least one
class implementing the `DataWrapperProtocol` interface. For example:

```python
from crdts import LWWRegister, StrWrapper
```

To instantiate a new LWWRegister use the following:

```python
lwwr = LWWRegister(name=StrWrapper('some name'))
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
name = StrWrapper('some name')
name = LWWRegister(name=name, clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, inject: dict) -> LWWRegister:`

Unpack the data bytes string into an instance.

#### `read() -> DataWrapperProtocol:`

Return the eventually consistent data view.

#### `@classmethod compare_values(value1: DataWrapperProtocol, value2: DataWrapperProtocol) -> bool:`

#### `update(state_update: StateUpdateProtocol) -> LWWRegister:`

Apply an update and return self (monad pattern).

#### `checksums(from_ts: Any, until_ts: Any) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(from_ts: Any, until_ts: Any, update_class: type[StateUpdateProtocol]) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

#### `write(value: DataWrapperProtocol, writer: int, update_class: type[StateUpdateProtocol]) -> StateUpdateProtocol:`

Writes the new value to the register and returns an update_class (StateUpdate by
default). Requires a writer int for tie breaking.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ScalarClock, LWWRegister, StrWrapper, IntWrapper

lwwr = LWWRegister(name=StrWrapper('some name'))
lwwr.write(StrWrapper('some value'))

view = lwwr.read() # should be StrWrapper("some value")

# updates to send to a replica
updates = lwwr.history()

# merge updates received from a replica
for update in updates:
    lwwr.update(update)
```