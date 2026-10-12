"""A/B benchmark: extract-v3 vs extract-v4 on one fixed stratified sample (aggregates only — no raw text, rule 1).

`uv run python scripts/benchmark_classify.py --make-sample`   writes data/eval/classify_ab_ids.json (source_item ids)
`uv run python scripts/benchmark_classify.py`                 compares both versions on that sample
"""

import json
import random
import re
import sys
from collections import Counter, defaultdict

from bmw_req.db import connect
from bmw_req.structure.taxonomy import quote_ok
from bmw_req.structure.classify import C_SEVERITY, D_PROMPT

SAMPLE = "data/eval/classify_ab_ids.json"
MAP = {"Likes": "like", "Defect": "defect", "Difficult to Use": "difficult_to_use", "Wants": "want"}
PURITY_TOPICS = ["Handling/Riding", "Seats", "Drivetrain", "Touch screen, operation"]


def items(conn):
    out = []
    for r in conn.execute("SELECT id, external_id, vehicle_model_id car, country, text, meta_json FROM source_item WHERE kind='feedback'"):
        m = json.loads(r["meta_json"])
        labels = m.get("bmw_labels") or []
        out.append({"id": r["id"], "ext": r["external_id"], "car": r["car"], "country": r["country"], "channel": m.get("channel"),
                    "types": {l["feedback_type"] for l in labels if l.get("feedback_type")},
                    "topics": {l.get("vfc_level2") for l in labels if l.get("vfc_level2")},
                    "c_sev": (C_SEVERITY.search(r["text"] or "") or [None, None])[1],
                    "d_prompt": bool(D_PROMPT.search(r["text"] or "")), "text": r["text"] or ""})
    return out


def make_sample(conn):
    rng = random.Random(2026)
    its = items(conn)
    by_ext = {i["ext"]: i["id"] for i in its}
    pick = set(by_ext[e] for e in json.load(open("data/eval/v3_val_ids.json")) if e in by_ext)
    pick |= {i["id"] for i in rng.sample([i for i in its if i["d_prompt"]], min(60, sum(i["d_prompt"] for i in its)))}
    pick |= {i["id"] for i in rng.sample([i for i in its if i["country"] == "KR"], 100)}
    pick |= {i["id"] for i in rng.sample([i for i in its if i["c_sev"]], 80)}
    strata = defaultdict(list)
    for i in its:
        strata[(i["channel"], i["car"], min(i["types"]) if i["types"] else None)].append(i["id"])
    keys = sorted(strata, key=str)
    while len(pick) < 400:
        k = keys[rng.randrange(len(keys))]
        pick.add(rng.choice(strata[k]))
    json.dump(sorted(pick), open(SAMPLE, "w"))
    print("sample", len(pick))


def compare(conn):
    ids = set(json.load(open(SAMPLE)))
    its = {i["id"]: i for i in items(conn) if i["id"] in ids}
    out = {}
    for v in ("extract-v3", "extract-v4"):
        ext = {r[0]: r[1] for r in conn.execute("SELECT source_item_id, in_scope FROM verbatim_extraction WHERE extractor_version = ?", (v,)) if r[0] in ids}
        sig = defaultdict(list)
        for r in conn.execute("SELECT source_item_id, feedback_type, category, severity, quote, aspect FROM signal WHERE extractor_version = ?", (v,)):
            if r[0] in ids:
                sig[r[0]].append(dict(r))
        hit, tot = Counter(), Counter()
        for i, it in its.items():
            if i not in ext:
                continue
            for t in it["types"]:
                if t in MAP:
                    tot[t] += 1
                    hit[t] += any(s["feedback_type"] == MAP[t] for s in sig[i])
        purity = {}
        for topic in PURITY_TOPICS:
            cats = Counter(s["category"] for i, it in its.items() if topic in it["topics"] for s in sig[i])
            purity[topic] = round(cats.most_common(1)[0][1] / sum(cats.values()), 2) if cats else None
        sev = {lvl: Counter(s["severity"] for i, it in its.items() if it["c_sev"] in lvls for s in sig[i] if s["feedback_type"] != "like")
               for lvl, lvls in (("serious", {"serious", "major", "significant"}), ("minor", {"minor"}))}
        allsig = [s for i in ext for s in sig[i]]
        per_ch = defaultdict(list)
        for i in ext:
            if ext[i]:
                per_ch[its[i]["channel"]].append(len(sig[i]))
        kr = [ext[i] for i in ext if its[i]["country"] == "KR"]
        out[v] = {
            "comments": len(ext), "signals": len(allsig),
            "bmw_recall": {t: round(hit[t] / tot[t], 3) for t in tot},
            "bmw_macro": round(sum(hit[t] / tot[t] for t in tot) / max(len(tot), 1), 3),
            "category_purity": purity,
            "sourceC_serious_high": round(sev["serious"]["high"] / max(sum(sev["serious"].values()), 1), 2),
            "sourceC_minor_low": round(sev["minor"]["low"] / max(sum(sev["minor"].values()), 1), 2),
            "quote_unverified": round(sum(not quote_ok(s["quote"], its[i]["text"]) for i in ext for s in sig[i]) / max(len(allsig), 1), 3),
            "quote_under_4_words": round(sum(len((s["quote"] or "").split()) < 4 for s in allsig) / max(len(allsig), 1), 3),
            "quote_has_survey_prompt": sum(bool(re.search(r"most improved about", s["quote"] or "", re.I)) for s in allsig),
            "signals_per_comment": {ch: round(sum(v_) / len(v_), 2) for ch, v_ in sorted(per_ch.items(), key=str)},
            "korea_in_scope": round(sum(kr) / max(len(kr), 1), 3),
            "aspect_coverage": round(sum(bool(s["aspect"]) and s["aspect"] != "other" for s in allsig) / max(len(allsig), 1), 3),
        }
    json.dump(out, open("data/eval/classify_ab.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    c = connect()
    make_sample(c) if "--make-sample" in sys.argv else compare(c)
