# crdts

## Classes

### `StateUpdate`

#### Annotations

- clock_uuid: bytes
- ts: Any
- data: Hashable

#### Methods

##### `pack() -> bytes:`

Serialize a StateUpdate. Assumes that all types within update.data and update.ts
are either built-in types or PackableProtocols accessible from this scope.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> StateUpdate:`

Deserialize a StateUpdate. Assumes that all types within update.data and
update.ts are either built-in types or PackableProtocols accessible from this
scope.

### `ScalarClock`

#### Annotations

- counter: int
- uuid: bytes
- default_ts: int

#### Methods

##### `read() -> int:`

Return the current timestamp.

##### `update(data: int) -> int:`

Update the clock and return the current time stamp.

##### `@staticmethod is_later(ts1: int, ts2: int) -> bool:`

Return True iff ts1 > ts2.

##### `@staticmethod are_concurrent(ts1: int, ts2: int) -> bool:`

Return True if not ts1 > ts2 and not ts2 > ts1.

##### `@staticmethod compare(ts1: int, ts2: int) -> int:`

Return 1 if ts1 is later than ts2; -1 if ts2 is later than ts1; and 0 if they
are concurrent/incomparable.

##### `pack() -> bytes:`

Packs the clock into bytes.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> ScalarClock:`

Unpacks a clock from bytes.

##### `@classmethod wrap_ts(ts: int) -> IntWrapper:`

Wrap a timestamp in an IntWrapper.

### `GSet`

#### Annotations

- members: set[SerializableType]
- clock: ClockProtocol
- update_history: dict[SerializableType, StateUpdateProtocol]

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> GSet:`

Unpack the data bytes string into an instance.

##### `read(inject: dict = {}) -> set[SerializableType]:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> GSet:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure. If from_ts and/or until_ts are supplied, only those updates
that are not outside of these temporal constraints will be included.

##### `history(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes. If from_ts and/ or until_ts are supplied, only those updates that are not
outside of these temporal constraints will be included.

##### `add(member: SerializableType, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Create, apply, and return a StateUpdate adding member to the set.

### `Counter`

#### Annotations

- counter: int
- clock: ClockProtocol

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> Counter:`

Unpack the data bytes string into an instance.

##### `read(/, *, inject: dict = {}) -> int:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> Counter:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `increase(amount: int = 1, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Increase the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network.

### `ORSet`

#### Annotations

- observed: set
- observed_metadata: dict
- removed: set
- removed_metadata: dict
- clock: ClockProtocol
- cache: Optional[tuple]

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> ORSet:`

Unpack the data bytes string into an instance.

##### `read() -> set[SerializableType]:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol) -> ORSet:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `observe(member: SerializableType, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Adds the given member to the observed set.

##### `remove(member: SerializableType, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Adds the given member to the removed set.

### `PNCounter`

#### Annotations

