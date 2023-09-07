# Causal Tree

The Causal Tree (CausalTree) is a CRDT that maintains an ordered list of items.
Items can be added to the beginning of the list or after a specific item already
in the list. Items can also be moved and deleted, leaving behind tombstones.

## Mathematics

The Causal Tree uses the LWWMap to encode a directed graph. Each item is
assigned a UUID, and links are created by referencing the UUID of a parent
item. It is possible to create cycles in this graph, which will remove all items
in the cycle from the views returned by `read` and `read_full`, but they will be
accessible via `read_excluded`.

When an item is deleted, rather than creating multiple updates that excise the
item and stich the graph back together, the item is replaced with a tombstone,
and its UUID stays in the graph.

## Usage

To use the CausalTree, import it from the crdts library.

```python
from crdts import CausalTree

causaltree = CausalTree()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

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
update = causaltree.put_first('first item', writer_id)
first_item = update.data[3]
causaltree.put_after('second item', writer_id, first_item.uuid)

assert causaltree.read() == ('first item', 'second item')
full_list = causaltree.read_full()
```

Note that items must meet the following type alias to work properly.

```python
SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType
```

Custom data types can be use if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

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

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

#### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CausalTree:`

Unpack the data bytes string into an instance.

#### `read(/, *, inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

#### `read_full(/, *, inject: dict = {}) -> tuple[CTDataWrapper]:`

Return the full, eventually consistent list of items with tombstones and
complete DataWrapperProtocols rather than the underlying values. Use this for
preparing deletion updates -- only a DataWrapperProtocol can be used for delete.

#### `read_excluded(/, *, inject: dict = {}) -> list[CTDataWrapper]:`

Returns a list of CTDataWrapper items that are excluded from the views returned
by read() and read_full() due to circular references (i.e. where an item is its
own descendant).

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CausalTree:`

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

#### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

#### `put(item: SerializableType, writer: int, uuid: bytes, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns a update_class (StateUpdate by default) that puts
the item after the parent.

#### `put_after(item: SerializableType, writer: int, parent_uuid: bytes, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class that puts the item after the
parent item.

#### `put_first(item: DataWrapperProtocol, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> tuple[StateUpdateProtocol]:`

Creates, applies, and returns at least one update_class (StateUpdate by default)
that puts the item as the first item. Any ties for first place will be resolved
by making the new item the parent of those other first items, and those
update_class instances will also be created, applied, and returned.

#### `move_item(item: CTDataWrapper, writer: int, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
moves the item to after the new parent.

#### `delete(ctdw: CTDataWrapper, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item specified by ctdw.

#### `calculate_cache(/, *, inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the cache
list.

#### `update_cache(item: CTDataWrapper, /, *, inject: dict = {}) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache.
