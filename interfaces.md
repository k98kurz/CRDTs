# crdts.interfaces

## Classes

### `Decimal`

### `PackableProtocol(Protocol)`

#### Methods

##### `pack() -> bytes:`

Packs the instance into bytes.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> PackableProtocol:`

Unpacks an instance from bytes. Must accept dependency injection to unpack other
Packable types.

##### `_proto_hook():`

##### `_no_init_or_replace_init():`

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

##### `_proto_hook():`

##### `_no_init_or_replace_init():`

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

##### `checksums(/, *, until_ts: Any = None, from_ts: Any = None) -> tuple[Any]:`

Returns any checksums for the underlying data to detect desynchronization due to
message failure.

##### `history(/, *, update_class: type[StateUpdateProtocol] = None, until_ts: Any = None, from_ts: Any = None) -> tuple[StateUpdateProtocol]:`

Returns a concise history of StateUpdates that will converge to the underlying
data. Useful for resynchronization by replaying all updates from divergent
nodes.

##### `_proto_hook():`

##### `_no_init_or_replace_init():`

### `DataWrapperProtocol(Protocol)`

#### Annotations

- value: Any

#### Methods

##### `pack() -> bytes:`

Package value into bytes.

##### `@classmethod unpack(data: bytes, /, *, inject: dict = {}) -> DataWrapperProtocol:`

Unpack value from bytes.

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

##### `_proto_hook():`

##### `_no_init_or_replace_init():`

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

##### `__init__(clock_uuid: bytes, ts: Any, data: Hashable) -> None:`

Initialize the instance.

##### `_proto_hook():`


