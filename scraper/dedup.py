#!/usr/bin/env python3
"""
articles/ フォルダ内の重複記事を削除する。
source_url を正規化（ドメイン統一・アンカー除去）してから比較する。
"""

import re
from pathlib import Path
from collections import defaultdict

ARTICLES_DIR = Path(__file__).parent.parent / "articles"


def normalize_url(url: str) -> str:
    """
    URLを正規化して同一記事を同一キーにまとめる。
    - http → https
    - 旧ドメイン(blog33.fc2.com) → 新ドメイン(blog.fc2.com)
    - #以降のアンカーを除去
    - 末尾スラッシュを除去
    """
    url = url.strip()
    url = url.split("#")[0]          # アンカー除去
    url = url.rstrip("/")
    url = url.replace("http://", "https://")
    url = re.sub(r"newhabits\.blog\d*\.fc2\.com", "newhabits.blog.fc2.com", url)
    return url


def main():
    files = sorted(ARTICLES_DIR.glob("*.md"))
    print(f"総ファイル数: {len(files)} 件")

    # 正規化URLごとにファイルをグループ化
    url_to_files = defaultdict(list)

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"source_url: (.+)", text)
        if m:
            norm = normalize_url(m.group(1))
            url_to_files[norm].append(f)

    # 重複を検出
    duplicates = {url: fs for url, fs in url_to_files.items() if len(fs) > 1}
    total_delete = sum(len(fs) - 1 for fs in duplicates.values())

    print(f"重複グループ: {len(duplicates)} 件")
    print(f"削除予定ファイル数: {total_delete} 件")

    if total_delete == 0:
        print("重複はありません。")
        return

    # 削除予定のサンプルを表示
    print("\n【削除例（最初の5グループ）】")
    for url, fs in list(duplicates.items())[:5]:
        print(f"  URL: {url}")
        print(f"    残す: {fs[0].name}")
        for f in fs[1:]:
            print(f"    削除: {f.name}")

    print(f"\n削除しますか？ (y/N): ", end="")
    ans = input().strip().lower()
    if ans != "y":
        print("キャンセルしました。")
        return

    # 重複を削除（最初のファイルを残す）
    deleted = 0
    for url, fs in duplicates.items():
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
