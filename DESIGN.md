---
name: Successor
description: A PM cockpit for deciding what successor cars offer each market, every number unfolding to the customer's words.
colors:
  cabin-black: "#08090b"
  panel-glass: "#0e1014"
  panel-raised: "#12151a"
  hover: "#171b22"
  press: "#1c212a"
  hairline: "#1d2027"
  hairline-strong: "#2a2f39"
  field-well: "#0a0c0f"
  text: "#e8ebf0"
  text-2: "#b9c0cb"
  muted: "#8b94a4"
  faint: "#636c7c"
  decision-blue: "#1c69d4"
  decision-blue-hi: "#4d94ff"
  decision-blue-ink: "#a9cbff"
  should-steel: "#3f6fb0"
  telltale-amber: "#f5a524"
  telltale-amber-ink: "#fbd38a"
  telltale-red: "#ff5a5f"
  telltale-red-ink: "#ffb3b5"
  telltale-green: "#3ccf91"
  telltale-green-ink: "#a6ecc9"
  telltale-violet: "#a78bfa"
typography:
  instrument:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "64px"
    fontWeight: 300
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 118"
    fontFeature: "'pnum' 1, 'zero' 0, 'ss01' 0"
  display:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.12
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 112"
  headline:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 106"
  title:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "'pnum' 1"
  lead:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 550
    lineHeight: 1.4
  micro:
    fontFamily: "Mona Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.01em"
rounded:
  bar: "2px"
  chip: "6px"
  ctl: "7px"
  row: "9px"
  panel: "12px"
  floating: "14px"
  sheet: "16px"
  pill: "999px"
spacing:
  stack: "10px"
  panel-y: "14px"
  panel-x: "18px"
  grid: "18px"
  gutter: "28px"
  gutter-phone: "16px"
  band: "52px"
  dock-clear: "104px"
components:
  button:
    backgroundColor: "{colors.panel-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.ctl}"
    padding: "0 14px"
    height: "34px"
  button-hover:
    backgroundColor: "{colors.hover}"
  button-primary:
    backgroundColor: "{colors.decision-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.ctl}"
    padding: "0 14px"
    height: "34px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-2}"
    rounded: "{rounded.ctl}"
    padding: "0 14px"
    height: "34px"
  input:
    backgroundColor: "{colors.field-well}"
    textColor: "{colors.text}"
    rounded: "{rounded.ctl}"
    padding: "0 12px"
    height: "36px"
  chip:
    backgroundColor: "rgba(255, 255, 255, 0.06)"
    textColor: "{colors.text-2}"
    rounded: "{rounded.chip}"
    padding: "0 8px"
    height: "22px"
  chip-blue:
    backgroundColor: "rgba(28, 105, 212, 0.16)"
    textColor: "{colors.decision-blue-ink}"
  priority-must:
    backgroundColor: "{colors.decision-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.chip}"
    padding: "0 9px"
    height: "22px"
  priority-should:
    backgroundColor: "transparent"
    textColor: "{colors.decision-blue-ink}"
    rounded: "{rounded.chip}"
    padding: "0 9px"
    height: "22px"
  panel:
    backgroundColor: "{colors.panel-glass}"
    rounded: "{rounded.panel}"
    padding: "14px 18px 18px"
  dock-item:
    textColor: "{colors.muted}"
    rounded: "11px"
    padding: "0 13px"
    height: "38px"
---

# Design System: Successor

## Overview

**Creative North Star: "The Cabin at Night"**

Successor is a decision instrument dressed as the interior of the car it decides about: near-black cabin glass, hairline seams, one blue that lights only where a decision or focus lives, and small coloured telltales that report state the way a dashboard does. Numbers are readouts, not decoration; when a figure matters it is set wide and light like a gauge, and every figure can be opened down to the customer's words.

