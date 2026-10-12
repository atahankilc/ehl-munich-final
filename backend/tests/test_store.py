"""Schema and feedback-ingest tests on synthetic data (no BMW data, no paid calls)."""

import json

import openpyxl
import psycopg
import pytest

from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.ingest.feedback import SHEET, ingest_feedback

HEADER = ["ID", "Source", "Brand", "Sales Description", "Country", "Derivate (e-code)", "Engine Type",
          "Feedback Type", "Customer Feedback", "Vfc level2 3 Name", "Vfc level2 Name", "Vfc level3 Name"]


@pytest.fixture
def conn(pg_url):
    c = connect()
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
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        conn.execute("UPDATE audit_event SET action = 'z'")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
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
