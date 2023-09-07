# Fractionally-Indexed Array

The fractionally-indexed array (FIA) is a list CRDT that allows updates to be
issued that insert or remove items. Items can also be moved simply by putting
the item at the new location, overwriting the index associated with the item.

The FIA uses the LWWMap as its underlying CRDT and adds the fractional index
logic on top.

## Mathematics

The state of the FIArray is composed of the following:
- `positions: LWWMap` - the LWWMap mapping items to indices
- `clock: ClockProtocol` - the clock used for synchronization
- `cache_full: list[DataWrapperProtocol]` - the ordered list of items
- `cache: list[Any]` - the ordered list of unwrapped items

The conflict-free merge semantics are coded in the LWWMap and its underlying
classes. The FIArray class has the following unique mathematical properties:

- Inserting at the beginning is done by averaging between 0 and the first item
(or 1 if the list is empty).
- Inserting at the end is done by averaging between 1 and the last item (or 0 if
the list is empty).
- Inserting between two items is done by averaging their indices.
- To avoid the small chance that two items will be inserted at the same location
by different nodes asynchronously, a small random offset is added.
- Deleting removes the item from the underlying LWWMap.
- Performance optimization for large lists is accomplished with a cache system
and the `bisect` algorithm for quickly finding the correct insertion point.

To avoid resorting the entire list on each read, a cache system is included.

## Usage

To use the FIArray in your code, import it from the crdts library as well as a
class implementing the `DataWrapperProtocol` interface. For example:

```python
from crdts import FIArray, StrWrapper

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

Note that items must meet the following type alias to work properly.

```python
SerializableType = DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType
```

Custom data types can be used if a class implementing the `DataWrapperProtocol`
is first used to wrap the item. This ensures reliable serialization.

### Usage Example

Below is an example of how to use this CRDT.

```python
from crdts import ScalarClock, FIArray, StrWrapper, BytesWrapper

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

fia_node1.put_first(StrWrapper('first'), writer_id1)
last = fia_node1.put_last(StrWrapper('last'), writer_id1).data[3]
synchronize()

fia_node2.delete(last, 2)
first = fia_node2.read_full()[0]
fia_node2.put_after(StrWrapper('new last'), writer_id2, first)
synchronize()

fia_node1.put_last(StrWrapper('actual new last'), writer_id1)
fia_node2.put_before(StrWrapper('before "new last"'), writer_id2, fia_node2.read_full()[-1])
synchronize()

assert fia_node1.read_full() == fia_node2.read_full()

print(fia_node1.read())
```

### Methods

#### `__init__`

```python
    def __init__(self, positions: LWWMap = None, clock: ClockProtocol = None) -> None:
```

This method initializes an instance. For example:

```python
fia1 = FIArray()
fia2 = FIArray(positions=LWWMap(), clock=SomeClockImplementation(uuid=b'some uuid'))
fia3 = FIArray(clock=SomeClockImplementation(uuid=b'some uuid'))
```

#### `read`

```python
    def read(self) -> tuple[Any]:
```

Return the eventually consistent data view. Note that values returned from this
cannot be used for preparing deletion updates; use the result of `read_full`
instead. For example:

```python
for item in fia.read():
    print(f'{type(item)=}, repr={item}')
```

#### `read_full`

```python
    def read_full(self) -> tuple[DataWrapperProtocol]:
```

Returns the full, eventually consistent list of items without tombstones but
with complete DataWrapperProtocols rather than the underlying values. Use this
for preparing deletion updates -- only a DataWrapperProtocol can be used for
`delete`. For example:

```python
for item in fia.read_full():
    print(f'{item.__class__.__name__}.value={item.value}')
```

#### `update`

```python
    def update(self, state_update: StateUpdateProtocol) -> FIArray:
```

Applies an update and returns self (in monad pattern). For example:

```python
state_update = fia1.put_first(StrWrapper('first'), 1)
fia2.update(state_update)
```

#### `checksums`

```python
    def checksums(self) -> tuple[int]:
```

Returns checksums for the underlying data to detect desynchronization due to
network partition. For example:

```python
if fia.checksums() != received_checksums:
    # out of sync with peer
    ...
else:
    # in sync with peer
    ...
```

#### `history`

```python
    def history(self) -> tuple[StateUpdate]:
```

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes. For example:

```python
send_history(fia.history())

for state_update in receive_history():
    fia.update(state_update)
```

#### `@classmethod index_offset`

```python
    @classmethod
    def index_offset(cls, index: Decimal) -> Decimal:
```

Adds a small random offset. For example:

```python
offset = FIArray.index_offset(Decimal('0.1'))
assert 0.11 <= offset <= 0.19
offset = FIArray.index_offset(Decimal('0.05'))
assert 0.051 <= offset <= 0.059
```

#### `@classmethod index_between`

```python
    @classmethod
    def index_between(cls, first: Decimal, second: Decimal) -> Decimal:
