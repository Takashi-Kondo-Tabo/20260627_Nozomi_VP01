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

1. **PDF upload** → `.gr__large-circle img` count is 10 (ranks 1-5 +
   30-34), `.gr__small-dot` count is 24 (ranks 6-29); check
   `img.naturalWidth > 0` for every illustration (broken paths fail
   silently otherwise).
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
