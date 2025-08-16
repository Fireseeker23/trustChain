import hashlib
from typing import Iterable, List

# Deterministic order by key; leaf = keccak(key || ":" || value)
try:
    from eth_utils import keccak
except Exception:
    def keccak(x: bytes) -> bytes:
        return hashlib.sha3_256(x).digest()
    
def leaf(key: str, value: str) -> bytes:
    return keccak((key + ":" + value).encode())


def merkle_root(pairs: Iterable[tuple]) -> bytes:
    nodes: List[bytes] = [leaf(k, str(v)) for k, v in sorted(pairs, key=lambda kv: kv[0])]
    if not nodes:
        return b"\x00"* 32
    while len(nodes) > 1:
        nxt: List[bytes] = []
        for i in range(0, len(nodes), 2):
            a = nodes[i]
            b = nodes[i+1] if i+1 < len(nodes) else nodes[i]
            nxt.append(keccak(a + b))
        nodes = nxt
    return nodes[0]