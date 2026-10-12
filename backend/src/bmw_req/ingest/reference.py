"""Minimal reference rows the ingest needs (D-021). Markets and models are config, not code paths
(AGENTS rule 7). Platforms, plants, production and market profiles come later from the cited seed docs."""

import json

from bmw_req.db import Connection

EUROPE = [
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE",
    "IS", "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK",
]

MARKETS = [
    ("EU", "Europe", EUROPE),
    ("US", "United States", ["US"]),
    ("CN", "China", ["CN"]),
    ("RoW", "Rest of world", ["*"]),
]

BRANDS = [("BMW", "BMW", "BMW Group")]

# (id, brand, line, body)
VEHICLE_MODELS = [
    ("F70", "BMW", "1 Series", "hatchback"),
    ("G60", "BMW", "5 Series", "sedan"),
    ("G68", "BMW", "5 Series", "sedan, long wheelbase (China)"),
    ("G70", "BMW", "7 Series", "sedan"),
]


def seed(conn: Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO brand (id, name, brand_group) VALUES (?, ?, ?)", BRANDS
    )
    conn.executemany(
        "INSERT OR IGNORE INTO market (code, name, countries_json) VALUES (?, ?, ?)",
        [(code, name, json.dumps(countries)) for code, name, countries in MARKETS],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO vehicle_model (id, brand_id, line, body) VALUES (?, ?, ?, ?)", VEHICLE_MODELS
    )


def country_to_market(conn: Connection) -> callable:
    """Build a country → market-code lookup from the `market` rows; '*' is the catch-all."""
    exact, fallback = {}, None
    for row in conn.execute("SELECT code, countries_json FROM market"):
        for c in json.loads(row["countries_json"]):
            if c == "*":
                fallback = row["code"]
            else:
                exact[c] = row["code"]
    return lambda country: exact.get(country, fallback)


# --- Curated reference layer (knowledge-base.md layer 2) --------------------------------------------------

def _j(v):
    return None if v is None else json.dumps(v, ensure_ascii=False, sort_keys=True)