- positive: int
- negative: int
- clock: ClockProtocol

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> PNCounter:`

Unpack the data bytes string into an instance.

##### `read() -> int:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol) -> PNCounter:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `increase(amount: int = 1, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Increase the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network.

##### `decrease(amount: int = 1, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Decrease the counter by the given amount (default 1). Returns the update_class
(StateUpdate by default) that should be propagated to the network.

### `FIArray`

#### Annotations

- positions: LWWMap
- clock: ClockProtocol
- cache_full: list[FIAItemWrapper]
- cache: list[SerializableType]

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> FIArray:`

Unpack the data bytes string into an instance.

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

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

##### `@classmethod index_between(first: Decimal, second: Decimal) -> Decimal:`

Return an index between first and second with a random offset.

##### `put(item: SerializableType, writer: int, index: Decimal, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at the index. The FIAItemWrapper will be at index 3 of the data
attribute of the returned update_class instance.

##### `put_between(item: SerializableType, writer: int, first: FIAItemWrapper, second: FIAItemWrapper, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between first and second. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance.

##### `put_before(item: SerializableType, writer: int, other: FIAItemWrapper, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item before the other item. The FIAItemWrapper will be at index 3 of the
data attribute of the returned update_class instance.

##### `put_after(item: SerializableType, writer: int, other: FIAItemWrapper, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item after the other item. The FIAItemWrapper will be at index 3 of the data
attribute of the returned update_class instance.

##### `put_first(item: SerializableType, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between 0 and the first item. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance.

##### `put_last(item: SerializableType, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at an index between the last item and 1. The FIAItemWrapper will be at
index 3 of the data attribute of the returned update_class instance.

##### `move_item(item: FIAItemWrapper, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, before: FIAItemWrapper = None, after: FIAItemWrapper = None, new_index: Decimal = None) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that puts
the item at the new index, or directly before the before, or directly after the
after, or halfway between before and after. The FIAItemWrapper will be at index
3 of the data attribute of the returned update_class instance.

##### `delete(item: FIAItemWrapper, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item. Index 3 of the data attribute of the returned update_class
instance will be the NoneWrapper tombstone.

##### `calculate_cache(inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the
cache_full list. Resets the cache.

##### `update_cache(uuid: BytesWrapper, item: FIAItemWrapper | NoneWrapper, visible: bool, /, *, inject: dict = {}) -> None:`

Updates cache_full by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets cache.

### `RGArray`

#### Annotations

- items: ORSet
- clock: ClockProtocol
- cache_full: list[RGAItemWrapper]
- cache: tuple[Any]

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> RGArray:`

Unpack the data bytes string into an instance.

##### `read() -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

##### `read_full() -> tuple[RGAItemWrapper]:`

Return the full, eventually consistent list of items without tombstones but with
complete RGAItemWrappers rather than the underlying values. Use this for
preparing deletion updates -- only a RGAItemWrapper can be used for delete.

##### `update(state_update: StateUpdateProtocol) -> RGArray:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying all
updates from divergent nodes.

##### `append(item: SerializableType, writer: int, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
appends the item.

##### `delete(item: RGAItemWrapper, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the specified item.

##### `calculate_cache() -> None:`

Reads the items from the underlying ORSet, orders them, then sets the cache_full
list. Resets the cache.

##### `update_cache(item: RGAItemWrapper, visible: bool) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache.

### `LWWRegister`

#### Annotations

- name: DataWrapperProtocol
- value: DataWrapperProtocol
- clock: ClockProtocol
- last_update: Any
- last_writer: int

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWRegister:`

Unpack the data bytes string into an instance.

##### `read(inject: dict = {}) -> DataWrapperProtocol:`

Return the eventually consistent data view.

##### `@classmethod compare_values(value1: DataWrapperProtocol, value2: DataWrapperProtocol) -> bool:`

##### `update(state_update: StateUpdateProtocol) -> LWWRegister:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of update_class (StateUpdate by default) that will
converge to the underlying data. Useful for resynchronization by replaying
updates from divergent nodes.

##### `write(value: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Writes the new value to the register and returns an update_class (StateUpdate by
default). Requires a writer int for tie breaking.

### `LWWMap`

#### Annotations

- names: ORSet
- registers: dict[DataWrapperProtocol, LWWRegister]
- clock: ClockProtocol

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> LWWMap:`

Unpack the data bytes string into an instance.

##### `read(inject: dict = {}) -> dict:`

Return the eventually consistent data view.

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> LWWMap:`

Apply an update and return self (monad pattern).

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdateProtocols that will converge to the
underlying data. Useful for resynchronization by replaying updates from
divergent nodes.

##### `extend(name: DataWrapperProtocol, value: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Extends the dict with name: value. Returns an update_class (StateUpdate by
default) that should be propagated to all nodes.

##### `unset(name: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Removes the key name from the dict. Returns a StateUpdate.

### `CausalTree`

#### Annotations

- positions: LWWMap
- clock: ClockProtocol
- cache: list[CTDataWrapper]

#### Methods

##### `pack() -> bytes:`

Pack the data and metadata into a bytes string.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CausalTree:`

Unpack the data bytes string into an instance.

##### `read(/, *, inject: dict = {}) -> tuple[SerializableType]:`

Return the eventually consistent data view. Cannot be used for preparing
deletion updates.

##### `read_full(/, *, inject: dict = {}) -> tuple[CTDataWrapper]:`

Return the full, eventually consistent list of items with tombstones and
complete DataWrapperProtocols rather than the underlying values. Use this for
preparing deletion updates -- only a DataWrapperProtocol can be used for delete.

##### `read_excluded(/, *, inject: dict = {}) -> list[CTDataWrapper]:`

Returns a list of CTDataWrapper items that are excluded from the views returned
by read() and read_full() due to circular references (i.e. where an item is its
own descendant).

##### `update(state_update: StateUpdateProtocol, /, *, inject: dict = {}) -> CausalTree:`

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[int]:`

