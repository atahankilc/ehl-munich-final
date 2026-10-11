---
name: SharkSight
description: Track-while-scan for product evidence. Every checkpoint is a sweep over one fixed evidence space, shown on true black.
colors:
  void: "#000000"
  glass: "rgba(10, 12, 15, 0.72)"
  hair: "rgba(255, 255, 255, 0.09)"
  hair-strong: "rgba(255, 255, 255, 0.16)"
  ink: "#f2f4f7"
  ink-2: "#b4bac4"
  ink-3: "#868d99"
  sweep: "#1c69d4"
  sweep-hi: "#4d94ff"
  sweep-wash: "rgba(28, 105, 212, 0.18)"
  lost-amber: "#f5a524"
  type-comment: "#3987e5"
  type-research: "#d95926"
  type-study: "#199e70"
  type-option: "#c98500"
  type-sales: "#d55181"
typography:
  instrument:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "34px"
    fontWeight: 300
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 118"
    fontFeature: "'tnum' 1"
  read:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.5
  title:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 500
    lineHeight: 1.35
  body:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "'tnum' 1"
  detail:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
  label-strong:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "0.08em"
  micro:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    letterSpacing: "0.02em"
rounded:
  tag: "4px"
  row: "6px"
  panel: "10px"
spacing:
  edge: "24px"
  edge-compact: "16px"
components:
  glass-panel:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "16px 18px 14px"
  inspector-sheet:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "28px 26px 24px"
    width: "400px"
  hover-card:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    typography: "{typography.detail}"
    rounded: "{rounded.panel}"
    padding: "12px 14px"
    width: "320px"
  sweep-node:
    backgroundColor: "{colors.void}"
    textColor: "{colors.ink-3}"
    typography: "{typography.label-strong}"
    size: "9px"
  sweep-node-active:
    backgroundColor: "{colors.sweep-hi}"
    textColor: "{colors.ink}"
    typography: "{typography.label-strong}"
    size: "9px"
  sweep-timeline:
    width: "300px"
  filter-chip:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "99px"
    height: "28px"
    padding: "0 11px"
  filter-chip-active:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "99px"
    height: "28px"
    padding: "0 4px 0 11px"
  filter-row:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.row}"
    padding: "5px 8px"
  readout-numeral:
    textColor: "{colors.ink}"
    typography: "{typography.instrument}"
---

# Design System: SharkSight

## Overview

**Creative North Star: "Track-While-Scan"**

The whole interface is a scan volume. A true-black field holds every piece of raw evidence as a contact in one fixed 3D space; each checkpoint is a sweep that passes through that space, and the screen shows what the sweep acquired and how existing tracks changed. The 3D canvas is the page. Everything else sits at the edges of the volume: the readout, the filter chips and the checkpoint timeline as frameless text and marks straight on the black, the inspector, audit trail and guide dock on a frameless dark field that feathers into the volume, the hover card on the same field, so the evidence is never boxed into cards or framed by chrome.

Density sits in the contacts, not in the text. Numerals carry the information, set wide, light and tabular like instrument readouts; words are short labels. The only running text is the customer's own words, shown in the inspector at reading size. Colour is categorical and earned: each raw data type has its own hue, one blue belongs to the sweep and the PM's current position, and amber is held back for loss. State is carried by mark shape, never by hue alone.

Motion is a single event, not ambience. The volume never turns by itself; it moves only when the PM drags it. The sweep plays once on arrival and once on each checkpoint change, and contacts it passes flare white as they are acquired.

