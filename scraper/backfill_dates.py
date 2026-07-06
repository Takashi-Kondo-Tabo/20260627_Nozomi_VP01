#!/usr/bin/env python3
"""
articles/ 内の日付が空欄の記事について、本文中の日付表記から
日付を推定して front matter に補完する。

抽出戦略（優先順）:
  1. 本文中の「関連記事」リストに自分のタイトルが (YYYY/MM/DD) 形式で
     載っている場合、それを使う
  2. 本文冒頭付近にある YY.MM.DD / YYYY/MM/DD / YYYY年MM月DD日 形式の
     日付を使う（全角数字も対応）
  3. 見つからない場合は空欄のまま
"""

import re
from pathlib import Path

ARTICLES_DIR = Path(__file__).parent.parent / "articles"

ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")


def normalize_digits(text: str) -> str:
    return text.translate(ZEN2HAN)


def extract_title(text: str) -> str:
    m = re.search(r'^title:\s*"?(.+?)"?\s*$', text, re.MULTILINE)
    return m.group(1) if m else ""


def find_date_via_related_list(body: str, title: str) -> str:
    """本文中の「タイトル (YYYY/MM/DD)」形式から日付を取得する。"""
    if not title:
        return ""
    norm_body = normalize_digits(body)
    pattern = re.escape(title) + r"\s*[\(（](\d{4})[/／](\d{1,2})[/／](\d{1,2})[\)）]"
    m = re.search(pattern, norm_body)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ""


def find_date_in_body(body: str) -> str:
    """本文冒頭付近の日付表記から日付を推定する。"""
    norm_body = normalize_digits(body)
    head = norm_body[:500]  # 冒頭500文字を優先的に探索

    patterns = [
        r"(\d{4})[年/.\-](\d{1,2})[月/.\-](\d{1,2})日?",  # 2008年08月26日 / 2008/08/26 / 2008.08.26
        r"(\d{2})[.\-](\d{1,2})[.\-](\d{1,2})(?!\d)",       # 08.10.17 （2桁年）
    ]

    for text in (head, norm_body):
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                y, mo, d = m.groups()
                year = int(y)
                if year < 100:
                    year += 2000 if year < 50 else 1900
                try:
                    mo_i, d_i = int(mo), int(d)
                    if 1 <= mo_i <= 12 and 1 <= d_i <= 31 and 1990 <= year <= 2030:
                        return f"{year}-{mo_i:02d}-{d_i:02d}"
                except ValueError:
                    continue
    return ""


def process_file(path: Path) -> str:
    """
    ファイルを処理し、日付が補完できた場合は 'filled'、
    すでに日付がある場合は 'skipped'、
    見つからなかった場合は 'not_found' を返す。
    """
    text = path.read_text(encoding="utf-8", errors="ignore")

    m = re.search(r"^date:[ \t]*(.*)$", text, re.MULTILINE)
    if not m:
        return "no_field"
    if m.group(1).strip():
        return "skipped"

    if not text.startswith("---"):
        return "no_field"
    end = text.find("---", 3)
    if end == -1:
        return "no_field"

    front = text[:end]
    body = text[end + 3:]

    title = extract_title(front)
    date = find_date_via_related_list(body, title) or find_date_in_body(body)

    if not date:
        return "not_found"

    new_front = re.sub(r"^date:[ \t]*$", f"date: {date}", front, flags=re.MULTILINE)
    new_text = new_front + "---" + body
    path.write_text(new_text, encoding="utf-8")
    return "filled"


def main():
    files = sorted(ARTICLES_DIR.glob("*.md"))
    print(f"総ファイル数: {len(files)} 件")

    counts = {"filled": 0, "skipped": 0, "not_found": 0, "no_field": 0}

    for i, f in enumerate(files, 1):
        result = process_file(f)
        counts[result] += 1
        if i % 200 == 0:
            print(f"  {i}/{len(files)} 処理済み...")

    print("\n結果:")
    print(f"  補完成功: {counts['filled']} 件")
    print(f"  既に日付あり: {counts['skipped']} 件")
    print(f"  日付が見つからず: {counts['not_found']} 件")
    print(f"  front matter異常: {counts['no_field']} 件")

    if counts["filled"] > 0:
        print("\n次のステップ: インデックスを再構築してください")
        print("  python3 main.py index")


if __name__ == "__main__":
    main()
