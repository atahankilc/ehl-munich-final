"""Stage `classify` (D-043, extract-v4): every comment → signals in the shared aspect space, per checkpoint.

Improvements over extract-v3 (review 2026-10-11): fixed aspect list shared with study/research/options; intensity
(how strongly) separate from impact (what it does to ownership); one signal per (aspect, nature); deterministic hints
per comment (channel, engine, Source C self-reported severity, Source D survey-prompt text that is NOT the customer's
words); quotes ≥ 4 words; a cacheable ~2k-token prefix; 20 comments per luna Flex call.

Classification is per item and does not depend on time: the cp1 run classifies cp1-visible comments, the cp2 run
(parent = cp1 run) classifies only the delta and carries cp1 results forward as `held` tracks.

`uv run python -m bmw_req.structure.classify --sample data/eval/classify_ab_ids.json`   (A/B sample, no run id)
`uv run python -m bmw_req.structure.classify --checkpoint cp1`                           (then cp2)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

import openai
from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.llm import LLM, BudgetExceeded
from bmw_req.structure.taxonomy import quote_ok
from bmw_req.structure.taxonomy import ALL_ASPECTS, CATEGORIES, CATEGORY_OF, CONTEXTS, FEEDBACK_TYPE, SEVERITY, taxonomy_text

VERSION = "extract-v4"
BATCH = 20
RETRIES = 4

Aspect = Literal[tuple(ALL_ASPECTS)]  # type: ignore[valid-type]
Category = Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
Context = Literal[tuple(CONTEXTS)]  # type: ignore[valid-type]


class SignalV4(BaseModel):
    category: Category
    aspect: Aspect
    component: str = Field(description="Short lower-case component, e.g. 'rear headrest', 'wireless charger'")
    nature: Literal["like", "defect", "usability", "performance_gap", "missing_feature", "support_question"]
    want_kind: Literal["new_feature", "improvement", "exists_elsewhere", "variant_availability"] | None
    intensity: Literal[1, 2, 3] = Field(description="1 mild, 2 clear, 3 strong — for likes and pains alike")
    impact: Literal["none", "annoyance", "impaired", "unusable", "safety"]
    occupant: Literal["driver", "front", "rear", "all", "unknown"]
    context: list[Context]
    benchmark: Literal["none", "previous_bmw", "competitor", "phone_tech"]
    benchmark_name: str | None
    future_cue: bool = Field(description="Rising expectation or comparison to newer technology")
    explicit: bool = Field(description="The customer states the need; false if it is inferred")
    need_statement: str = Field(description="Solution-neutral customer need in one sentence")
    quote: str = Field(description="Contiguous span of the customer's own words, at least 4 words")


class CommentResult(BaseModel):
    comment_id: str
    in_scope: bool
    out_of_scope_reason: str | None
    signals: list[SignalV4]


class Batch(BaseModel):
    results: list[CommentResult]


INSTRUCTIONS = f"""You classify customer comments about a BMW car for product-requirements work. For EVERY comment in the
input return exactly one result with its comment_id. Do not invent facts.

SCOPE. Customer-facing topics only: features, equipment, comfort, space, usability, infotainment, design and quality
perception, driving experience, range and charging as experienced, variants and packages. Out of scope: dealer,
service, sales, pricing, financing, recalls handling, regulation, engineering specs, charging-network operators.
Mixed comments: extract every in-scope signal. If nothing is in scope or the comment has no usable content, set
in_scope=false with a short out_of_scope_reason and no signals.

SIGNALS. One signal per (aspect, nature) per comment, at most 6. Merge repeated mentions of the same aspect.

ASPECT — choose exactly one from this fixed list; category must be the aspect's parent:
{taxonomy_text()}
Tie-breaks: ride smoothness, bumps, road noise → Comfort & Space (ride_comfort / cabin_noise); how the car feels to
drive, steering, agility → Driving Experience; engine/motor sound, gearbox, smoothness of the drive unit → Powertrain;
screens, menus, iDrive → display_ui; physical buttons and their placement → controls_layout; squeaks and rattles →
squeaks_rattles, not cabin_noise.

