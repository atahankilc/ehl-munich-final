"""Ingest `{F70,G60,G70}_OptionList.PDF` (German price lists, data-inventory §4).

`pdftotext -layout` per page (deterministic); equipment pages are then structured by the cheap model
(one Flex call per page). Each item keeps the exact PDF line it came from; `line_verified` says whether
that line is really on the page (whitespace-normalized). One `source_item` (kind 'option_list') per item,
deduped within a model. Prices are stored as information only (pricing is out of scope).
Re-runs are free (LLM cache) and idempotent (UNIQUE(kind, ref)).

`uv run python -m bmw_req.ingest.options [F70 G60 G70] [--pages 6,17] [--dry-run]`
"""

import argparse
import json
import re
import sqlite3
import subprocess
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import openai
from pydantic import BaseModel, Field

from bmw_req.ingest.common import audit_batch, existing_refs, open_batch
from bmw_req.pipeline.extract import Category

WAVE = 1
MARKET = "EU"                 # German market list
LIST_LABEL = "DE price list Jul 2026"
FILE_PATTERN = "{model}_OptionList.PDF"
MAX_OUTPUT_TOKENS = 16_000
WORKERS = 8
RETRIES = 3

# Page heading (first non-empty line) → section. Pages with other headings (prices, colours, technical
# data, dimensions, BMW Welt, recycling) are skipped.
SECTIONS = [
    (re.compile(r"^AUSGEWÄHLTE SERIENAUSSTATTUNGEN"), "standard_equipment"),
    (re.compile(r"^M SPORT DESIGN"), "package"),
    (re.compile(r"^M SPORTPAKET"), "package"),
    (re.compile(r"^SONDERAUSSTATTUNGEN"), "options"),
    (re.compile(r"^RÄDER UND REIFEN"), "wheels"),
    (re.compile(r"^[\w ]*\bxDRIVE\.$"), "model_equipment"),    # e.g. 'M135 xDRIVE.', 'i5 M60 xDRIVE.'
]

ASSUMPTION = ("German-market list. Equipment for US/CN is assumed comparable — an assumption, not evidence "
              "(data-inventory §4).")
PRICE_NOTE = "Price is information only; pricing/business cases are out of scope."


class OptionItem(BaseModel):
    name_de: str = Field(description="Equipment name exactly as in the list (German)")
    name_en: str = Field(description="English translation of the name")
    category: Category
    availability: Literal["standard", "optional", "package"] = Field(
        description="standard = series equipment (■) of at least one model; optional = orderable option (□ / price);"
                    " package = an equipment package itself or an item that is only available inside a package")
    package_name: str | None = Field(description="Package this item belongs to (e.g. 'M Sportpaket', 'Comfort Paket'),"
                                                 " else null")
    option_code: str | None = Field(description="SA-Nr. option code if shown (e.g. '7EW'), else null")
    applies_to: list[str] = Field(description="Model variants the page marks this for (column headers); empty if all"
                                              " or unclear")
    price_eur: float | None = Field(description="Price in EUR incl. VAT as printed (2.400,– → 2400), else null")
    source_line: str = Field(description="The exact line of the page text the item name comes from, copied verbatim")


class OptionPage(BaseModel):
    items: list[OptionItem]


INSTRUCTIONS = """You structure one page of a German BMW price list (text from `pdftotext -layout`) into equipment items.
Return every customer-facing equipment item on the page: standard equipment, options, packages and package contents,
wheels. Skip column headers, prices-only lines, footnotes, legal text, paint/upholstery colour names, and technical data.
Rules:
- Matrix columns are model variants; ■ = standard for that variant, □ = optional. Use the column positions to fill
  applies_to only when clear; else leave it empty.
- A package header line (e.g. 'COMFORT PAKET  7VB  2.750,–') is one item with availability 'package'; its listed contents
  ('– Sitzheizung vorn und hinten') are items with availability 'package' and package_name set. On M Sportpaket / M Sport
  Design / model pages, items are contents of that package or model (package_name = the page's package/model name).
- Merge a name with its indented continuation lines into one item, but source_line must be ONE exact line from the page
  (the line holding the name), copied character for character without the trailing ■/□ marks and prices.
- category: pick the closest customer-facing category; wheels → Exterior; assistance systems → Driver Assistance
  (as experienced); seats/climate/space → Comfort & Space; displays/apps/audio → Infotainment & Digital;
  materials/trims/lighting design → Design & Quality Perception; packages → Variants & Packages.
- Footnote markers glued to names ('BMW Maps5', 'Vehicle Apps6') are not part of the name: drop them in name_de and
  name_en (source_line stays exactly as printed).
- Prices: EUR incl. VAT (the first number, not the [bracketed] net price); '–,–' = 0; none shown = null."""

_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", " ": " "})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace("­", "").translate(_DASHES)
    return re.sub(r"\s+", " ", s).strip().casefold()


def line_ok(line: str, page_text: str) -> bool:
    """`line` occurs in the page text (whitespace, soft hyphens, dashes and case normalized)."""
    n = norm(line)
    return bool(n) and n in norm(page_text)


def slug(s: str, max_len: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ß", "ss")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:max_len] or "item"


def pdf_pages(path: Path) -> list[str]:
    info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=True).stdout
    n = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    return [
        subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(path), "-"],
                       capture_output=True, text=True, check=True).stdout
        for p in range(1, n + 1)
    ]


def page_section(text: str) -> str | None:
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    for pattern, section in SECTIONS:
        if pattern.search(first):
            return section
    return None


def page_heading(text: str) -> str:
    return next((ln.strip() for ln in text.splitlines() if ln.strip()), "").rstrip(".")


