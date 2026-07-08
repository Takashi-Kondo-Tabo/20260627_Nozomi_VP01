#!/usr/bin/env python3
"""
ブログ記事生成システム - Web GUI (Flask)

使い方:
  bash start_web.sh
  ブラウザで http://127.0.0.1:5050 を開く
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_from_directory

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

from src.generator import generate_article, batch_generate
from src.indexer import build_index, load_index
from src.indexer import search as index_search
from src.stats import compute_stats
from src.style_analyzer import analyze_style_with_claude, get_style_guide
from src.theme_suggester import suggest_themes

app = Flask(__name__, static_folder="static", static_url_path="")

CONFIG_PATH = ROOT_DIR / "config.yaml"
STYLE_CACHE = ROOT_DIR / "index" / "style_guide.txt"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 相対パスをリポジトリルート基準の絶対パスに変換
    for key in ("articles_dir", "output_dir", "index_path"):
        p = Path(cfg[key])
        if not p.is_absolute():
            cfg[key] = str(ROOT_DIR / p)
    return cfg


def get_index_safe(cfg: dict):
    try:
        return load_index(cfg["index_path"])
    except FileNotFoundError:
        return None


@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/status")
def api_status():
    cfg = load_config()
    idx = get_index_safe(cfg)
    return jsonify({
        "has_index": idx is not None,
        "total_articles": idx["total"] if idx else 0,
        "has_api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "has_style_guide": STYLE_CACHE.exists(),
    })


@app.route("/api/stats")
def api_stats():
    cfg = load_config()
    idx = get_index_safe(cfg)
    if not idx:
        return jsonify({"error": "インデックスが存在しません。先に構築してください。"}), 400
    return jsonify(compute_stats(idx))


@app.route("/api/index", methods=["POST"])
def api_build_index():
    cfg = load_config()
    result = build_index(
        articles_dir=cfg["articles_dir"],
        index_path=cfg["index_path"],
        min_length=cfg.get("min_article_length", 100),
    )
    if not result:
        return jsonify({"error": "記事が見つかりませんでした。"}), 400
    return jsonify({"total": result["total"]})


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    top = int(request.args.get("top", 5))
    cfg = load_config()
    idx = get_index_safe(cfg)
    if not idx:
        return jsonify({"error": "インデックスが存在しません。"}), 400
    results = index_search(query, idx, top_k=top)
    return jsonify({"results": results})


@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    data = request.get_json(force=True) or {}
    n = int(data.get("n", 10))
    focus = data.get("focus", "")

    cfg = load_config()
    idx = get_index_safe(cfg)
    if not idx:
        return jsonify({"error": "インデックスが存在しません。"}), 400
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません。"}), 400

    raw = suggest_themes(cfg, index=idx, n_themes=n, focus=focus)
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        themes = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return jsonify({"error": "テーマ解析に失敗しました。", "raw": raw}), 500

    return jsonify({"themes": themes})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True) or {}
    theme = data.get("theme", "").strip()
    if not theme:
        return jsonify({"error": "テーマを入力してください。"}), 400

    refs_count = data.get("refs")
    instruction = data.get("instruction", "")
    use_style_guide = data.get("use_style_guide", True)

    cfg = load_config()
    idx = get_index_safe(cfg)
    if not idx:
        return jsonify({"error": "インデックスが存在しません。"}), 400
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません。"}), 400

    style_guide = ""
    if use_style_guide:
        try:
            style_guide = get_style_guide(idx, cfg, cache_path=str(STYLE_CACHE))
        except Exception:
            pass

    article, refs = generate_article(
        theme=theme, config=cfg, index=idx,
        top_k=int(refs_count) if refs_count else None,
        style_guide=style_guide, extra_instruction=instruction,
    )

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[\s/\\:*?"<>|]', "-", theme)[:40].strip("-")
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{date_str}_{slug}.md"
    out_path.write_text(article, encoding="utf-8")

    return jsonify({
        "article": article,
        "refs": [{"title": r["title"], "date": r.get("date", ""), "score": r.get("score")} for r in refs],
        "saved_path": str(out_path.relative_to(ROOT_DIR)),
    })


@app.route("/api/batch", methods=["POST"])
def api_batch():
    data = request.get_json(force=True) or {}
    themes = [t.strip() for t in data.get("themes", []) if t.strip()]
    if not themes:
        return jsonify({"error": "テーマが指定されていません。"}), 400

    cfg = load_config()
    idx = get_index_safe(cfg)
    if not idx:
        return jsonify({"error": "インデックスが存在しません。"}), 400
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません。"}), 400

    style_guide = ""
    try:
        style_guide = get_style_guide(idx, cfg, cache_path=str(STYLE_CACHE))
    except Exception:
        pass

    out_dir = Path(cfg["output_dir"])
    results = batch_generate(
        themes=themes, config=cfg, index=idx,
        output_dir=out_dir, style_guide=style_guide,
    )

    return jsonify({
        "results": [
            {"theme": r["theme"], "path": str(Path(r["path"]).relative_to(ROOT_DIR))}
            for r in results
        ]
    })


@app.route("/api/analyze-style", methods=["POST"])
def api_analyze_style():
    cfg = load_config()
    idx = get_index_safe(cfg)
    if not idx:
        return jsonify({"error": "インデックスが存在しません。"}), 400
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません。"}), 400

    data = request.get_json(force=True) or {}
    if data.get("refresh") and STYLE_CACHE.exists():
        STYLE_CACHE.unlink()

    guide = get_style_guide(idx, cfg, cache_path=str(STYLE_CACHE))
    return jsonify({"style_guide": guide})


@app.route("/api/outputs")
def api_outputs():
    cfg = load_config()
    out_dir = Path(cfg["output_dir"])
    if not out_dir.exists():
        return jsonify({"files": []})

    files = sorted(out_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jsonify({
        "files": [
            {"name": f.name, "path": str(f.relative_to(ROOT_DIR)), "mtime": f.stat().st_mtime}
            for f in files[:50]
        ]
    })


@app.route("/api/outputs/<path:filename>")
def api_output_content(filename):
    cfg = load_config()
    out_dir = Path(cfg["output_dir"])
    target = (out_dir / filename).resolve()
    if not str(target).startswith(str(out_dir.resolve())) or not target.exists():
        return jsonify({"error": "ファイルが見つかりません。"}), 404
    return jsonify({"content": target.read_text(encoding="utf-8")})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"ブログ記事生成システム Web GUI を起動しました: http://{host}:{port}")
    if host == "0.0.0.0":
        print("同じWi-Fiネットワーク内の他端末（iPadなど）からもアクセスできます。")
    app.run(host=host, port=port, debug=False)