NATURE:
- like: praise (also "must not lose").
- defect: broken, faulty or behaves wrongly (drops, opens by itself, warning without cause).
- usability: works as designed but hard to understand or operate.
- performance_gap: works as designed but not good enough (seats firm, cools slowly, too noisy, range short).
- missing_feature: asks for something the car does not have (want_kind: new_feature | improvement |
  exists_elsewhere = they saw it in another car or phone | variant_availability = wants a trim/body/powertrain/option
  that is not offered in their market).
- support_question: they asked how a function works or needed help to set it up (weak usability evidence).
Requests: when the customer phrases it as a wish or request ("I wish", "would like", "should have", "please add",
"needs a ...", "it would be nice if"), use missing_feature (want_kind improvement if a weaker version exists, else
new_feature), even if it is also a complaint. performance_gap is for dissatisfaction stated without a request.
want_kind is null unless nature is missing_feature.

INTENSITY (1 mild, 2 clear, 3 strong) measures how strongly the customer feels, for likes as much as for pains
("love", "best car ever" = 3; "nice" = 1). IMPACT measures what it does to ownership: none (likes), annoyance,
impaired (a function is degraded), unusable (cannot use it), safety. If a hint gives reported_severity, let it inform
impact but do not copy it blindly.

OCCUPANT: who is affected. CONTEXT: only conditions the comment states. BENCHMARK: only if the customer compares
with a previous BMW, a competitor car, or phone/consumer tech (name it).
future_cue: the customer expects more because newer tech or other products already do it.
explicit: true if the customer states the need; false if you infer it.

QUOTE: copy a contiguous span of the customer's own words, character for character, at least 4 words. A hint
`survey_prompt` marks template text that the survey inserted — never quote it and never treat it as a need.
need_statement: the underlying need in customer terms, not a technical solution.

EXAMPLES (invented):
1. "Rear seats are way too upright for my teenagers on long trips, they complain every time." →
   Comfort & Space / seat_comfort; nature performance_gap; intensity 2; impact annoyance;
   occupant rear; context [long_distance]; quote "Rear seats are way too upright".
2. "Love the sound system, absolutely incredible." → audio; like; intensity 3; impact none; occupant all.
3. "Customer stated CarPlay disconnects several times per drive." → phone_projection; defect; intensity 2;
   impact impaired; occupant driver.
4. "Why can't I start the climate from my phone like my wife's Tesla?" → app_remote; missing_feature;
   want_kind exists_elsewhere; benchmark competitor "Tesla"; future_cue true.
5. "Customer asked how to turn off the lane departure warning." → safety_warnings; support_question; intensity 1;
   impact annoyance.
6. "The X package is not available with the 4-cylinder in the US." → equipment_availability; missing_feature;
   want_kind variant_availability.
