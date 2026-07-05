#!/usr/bin/env python3
"""
articles/ フォルダ内の重複記事を削除する。
source_url が同じファイルのうち、最初の1件だけを残す。
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

ARTICLES_DIR = Path(__file__).parent.parent / "articles"


def main():
    files = sorted(ARTICLES_DIR.glob("*.md"))
    print(f"総ファイル数: {len(files)} 件")

    # source_url ごとにファイルをグループ化
    url_to_files = defaultdict(list)
    no_url = []

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"source_url: (.+)", text)
        if m:
            url = m.group(1).strip()
            url_to_files[url].append(f)
        else:
            no_url.append(f)

    # 重複を検出
    duplicates = {url: fs for url, fs in url_to_files.items() if len(fs) > 1}
    print(f"重複URL: {len(duplicates)} 件")

    total_delete = sum(len(fs) - 1 for fs in duplicates.values())
    print(f"削除予定ファイル数: {total_delete} 件")

    if total_delete == 0:
        print("重複はありません。")
        return

    # 確認
    print("\n削除しますか？ (y/N): ", end="")
    ans = input().strip().lower()
    if ans != "y":
        print("キャンセルしました。")
        return

    # 重複を削除（最初のファイルを残す）
    deleted = 0
    for url, fs in duplicates.items():
        keep = fs[0]   # 最初のファイルを残す
        for f in fs[1:]:
            f.unlink()
            deleted += 1

    print(f"\n完了! {deleted} 件削除しました。")
    remaining = len(list(ARTICLES_DIR.glob("*.md")))
    print(f"残りファイル数: {remaining} 件")
    print("\n次のステップ: インデックスを再構築してください")
    print("  /Library/Developer/CommandLineTools/usr/bin/python3 main.py index")


if __name__ == "__main__":
    main()
