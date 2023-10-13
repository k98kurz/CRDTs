# Causal Tree

The Causal Tree (`CausalTree`) is a CRDT that maintains an ordered list of items.
Items can be added to the beginning of the list or after a specific item already
in the list. Items can also be moved and deleted, leaving behind tombstones.

## Mathematics

The Causal Tree uses the `LWWMap` to encode a directed graph. Each item is
assigned a UUID, and links are created by referencing the UUID of a parent
item. It is possible to create cycles in this graph, which will remove all items
in the cycle from the views returned by `read` and `read_full`, but they will be
accessible via `read_excluded`.

When an item is deleted, rather than creating multiple updates that excise the
item and stitch the graph back together, the item is replaced with a tombstone,
and its UUID stays in the graph.

## Usage

To use the `CausalTree`, import it from the crdts library.

```python
from crdts import CausalTree

causaltree = CausalTree()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import CausalTree, ScalarClock

writer_id = 1
clock_uuid = b'12345 should be unique' # probably shared from another node
causaltree = CausalTree(clock=ScalarClock(uuid=clock_uuid))

# alternate instantiation
causaltree = CausalTree()
causaltree.clock.uuid = clock_uuid
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

Items can then be added to the CausalTree with the `put_first` and `put_after`
methods, and these items can then be moved by using the `move_item` method.

```python
update = causaltree.put_first('first item', writer_id)[0]
first_item = update.data[3]
causaltree.put_after('second item', writer_id, first_item.uuid)

assert causaltree.read() == ('first item', 'second item')
full_list = causaltree.read_full()
```

Alternately, the `ListProtocol` methods can be used for deletion:

```python
causaltree.append('something', writer_id)
index = causaltree.index('something')
causaltree.remove(index)
```

Note that items must meet the `packify.SerializableType` type alias to work properly:

`packify.interface.Packable | dict | list | set | tuple | int | float | decimal.Decimal | str | bytes | bytearray | None`

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization, as well as
comparisons between elements for deterministic ordering.

Additionally, it is possible that some items get excluded from the data views
returned by `read` and `read_full` due to being orphans or having circular
references (i.e. an item being its own ancestor/descendant). These can be
accessed using the `read_excluded` method.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import CausalTree

writer_id = 1
causaltree = CausalTree()
first = causaltree.put_first('first', writer_id)[0].data[3]
causaltree.put_after('second', writer_id, first.uuid)

# replicate
writer_id2 = 2
ct2 = CausalTree.unpack(causaltree.pack())

# make concurrent updates
second = causaltree.read_full()[1]
divergence_ts = causaltree.clock.read()-1
causaltree.put_after('third', writer_id, second.uuid)
ct2.put_after('alternate third', writer_id2, second.uuid)

# synchronize
history1 = causaltree.history(from_ts=divergence_ts)
history2 = ct2.history(from_ts=divergence_ts)
for update in history1:
    ct2.update(update)

for update in history2:
    causaltree.update(update)

# prove they have resynchronized and have the same state
assert causaltree.read() == ct2.read()
```

### Methods

Below is documentation for the methods generated automatically by autodox.

#### `__init__(positions: LWWMap = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize a CausalTree from an LWWMap of item positions and a shared clock.
Raises TypeError for invalid positions or clock.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CausalTree:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(/, *, inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

#### `read_full(/, *, inject: dict = {}) -> tuple[CTDataWrapper]:`

Return the full, eventually consistent list of items with tombstones and
complete CTDataWrappers rather than just the underlying values. Use this for
preparing deletion updates -- only a CTDataWrapper can be used for delete.

#### `read_excluded(/, *, inject: dict = {}) -> list[CTDataWrapper]:`

Returns a list of CTDataWrapper items that are excluded from the views returned
by read() and read_full() due to circular references (i.e. where an item is its
own descendant).

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CausalTree:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

#### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

#### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

#### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

#### `put(item: SerializableType, writer: SerializableType, uuid: bytes, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item after the parent. Raises TypeError on invalid item, writer, uuid, or
parent_uuid.

#### `put_after(item: SerializableType, writer: SerializableType, parent_uuid: bytes, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class that puts the item after the
parent item. Raises TypeError on invalid item, writer, or parent_uuid.

#### `put_first(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:`

Creates, applies, and returns at least one update_class (StateUpdate by default)
that puts the item as the first item. Any ties for first place will be resolved
by making the new item the parent of those other first items, and those
update_class instances will also be created, applied, and returned. Raises
TypeError on invalid item or writer.

#### `move_item(item: CTDataWrapper, writer: SerializableType, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
moves the item to after the new parent. Raises TypeError on invalid item,
writer, or parent_uuid.

#### `index(item: SerializableType, _start: int = 0, _stop: int = None) -> int:`

Returns the int index of the item in the list returned by read_full(). Raises
ValueError if the item is not present.

#### `append(item: SerializableType, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item to the end of the list returned by read(). Raises TypeError on
invalid item or writer.

#### `remove(index: int, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
removes the item at the index in the list returned by read(). Raises ValueError
if the index is out of bounds. Raises TypeError if index is not an int.

#### `delete(ctdw: CTDataWrapper, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item specified by ctdw. Raises TypeError or UsageError on invalid
ctdw or writer.

#### `calculate_cache(/, *, inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the cache
list.

#### `update_cache(item: CTDataWrapper, /, *, inject: dict = {}) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache. Raises TypeError on invalid item.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.
