# crdts.interfaces

## Classes

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

##### `__hash__() -> int:`

Data type must be hashable.

##### `__eq__() -> bool:`

Data type must be comparable.

##### `__ne__() -> bool:`

Data type must be comparable.

##### `__gt__() -> bool:`

Data type must be comparable.

##### `__ge__() -> bool:`

Data type must be comparable.

##### `__lt__() -> bool:`

Data type must be comparable.

##### `__le__() -> bool:`

Data type must be comparable.

##### `pack() -> bytes:`

Package value into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> DataWrapperProtocol:`

Unpack value from bytes.

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


