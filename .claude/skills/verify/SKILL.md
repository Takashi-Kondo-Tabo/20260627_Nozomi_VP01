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

1. **PDF upload** → `.ranking-result__list` renders 34
   `.ranking-result__item`s, rank 1 and rank 34 match the fixture.
2. **Paste fallback** → fill `textarea`, click the button with text
   `解析する`, same assertions.
3. **Incomplete input probe** → paste only ranks 1–10, confirm
   `.ranking-result__incomplete` shows the correct missing-rank list
   (11–34).

Check `page.on('console', ...)` / `pageerror` for unexpected errors
(pdfjs worker wiring is a common source of silent failures).
