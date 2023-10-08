from .errors import tert, vert
from .interfaces import CRDTProtocol, StateUpdateProtocol
from .stateupdate import StateUpdate
from hashlib import sha256
from typing import Type


def get_merkle_history(crdt: CRDTProtocol, /, *,
                        update_class: Type[StateUpdateProtocol] = StateUpdate
                        ) -> list[bytes, list[bytes], dict[bytes, bytes]]:
    """Get a Merklized history for the StateUpdates of the form
        [root, [content_id for update in crdt.history()], {
        content_id: packed for update in crdt.history()}] where
        packed is the result of update.pack() and content_id is the
        sha256 of the packed update.
    """
    history = crdt.history(update_class=update_class)
    leaves = [
        update.pack()
        for update in history
    ]
    leaf_ids = [
        sha256(leaf).digest()
        for leaf in leaves
    ]
    history = {
        leaf_id: leaf
        for leaf_id, leaf in zip(leaf_ids, leaves)
    }
    leaf_ids.sort()
    root = sha256(b''.join(leaf_ids)).digest()
    return [root, leaf_ids, history]

def resolve_merkle_histories(crdt: CRDTProtocol, history: list[bytes, list[bytes]]) -> list[bytes]:
    """Accept a history of form [root, leaves] from another node.
        Return the leaves that need to be resolved and merged for
        synchronization. Raises TypeError or ValueError for invalid
        input.
    """
    tert(type(history) in (list, tuple), 'history must be [[bytes, ], bytes]')
    vert(len(history) >= 2, 'history must be [[bytes, ], bytes]')
    tert(all([type(leaf) is bytes for leaf in history[1]]),
            'history must be [[bytes, ], bytes]')
    local_history = get_merkle_history(crdt)
    if local_history[0] == history[0]:
        return []
    return [
        leaf for leaf in history[1]
        if leaf not in local_history[1]
    ]
