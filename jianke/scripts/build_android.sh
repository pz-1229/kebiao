#!/usr/bin/env bash
# 在 Linux / WSL2(Windows) 里构建 Android 调试 APK。
# 首次构建会下载 Android SDK/NDK，通常需要 30–60 分钟。
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
  echo "需要 python3，请先安装（Ubuntu: sudo apt install python3 python3-pip）。" >&2
  exit 1
fi

if ! command -v buildozer >/dev/null 2>&1; then
  echo "未找到 buildozer，正在安装到用户目录……"
  python3 -m pip install --user --upgrade buildozer
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v java >/dev/null 2>&1; then
  echo "未找到 Java。Ubuntu/WSL 请先运行：" >&2
  echo "  sudo apt update && sudo apt install -y openjdk-17-jdk" >&2
  exit 1
fi

echo "开始构建 debug APK……"
buildozer android debug
echo
echo "完成。APK 通常在：$(pwd)/bin/"
ls -lh bin/*.apk 2>/dev/null || true
