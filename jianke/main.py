"""简课：一个没有广告的本地课程表。

运行：
    python main.py

安卓打包见 README.md / buildozer.spec。
"""

from __future__ import annotations

import os
import sys


def _configure_desktop_window():
    """桌面端用手机尺寸预览；安卓上由系统决定窗口大小。"""
    if sys.platform.startswith("win") or sys.platform == "darwin":
        try:
            from kivy.config import Config

            Config.set("graphics", "width", "390")
            Config.set("graphics", "height", "844")
            Config.set("graphics", "resizable", "1")
        except Exception:
            pass


def main():
    _configure_desktop_window()
    from jianke_app.app import JianKeApp

    JianKeApp().run()


if __name__ == "__main__":
    main()
