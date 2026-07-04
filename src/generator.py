"""
Claude APIを使って新しいブログ記事を生成する。
参照記事と文体ガイドをコンテキストとして渡し、著者スタイルを忠実に模倣する。
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


def _build_system_prompt(config: dict, style_guide: str = "") -> str:
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

    if style_guide:
        parts.append(f"【著者の文体ガイド（分析済み）】\n{style_guide}")
    elif style_hint:
        parts.append(f"文体の特徴: {style_hint}")

    parts.append(
        "提供された参照記事の文体・構成・視点を学習し、"
        "同じ著者が書いたと感じられる自然な新記事を作成してください。"
        "参照記事の内容をそのままコピーせず、新テーマに適した独自の内容を生成してください。"
    )

    return "\n".join(parts)


def _build_user_prompt(theme: str, refs: list[dict], config: dict, extra_instruction: str = "") -> str:
    ref_texts = []
    for i, ref in enumerate(refs, 1):
        body = _read_full_article(ref["path"])
        ref_texts.append(
            f"=== 参照記事 {i}: {ref['title']} ({ref.get('date', '')}) ===\n{body}"
        )

    refs_block = "\n\n".join(ref_texts) if ref_texts else "（参照記事なし）"
    extra = f"\n【追加指示】\n{extra_instruction}" if extra_instruction else ""

    return f"""以下の参照記事を参考にして、新しいブログ記事を書いてください。

【新記事のテーマ】
{theme}

【参照記事】
{refs_block}

【出力形式】
Markdownで出力してください。先頭にYAML front matter（title, date, tags）を付けてください。
本文は見出し・段落・必要に応じてリストを使い、2000〜3000文字程度を目安にしてください。{extra}
"""


def generate_article(
    theme: str,
    config: dict,
    index: dict | None = None,
    index_path: str | None = None,
    top_k: int | None = None,
    style_guide: str = "",
    extra_instruction: str = "",
) -> tuple[str, list[dict]]:
    if index is None:
        index = load_index(index_path or config["index_path"])

    k = top_k or config.get("max_reference_articles", 5)
    refs = search(theme, index, top_k=k)

    client = anthropic.Anthropic()
    system = _build_system_prompt(config, style_guide=style_guide)
    user = _build_user_prompt(theme, refs, config, extra_instruction=extra_instruction)

    message = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=config.get("max_tokens", 4096),
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    return message.content[0].text, refs


def batch_generate(
    themes: list[str],
    config: dict,
    index: dict,
    output_dir: Path,
    style_guide: str = "",
    on_progress=None,
) -> list[dict]:
    """
    複数テーマを順番に生成して output_dir に保存する。
    on_progress(i, total, theme, path) コールバックで進捗を通知する。
    """
    from datetime import datetime
    import re

    results = []
    total = len(themes)

    for i, theme in enumerate(themes, 1):
        article, refs = generate_article(
            theme=theme, config=config, index=index, style_guide=style_guide
        )

        slug = re.sub(r'[\s/\\:*?"<>|]', "-", theme)[:40].strip("-")
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{date_str}_{slug}.md"
        out_path = output_dir / filename
        out_path.write_text(article, encoding="utf-8")

        result = {"theme": theme, "path": str(out_path), "refs": refs}
        results.append(result)

        if on_progress:
            on_progress(i, total, theme, str(out_path))

    return results
