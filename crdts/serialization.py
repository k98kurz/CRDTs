from __future__ import annotations
from .datawrappers import (
    StrWrapper,
    BytesWrapper,
    DecimalWrapper,
    IntWrapper,
    RGATupleWrapper,
    CTDataWrapper,
)
from .errors import tressa
from .interfaces import PackableProtocol
from typing import Any
import struct


def serialize_part(data: Any) -> bytes:
    """Serializes an instance of a PackableProtocol implementation or
        built-in type, recursively calling itself as necessary.
    """
    tressa(isinstance(data, PackableProtocol) or \
        type(data) in (list, set, tuple, str, bytes, bytearray, int, float),
        'data type must be one of (PackableProtocol, list, set, tuple, ' + \
        'str, bytes, bytearray, int, float)')

    if isinstance(data, PackableProtocol):
        packed = bytes(data.__class__.__name__, 'utf-8').hex()
        packed = bytes(packed, 'utf-8') + b'_' + data.pack()
        return struct.pack(
            f'!1sI{len(packed)}s',
            b'p',
            len(packed),
            packed
        )

    if type(data) in (list, set, tuple):
        items = b''.join([serialize_part(item) for item in data])
        code = ({
            list: b'l',
            set: b'e',
            tuple: b't'
        })[type(data)]

        return struct.pack(
            f'!1sI{len(items)}s',
            code,
            len(items),
            items
        )

    if type(data) in (bytes, bytearray):
        return struct.pack(
            f'!1sI{len(data)}s',
            b'b' if type(data) is bytes else b'a',
            len(data),
            data
        )

    if type(data) is str:
        data = bytes(data, 'utf-8')
        return struct.pack(
            f'!1sI{len(data)}s',
            b's',
            len(data),
            data
        )

    if type(data) is int:
        return struct.pack(
            f'!1sII',
            b'i',
            4,
            data
        )

    if type(data) is float:
        return struct.pack(
            f'!1sId',
            b'f',
            8,
            data
        )


def deserialize_part(data: bytes, inject: dict = {}) -> Any:
    """Deserializes an instance of a PackableProtocol implementation
        or built-in type, recursively calling itself as necessary.
    """
    code, data = struct.unpack(f'!1s{len(data)-1}s', data)
    dependencies = {**globals(), **inject}

    if code == b'p':
        packed_len, data = struct.unpack(f'!I{len(data)-4}s', data)
        packed, _ = struct.unpack(f'!{packed_len}s{len(data)-packed_len}s', data)
        packed_class, _, packed_data = packed.partition(b'_')
        packed_class = str(bytes.fromhex(str(packed_class, 'utf-8')), 'utf-8')
        tressa(packed_class in dependencies,
            f'{packed_class} not found in globals or inject; cannot unpack')
        tressa(hasattr(dependencies[packed_class], 'unpack'),
            f'{packed_class} must have unpack method')
        return dependencies[packed_class].unpack(packed_data)

    if code in (b'l', b'e', b't'):
        let_len, data = struct.unpack(f'!I{len(data)-4}s', data)
        let_data, _ = struct.unpack(f'!{let_len}s{len(data)-let_len}s', data)
        items = []
        while len(let_data) > 0:
            _, item_len, _ = struct.unpack(f'!1sI{len(let_data)-5}s', let_data)
            item, let_data = struct.unpack(
                f'!{5+item_len}s{len(let_data)-5-item_len}s',
                let_data
            )
            items += [deserialize_part(item, inject=inject)]

        if code == b'l':
            return items
        if code == b'e':
            return set(items)
        if code == b't':
            return tuple(items)

    if code in (b'b', b'a'):
        bt_len, data = struct.unpack(f'!I{len(data)-4}s', data)
        bt_data, _ = struct.unpack(f'!{bt_len}s{len(data)-bt_len}s', data)
        return bt_data if code == b'b' else bytearray(bt_data)

    if code == b's':
        s_len, data = struct.unpack(f'!I{len(data)-4}s', data)
        s, _ = struct.unpack(f'!{s_len}s{len(data)-s_len}s', data)
        return str(s, 'utf-8')

    if code == b'i':
        return struct.unpack(f'!II{len(data)-8}s', data)[1]

    if code == b'f':
        return struct.unpack(f'!Id{len(data)-12}s', data)[1]
