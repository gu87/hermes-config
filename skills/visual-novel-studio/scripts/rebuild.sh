#!/bin/bash
# VNS 一键重建：validate → compress → assemble → accept_test
# 用法: cd game-dir/ && bash rebuild.sh [image-dir]
# 默认 img-dir: compressed/
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VNS_SCRIPTS="/Users/gu/.hermes/scripts/vns"
GAME_DIR="$(pwd)"
IMG_DIR="${1:-compressed}"
TITLE="${2:-沉浸剧本}"
OUT="${3:-dist/index.html}"

echo "═══════════════════════════════════"
echo " VNS 一键重建"
echo " Game: $(basename "$GAME_DIR")"
echo "═══════════════════════════════════"

# Step 1: Quality Gate A
echo ""
echo "🅰 Gate A — 数据格式校验"
echo "─────────────────────"
if [ -f script_flat.json ]; then
    python3 "$VNS_SCRIPTS/validate_script.py" script_flat.json --img-dir "$IMG_DIR" || {
        echo "❌ Gate A 失败！修复后重试。"
        exit 1
    }
else
    echo "⚠️  未找到 script_flat.json，跳过 Gate A"
fi

# Step 2: Compress new images
echo ""
echo "📦 压缩新图片"
echo "─────────────────────"
if [ -d raw ]; then
    shopt -s nullglob
    for f in raw/*.png raw/*.jpg raw/*.jpeg; do
        [ -f "$f" ] || continue
        name="$(basename "$f")"
        base="${name%.*}"
        if [ -f "$IMG_DIR/$base.webp" ] || [ -f "$IMG_DIR/$base.jpg" ]; then
            echo "  [skip] $base"
            continue
        fi
        case "$base" in
            bg*)   TYPE="bg" ;;
            hero*) TYPE="hero" ;;
            panel*) TYPE="panel" ;;
            *)     TYPE="bg" ;;
        esac
        echo "  [compress] $base ($TYPE)"
        python3 "$VNS_SCRIPTS/compress.py" "$f" --type "$TYPE" --out "$IMG_DIR/$base.webp"
    done
    shopt -u nullglob
else
    echo "  ⚠️  未找到 raw/ 目录"
fi

# Step 3: Build
echo ""
echo "🏗️  构建 HTML"
echo "─────────────────────"
python3 "$VNS_SCRIPTS/assemble.py" \
    --script script_flat.json \
    --img-dir "$IMG_DIR" \
    --title "$TITLE" \
    --out "$OUT"

# Step 4: Quality Gate B
echo ""
echo "🅱 Gate B — 自动验收测试"
echo "─────────────────────"
python3 "$VNS_SCRIPTS/accept_test.py" "$OUT" || {
    echo "❌ Gate B 失败！检查输出后重试。"
    exit 1
}

echo ""
echo "═══════════════════════════════════"
echo " ✅ 全部通过！交付: $OUT"
echo "═══════════════════════════════════"
