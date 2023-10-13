# crdts

## Classes

### `StateUpdate`

Default class for encoding delta states.

#### Annotations

- clock_uuid: bytes
- ts: SerializableType
- data: Hashable

#### Methods

##### `__init__(clock_uuid: bytes, ts: SerializableType, data: Hashable):`

##### `pack() -> bytes:`

Serialize a StateUpdate. Assumes that all types within update.data and update.ts
are packable by packify.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> StateUpdate:`

Deserialize a StateUpdate. Assumes that all types within update.data and
update.ts are either built-in types or packify.Packables accessible from the
inject dict.

### `ScalarClock`

Implements a Lamport logical scalar clock.

#### Annotations

- counter: int
- uuid: bytes
- default_ts: int

#### Methods

##### `__init__(counter: int = 1, uuid: bytes = <factory>, default_ts: int = 0):`

##### `read() -> int:`

Return the current timestamp.

##### `update(data: int) -> int:`

Update the clock and return the current time stamp. Raises TypeError for invalid
data.

##### `@staticmethod is_later(ts1: int, ts2: int) -> bool:`

Return True iff ts1 > ts2. Raises TypeError for invalid ts1 or ts2.

##### `@staticmethod are_concurrent(ts1: int, ts2: int) -> bool:`

Return True if not ts1 > ts2 and not ts2 > ts1. Raises TypeError for invalid ts1
or ts2.

##### `@staticmethod compare(ts1: int, ts2: int) -> int:`

Return 1 if ts1 is later than ts2; -1 if ts2 is later than ts1; and 0 if they
are concurrent/incomparable. Raises TypeError for invalid ts1 or ts2.

##### `pack() -> bytes:`

Packs the clock into bytes.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> ScalarClock:`

Unpacks a clock from bytes. Raises TypeError or ValueError for invalid data.

### `GSet`

Implements the Grow-only Set (GSet) CRDT.

#### Annotations

- members: set[SerializableType]
- clock: ClockProtocol
- metadata: dict[SerializableType, Any]
- listeners: list[Callable]

#### Methods

