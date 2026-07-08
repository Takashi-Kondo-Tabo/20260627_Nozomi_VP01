# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page Vite + React + TypeScript app, no backend. A coach uses it in
CliftonStrengths coaching sessions: upload a client's Gallup CliftonStrengths 34
PDF report (or paste the ranking as text), and it renders the client's 34-theme
ranking as an illustrated "graphic recording" — reproducing a specific hand-drawn
template the coach created, with the client's actual rank/theme data overlaid on
it. Everything (PDF parsing, rendering, PDF export) runs client-side in the
browser; report PDFs are never uploaded to a server.

## Commands

```bash
npm install
npm run dev       # vite dev server
npm run build     # tsc -b && vite build
npm run test      # vitest run (parseRanking.ts logic only)
```

There is no lint script and no CI config in this repo.

To run the app end-to-end (not just unit tests), see `.claude/skills/verify/SKILL.md`
— it documents how to drive the app with Playwright in this sandboxed environment
(Chromium/Playwright are preinstalled but not npm-linked into the project, so the
driver script has to be copied next to the global install to resolve; see the
skill for the exact recipe), how to generate a synthetic non-personal test PDF,
and how to verify the print-to-PDF export produces real vector/text content
rather than a rasterized screenshot.

## Architecture

### Data flow

`RankingInput` (PDF upload via `pdfjs-dist`, or a pasted-text textarea) →
`parseRankingFromText` (`src/lib/parseRanking.ts`) → `ParseResult` → `App.tsx`
state → `GraphicRecording` renders it, and `ParseFeedback` shows completeness
warnings (Gallup report formats/OCR can yield partial matches).

`parseRankingFromText` works by regex-matching repeated `"<rank>. <theme name>"`
occurrences against the 34 canonical Japanese theme names (Gallup reports repeat
the full ranked list several times across pages, so this is intentionally
tolerant of matching the same rank multiple times). It does not care whether the
input came from a PDF or was pasted — both funnel through the same function.

### The three "layers" of the visualization (`GraphicRecording.tsx`)

The rendered graphic isn't built from scratch — it's the coach's own hand-drawn
artwork, reconstructed as separate layers that happen to line up:

1. **Background** (`public/graphic-recording-template.svg`): the coach's blank
   template — river/ribbon path, 10 empty circle outlines (ranks 1-5, 30-34),
   small ribbon "stem" nodes for ranks 6-29, decorative flag/banner/legend.
   Inlined into the DOM (not `<img src>`) via `InlineSvg` so it survives as real
   vector paths through print-to-PDF, not a flattened raster.
2. **Illustrations** (`public/illustrations-svg/<theme-id>.svg`, 34 files): the
   coach's hand-drawn character art for each theme, also inlined via `InlineSvg`.
   These are content-only — no circle border, no background fill of their own.
   The visible circle outline for every slot comes *only* from the template
   layer; illustrations are clipped to a circle purely via the CSS container
   (`.gr__large-circle { border-radius: 50%; overflow: hidden }`). This was a
   deliberate fix: keeping the illustration's own hand-drawn circle border
   produced a visible double-outline, since it's a *different* hand-drawn circle
   than the template's for the same slot and the two never exactly coincide.
3. **Dynamic overlay**: rank badges, theme names, and domain-color coding,
   positioned via `templateLayout.ts` percentages and rendered as normal DOM
   text/badges on top.

All three layers share one coordinate convention: percentages of the
`.gr__canvas` container's width/height. `.gr__canvas` has
`aspect-ratio: 842 / 595` (the template PDF's own point-space page size), so
positions computed as percentages stay correct regardless of the template's
source resolution or how the canvas is scaled on screen.

### `templateLayout.ts`: where the badge positions come from

`TOP5_LAYOUT` / `BOTTOM5_LAYOUT` (ranks 1-5, 30-34) and `MID24_LAYOUT` (ranks
6-29) are **not** derived analytically — they're traced coordinates, baked in as
data, obtained by OpenCV circle-detection on a rasterized render of the template
PDF (see the SKILL.md "Regenerating..." sections for the exact recipe if the
coach ever provides an updated template or illustration sheet). Two non-obvious
things about this data:

- **Reading order reverses for ranks 6-29.** Ranks 1-5 and 30-34 read left to
  right, but the ribbon curves down to the right of circle 5 and flows
  *right-to-left* for 6-29 (rank 6 is the rightmost node, rank 29 the leftmost,
  right before the ribbon turns orange for rank 30). Get this backwards and
  every mid-rank label lands on the wrong node.
- **`assignLanes()` staggers the 24 mid-rank labels into vertical "lanes"**
  above their ribbon node so tightly-clustered labels don't overlap — greedy
  interval-scheduling by x-position, not a literal trace of the template's own
  hand-drawn stem branches (that turned out not to be reliably extractable from
  the vector data; see SKILL.md for what was tried and rejected).

### Illustration extraction (already done; only relevant if source art changes)

The coach's source PDFs (illustration sheet, blank template) turned out to be
pure vector strokes with no embedded fonts or raster images — typical of iPad
drawing-app PDF export. `public/illustrations-svg/*.svg` were generated by
converting the illustration sheet to SVG (`pdftocairo -svg`) and bucketing its
individual `<path>` elements by which of the 34 known circle regions contains
each path's coordinate centroid, then excluding (a) the master sheet's own
baked-in rank-number band per circle — it shows *that sheet's* fixed order, not
a given client's actual rank, and (b) each illustration's own outer
circle-boundary stroke (see the double-outline note above). This is one-time
generation, not something the running app does — there's no build step that
regenerates these from a source PDF automatically. Full recipe, including the
exact filtering heuristics and their tuned thresholds, is in
`.claude/skills/verify/SKILL.md`.

### PDF export

The "PDFとして保存" button calls `window.print()`. `@media print` rules across
`App.css`, `GraphicRecording.css`, and `index.css` hide everything except
`.print-area` and size the page to a custom `@page` (297mm × 244mm — taller than
plain A4 landscape; this was tuned empirically because Chromium's print layout
spills a near-empty second page under the "correct" computed size for this
content's aspect ratio, for reasons not fully root-caused — verify page count
directly after touching this, don't trust the CSS math). Because the
illustrations and template are inlined SVG (not `<img>`) and the badges/names
are plain DOM text, the resulting PDF has the theme art as real vector paths and
the labels as real, selectable/editable text — not a rasterized screenshot. The
coach specifically wants this so she can hand-tune the PDF afterward in a vector
editor (Illustrator).

### Domain color legend

The four CliftonStrengths domains (`src/data/themes.ts` → `DOMAINS`) are colored
to match the coach's own hand-drawn legend (red/orange/blue/purple), which does
**not** match Gallup's official domain palette. Don't "correct" these to
Gallup's colors.
