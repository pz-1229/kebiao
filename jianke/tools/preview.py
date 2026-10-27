"""本地预览 / 自动截图脚本（仅开发用）。

用法：
    python tools/preview.py --screen today --out previews/today.png
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from datetime import date
from pathlib import Path

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT.parent / ".deps"
KIVY_HOME = ROOT.parent / ".kivyhome"
PREVIEW_DATA = Path(os.environ.get("JIANKE_PREVIEW_DIR", ROOT.parent / ".preview-data"))

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "warning")
os.environ["KIVY_HOME"] = str(KIVY_HOME)
os.environ["JIANKE_DATA_DIR"] = str(PREVIEW_DATA)

if sys.platform == "win32":
    for folder in (
        DEPS / "kivy_deps.sdl2-0.8.0.data" / "data" / "share" / "sdl2" / "bin",
        DEPS / "kivy_deps_glew-0.3.2.data" / "data" / "share" / "glew" / "bin",
        DEPS / "kivy_deps_angle-0.5.0.data" / "data" / "share" / "angle" / "bin",
    ):
        if folder.exists():
            os.add_dll_directory(str(folder))
    os.environ["PATH"] = os.pathsep.join(
        [
            str(DEPS / "kivy_deps.sdl2-0.8.0.data" / "data" / "share" / "sdl2" / "bin"),
            str(DEPS / "kivy_deps_glew-0.3.2.data" / "data" / "share" / "glew" / "bin"),
            str(DEPS / "kivy_deps_angle-0.5.0.data" / "data" / "share" / "angle" / "bin"),
            os.environ.get("PATH", ""),
        ]
    )

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(DEPS))

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "390")
Config.set("graphics", "height", "844")
Config.set("graphics", "resizable", "0")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402

from jianke_app.app import JianKeApp  # noqa: E402
from jianke_app.core import demo_data  # noqa: E402
from jianke_app.storage import Storage  # noqa: E402


def ensure_demo_data():
    PREVIEW_DATA.mkdir(parents=True, exist_ok=True)
    path = PREVIEW_DATA / "jianke-data.json"
    if not path.exists():
        Storage(path).save(demo_data(date.today()))


def _capture_gl(out: Path):
    """直接从 OpenGL 帧缓冲截图。

    Kivy 2.3.1 的 Window.screenshot 在宽度不是 4 的倍数时没设置
    GL_PACK_ALIGNMENT=1，RGB 行会错位成斜条纹；这里自己读并翻转。
    """
    from PIL import Image
    from kivy.graphics.opengl import (
        GL_PACK_ALIGNMENT,
        GL_RGB,
        GL_UNSIGNED_BYTE,
        glFinish,
        glPixelStorei,
        glReadPixels,
    )

    glFinish()
    width, height = int(Window.size[0]), int(Window.size[1])
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    data = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
    glPixelStorei(GL_PACK_ALIGNMENT, 4)
    image = Image.frombytes("RGB", (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    image.save(out)


def _capture_desktop_window(title: str, out: Path):
    """Kivy 的 Window.screenshot 在部分 Windows/GL 驱动上会读错行宽，
    改用系统合成后的窗口截图，保证预览图与真机布局一致。"""
    from ctypes import wintypes

    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        raise RuntimeError(f"找不到窗口：{title}")
    if os.environ.get("JIANKE_MOVE_WINDOW"):
        user32.SetWindowPos(hwnd, 0, 80, 80, 0, 0, 0x0001 | 0x0004)
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    image = ImageGrab.grab(
        bbox=(point.x, point.y, point.x + rect.right, point.y + rect.bottom),
        all_screens=True,
    )
    image.save(out)
    if os.environ.get("JIANKE_CAPTURE_CONTEXT"):
        context = ImageGrab.grab(
            bbox=(point.x - 160, point.y - 100, point.x + rect.right + 160, point.y + rect.bottom + 100),
            all_screens=True,
        )
        context.save(out.with_name(out.stem + "_context.png"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen", default="today", choices=["today", "week", "settings", "detail", "editor", "backup", "periods"])
    parser.add_argument("--out", default=str(ROOT / "previews" / "app.png"))
    parser.add_argument("--theme", default="", choices=["", "light", "dark"])
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--no-demo", action="store_true")
    args = parser.parse_args()
    if not args.no_demo:
        ensure_demo_data()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    app = JianKeApp()

    def boot(_dt):
        try:
            if args.theme and app.data.theme != args.theme:
                app.data.theme = args.theme
                app.apply_theme()
            if args.screen == "today":
                app.show_tab(0)
            elif args.screen == "week":
                app.show_tab(1)
            elif args.screen == "settings":
                app.show_tab(2)
            elif args.screen == "detail":
                app.open_detail(app.data.courses[0])
            elif args.screen == "editor":
                app.open_editor(app.data.courses[0], origin="week")
            elif args.screen == "backup":
                app.show_tab(2)
                app.open_backup()
            elif args.screen == "periods":
                app.show_tab(2)
                app.open_periods()
            Clock.schedule_once(capture, args.delay)
        except Exception as exc:
            import traceback

            traceback.print_exc()
            app.stop()

    def capture(_dt):
        try:
            _capture_gl(out)
            print("SCREENSHOT", out)
        except Exception:
            import traceback

            traceback.print_exc()
        Clock.schedule_once(lambda *_: app.stop(), 0.4)

    Clock.schedule_once(boot, 0.7)
    app.run()


if __name__ == "__main__":
    main()
