"""颜色、字体与小尺寸规范。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

FONT_NAME = "JianKeSans"


def rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    color = get_color_from_hex(hex_color)
    return (color[0], color[1], color[2], float(alpha))


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    surface: str
    surface_alt: str
    ink: str
    muted: str
    faint: str
    line: str
    accent: str
    accent_ink: str
    accent_soft: str
    hero: str
    hero_ink: str
    hero_muted: str
    danger: str
    danger_soft: str
    chip: str
    overlay: str
    nav: str
    now_line: str
    is_dark: bool = False

    def c(self, key: str, alpha: float = 1.0):
        return rgba(getattr(self, key), alpha)

    def course(self, index: int) -> tuple[str, str]:
        item = COURSE_COLORS[index % len(COURSE_COLORS)]
        return item["dark"] if self.is_dark else item["light"]


LIGHT = Palette(
    name="light",
    bg="#F4F2EC",
    surface="#FFFFFF",
    surface_alt="#EFEEE7",
    ink="#19231C",
    muted="#707B73",
    faint="#A0A9A2",
    line="#E5E2D8",
    accent="#2B5C45",
    accent_ink="#FFFFFF",
    accent_soft="#E1ECE5",
    hero="#224634",
    hero_ink="#F7F4E9",
    hero_muted="#BDD0C3",
    danger="#B24F3B",
    danger_soft="#F7E7E1",
    chip="#F1EFE8",
    overlay="#172019CC",
    nav="#FBFAF6",
    now_line="#D97858",
)

DARK = Palette(
    name="dark",
    bg="#101713",
    surface="#18221C",
    surface_alt="#202B24",
    ink="#EEF0E8",
    muted="#AAB6AD",
    faint="#829087",
    line="#2A382F",
    accent="#9BCFAF",
    accent_ink="#0E1D15",
    accent_soft="#23382C",
    hero="#274435",
    hero_ink="#F7F4E9",
    hero_muted="#B7CCBD",
    danger="#F0A08D",
    danger_soft="#3D2A24",
    chip="#222E27",
    overlay="#000000B8",
    nav="#141D18",
    now_line="#E39A7E",
    is_dark=True,
)

COURSE_COLORS = (
    {"name": "鼠尾草", "light": ("#DDEADF", "#23513A"), "dark": ("#294337", "#D6EBDD")},
    {"name": "陶土", "light": ("#F1DFD6", "#6A3D2D"), "dark": ("#4A342B", "#F0D6CA")},
    {"name": "燕麦", "light": ("#F0E6CC", "#5B4B26"), "dark": ("#443C27", "#EDE0C1")},
    {"name": "雾蓝", "light": ("#DCE7F0", "#2C4D64"), "dark": ("#2A3D49", "#D7E8F4")},
    {"name": "丁香", "light": ("#E5E0F0", "#473B60"), "dark": ("#383248", "#E4DBF3")},
    {"name": "玫瑰", "light": ("#F1DEE2", "#673B46"), "dark": ("#493038", "#F2D8DF")},
    {"name": "苔绿", "light": ("#E5E8D5", "#4B5128"), "dark": ("#3B4129", "#E2E7C8")},
    {"name": "石板", "light": ("#E2E6E3", "#3D4B44"), "dark": ("#333F39", "#DDE5DF")},
)


def palette_for(theme: str) -> Palette:
    return DARK if theme == "dark" else LIGHT


def register_font() -> None:
    from kivy.core.text import LabelBase

    font_path = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansSC-Regular.ttf"
    if font_path.exists():
        LabelBase.register(name=FONT_NAME, fn_regular=str(font_path), fn_bold=str(font_path))
    else:
        # 开发环境找不到字体时退回系统字体，至少能启动；正式 APK 会带上字体。
        LabelBase.register(name=FONT_NAME, fn_regular="Roboto")


# 常用尺寸（dp）
PAGE_PAD = dp(20)
CARD_RADIUS = 18
HERO_RADIUS = 24
NAV_HEIGHT = dp(64)
TOP_PAD = dp(14)


def fs(size: float) -> float:
    """字号统一用 sp，方便系统字体缩放。"""
    return sp(size)
