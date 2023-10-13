from __future__ import annotations
from packify import SerializableType
from typing import Any, Callable, Hashable, Protocol, Type, runtime_checkable


@runtime_checkable
class ClockProtocol(Protocol):
    """Duck typed Protocol showing what a clock must do."""
    uuid: bytes
    default_ts: SerializableType

    def read(self, /, *, inject: dict = {}) -> SerializableType:
        """Return the current timestamp."""
        ...

    def update(self, data: SerializableType = None) -> SerializableType:
        """Update the clock and return the current time stamp."""
        ...

    @staticmethod
    def is_later(ts1: SerializableType, ts2: SerializableType) -> bool:
        """Return True iff ts1 > ts2."""
        ...

    @staticmethod
    def are_concurrent(ts1: SerializableType, ts2: SerializableType) -> bool:
        """Return True if not ts1 > ts2 and not ts2 > ts1."""
        ...

    @staticmethod
    def compare(ts1: SerializableType, ts2: SerializableType) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable.
        """
        ...

    def pack(self) -> bytes:
        """Pack the clock into bytes."""
        ...

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> ClockProtocol:
        """Unpack a clock from bytes."""
        ...


@runtime_checkable
class CRDTProtocol(Protocol):
    """Duck typed Protocol showing what CRDTs must do."""
    clock: ClockProtocol

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        ...

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> CRDTProtocol:
        """Unpack the data bytes string into an instance."""
        ...

    def read(self, /, *, inject: dict = {}) -> Any:
        """Return the eventually consistent data view."""
        ...

    def update(self, state_update: StateUpdateProtocol, /, *,
               inject: dict = {}) -> CRDTProtocol:
        """Apply an update and return self (monad pattern). Should call
            self.invoke_listeners after validating the state_update.
        """
        ...

    def checksums(self, /, *, from_ts: Any = None, until_ts: Any = None) -> tuple[Any]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        ...

    def history(self, /, *, from_ts: Any = None, until_ts: Any = None,
                update_class: Type[StateUpdateProtocol] = None) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        ...

    def get_merkle_history(self, /, *, update_class: Type[StateUpdateProtocol]
                           ) -> list[bytes, list[bytes], dict[bytes, bytes]]:
        """Get a Merklized history for the StateUpdates of the form
            [root, [content_id for update in self.history()], {
            content_id: packed for update in self.history()}] where
            packed is the result of update.pack() and content_id is the
            sha256 of the packed update.
        """
        ...

    def resolve_merkle_histories(self, history: list[bytes, list[bytes]]) -> list[bytes]:
        """Accept a history of form [root, leaves] from another node.
            Return the leaves that need to be resolved and merged for
            synchronization.
        """
        ...

    def add_listener(self, listener: Callable[[StateUpdateProtocol], None]) -> None:
        """Adds a listener that is called on each update."""
        ...

    def remove_listener(self, listener: Callable[[StateUpdateProtocol], None]) -> None:
        """Removes a listener if it was previously added."""
        ...

    def invoke_listeners(self, state_update: StateUpdateProtocol) -> None:
        """Invokes all event listeners, passing them the state_update."""
        ...


@runtime_checkable
class ListProtocol(Protocol):
    def index(self, item, _start: int = 0, _stop: int = -1) -> int:
        """Returns the int index of the item in the list returned by
            read(). Should raise a ValueError if the item is not
            present.
        """
        ...

    def append(self, item, writer, /, *, update_class: Type[StateUpdateProtocol]
               ) -> tuple[StateUpdateProtocol]:
        """Creates, applies, and returns a tuple of update_class objects
            that append the item to the end of the list returned by
            read().
        """
        ...

    def remove(self, index: int, writer, /, *, update_class: Type[StateUpdateProtocol]
               ) -> tuple[StateUpdateProtocol]:
        """Creates, applies, and returns a tuple of update_class objects
            that remove the item at the index in the list returned by
            read(). Should raise ValueError if the index is out of
            bounds.
        """
        ...


@runtime_checkable
class DataWrapperProtocol(Protocol):
    """Duck type protocol for values that can be written to a LWWRegister,
        included in a GSet or ORSet, or be used as the key for a LWWMap.
        Can also be packed, unpacked, and compared.
    """
    value: Any

    def __hash__(self) -> int:
        """Data type must be hashable."""
        ...

    def __eq__(self, other) -> bool:
        """Data type must be comparable."""
        ...

    def __ne__(self, other) -> bool:
        """Data type must be comparable."""
        ...

    def __gt__(self, other) -> bool:
        """Data type must be comparable."""
        ...

    def __ge__(self, other) -> bool:
        """Data type must be comparable."""
        ...

    def __lt__(self, other) -> bool:
        """Data type must be comparable."""
        ...

    def __le__(self, other) -> bool:
        """Data type must be comparable."""
        ...

    def pack(self) -> bytes:
        """Package value into bytes."""
        ...

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> DataWrapperProtocol:
        """Unpack value from bytes."""
        ...


@runtime_checkable
class StateUpdateProtocol(Protocol):
    clock_uuid: bytes
    ts: Any
    data: Hashable

    def __init__(self, /, *, clock_uuid: bytes, ts: Any, data: Hashable) -> None:
        """Initialize the instance."""
        ...

    def pack(self) -> bytes:
        """Pack the instance into bytes."""
        ...

    @classmethod
    def unpack(cls, data: bytes, /, *, inject: dict = {}) -> StateUpdateProtocol:
        """Unpack an instance from bytes."""
        ...