Density is high but calm (Fey-level restraint): one panel level, rules and whitespace instead of boxes in boxes, 12-14px working text, and a large wide headline only where a screen states its one question. Chrome floats over content rather than framing it: a translucent panoramic status band across the top, a floating dock at the bottom centre, ⌘K for everything, right-hand drawers for detail. The 3D car stage is the canvas for per-zone requirements and shares the same tokens.

Rejected by the build: the sidebar-of-pages admin dashboard, the card grid of identical KPI tiles, light mode, BMW logos.

**Key Characteristics:**
- Dark only; cabin black with a faint fixed blue glow in the top-left corner.
- One accent (decision blue) for the primary action, focus, PM-confirmed Must, and the active wave.
- Telltale colours (amber, red, green, violet) carry state, never decoration.
- Mona Sans on its width axis: normal width for reading, wide/light for instrument numerals.
- Proportional figures everywhere; tabular figures are deliberately off.
- One panel level, hairline borders, soft offset shadows only on floating layers.

## Colors

A cockpit palette: a ladder of blue-tinted near-blacks, four cool greys for text, one decision blue, and a set of dashboard telltales each with a solid, an ink (text on dark) and a 13% wash.

### Primary
- **Decision Blue** (decision-blue): the primary button, the PM-confirmed Must mark, waiting-count badges, checkbox/range accents, the selected Must in the priority picker. If it is solid blue, a human decision or the one main action lives there.
- **Instrument Blue** (decision-blue-hi): focus rings, caret, score fills at Must, the current wave tick, the focused series in charts, active story dot.
- **Blue Ink** (decision-blue-ink): blue text on dark (links, Should labels, AI chips, decision-ask labels); with `blue-wash` rgba(28,105,212,0.16) for tinted chips and selected rows, and `blue-line` rgba(77,148,255,0.45) for outlined Should and selected queue items.
- **Should Steel** (should-steel): the desaturated blue for the Should band in score bars, pulse bars and waterfall bars; it sits between Instrument Blue (Must) and grey (Could).

### Secondary
- **Telltale Amber** (telltale-amber / -ink, wash rgba(245,165,36,0.13)): conflict, thin evidence, SIMULATION flag, deferred status, mid evidence bars.
- **Telltale Red** (telltale-red / -ink, wash rgba(255,90,95,0.13)): failed gate, rejected status, load errors, weak evidence bars, negative deltas.
- **Telltale Green** (telltale-green / -ink, wash rgba(60,207,145,0.13)): approved status, strong evidence bars, positive deltas, success toasts.
- **Telltale Violet** (telltale-violet, wash rgba(167,139,250,0.14)): challenged status only.

### Neutral
- **Cabin Black** (cabin-black): page background, under a fixed radial glow of `bg-glow` rgba(28,105,212,0.07).
- **Panel Glass** (panel-glass): every panel. **Panel Raised** (panel-raised): default button fill, selected segment. **Hover / Press** (hover, press): row and control states.
- **Field Well** (field-well): inputs, segmented-control tracks, kbd caps, priority picker; sits darker than the panel so fields read as recessed.
- **Hairline** (hairline): panel borders, table rules, `.rule` dividers. **Hairline Strong** (hairline-strong): control borders, outlined chips, drawer and palette edges.
- **Text** (text), **Text 2** (text-2): primary and secondary copy. **Muted** (muted): labels, table headers, inactive dock items. **Faint** (faint): metadata, placeholders, counts. Pure #fff is reserved for instrument numerals, titles in the selected item and text on solid blue.
- **Scrim** rgba(4,5,7,0.72): behind drawers and the command palette.

### Named Rules
**The One Blue Rule.** Blue means decision or focus. Solid Decision Blue appears on at most one action per view plus PM-confirmed Must marks; everything else blue is ink, wash or line.

**The Telltale Rule.** Amber, red, green and violet only report state (conflict, fail, approved, challenged, evidence strength, delta direction). A telltale colour used for decoration is a false warning light.