**Key Characteristics:**
- True black ground (#000) with the live 3D canvas full-bleed behind every overlay.
- Overlays pinned to the 24px edge: readout with the filter chips under it top-left, checkpoint timeline bottom-right (both frameless), inspector top-right (frameless feathered field).
- Wide, light, tabular numerals as the primary text.
- Five categorical data-type hues, one sweep blue, amber reserved for loss.
- Mark shape encodes track state: dot = held, ring = acquired by this sweep.
- One sweep per checkpoint change; no idle motion of the volume.

## Colors

A black instrument field with white ink, five categorical data hues validated on black, and two reserved signals: sweep blue and loss amber. Since 2026-10-11 a third, narrow pair sits beside them: rise green and fall red, for priority-level changes after a checkpoint only.

### Primary
- **Sweep Blue** (sweep, sweep-hi, sweep-wash): the sweep and the PM's position. The deep step colours the sweep blade's additive wash; the bright step draws the blade's leading edge, the active checkpoint node (with a 4px sweep-wash halo), the border of a filter chip in use, a chosen filter value's bar, the focus ring, links and text selection.

### Secondary
- **Loss Amber** (lost-amber): reserved for weakened and lost tracks, which appear from the clustering stage on. Raw sources are only ever acquired, so the scan surface uses amber only for the failed-scan message (a lost signal).

### Rise / Fall (priority-level changes only; PM request, 2026-10-11)
- **Rise Green** (rise #2fbf71, rise-hi #5ee69a, rise-glow): a PM-confirmed band the AI now places HIGHER after a checkpoint (an upgrade opportunity), and, small, an unconfirmed AI band that rose since the previous checkpoint.
- **Fall Red** (fall #ff3b30, fall-hi #ff6961, fall-glow): a PM-confirmed band the AI now places LOWER (the PM's decision is contradicted: big, never hidden), and, small, an unconfirmed AI band that fell.
- Contrast on black: rise 8.8:1, rise-hi 13.3:1, fall 5.9:1, fall-hi 7.5:1 (all WCAG AA for text); fills carry black text at the same ratios.

### Tertiary (categorical, one hue per raw data type)
- **Comment Blue** (type-comment): customer verbatims, the galaxy at the centre of the volume.
- **Research Vermilion** (type-research): cited web research on the dated outer ring.
- **Study Aqua** (type-study): customer-study ticks on the innermost range ring.
- **Option Ochre** (type-option): price-list equipment on the options ring.
- **Sales Magenta** (type-sales): BMW sales volumes on the sales ring; forecasts render as wireframe outlines in the same hue.

The same hue colours the data type's inline legend glyph wherever the type is named (readout, ring name tags, inspector header).

### Neutral
- **Void** (void): the page and the WebGL clear colour. Never a near-black; pure black is what makes the contacts read as emitters.
- **Smoked Glass** (glass): the page switch, with a backdrop blur over the canvas.
- **Field** (field): every other panel (inspector, hover card, filter values, audit trail, dock). Plain black at 86%, under a 10px blur and a feathered edge. No glow.
- **Hairline** (hair) and **Strong Hairline** (hair-strong): panel borders, chip outlines, filter bar tracks, the checkpoint rail, the z-bar midline, scrollbars, mobile pill outlines.
- **Ink** (ink): numerals, titles, the customer quote, active labels, the held mark.
- **Ink 2** (ink-2): secondary values, filter names and counts, ring labels, the checkpoint fill.
- **Ink 3** (ink-3): micro labels, inactive tabs and nodes, meta lines. Holds at least 4.5:1 on black; it is the floor for any text.

In 3D, range rings are white at 10% opacity and the time ring is a white dashed line at 22%.

### Named Rules
**The One Blue Rule.** Sweep blue means "the sweep, or where the PM is right now". It never fills a data series and never decorates.

**The Amber Is Loss Rule.** Amber appears only for weakened or lost tracks and lost signal. Option Ochre sits near it in hue, so a lost track always also carries its cross mark; amber never encodes state on its own.

**The Rise/Fall Rule.** Added at the PM's explicit request (Atahan, 2026-10-11): "for things that go up, make it look obvious that the PM should change their decision in a good way; if something goes worse, BIG RED indicators." Green and red mean only "this priority level moved after a checkpoint": up (green) or down (red) against the PM's confirmed band, loud for a PM decision (open proposal with `against: "pm"`), a small coloured ▲ / ▼ for an unconfirmed AI band that moved since the previous checkpoint. Never a data hue, never hover, never decoration, never a score move without a band change. Down is louder than up (solid red fill, glow, three-beat pulse; green is outlined, one gentle pulse). Blue keeps the PM's own position (the PM's band stays blue until they act) and amber keeps loss; both rules stand unchanged.

**The White Is Attention Rule.** Contacts rest in their data-type hue. They turn white only while a sweep flares them, while hovered, or under the white lock reticle. Blue is not used for hover.

## Typography

**Display Font:** Mona Sans Variable with its width axis (fallback ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif)
**Body Font:** the same family; one family runs the whole system.

**Character:** One grotesque in two voices. Numerals are stretched wide (118%), light (300) and tabular, so counts read like instrument dials; labels are the same face at normal width, small and quiet. Tabular figures are on globally.

### Hierarchy
- **Instrument** (300, 34px, line-height 1, -0.02em, width 118%): the readout totals (28px), the inspector's key figure (34px) and the checkpoint timeline's track counts (20px). Readout drops to 22px under 760px.
- **Read** (400, 18px, line-height 1.5, max 60ch): the customer's words in the inspector; the only reading text in the system.
- **Title** (500, 18px, line-height 1.35, balanced wrap): the inspected item's name or headline.
- **Body** (400, 14px, line-height 1.45): the base size; sweep-control track counts, secondary figures.
- **Detail** (400, 13px): hover-card text (clamped to three lines), inspector fact values, the source link.
- **Label** (400 or 600, 12px): filter chips, filter values and counts, layer names, "+n" increments. At 600 with 0.08em tracking it names checkpoints (JAN 26 / JUL 26).
- **Micro** (400, 11px, 0.02em, ink-3): field and readout labels, legend names, ring sublabels; at 600 with 0.1em tracking it labels the time ring.

### Named Rules
**The Numeral Leads Rule.** Where a value exists, the numeral is the largest thing in its group and its label sits beside or above it at micro size. Labels never outrank figures.

**The Labels, Not Paragraphs Rule.** Interface copy is a word or a short phrase. One-line explanations are allowed only in the inspector, where each layer says what its ring encodes. Paragraph-length text is reserved for evidence (customer words).

## Layout

There is no page grid. The canvas fills the viewport (`position: fixed; inset: 0`, body scroll off) and overlays are pinned to a 24px edge inset that respects the bottom safe area: readout top-left as five cells in two rows (comments and research, then the three car-ring types; one row from 1900px, so it clears the page switch at top centre) with the filter chips directly beneath it, the checkpoint timeline bottom-right at 300px wide, the inspector top-right at up to 440px wide with height capped so it never covers the sweep control. The hover card follows the pointer at a 16px offset and clamps to the viewport.

Spacing inside panels is tight and stepped by hand (8, 12, 14, 18, 22px gaps); the larger inspector uses 22px between blocks and 28/26/24px padding. Under 760px the edge drops to 16px, the readout wraps, and the inspector lifts to sit above the checkpoint timeline. Under 560px the timeline spans the width.

The 3D volume itself is the layout: comments in a unit ball, then range rings outward (study, options, sales, a dated research ring), car lines as fixed angular sectors, labels billboarded at the outer radius.

## Elevation & Depth

Depth comes from the scene, not from a shadow scale. Contacts fade with distance in the shader, and panels separate from the volume by smoked glass plus backdrop blur (12px for the page switch) and a hairline border; the inspector, hover card, filter value list, audit trail and dock instead sit on a frameless field (the `field` token: 86% plain black, no glow) with a feathered edge and no shadow; nothing on the black field sits on a surface lighter than glass.

### Shadow Vocabulary
None. The inspector, hover card, filter value list, audit trail and dock carry no shadow: their feathered field (the `field` token) separates them from the volume. Only the page switch keeps glass and a hairline border.

### Named Rules
**The Glass Over Canvas Rule.** Every panel is translucent over the live volume with a blur: a frameless feathered dark field (inspector, hover card, filter value list, audit trail, dock). No opaque panels, no solid sidebars. Instruments that are only labels, numerals and marks (readout, filter chips, checkpoint timeline) need no panel at all and sit straight on the black.

## Shapes

Gently rounded glass (10px) for every floating panel, 6px for interactive rows and nodes inside them, 4px for small tags and the focus ring. Marks are circles: an 8px filled dot for held tracks, an 8px ring (1.5px inset stroke) for acquired ones, a 9px node on the checkpoint timeline. Lines are hairlines (1px) everywhere, including the timeline rail and the z-bar midline; the only thick strokes are 2px filter bars and 4px z-bar fills. The lock reticle is four short white arc segments that rotate slowly around the selected contact.

## Components

### Checkpoint Timeline (signature)
Bottom-right, frameless, 300px wide. It keeps one size at every checkpoint, so switching never shifts it.
- **Head:** "Checkpoint" (12px/600 ink) over a micro line saying what the position means: "Evidence known up to 31 Jul 2026".
- **Timeline:** one hairline rail from JUL 25 to JUL 26 (the scene's date ring, straightened) with a 4px hairline tick per month and "JUL 25" as a micro label at its start. Each checkpoint is a 9px node at its cut-off date with its name above it (12px/600, 0.08em): ink-3 hairline on black; a node the current checkpoint builds on fills ink; the active node fills sweep-hi with a 4px sweep-wash halo and its name turns ink. Name and node are one button; together they are the radio group.
- **Fill:** ink-2 along the rail up to the active cut-off. On a checkpoint change it travels to the new cut-off over the 3D sweep's duration and curve (2400ms, ease-out cubic).
- **Track counts:** one line of 20px instrument numerals, always both: a held dot with what the earlier checkpoint knew (0 at the first) and a ring with what this sweep added; a "← →" micro hint at the right.

### Readout
Five cells top-left, one per colour in the scene: Customer comments, Web research, Customer study, Equipment options, Sales volumes. Each has its type glyph and a micro label above a 28px instrument numeral. The three car-ring cells add a second line for the cited public research on that ring in the same hue (public ratings, product news, public sales) with a hollow ring mark in the type colour. At a later checkpoint each count carries a "+n" increment. While filters are set, every count is what the filter leaves visible. Not interactive.

### Filter Chips
A row of chips directly under the readout, one per dimension, any number active at once (values within a dimension are alternatives, dimensions combine).
- **Always shown:** every chip is on the row, the ones in use first in the order they were set (so choosing a value never moves a set chip), then the unused ones. A chip in use shows its dimension in ink-3, the chosen value in ink (first value, "+n" for more) and an ×; a sweep-hi hairline border marks it as set. A "Clear all · Esc" text button follows once anything is set.
- **Fold toggle:** a 28px pill at the head of the row (sliders icon + chevrons, ink-3, hairline on hover). Folding hides the unused chips only (chips in use stay, so nothing is filtered unseen) and the toggle reads "Filter · n" with a chevrons-right; unfolding brings them back to the right. The choice is kept per browser.
- **Values:** hovering a chip opens its values in a list hanging under it, on the same frameless feathered dark field as the inspector: a micro scope line (what this dimension filters), then rows of name, a 2px bar and a tabular count; chosen rows in ink with a sweep-hi bar. Choosing a value closes the list again, so only the choice stays on the chip. Counts already apply the other active filters.
- **Chips:** 28px pills, hairline border on a 60% black fill, 12px ink-2 text. Car and Market filter every data type. The others belong to one type and carry its glyph: Channel, Label, Engine and Length (short under 80 characters, medium to 250, long) for comments; Trust, Topic and Fact type (figure, event, study or rating, policy, trend) for web research; Study result (above / around / below the car × market's average by half a standard deviation); Category and Availability (standard, optional, in a package) for equipment options; Sales year (2024, 2025, 2030 forecast). Items with no value for a global dimension (options have no market, global research has none) stay visible.
- **In the volume:** items the filters leave out dim to about 6–7% and can't be hovered or opened. Page 2 is never filtered.
- **Touch and keyboard:** chips open on tap or Enter; the fold toggle works on tap or Enter; Esc clears everything.

### Inspector Sheet
- **Field:** top-right under the Audit pill, 440px wide like the audit trail. No box, border, corner or shadow: the same frameless field as the audit trail and the dock (the `field` token, 10px blur) that feathers out at its edges, so content scrolling past the top or bottom fades into the volume.
- **Findings and notes inside** ("What the AI found", area notes) are not boxed either: each hangs off a hairline rail (1px hair-2 on the left, 12px indent), like the audit trail.
- **Head:** the layer name with its glyph (12px/600) and one ink-3 line saying what the ring encodes.
- **Body:** a title or the customer quote, an optional instrument figure, then a two-column fact grid (micro label over 13px ink-2 value).
- **Close:** a 30px square icon button, 8px radius, ink-3 to ink on hover with a 7% white wash. Esc closes; clicking empty space closes.
- **Entry:** fades in from 6px above over 240ms.
- **Charts inside:** neutral only (ink, ink-3, hairline outlines for forecasts); the categorical hue stays in the glyph.

### Audit Trail
- **Button:** top-right at the edge, a 28px pill like the filter chips (history icon + "Audit", 12px ink-2 on 60% black with a hairline border; ink with a stronger hairline while open).
- **Field:** no card. The trail sits on a frameless black field (86% with a 10px blur) that feathers out at all four edges through a mask, 440px wide, 46px below the edge like the inspector, so it reads as part of the black rather than a box on top of it.
- **Head:** "Audit trail" (12px/600) and one ink-3 line saying what the view holds; scope tabs in the filter-tab style (the current page, or Everything); then "who acted" chips (24px pills with the actor's mark and a count) that show or hide AI, System and PM rows. The page scope holds only the selected checkpoint ("Evidence · JAN 26"); Everything holds both, each row tagged JAN 26 / JUL 26 (or A/B TEST), and ends with a "Show history before the checkpoint rebuild" text button.
- **Trail:** one hairline rail down the left, day lines pinned at the top while scrolling. Marks on the rail say who acted: AI a hollow ring, System a small ink-3 dot, PM a filled ink dot (the only filled one, because the human decides); a stage starting or finishing is a larger ink ring and its line is set in ink as a milestone. Each row: the line in 12px ink-2, a micro meta line beneath (who · model · steps · time or time range), the checkpoint in micro caps at the right.
- **Folding:** identical steps of one stream (same action, stage and checkpoint, no gap over 10 minutes) fold into one row with their totals ("Classified 2,800 comments → 4,597 signals · 140 steps · 05:31–05:49"), even while another run's steps interleave; a stage milestone closes its streams. A chevron opens the fold into its single steps on a nested hairline. A fold that runs on into rows not loaded yet says "Latest:" and "140+ steps" rather than passing a partial total off as the total.
- **Never blue:** who acted is never coloured; blue is the sweep and the PM's position.
- **Esc** closes the trail first, without touching the scan's filters or selection.
- **Usage tab** (third tab after the page scope and Everything; the panel widens to 880px for it): every model call from `llm_usage` (GET /api/usage). Across the top three instrument figures (spent against the $100 cap with a 4px bar and hairline ticks at the guard's thresholds; calls with failures; tokens in / cached / out); then the spend split by model as one stacked bar in a grey ramp (Sol ink, Luna ink-2, embeddings ink-3) with a legend; then the four pipelines as selectable cards (name, spend, a 2px share bar, sweep-hi when open, one micro line on what runs there); then the open pipeline's steps in plain words (e.g. "Classify comments into signals"), sorted by cost: model as a text tag (Sol filled, Luna outlined, never a hue), calls with failures, tokens in / out, a 3px cost bar and the cost. Hover a step for its checkpoints, time range, Flex share and reasoning tokens. The method note says how cost is computed and how much is worst-case from failed calls; latest calls and the price table sit behind a text toggle.

### Guide Dock
- **Where:** bottom-left, 300px like the checkpoint timeline opposite it. A row of 32px pills styled exactly like the Audit button (icon + label, hairline border on 60% black, brighter border and ink text while open): Guide (book icon) on both pages, Agent (bot icon, plus a pulsing ink dot while it works) next to it on Structure.
- **One at a time:** clicking a pill opens its panel above the pills, on the same feathered black field as the audit trail, and closes the other; clicking the open pill closes it. Which panel is open, or none, is remembered per browser. On Structure the Agent opens first while the agent is running; opening an item switches an open dock to the Guide (a closed dock stays closed).
- **Guide:** with nothing open, a legend of the screen drawn with the scene's own marks (each data type, held dot / new ring, car slices; on Structure the cluster marks, themes, area diamonds and evidence arcs) and two or three usage hints. Opening an item switches it to that kind of item: what it is, how the screen encodes it, and "How the AI uses it" in plain words. Short label-size text, never paragraphs of copy beyond two or three sentences.
- **Inspector companion (Structure only, D-049):** research, study and option items show "Used as evidence": the themes the AI linked them to at this checkpoint, the relation as a tag (dashed for contradicts) and the AI's one-line reason.
- **Evidence → Structure bridge:** on Evidence the inspector shows the source only, closed by one hairline row: a quiet status ("Used in 3 themes at JUL 26", "Grouped into a cluster at JUL 26", "Not used as evidence at JUL 26") and, when the AI used the item, "View in Structure →" that switches page with the item (or a comment's cluster) selected.

### Hover Card
320px card following the pointer, on the same frameless dark field as the inspector (the `field` token, 10px blur, feathered edges, no border or shadow): up to three lines of 13px text, then a micro meta row that leads with the track mark (dot or ring). Pointer events off.

### Range Ring Labels
Billboarded in 3D: car name at 12px/600 ink-2 over its code at micro. Ring name tags are micro text with a 6px colour dot on a 70% black chip (4px radius).

### Loading and Error
A 64px hairline circle with a sweep-hi arc spinning once per 1.4s above the word "Scanning". Errors replace it with a centred amber line, max 48ch.

### Definition (page 3)
Page 3 stays in the same canvas. The scan volume sinks and shrinks out of view (0.9s) and unmounts; the area diamonds rise out of it and the requirements are built up on a plane above it (see Stages) until today's car rises at the centre on the last stage, and leaving glides the camera home as the volume rises back.
- **Car stage:** the car line's model, restyled as a graphite study model: every material becomes a neutral grey that keeps the original's brightness but drops hue and texture; glass is dark and translucent. Quiet light (a soft sky, one key, one cool rim), no environment map, no reflective floor, no shadow, no turntable. A single hairline ellipse on the ground (white at 10%) is the only floor. Interior zones and the battery floor turn the body to x-ray (12% opacity) while one of them is open.
- **Pins:** DOM marks at the requirement's car zone, 10px inside a 16px target, coloured by vehicle domain (eight categorical hues: exterior vermilion, interior aqua green, powertrain ochre, chassis magenta, assistance violet, digital teal, variants taupe, quality olive; never sweep blue, never amber). Shape is the track state: dot = held, ring = new, ring with a centre dot = target moved, amber with a cross = weakened or lost. Several requirements in one zone sit in rows of up to four. Hovered, open and linked pins turn white; the open one gets a 1px white lock ring. Pins on the far side of the car dim to 32% unless the body is in x-ray. The zone name appears on hover or while open, as a micro tag on a 70% black chip.
- **Link arcs:** white (ink) lines over and through the car between the two requirements' zones, never coloured. Solid = synergy or enables (enables carries a small cone near its target end), dashed = conflicts or competes for; width 1 / 1.7 / 2.6px by strength 1–3. With nothing open, the strong links show at 20% (a Links switch shows all or none); opening a requirement shows only its links at 92% with the shared resource (energy, mass, thermal, package, attention, aero, acoustic, compute) as a micro tag at the apex, dashed tag for a conflict. "Show bundle" lights every strong link of its connected group.
- **Top-left:** a readout of four numerals (requirements, links, bundles, open gaps, with "+n" at a later checkpoint), a dashed-hairline "Sample data" note while the pipeline has not filled the page, the car-line switch (1 / 5 / 7 Series) and Links switch as segmented pills, and domain chips with their colour dot and count (a sweep-hi border while in use, Esc clears).
- **Right column:** with nothing open, the requirement list on the inspector's field: grouped by domain, each row the pin mark, the title and the recommended target as the numeral at the right. Opening a requirement replaces it with the inspector, and the camera flies to its zone with the zone left of centre, clear of the sheet.
- **Inspector:** domain and one line on what a definition is; title and statement; "What changed" on a hairline rail when the target moved; the metric (name, unit, direction, method and conditions); one ladder per car line × market; acceptance criteria as criterion / pass value / condition rows; facts; linked requirements; open gaps and assumptions on rails; the sources behind the numbers.
- **Ladder:** one horizontal scale with "better" always to the right (lower-is-better metrics run reversed). Today, threshold, target and stretch sit on it with their value above (13px, wide, tabular) and their name below. The mark is the basis: filled = cited, hollow = projected, dashed = assumption, "?" = gap (placed between its neighbours, never given a number). An "AI" tag marks the recommended rung. Rungs closer than the button width are spaced apart; the printed values stay exact. Under the scale, one row per rung gives the basis, the note and its source ids as small hairline tags that jump to the source.
- **Choice flow:** clicking a rung opens a rationale field on a hairline rail (required, at least a few words) and a "Choose" button; the choice is applied at once and confirmed by a refetch. The chosen rung is the PM's position, so it is the one place blue appears on this page: a sweep-hi mark with the sweep-wash halo and a blue "PM" tag. Confirming or removing a link uses the same inline rationale; removed links leave the car and stay listed, struck through.
- **Checkpoint change:** pins that are new or whose target moved send out one white ring, and new links brighten once; nothing under reduced motion.

#### Stages
Page 3 continues page 2's object story instead of cutting to a new scene: the same things move, step by step, until they sit on the car.
- **Stepper:** page 2's funnel and stepper, same markup and `[` / `]` keys, in place of a readout: Areas → Requirements → Specified (gaps, cited numbers) → Links (bundles) → On the car (zones). Numerals at the readout's 28px so five stages clear the page switch. A stage the checkpoint has not produced yet shows "–" and is skipped by the stepper.
- **Arrival:** coming from Structure the page plays its stages once (about 2 s each, the move finishes before the next); any step, a stage name or "Skip" stops it. Under reduced motion it lands on the last stage with no moves.
- **Areas:** page 2's area diamonds (same colour, size, wireframe for new) rise straight up from their exact ring spots to a plane above the volume while the volume sinks away below; the camera glides up to look down on the plane, and is not moved again between plane stages. Labels add how many requirements an area became.
- **Drafted:** each diamond bursts into its requirements (the pin mark: domain hue, shape = track state), which arc into one group per vehicle domain on a ring at plane height; emptied diamonds shrink away. A group's name and count sit above its disc (hover lights the group, click filters like the domain chips). Hovering a requirement shows its title, domain and "from area · …", and rings its siblings from the same area.
- **Specified:** each requirement gets its recommended target as a micro tag to its right ("≥ 540 km", "≤ 16 min", long units left to the inspector), a "?" in ink-3 where a gap is open; tags that would collide hide until hovered.
- **Linked:** link arcs fade in between the requirements on the plane, in the car's arc vocabulary (white, solid / dashed, width by strength, shared resource at the apex of the open requirement's links).
- **On the car:** the car rises, the camera swings down to it, and every requirement flies from its group to its zone; the pins and the arcs over the car take over when they land. Stepping back runs every move in reverse (fly, then links, then the split); leaving for Structure drops the requirements and lowers the diamonds back onto their ring. Camera glides turn around what they look at rather than cutting through it. Selecting a requirement opens the inspector at any stage; the camera flies to its zone only on the car.

### Prioritize (page 4)
Page 4 continues on page 3's car in the same canvas: the requirement pins lift off the car and become a priority skyline around it (D-050). Unit = requirement × car line × market.
- **Transition:** each pin leaves its zone on a lifted arc to its slot on a ring around the car (radius ≈ 1.4 × the car's half-length), then grows up into its column; the columns leave in ring order, about 2.3 s in all. The car stays solid (no x-ray); the skyline stands on the ring around it. Going back to Definition runs the same move in reverse: the columns shrink, fly back onto their zones, and page 3's pins take over once they have landed (page 3 stays on its last stage, no replay). Under reduced motion every move jumps.
- **Skyline:** one column per requirement on the car line, grouped by vehicle domain round the ring (a gap between groups, the group's name and count as a ground chip outside it), ordered by best score; every requirement keeps its slot across markets. Height = the target's score in the selected market (100 ≈ twice the car's height). Hue = domain; band = mark: Must a solid square column, Should an outlined column over a 13% fill, Could a thin line with a cap dot. A market without a target leaves a hollow ink-3 slot on the ground. The score sits above each column as a small wide numeral on a 62% black chip (colliding chips hide, lowest score first); Must numerals in ink, the rest ink-2.
- **Thresholds:** two faint planes over the ring at Should 45 and Must 60: a white annulus at ~3–4% plus hairline circles, each named in micro caps on the camera side.
- **Market switch:** the heights morph (≈ 0.6 s ease) and the marks change band in place, so the PM sees where markets disagree (D-011). `[` / `]` step through the line's markets.
- **JAN → JUL:** a ghost tick (white, 38%) keeps JAN's height; the numeral adds the delta; risers and fallers (≥ 3 points or a band change) send out one white ring; an open AI proposal adds a ▲ / ▼ to the numeral, coloured rise / fall when the unconfirmed AI band itself moved.
- **Rise / Fall on a confirmed column:** the column stays at the PM's level (JAN's score clamped into the PM's band) with its blue "M ✓"; the AI's score becomes a coloured ghost box plus ring, joined to the PM's cap by a rise / drop line with an arrowhead beside the column (camera side). DOWN: a solid red badge above the chip "▼ Must → Should · cause", red ghost and ring at the lower height, a heavy drop line, a red double ring pulsing three times on arrival. UP: an outlined green badge "▲ Should → Must · upgrade suggested", green ghost above the column, a rise line, one gentle green ring. Down labels never hide in collisions, up labels beat every other label. Reduced motion: no pulse, static marks stay. The weights preview keeps the white "!" (hypothetical, not a checkpoint change).
- **Challenged decisions (HUD, under the stats):** "n of your decisions are challenged at JUL" then two groups on a 3px rule: red "▼ n downgrades — review" first, green "▲ n upgrade opportunities" second, 15px heads; rows = title · line · market · PM band (blue) ▲/▼ proposed band · cause; a row opens the inspector. While the matrix is up the groups fold to "▼ n ▲ n". The inspector opens with a red / green banner (kicker, "Your Must → AI: Should", plain sentence, factor deltas, Accept / Reject with a required rationale) that replaces the lower proposal box. Matrix cells get a red / green outline and "▼S" / "▲M"; list rows a red / green tag "▼ Must → Should" and a 3px edge, downs above ups.
- **Bundles and flags:** a bundle's bases are joined by a faint white chord through the inside of the ring (16%, 62% while a member is hovered or open, or "Show bundle"). Two Musts that must be chosen jointly carry a dashed white arc between their tops, labelled "choose jointly · <resource>" in the dashed link tag. Brand-fit fail puts a barred ink circle before the numeral.
- **The PM's position:** a confirmed band is the one blue mark: a sweep-hi disc with its wash halo at the column's base; in DOM, a sweep-hi underline with the wash under the band mark and the blue "PM" tag.
- **Attention:** hovered and open columns turn white (the open one's numeral gets a 1px white ring); opening one dims the others to 28%; the camera glides so the ring sits left of the panel.
- **Top-left (below the page switch):** the band readout (Must / Should / Could as 34px numerals with their band mark), a hairline, then Proposals, Choose jointly, Blocked and Markets disagree at 20px; a micro line (targets, PM-confirmed, weights scheme, "market weight stylized (Q-015)"); the car line, market and Skyline / Matrix switches as segmented pills; the dashed "Sample data" note while the stage has not run.
- **Priorities pill:** top-right next to Audit (one panel at a time). With nothing open, the ranked list for the market grouped by band: rank, band mark (domain hue), title, tags (PM, barred brand circle, dashed "joint", "→ band" for a proposal), confidence level, score with ▲▼ since JAN.
- **Inspector:** domain · line · market; title; the score at 52px with the band, "PM" or "AI proposal", rank and confidence; the same requirement in the line's other markets as small buttons (band mark + score; "markets disagree"); the waterfall; rationale on a rail; gates (pass a filled dot, warn a half-filled ring, fail a barred ring, with the checker's reason; brand fail adds the blocking line); the ladder rung with a what-if switch (baseline / threshold / target / stretch: the recomputed score, band change and "+1 exposure via <resource>" for linked requirements, never stored); bundle members; flags; history per checkpoint; an open proposal (old → proposed band, cause, factor deltas, Accept / Reject with a required rationale); the PM decision (Must / Should / Could as band-mark buttons, "AI" on the proposed one, required rationale, "Override and confirm" when brand fit fails).
- **Waterfall (D-037):** one 0–100 scale, rows grouped Customer / Business / Future: each factor a step from the running total (ink-2), a missing factor a dashed "gap" box; the base as an outlined bar; × confidence and negative modifiers as ink-3 hatched steps down; the score as a full ink bar; Should 45 and Must 60 as dashed vertical lines named above, and a white "what-if" tick while a rung is previewed. Neutral only.
- **Matrix:** the 2D alternative, on the inspector's field between the left column and the right panel: rows grouped by domain, one column per market of the line (the selected one outlined); each cell the band mark in the domain hue with its score, ▲▼ where JAN → JUL moved it, "P" for an open proposal, the PM underline where confirmed; a white tick at the row's end where markets disagree. Clicking a cell opens that market's target. The skyline behind steps back (columns 28%, labels 12%). Esc returns to the skyline.
- **Guide / Agent:** the dock's Guide explains the skyline with its own marks (or the matrix, or the open target's waterfall); the Agent panel shows the page-4 stages (fit gate, score).

### Document (page 5)
Page 5 is the deliverable: the final, traceable requirement list for one car line × market at the selected checkpoint (GET /api/document). It is a reading surface, so it is the one page where a sheet covers the scene.
- **Transition:** page 4's scene stays mounted (the canvas treats Document as Prioritize) and steps back: it sinks 5vh, scales to 0.97 and dims to 30% over 300 ms, pointer events off; the sheet fades up 14px over the same time. Reduced motion: no transition, no slide.
- **Sheet:** one frameless field (the `field` token, 10px blur, feathered left/right and bottom), up to 1120px wide, from under the page switch to just above the checkpoint timeline; no box, border or shadow. It scrolls inside.
- **Head:** kicker ("Requirement document · JUL 26 · evidence to 31 Jul 2026"), the line × market as a 28px wide-light title, Markdown / CSV export pills right (each export is an audit event); car line and market as page 3's segmented pills (shared with pages 3–4, so the skyline behind follows); a "Changes since JAN" pill at JUL 26. Readout: Must / Should / Could as 34px numerals with their band marks, a hairline, "Confirmed by PM n/N" and "Open proposals" at 22px, and a micro line with generation time, weights version and run. A search field and domain chips (domain dot + count; sweep-hi border while in use) filter the list.
- **List:** grouped by band (the PM's confirmed band, else the AI's), ordered by score. Each row on a hairline: the stable ID (REQ-5US-030, micro), the band mark in the domain hue (PM-confirmed adds page 4's blue underline), title, the target in use ("≤ 0.6 mm · assumption", a blue "PM" tag when the PM chose the rung), tags ("→ Must" for an open AI proposal, a gate mark for a brand warn/fail, dashed "borrowed" for borrowed voice), evidence level, "PM ✓" in sweep-hi only when confirmed, and the score as a 20px numeral with ▲▼ since JAN.
- **Record (row open):** the statement at 16px, a micro meta line (ID, key, version, horizon, Kano, decision type, status), then a two-column grid of sections with micro-caps heads on a hairline: Decision (score at 44px, band, status, the PM's confirmation on a blue rail, an open proposal on an ink rail, "Open in Prioritize →"), Metric and target (with the ladder as a hairline table: basis marks as on page 3, "AI" on the recommended rung, blue "PM" on a chosen one), Acceptance criteria, Prioritization rationale (rationale on a rail, factor bars in ink-2, gaps as "gap"), Evidence (type-hue dot per source, tier, date, relation, a sweep-hi "source" link for URLs, two customer quotes per comment cluster with their comment IDs), Assumptions / gaps / uncertainties on rails, Gates, Linked requirements (dashed tag for conflicts / competes for, struck through when removed), History (score and band per checkpoint, proposals with their outcome, PM decisions).
- **Changes since JAN:** a section under the head: eight 20px counts (new, removed, band up, band down, PM decisions, accepted, rejected, open) and short lists of new requirements, band moves (AI and PM, score from → to), PM decisions and open proposals.
- **Rise / Fall:** challenged PM rows carry a red "▼ Must → Should" (solid) or green "▲ Should → Must" (outlined) tag and a 3px edge, downs first in each band; the readout adds "▼ Downgrades — review" and "▲ Upgrade opportunities" counts; the record's Decision section a coloured rail with the plain sentence; "Changes since JAN" opens with "PM decisions now contradicted (down)" and "Upgrade opportunities (up)". Unconfirmed AI band moves colour the small score arrow. Dev / demo only: `?sample=1` overlays page 4's sample PM decisions on the live rows (labelled "Sample overlay").
- **Blue:** only the PM's marks (✓, underline, PM tags, the confirmation rail), the focus ring and source links.
- **Guide:** the dock's Guide explains the band marks, the PM ✓, proposal tag, gates and evidence levels; it switches to "Requirement record" while a row is open.

## Do's and Don'ts

### Do:
- **Do** keep the ground pure black (#000) and render overlays as blurred glass over the live canvas.
- **Do** give each raw data type its own categorical hue and repeat that hue in its legend glyph wherever the type is named.
- **Do** encode track state by mark shape: dot = held, ring = acquired by this sweep. The direction reserves double ring = strengthened and amber cross = lost for the clustering stage on; those marks are not built yet, so record them here once they ship.
- **Do** set every count as a wide (118%), light (300), tabular numeral and keep its label at micro size.
- **Do** play the sweep once on arrival and once per checkpoint change, using cubic-bezier(0.16, 1, 0.3, 1) for UI motion (160ms for colour, 240ms for panels and nodes).
- **Do** give every element in the volume an inspector that names its layer and says in one line what it encodes.
- **Do** honour reduced motion: transitions and animations drop to 0ms. The one exception is the focus glide (opening an item lifts its layer and sinks the others): it still glides without overshoot, pulse or ripple, because the move is what shows which layer the item belongs to.

### Don't:
- **Don't** auto-rotate the volume or add idle motion; it moves only when the PM drags it.
- **Don't** use sweep blue for data, hover or decoration; it belongs to the sweep and the PM's position.
- **Don't** use amber for anything but weakened or lost tracks and lost signal, and never without its cross mark.
- **Don't** frame evidence in sidebar-plus-chart-card dashboards or opaque panels; overlays float at the edges of the volume.
- **Don't** set text below ink-3 (#868d99) on black.
- **Don't** write paragraph copy in the interface; paragraphs belong to the evidence itself.
