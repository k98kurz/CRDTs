# Fractionally-Indexed Array

The fractionally-indexed array (`FIArray`) is a list CRDT that allows updates to
be issued that insert or remove items. Items can also be moved simply by putting
the item at the new location, overwriting the index associated with the item.

The `FIArray` uses the LWWMap as its underlying CRDT and adds the fractional
index logic on top.

## Mathematics

The state of the `FIArray` is composed of the following:
- `positions: LWWMap` - the `LWWMap` mapping items to indices
- `clock: ClockProtocol` - the clock used for synchronization
- `cache_full: list[FIAItemWrapper]` - the ordered list of wrapped items
- `cache: list[SerializableType]` - the ordered list of unwrapped items

The conflict-free merge semantics are coded in the `LWWMap` and its underlying
classes. The `FIArray` class has the following unique mathematical properties:

- Inserting at the beginning is done by averaging between 0 and the first item
(or 1 if the list is empty).
- Inserting at the end is done by averaging between 1 and the last item (or 0 if
the list is empty).
- Inserting between two items is done by averaging their indices.
- To avoid the small chance that two items will be inserted at the same location
by different nodes asynchronously, a small random offset is added.
- Deleting removes the item from the underlying `LWWMap`.
- Performance optimization for large lists is accomplished with a cache system
and the `bisect` algorithm for quickly finding the correct insertion point.

To avoid resorting the entire list on each read, a cache system is included.

## Usage

To use the FIArray in your code, import it from the crdts library.

```python
from crdts import FIArray

fia = FIArray()
```

To create a local representation of a shared instance, use a shared, unique
bytes value as the clock UUID:

```python
from crdts import ScalarClock

clock_uuid = b'12345 should be unique'
fia = FIArray(clock=ScalarClock(uuid=clock_uuuid))
```

Each instance instantiated with default values will have a clock with a UUID
(UUID4). This can then be shared across a network of nodes.

Items can then be added with `put`, `put_first`, `put_last`, `put_between`,
`put_after`, and `put_before`. Items can be moved with `move_item` and removed
with `delete`.

```python
update = fia.put_first('first item', writer_id)
first_item = update.data[3]
fia.put_after('second item', writer_id, first_item)

assert fia.read() == ('first item', 'second item')
full_list = fia.read_full()
```

Alternately, the `ListProtocol` methods can be used for simplicity:

```python
fia.append('something', writer_id)
index = fia.index('something')
fia.remove(index, writer_id)
```

The `append` method differs from the other `put_` methods in that it simply adds
a very small amount (1E-20) to the index of the last item in the list rather
than dividing the space between that last index and 1 evenly. This leaves enough
space between items for insertions between and reordering of items, but only
just. After a series of edits to the list, calling `fia.normalize_list(writer_id)`
will renormalize the indices. Both `normalize` and `normalize_list` create an
update for every item in the list, so they should only be called when the index
space is close to exhaustion from concentrated activity in one subset of the
index space, e.g. using `put_last` many times instead of `append`, or `put_first`
after an initial `append`.

Note that items must meet the `packify.SerializableType` type alias to work properly:

`packify.interface.Packable | dict | list | set | tuple | int | float | decimal.Decimal | str | bytes | bytearray | None`

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ScalarClock, FIArray

fia_node1 = FIArray()
writer_id1 = 1
fia_node2 = FIArray(clock=ScalarClock(uuid=fia_node1.clock.uuid))
writer_id2 = 2

def synchronize():
    if fia_node1.checksums() != fia_node2.checksums():
        for state_update in fia_node1.history():
            fia_node2.update(state_update)
        for state_update in fia_node2.history():
            fia_node1.update(state_update)

fia_node1.put_first('first', writer_id1)
last = fia_node1.put_last('last', writer_id1).data[3]
synchronize()

fia_node2.delete(last, 2)
first = fia_node2.read_full()[0]
fia_node2.put_after('new last', writer_id2, first)
synchronize()

fia_node1.put_last('actual new last', writer_id1)
fia_node2.put_before('before "new last"', writer_id2, fia_node2.read_full()[-1])
synchronize()

assert fia_node1.read_full() == fia_node2.read_full()

