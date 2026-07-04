"""
インデックス済み記事の統計・傾向分析。
"""

import re
from collections import Counter
from pathlib import Path


def compute_stats(index: dict) -> dict:
    docs = index.get("docs", [])
    if not docs:
        return {}

    # 年別記事数
    by_year: Counter = Counter()
    for d in docs:
        m = re.match(r"(\d{4})", d.get("date", ""))
        if m:
            by_year[m.group(1)] += 1

    # 月別記事数（全期間）
    by_month: Counter = Counter()
    for d in docs:
        m = re.match(r"(\d{4}-\d{2})", d.get("date", ""))
        if m:
            by_month[m.group(1)] += 1

    # 記事数が多い月TOP5
    top_months = by_month.most_common(5)

    # IDF分布から重要キーワードを抽出
    idf = index.get("idf", {})
    # IDF中間帯（ありふれすぎず、希少すぎない）のキーワードを取得
    keywords = sorted(
        [(t, v) for t, v in idf.items() if 2.0 < v < 5.5 and len(t) >= 2],
        key=lambda x: x[1],
    )[:30]

    return {
        "total": index.get("total", len(docs)),
        "by_year": dict(sorted(by_year.items())),
        "top_months": top_months,
        "top_keywords": [k for k, _ in keywords[:20]],
        "built_at": index.get("built_at", ""),
    }


def format_stats_table(stats: dict) -> str:
    """統計情報を表形式の文字列で返す。"""
    lines = [
        f"総記事数: {stats['total']} 件",
        f"インデックス構築日時: {stats.get('built_at', 'N/A')}",
        "",
        "【年別記事数】",
    ]
    for year, cnt in sorted(stats.get("by_year", {}).items()):
        bar = "█" * (cnt // 5)
        lines.append(f"  {year}: {cnt:4d}件  {bar}")

    lines += ["", "【記事数の多い月 TOP5】"]
    for month, cnt in stats.get("top_months", []):
        lines.append(f"  {month}: {cnt} 件")

    lines += ["", "【頻出キーワード】"]
    lines.append("  " + "、".join(stats.get("top_keywords", [])))

    return "\n".join(lines)
