# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A system that scrapes ~1,900 posts from a personal FC2 blog (https://newhabits.blog.fc2.com, active since 2008), builds a local TF-IDF search index over them, and uses the Claude API to draft new posts in the author's style, citing the specific past posts it drew on.

## Commands

```bash
# Setup
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."   # or put it in .env as ANTHROPIC_API_KEY=...

# Web GUI (primary interface)
bash start_web.sh                        # http://127.0.0.1:5050

# CLI (equivalent functionality)
python main.py index                     # (re)build the search index from articles/
python main.py stats                     # year/month breakdown, top keywords
python main.py search "keyword"          # TF-IDF search over indexed articles
python main.py suggest --focus "..."     # propose unwritten themes
python main.py generate "theme" --preview
python main.py batch themes.txt          # one theme per line
python main.py analyze-style [--refresh] # cache index/style_guide.txt
python main.py interactive               # guided suggest -> pick -> generate flow

# One-time / maintenance scraper scripts (run locally, not from this sandbox —
# the sandbox's proxy blocks the FC2 domain)
python scraper/scrape_fc2.py             # crawl and save articles/*.md
python scraper/dedup.py                  # collapse http/https/old-domain/#anchor URL variants
python scraper/backfill_dates.py         # fill date: from body text when the scraper found none
```

No test suite exists. Validate changes by running the relevant CLI command or hitting the corresponding `/api/*` route and inspecting output.

## Architecture

**Two frontends, one core.** `main.py` (CLI, via `click`) and `webapp/app.py` (Flask, via `/api/*` JSON routes) are both thin wrappers around `src/`. Any new capability should go in `src/` first, then be exposed from both entry points — don't put logic directly in `main.py` or `app.py`.

**Data flow**: `articles/*.md` (YAML front matter: `title`, `date`, `tags`, `source_url`) → `src/indexer.build_index()` → `index/index.json` (TF-IDF vectors, no external ML deps) → `src/indexer.search()` for retrieval → `src/generator.generate_article()` sends the top-k matched articles' full text plus a cached style guide as context to Claude → output saved to `output/*.md` with a "参考にした過去記事" (reference articles) footer of title/date/URL links appended by `_append_references`.

**Style guide caching**: `src/style_analyzer.get_style_guide()` samples articles, computes local stats (avg sentence length, heading/list usage) plus an LLM-written style summary, and caches the result at `index/style_guide.txt`. Every generation path (`generate`, `batch`, `interactive`, and the web `/api/generate`) reads this cache rather than re-analyzing each time; delete the file or pass `--refresh` / `refresh: true` to force re-analysis.

**Search is homegrown TF-IDF**, not an embedding/vector DB. Japanese text is tokenized via 2-gram/3-gram over the Unicode Han+Kana range plus 2+ char English words (`src/indexer.tokenize`); there's no MeCab or other morphological analyzer dependency. Keep this in mind before "fixing" search relevance — it's a deliberate zero-dependency tradeoff, not an oversight.

**Python 3.9 compatibility is required.** The target machines run the macOS Xcode Command Line Tools' Python 3.9.6, not a modern one. Do not use `X | None` union syntax, `list[X]`/`dict[K,V]` as runtime annotations where 3.9 would choke, or other 3.10+-only syntax — use `typing.Optional`/`typing.List` etc. This has broken things before (see git history: "Fix Python 3.9 compatibility").

**Scraper URL normalization matters.** The blog has moved domains over time (`blog33.fc2.com` → `blog.fc2.com`) and pages carry `#cm` comment anchors; `scraper/dedup.py`'s `normalize_url()` is what collapses these into one canonical article. If re-scraping, dedup before indexing or the same post will appear multiple times in search results and suggestions.

## Environment notes

This sandbox cannot reach the live FC2 blog (proxy blocks it) — the scraper must be run on the user's local Mac, where the actual `articles/` corpus and `.env` live inside an iCloud Drive folder shared across the user's machines. `config.yaml` paths (`articles_dir`, `output_dir`, `index_path`) are relative to the repo root; `webapp/app.py`'s `load_config()` resolves them against `ROOT_DIR` so the Flask process can be launched from any working directory.