print(fia_node1.read())
```

### Methods

#### `__init__(positions: LWWMap = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize an FIArray from an LWWMap of item positions and a shared clock.
Raises TypeError for invalid positions or clock.

#### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

#### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> FIArray:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

#### `read(/, *, inject: dict = {}) -> tuple[Any]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

#### `read_full(/, *, inject: dict = {}) -> tuple[FIAItemWrapper]:`

Return the full, eventually consistent list of items without tombstones but with
complete FIAItemWrappers rather than the underlying SerializableType values. Use
the resulting FIAItemWrapper(s) for calling delete and move_item. (The
FIAItemWrapper containing a value put into the list will be index 3 of the
StateUpdate returned by a put method.)

#### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> FIArray:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.

#### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

#### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

#### `@classmethod index_between(first: Decimal, second: Decimal) -> Decimal:`

Return an index between first and second with a random offset.

#### `put(item: SerializableType, writer: SerializableType, index: Decimal, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at the index. The FIAItemWrapper will be at index 3 of the data
attribute of the returned update_class instance. Raises TypeError for invalid
item.

#### `put_between(item: SerializableType, writer: SerializableType, first: FIAItemWrapper, second: FIAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between first and second. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance. Raises
TypeError for invalid item.

#### `put_before(item: SerializableType, writer: SerializableType, other: FIAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item before the other item. The FIAItemWrapper will be at index 3 of the
data attribute of the returned update_class instance. Raises UsageError if other
does not already have a position. Raises TypeError for invalid item.

#### `put_after(item: SerializableType, writer: SerializableType, other: FIAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item after the other item. The FIAItemWrapper will be at index 3 of the data
attribute of the returned update_class instance. Raises UsageError if other does
not already have a position. Raises TypeError for invalid item.

#### `put_first(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between 0 and the first item. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance. Raises
UsageError if other does not already have a position. Raises TypeError for
invalid item.

#### `put_last(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between the last item and 1. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance. Raises
UsageError if other does not already have a position. Raises TypeError for
invalid item.

#### `move_item(item: FIAItemWrapper, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate, before: FIAItemWrapper = None, after: FIAItemWrapper = None, new_index: Decimal = None) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at the new index, or directly before the before, or directly after the
after, or halfway between before and after. The FIAItemWrapper will be at index
3 of the data attribute of the returned update_class instance. Raises UsageError
if one of new_index, before, or after is not set. Raises TypeError for invalid
item, writer, new_index, before, or after.

#### `normalize(writer: SerializableType, max_index: Decimal = 1.0, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:`

Evenly distribute the item indices. Returns tuple of update_class (StateUpdate
by default) that encode the index updates. Applies each update as it is
generated.

#### `normalize_list(writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:`

Calls normalize with a max_index calculated for use with the append method as
the primary mechanism for adding to the list. Returns tuple of update_class
(StateUpdate by default) that encode the index updates. Applies each update as
it is generated.

#### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

#### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

#### `index(item: SerializableType, _start: int = 0, _stop: int = None) -> int:`

Returns the int index of the item in the list returned by read(). Raises
ValueError if the item is not present.

#### `append(item: SerializableType, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item to the end of the list returned by read(). Raises TypeError for
invalid item.

#### `remove(index: int, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
removes the item at the index in the list returned by read(). Raise ValueError
if the index is out of bounds. Raises TypeError for invalid item or index.

#### `delete(item: FIAItemWrapper, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item. Index 3 of the data attribute of the returned update_class
instance will be the NoneWrapper tombstone. Raises TypeError for invalid item.

#### `calculate_cache(inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the
cache_full list. Resets the cache.

#### `update_cache(uuid: BytesWrapper, item: FIAItemWrapper | None, visible: bool, /, *, inject: dict = {}) -> None:`

Updates cache_full by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets cache. Raises TypeError for invalid item or visible.

#### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

#### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

#### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### Notes

- Any clock which implements the `ClockProtocol` interface can be used instead
of the bundled `ScalarClock`.
- Fractional index precision can and will be exhausted by sufficiently large
lists.


#### Performance Improvement

Commit 316354dea20442a0eaab49fa4cd891b0c57185ea included a substantial refactor
to bring the internal view building/caching mechanism into alignment with the
system built out for the RGA. Before the improvement, each time the underlying
data changed, the cache would be destroyed and require full recalculation upon
the next call to `read`. After the refactor, the cache updates by removing the
value if it is already in the cache, then finding the correct index for
inserting if it must be inserted using the bisect algorithm.

Performance was measured pre-improvement using the following benchmark code:

```python
from crdts import FIArray, StrWrapper
import time

def perf_benchmark(func: callable, n: int = 10000, args: list = [], kwargs: dict = {}):
    start = time.perf_counter()
    for _ in range(n):
        func(*args, **kwargs)
    end = time.perf_counter()
    return end - start

base_fia = FIArray()
for i in range(500):
    _ = base_fia.put_first(StrWrapper(str(i)), i)

for i in range(500, 1_000):
    _ = base_fia.put_last(StrWrapper(str(i)), i)

mid_point = base_fia.read()[len(base_fia.read())//2]
packed = base_fia.pack()

def test_large_list():
    unpacked = FIArray.unpack(packed)
    for i in range(1_000, 1_100):
        try:
            _ = unpacked.put_after(StrWrapper(str(i)), i, mid_point)
            _ = unpacked.read()
        except BaseException as e:
            print(f'failed on iteration {i}')
            print(f'{(mid_point in unpacked.read())=}')
            print(f'{(mid_point in unpacked.positions.read())=}')
            print(f'{unpacked.positions.read()[mid_point]=}')
            raise e

perf_benchmark(test_large_list, 100)
```

Performance was measured post-improvement by changing the benchmark code thus:

```python
...
mid_point = base_fia.read_full()[len(base_fia.read())//2]
...

def test_large_list():
    unpacked = FIArray.unpack(packed)
    for i in range(1_000, 1_100):
        try:
            _ = unpacked.put_after(StrWrapper(str(i)), i, mid_point)
            _ = unpacked.read()
        except BaseException as e:
            print(f'failed on iteration {i}')
            print(f'{(mid_point in unpacked.read_full())=}')
            print(f'{(mid_point in unpacked.positions.read())=}')
            print(f'{unpacked.positions.read()[mid_point]=}')
            raise e

perf_benchmark(test_large_list, 100)
```

##### Pre-improvement
###### Trials

- 167.22500710003078
- 162.18023559998255
- 174.73388590000104

###### Average

168.046376200005

##### Post-improvement
###### Trials

- 99.60765050002374
- 101.68870189995505
- 98.48197939997772

###### Average

99.9261105999855

###### Performance Difference

99.9261105999855 / 168.046376200005 = 0.59463...

40% reduction in benchmark time on average
