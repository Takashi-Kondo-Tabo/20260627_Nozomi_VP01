---
name: verify
description: Build/launch/drive recipe for this repo (CliftonStrengths 34 visualizer, Vite+React+TS). Use when verifying changes end-to-end in a browser.
---

# Verify recipe for this repo

Single-page Vite + React + TS app, no backend. All PDF parsing runs
client-side in the browser via pdfjs-dist.

## Build & launch

```bash
npm install
npx vite --port 5183 --strictPort &   # dev server, http://localhost:5183/
```

## Unit tests (parser logic only — not a substitute for driving the UI)

```bash
npx vitest run
```

## Driving the app with Playwright

Playwright/Chromium are pre-installed but not npm-linked into this
project. Resolve them by copying the driver script next to the global
install (ESM resolution walks up from the script's own path, `NODE_PATH`
does not work for ESM):

```bash
cp my-script.mjs /opt/node22/lib/node_modules/verify.mjs
node /opt/node22/lib/node_modules/verify.mjs
rm /opt/node22/lib/node_modules/verify.mjs
```

Launch Chromium with `executablePath: '/opt/pw-browsers/chromium'`.

## Generating a synthetic test PDF (never use a real client's report)

Gallup CliftonStrengths PDFs contain personal data (name, birthdate) —
never commit one or hardcode its contents. To test the PDF-upload flow,
generate a synthetic fixture with `pdf-lib` + `@pdf-lib/fontkit`,
embedding the system Japanese font at
`/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf` (StandardFonts
Helvetica cannot encode Japanese glyphs). Write `N. <theme name ja>`
lines for a fictional 1–34 permutation (e.g. `THEMES` reversed) and
feed the resulting PDF to `input[type=file]` via
`page.locator('input[type=file]').setInputFiles(path)`.

## Flows worth driving

1. **PDF upload** → `.gr__large-illustration svg` count is 10 (ranks
   1-5 + 30-34, inline-fetched from `public/illustrations-svg/*.svg`
   by `InlineSvg`), `.gr__small-dot` count is 24 (ranks 6-29).
2. **Paste fallback** → fill `textarea`, click the button with text
   `解析する`, same assertions.
3. **Incomplete input probe** → paste only ranks 1–10, confirm
   `.ranking-result__incomplete` shows the correct missing-rank list
   (11–34).

Check `page.on('console', ...)` / `pageerror` for unexpected errors
(pdfjs worker wiring is a common source of silent failures).

## Verifying the PDF export (print-to-PDF)

The "PDFとして保存" button calls `window.print()`; `@media print` CSS
in App.css/GraphicRecording.css/index.css hides the input forms and
sizes `.gr__canvas` to a custom `@page` (297mm × 244mm — taller than
plain A4 landscape, empirically tuned so Chromium's print layout
doesn't spill a near-empty page 2; don't trust the aspect-ratio math
alone, verify page count directly after any layout change).

Playwright's `page.pdf()` exercises the same print CSS path
non-interactively (no OS dialog):

```js
await page.pdf({
  path: 'out.pdf',
  landscape: true,
  printBackground: true,
  preferCSSPageSize: true, // required to respect the custom @page size
})
```

Then check with poppler-utils (`apt-get install poppler-utils` if
missing):

```bash
pdfinfo out.pdf | grep Pages   # must be 1, not 2
pdftotext out.pdf - | head     # must contain real Japanese text,
                                # confirming labels are text objects,
                                # not a rasterized screenshot
```

## Verifying the illustrations stay vector paths (not rasterized)

`public/illustrations-svg/*.svg` are real vector paths extracted from
the coach's source PDF (see below) and inlined into the DOM via
`InlineSvg` (fetch + `dangerouslySetInnerHTML`) rather than referenced
via `<img src>`, specifically so they survive as PDF path objects
through print-to-PDF. `pdfimages -list out.pdf` will still show a
handful of small ~90×90 grayscale JPEG tiles — those are the CSS
`box-shadow` on the rank badges getting rasterized (Chromium can't
express box-shadow as a native PDF primitive), not the illustrations.
To confirm the character line art itself is still vector, don't trust
`pdfimages` alone — render at high DPI and zoom into a dense area
(e.g. hair hachure lines):

```bash
pdftoppm -f 1 -l 1 -r 600 -png out.pdf zoom-check
# then crop e.g. the top-left illustration and upscale with
# Image.NEAREST in PIL — real vector paths stay crisp at any zoom;
# a rasterized fallback shows visible pixelation/blur.
```

### Regenerating the SVG illustrations from a new source sheet

If the coach provides an updated illustration sheet PDF: check it's
vector first (`pdfimages -list` and `pdffonts` both empty means it's
pure vector strokes, typical of iPad drawing-app PDF export). Render
it at 400dpi with `pdftoppm`, run the same OpenCV circle-detection
approach used for `circle_candidates.json` (Hough circles per
quadrant, tuned to detect theme-count+1 to catch the domain-flag
circle, then split into two rows and drop the flag) to get each
theme's `(cx, cy, r)` in pixel space, convert to the PDF's point space
(`pt = px * 72 / 400`), then bucket the source PDF's vector `<path>`
elements (via `pdftocairo -svg`) by which circle contains each path's
coordinate centroid. Exclude paths whose centroid falls in the bottom
~55% of a circle's radius below center — that's the master sheet's own
baked-in rank number/name band, which would otherwise conflict with
the app's own rank badge for a given client's actual ranking. **Also
exclude each illustration's own outer circle-boundary stroke**
(bounding box width AND height both > `r*1.4`, centroid within
`r*1.12` of the circle center — reliably exactly one path per circle):
the app overlays illustrations on the *template's* circle outline (a
separately hand-drawn circle in a different source PDF), so keeping
the illustration's own ring too produces a visible double-outline that
doesn't line up with the template — this was reported as "background
misalignment" and the fix was dropping that one path, not
repositioning anything.

## The background template is also vector

`public/graphic-recording-template.svg` is `pdftocairo -svg` output
of the coach's blank template PDF (`viewBox="0 0 842 595"`, i.e. its
native point space — same convention as the illustration circles
above), inlined via `InlineSvg` the same way as the illustrations.
`.gr__canvas`'s `aspect-ratio` CSS must stay `842 / 595` to match.
`TOP5_LAYOUT` / `BOTTOM5_LAYOUT` / `MID24_LAYOUT` in
`templateLayout.ts` are percentages, so they're resolution-independent
and didn't need to change when the background switched from a raster
PNG render of that same PDF to this native SVG.

Don't re-derive `MID24_LAYOUT` from the template's vector `<path>`
data by searching for small circular bounding boxes — that was tried
and it finds the wrong set of marks (there's a uniformly-sized decoy
cluster elsewhere on the page); the ribbon nodes aren't reliably
isolable as single small closed paths. The existing raster
Hough-circle-detected values are the ones actually in use.
