"""D-059 P2 exit check: the evidence candidates per theme from pgvector (SQL) equal the former numpy search.

`uv run python scripts/check_retrieval.py`   — read-only, no LLM. For every theme with an embedding at each checkpoint,
compares the K nearest research / study / option nodes (contextualize.candidates) with the numpy implementation it
replaced (normalised dot product, ties to the higher node id). Prints the overlap; exit 1 on any difference.
"""

import sys

import numpy as np

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.structure import contextualize as X


def numpy_candidates(conn, t, nodes):
    tv = X.vec(t["embedding"])
    vecs = {(r[0], r[1]): (r[2], X.vec(r[3])) for r in conn.execute("SELECT node_type, node_id, text, embedding FROM node_embedding")}
    out = []
    for typ, k in X.K.items():
        pool = [(float(v @ tv), nid, txt) for (ty, nid), (txt, v) in vecs.items() if ty == typ and nid in set(nodes.get(typ, []))]
        out += [(typ, nid, txt) for _, nid, txt in sorted(pool, reverse=True)[:k]]
    return out


def main() -> int:
    conn = connect()
    bad = total = 0
    for cp in ("cp1", "cp2"):
        run = C.latest_run(conn, cp, "contextualize")
        if run is None:
            continue
        nodes = X.visible_nodes(conn, cp)
        themes = conn.execute("SELECT t.key, t.embedding FROM theme t WHERE t.key IN "
                              "(SELECT theme_key FROM theme_member WHERE run_id = ?) AND t.embedding IS NOT NULL", (run["id"],)).fetchall()
        for t in themes:
            total += 1
            a, b = X.candidates(conn, t, nodes), numpy_candidates(conn, t, nodes)
            if a != b:
                bad += 1
                overlap = len(set(a) & set(b)) / max(len(b), 1)
                print(f"{cp} {t['key']}: {'same set, other order' if set(a) == set(b) else f'overlap {overlap:.0%}'}")
        print(f"{cp}: {len(themes)} themes checked")
    print(f"{total - bad} of {total} themes: identical candidates")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
