"""The comment galaxy (D-041): every raw customer comment as a point in a fixed 3D evidence space.

1. Embed each comment's raw text (no AI interpretation) with the embedding model, through the budget-guarded wrapper.
   Stored in `source_embedding` (keyed by source_item_id, pgvector). ~10k comments ≈ $0.01.
2. Lay the space out once over ALL comments: PCA to 50 dims, then 3D t-SNE (seed 2026), scaled into a unit ball.
   One layout for both checkpoints, so a comment never moves when the second sweep arrives; the layout only encodes
   textual similarity, not counts or conclusions (same documented trade-off as D-027's cluster structure).

`uv run python -m bmw_req.structure.galaxy`
"""

from __future__ import annotations


import numpy as np

from bmw_req.db import Connection, vec
from bmw_req.llm.client import LLM

BATCH = 512
SEED = 2026
METHOD = "pca50+tsne3d(perplexity=40,seed=2026)"


def embed_comments(conn: Connection, llm: LLM) -> int:
    rows = conn.execute(
        """SELECT id, text FROM source_item WHERE kind = 'feedback' AND COALESCE(TRIM(text), '') != ''
           AND id NOT IN (SELECT source_item_id FROM source_embedding) ORDER BY id""").fetchall()
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        vecs = llm.embed([r["text"][:4000] for r in chunk], job="embed:comments:galaxy")
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany("INSERT INTO source_embedding (source_item_id, embedding) VALUES (?, ?)",
                         [(r["id"], vec(v)) for r, v in zip(chunk, vecs)])
        conn.execute("COMMIT")
    return len(rows)


def layout(conn: Connection) -> int:
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE

    rows = conn.execute("""SELECT s.id, e.embedding FROM source_item s JOIN source_embedding e ON e.source_item_id = s.id
                           WHERE s.kind = 'feedback' ORDER BY s.id""").fetchall()
    ids = [r["id"] for r in rows]
    X = np.stack([vec(r["embedding"]) for r in rows])
    X = PCA(n_components=50, random_state=SEED).fit_transform(X)
    Y = TSNE(n_components=3, perplexity=40, init="pca", random_state=SEED, max_iter=1000).fit_transform(X)
    Y -= np.median(Y, axis=0)
    Y /= np.percentile(np.linalg.norm(Y, axis=1), 98)   # 98 % of points inside the unit ball
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("DELETE FROM source_layout")
    conn.executemany("INSERT INTO source_layout (source_item_id, x, y, z, method) VALUES (?, ?, ?, ?, ?)",
                     [(i, float(p[0]), float(p[1]), float(p[2]), METHOD) for i, p in zip(ids, Y)])
    conn.execute("COMMIT")
    return len(ids)


if __name__ == "__main__":
    from bmw_req.db import connect

    c = connect()
    print("embedded", embed_comments(c, LLM(conn=c)))
    print("laid out", layout(c))
