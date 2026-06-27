"""
既存記事のインデックスを分析して、まだ書かれていない新テーマを提案する。
"""

import json
import re
from collections import Counter

import anthropic

from .indexer import load_index, tokenize


def _extract_top_keywords(index: dict, top_n: int = 100) -> list[str]:
    idf = index["idf"]
    # IDF が低い（＝ありふれた）単語を除外し、中程度のIDF帯を取得
    candidates = [
        (t, v) for t, v in idf.items()
        if 1.5 < v < 6.0 and len(t) >= 2
    ]
    candidates.sort(key=lambda x: x[1])
    return [t for t, _ in candidates[:top_n]]


def _sample_titles(index: dict, n: int = 30) -> list[str]:
    docs = index.get("docs", [])
    step = max(1, len(docs) // n)
    return [docs[i]["title"] for i in range(0, len(docs), step)][:n]


def suggest_themes(
    config: dict,
    index: dict | None = None,
    index_path: str | None = None,
    n_themes: int = 10,
    focus: str = "",
) -> str:
    if index is None:
        index = load_index(index_path or config["index_path"])

    keywords = _extract_top_keywords(index)
    titles = _sample_titles(index)

    focus_clause = f"\n特に「{focus}」に関連するテーマを重視してください。" if focus else ""

    prompt = f"""あなたは経験豊富なブログ編集者です。

以下のデータは、あるブログの過去記事の特徴を示しています。

【頻出キーワード（一部）】
{', '.join(keywords[:50])}

【記事タイトルのサンプル】
{chr(10).join(f'- {t}' for t in titles)}

このブログの著者が「まだ書いていなそうな」新しいテーマを{n_themes}個提案してください。{focus_clause}

各テーマについて：
1. テーマタイトル（具体的で魅力的な記事タイトル形式）
2. 一行の説明（なぜ読者に価値があるか）
3. 関連キーワード3〜5個

JSON配列形式で出力してください：
[
  {{
    "title": "テーマタイトル",
    "description": "説明",
    "keywords": ["kw1", "kw2", "kw3"]
  }},
  ...
]
"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