```

Return an index between first and second with a random offset. For example:

```python
offset = FIArray.index_between(Decimal(0), Decimal(1))
assert 0.51 <= offset <= 0.59
offset = FIArray.index_between(Decimal(0), Decimal('0.5'))
assert 0.251 <= offset <= 0.259
```

#### `@staticmethod least_significant_digit`

```python
    @staticmethod
    def least_significant_digit(number: Decimal) -> tuple[int, int]:
```

Returns the least significant digit and its place as an exponent of 10, e.g.
0.201 -> (1, -3). For example:

```python
lsd = FIArray.least_significant_digit(Decimal('0.123'))
assert lsd == (3, -3)
lsd = FIArray.least_significant_digit(Decimal('0.4321'))
assert lsd == (1, -4)
```

#### `put`

```python
    def put(self, item: DataWrapperProtocol, writer: int,
        index: Decimal) -> StateUpdate:
```

Creates, applies, and returns a StateUpdate that puts the item at the index. For
example:

```python
state_update = fia_node_99.put(StrWrapper('example'), 99, Decimal('0.12345'))
assert fia_node_99.read() == fia_node_99.update(state_update).read()
```

#### `put_between`

```python
    def put_between(self, item: DataWrapperProtocol, writer: int,
        first: DataWrapperProtocol, second: DataWrapperProtocol) -> StateUpdate:
```

Creates, applies, and returns a StateUpdate that puts the item at an index
between first and second. For example:

```python
fia = FIArray()
fia.put(StrWrapper('first'), 1, Decimal('0.1'))
fia.put(StrWrapper('third'), 1, Decimal('0.9'))
fia.put_between(StrWrapper('second'), 1, StrWrapper('first'), StrWrapper('third'))
assert fia.read() == ('first', 'second', 'third')
```

#### `put_before`

```python
    def put_before(self, item: DataWrapperProtocol, writer: int,
        other: DataWrapperProtocol) -> StateUpdate:
```

Creates, applies, and returns a StateUpdate that puts the item before the other
item. For example:

```python
fia = FIArray()
fia.put(StrWrapper('item1'), 1, Decimal('0.5'))
fia.put_before(StrWrapper('item2'), 1, StrWrapper('item1'))
assert fia.read() == ('item2', 'item1')
```

#### `put_after`

```python
    def put_after(self, item: DataWrapperProtocol, writer: int,
        other: DataWrapperProtocol) -> StateUpdate:
```
Creates, applies, and returns a StateUpdate that puts the item after the other
item. For example:

```python
fia = FIArray()
fia.put(StrWrapper('item1'), 1, Decimal('0.5'))
fia.put_after(StrWrapper('item2'), 1, StrWrapper('item1'))
assert fia.read() == ('item1', 'item2')
```

#### `put_first`

```python
    def put_first(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
```

Creates, applies, and returns a StateUpdate that puts the item at an index
between 0 and the first item. For example:

```python
fia = FIArray()
fia.put_first(StrWrapper('item3'), 1)
fia.put_first(StrWrapper('item2'), 1)
fia.put_first(StrWrapper('item1'), 1)
assert fia.read() == ('item1', 'item2', 'item3')
```

#### `put_last`

```python
    def put_last(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
```

Creates, applies, and returns a StateUpdate that puts the item at an index
between the last item and 1. For example:

```python
fia = FIArray()
fia.put_last(StrWrapper('item1'), 1)
fia.put_last(StrWrapper('item2'), 1)
fia.put_last(StrWrapper('item3'), 1)
assert fia.read() == ('item1', 'item2', 'item3')
```

#### `delete`

```python
    def delete(self, item: DataWrapperProtocol, writer: int) -> StateUpdate:
```

Creates, applies, and returns a StateUpdate that deletes the item. For example:

```python
fia = FIArray()
fia.put_first(StrWrapper('item1'), 1)
fia.put_first(StrWrapper('item2'), 1)
fia.delete(StrWrapper('item1'), 1)
assert fia.read() == ('item2',)
```

#### `pack`

```python
    def pack(self) -> bytes:
```

Serializes an instance to bytes for storage or transmission.

#### `@classmethod unpack`

```python
    @classmethod
    def unpack(cls, data: bytes) -> FIArray:
```

Deserializes an instance from bytes.

#### `calculate_cache`

```python
    def calculate_cache(self) -> None:
```

Reads the items from the underlying LWWMap, orders them, then sets the
cache_full list. Resets the cache. Used internally for performance optimization.

#### `update_cache`

```python
    def update_cache(self, item: DataWrapperProtocol, visible: bool) -> None:
```

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache. Used internally for performance optimization.

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
