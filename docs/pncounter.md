# Positive-Negative Counter

The Positive-Negative Counter (`PNCounter`) is a CRDT that tracks an integer
that can be increased and decreased. It does this by effectively tracking 2
Counters and subtracting one from the other. Like the Counter, this is fairly
limited and useful primarily for composition into more useful CRDTs -- it does
not track enough state to add concurrent increases as they create identical
delta states.

## Usage

To use the `PNCounter`, import it from the crdts library and instantiate.

```python
from crdts import PNCounter

pnc = PNCounter()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import PNCounter, ScalarClock

clock_uuid = b'12345 should be unique' # probably shared from another node
pnc = PNCounter(clock=ScalarClock(uuid=clock_uuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

The counter can then be increased or decreased by an arbitrary amount (1 by default):

```python
pnc.increase()
pnc.increase(3)
pnc.decrease()
pnc.decrease(2)
```

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import PNCounter

# instantiate and update
pnc1 = PNCounter()
pnc1.increase()
pnc1.increase()
pnc1.decrease()
pnc1.increase()

# simulate a replica
pnc2 = PNCounter()
pnc2.clock.uuid = pnc1.clock.uuid

# synchronize
for update in pnc1.history():
    pnc2.update(update)

# prove they have the same state
assert pnc1.read() == pnc2.read()
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `__init__(positive: int = 0, negative: int = 0, clock: ClockProtocol = <factory>, listeners: list[Callable] = <factory>):`

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> PNCounter:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read() -> int:`

Return the eventually consistent data view.

#### `update(state_update: StateUpdateProtocol) -> PNCounter:`

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

#### `increase(amount: int = 1, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Increase the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network. Raises
TypeError or ValueError for invalid amount or update_class.

#### `decrease(amount: int = 1, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Decrease the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network. Raises
TypeError or ValueError for invalid amount or update_class.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
