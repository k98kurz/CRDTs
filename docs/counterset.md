# Grow-only Positive-Negative Counter Set

This is a composite CRDT of a `GSet` containing counter IDs and the
corresponding `PNCounter`s. It provides a way for many replicas to increment and
decrement a counter that is the sum of a `PNCounter` for each replica.

## Mathematics

The mathematics are identical to those of the `GSet` and the `PNCounter` except
that the state of the `CounterSet` is the sum of the states of the `PNCounter`s.
See the documentation for the
[GSet](https://github.com/k98kurz/CRDTs/blob/master/docs/gset.md) and the
[PNCounter](https://github.com/k98kurz/CRDTs/blob/master/docs/pncounter.md) for
more details.

## Usage

To use the `CounterSet`, import it from the crdts library.

```python
from crdts import CounterSet

cset = CounterSet()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
cset = CounterSet(clock=ScalarClock(uuid=clock_uuid))

# alternately
cset = CounterSet()
cset.clock.uuid = clock_uuid
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

The Counter Set can then be increased and decreased by using the key for a
constituent `PNCounter`:

```python
cset.increase("replica1", 420)
cset.decrease("replica2", 69)
```

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import CounterSet, StateUpdate

cset1 = CounterSet()
cset1.increase("replica1")
cset1.increase("replica1", 420)

view = cset1.read() # should be 2

# simulate a replica
cset2 = CounterSet.unpack(cset1.pack())

# make concurrent updates
cset1.decrease("replica1", 69)
cset2.increase(b"replica2")
cset2.increase(b"replica2")

# resynchronize replica1 using merklized history feature
history = cset2.get_merkle_history()
diff1 = cset1.resolve_merkle_histories(history)
packed_updates: dict = history[2]

for update_id in diff1:
    cset1.update(StateUpdate.unpack(packed_updates[update_id]))

# resynchronize replica2 using non-merklized history system
history = cset1.history()
for update in history:
    cset2.update(update)

# prove they have synchronized and have the same state
assert cset1.read() == cset2.read()
assert cset1.get_merkle_history()[0] == cset2.get_merkle_history()[0]

# cset1.read() will be 354
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `__init__(uuid: bytes = None, clock: ClockProtocol = None, counter_ids: GSet = None, counters: dict[SerializableType, PNCounter] = None, listeners: list[Callable] = None) -> None:`

Initialize a CounterSet from a uuid, a clock, a GSet, and a dict mapping names
to PNCounters (all parameters optional).

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CounterSet:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(/, *, inject: dict = {}) -> int:`

Return the eventually consistent data view. Cannot be used for preparing remove
updates.

#### `read_full(/, *, inject: dict = {}) -> dict[SerializableType, int]:`

Return the full, eventually consistent dict mapping the counter ids to their int
states.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CounterSet:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

#### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[Any]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

#### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

#### `increase(counter_id: Hashable = b'', amount: int = 1, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Increase the PNCounter with the given counter_id by the given amount. Returns
the update_class (StateUpdate by default) that should be propagated to the
network. Raises TypeError or ValueError on invalid amount or counter_id.

#### `decrease(counter_id: Hashable = b'', amount: int = 1, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Decrease the PNCounter with the given counter_id by the given amount. Returns
the update_class (StateUpdate by default) that should be propagated to the
network. Raises TypeError or ValueError on invalid amount or counter_id.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
