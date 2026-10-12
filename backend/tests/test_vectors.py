"""pgvector in the app (D-059): embeddings round-trip as float32 arrays, and the evidence retrieval (exact nearest
neighbours in SQL) ranks like a plain cosine search, ties to the higher node id."""

import numpy as np

from bmw_req.db import connect, vec
from bmw_req.structure import contextualize as X


def unit(*xs):
    v = np.zeros(1536, dtype=np.float32)
    v[: len(xs)] = xs
    return v / np.linalg.norm(v)


def test_vectors_round_trip_as_float32(pg_url):
    c = connect()
    v = unit(1, 2, 3)
    c.execute("INSERT INTO node_embedding (node_type, node_id, text, embedding) VALUES ('study', 1, 'x', ?)", (v,))
    back = vec(c.execute("SELECT embedding FROM node_embedding").fetchone()[0])
    assert back.dtype == np.float32 and np.allclose(back, v)


def test_candidates_are_the_nearest_per_type(pg_url, monkeypatch):
    c = connect()
    monkeypatch.setattr(X, "K", {"research": 2, "study": 1, "option": 1})
    rows = [("research", 1, unit(1, 0)), ("research", 2, unit(1, 1)), ("research", 3, unit(0, 1)), ("research", 4, unit(1, 0)),
            ("study", 5, unit(0, 1)), ("study", 6, unit(1, 0.1)), ("option", 7, unit(1, 0))]
    c.executemany("INSERT INTO node_embedding (node_type, node_id, text, embedding) VALUES (?, ?, ?, ?)",
                  [(t, i, f"n{i}", v) for t, i, v in rows])
    theme = {"embedding": unit(1, 0)}
    nodes = {"research": [1, 2, 3, 4], "study": [5, 6], "option": []}   # option 7 not visible at this checkpoint
    got = X.candidates(c, theme, nodes)
    # research 1 and 4 tie exactly → the higher id first; study 6 is nearer than 5; no visible option
    assert [(t, i) for t, i, _ in got] == [("research", 4), ("research", 1), ("study", 6)]