**The Three-Step Tint Rule.** Every state colour comes as solid (dot, bar, icon), ink (text), and a 13-16% wash (chip or note background). Never put solid-colour text on a wash.

## Typography

**Display Font:** Mona Sans Variable (with ui-sans-serif, system-ui fallback)
**Body Font:** Mona Sans Variable, same family
**Label/Mono Font:** none; IDs use Mona Sans narrowed to 92% width with 0.02em tracking.

**Character:** One family carried on its width axis. Text reads at normal width; headings widen slightly (106-112%); instrument numerals go wide (118%) and light (300), so scores and counts read like gauge faces rather than spreadsheet cells.

### Hierarchy
- **Instrument** (300, 64px token, wdth 118, line-height 1, -0.02em): genuine readouts only: score arc centres (scaled to 30% of arc size), budget, job counts. White.
- **Display** (600, 34px, 1.12, wdth 112, max 22ch): the briefing headline; the decision workspace title runs the same voice at 30px / wdth 108 / max 30ch.
- **Headline** (600, 28px, 1.15, wdth 106): page titles in the page head.
- **Title** (600, 20px, 1.25): section and drawer titles. Panel heads drop to 14px / 600.
- **Lead** (400, 16-17px, 1.55-1.7, max 64-70ch): briefing paragraph, page lede, customer-need text (19px in the decision ask).
- **Body** (400, 14px, 1.5): default; tables and lists run 13-13.5px.
- **Label** (550, 12px): field labels, section labels inside a panel, table headers (500, muted).
- **Micro** (11-11.5px, 600 for chips): chips, priority marks, captions, quote attributions.

### Named Rules
**The Proportional Figures Rule.** All numerals use proportional figures (`font-variant-numeric: proportional-nums`, `zero` and `ss01` off). Mona Sans's tabular set brings a code-style slashed zero; it is never switched on, including in tables and right-aligned columns.

**The Gauge Rule.** Wide light numerals are earned: only a number the PM reads as a measurement (score, budget, count that matters) gets the instrument style. Labels and body numbers stay normal width.

**The No-Kicker Rule.** Headings stand alone: no eyebrow or kicker line above them, no section numbers, no gradient text. Context sits beside or below a title (meta line, chips), not stacked above it.

## Layout

Pages are a single centred column (`max-width` 1480px; the decision screen widens to 1560px) with a 28px gutter (16px under 720px). Top padding clears the fixed 52px status band plus 28px; bottom padding of 104px clears the floating dock. Content is composed with CSS grid in twelfths: the briefing splits 7/5 (recap and portfolio pulse) then 8/4; the decision screen is a 312px sticky queue rail beside a workspace that splits 1.15fr / 1fr. Every multi-column grid collapses to one column between 1000px and 1280px, and grid children carry `min-width: 0` so nothing forces horizontal page scroll.

Rhythm: 18px between major blocks and grid columns, 14px between stacked panels in a workspace, 10px inside stacks and rows. Panels pad 14px top, 18px sides and bottom; drawers 18-20px. Wide tables scroll inside their panel with soft edge shadows that appear only while there is more to scroll.

**The Floating Chrome Rule.** Navigation never takes a column. The band floats on top, the dock floats at the bottom centre, detail opens in a right drawer, search lives in ⌘K. The page itself is all content.

## Elevation & Depth

Depth is tonal first: cabin black, then panel glass, then raised controls, with hairline borders doing the separation. Shadows exist only for layers that float above the page (dock, ⌘K button, drawer, palette, toasts, Story card) and for the single decision panel in the workspace side column. Floating chrome adds translucency and backdrop blur (14-18px with 140-150% saturation) so the page reads through it like tinted glass.