def extract_page(llm, model: str, page_no: int, text: str):
    return llm.generate(
        job=f"ingest:options:{model}", tier="fast", schema=OptionPage, reasoning_effort="low", flex=True,
        max_output_tokens=MAX_OUTPUT_TOKENS, instructions=INSTRUCTIONS,
        input=f"Model: BMW {model}. Page {page_no}, section '{page_heading(text)}'.\n\n{text}",
    )


def build_rows(model: str, file_name: str, pages: dict[int, str], results: dict[int, tuple]) -> list[dict]:
    """Deterministic part: verify lines, dedupe within the model, make refs. `results`: page → (OptionPage, usage_id)."""
    rows, seen_keys, seen_refs = [], set(), set()
    for page_no in sorted(results):
        parsed, usage_id = results[page_no]
        text = pages[page_no]
        for it in parsed.items:
            key = (norm(it.name_de), it.availability, norm(it.package_name or ""))
            if not norm(it.name_de) or key in seen_keys:
                continue
            seen_keys.add(key)
            base = f"{file_name}#p{page_no}:{slug(it.name_de)}"
            ref, k = base, 2
            while ref in seen_refs:
                ref, k = f"{base}-{k}", k + 1
            seen_refs.add(ref)
            rows.append({
                "ref": ref, "model": model, "page": page_no,
                "text": f"{it.name_en} ({it.availability}, {LIST_LABEL})",
                "quote": it.source_line.strip(),
                "external_id": it.option_code,
                "meta": {
                    **it.model_dump(), "page": page_no, "section": page_section(text), "heading": page_heading(text),
                    "line_verified": line_ok(it.source_line, text), "llm_usage_id": usage_id,
                    "market_note": ASSUMPTION, "price_note": PRICE_NOTE,
                },
            })
    return rows


def store_rows(conn: sqlite3.Connection, file_name: str, rows: list[dict], llm_model: str | None) -> int:
    seen = existing_refs(conn, "option_list", file_name)
    new = [r for r in rows if r["ref"] not in seen]
    if not new:
        return 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        batch_id = open_batch(conn, "option_list", f"{len(new)} equipment items from {file_name}", file_name)
        conn.executemany(
            """INSERT INTO source_item (kind, ref, external_id, trust_tier, vehicle_model_id, market_code,
                                        text, quote, meta_json, ingest_batch_id, wave)
               VALUES ('option_list', ?, ?, 'T1', ?, ?, ?, ?, ?, ?, ?)""",
            [(r["ref"], r["external_id"], r["model"], MARKET, r["text"], r["quote"], json.dumps(r["meta"]),
              batch_id, WAVE) for r in new],
        )
        verified = sum(r["meta"]["line_verified"] for r in new)
        audit_batch(conn, "ingest.options", batch_id, {
            "file": file_name, "items": len(new), "line_verified": verified, "llm_model": llm_model,
            "llm_usage_ids": sorted({r["meta"]["llm_usage_id"] for r in new if r["meta"]["llm_usage_id"]}),
        })
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(new)


def ingest_options(conn, make_llm, path: Path, model: str, only_pages: list[int] | None = None,
                   dry_run: bool = False, llm_model: str | None = None) -> dict:
    """`make_llm()` returns an LLM; called once per worker thread (each LLM holds its own DB connection)."""
    path = Path(path)
    texts = pdf_pages(path)
    pages = {i: t for i, t in enumerate(texts, start=1) if page_section(t)}
    if only_pages:
        pages = {p: t for p, t in pages.items() if p in only_pages}

    local = threading.local()

    def run(p):
        if not hasattr(local, "llm"):
            local.llm = make_llm()
        for attempt in range(RETRIES):
            try:
                res = extract_page(local.llm, model, p, pages[p])
                break
            except (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError,
                    openai.APIConnectionError):
                if attempt == RETRIES - 1:
                    raise
                time.sleep(10 * 2 ** attempt)
        return p, (res.parsed, res.usage_id), res.cost_usd

    with ThreadPoolExecutor(WORKERS) as pool:
        out = list(pool.map(run, sorted(pages)))
    results = {p: r for p, r, _ in out}
    cost = sum(c for *_, c in out)
    rows = build_rows(model, path.name, pages, results)
    stored = 0 if dry_run else store_rows(conn, path.name, rows, llm_model)
    return {"pages": sorted(pages), "items": len(rows), "verified": sum(r["meta"]["line_verified"] for r in rows),
            "stored": stored, "cost_usd": cost, "rows": rows}


def main() -> None:
    from bmw_req.config import get_settings
    from bmw_req.db import connect
    from bmw_req.ingest import reference
    from bmw_req.llm import LLM

    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*", default=["F70", "G60", "G70"])
    ap.add_argument("--pages", help="comma-separated page numbers (pilot)")
    ap.add_argument("--dry-run", action="store_true", help="extract and print, don't store")
    args = ap.parse_args()
    only = [int(p) for p in args.pages.split(",")] if args.pages else None

    conn = connect()
    reference.seed(conn)

    def make_llm():
        return LLM(conn=connect())
    for model in args.models:
        path = get_settings().raw_data_dir / FILE_PATTERN.format(model=model)
        r = ingest_options(conn, make_llm, path, model, only, args.dry_run,
                           llm_model=get_settings().model_fast)
        print(f"{model}: pages {r['pages']} → {r['items']} items, {r['verified']} lines verified, "
              f"{r['stored']} stored, ${r['cost_usd']:.4f}")
        if args.dry_run:
            for row in r["rows"]:
                m = row["meta"]
                print(f"  p{m['page']} [{m['availability']}/{m['category']}] {m['name_de']} → {m['name_en']}"
                      f" | pkg={m['package_name']} code={m['option_code']} €={m['price_eur']} "
                      f"to={m['applies_to']} ok={m['line_verified']}")


if __name__ == "__main__":
    main()