Returns checksums for the underlying data to detect desynchronization due to
network partition.

##### `history(/, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

##### `put(item: SerializableType, writer: int, uuid: bytes, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns a update_class (StateUpdate by default) that puts
the item after the parent.

##### `put_after(item: SerializableType, writer: int, parent_uuid: bytes, /, *, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class that puts the item after the
parent item.

##### `put_first(item: DataWrapperProtocol, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> tuple[StateUpdateProtocol]:`

Creates, applies, and returns at least one update_class (StateUpdate by default)
that puts the item as the first item. Any ties for first place will be resolved
by making the new item the parent of those other first items, and those
update_class instances will also be created, applied, and returned.

##### `move_item(item: CTDataWrapper, writer: int, parent_uuid: bytes = b'', /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
moves the item to after the new parent.

##### `delete(ctdw: CTDataWrapper, writer: int, /, *, inject: dict = {}, update_class: type[StateUpdateProtocol] = <class 'crdts.stateupdate.StateUpdate'>) -> StateUpdateProtocol:`

Creates, applies, and returns an update_class (StateUpdate by default) that
deletes the item specified by ctdw.

##### `calculate_cache(/, *, inject: dict = {}) -> None:`

Reads the items from the underlying LWWMap, orders them, then sets the cache
list.

##### `update_cache(item: CTDataWrapper, /, *, inject: dict = {}) -> None:`

Updates the cache by finding the correct insertion index for the given item,
then inserting it there or removing it. Uses the bisect algorithm if necessary.
Resets the cache.

### `StateUpdateProtocol(Protocol)`

#### Annotations

- clock_uuid: bytes
- ts: Any
- data: Hashable

#### Methods

##### `pack() -> bytes:`

Pack the instance into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> StateUpdateProtocol:`

Unpack an instance from bytes.

### `ClockProtocol(Protocol)`

#### Annotations

- uuid: bytes
- default_ts: Any

#### Methods

##### `read(/, *, inject: dict = {}) -> Any:`

Return the current timestamp.

##### `update(data: Any = None) -> Any:`

Update the clock and return the current time stamp.

##### `@staticmethod is_later(ts1: Any, ts2: Any) -> bool:`

Return True iff ts1 > ts2.

##### `@staticmethod are_concurrent(ts1: Any, ts2: Any) -> bool:`

Return True if not ts1 > ts2 and not ts2 > ts1.

##### `@staticmethod compare(ts1: Any, ts2: Any) -> int:`

Return 1 if ts1 is later than ts2; -1 if ts2 is later than ts1; and 0 if they
are concurrent/incomparable.

##### `pack() -> bytes:`

Pack the clock into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> ClockProtocol:`

Unpack a clock from bytes.

##### `@classmethod wrap_ts(ts: Any, /, *, inject: dict = {}) -> DataWrapperProtocol:`

Wrap a timestamp in a data wrapper.

### `CRDTProtocol(Protocol)`

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

Apply an update and return self (monad pattern).

##### `checksums(from_ts: Any = None, until_ts: Any = None) -> tuple[Any]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(from_ts: Any, until_ts: Any = None, update_class: type[StateUpdateProtocol] = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

### `DataWrapperProtocol(Protocol)`

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

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> BytesWrapper:`

### `CTDataWrapper`

#### Annotations

- value: SerializableType
- uuid: bytes
- parent_uuid: bytes
- visible: bool

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> CTDataWrapper:`

### `DecimalWrapper(StrWrapper)`

#### Annotations

- value: Decimal

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> DecimalWrapper:`

### `IntWrapper(DecimalWrapper)`

#### Annotations

- value: int

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> IntWrapper:`

### `NoneWrapper`

#### Annotations

- value: NoneType

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> NoneWrapper:`

### `RGAItemWrapper(StrWrapper)`

#### Annotations

- value: DataWrapperProtocol
- ts: DataWrapperProtocol
- writer: int

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> RGAItemWrapper:`

### `StrWrapper`

#### Annotations

- value: str

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> StrWrapper:`

## Functions

### `serialize_part(data: Any) -> bytes:`

Serializes an instance of a PackableProtocol implementation or built-in type,
recursively calling itself as necessary.

### `deserialize_part(data: bytes, inject: dict = {}) -> Any:`

Deserializes an instance of a PackableProtocol implementation or built-in type,
recursively calling itself as necessary.


