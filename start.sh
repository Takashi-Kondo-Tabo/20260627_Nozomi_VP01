#!/bin/bash
# ブログ記事生成システム 起動スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# .env からAPIキーを読み込む
if [ -f ".env" ]; then
    API_KEY=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d'=' -f2- | tr -d '\r\n')
    if [ -n "$API_KEY" ]; then
        export ANTHROPIC_API_KEY="$API_KEY"
    fi
fi

# APIキーの確認
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "エラー: ANTHROPIC_API_KEY が設定されていません。"
    echo ".env ファイルにAPIキーを記載してください。"
    exit 1
fi

# Python の確認
PYTHON=""
for cmd in /Library/Developer/CommandLineTools/usr/bin/python3 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "エラー: Python が見つかりません。"
    exit 1
fi

echo "==============================="
echo "  ブログ記事生成システム"
echo "==============================="
echo ""

$PYTHON main.py interactive