### Shadow Vocabulary
- **Lift 1** (`box-shadow: 0 1px 2px rgba(0,0,0,0.5), 0 8px 24px rgba(0,0,0,0.35)`): the decision panel, chart tooltips.
- **Lift 2** (`box-shadow: 0 2px 6px rgba(0,0,0,0.55), 0 24px 60px rgba(0,0,0,0.55)`): dock, drawer, command palette, toasts, Story card.
- **Inset hairline** (`box-shadow: inset 0 0 0 1px <hairline>`): outlined chips, selected segment, field wells, fit-gate list; draws a border without changing box size.

### Named Rules
**The Offset-Not-Halo Rule.** Shadows are offset and soft-blurred black, never a coloured glow around an element. Telltale dots get a 3px tinted ring, which is the light's own lens, not a halo.

**The One Level Rule.** A panel never sits inside a panel. Group inside a panel with whitespace, `.rule` hairlines and type.

## Shapes

Gently rounded, tighter as things get smaller: 2px on bars and tracks, 6px on chips and priority marks, 7px on buttons and inputs, 9px on list rows and queue items, 12px on panels, 14px on floating cards (palette, Story), 16px on the dock and drawer sheet, full pill on counts, avatars, the waiting badge. Bars are 3-6px thin; strokes are 1-1.5px; icons are lucide line icons at 15-18px. No coloured side borders on any container.

## Components

### Buttons
Quiet raised keys; only the primary one is lit.
- **Shape:** gently rounded (7px), 34px tall (28px small, 42px large, square icon variant).
- **Default:** Panel Raised fill, Hairline Strong border, 13px / 550 text.
- **Primary:** solid Decision Blue, white text; one per view. Hover lightens to #2477ea.
- **Ghost:** transparent, Text 2; hover fills with Hover. **Danger:** red ink text, red wash on hover.
- **Hover / Active:** fill steps to Hover; active presses 1px down onto Press. Transitions 140ms. Disabled at 45% opacity.
- **Focus:** 2px Instrument Blue outline, 2px offset, on every focusable element.

### Chips
- **Style:** 22px, 6px radius, 11.5px / 600, white 6% wash with Text 2. Tones `up` (green), `down` (red), `warn` (amber), `blue`, `violet` use wash + ink; `outline` uses an inset Hairline Strong ring on transparent.
- **Delta chips** carry a lucide arrow (up-right, down-right, minus) and sit inline in prose.

### Telltales (signature)
A 7px dot in the state colour with a 3px ring of the same colour at 22%, followed by a 12px Text 2 word. Status map: proposed = blue, challenged = violet, approved = green, deferred = amber, rejected = red. A pulsing variant marks a running job.

### Priority Mark (signature)
The single most important encoding in the app. **Filled = the PM confirmed it; dashed + "AI" = the AI suggests it.** Must is solid Decision Blue with white text; Should is a Blue Line outline with Blue Ink text; Could is a Hairline Strong outline in Muted. An AI suggestion replaces the outline with a 1px dashed outline in the same colour family (Must becomes blue wash with a dashed Instrument Blue edge) and appends a 9px / 700 "AI" tag. The per-market priority picker mirrors it: M / S / C segments in a field well, selected Must solid blue.

### Evidence Meter (signature)
Four 3px signal bars rising 4, 7, 10, 13px. E1 lights all four, E4 one. Three or more lit = green, two = amber, one = red; unlit bars are Hairline Strong. Optional 12px label ("Strong", "Good", "Limited", "Assumption only").