##### `__init__(members: set[SerializableType] = <factory>, clock: ClockProtocol = <factory>, metadata: dict[SerializableType, Any] = <factory>, listeners: list[Callable] = <factory>):`

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> GSet:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(inject: dict = {}) -> set[SerializableType]:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> GSet:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure. If from_ts and/or until_ts are supplied, only those updates
that are not outside of these temporal constraints will be included.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes. If from_ts and/ or until_ts are supplied, only those updates that are not
outside of these temporal constraints will be included.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `add(member: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Create, apply, and return a StateUpdate adding member to the set.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `Counter`

Implements the Counter CRDT.

#### Annotations

- counter: int
- clock: ClockProtocol
- listeners: list[Callable]

#### Methods

##### `__init__(counter: int = 0, clock: ClockProtocol = <factory>, listeners: list[Callable] = <factory>):`

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> Counter:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> int:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> Counter:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
on invalid state_update.clock_uuid or state_update.data.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `increase(amount: int = 1, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Increase the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network. Raises
TypeError or ValueError for invalid amount.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `ORSet`

Implements the Observed Removed Set (ORSet) CRDT. Comprised of two Sets with a
read method that removes the removed set members from the observed set.
Add-biased.

#### Annotations

- observed: set[SerializableType]
- observed_metadata: dict[SerializableType, StateUpdateProtocol]
- removed: set[SerializableType]
- removed_metadata: dict[SerializableType, StateUpdateProtocol]
- clock: ClockProtocol
- cache: Optional[tuple]
- listeners: list[Callable]

#### Methods

##### `__init__(observed: set[SerializableType] = <factory>, observed_metadata: dict[SerializableType, StateUpdateProtocol] = <factory>, removed: set[SerializableType] = <factory>, removed_metadata: dict[SerializableType, StateUpdateProtocol] = <factory>, clock: ClockProtocol = <factory>, cache: Optional[tuple] = None, listeners: list[Callable] = <factory>):`

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> ORSet:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> set[SerializableType]:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> ORSet:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `observe(member: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that adds
the given member to the observed set. The member will be in the data attribute
at index 1. Raises TypeError for invalid member (must be SerializableType that
is also Hashable).

##### `remove(member: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that adds
the given member to the removed set. Raises TypeError for invalid member (must
be SerializableType that is also Hashable).

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `PNCounter`

Implements the Positive Negative Counter (PNCounter) CRDT. Comprised of two
Counter CRDTs with a read method that subtracts the negative counter from the
positive counter.

#### Annotations

- positive: int
- negative: int
- clock: ClockProtocol
- listeners: list[Callable]

#### Methods

##### `__init__(positive: int = 0, negative: int = 0, clock: ClockProtocol = <factory>, listeners: list[Callable] = <factory>):`

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> PNCounter:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read() -> int:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol) -> PNCounter:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update, state_update.clock_uuid, or state_update.data.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `increase(amount: int = 1, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Increase the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network. Raises
TypeError or ValueError for invalid amount or update_class.

##### `decrease(amount: int = 1, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Decrease the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network. Raises
TypeError or ValueError for invalid amount or update_class.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `CounterSet`

A CRDT for computing a composite Counter. Use with multiple replicas where each
replica has a single counter_id.

#### Annotations

- clock: ClockProtocol
- counter_ids: GSet
- counters: dict[SerializableType, PNCounter]
- listeners: list[Callable]

#### Methods

##### `__init__(uuid: bytes = None, clock: ClockProtocol = None, counter_ids: GSet = None, counters: dict[SerializableType, PNCounter] = None, listeners: list[Callable] = None) -> None:`

Initialize a CounterSet from a uuid, a clock, a GSet, and a dict mapping names
to PNCounters (all parameters optional).

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CounterSet:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> int:`

Return the eventually consistent data view. Cannot be used for preparing remove
updates.

##### `read_full(/, *, inject: dict = {}) -> dict[SerializableType, int]:`

Return the full, eventually consistent dict mapping the counter ids to their int
states.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CounterSet:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[Any]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `increase(counter_id: Hashable = b'', amount: int = 1, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Increase the PNCounter with the given counter_id by the given amount. Returns
the update_class (StateUpdate by default) that should be propagated to the
network. Raises TypeError or ValueError on invalid amount or counter_id.

##### `decrease(counter_id: Hashable = b'', amount: int = 1, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Decrease the PNCounter with the given counter_id by the given amount. Returns
the update_class (StateUpdate by default) that should be propagated to the
network. Raises TypeError or ValueError on invalid amount or counter_id.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `FIArray`

Implements a fractionally-indexed array CRDT.

#### Annotations

- positions: LWWMap
- clock: ClockProtocol
- cache_full: list[FIAItemWrapper]
- cache: list[SerializableType]
- listeners: list[Callable]

#### Methods

##### `__init__(positions: LWWMap = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize an FIArray from an LWWMap of item positions and a shared clock.
Raises TypeError for invalid positions or clock.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> FIArray:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> tuple[Any]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

##### `read_full(/, *, inject: dict = {}) -> tuple[FIAItemWrapper]:`

Return the full, eventually consistent list of items without tombstones but with
complete FIAItemWrappers rather than the underlying SerializableType values. Use
the resulting FIAItemWrapper(s) for calling delete and move_item. (The
FIAItemWrapper containing a value put into the list will be index 3 of the
StateUpdate returned by a put method.)

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> FIArray:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

##### `@classmethod index_between(first: Decimal, second: Decimal) -> Decimal:`

Return an index between first and second with a random offset.

##### `put(item: SerializableType, writer: SerializableType, index: Decimal, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at the index. The FIAItemWrapper will be at index 3 of the data
attribute of the returned update_class instance. Raises TypeError for invalid
item.

##### `put_between(item: SerializableType, writer: SerializableType, first: FIAItemWrapper, second: FIAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between first and second. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance. Raises
TypeError for invalid item.

##### `put_before(item: SerializableType, writer: SerializableType, other: FIAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item before the other item. The FIAItemWrapper will be at index 3 of the
data attribute of the returned update_class instance. Raises UsageError if other
does not already have a position. Raises TypeError for invalid item.

##### `put_after(item: SerializableType, writer: SerializableType, other: FIAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item after the other item. The FIAItemWrapper will be at index 3 of the data
attribute of the returned update_class instance. Raises UsageError if other does
not already have a position. Raises TypeError for invalid item.

##### `put_first(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between 0 and the first item. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance. Raises
UsageError if other does not already have a position. Raises TypeError for
invalid item.

##### `put_last(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between the last item and 1. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance. Raises
UsageError if other does not already have a position. Raises TypeError for
invalid item.

##### `move_item(item: FIAItemWrapper, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate, before: FIAItemWrapper = None, after: FIAItemWrapper = None, new_index: Decimal = None) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at the new index, or directly before the before, or directly after the
after, or halfway between before and after. The FIAItemWrapper will be at index
3 of the data attribute of the returned update_class instance. Raises UsageError
if one of new_index, before, or after is not set. Raises TypeError for invalid
item, writer, new_index, before, or after.

##### `normalize(writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:`

Evenly distribute the item indices. Returns tuple of update_class (StateUpdate
by default) that encode the index updates. Does not apply the updates locally.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `index(item: SerializableType, _start: int = 0, _stop: int = None) -> int:`

Returns the int index of the item in the list returned by read(). Raises
ValueError if the item is not present.

##### `append(item: SerializableType, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item to the end of the list returned by read(). Raises TypeError for
invalid item.

##### `remove(index: int, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
removes the item at the index in the list returned by read(). Raise ValueError
if the index is out of bounds. Raises TypeError for invalid item or index.

##### `delete(item: FIAItemWrapper, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item. Index 3 of the data attribute of the returned update_class
instance will be the NoneWrapper tombstone. Raises TypeError for invalid item.

##### `calculate_cache(inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the
cache_full list. Resets the cache.

##### `update_cache(uuid: BytesWrapper, item: FIAItemWrapper | None, visible: bool, /, *, inject: dict = {}) -> None:`

Updates cache_full by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets cache. Raises TypeError for invalid item or visible.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `RGArray`

Implements the Replicated Growable Array CRDT. This uses the ORSet to handle
CRDT logic and provides a logical view over top of it.

#### Annotations

- items: ORSet
- clock: ClockProtocol
- cache_full: list[RGAItemWrapper]
- cache: tuple[Any]
- listeners: list[Callable]

#### Methods

##### `__init__(items: ORSet = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize an RGA from an ORSet of items and a shared clock. Raises TypeError
for invalid items or clock.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> RGArray:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

##### `read_full(/, *, inject: dict = {}) -> tuple[RGAItemWrapper]:`

Return the full, eventually consistent list of items without tombstones but with
complete RGAItemWrappers rather than the underlying values. Use this for
preparing deletion updates -- only a RGAItemWrapper can be used for delete.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> RGArray:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid amount or update_class.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying all
updates from divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `index(item: SerializableType, _start: int = 0, _stop: int = None) -> int:`

Returns the int index of the item in the list returned by read(). Raises
ValueError if the item is not present.

##### `append(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item to the end of the list returned by read(). The RGAItemWrapper
will be in the data attribute at index 1. Raises TypeError for invalid item,
writer, or update_class.

##### `remove(index: int, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
removes the item at the index in the list returned by read(). Raises ValueError
if the index is out of bounds or TypeError if index is not an int.

##### `delete(item: RGAItemWrapper, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the specified item. Raises TypeError for invalid item or update_class.

##### `calculate_cache() -> None:`

Reads the items from the underlying ORSet, orders them, then sets the cache_full
list. Resets the cache.

##### `update_cache(item: RGAItemWrapper, visible: bool) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache. Raises TypeError for invalid item or visible.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `LWWRegister`

Implements the Last Writer Wins Register CRDT.

#### Annotations

- name: SerializableType
- value: SerializableType
- clock: ClockProtocol
- last_update: Any
- last_writer: SerializableType
- listeners: list[Callable]

#### Methods

##### `__init__(name: SerializableType, value: SerializableType = None, clock: ClockProtocol = None, last_update: Any = None, last_writer: SerializableType = None, listeners: list[Callable] = None) -> None:`

Initialize an LWWRegister from a name, a value, and a shared clock. Raises
TypeError for invalid parameters.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWRegister:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> SerializableType:`

Return the eventually consistent data view.

##### `@classmethod compare_values(value1: SerializableType, value2: SerializableType) -> bool:`

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> LWWRegister:`

Apply an update and return self (monad pattern). Raises TypeError, ValueError,
or UsageError for invalid state_update.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `write(value: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Writes the new value to the register and returns an update_class (StateUpdate by
default). Requires a SerializableType writer id for tie breaking. Raises
TypeError for invalid value or writer.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `LWWMap`

Implements the Last Writer Wins Map CRDT.
https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-l-w-w-map/index.html

#### Annotations

- names: ORSet
- registers: dict[SerializableType, LWWRegister]
- clock: ClockProtocol
- listeners: list[Callable]

#### Methods

##### `__init__(names: ORSet = None, registers: dict = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize an LWWMap from an ORSet of names, a list of LWWRegisters, and a
shared clock. Raises TypeError or UsageError for invalid parameters.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWMap:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(inject: dict = {}) -> dict:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> LWWMap:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdateProtocols that will converge to the
underlying data. Useful for resynchronization by replaying updates from
divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `set(name: Hashable, value: SerializableType, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Extends the dict with name: value. Returns an update_class (StateUpdate by
default) that should be propagated to all nodes. Raises TypeError for invalid
name, value, or writer.

##### `unset(name: Hashable, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Removes the key name from the dict. Returns a StateUpdate. Raises TypeError for
invalid name or writer.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `MVRegister`

Implements the Multi-Value Register CRDT.

#### Annotations

- name: SerializableType
- values: list[SerializableType]
- clock: ClockProtocol
- last_update: Any
- listeners: list[Callable]

#### Methods

##### `__init__(name: SerializableType, values: list[SerializableType] = [], clock: ClockProtocol = None, last_update: Any = None, listeners: list[Callable] = None) -> None:`

Initialize an MVRegister instance from name, values, clock, and last_update (all
but the first are optional). Raises TypeError for invalid name, values, or
clock.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> MVRegister:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view.

##### `@classmethod compare_values(value1: SerializableType, value2: SerializableType) -> bool:`

Return True if value1 is greater than value2, else False.

##### `update(state_update: StateUpdateProtocol) -> MVRegister:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update, state_update.clock_uuid, or state_update.data.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `write(value: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Writes the new value to the register and returns an update_class (StateUpdate by
default). Raises TypeError for invalid value.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `MVMap`

Implements a Map CRDT using Multi-Value Registers.
https://concordant.gitlabpages.inria.fr/software/c-crdtlib/c-crdtlib/crdtlib.crdt/-m-v-map/index.html

#### Annotations

- names: ORSet
- registers: dict[SerializableType, MVRegister]
- clock: ClockProtocol
- listeners: list[Callable]

#### Methods

##### `__init__(names: ORSet = None, registers: dict = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize an MVMap from an ORSet of names, a list of MVRegisters, and a shared
clock. Raises TypeError or UsageError for invalid arguments.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> MVMap:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read() -> dict:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol) -> MVMap:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdateProtocols that will converge to the
underlying data. Useful for resynchronization by replaying updates from
divergent nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `set(name: SerializableType, value: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Extends the dict with name: value. Returns an update_class (StateUpdate by
default) that should be propagated to all nodes. Raises TypeError for invalid
name or value.

##### `unset(name: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Removes the key name from the dict. Returns a StateUpdate. Raises TypeError for
invalid name.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `CausalTree`

Implements a Causal Tree CRDT.

#### Annotations

- positions: LWWMap
- clock: ClockProtocol
- cache: list[CTDataWrapper]
- listeners: list[Callable]

#### Methods

##### `__init__(positions: LWWMap = None, clock: ClockProtocol = None, listeners: list[Callable] = None) -> None:`

Initialize a CausalTree from an LWWMap of item positions and a shared clock.
Raises TypeError for invalid positions or clock.

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string. Raises packify.UsageError on
failure.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CausalTree:`

Unpack the data bytes string into an instance. Raises packify.UsageError or
ValueError on failure.

##### `read(/, *, inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

##### `read_full(/, *, inject: dict = {}) -> tuple[CTDataWrapper]:`

Return the full, eventually consistent list of items with tombstones and
complete CTDataWrappers rather than just the underlying values. Use this for
preparing deletion updates -- only a CTDataWrapper can be used for delete.

##### `read_excluded(/, *, inject: dict = {}) -> list[CTDataWrapper]:`

Returns a list of CTDataWrapper items that are excluded from the views returned
by read() and read_full() due to circular references (i.e. where an item is its
own descendant).

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CausalTree:`

Apply an update and return self (monad pattern). Raises TypeError or ValueError
for invalid state_update.clock_uuid or state_update.data.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

##### `get_merkle_history(/, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization. Raises TypeError or
ValueError for invalid input.

##### `put(item: SerializableType, writer: SerializableType, uuid: bytes, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item after the parent. Raises TypeError on invalid item, writer, uuid, or
parent_uuid.

##### `put_after(item: SerializableType, writer: SerializableType, parent_uuid: bytes, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class that puts the item after the
parent item. Raises TypeError on invalid item, writer, or parent_uuid.

##### `put_first(item: SerializableType, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> tuple[StateUpdateProtocol]:`

Creates, applies, and returns at least one update_class (StateUpdate by default)
that puts the item as the first item. Any ties for first place will be resolved
by making the new item the parent of those other first items, and those
update_class instances will also be created, applied, and returned. Raises
TypeError on invalid item or writer.

##### `move_item(item: CTDataWrapper, writer: SerializableType, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
moves the item to after the new parent. Raises TypeError on invalid item,
writer, or parent_uuid.

##### `index(item: SerializableType, _start: int = 0, _stop: int = None) -> int:`

Returns the int index of the item in the list returned by read_full(). Raises
ValueError if the item is not present.

##### `append(item: SerializableType, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item to the end of the list returned by read(). Raises TypeError on
invalid item or writer.

##### `remove(index: int, writer: SerializableType, /, *, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
removes the item at the index in the list returned by read(). Raises ValueError
if the index is out of bounds. Raises TypeError if index is not an int.

##### `delete(ctdw: CTDataWrapper, writer: SerializableType, /, *, inject: dict = {}, update_class: Type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item specified by ctdw. Raises TypeError or UsageError on invalid
ctdw or writer.

##### `calculate_cache(/, *, inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the cache
list.

##### `update_cache(item: CTDataWrapper, /, *, inject: dict = {}) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache. Raises TypeError on invalid item.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `StateUpdateProtocol(Protocol)`

#### Annotations

- clock_uuid: bytes
- ts: Any
- data: Hashable

#### Methods

##### `__init__(clock_uuid: bytes, ts: Any, data: Hashable) -> None:`

Initialize the instance.

##### `pack() -> bytes:`

Pack the instance into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> StateUpdateProtocol:`

Unpack an instance from bytes.

### `ClockProtocol(Protocol)`

Duck typed Protocol showing what a clock must do.

#### Annotations

- uuid: bytes
- default_ts: SerializableType

#### Methods

##### `read(/, *, inject: dict = {}) -> SerializableType:`

Return the current timestamp.

##### `update(data: SerializableType = None) -> SerializableType:`

Update the clock and return the current time stamp.

##### `@staticmethod is_later(ts1: SerializableType, ts2: SerializableType) -> bool:`

Return True iff ts1 > ts2.

##### `@staticmethod are_concurrent(ts1: SerializableType, ts2: SerializableType) -> bool:`

Return True if not ts1 > ts2 and not ts2 > ts1.

##### `@staticmethod compare(ts1: SerializableType, ts2: SerializableType) -> int:`

Return 1 if ts1 is later than ts2; -1 if ts2 is later than ts1; and 0 if they
are concurrent/incomparable.

##### `pack() -> bytes:`

Pack the clock into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> ClockProtocol:`

Unpack a clock from bytes.

### `CRDTProtocol(Protocol)`

Duck typed Protocol showing what CRDTs must do.

#### Annotations

- clock: ClockProtocol

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CRDTProtocol:`

Unpack the data bytes string into an instance.

##### `read(/, *, inject: dict = {}) -> Any:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CRDTProtocol:`

Apply an update and return self (monad pattern). Should call
self.invoke_listeners after validating the state_update.

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[Any]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: Type[StateUpdateProtocol] = None, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

##### `get_merkle_history(update_class: Type[StateUpdateProtocol]) -> list[bytes, list[bytes], dict[bytes, bytes]]:`

Get a Merklized history for the StateUpdates of the form [root, [content_id for
update in self.history()], { content_id: packed for update in self.history()}]
where packed is the result of update.pack() and content_id is the sha256 of the
packed update.

##### `resolve_merkle_histories(history: list[bytes, list[bytes]]) -> list[bytes]:`

Accept a history of form [root, leaves] from another node. Return the leaves
that need to be resolved and merged for synchronization.

##### `add_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Adds a listener that is called on each update.

##### `remove_listener(listener: Callable[[StateUpdateProtocol], None]) -> None:`

Removes a listener if it was previously added.

##### `invoke_listeners(state_update: StateUpdateProtocol) -> None:`

Invokes all event listeners, passing them the state_update.

### `ListProtocol(Protocol)`

#### Methods

##### `index(_start: int = 0, _stop: int = -1) -> int:`

Returns the int index of the item in the list returned by read(). Should raise a
ValueError if the item is not present.

##### `append(update_class: Type[StateUpdateProtocol]) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class that appends the item to the end
of the list returned by read().

##### `remove(index: int, update_class: Type[StateUpdateProtocol]) -> tuple[StateUpdateProtocol]:`

Creates, applies, and returns an update_class that removes the item at the index
in the list returned by read(). Should raise ValueError if the index is out of
bounds.

### `DataWrapperProtocol(Protocol)`

Duck type protocol for values that can be written to a LWWRegister, included in
a GSet or ORSet, or be used as the key for a LWWMap. Can also be packed,
unpacked, and compared.

#### Annotations

- value: Any

#### Methods

##### `pack() -> bytes:`

Package value into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> DataWrapperProtocol:`

Unpack value from bytes.

### `BytesWrapper(StrWrapper)`

#### Annotations

- value: bytes

#### Methods

##### `__init__(value: bytes) -> None:`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> BytesWrapper:`

### `CTDataWrapper`

#### Annotations

- value: SerializableType
- uuid: bytes
- parent_uuid: bytes
- visible: bool

#### Methods

##### `__init__(value: SerializableType, uuid: bytes, parent_uuid: bytes, visible: bool = True) -> None:`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CTDataWrapper:`

### `DecimalWrapper(StrWrapper)`

#### Annotations

- value: Decimal

#### Methods

##### `__init__(value: Decimal) -> None:`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> DecimalWrapper:`

### `IntWrapper(DecimalWrapper)`

#### Annotations

- value: int

#### Methods

##### `__init__(value: int) -> None:`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> IntWrapper:`

### `NoneWrapper`

Implementation of DataWrapperProtocol for use in removing registers from the
LWWMap by setting them to a None value.

#### Annotations

- value: NoneType

#### Methods

##### `__init__(value: NoneType = None):`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> NoneWrapper:`

### `RGAItemWrapper(StrWrapper)`

#### Annotations

- value: SerializableType
- ts: SerializableType
- writer: SerializableType

#### Methods

##### `__init__(value: SerializableType, ts: SerializableType, writer: SerializableType) -> None:`

##### `pack() -> bytes:`

Pack instance to bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> RGAItemWrapper:`

### `StrWrapper`

StrWrapper(value: 'str')

#### Annotations

- value: str

#### Methods

##### `__init__(value: str):`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> StrWrapper:`


