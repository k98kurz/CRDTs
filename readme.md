# CRDTs

This package implements several CRDTs in a hopefully easy-to-use way.

## Overview

This package includes several Conflict-free Replicated Data Types. See
[Verifying Strong Eventual Consistency in Distributed Systems by Gomes,
Kleppmann, Mulligan, and Beresford](https://doi.org/10.1145/3133933) for more
details. This package includes the following CRDTs:
- Grow-only Set
- Counter
- Observed-Removed Set
- Positive-Negative Counter
- Fractionally-Indexed Array
- Replicated Growable Array
- Last-Writer-Wins Register
- Last-Writer-Wins Map

These are implemented as delta-CRDTs with small update messages and additional
methods for resynchronization to recover from dropped messages/transmission
failures. See [Efficient State-based CRDTs by
Delta-Mutation](https://arxiv.org/abs/1410.2803) for details.

A Composite CRDT class is also included for making arbitrary compositions of
CRDTs for more complex data structures. The Composite CRDT functions like the
LWWRegister, but with CRDTs instead of register values. To make all of this work
without a separate logical clock package, a simple Lamport scalar clock is
included.

## Status

Each implementation must include a full test suite to be considered complete.

- [x] Base Interfaces
- [x] GSet
- [x] Counter
- [x] ORSet
- [x] PNCounter
- [x] RGArray
- [x] LWWRegister
- [x] LWWMap
- [x] FIArray
- [ ] CausalTree
- [ ] CompositeCRDT
- [ ] Decent documentation

## Setup and Usage

Requires python 3+.

### Setup

To install, clone/unpack the repo.

#### Usage

@todo

## Interfaces and Classes

Below are the interfaces and classes, along with attributes and methods. Note
that any type that includes itself in a return signature indicates a jquery-
style monad pattern.

### Interfaces

- ClockProtocol(Protocol)
    - `uuid: bytes`
    - `read(self) -> Any`
    - `update(self, data: Any = None) -> Any`
    - `@staticmethod is_later(ts1: Any, ts2: Any) -> bool`
    - `@staticmethod are_concurrent(ts1: Any, ts2: Any) -> bool`
    - `@staticmethod compare(ts1: Any, ts2: Any) -> int`
    - `pack(self) -> bytes`
    - `@classmethod unpack(cls, data: bytes) -> ClockProtocol`
- CRDTProtocol(Protocol)
    - `clock: ClockProtocol`
    - `pack(self) -> bytes`
    - `@classmethod unpack(cls, data: bytes) -> CRDTProtocol`
    - `read(self) -> Any`
    - `update(self, state_update: StateUpdateProtocol) -> CRDTProtocol`
    - `checksums(self) -> tuple[Any]`
    - `history(self) -> tuple[StateUpdateProtocol]`
- DataWrapperProtocol(Protocol)
    - `value: Any`
    - `__hash__(self) -> int`
    - `__eq__(self, other) -> bool`
    - `pack(self) -> bytes`
    - `@classmethod unpack(cls, data: bytes) -> DataWrapperProtocol`
- StateUpdateProtocol(Protocol)
    - `clock_uuid: bytes`
    - `ts: Any`
    - `data: Hashable`

### Classes
- NoneWrapper(DataWrapperProtocol)
- StateUpdate(StateUpdateProtocol)
- ScalarClock(ClockProtocol)
    - `counter: int`
- GSet(CRDTProtocol)
    - `members: set = field(default_factory=set)`
    - `clock: ClockProtocol = field(default_factory=ScalarClock)`
    - `add(self, member: Hashable) -> StateUpdate`
- Counter(CRDTProtocol)
    - `counter: int = field(default=0)`
    - `clock: ClockProtocol = field(default_factory=ScalarClock)`
    - `increase(self, amount: int = 1) -> StateUpdate`
- ORSet(CRDTProtocol)
    - `observed: set = field(default_factory=set)`
    - `observed_metadata: dict = field(default_factory=dict)`
    - `removed: set = field(default_factory=set)`
    - `removed_metadata: dict = field(default_factory=dict)`
    - `clock: ClockProtocol = field(default_factory=ScalarClock)`
    - `cache: Optional[tuple] = field(default=None)`
    - `observe(self, member: Hashable) -> StateUpdate`
    - `remove(self, member: Hashable) -> StateUpdate`
- PNCounter(CRDTProtocol)
    - `positive: int = field(default=0)`
    - `negative: int = field(default=0)`
    - `clock: ClockProtocol = field(default_factory=ScalarClock)`
    - `increase(self, amount: int = 1) -> StateUpdate`
    - `decrease(self, amount: int = 1) -> StateUpdate`
- RGArray (CRDTProtocol)
    - `items: ORSet`
    - `clock: ClockProtocol`
    - `cache_full: list[RGATupleWrapper]`
    - `cache: tuple[Any]`
    - `__init__(self, items: ORSet = None, clock: ClockProtocol = None) -> None`
    - `pack(self) -> bytes`
    - `@classmethod unpack(cls, data: bytes) -> RGArray`
    - `read(self) -> tuple[RGATupleWrapper]`
    - `read_full(self) -> tuple[RGATupleWrapper]`
    - `update(self, state_update: StateUpdateProtocol) -> RGArray`
    - `checksums(self) -> tuple[int]`
    - `history(self) -> tuple[StateUpdate]`
    - `append(self, item: DataWrapperProtocol, writer: int) -> StateUpdate`
    - `delete(self, item: RGATupleWrapper) -> StateUpdate`
    - `calculate_cache(self) -> None`
    - `update_cache(self, item: RGATupleWrapper, visible: bool) -> None`
- LWWRegister(CRDTProtocol)
    - `name: DataWrapperProtocol`
    - `value: DataWrapperProtocol = field(default=NoneWrapper)`
    - `clock: ClockProtocol = field(default_factory=ScalarClock)`
    - `last_update: int = field(default=0)`
    - `last_writer: int = field(default=0)`
    - `write(self, value: DataWrapperProtocol, writer: int) -> StateUpdate`
- LWWMap(CRDTProtocol)
    - `names: ORSet`
    - `registers: dict[DataWrapperProtocol, LWWRegister]`
    - `clock: ClockProtocol`
    - `extend(self, name: DataWrapperProtocol, value: DataWrapperProtocol, writer: int) -> StateUpdate`
    - `unset(self, name: DataWrapperProtocol, writer: int) -> StateUpdate`
- FIArray(CRDTProtocol)
    - `positions: LWWMap`
    - `clock: ClockProtocol`
    - `cache: Optional[tuple]`
    - `@classmethod index_offset(cls, index: Decimal) -> Decimal`
    - `@classmethod index_between(cls, first: Decimal, second: Decimal) -> Decimal`
    - `put(self, item: DataWrapperProtocol, writer: int, index: Decimal) -> StateUpdate`
    - `put_between(self, item: DataWrapperProtocol, writer: int, first: DataWrapperProtocol, second: DataWrapperProtocol) -> StateUpdate`
    - `put_before(self, item: DataWrapperProtocol, writer: int, other: DataWrapperProtocol) -> StateUpdate`
    - `put_after(self, item: DataWrapperProtocol, writer: int, other: DataWrapperProtocol) -> StateUpdate`
    - `put_first(self, item: DataWrapperProtocol, writer: int) -> StateUpdate`
    - `put_last(self, item: DataWrapperProtocol, writer: int) -> StateUpdate`
    - `delete(self, item: DataWrapperProtocol, writer: int) -> StateUpdate`
- ValidCRDTs(Enum)
- CompositeCRDT(CRDTProtocol)
    - currently unimplemented

## Tests

Open a terminal in the root directory and run the following:

```
python tests/test_classes.py
```

The tests demonstrate the intended (and actual) behavior of the classes, as
well as some contrived examples of how they are used. Perusing the tests will be
informative to anyone seeking to use this package.

## ISC License

Copyleft (c) 2023 k98kurz

Permission to use, copy, modify, and/or distribute this software
for any purpose with or without fee is hereby granted, provided
that the above copyleft notice and this permission notice appear in
all copies.

Exceptions: this permission is not granted to Alphabet/Google, Amazon,
Apple, Microsoft, Netflix, Meta/Facebook, Twitter, or Disney; nor is
permission granted to any company that contracts to supply weapons or
logistics to any national military; nor is permission granted to any
national government or governmental agency; nor is permission granted to
any employees, associates, or affiliates of these designated entities.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
