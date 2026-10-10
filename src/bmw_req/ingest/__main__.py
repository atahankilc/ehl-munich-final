"""`uv run python -m bmw_req.ingest [F70 G60 G70]` — seed reference rows and ingest feedback files.

Other datasets: `python -m bmw_req.ingest.study`, `.sales`, `.options [F70 G60 G70]`."""

import sys

from bmw_req.config import get_settings
from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.ingest.feedback import ingest_feedback


def main(derivatives: list[str]) -> None:
    settings = get_settings()
    conn = connect()
    reference.seed(conn)
    for d in derivatives:
        n = ingest_feedback(conn, settings.raw_data_dir / f"{d}_feedback_hackathon.xlsx")
        print(f"{d}: {n} new verbatims")


if __name__ == "__main__":
    main(sys.argv[1:] or ["G60"])
