# CRDTs

This package implements several CRDTs in a hopefully easy-to-use way.

## Overview

This package includes several Conflict-free Replicated Data Types. See
[Verifying Strong Eventual Consistency in Distributed Systems by Gomes,
Kleppmann, Mulligan, and Beresford](https://doi.org/10.1145/3133933) and
[Verifying Strong Eventual Consistency in δ-CRDTs by Taylor
Blau](https://arxiv.org/abs/2006.09823) for more details. This package includes
the following CRDTs (class names in parentheses):
- Counter (Counter)
- Positive-Negative Counter (PNCounter)
- Grow-only Set (GSet)
- Observed-Removed Set (ORSet)
- Fractionally-Indexed Array (FIArray)
- Replicated Growable Array (RGArray)
- Last-Writer-Wins Register (LWWRegister)
- Last-Writer-Wins Map (LWWMap)
- Multi-Value Register (MVRegister)
- Multi-Value Map (MVMap)
- Causal Tree (CausalTree)

These are implemented as delta-CRDTs with small update messages and additional
methods for resynchronization to recover from dropped messages/transmission
failures. See [Efficient State-based CRDTs by
Delta-Mutation](https://arxiv.org/abs/1410.2803) for details.

For synchronization without a separate logical clock package, a simple Lamport
`ScalarClock` class is included, though any logical clock that fulfills the
simple `ClockProtocol` interface can be used. The `StateUpdate` class is
provided as a default implementation of the `StateUpdateProtocol` interface. A
handful of classes implementing the `DataWrapperProtocol` interface are included
for use in the CRDTs that need them.

Everything in this package is designed to serialize and deserialize for reliable
network transmission and/or persistence to disk.

## Status

Each implementation must include a full test suite to be considered complete.

- [x] Base Interfaces
- [x] GSet
- [x] ORSet
- [x] Counter
- [x] PNCounter
- [x] RGArray
- [x] LWWRegister
- [x] LWWMap
- [x] MVRegister
- [x] MVMap
- [x] FIArray
- [x] CausalTree
- [ ] Decent documentation

## Setup and Usage

Requires python 3+.

### Setup

To install, clone/unpack the repo.

### Usage

Each CRDT follows the `CRDTProtocol` and includes the following methods:

- `read(self) -> Any`: produces the view of the data
- `update(self, state_update: StateUpdateProtocol) -> CRDTProtocol`: applies an
update and returns `self` in monad pattern
- `pack(self) -> bytes`: serializes entire CRDT to bytes
- `@classmethod unpack(cls, data: bytes) -> CRDTProtocol`: deserializes a CRDT

Beyond this, each CRDT has its own specific methods unique to the type. Full
documentation for each class in this library can be found in the
[docs.md](https://github.com/k98kurz/CRDTs/blob/master/docs.md) file generated
using [autodox](https://pypi.org/project/autodox/).

Documentation explaining how each CRDT works can be found here:
- [GSet](https://github.com/k98kurz/CRDTs/blob/docs/gset.md)
- [ORSet](https://github.com/k98kurz/CRDTs/blob/docs/orset.md)
- [Counter](https://github.com/k98kurz/CRDTs/blob/docs/counter.md)
- [PNCounter](https://github.com/k98kurz/CRDTs/blob/docs/pncounter.md)
- [RGArray](https://github.com/k98kurz/CRDTs/blob/docs/rgarray.md)
- [LWWRegister](https://github.com/k98kurz/CRDTs/blob/docs/lwwregister.md)
- [LWWMap](https://github.com/k98kurz/CRDTs/blob/docs/lwwmap.md)
- [MVRegister](https://github.com/k98kurz/CRDTs/blob/docs/mvregister.md)
- [MVMap](https://github.com/k98kurz/CRDTs/blob/docs/mvmap.md)
- [FIArray](https://github.com/k98kurz/CRDTs/blob/docs/fiarray.md)
- [CausalTree](https://github.com/k98kurz/CRDTs/blob/docs/causaltree.md)

Each documentation file includes examples of how the CRDT can be used.

To use custom implementations of included interfaces, note that they must be
injected properly. For a custom implementation of `StateUpdateProtocol`, the
class will have to be passed to any CRDT method that produces `StateUpdate`s by
default by using the `update_class=` named parameter. For a custom
implementation of `DataWrapperProtocol`, the relevant class must be provided to
any calls to `unpack` when anything containing the custom class is deserialized,
e.g. `LWWMap.unpack(data, inject={'MyDataWrapper': MyDataWrapper})`.

Additionally, the functions `serialize_part` and `deserialize_part` can be used
for serializing and deserializing complex structures to and from bytes. Any
custom class implementing the `PackableProtocol` interface will be compatible
with these functions and must be injected into `deserialize_part`, e.g.
`deserialize_part(data, inject={'MyPackableClass': MyPackableClass})`.

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
- StrWrapper(DataWrapperProtocol)
    - `value: str`
- BytesWrapper(StrWrapper)
    - `value: bytes`
- CTDataWrapper(DataWrapperProtocol)
    - `value: DataWrapperProtocol`
- DecimalWrapper(StrWrapper)
    - `value: Decimal`
- IntWrapper(DecimalWrapper)
    - `value: int`
- RGATupleWrapper(StrWrapper)
    - `value: tuple[DataWrapperProtocol, tuple[DataWrapperProtocol, int]]`
- NoneWrapper(DataWrapperProtocol)
- GSet(CRDTProtocol)
    - `members: set`
    - `clock: ClockProtocol`
    - `update_history: dict[DataWrapperProtocol, StateUpdateProtocol]`
    - `add(self, member: Hashable) -> StateUpdate`
- Counter(CRDTProtocol)
    - `counter: int`
    - `clock: ClockProtocol`
    - `increase(self, amount: int = 1) -> StateUpdate`
- ORSet(CRDTProtocol)
    - `observed: set`
    - `observed_metadata: dict`
    - `removed: set`
    - `removed_metadata: dict`
    - `clock: ClockProtocol`
    - `cache: Optional[tuple]`
    - `observe(self, member: Hashable) -> StateUpdate`
    - `remove(self, member: Hashable) -> StateUpdate`
- PNCounter(CRDTProtocol)
    - `positive: int`
    - `negative: int`
    - `clock: ClockProtocol`
    - `increase(self, amount: int = 1) -> StateUpdate`
    - `decrease(self, amount: int = 1) -> StateUpdate`
- RGArray (CRDTProtocol)
    - `items: ORSet`
    - `clock: ClockProtocol`
    - `cache_full: list[RGATupleWrapper]`
    - `cache: tuple[Any]`
    - `__init__(self, items: ORSet = None, clock: ClockProtocol = None) -> None`
    - `read(self) -> tuple[Any]`
    - `read_full(self) -> tuple[RGATupleWrapper]`
    - `append(self, item: DataWrapperProtocol, writer: int) -> StateUpdate`
    - `delete(self, item: RGATupleWrapper) -> StateUpdate`
    - `calculate_cache(self) -> None`
    - `update_cache(self, item: RGATupleWrapper, visible: bool) -> None`
- LWWRegister(CRDTProtocol)
    - `name: DataWrapperProtocol`
    - `value: DataWrapperProtocol`
    - `clock: ClockProtocol`
    - `last_update: int`
    - `last_writer: int`
    - `__init__(self, name: DataWrapperProtocol, value: DataWrapperProtocol = None, clock: ClockProtocol = None, last_update: Any = None, last_writer: int = 0) -> None`
    - `@classmethod compare_values(cls, value1: DataWrapperProtocol, value2: DataWrapperProtocol) -> bool`
    - `write(self, value: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
- LWWMap(CRDTProtocol)
    - `names: ORSet`
    - `registers: dict[DataWrapperProtocol, LWWRegister]`
    - `clock: ClockProtocol`
    - `extend(self, name: DataWrapperProtocol, value: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `unset(self, name: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
- MVRegister(CRDTProtocol)
    - `name: DataWrapperProtocol`
    - `values: list[DataWrapperProtocol]`
    - `clock: ClockProtocol`
    - `@classmethod compare_values(cls, value1: DataWrapperProtocol, value2: DataWrapperProtocol) -> bool`
    - `write(self, value: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
- MVMap(CRDTProtocol)
    - `names: ORSet`
    - `registers: dict[DataWrapperProtocol, MVRegister]`
    - `clock: ClockProtocol`
    - `extend(self, name: DataWrapperProtocol, value: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `unset(self, name: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
- FIArray(CRDTProtocol)
    - `positions: LWWMap`
    - `clock: ClockProtocol`
    - `cache_full: list[DataWrapperProtocol]`
    - `cache: list[Any]`
    - `__init__(self, positions: LWWMap = None, clock: ClockProtocol = None) -> None`
    - `@classmethod index_between(cls, first: Decimal, second: Decimal) -> Decimal`
    - `read_full(self) -> tuple[DataWrapperProtocol]`
    - `put(self, item: DataWrapperProtocol, writer: int, index: Decimal, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol:`
    - `put_between(self, item: DataWrapperProtocol, writer: int, first: DataWrapperProtocol, second: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `put_before(self, item: DataWrapperProtocol, writer: int, other: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `put_after(self, item: DataWrapperProtocol, writer: int, other: DataWrapperProtocol, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `put_first(self, item: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `put_last(self, item: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `delete(self, item: DataWrapperProtocol, writer: int, /, *, update_class: type[StateUpdateProtocol] = StateUpdate) -> StateUpdateProtocol`
    - `calculate_cache(self) -> None`
    - `update_cache(self, item: DataWrapperProtocol, visible: bool) -> None`

## Tests

Open a terminal in the root directory and run the following:

```bash
find ./tests -name test_*.py -exec python {} \;
```

Alternately, for non-POSIX systems, run the following:

```
python test_datawrappers.py
python test_scalarclock.py
python test_serialization.py
python test_stateupdate.py
python test_causaltree.py
python test_counter.py
python test_fiarray.py
python test_gset.py
python test_lwwmap.py
python test_lwwregister.py
python test_mvmap.py
python test_mvregister.py
python test_orset.py
python test_pncounter.py
python test_rgarray.py
```

The 226 tests demonstrate the intended (and actual) behavior of the classes, as
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
