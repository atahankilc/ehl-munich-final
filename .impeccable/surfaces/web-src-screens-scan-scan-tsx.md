---
version: 1
slug: "web-src-screens-scan-scan-tsx"
primary_target: "web/src/screens/scan/Scan.tsx"
related_targets: []
---

# Scan — raw evidence space

Mode: Operate. Audience: the BMW PM (Atahan) and hackathon judges on a laptop/projector. Job: see every piece of raw evidence the system holds, as one space, at a checkpoint; switch Jan 26 → Jul 26 and see what the second sweep added. Constraints: localhost only (confidential comments), black only, near-textless, 3D-first; checkpoint 2 always builds on checkpoint 1 (tracks, not snapshots).

## Direction contract
THESIS: each checkpoint is a radar sweep over one fixed evidence space; the app shows what a sweep acquired and how every track changed. Refuses the sidebar-plus-chart-cards dashboard.
OWN-WORLD: true black scan volume, white contacts, one BMW blue for the sweep and PM marks, amber only for weakened/lost; hairline range rings; mark shape encodes state (ring new, dot held, double ring strengthened, cross lost); numerals are the main text, wide Mona Sans.
STORY: the PM sees all raw evidence as one space, sweeps to July, watches new contacts flare in, hovers one to read the customer's words, filters by car or market.
FIRST VIEWPORT: full-bleed 3D galaxy of ~10k comments in a slowly turning scan volume; top-left three readout numerals; bottom-right the JAN 26 / JUL 26 sweep control; left edge a thin car/market key; click opens a right-side sheet with the comment.
FORM: own list candidate 5 of 7, track-while-scan; seed 8f8f8a79. Signature interaction: switching checkpoint sends a sweep plane through the volume, contacts it passes light up.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Recorded adaptations (2026-10-11, after the first finish review)
- User-pinned: each raw data type has its own colour (comments blue, research orange, study aqua, options yellow, sales magenta; validated categorical palette on black). This replaces "white contacts"; track state stays in mark shape (dot = held, ring = acquired by this sweep), flare and hover go white, the lock reticle is white.
- User-pinned: no auto-rotation; the volume moves only when the PM drags it. The sweep plays once on arrival (JAN → JUL) when no checkpoint is in the URL.
- Strengthened / weakened / lost marks and amber do not apply to raw sources (they are only ever acquired); they appear from the clustering stage on, where `track` states change.
- Key keeps five dimensions (car, market, channel, BMW label, engine): the raw comments carry all five and the PM asked to see the raw data.
- Every ring element opens an inspector that names its layer and says in one line what the ring encodes (user request).