### Score Bar and Score Arc (signature)
- **Score Bar:** a 4px track (#1e222a) with ticks at 45 (Should) and 60 (Must); fill is Instrument Blue at Must, Should Steel at Should, grey at Could; value to the right in 12.5px proportional figures.
- **Score Arc:** a 240° gauge, 6px round-capped stroke, the same two band ticks, instrument numeral in the centre with a muted caption below.

### Cards / Containers
- **Corner Style:** 12px.
- **Background:** Panel Glass with a 1px Hairline border.
- **Shadow Strategy:** none at rest (see Elevation); the decision panel alone takes Lift 1 and a slightly bluer border.
- **Internal Padding:** head 14px 18px 0 (min 44px, 14px / 600 title), body 14px 18px 18px.
- **Notes:** conflicts are an amber-wash block with an inset amber ring; errors a red-wash note with a red telltale and retry; empty states centred text saying what to do next.

### Inputs / Fields
- **Style:** Field Well background, Hairline Strong border, 7px radius, 36px tall, 13.5px text, placeholder in Faint. Selects use a custom chevron; textareas min 64px.
- **Focus:** border turns Instrument Blue and the well lightens a step; caret is Instrument Blue.
- **Segmented control:** a field-well track (9px radius, 3px padding) with 28px segments; the pressed segment lifts to Panel Raised with an inset hairline and a 1px shadow.
- **Reason field:** every write requires a reason of at least 5 characters, recorded with the actor's name.

### Navigation
- **Status band:** fixed 52px top band, translucent cabin black with 14px blur and a 5% white bottom hairline. Left: product mark and wide (118%) name, separator, SIMULATION flag, wave ticks (16 x 4px; done grey, current Instrument Blue), wave text. Right: blue "N waiting for you" pill, spend meter, Present, actor avatar, ⌘K button. Elements drop out by priority under 1080px and 760px.
- **Floating dock:** bottom-centre, 16px-radius translucent bar with Lift 2; 38px items in Muted 12.5px / 550 with a 17px lucide icon; the active item turns white over an 8% white pad; Decide carries a blue count badge. Labels hide under 860px. A separate 48px round ⌘K button sits beside it.
- **Command palette:** 640px box at 14vh, 14px radius, 52px input, 40px items, selected item on Hover.
- **Drawer:** right sheet inset 10px from the viewport edges, max 560px, 16px radius, Lift 2, over the scrim.

### Story Card (signature)
Presenter mode: a 380px floating card bottom-left (bluer glass rgba(16,20,28,0.94), #2a3446 border, Lift 2, 16px blur) with a blue-ink step counter, a 16px / wdth 108 title, a 13px "say this" line, a row of 3px progress dots (past grey, current Instrument Blue) and back/next buttons. It lifts above the dock under 1280px.

### Car Stage
The three.js canvas sits on a radial cabin-black gradient and uses the same palette via a mirrored token object. Zone focus flies the camera to a zone and renders interior zones in x-ray; DOM pins over the canvas use the app's type and blue.

## Do's and Don'ts

### Do:
- **Do** use solid Decision Blue for exactly one main action per view and for PM-confirmed Must marks.
- **Do** show any AI-originated priority as a dashed mark with the "AI" tag until a human confirms it.
- **Do** encode evidence with the four signal bars and scores with a bar or arc ticked at 45 and 60.
- **Do** report state with telltale dots and wash-plus-ink chips (amber conflict, red fail, green approved, violet challenged).
- **Do** set numerals in proportional figures; reserve wide (118%) light (300) numerals for genuine readouts.
- **Do** keep one panel level and group inside it with whitespace, hairline rules and type.
- **Do** float chrome (band, dock, ⌘K, right drawers) and keep the page all content; clear the band (52px) and dock (104px).
- **Do** use skeletons for loading, an error note with retry, and empty states that say what to do next.
- **Do** honour reduced motion; the duration tokens collapse to 0ms.

### Don't:
- **Don't** add a sidebar of pages or a grid of identical icon-title-number KPI tiles.
- **Don't** turn on tabular figures or the slashed zero.
- **Don't** nest a panel inside a panel.
- **Don't** put a coloured stripe on the side of a card, row or note.
- **Don't** add eyebrow or kicker labels above headings, section numbers, gradient text or emoji.
- **Don't** use a telltale colour for decoration, or a coloured glow halo for emphasis.
- **Don't** introduce a light theme or any BMW logo or trademark.
- **Don't** show option-list prices.
