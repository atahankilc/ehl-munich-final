"""Prioritization layer (D-050, contract `foundation/documents/prioritization.md`): BMW step 4 on top of the
requirement definition layer (D-048).

Two checkpoint stages: `gate` (LLM brand / segment / market / feasibility checks, `gate.py`) and `prioritize`
(deterministic prio-v1 per requirement × car line × market, `score.py`). The AI writes scores (logged) and *proposed*
bands; confirmed priorities are PM decisions (`prio_decision`, append-only) and a band that moves against a confirmed
or earlier band becomes a `prio_proposal` with its factor-level cause (rule 5, D-013).

This module owns the schema of the prio_* tables.
"""


BANDS = ("Must", "Should", "Could")
BAND_RANK = {b: i for i, b in enumerate(BANDS)}   # lower = stronger


