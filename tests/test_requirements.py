"""Derivation validation, portfolio consolidation and storage (fake LLM, no paid calls)."""

from types import SimpleNamespace

from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.pipeline import requirements as R


def draft(title, targets, findings, **kw):
    base = dict(title=title, description="d", category="Interior", target_metric="≥ 95 % in 5 s", acceptance_criteria="clinic",
                horizon="today", horizon_reason="r", kano_class="basic", kano_drift="stable", must_not_lose=False,
                effort="S", effort_reason="r", supporting_finding_ids=findings, conflicting_finding_ids=[],
                conflicting_evidence="none found", evidence_summary="e", assumptions=["a"], uncertainties=["u"],
                targets=[dict(vehicle_model_id=d, market_code=m, realization="platform_wide", market_note="n") for d, m in targets])
    base.update(kw)
    return R.RequirementDraft.model_validate(base)


def test_validate_drops_unknown_ids_targets_and_empty_drafts():
    res = R.DerivationResult(requirements=[
        draft("ok", [("G60", "US"), ("G60", "CN")], [1, 99]),     # CN is not a G60 target; 99 unknown
        draft("no evidence", [("G60", "US")], [99]),
    ])
    ok, problems = R.validate(res, {1, 2}, ["G60", "G68"])
    assert [d.title for d in ok] == ["ok"]
    assert ok[0].supporting_finding_ids == [1]
    assert [(t.vehicle_model_id, t.market_code) for t in ok[0].targets] == [("G60", "US")]
    assert any("DROPPED" in p for p in problems)


class FakeLLM:
    def __init__(self, groups):
        self.groups = groups

    def generate(self, **kw):
        return SimpleNamespace(parsed=R.MergeResult(groups=[R.MergeGroup(**g) for g in self.groups]), cost_usd=0.0)

    def model_for(self, tier):
        return "fake"


def test_consolidate_unions_targets_and_evidence_across_lines():
    drafts = [("5 Series", draft("Tactile controls 5", [("G60", "US")], [1], effort="M")),
              ("7 Series", draft("Tactile controls 7", [("G70", "US"), ("G70", "CN")], [2], effort="S")),
              ("1 Series", draft("Other need", [("F70", "EU")], [3]))]
    llm = FakeLLM([dict(members=[0, 1], title="Tactile controls", description="d", target_metric="m",
                        acceptance_criteria="a", reason="same need")])
    merged, notes = R.consolidate(llm, drafts, job="t")
    assert len(merged) == 2 and notes
    m = merged[0]
    assert m.title == "Tactile controls"
    assert {(t.vehicle_model_id, t.market_code) for t in m.targets} == {("G60", "US"), ("G70", "US"), ("G70", "CN")}
    assert m.supporting_finding_ids == [1, 2] and m.effort == "M"


def test_store_creates_proposed_requirement_with_audit():
    conn = connect(":memory:")
    reference.seed(conn)
    conn.execute("""INSERT INTO finding (id, type, title, scope_level, vehicle_model_id, created_by, source_kind)
                    VALUES (1, 'defect', 'f', 'derivative', 'G60', 't', 'verbatim')""")
    ids = R.store(conn, [draft("Tactile controls", [("G60", "US")], [1])], model="fake", usage_id=None, wave=1)
    r = conn.execute("SELECT * FROM requirement WHERE id = ?", (ids[0],)).fetchone()
    assert r["status"] == "proposed" and r["created_by"] == "ai:fake"
    actions = [a[0] for a in conn.execute("SELECT action FROM audit_event WHERE entity_id = ?", (ids[0],))]
    assert actions == ["create", "add_target", "link_findings"]
