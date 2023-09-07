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
- [x] Decent documentation
- [ ] New CRDT: CounterSet
- [ ] New CRDT: Graph
- [ ] ListProtocol: RGArray, FIArray, CausalTree
- [ ] Refactor: change writer_id from int to SerializableType
- [ ] New CRDT: Document
- [ ] Hooks/event listeners

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
- [GSet](https://github.com/k98kurz/CRDTs/blob/master/docs/gset.md)
- [ORSet](https://github.com/k98kurz/CRDTs/blob/master/docs/orset.md)
- [Counter](https://github.com/k98kurz/CRDTs/blob/master/docs/counter.md)
- [PNCounter](https://github.com/k98kurz/CRDTs/blob/master/docs/pncounter.md)
- [RGArray](https://github.com/k98kurz/CRDTs/blob/master/docs/rgarray.md)
- [LWWRegister](https://github.com/k98kurz/CRDTs/blob/master/docs/lwwregister.md)
- [LWWMap](https://github.com/k98kurz/CRDTs/blob/master/docs/lwwmap.md)
- [MVRegister](https://github.com/k98kurz/CRDTs/blob/master/docs/mvregister.md)
- [MVMap](https://github.com/k98kurz/CRDTs/blob/master/docs/mvmap.md)
- [FIArray](https://github.com/k98kurz/CRDTs/blob/master/docs/fiarray.md)
- [CausalTree](https://github.com/k98kurz/CRDTs/blob/master/docs/causaltree.md)

Each documentation file includes examples of how the CRDT can be used.

To use custom implementations of included interfaces, note that they must be
injected properly. For a custom implementation of `StateUpdateProtocol`, the
class will have to be passed to any CRDT method that produces `StateUpdate`s by
default by using the `update_class=` named parameter. For a custom
implementation of `DataWrapperProtocol`, the relevant class must be provided to
any calls to `unpack` when anything containing the custom class is deserialized,
e.g. `LWWMap.unpack(data, inject={'MyDataWrapper': MyDataWrapper})`. The
interfaces are autodox documented in
[interfaces.md](https://github.com/k98kurz/CRDTs/blob/master/interfaces.md).

Additionally, the functions `serialize_part` and `deserialize_part` can be used
for serializing and deserializing complex structures to and from bytes. Any
custom class implementing the `PackableProtocol` interface will be compatible
with these functions and must be injected into `deserialize_part`, e.g.
`deserialize_part(data, inject={'MyPackableClass': MyPackableClass})`.

#### Synchronization

Note that the `checksums` and `history` methods for every CRDT support timestamp
constraints `from_ts` and `until_ts`. This allows for nodes to synchronize
without having to ship all updates across the network, which is a primary
advantage of δ-CRDTs. How to best implement synchronization to utilize this
feature is left to the library consumer, but I would start with something like
the following:

```python
def make_ts_buckets(max_ts: int, max_bucket_size: int = 16) -> list[tuple[int, int]]:
    """Divides checksums and updates into buckets of form (from_ts, until_ts)
        based upon the max_ts and max_bucket_size.
    """
    if max_ts < max_bucket_size:
        return [(0, max_ts)]
    n_buckets = math.ceil(math.log2(1 + max_ts/max_bucket_size))
    bucket_size = math.ceil(max_ts / n_buckets)
    buckets = []
    for i in range(n_buckets):
        buckets.append((i*bucket_size, (i+1)*bucket_size))
    return buckets

def make_synchronization_dict(crdt: CRDTProtocol) -> dict[tuple[int, int], tuple[Any]]:
    buckets = make_ts_buckets(crdt.clock.read())
    return {
        b: crdt.checksums(from_ts=b[0], until_ts=b[1])
        for b in buckets
    }

def check_synchronization_dict(crdt: CRDTProtocol,
        sync: dict[tuple[int, int]], tuple[Any]) -> list[tuple[int, int]]:
    """Checks a CRDT against a synchronization dict. If the checksums differ for
        any timestamp bucket, include that timestamp bucket in the return list.
        The state updates for those buckets can then be requested from the
        remote replica.
    """
    different_buckets = []
    for bucket, chksms in sync:
        if crdt.checksums(from_ts=bucket[0], until_ts=bucket[1]) != chksms:
            different_buckets.append(bucket)
    return different_buckets

def make_synchronization_history(crdt: CRDTProtocol,
        different_buckets: list[tuple[int, int]]) -> list[StateUpdate]:
    """Returns all the StateUpdates requested for the given buckets."""
    history = []
    for b in different_buckets:
        history.extend(crdt.history(from_ts=b[0], until_ts=b[1]))
    return history
```

The above divides timestamps into dynamically-sized buckets no larger than the
supplied `max_bucket_size` parameter and is meant to demonstrate the concept of
synchronization via δ-states. The number of buckets will scale linearly with the
age of the CRDT and the `max_bucket_size` parameter. It could be adapted to
scale the number of buckets logarithmically with the age/state size of the CRDT
by calculating the `max_bucket_size` parameter rather than hard-coding it.
For example, `bucket_sizer = lambda ts: math.ceil(ts/math.log2(ts+1))` which
would be called with `bucket_sizer(crdt.clock.read())`; this will result in a
number of buckets equal to the log base 2 of the max timestamp:
- ts=16, bucket_count=4
- ts=32, bucket_count=5
- ts=64, bucket_count=6
- ...
- ts=1024, bucket_count=10

## Interfaces and Classes

Below are the interfaces and classes, along with attributes and methods. Note
that any type that includes itself in a return signature indicates a jquery-
style monad pattern.

### Interfaces

- ClockProtocol(Protocol)
- CRDTProtocol(Protocol)
- DataWrapperProtocol(Protocol)
- StateUpdateProtocol(Protocol)

### Type Alias

There is a type alias, `SerializableType`, used in several places. It is equal
to the following: `DataWrapperProtocol|int|float|str|bytes|bytearray|NoneType`.

### Classes
- NoneWrapper(DataWrapperProtocol)
- StateUpdate(StateUpdateProtocol)
- ScalarClock(ClockProtocol)
- StrWrapper(DataWrapperProtocol)
- BytesWrapper(StrWrapper)
- CTDataWrapper(DataWrapperProtocol)
- DecimalWrapper(StrWrapper)
- IntWrapper(DecimalWrapper)
- RGAItemWrapper(StrWrapper)
- NoneWrapper(DataWrapperProtocol)
- GSet(CRDTProtocol)
- Counter(CRDTProtocol)
- ORSet(CRDTProtocol)
- PNCounter(CRDTProtocol)
- RGArray (CRDTProtocol)
- LWWRegister(CRDTProtocol)
- LWWMap(CRDTProtocol)
- MVRegister(CRDTProtocol)
- MVMap(CRDTProtocol)
- FIArray(CRDTProtocol)

## Tests

Clone the repository, then open a terminal in the root directory and run the
following:

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

The 233 tests demonstrate the intended (and actual) behavior of the classes, as
well as some contrived examples of how they are used. Perusing the tests will be
informative to anyone seeking to use this package.

## ISC License

Copyleft (c) 2023 k98kurz

Permission to use, copy, modify, and/or distribute this software
for any purpose with or without fee is hereby granted, provided
that the above copyleft notice and this permission notice appear in
all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
