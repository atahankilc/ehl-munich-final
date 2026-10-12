---
version: 1
slug: "web-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Successor — PM cockpit (web app)

Scope: the whole PM web app (`frontend/`), Operate mode, a real tool that also has to read well when shown live.
Audience/job: PM decides what successor cars offer per market; viewers follow the process.
Constraints: dark only, BMW-like blue accent, no BMW logo, English + current domain terms, localhost only.
Inspiration pinned by user: Fey (web) — calm near-black, dense refined data, floating dock, ⌘K, AI recap card, right drawers.

## Direction contract
THESIS: The PM's decision tool speaks the language of the car it decides about: one cockpit where the car itself is the canvas and every number unfolds to the customer's words. Refuses the sidebar-of-pages admin dashboard and the card-grid of KPI tiles.
OWN-WORLD: Near-black cabin glass (#08090b → #0e1014 panels, hairline #1d2027), one BMW-blue (#1c69d4 / #4d94ff) for decisions and focus; telltale lights for state (amber conflict, red fail, green approved, dashed blue AI-proposal). Mona Sans: wide/light numerals as instrument readouts, normal width for text. Thin score arcs, band ticks at 45/60, lucide strokes.
STORY: See what changed since last wave → decide in one queue with reasons → see the result on the car per market → open any number down to quotes → prove it in the audit timeline.
FIRST VIEWPORT: Panoramic status band (product, SIMULATION wave 3 · Nov 2027 with wave ticks, actor, spend, ⌘K). Briefing: left 7/12 AI-free wave briefing paragraph with inline delta chips and "N decisions waiting" primary action; right 5/12 portfolio pulse (car × market grid, Must counts, evidence gaps). Below: "Since last wave" event feed. Floating dock bottom centre.
FORM: cockpit HMI × Fey restraint — own list position 3; seed key 3c8f88bb.
SIGNATURE: car zone focus — camera flies to a zone, body turns x-ray for interior zones, the requirement list scrolls in sync; rotary J/K stepping in the decision queue.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
