"""Schema and feedback-ingest tests on synthetic data (no BMW data, no paid calls)."""

import json
import sqlite3

import openpyxl
import pytest

from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.ingest.feedback import SHEET, ingest_feedback

HEADER = ["ID", "Source", "Brand", "Sales Description", "Country", "Derivate (e-code)", "Engine Type",
          "Feedback Type", "Customer Feedback", "Vfc level2 3 Name", "Vfc level2 Name", "Vfc level3 Name"]


@pytest.fixture
def conn():
    c = connect(":memory:")
    reference.seed(c)
    return c


def write_xlsx(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_audit_event_is_append_only(conn):
    conn.execute("INSERT INTO audit_event (actor_type, action, entity_type, entity_id) VALUES ('system', 'x', 'y', '1')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE audit_event SET action = 'z'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_event")


def test_country_mapping_from_market_rows(conn):
    m = reference.country_to_market(conn)
    assert (m("GB"), m("NO"), m("US"), m("CN"), m("JP"), m("KR")) == ("EU", "EU", "US", "CN", "RoW", "RoW")


def test_ingest_dedupes_by_id_and_is_idempotent(conn, tmp_path):
    p = tmp_path / "G60_feedback_hackathon.xlsx"
    write_xlsx(p, [
        ["G60-0001", "Source A", "[BMW]", "[BMW 5 Series]", "US", "G60", "BEVE", "Wants", "more range",
         "Electric Range : Customer request", "Electric Range", "Customer request: function"],
        ["G60-0001", "Source A", "[BMW]", "[BMW 5 Series]", "US", "G60", "BEVE", "Defect", "more range",
         "Charging : Defect", "Charging", "Defect"],
        ["G60-0002", "Source D", "[BMW]", "[BMW 5 Series]", "KR", "G60", "ICE", None, "love the seats",
         None, None, None],
    ])
    assert ingest_feedback(conn, p) == 2
    assert ingest_feedback(conn, p) == 0
    rows = {r["external_id"]: r for r in conn.execute("SELECT * FROM source_item")}
    meta = json.loads(rows["G60-0001"]["meta_json"])
    assert rows["G60-0001"]["market_code"] == "US" and rows["G60-0002"]["market_code"] == "RoW"
    assert meta["engine"] == "BEV" and len(meta["bmw_labels"]) == 2 and meta["excel_rows"] == [2, 3]
    assert json.loads(rows["G60-0002"]["meta_json"])["bmw_labels"] == []
    assert rows["G60-0001"]["ref"] == "G60_feedback_hackathon.xlsx#Feedback_Explorer:G60-0001"
    assert conn.execute("SELECT COUNT(*) FROM ingest_batch").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'ingest'").fetchone()[0] == 1


def test_extraction_store_flags_quotes_and_skips_invented(conn):
    from bmw_req.pipeline.extract import BatchResult, quote_ok
    from bmw_req.pipeline.run_extract import pending, store

    conn.execute("INSERT INTO source_item (kind, ref, external_id, vehicle_model_id, text, meta_json)"
                 " VALUES ('feedback', 'f#1', 'G60-1', 'G60', 'Customer stated  the Seats are hard.', '{\"engine\": \"ICE\"}')")
    conn.execute("INSERT INTO source_item (kind, ref, external_id, vehicle_model_id, text, meta_json)"
                 " VALUES ('feedback', 'f#2', 'G60-2', 'G60', 'love it', '{\"engine\": \"ICE\"}')")
    chunk = pending(conn, "G60", None)
    assert [v["id"] for v in chunk] == ["G60-1", "G60-2"]
    sig = dict(category="Comfort & Space", topic="Seats", feedback_type="complaint", severity="low", need_statement="n")
    batch = BatchResult.model_validate({"results": [
        {"verbatim_id": "G60-1", "in_scope": True, "out_of_scope_reason": None, "signals": [
            {**sig, "quote": "the seats are hard"}, {**sig, "quote": "he said the seats are hard"}]},
        {"verbatim_id": "G60-999", "in_scope": True, "out_of_scope_reason": None, "signals": [{**sig, "quote": "x"}]},
    ]})
    stats = store(conn, chunk, batch, None, "m")
    assert stats == {"stored": 1, "signals": 2, "unverified_quotes": 1}
    assert [v["id"] for v in pending(conn, "G60", None)] == ["G60-2"]   # missing ID stays pending
    assert quote_ok("Seats are", "the  seats are hard") and not quote_ok("", "x")
