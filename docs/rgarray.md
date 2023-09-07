# Replicated Growable Array

The Replicated Growable Array (`RGArray`) is a CRDT that tracks a simple list.
Items can be added or removed from the list.

## Mathematics

The `RGArray` uses an ORSet under the hood for tracking additions and removals.
When an item is appended, it is wrapped in a `RGAItemWrapper` which includes the
timestamp and writer id. This `RGAItemWrapper` is then observed by the ORSet.
Deletions work by putting a `RGAItemWrapper` into the removed set of the ORSet.

The `RGArray` does not allow moving/reindexing items.

Note that it is technically possible to undelete items from the list at their
original index, but this is not currently implemented -- such an operation would
have to be done directly on the underlying ORSet.

Deterministic ordering is done very simply: items are ordered first by timestamp,
then ties are broken using the writer id, then any remaining ties are broken by
comparing the serialized item values.

## Usage

To use the `RGArray`, import it from the crdts library.

```python
from crdts import RGArray

rga = RGArray()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import RGArray, ScalarClock

writer_id = 1
clock_uuid = b'12345 should be unique' # probably shared from another node
rga = RGArray(clock=ScalarClock(uuid=clock_uuid))

# alternately instantiate and then set the clock uuid
rga = RGArray()
rga.clock.uuid = clock_uuid
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

Items can then be added to the RGArray with the `append` method or deleted with
the `delete` method. Note that the `delete` method requires the `RGAItemWrapper`
instance rather than the raw value.

```python
rgaitem = rga.append('some item', writer_id).data[1]
rga.delete(rgaitem)

rga.append('some other item', writer_id)
rgaitem = rga.read_full()[0]
rga.delete(rgaitem)
```

Note that items must meet the following type alias to work properly with
`append`.

```python
SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType
```

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import RGArray

writer_id = 1
rga = RGArray()
first = rga.append('first', writer_id).data[1]
rga.append('second', writer_id)

# replicate
writer_id2 = 2
rga2 = RGArray.unpack(rga.pack())

# make concurrent updates
divergence_ts = rga.clock.read()-1
rga.delete(first)
rga2.append('third', writer_id2)

# synchronize
history1 = rga.history(from_ts=divergence_ts)
history2 = rga2.history(from_ts=divergence_ts)
for update in history1:
    rga2.update(update)

for update in history2:
    rga.update(update)

# prove they have resynchronized and have the same state
assert rga.read() == rga2.read()
```

### Properties

- items: ORSet
- clock: ClockProtocol
- cache_full: list[RGAItemWrapper]
- cache: tuple[Any]

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, inject: dict = {}) -> RGArray:`

Unpack the data bytes string into an instance.

#### `read(/, *, inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

#### `read_full(/, *, inject: dict = {}) -> tuple[RGAItemWrapper]:`

Return the full, eventually consistent list of items without tombstones but with
complete RGAItemWrappers rather than the underlying values. Use this for
preparing deletion updates -- only a RGAItemWrapper can be used for delete.

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> RGArray:`

Apply an update and return self (monad pattern).

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

#### `history(/, *, update_class: type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying all
updates from divergent nodes.

#### `append(item: SerializableType, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item. The RGAItemWrapper will be in the data attribute at index 1.

#### `delete(item: RGAItemWrapper, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the specified item.

#### `calculate_cache() -> None:`

Reads the items from the underlying ORSet, orders them, then sets the cache_full
list. Resets the cache.

#### `update_cache(item: RGAItemWrapper, visible: bool) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache.

#### `__init__(items: ORSet = None, clock: ClockProtocol = None) -> None:`

Initialize an RGA from an ORSet of items and a shared clock.
