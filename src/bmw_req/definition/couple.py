"""Stage `couple` (D-048): links between requirements — the "roof of the House of Quality", at customer level.

Candidates are deterministic: two requirements that share ≥ 1 car line and draw on ≥ 1 common resource
(`domains.shared_resources` over their aspects: energy, mass, thermal, package, attention, aero, acoustic, compute).
Each requirement keeps at most MAX_NEIGHBOURS candidates (ranked by shared resources, then same zone) so the judge
never sees an everything-with-everything matrix; pairs whose primary aspects form a classic trade-off
(`domains.TENSIONS`: range × handling via mass, wheels × cabin noise via acoustic, …) are always added. luna judges each pair in batches — none | conflicts | competes_for |
enables | synergy, via one resource, strength 1–3, direction, a ≤ 25-word customer-level rationale (including when A's
stretch rung would hurt B). Conflicts and strength-3 links are re-checked by sol (low effort), which may weaken or drop
them. Code checks: `via` must be a RESOURCES key (else the first shared resource), `enables` must be directional, the
rest mutual by default. Links stay AI proposals; the PM confirms or removes them (`def_link_review`).
cp2: pairs touching a requirement whose define or spec version changed (or a new requirement) are re-judged; the
others carry their cp1 link forward. Tracks `link:<a>|<b>|<relation>` (weight = strength).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.definition.define import ensure, generate
from bmw_req.definition.domains import RESOURCES, TENSIONS, shared_resources
from bmw_req.llm import LLM
from bmw_req.structure.events import log

MAX_NEIGHBOURS = 10
MAX_TENSIONS = 4    # extra trade-off pairs per requirement beyond the cap
MAX_SOFT = 4        # pairs that share only attention / package / compute, per requirement
PHYSICAL = {"mass", "energy", "thermal", "aero", "acoustic"}
BATCH = 24
RECHECK_BATCH = 16
Resource = Literal["energy", "mass", "thermal", "package", "attention", "aero", "acoustic", "compute"]
assert set(Resource.__args__) == set(RESOURCES)


class Judgment(BaseModel):
    a: str
    b: str
    relation: Literal["none", "conflicts", "competes_for", "enables", "synergy"]
    via: Resource | None
    strength: int = Field(description="1 weak, 2 clear, 3 strong — 0 when relation is none")
    direction: Literal["a_to_b", "b_to_a", "mutual"]
    rationale: str = Field(description="≤ 25 words, customer level")


class Batch(BaseModel):
    judgments: list[Judgment]


INSTRUCTIONS = f"""You judge how pairs of proposed BMW customer requirements (successor cars) interact — the roof of a
House of Quality, at CUSTOMER level, never as engineering specs. Each pair shares a car line and at least one
resource:
{json.dumps(RESOURCES, indent=0)}

For each pair decide:
- none: no real interaction customers would notice (say none when the link is speculative).
- conflicts: RAISING A's target makes B measurably WORSE for the customer (direction a_to_b, b_to_a or mutual). E.g.
  "A larger, heavier battery for 700 km range blunts the agility customers love — via mass"; "19-21 inch wheels
  for the sporty look cost range and add road noise — via aero"; "faster DC charging and hard driving heat-load the
  car and slow cabin cool-down after a stop — via thermal".
- competes_for: both need the same FINITE space, energy, time or attention, but can be balanced without one getting
  worse by design. E.g. "rear legroom and boot volume share one wheelbase — via package"; "a big centre screen and
  physical buttons compete for the same dash area — via package".
- enables: A makes B possible or much easier (direction a_to_b or b_to_a). E.g. "an efficient heat pump keeps winter
  range up — via energy"; "over-the-air updates let assistance features improve after purchase — via compute".
- synergy: delivering one helps the other (mutual). E.g. "acoustic glazing makes the cabin quieter and the audio
  clearer — via acoustic"; "lighter body helps both handling and range — via mass".