def load_reference(conn: Connection) -> dict:
    """Load `bmw_req.reference_data` idempotently: sources → source_item(kind='reference'), then platforms,
    plants, production, brands, vehicle models (BMW + competitors) and market profiles, each pointing at the
    source_item ids. Writes one audit_event (actor 'system', action 'load_reference') when content changed."""
    import hashlib

    from bmw_req import reference_data as rd

    payload = {k: getattr(rd, k) for k in ("SOURCES", "PLATFORMS", "PLANTS", "PRODUCTION", "BRANDS",
                                           "BMW_MODELS", "COMPETITOR_MODELS", "MARKET_PROFILES")}
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
    last = conn.execute("SELECT new_value FROM audit_event WHERE action = 'load_reference' ORDER BY id DESC LIMIT 1").fetchone()
    seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        batch = conn.execute("SELECT id FROM ingest_batch WHERE kind = 'reference' AND description = ?",
                             (f"curated reference layer {digest}",)).fetchone()
        batch_id = batch["id"] if batch else conn.execute(
            "INSERT INTO ingest_batch (kind, description, file) VALUES ('reference', ?, 'backend/src/bmw_req/reference_data.py') RETURNING id",
            (f"curated reference layer {digest}",)).fetchone()[0]
        ids = {}
        for key, (ref, url, published, tier, text, unverified) in rd.SOURCES.items():
            meta = _j({"key": key, "unverified": unverified, "origin_doc": ref.split("#")[0]})
            conn.execute(
                """INSERT INTO source_item (kind, ref, external_id, trust_tier, url, published_at, text, meta_json, ingest_batch_id)
                   VALUES ('reference', ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(kind, ref) DO UPDATE SET external_id=excluded.external_id, trust_tier=excluded.trust_tier,
                     url=excluded.url, published_at=excluded.published_at, text=excluded.text, meta_json=excluded.meta_json""",
                (ref, key, tier, url, published, text, meta, batch_id))
            ids[key] = conn.execute("SELECT id FROM source_item WHERE kind = 'reference' AND ref = ?", (ref,)).fetchone()["id"]

        def sids(keys):
            missing = [k for k in keys if k not in ids]
            if missing:
                raise KeyError(f"unknown reference source keys: {missing}")
            return _j([ids[k] for k in keys])

        for pid, owner, pts, intro, out, succ, src in rd.PLATFORMS:
            conn.execute(
                """INSERT INTO platform (id, owner_brand_group, powertrains_json, introduced, phase_out, successor_platform_id, source_ids_json)
                   VALUES (?, ?, ?, ?, ?, NULL, ?) ON CONFLICT(id) DO UPDATE SET owner_brand_group=excluded.owner_brand_group,
                   powertrains_json=excluded.powertrains_json, introduced=excluded.introduced, phase_out=excluded.phase_out,
                   source_ids_json=excluded.source_ids_json""",
                (pid, owner, _j(pts), intro, out, sids(src)))
        for pid, *_rest in rd.PLATFORMS:
            conn.execute("UPDATE platform SET successor_platform_id = ? WHERE id = ?", (_rest[4], pid))

        for pid, name, city, country, plats, pts, nk, cap, src in rd.PLANTS:
            conn.execute(
                """INSERT INTO plant (id, name, city, country, platforms_json, powertrains_json, nk_ready_from, capacity_note, source_ids_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, city=excluded.city,
                   country=excluded.country, platforms_json=excluded.platforms_json, powertrains_json=excluded.powertrains_json,
                   nk_ready_from=excluded.nk_ready_from, capacity_note=excluded.capacity_note, source_ids_json=excluded.source_ids_json""",
                (pid, name, city, country, _j(plats), _j(pts), nk, cap, sids(src)))

        for bid, name, group, pos, values, guard, src in rd.BRANDS:
            conn.execute(
                """INSERT INTO brand (id, name, brand_group, positioning, core_values_json, guardrails_json, source_ids_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, brand_group=excluded.brand_group,
                   positioning=excluded.positioning, core_values_json=excluded.core_values_json,
                   guardrails_json=excluded.guardrails_json, source_ids_json=excluded.source_ids_json""",
                (bid, name, group, pos, _j(values), _j(guard), sids(src)))

        for mid, f in rd.BMW_MODELS.items():
            conn.execute(
                """UPDATE vehicle_model SET segment=?, platform_id=?, generation=?, sop=?, powertrains_json=?,
                   market_variants_json=?, profile_json=?, source_ids_json=?, is_bmw_group=1 WHERE id=?""",
                (f["segment"], f["platform_id"], f["generation"], f["sop"], _j(f["powertrains"]),
                 _j(f["market_variants"]), _j(f["profile"]), sids(f["sources"]), mid))
        for mid, brand, line, body, seg, pts, vs, markets, prof, src in rd.COMPETITOR_MODELS:
            conn.execute(
                """INSERT INTO vehicle_model (id, brand_id, line, body, segment, powertrains_json, is_bmw_group, profile_json, source_ids_json)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?) ON CONFLICT(id) DO UPDATE SET brand_id=excluded.brand_id, line=excluded.line,
                   body=excluded.body, segment=excluded.segment, powertrains_json=excluded.powertrains_json, is_bmw_group=0,
                   profile_json=excluded.profile_json, source_ids_json=excluded.source_ids_json""",
                (mid, brand, line, body, seg, _j(pts), _j({**prof, "competes_with": vs, "markets": markets}), sids(src)))

        conn.execute("DELETE FROM production WHERE vehicle_model_id IN (%s)" % ",".join("?" * len(rd.BMW_MODELS)),
                     list(rd.BMW_MODELS))
        for mid, plant, variant, markets, since, until, src in rd.PRODUCTION:
            conn.execute(
                """INSERT INTO production (vehicle_model_id, plant_id, market_variant, markets_served_json, since, until, source_ids_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""", (mid, plant, variant, _j(markets), since, until, sids(src)))

        for code, p in rd.MARKET_PROFILES.items():
            conn.execute(
                """UPDATE market SET climate=?, usage_patterns=?, cultural_expectations=?, infrastructure=?, powertrain_mix=?,
                   profile_source_ids_json=?, profile_valid_from='2026-10-10' WHERE code=?""",
                (p["climate"], p["usage_patterns"], p["cultural_expectations"], p["infrastructure"], p["powertrain_mix"],
                 sids(p["sources"]), code))

        counts = {"sources": len(rd.SOURCES), "platforms": len(rd.PLATFORMS), "plants": len(rd.PLANTS),
                  "production": len(rd.PRODUCTION), "brands": len(rd.BRANDS), "bmw_models": len(rd.BMW_MODELS),
                  "competitor_models": len(rd.COMPETITOR_MODELS), "market_profiles": len(rd.MARKET_PROFILES)}
        changed = last is None or json.loads(last["new_value"]).get("digest") != digest
        if changed:
            conn.execute(
                """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, old_value, new_value, rationale)
                   VALUES ('system', 'ingest.reference', 'load_reference', 'reference_layer', 'reference_data', ?, ?, ?)""",
                (last["new_value"] if last else None, _j({"digest": digest, **counts}),
                 "Curated reference layer loaded from cited seed docs; status proposed - PM must accept reference facts and brand guardrails."))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {**counts, "changed": changed}


if __name__ == "__main__":
    from bmw_req.db import connect

    print(load_reference(connect()))
