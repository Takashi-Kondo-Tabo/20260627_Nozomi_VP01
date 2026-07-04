"""
既存記事から著者固有の文体パターンを抽出する。
抽出した特徴をClaude APIへのプロンプトに注入することで
より著者らしい文章を生成できる。
"""

import math
import random
import re
from collections import Counter
from pathlib import Path

import anthropic


def _sample_articles(index: dict, n: int = 20) -> list[dict]:
    """インデックスからランダムにサンプル記事を取得する。"""
    docs = index.get("docs", [])
    if len(docs) <= n:
        return docs
    return random.sample(docs, n)


def _read_bodies(docs: list[dict], max_chars: int = 800) -> list[str]:
    bodies = []
    for d in docs:
        try:
            text = Path(d["path"]).read_text(encoding="utf-8", errors="ignore")
            # front matter を除去
            if text.startswith("---"):
                end = text.find("---", 3)
                text = text[end + 3:].strip() if end != -1 else text
            bodies.append(text[:max_chars])
        except OSError:
            pass
    return bodies


def _local_style_stats(bodies: list[str]) -> dict:
    """文体の統計情報をローカルで計算する（API不要）。"""
    all_text = "\n".join(bodies)

    # 文末表現の分布
    endings = Counter()
    for sent in re.findall(r"[^。！？\n]+[。！？]", all_text):
        tail = sent.strip()[-3:]
        endings[tail] += 1

    # 平均文長（文字数）
    sentences = re.findall(r"[^。！？\n]+[。！？]", all_text)
    avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

    # 段落あたりの平均文数
    paragraphs = [p.strip() for p in all_text.split("\n\n") if p.strip()]
    avg_sents_per_para = (
        sum(len(re.findall(r"[。！？]", p)) for p in paragraphs)
        / max(len(paragraphs), 1)
    )

    # 見出しの使用頻度
    headings = re.findall(r"^#{1,4} .+", all_text, re.MULTILINE)
    heading_ratio = len(headings) / max(len(paragraphs), 1)

    # リスト（箇条書き）の使用頻度
    list_items = re.findall(r"^[-・*] .+", all_text, re.MULTILINE)
    list_ratio = len(list_items) / max(len(paragraphs), 1)

    # 最頻出の文末（上位5件）
    top_endings = [e for e, _ in endings.most_common(5)]

    return {
        "avg_sentence_length": round(avg_len, 1),
        "avg_sentences_per_paragraph": round(avg_sents_per_para, 1),
        "heading_usage": "多い" if heading_ratio > 0.3 else "少ない",
        "list_usage": "多い" if list_ratio > 0.2 else "少ない",
        "top_sentence_endings": top_endings,
    }


def analyze_style_with_claude(index: dict, config: dict) -> str:
    """
    Claude APIを使って著者の文体を詳細分析し、
    文章生成時に使えるスタイルガイドを返す。
    """
    docs = _sample_articles(index, n=15)
    bodies = _read_bodies(docs)

    if not bodies:
        return ""

    local_stats = _local_style_stats(bodies)

    sample_text = "\n\n---\n\n".join(bodies[:8])

    prompt = f"""以下は、あるブログ著者の記事サンプルです。

{sample_text}

---

この著者の文体を分析して、以下の観点でまとめてください（各項目1〜2文で簡潔に）:

1. 文体・口調（です・ます調か、だ・である調か、砕けた表現の有無など）
2. 文の長さとリズム（短文多用か、長文多用か）
3. 構成パターン（冒頭の書き方、展開の仕方、締めの特徴）
4. よく使う表現・言い回しの特徴
5. 読者への語りかけ方（直接的か間接的か）
6. 具体例・体験談の使い方

【補足情報（自動計算）】
- 平均文長: {local_stats['avg_sentence_length']} 文字
- 段落あたり平均文数: {local_stats['avg_sentences_per_paragraph']}
- 見出しの使用: {local_stats['heading_usage']}
- 箇条書きの使用: {local_stats['list_usage']}
- よく使う文末: {', '.join(local_stats['top_sentence_endings'])}

分析結果は「新しい記事を書く際の文体ガイド」として使えるよう、
箇条書きでまとめてください。
"""

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def get_style_guide(index: dict, config: dict, cache_path: str = "index/style_guide.txt") -> str:
    """
    文体ガイドを返す。キャッシュがあればそれを使う。
    """
    p = Path(cache_path)
    if p.exists():
        return p.read_text(encoding="utf-8")

    print("文体を分析中...")
    guide = analyze_style_with_claude(index, config)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(guide, encoding="utf-8")
    return guide
