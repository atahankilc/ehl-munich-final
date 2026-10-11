"""Checkpoint visibility and the cp1 → cp2 run lineage (D-041), on synthetic data (no BMW data, no paid calls)."""

import json

import pytest

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.ingest import reference


@pytest.fixture
def conn():
    c = connect(":memory:")
    reference.seed(c)
    C.ensure(c)
    return c


def add(conn, kind, ref, wave=1, published=None):
    conn.execute("INSERT INTO source_item (kind, ref, wave, published_at, meta_json) VALUES (?, ?, ?, ?, '{}')",
                 (kind, ref, wave, published))


def cp_of(conn, ref):
    return conn.execute("SELECT checkpoint FROM source_item WHERE ref = ?", (ref,)).fetchone()[0]


def test_dates_map_to_the_first_checkpoint_that_knows_them():
    assert C.checkpoint_for(C.parse_date("2026-01-31")) == "cp1"
    assert C.checkpoint_for(C.parse_date("2026-02-01")) == "cp2"
    assert C.checkpoint_for(C.parse_date("2026-07")) == "cp2"      # month → month end
    assert C.checkpoint_for(C.parse_date("2025")) == "cp1"         # year → year end
    assert C.checkpoint_for(C.parse_date("2026-08-01")) is None    # after the last cut-off: never visible
    assert C.checkpoint_for(None) is None
    assert C.visible_ids("cp2") == ("cp2", "cp1") and C.visible_ids("cp1") == ("cp1",)


def test_visibility_rules(conn):
    add(conn, "feedback", "a", wave=1)
    add(conn, "feedback", "b", wave=2)
    add(conn, "study", "s", wave=2)                       # BMW internal: known at cp1 whatever its old wave
    add(conn, "web", "w-jan", published="2026-01-10")
    add(conn, "web", "w-jul", published="2026-06-30")
    add(conn, "web", "w-late", published="2026-09-01")
    add(conn, "web", "w-undated")                         # no date: never visible (no leak)
    add(conn, "research", "r-undated")                    # research marked undated: background at cp1
    C.assign_visibility(conn)
    assert [cp_of(conn, r) for r in ("a", "b", "s", "w-jan", "w-jul", "w-late", "w-undated", "r-undated")] == \
           ["cp1", "cp2", "cp1", "cp1", "cp2", None, None, "cp1"]


def test_cp2_cannot_run_before_cp1(conn):
    with pytest.raises(C.CheckpointError):
        C.start_run(conn, "cp2", "cluster", "test")


def test_cp2_builds_on_cp1_and_tracks_every_change(conn):
    r1 = C.start_run(conn, "cp1", "cluster", "test")
    C.write_tracks(conn, r1, {"k-held": (10, None), "k-up": (10, None), "k-down": (10, None), "k-gone": (5, None)})
    C.finish_run(conn, r1, {})
    r2 = C.start_run(conn, "cp2", "cluster", "test")
    assert conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (r2,)).fetchone()[0] == r1
    counts = C.write_tracks(conn, r2, {"k-held": (10.5, None), "k-up": (13, None), "k-down": (7, None),
                                       "k-new": (3, {"why": "second half of comments"})})
    assert counts == {"new": 1, "held": 1, "strengthened": 1, "weakened": 1, "lost": 1}
    states = dict(conn.execute("SELECT entity_key, state FROM track WHERE run_id = ?", (r2,)).fetchall())
    assert states == {"k-held": "held", "k-up": "strengthened", "k-down": "weakened", "k-new": "new", "k-gone": "lost"}
    lost = conn.execute("SELECT prev_weight FROM track WHERE run_id = ? AND entity_key = 'k-gone'", (r2,)).fetchone()
    assert lost[0] == 5                                   # nothing disappears silently: the old weight is kept


def test_rerun_supersedes_and_child_uses_latest_parent(conn):
    a = C.start_run(conn, "cp1", "acquire", "t"); C.finish_run(conn, a, {})
    b = C.start_run(conn, "cp1", "acquire", "t"); C.finish_run(conn, b, {})
    assert conn.execute("SELECT status FROM checkpoint_run WHERE id = ?", (a,)).fetchone()[0] == "superseded"
    c = C.start_run(conn, "cp2", "acquire", "t")
    assert conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (c,)).fetchone()[0] == b


def test_acquire_holds_cp1_sources_and_adds_the_second_half(conn):
    add(conn, "feedback", "a", wave=1)
    add(conn, "feedback", "b", wave=2)
    add(conn, "option_list", "o")
    C.assign_visibility(conn)
    one = C.run_acquire(conn, "cp1")
    two = C.run_acquire(conn, "cp2")
    assert (one["new"], one["held"]) == (2, 0)
    assert (two["new"], two["held"], two["lost"]) == (1, 2, 0)
    stats = json.loads(conn.execute("SELECT stats_json FROM checkpoint_run WHERE id = ?", (two["run_id"],)).fetchone()[0])
    assert stats["held"] == 2
