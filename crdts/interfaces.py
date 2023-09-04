from __future__ import annotations
from typing import Any, Hashable, Protocol, runtime_checkable


@runtime_checkable
class PackableProtocol(Protocol):
    def pack(self) -> bytes:
        """Packs the instance into bytes."""
        ...

    @classmethod
    def unpack(cls, data: bytes) -> PackableProtocol:
        """Unpacks an instance from bytes."""
        ...


@runtime_checkable
class ClockProtocol(Protocol):
    """Duck typed Protocol showing what a clock must do."""
    uuid: bytes
    default_ts: Any

    def read(self) -> Any:
        """Return the current timestamp."""
        ...

    def update(self, data: Any = None) -> Any:
        """Update the clock and return the current time stamp."""
        ...

    @staticmethod
    def is_later(ts1: Any, ts2: Any) -> bool:
        """Return True iff ts1 > ts2."""
        ...

    @staticmethod
    def are_concurrent(ts1: Any, ts2: Any) -> bool:
        """Return True if not ts1 > ts2 and not ts2 > ts1."""
        ...

    @staticmethod
    def compare(ts1: Any, ts2: Any) -> int:
        """Return 1 if ts1 is later than ts2; -1 if ts2 is later than
            ts1; and 0 if they are concurrent/incomparable.
        """
        ...

    def pack(self) -> bytes:
        """Pack the clock into bytes."""
        ...

    @classmethod
    def unpack(cls, data: bytes) -> ClockProtocol:
        """Unpack a clock from bytes."""
        ...

    @classmethod
    def wrap_ts(cls, ts: Any) -> DataWrapperProtocol:
        """Wrap a timestamp in a data wrapper."""
        ...


@runtime_checkable
class CRDTProtocol(Protocol):
    """Duck typed Protocol showing what CRDTs must do."""
    clock: ClockProtocol

    def pack(self) -> bytes:
        """Pack the data and metadata into a bytes string."""
        ...

    @classmethod
    def unpack(cls, data: bytes) -> CRDTProtocol:
        """Unpack the data bytes string into an instance."""
        ...

    def read(self) -> Any:
        """Return the eventually consistent data view."""
        ...

    def update(self, state_update: StateUpdateProtocol) -> CRDTProtocol:
        """Apply an update and return self (monad pattern)."""
        ...

    def checksums(self) -> tuple[Any]:
        """Returns any checksums for the underlying data to detect
            desynchronization due to message failure.
        """
        ...

    def history(self, update_class: type[StateUpdateProtocol]) -> tuple[StateUpdateProtocol]:
        """Returns a concise history of StateUpdates that will converge
            to the underlying data. Useful for resynchronization by
            replaying all updates from divergent nodes.
        """
        ...


@runtime_checkable
class DataWrapperProtocol(Protocol):
    """Duck type protocol for values that can be written to a LWWRegister,
        included in a GSet or ORSet, or be used as the key for a LWWMap.
    """
    value: Any

    def __hash__(self) -> int:
        """Data type must be hashable."""
        ...

    def __eq__(self, other) -> bool:
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
    def unpack(cls, data: bytes, inject: dict = {}) -> DataWrapperProtocol:
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
    def unpack(cls, data: bytes) -> StateUpdateProtocol:
        """Unpack an instance from bytes."""
        ...
