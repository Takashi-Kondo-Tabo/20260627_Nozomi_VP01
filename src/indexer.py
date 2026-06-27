"""
既存ブログ記事をスキャンしてTF-IDFベースの検索インデックスを構築する。
対応フォーマット: .md / .txt
"""

import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_metadata(text: str, filepath: Path) -> dict[str, Any]:
    """
    Front matter（YAML形式）またはファイル名から日付・タイトルを抽出する。
    """
    title = ""
    date = ""
    body = text

    # YAML front matter の解析
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(text[3:end])
                if isinstance(fm, dict):
                    title = str(fm.get("title", ""))
                    date = str(fm.get("date", ""))
                body = text[end + 3:].strip()
            except yaml.YAMLError:
                pass

    if not title:
        title = filepath.stem.replace("-", " ").replace("_", " ")

    # ファイル名から日付を推測（例: 2024-01-15-article-title.md）
    if not date:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", filepath.stem)
        if m:
            date = m.group(1)

    return {"title": title, "date": date, "body": body, "path": str(filepath)}


def tokenize(text: str) -> list[str]:
    """
    日本語・英語混在テキストをトークン化する。
    簡易実装として1〜3文字の日本語n-gramと英単語を組み合わせる。
    """
    tokens = []

    # 英単語
    tokens += re.findall(r"[a-zA-Z]{2,}", text.lower())

    # 日本語: 2-gramと3-gram
    ja_chars = re.sub(r"[^぀-鿿゠-ヿ]", "", text)
    for n in (2, 3):
        tokens += [ja_chars[i:i+n] for i in range(len(ja_chars) - n + 1)]

    return tokens


def build_index(articles_dir: str, index_path: str, min_length: int = 100) -> dict:
    articles_dir = Path(articles_dir)
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    files = list(articles_dir.rglob("*.md")) + list(articles_dir.rglob("*.txt"))
    if not files:
        print(f"[警告] {articles_dir} に記事が見つかりませんでした。")
        return {}

    print(f"{len(files)} 件の記事を処理中...")

    docs: list[dict] = []
    tf_map: list[dict[str, float]] = []  # term frequency per document
    df: dict[str, int] = defaultdict(int)  # document frequency

    for i, fp in enumerate(files, 1):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if len(text) < min_length:
            continue

        meta = extract_metadata(text, fp)
        tokens = tokenize(meta["body"])
        if not tokens:
            continue

        tf_raw = Counter(tokens)
        total = sum(tf_raw.values())
        tf = {t: c / total for t, c in tf_raw.items()}

        for t in tf:
            df[t] += 1

        docs.append(meta)
        tf_map.append(tf)

        if i % 100 == 0:
            print(f"  {i}/{len(files)} 処理済み")

    n = len(docs)
    print(f"有効な記事: {n} 件")

    # IDF計算 & TF-IDF ベクトルを格納
    idf: dict[str, float] = {
        t: math.log((n + 1) / (cnt + 1)) + 1
        for t, cnt in df.items()
    }

    index = {
        "built_at": datetime.now().isoformat(),
        "total": n,
        "idf": idf,
        "docs": [
            {
                "id": i,
                "title": d["title"],
                "date": d["date"],
                "path": d["path"],
                "preview": d["body"][:200],
                "tf": tf_map[i],
            }
            for i, d in enumerate(docs)
        ],
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"インデックスを保存しました: {index_path}")
    return index


def load_index(index_path: str) -> dict:
    p = Path(index_path)
    if not p.exists():
        raise FileNotFoundError(
            f"インデックスが見つかりません: {p}\n"
            "`python main.py index` を先に実行してください。"
        )
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def search(query: str, index: dict, top_k: int = 5) -> list[dict]:
    """
    クエリに対してTF-IDFコサイン類似度で上位k件の記事を返す。
    """
    idf = index["idf"]
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    q_tf_raw = Counter(q_tokens)
    q_total = sum(q_tf_raw.values())
    q_vec: dict[str, float] = {
        t: (c / q_total) * idf.get(t, 0) for t, c in q_tf_raw.items()
    }

    q_norm = math.sqrt(sum(v ** 2 for v in q_vec.values())) or 1.0

    scores: list[tuple[float, dict]] = []
    for doc in index["docs"]:
        tf = doc["tf"]
        dot = sum(q_vec.get(t, 0) * tf.get(t, 0) * idf.get(t, 0) for t in q_vec)
        d_norm = math.sqrt(sum((tf.get(t, 0) * idf.get(t, 0)) ** 2 for t in tf)) or 1.0
        score = dot / (q_norm * d_norm)
        scores.append((score, doc))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [{"score": round(s, 4), **d} for s, d in scores[:top_k] if s > 0]
