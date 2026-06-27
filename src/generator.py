"""
Claude APIを使って新しいブログ記事を生成する。
参照記事をコンテキストとして渡し、著者スタイルを模倣する。
"""

from pathlib import Path

import anthropic

from .indexer import load_index, search


def _read_full_article(path: str, max_chars: int = 1500) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]
    except OSError:
        return ""


def _build_system_prompt(config: dict) -> str:
    lang = config.get("blog_language", "ja")
    author = config.get("author_name", "")
    style_hint = config.get("blog_style_hint", "")

    parts = []
    if lang == "ja":
        parts.append("あなたは経験豊富なブログライターです。")
    else:
        parts.append("You are an experienced blog writer.")

    if author:
        parts.append(f"著者名: {author}")

    if style_hint:
        parts.append(f"文体の特徴: {style_hint}")

    parts.append(
        "提供された参照記事の文体・構成・視点を学習し、"
        "同じ著者が書いたと感じられる自然な新記事を作成してください。"
        "参照記事の内容をそのままコピーせず、新テーマに適した独自の内容を生成してください。"
    )

    return "\n".join(parts)


def _build_user_prompt(theme: str, refs: list[dict], config: dict) -> str:
    ref_texts = []
    for i, ref in enumerate(refs, 1):
        body = _read_full_article(ref["path"])
        ref_texts.append(
            f"=== 参照記事 {i}: {ref['title']} ({ref.get('date', '')}) ===\n{body}"
        )

    refs_block = "\n\n".join(ref_texts)

    return f"""以下の参照記事を参考にして、新しいブログ記事を書いてください。

【新記事のテーマ】
{theme}

【参照記事】
{refs_block}

【出力形式】
Markdownで出力してください。先頭にYAML front matter（title, date, tags）を付けてください。
本文は見出し・段落・必要に応じてリストを使い、2000〜3000文字程度を目安にしてください。
"""


def generate_article(
    theme: str,
    config: dict,
    index: dict | None = None,
    index_path: str | None = None,
    top_k: int | None = None,
) -> str:
    if index is None:
        index = load_index(index_path or config["index_path"])

    k = top_k or config.get("max_reference_articles", 5)
    refs = search(theme, index, top_k=k)

    client = anthropic.Anthropic()

    system = _build_system_prompt(config)
    user = _build_user_prompt(theme, refs, config)

    message = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=config.get("max_tokens", 4096),
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    return message.content[0].text, refs
