#!/usr/bin/env python3
"""
FC2ブログ記事スクレイパー
対象: https://newhabits.blog.fc2.com

使い方:
  pip install requests beautifulsoup4 lxml
  python scrape_fc2.py

記事を ../articles/ ディレクトリにMarkdownファイルとして保存します。
"""

import os
import re
import time
import random
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://newhabits.blog.fc2.com"
OUTPUT_DIR = Path(__file__).parent.parent / "articles"

# サーバーへの負荷を軽減するためのウェイト（秒）
DELAY_MIN = 1.5
DELAY_MAX = 3.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL,
}


def get_page(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [エラー] {url}: {e}")
        return None


def extract_article(soup: BeautifulSoup, url: str) -> dict | None:
    """
    FC2ブログの記事ページから本文・タイトル・日付・タグを抽出する。

    FC2ブログの主なCSSクラス:
      タイトル: .entry-title, .title_entry, h1.entry-title
      日付:     .date, .update_date, time[datetime]
      本文:     .entry-body, #entry_body, .article-content
      タグ:     .tag-list a, .tags a
    """

    # --- タイトル ---
    title = ""
    for sel in [
        ".entry-title a", ".entry-title", ".title_entry",
        "h1.entry-title", ".article-title", "h1.title", "h1",
    ]:
        el = soup.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            break

    # --- 日付 ---
    date = ""
    for sel in ["time[datetime]", ".date", ".update_date", ".entry-date", ".post-date"]:
        el = soup.select_one(sel)
        if el:
            raw = el.get("datetime") or el.get_text(strip=True)
            m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", raw)
            if m:
                date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                break
    # URLからも日付を推測（フォールバック）
    if not date:
        m = re.search(r"/(\d{4})(\d{2})(\d{2})", url)
        if m:
            date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # --- タグ ---
    tags: list[str] = []
    for sel in [".tag-list a", ".tags a", ".category a", ".entry-tag a"]:
        els = soup.select(sel)
        if els:
            tags = [e.get_text(strip=True) for e in els]
            break

    # --- 本文 ---
    body_html = None
    for sel in [
        ".entry-body", "#entry_body", ".article-content",
        ".entry-content", ".post-body", ".content",
    ]:
        el = soup.select_one(sel)
        if el:
            body_html = el
            break

    if not body_html:
        return None

    # 不要な要素を除去
    for tag in body_html.select("script, style, .sns-share, .share-buttons, iframe"):
        tag.decompose()

    body_md = html_to_markdown(body_html)

    if not title and not body_md:
        return None

    return {
        "url": url,
        "title": title,
        "date": date,
        "tags": tags,
        "body": body_md,
    }


def html_to_markdown(el: BeautifulSoup) -> str:
    """HTML要素を簡易Markdown文字列に変換する。"""
    lines = []

    for node in el.descendants:
        if node.name is None:
            # テキストノードはスキップ（親タグで処理）
            continue
        if node.name in ("p", "div"):
            text = node.get_text(strip=True)
            if text and not any(text in l for l in lines):
                lines.append(text)
        elif node.name == "h2":
            text = node.get_text(strip=True)
            if text:
                lines.append(f"## {text}")
        elif node.name == "h3":
            text = node.get_text(strip=True)
            if text:
                lines.append(f"### {text}")
        elif node.name == "h4":
            text = node.get_text(strip=True)
            if text:
                lines.append(f"#### {text}")
        elif node.name == "li":
            text = node.get_text(strip=True)
            if text:
                lines.append(f"- {text}")
        elif node.name == "blockquote":
            text = node.get_text(strip=True)
            if text:
                lines.append(f"> {text}")

    # 重複行・空行の整理
    seen = set()
    deduped = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            deduped.append(line)

    # それでも本文が取れない場合は全テキストをフォールバック
    result = "\n\n".join(deduped).strip()
    if not result:
        result = el.get_text(separator="\n", strip=True)

    return result


def article_to_markdown(article: dict) -> str:
    """記事辞書をYAML front matter付きMarkdownに変換する。"""
    tags_str = "[" + ", ".join(article["tags"]) + "]" if article["tags"] else "[]"
    title_escaped = article["title"].replace('"', '\\"')
    return (
        f'---\n'
        f'title: "{title_escaped}"\n'
        f'date: {article["date"]}\n'
        f'tags: {tags_str}\n'
        f'source_url: {article["url"]}\n'
        f'---\n\n'
        f'{article["body"]}\n'
    )


def make_filename(article: dict, index: int) -> str:
    date = article["date"] or "0000-00-00"
    title = article["title"]
    slug = re.sub(r'[\s/\\:*?"<>|]', "-", title)
    slug = re.sub(r"-+", "-", slug).strip("-")[:40]
    return f"{date}_{index:04d}_{slug}.md"


# ----------------------------------------------------------------
# URL収集
# ----------------------------------------------------------------

def collect_all_article_urls(session: requests.Session) -> list[str]:
    """
    FC2ブログの全記事URLを収集する。
    戦略:
      1. トップページ → 月別アーカイブリンクを取得
      2. 各月のページを辿って記事URLを収集
      3. ページネーション（?page=N または &page=N）も処理
    """
    urls: set[str] = set()

    print(f"トップページを取得中: {BASE_URL}/")
    soup = get_page(BASE_URL + "/", session)
    if not soup:
        print("トップページの取得に失敗しました。")
        return []

    # トップページの記事URLを収集
    _collect_article_links_from_soup(soup, urls)

    # 月別アーカイブリンクを収集
    archive_urls = _find_archive_links(soup)
    print(f"月別アーカイブ: {len(archive_urls)} 件発見")

    if archive_urls:
        for arch_url in sorted(archive_urls, reverse=True):
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            print(f"  アーカイブ取得: {arch_url}")
            arch_soup = get_page(arch_url, session)
            if arch_soup:
                _collect_article_links_from_soup(arch_soup, urls)
                # ページネーションを処理
                _follow_archive_pages(arch_url, arch_soup, urls, session)
    else:
        # 月別アーカイブがない場合はトップからページネーションを辿る
        print("月別アーカイブが見つかりません。ページネーション方式で収集します。")
        _follow_archive_pages(BASE_URL, soup, urls, session)

    return sorted(urls)


def _find_archive_links(soup: BeautifulSoup) -> list[str]:
    """サイドバー等にある月別アーカイブリンクを収集する。"""
    result = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        full = href if href.startswith("http") else BASE_URL + href
        # FC2の月別アーカイブURL例: https://newhabits.blog.fc2.com/blog-date-202401.html
        if re.search(r"blog-date-\d{6}\.html", full):
            result.add(full)
        # カテゴリページ
        if re.search(r"blog-category-\d+\.html", full):
            result.add(full)
    return list(result)


def _collect_article_links_from_soup(soup: BeautifulSoup, urls: set):
    """ページ内の個別記事リンク（blog-entry-XXXX.html）を収集する。"""
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        full = href if href.startswith("http") else BASE_URL + href
        if re.search(r"blog-entry-\d+\.html", full):
            # クエリ文字列を除去してクリーンなURLに
            clean = full.split("?")[0]
            urls.add(clean)


def _follow_archive_pages(
    base_url: str,
    soup: BeautifulSoup,
    urls: set,
    session: requests.Session,
):
    """「次のページ」リンクを辿って全記事URLを収集する。"""
    visited = {base_url}
    current_soup = soup
    page = 1

    while True:
        next_url = _find_next_page(current_soup, visited)
        if not next_url:
            break

        visited.add(next_url)
        page += 1
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        print(f"    ページ {page}: {next_url}")

        next_soup = get_page(next_url, session)
        if not next_soup:
            break

        before = len(urls)
        _collect_article_links_from_soup(next_soup, urls)
        added = len(urls) - before
        print(f"    記事URL +{added} 件 (累計: {len(urls)} 件)")

        current_soup = next_soup


def _find_next_page(soup: BeautifulSoup, visited: set) -> str | None:
    """「次のページ」リンクを返す。"""
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        full = href if href.startswith("http") else BASE_URL + href

        is_next = any(kw in text for kw in ["次", "older", "NEXT", "next", "≫", ">>", "前の記事"])
        if is_next and full not in visited and BASE_URL in full:
            return full

    # FC2のページネーションクラスも確認
    for a in soup.select(".paging a, .pagination a, .page-nav a"):
        href = a.get("href", "")
        full = href if href.startswith("http") else BASE_URL + href
        if full not in visited and BASE_URL in full:
            return full

    return None


# ----------------------------------------------------------------
# メイン処理
# ----------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 60)
    print("FC2ブログ記事スクレイパー")
    print(f"対象: {BASE_URL}")
    print(f"出力先: {OUTPUT_DIR.resolve()}")
    print("=" * 60)
    print()

    # 既存ファイルのURLを確認（再実行時にスキップ）
    existing_urls: set[str] = set()
    for f in OUTPUT_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"source_url: (.+)", text)
        if m:
            existing_urls.add(m.group(1).strip())
    if existing_urls:
        print(f"既存のダウンロード済み記事: {len(existing_urls)} 件 (スキップします)")
        print()

    # 記事URLを収集
    article_urls = collect_all_article_urls(session)
    new_urls = [u for u in article_urls if u not in existing_urls]

    print(f"\n収集した記事URL: {len(article_urls)} 件")
    print(f"未取得: {len(new_urls)} 件\n")

    if not new_urls:
        print("すべての記事は取得済みです。")
        return

    # 各記事を取得・保存
    saved = 0
    failed = 0
    start_index = len(existing_urls) + 1

    for i, url in enumerate(new_urls, start_index):
        print(f"[{i}/{len(article_urls)}] {url}")
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        soup = get_page(url, session)
        if not soup:
            failed += 1
            continue

        article = extract_article(soup, url)
        if not article:
            print(f"  [スキップ] 記事本文を取得できませんでした")
            failed += 1
            continue

        md = article_to_markdown(article)
        filename = make_filename(article, i)
        out_path = OUTPUT_DIR / filename
        out_path.write_text(md, encoding="utf-8")
        print(f"  保存: {filename[:60]}")
        saved += 1

        # 50件ごとに少し長めに待機
        if saved % 50 == 0:
            wait = random.uniform(5, 10)
            print(f"\n--- {saved} 件保存済み。{wait:.0f}秒待機... ---\n")
            time.sleep(wait)

    print(f"\n{'=' * 60}")
    print(f"完了!  保存: {saved} 件 / 失敗: {failed} 件")
    print(f"出力先: {OUTPUT_DIR.resolve()}")
    print()
    print("次のステップ:")
    print("  1. このリポジトリのルートに移動")
    print("  2. python main.py index    ← インデックス構築")
    print("  3. python main.py suggest  ← テーマ提案")
    print("  4. python main.py generate 'テーマ'  ← 記事生成")


if __name__ == "__main__":
    main()
