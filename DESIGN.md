---
name: Successor
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

# Design System: Successor

## Overview

**Creative North Star: "Track-While-Scan"**

The whole interface is a scan volume. A true-black field holds every piece of raw evidence as a contact in one fixed 3D space; each checkpoint is a sweep that passes through that space, and the screen shows what the sweep acquired and how existing tracks changed. The 3D canvas is the page. Everything else sits at the edges of the volume: the readout, the filter chips and the checkpoint timeline as frameless text and marks straight on the black, the inspector and the hover card as small sheets of tinted glass, so the evidence is never boxed into cards or framed by chrome.

Density sits in the contacts, not in the text. Numerals carry the information, set wide, light and tabular like instrument readouts; words are short labels. The only running text is the customer's own words, shown in the inspector at reading size. Colour is categorical and earned: each raw data type has its own hue, one blue belongs to the sweep and the PM's current position, and amber is held back for loss. State is carried by mark shape, never by hue alone.

Motion is a single event, not ambience. The volume never turns by itself; it moves only when the PM drags it. The sweep plays once on arrival and once on each checkpoint change, and contacts it passes flare white as they are acquired.

**Key Characteristics:**
- True black ground (#000) with the live 3D canvas full-bleed behind every overlay.
- Overlays pinned to the 24px edge: readout with the filter chips under it top-left, checkpoint timeline bottom-right (both frameless), inspector top-right (glass).
- Wide, light, tabular numerals as the primary text.
- Five categorical data-type hues, one sweep blue, amber reserved for loss.
- Mark shape encodes track state: dot = held, ring = acquired by this sweep.
- One sweep per checkpoint change; no idle motion of the volume.

## Colors

A black instrument field with white ink, five categorical data hues validated on black, and two reserved signals: sweep blue and loss amber.

### Primary
- **Sweep Blue** (sweep, sweep-hi, sweep-wash): the sweep and the PM's position. The deep step colours the sweep blade's additive wash; the bright step draws the blade's leading edge, the active checkpoint node (with a 4px sweep-wash halo), the border of a filter chip in use, a chosen filter value's bar, the focus ring, links and text selection.

### Secondary
- **Loss Amber** (lost-amber): reserved for weakened and lost tracks, which appear from the clustering stage on. Raw sources are only ever acquired, so the scan surface uses amber only for the failed-scan message (a lost signal).

### Tertiary (categorical, one hue per raw data type)
- **Comment Blue** (type-comment): customer verbatims, the galaxy at the centre of the volume.
- **Research Vermilion** (type-research): cited web research on the dated outer ring.
- **Study Aqua** (type-study): customer-study ticks on the innermost range ring.
- **Option Ochre** (type-option): price-list equipment on the options ring.
- **Sales Magenta** (type-sales): BMW sales volumes on the sales ring; forecasts render as wireframe outlines in the same hue.

The same hue colours the data type's inline legend glyph wherever the type is named (readout, ring name tags, inspector header).

### Neutral
- **Void** (void): the page and the WebGL clear colour. Never a near-black; pure black is what makes the contacts read as emitters.
- **Smoked Glass** (glass): every floating panel, always with a backdrop blur over the canvas.
- **Hairline** (hair) and **Strong Hairline** (hair-strong): panel borders, chip outlines, filter bar tracks, the checkpoint rail, the z-bar midline, scrollbars, mobile pill outlines.
- **Ink** (ink): numerals, titles, the customer quote, active labels, the held mark.
- **Ink 2** (ink-2): secondary values, filter names and counts, ring labels, the checkpoint fill.
- **Ink 3** (ink-3): micro labels, inactive tabs and nodes, meta lines. Holds at least 4.5:1 on black; it is the floor for any text.

In 3D, range rings are white at 10% opacity and the time ring is a white dashed line at 22%.

### Named Rules
**The One Blue Rule.** Sweep blue means "the sweep, or where the PM is right now". It never fills a data series and never decorates.

**The Amber Is Loss Rule.** Amber appears only for weakened or lost tracks and lost signal. Option Ochre sits near it in hue, so a lost track always also carries its cross mark; amber never encodes state on its own.

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

There is no page grid. The canvas fills the viewport (`position: fixed; inset: 0`, body scroll off) and overlays are pinned to a 24px edge inset that respects the bottom safe area: readout top-left as five cells in two rows (comments and research, then the three car-ring types; one row from 1900px, so it clears the page switch at top centre) with the filter chips directly beneath it, the checkpoint timeline bottom-right at 300px wide, the inspector top-right at up to 400px wide with height capped so it never covers the sweep control. The hover card follows the pointer at a 16px offset and clamps to the viewport.

Spacing inside panels is tight and stepped by hand (8, 12, 14, 18, 22px gaps); the larger inspector uses 22px between blocks and 28/26/24px padding. Under 760px the edge drops to 16px, the readout wraps, and the inspector lifts to sit above the checkpoint timeline. Under 560px the timeline spans the width.

The 3D volume itself is the layout: comments in a unit ball, then range rings outward (study, options, sales, a dated research ring), car lines as fixed angular sectors, labels billboarded at the outer radius.

## Elevation & Depth

Depth comes from the scene, not from a shadow scale. Contacts fade with distance in the shader, and panels separate from the volume by smoked glass plus backdrop blur (12px for the hover card and page switch, 16px for the inspector) and a hairline border. Floating panels carry one soft, two-layer black shadow so they lift off bright contacts behind them; nothing on the black field sits on a surface lighter than glass.

### Shadow Vocabulary
- **Float** (`box-shadow: 0 2px 6px rgba(0,0,0,.5), 0 24px 60px rgba(0,0,0,.6)`): the inspector.
- **Float Small** (`box-shadow: 0 2px 6px rgba(0,0,0,.5), 0 16px 40px rgba(0,0,0,.5)`): the hover card.

### Named Rules
**The Glass Over Canvas Rule.** Every panel is translucent glass with blur over the live volume. No opaque panels, no solid sidebars. Instruments that are only labels, numerals and marks (readout, filter chips, checkpoint timeline) need no panel at all and sit straight on the black.

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
- **Values:** hovering a chip opens its values in a glass list hanging under it: a micro scope line (what this dimension filters), then rows of name, a 2px bar and a tabular count; chosen rows in ink with a sweep-hi bar. Choosing a value closes the list again, so only the choice stays on the chip. Counts already apply the other active filters.
- **Chips:** 28px pills, hairline border on a 60% black fill, 12px ink-2 text. Car and Market filter every data type. The others belong to one type and carry its glyph: Channel, Label, Engine and Length (short under 80 characters, medium to 250, long) for comments; Trust, Topic and Fact type (figure, event, study or rating, policy, trend) for web research; Study result (above / around / below the car × market's average by half a standard deviation); Category and Availability (standard, optional, in a package) for equipment options; Sales year (2024, 2025, 2030 forecast). Items with no value for a global dimension (options have no market, global research has none) stay visible.
- **In the volume:** items the filters leave out dim to about 6–7% and can't be hovered or opened. Page 2 is never filtered.
- **Touch and keyboard:** chips open on tap or Enter; the fold toggle works on tap or Enter; Esc clears everything.

### Inspector Sheet
- **Corner Style:** 10px. **Background:** glass with 16px blur and a hairline border. **Shadow:** Float.
- **Head:** the layer name with its glyph (12px/600) and one ink-3 line saying what the ring encodes.
- **Body:** a title or the customer quote, an optional instrument figure, then a two-column fact grid (micro label over 13px ink-2 value).
- **Close:** a 30px square icon button, 8px radius, ink-3 to ink on hover with a 7% white wash. Esc closes; clicking empty space closes.
- **Entry:** fades in from 6px above over 240ms.
- **Charts inside:** neutral only (ink, ink-3, hairline outlines for forecasts); the categorical hue stays in the glyph.

### Audit Trail
- **Button:** top-right at the edge, a 28px pill like the filter chips (history icon + "Audit", 12px ink-2 on 60% black with a hairline border; ink with a stronger hairline while open).
- **Field:** no card. The trail sits on a frameless black field (86% with a 10px blur) that feathers out at all four edges through a mask, 440px wide, 46px below the edge like the inspector, so it reads as part of the black rather than a box on top of it.
- **Head:** "Audit trail" (12px/600) and one ink-3 line saying what the view holds; scope tabs in the filter-tab style (the current page, or Everything); then "who acted" chips (24px pills with the actor's mark and a count) that show or hide AI, System and PM rows.
- **Trail:** one hairline rail down the left, day lines pinned at the top while scrolling. Marks on the rail say who acted: AI a hollow ring, System a small ink-3 dot, PM a filled ink dot (the only filled one, because the human decides); a stage starting or finishing is a larger ink ring and its line is set in ink as a milestone. Each row: the line in 12px ink-2, a micro meta line beneath (who · model · steps · time or time range), the checkpoint in micro caps at the right.
- **Folding:** identical steps of one stream (same action, stage and checkpoint, no gap over 10 minutes) fold into one row with their totals ("Classified 2,800 comments → 4,597 signals · 140 steps · 05:31–05:49"), even while another run's steps interleave; a stage milestone closes its streams. A chevron opens the fold into its single steps on a nested hairline. A fold that runs on into rows not loaded yet says "Latest:" and "140+ steps" rather than passing a partial total off as the total.
- **Never blue:** who acted is never coloured; blue is the sweep and the PM's position.
- **Esc** closes the trail first, without touching the scan's filters or selection.

### Guide Dock
- **Where:** bottom-left, 300px like the checkpoint timeline opposite it, on the same feathered black field as the audit trail; folds to its tab row (remembered per browser).
- **Tabs:** Guide on both pages; Agent (the live agent panel) as a second tab on Structure, opened first while the agent is running.
- **Guide:** with nothing open, a legend of the screen drawn with the scene's own marks (each data type, held dot / new ring, car slices; on Structure the cluster marks, themes, area diamonds and evidence arcs) and two or three usage hints. Opening an item switches it to that kind of item: what it is, how the screen encodes it, and "How the AI uses it" in plain words. Short label-size text, never paragraphs of copy beyond two or three sentences.
- **Inspector companion:** research, study and option items show "Used as evidence": the themes the AI linked them to at this checkpoint, the relation as a tag (dashed for contradicts) and the AI's one-line reason.

### Hover Card
320px glass card following the pointer: up to three lines of 13px text, then a micro meta row that leads with the track mark (dot or ring). Pointer events off.

### Range Ring Labels
Billboarded in 3D: car name at 12px/600 ink-2 over its code at micro. Ring name tags are micro text with a 6px colour dot on a 70% black chip (4px radius).

### Loading and Error
A 64px hairline circle with a sweep-hi arc spinning once per 1.4s above the word "Scanning". Errors replace it with a centred amber line, max 48ch.

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