7. "Dealer never called me back." → in_scope false (dealer).
8. "Great car." → in_scope false (no topic).
"""

def severity(impact: str, intensity: int) -> str:
    """Backward-compatible severity: high = unusable / safety, or impaired at the strongest intensity."""
    if impact in ("unusable", "safety") or (impact == "impaired" and intensity >= 3):
        return "high"
    return SEVERITY[impact]


# ------------------------------------------------------------------------------------------------ hints
C_SEVERITY = re.compile(r"\bI had an? (minor|serious|significant|major) problem\b", re.I)
D_PROMPT = re.compile(r"(that is the one thing (that )?could be most improved about the [^.]*\.?)", re.I)


def hints(text: str, meta: dict) -> dict:
    h = {"channel": meta.get("channel"), "engine": meta.get("engine")}
    m = C_SEVERITY.search(text or "")
    if m:
        h["reported_severity"] = m.group(1).lower()
    d = D_PROMPT.search(text or "")
    if d:
        h["survey_prompt"] = d.group(1)
    return h


def quote_good(q: str, text: str, survey_prompt: str | None) -> bool:
    if not quote_ok(q, text) or len(q.split()) < 4:
        return False
    if not survey_prompt:
        return True
    sp, ql = survey_prompt.lower(), q.lower().strip(" .")
    return ql not in sp and sp[:30] not in ql   # neither a piece of the survey prompt nor containing it


# ------------------------------------------------------------------------------------------------ run
_local = threading.local()


def _llm() -> LLM:
    if not hasattr(_local, "llm"):
        _local.llm = LLM(conn=connect())
    return _local.llm


def classify_batch(llm: LLM, items: list[dict], job: str):
    payload = [{"comment_id": it["key"], "hints": it["hints"], "text": it["text"]} for it in items]
    res = llm.generate(job=job, tier="fast", instructions=INSTRUCTIONS, input=json.dumps(payload, ensure_ascii=False),
                       schema=Batch, reasoning_effort="low", max_output_tokens=16_000, flex=True)
    return res.parsed, res


def store(conn, items: list[dict], batch: Batch, usage_id, model: str, run_id: int | None) -> dict:
    by_key = {it["key"]: it for it in items}
    seen, n_sig, bad = set(), 0, 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for r in batch.results:
            it = by_key.get(r.comment_id)
            if it is None or r.comment_id in seen:
                continue
            seen.add(r.comment_id)
            conn.execute("INSERT INTO verbatim_extraction (source_item_id, extractor_version, in_scope, out_of_scope_reason,"
                         " llm_usage_id, classify_run_id) VALUES (?, ?, ?, ?, ?, ?)",
                         (it["id"], VERSION, int(r.in_scope), r.out_of_scope_reason, usage_id, run_id))
            for s in r.signals[:6]:
                ok = quote_good(s.quote, it["text"], it["hints"].get("survey_prompt"))
                bad += not ok
                cat = CATEGORY_OF.get(s.aspect, s.category)
                conn.execute(
                    """INSERT INTO signal (source_item_id, extractor_version, category, topic, feedback_type, severity,
                         need_statement, quote, quote_verified, llm_usage_id, support_question, aspect, nature, want_kind,
                         intensity, impact, occupant, context_json, benchmark, benchmark_name, future_cue, explicit,
                         classify_run_id, source_kind)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'feedback')""",
                    (it["id"], VERSION, cat, s.component, FEEDBACK_TYPE[s.nature], severity(s.impact, s.intensity), s.need_statement,
                     s.quote, int(ok), usage_id, int(s.nature == "support_question"), s.aspect, s.nature, s.want_kind,
                     s.intensity, s.impact, s.occupant, json.dumps(s.context), s.benchmark, s.benchmark_name,
                     int(s.future_cue), int(s.explicit), run_id))
                n_sig += 1
        conn.execute("""INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, model, prompt_ref)
                        VALUES ('ai', 'structure.classify', 'classify_comments', 'llm_usage', ?, ?, ?, ?)""",
                     (str(usage_id), json.dumps({"comments": len(seen), "signals": n_sig, "unverified_quotes": bad}),
                      model, VERSION))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"stored": len(seen), "signals": n_sig, "bad_quotes": bad, "missing": len(set(by_key) - seen)}


def pending(conn, ids: list[int] | None = None, checkpoint: str | None = None) -> list[dict]:
    q = """SELECT s.id, s.external_id, s.text, s.meta_json FROM source_item s WHERE s.kind = 'feedback'
           AND NOT EXISTS (SELECT 1 FROM verbatim_extraction e WHERE e.source_item_id = s.id AND e.extractor_version = ?)"""
    args: list = [VERSION]
    if checkpoint:
        q += " AND s.checkpoint = ?"
        args.append(checkpoint)
    rows = conn.execute(q + " ORDER BY s.id", args).fetchall()
    if ids is not None:
        want = set(ids)
        rows = [r for r in rows if r["id"] in want]
    out = []
    for r in rows:
        meta = json.loads(r["meta_json"] or "{}")
        out.append({"id": r["id"], "key": r["external_id"], "text": r["text"] or "", "hints": hints(r["text"] or "", meta)})
    return out


def run(items: list[dict], job: str, run_id: int | None, cap_usd: float, workers: int = 12) -> dict:
    first = connect().execute("SELECT COALESCE(MAX(id), 0) FROM llm_usage").fetchone()[0]

    def spent() -> float:   # each worker thread reads through its own connection (sqlite3 is not thread-safe)
        return _llm().conn.execute("""SELECT COALESCE(SUM(CASE WHEN status='reserved' THEN reserved_usd ELSE cost_usd END),0)
                                      FROM llm_usage WHERE job = ? AND id > ?""", (job, first)).fetchone()[0]
    chunks = [items[i:i + BATCH] for i in range(0, len(items), BATCH)]
    totals = {"stored": 0, "signals": 0, "bad_quotes": 0, "missing": 0, "failed": 0}
    t0 = time.time()

    def work(chunk):
        llm = _llm()
        for attempt in range(RETRIES):
            if spent() > cap_usd:
                raise BudgetExceeded(f"run cap ${cap_usd} reached")
            try:
                batch, res = classify_batch(llm, chunk, job)
                if batch is None:          # truncated / refused structured output: retry the chunk
                    continue
                return store(llm.conn, chunk, batch, res.usage_id, llm.model_for("fast"), run_id)
            except (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError, openai.APIConnectionError):
                time.sleep(10 * 2 ** attempt + random.random() * 5)
        return {"failed": 1}

    with ThreadPoolExecutor(workers) as pool:
        futs = [pool.submit(work, c) for c in chunks]
        for n, f in enumerate(as_completed(futs), 1):
            try:
                r = f.result()
            except BudgetExceeded as e:
                print("ABORT", e, flush=True)
                for o in futs:
                    o.cancel()
                break
            except Exception as e:   # parse failure etc.: the chunk stays pending
                totals["failed"] += 1
                print(f"[{n}/{len(chunks)}] FAILED {e!r:.200}", flush=True)
                continue
            for k, v in r.items():
                totals[k] = totals.get(k, 0) + v
            if n % 10 == 0 or n == len(chunks):
                print(f"[{n}/{len(chunks)}] {time.time() - t0:.0f}s spend ${spent():.4f} {totals}", flush=True)
    totals["cost_usd"] = round(spent(), 4)
    return totals


def run_checkpoint(cp: str, actor: str = "system", cap_usd: float = 1.0) -> dict:
    """Classify the comments that become visible at `cp` (cp2 = delta only), attach earlier v4 rows of the same
    items to this run, and write tracks: one per classified comment (weight = in-scope signal count)."""
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    run_id = C.start_run(conn, cp, "classify", actor)
    conn.execute("COMMIT")
    todo = pending(conn, checkpoint=cp)
    print(f"{cp}: {len(todo)} comments to classify", flush=True)
    stats = run(todo, f"classify:{VERSION}:{cp}", run_id, cap_usd) if todo else {}
    conn.execute("BEGIN IMMEDIATE")
    try:
        # items classified earlier (A/B sample) that belong to this checkpoint join this run
        conn.execute("""UPDATE verbatim_extraction SET classify_run_id = ? WHERE extractor_version = ? AND classify_run_id IS NULL
                        AND source_item_id IN (SELECT id FROM source_item WHERE checkpoint = ?)""", (run_id, VERSION, cp))
        conn.execute("""UPDATE signal SET classify_run_id = ? WHERE extractor_version = ? AND classify_run_id IS NULL
                        AND source_item_id IN (SELECT id FROM source_item WHERE checkpoint = ?)""", (run_id, VERSION, cp))
        vis = C.visible_ids(cp)
        q = ",".join("?" * len(vis))
        entities = {f"classified:feedback:{r['id']}": (float(r["n"]), None) for r in conn.execute(
            f"""SELECT s.id, COUNT(g.id) n FROM source_item s JOIN verbatim_extraction e ON e.source_item_id = s.id
                AND e.extractor_version = ? LEFT JOIN signal g ON g.source_item_id = s.id AND g.extractor_version = ?
                WHERE s.kind = 'feedback' AND s.checkpoint IN ({q}) GROUP BY s.id""", (VERSION, VERSION, *vis))}
        tracks = C.write_tracks(conn, run_id, entities)
        C.finish_run(conn, run_id, {**stats, "tracks": tracks})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats, "tracks": tracks}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="JSON list of source_item ids (A/B test; no run id)")
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"])
    ap.add_argument("--cap-usd", type=float, default=1.0)
    a = ap.parse_args()
    if a.sample:
        print(run(pending(connect(), ids=json.load(open(a.sample))), f"classify:{VERSION}:ab", None, a.cap_usd))
    elif a.checkpoint:
        print(json.dumps(run_checkpoint(a.checkpoint, cap_usd=a.cap_usd), indent=1))
