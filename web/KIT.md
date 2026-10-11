# Successor web — UI kit rules (read before building a screen)

World: "cockpit" — near-black cabin glass, one BMW-like blue for decisions and focus, telltale lights for state,
Fey-level restraint and density. Dark only. No BMW logos. English, current domain terms (`src/lib/labels.ts`).

## Files
- Tokens: `src/styles/tokens.css` (colours, type scale, radii, motion). Base classes: `src/styles/base.css`.
- Primitives: `src/components/ui.tsx` — `PriorityMark` (filled = PM-confirmed, dashed + "AI" = AI suggestion),
  `EvidenceMeter` (signal bars E1–E4), `ScoreBar` (0–100 with ticks at 45/60), `ScoreArc` (headline gauge), `Delta`,
  `StatusLight`, `Seg` (segmented control), `Kbd`, `Skeleton(Block)`, `ErrorNote`, `Empty`, `Stat`.
- Requirement blocks: `src/components/req.tsx` (`DecisionAsk`, `VoiceByMarket`, `Quotes`, `StudyAndWeb`, `Conflict`,
  `MarketTable`, `FitGates`, `AssumptionsBlock`, `ReqTags`).
- Actions: `src/components/actions.tsx` (`ReasonField`, `reasonOk`, `useJob`, `ChallengeDrawer`, `OverrideDrawer`).
- Shell: `PageHead` from `src/components/Shell.tsx`; `Drawer` for side detail; `useToast()` for confirmations.
- Data: `api.get/post/put/patch` + `qs()` from `src/lib/api.ts`, TanStack Query (`useQuery` with stable keys),
  `invalidateAll()` after every write. Types in `src/lib/types.ts` (extend there, don't redefine locally).
- Formatting: `src/lib/format.ts`. Labels: `src/lib/labels.ts` (`car()`, `mkt()`, `targetLabel()`, EVIDENCE, KANO…).

## Layout
- A screen is `<main className="page">` → `PageHead` → content. Bottom padding already clears the floating dock.
- Containers: `.panel` (+ `.panel-head` / `.panel-body`). ONE level only — never a panel inside a panel, never a
  "card grid" of identical icon+title+text tiles. Group with whitespace, rules (`.rule`) and type instead.
- Tables: `.table` (+ `.clickable` rows, `.r` for numbers). Numbers always tabular (`.num`).
- Controls: `.btn` (`.btn-primary` for the one main action per view, `.btn-ghost`, `.btn-danger`, `.btn-sm`),
  `.input`, `.textarea`, `.select`, `Seg`. Chips: `.chip` (+ `up` `down` `warn` `blue` `violet` `outline`).
  Telltales: `.telltale` (+ `blue` `amber` `red` `green` `violet`).
- Headings: `t-head` (page), `t-title` (section/drawer), `panel-head h2` (14px). No eyebrow/kicker labels above
  headings, no section numbers, no gradient text, no coloured side borders, no glow halos, no emoji.
- Big numbers: `.instrument` (wide, light) — only for genuine readouts (scores, counts that matter).

## Behaviour
- Every write needs a reason (`ReasonField`, ≥5 chars) and shows a toast "… Recorded in the audit trail.".
- Loading: skeletons, not spinners. Errors: `ErrorNote` with retry. Empty: `Empty` with what to do next.
- Links between screens: requirements → `/requirements/:id`; cars → `/cars/:vehicle?market=XX`;
  markets → `/markets/:code`; decisions → `/decide/req:REQ-0001`.
- Keyboard first where it helps; respect reduced motion (tokens already zero durations).
- Never show option-list prices. Customer quotes are confidential but fine on this localhost app.
