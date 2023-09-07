# Counter

The `Counter` is a CRDT that tracks a positive integer that only increases. Note
that this is a fairly limited CRDT useful primarily for composition into more
useful CRDTs, e.g. a multi-replica counter.

## Usage

To use the `Counter`, import it from the crdts library and instantiate.

```python
from crdts import Counter

counter = Counter()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import Counter, ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
counter = Counter(clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> Counter:`

Unpack the data bytes string into an instance.

#### `read(/, *, inject: dict = {}) -> int:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> Counter:`

Apply an update and return self (monad pattern).

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

#### `increase(amount: int = 1, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Increase the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network.

#### `__init__(counter: int = 0, clock: ClockProtocol = <factory>):`

#### `__repr__():`

#### `__eq__():`

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import Counter

# create a Counter and increment a few times
counter = Counter()
counter.increase()
counter.increase()

# simulate replica
counter2 = Counter()
counter2.clock.uuid = counter.clock.uuid

# synchronize
for update in counter.history():
    counter2.update(update)

# prove they have the same state
assert counter.read() == counter2.read()
```