Physical trade-offs (mass, energy, thermal, aero, acoustic) between range, performance, handling, ride, wheels,
charging and climate are usually REAL conflicts — do not soften them to competes_for.
via: the resource the interaction runs through (normally one of the pair's shared resources). strength: 1 weak,
2 clear, 3 strong. rationale: ≤ 25 words a product manager understands; if only A's STRETCH level would hurt B, say
so ("only at stretch: …"). Do not invent links: most pairs are none or weak."""

RECHECK = """You re-check proposed strong or conflicting links between BMW customer requirements (successor cars).
For each, return the corrected judgment: keep it, change strength or relation, or set relation 'none' only if the
interaction is speculative. Keep genuine physical trade-offs as conflicts. The original judge's rules:

""" + INSTRUCTIONS


def candidates(reqs: list[dict], max_n: int = MAX_NEIGHBOURS) -> list[tuple[str, str, list[str]]]:
    """Pairs sharing ≥ 1 line and ≥ 1 resource; greedy by (shared resources, same primary zone) under a per-requirement
    cap. Keys in each pair are sorted, so a pair is stable across checkpoints."""
    pairs = []
    for i, a in enumerate(reqs):
        for b in reqs[i + 1:]:
            if not set(a["lines"]) & set(b["lines"]):
                continue
            res = shared_resources(a["aspects"], b["aspects"])
            if not res:
                continue
            x, y = sorted((a, b), key=lambda r: r["key"])
            same_zone = bool(a["zones"] and b["zones"] and a["zones"][0] == b["zones"][0])
            score = 2 * sum(r in PHYSICAL for r in res) + len(res)   # physical trade-offs before attention/package
            pairs.append((score, same_zone, x["key"], y["key"], res))
    pairs.sort(key=lambda p: (-p[0], not p[1], p[2], p[3]))
    deg, soft, out = Counter(), Counter(), []
    for _, _, a, b, res in pairs:
        only_soft = not any(r in PHYSICAL for r in res)
        if deg[a] < max_n and deg[b] < max_n and (not only_soft or (soft[a] < MAX_SOFT and soft[b] < MAX_SOFT)):
            deg[a] += 1
            deg[b] += 1
            if only_soft:
                soft[a] += 1
                soft[b] += 1
            out.append((a, b, res))
    # classic trade-offs (domains.TENSIONS) between primary aspects are always judged, cap or not
    by, seen, extra = {r["key"]: r for r in reqs}, {(a, b) for a, b, _ in out}, Counter()
    for i, a in enumerate(reqs):
        for b in reqs[i + 1:]:
            x, y = sorted((a["key"], b["key"]))
            via = TENSIONS.get(frozenset((a["aspects"][0], b["aspects"][0]))) if a["aspects"] and b["aspects"] else None
            if via and (x, y) not in seen and set(a["lines"]) & set(b["lines"]) and a["aspects"][0] != b["aspects"][0] \
                    and extra[x] < MAX_TENSIONS and extra[y] < MAX_TENSIONS:
                extra[x] += 1
                extra[y] += 1
                out.append((x, y, list(dict.fromkeys([via, *shared_resources(by[x]["aspects"], by[y]["aspects"])]))))
    return out


def req_view(conn, run_spec: int | None, r) -> dict:
    spec = conn.execute("SELECT metric_json, ladder_json FROM def_spec WHERE run_id = ? AND req_key = ?", (run_spec, r["key"])).fetchone() if run_spec else None
    v = {"key": r["key"], "title": r["title"], "statement": r["statement"], "aspects": json.loads(r["aspects_json"]),
         "zones": json.loads(r["zones_json"]), "lines": json.loads(r["lines_json"]), "decision_type": r["decision_type"]}
    if spec:
        m, lad = json.loads(spec["metric_json"]), json.loads(spec["ladder_json"])
        v["metric"] = m["name"]
        top = lad[0] if lad else None
        if top:
            rec = top.get(top["recommended"]) or {}
            v["recommended"] = f"{top['line']} {top['market']}: {rec.get('text')}"
            if top.get("stretch"):
                v["stretch"] = top["stretch"].get("text")
    return v


def clean(j: Judgment, shared: list[str]) -> dict | None:
    if j.relation == "none" or j.strength < 1:
        return None
    via = j.via if j.via in RESOURCES else (shared[0] if shared else None)
    direction = j.direction
    if j.relation == "enables" and direction == "mutual":
        direction = "a_to_b"
    if j.relation in ("competes_for", "synergy"):
        direction = "mutual"
    return {"relation": j.relation, "via": via, "strength": max(1, min(3, j.strength)), "direction": direction,
            "rationale": j.rationale}


def run(conn, cp: str, actor: str = "system", pilot: int | None = None, llm: LLM | None = None) -> dict:
    ensure(conn)
    llm = llm or LLM(conn=conn)
    drun, srun = C.latest_run(conn, cp, "define"), C.latest_run(conn, cp, "specify")
    if drun is None or srun is None:
        raise C.CheckpointError(f"Run 'define' and 'specify' at {cp} first")
    rows = conn.execute("SELECT * FROM def_requirement WHERE run_id = ? ORDER BY key", (drun["id"],)).fetchall()
    views = {r["key"]: req_view(conn, srun["id"], r) for r in rows}
    cands = candidates(list(views.values()))
    run_id = parent = None
    if not pilot:
        conn.execute("BEGIN IMMEDIATE")
        run_id = C.start_run(conn, cp, "couple", actor)
        conn.execute("COMMIT")
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
    elif C.BY_ID[cp].parent_id:
        p = C.latest_run(conn, C.BY_ID[cp].parent_id, "couple")
        parent = p["id"] if p else None

    carried, todo = [], cands
    if parent:
        prun = conn.execute("SELECT stats_json FROM checkpoint_run WHERE id = ?", (parent,)).fetchone()
        up = json.loads(prun["stats_json"] or "{}").get("upstream", {})
        pver = {r[0]: r[1] for r in conn.execute("SELECT key, version FROM def_requirement WHERE run_id = ?", (up.get("define"),))}
        psv = {r[0]: r[1] for r in conn.execute("SELECT req_key, version FROM def_spec WHERE run_id = ?", (up.get("specify"),))}
        sv = {r[0]: r[1] for r in conn.execute("SELECT req_key, version FROM def_spec WHERE run_id = ?", (srun["id"],))}
        changed = {r["key"] for r in rows if pver.get(r["key"]) != r["version"] or psv.get(r["key"]) != sv.get(r["key"])}
        plinks = defaultdict(list)
        judged = set(json.loads(prun["stats_json"] or "{}").get("judged_pairs", []))
        for l in conn.execute("SELECT * FROM def_link WHERE run_id = ?", (parent,)):
            plinks[f"{l['a_key']}|{l['b_key']}"].append(dict(l))
        todo = []
        for a, b, res in cands:
            k = f"{a}|{b}"
            if a in changed or b in changed or (k not in plinks and k not in judged):
                todo.append((a, b, res))
            else:
                carried += plinks.get(k, [])
    if pilot:
        todo = todo[:pilot]
    else:
        log(conn, "couple", "start", {"requirements": len(rows), "candidates": len(cands), "to_judge": len(todo),
                                      "carried": len(carried)}, run_id)

    fast, smart = llm.model_for("fast"), llm.model_for("smart")
    links: dict[tuple, dict] = {}
    shared = {(a, b): res for a, b, res in todo}
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        keys = sorted({k for a, b, _ in chunk for k in (a, b)})
        payload = {"requirements": {k: {x: v for x, v in views[k].items() if x not in ("zones", "key")} for k in keys},
                   "pairs": [{"a": a, "b": b, "shared_resources": res} for a, b, res in chunk]}
        try:
            res = generate(llm, waits=(), job=f"couple:{cp}", tier="fast", instructions=INSTRUCTIONS, input=json.dumps(payload, ensure_ascii=False),
                               schema=Batch, reasoning_effort="low", max_output_tokens=12_000, flex=True)
            got = res.parsed.judgments if res.parsed else []
        except Exception as e:
            got = []
            if not pilot:
                log(conn, "couple", "batch_failed", {"pairs": len(chunk), "error": repr(e)[:300]}, run_id)
        for j in got:
            k = (j.a, j.b) if (j.a, j.b) in shared else (j.b, j.a) if (j.b, j.a) in shared else None
            if k is None:
                continue
            if k != (j.a, j.b):   # model swapped the pair: mirror the direction
                j.direction = {"a_to_b": "b_to_a", "b_to_a": "a_to_b"}.get(j.direction, j.direction)
            c = clean(j, shared[k])
            if c:
                links[k] = {**c, "method": "luna", "model": fast}
        if not pilot:
            log(conn, "couple", "judge", {"pairs": len(chunk), "links": sum(1 for a, b, _ in chunk if (a, b) in links)}, run_id, fast)

    strong = [k for k, l in links.items() if l["relation"] == "conflicts" or l["strength"] == 3]
    for i in range(0, len(strong), RECHECK_BATCH):
        chunk = strong[i:i + RECHECK_BATCH]
        keys = sorted({x for k in chunk for x in k})
        payload = {"requirements": {k: {x: v for x, v in views[k].items() if x not in ("zones", "key")} for k in keys},
                   "proposed": [{"a": a, "b": b, "shared_resources": shared[(a, b)], **{x: links[(a, b)][x] for x in
                                ("relation", "via", "strength", "direction", "rationale")}} for a, b in chunk]}
        try:
            res = generate(llm, job=f"couple:{cp}:recheck", tier="smart", instructions=RECHECK, input=json.dumps(payload, ensure_ascii=False),
                               schema=Batch, reasoning_effort="low", max_output_tokens=8_000, flex=True)
            got = res.parsed.judgments if res.parsed else []
        except Exception as e:
            got = []
            if not pilot:
                log(conn, "couple", "batch_failed", {"recheck": len(chunk), "error": repr(e)[:300]}, run_id)
        seen = set()
        for j in got:
            k = (j.a, j.b) if (j.a, j.b) in links else (j.b, j.a) if (j.b, j.a) in links else None
            if k is None or k in seen:
                continue
            seen.add(k)
            if k != (j.a, j.b):
                j.direction = {"a_to_b": "b_to_a", "b_to_a": "a_to_b"}.get(j.direction, j.direction)
            c = clean(j, shared[k])
            if c is None:
                links.pop(k)
            else:
                links[k] = {**c, "method": "luna+sol", "model": smart}
        if not pilot:
            log(conn, "couple", "recheck", {"links": len(chunk), "kept": sum(1 for k in chunk if k in links)}, run_id, smart)
    if pilot:
        return {"pilot": True, "candidates": len(cands), "judged": len(todo),
                "links": [{"a": a, "b": b, **l} for (a, b), l in links.items()]}

    out = [{"a_key": a, "b_key": b, **l} for (a, b), l in links.items()] + \
          [{k: l[k] for k in ("a_key", "b_key", "relation", "via", "strength", "direction", "rationale", "method", "model")}
           for l in carried if l["a_key"] in views and l["b_key"] in views]
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany("""INSERT OR IGNORE INTO def_link (run_id, a_key, b_key, relation, via, strength, direction, rationale, method, model)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         [(run_id, l["a_key"], l["b_key"], l["relation"], l["via"], l["strength"], l["direction"], l["rationale"],
                           l["method"], l["model"]) for l in out])
        ents = {f"link:{l['a_key']}|{l['b_key']}|{l['relation']}": (float(l["strength"]), {"via": l["via"]}) for l in out}
        tracks = C.write_tracks(conn, run_id, ents)
        stats = {"requirements": len(rows), "candidates": len(cands), "judged": len(todo), "carried": len(carried),
                 "links": len(out), "by_relation": dict(Counter(l["relation"] for l in out)),
                 "by_via": dict(Counter(l["via"] for l in out)), "rechecked": len(strong), "tracks": tracks,
                 "judged_pairs": [f"{a}|{b}" for a, b, _ in cands],
                 "upstream": {"define": drun["id"], "specify": srun["id"]}}
        C.finish_run(conn, run_id, stats)
        log(conn, "couple", "finish", {k: v for k, v in stats.items() if k != "judged_pairs"}, run_id)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **{k: v for k, v in stats.items() if k != "judged_pairs"}}
