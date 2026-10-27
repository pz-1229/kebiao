"""简课的界面组件：卡片、按钮、图标、输入框和弹窗。

全部用 Kivy 的 Canvas 绘制，不依赖图片素材，因此在安卓上清晰且体积小。
"""

from __future__ import annotations

from typing import Callable

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from .theme import CARD_RADIUS, FONT_NAME, Palette, fs, rgba


def _as_color(value, alpha: float | None = None) -> tuple[float, float, float, float]:
    if isinstance(value, str):
        return rgba(value, 1.0 if alpha is None else alpha)
    if len(value) == 3:
        return (value[0], value[1], value[2], 1.0 if alpha is None else alpha)
    if alpha is None:
        return tuple(value)
    return (value[0], value[1], value[2], alpha)


def measure_text(text: str, size: float = 14, bold: bool = False) -> tuple[float, float]:
    """量出一行文字的实际像素尺寸，用于胶囊、Toast 这类自适应宽度的控件。"""
    label = CoreLabel(text=text, font_name=FONT_NAME, font_size=fs(size), bold=bold)
    label.refresh()
    return label.texture.size


class Txt(Label):
    """统一字体与颜色的文本。"""

    def __init__(
        self,
        text: str = "",
        *,
        size: float = 14,
        color="#19231C",
        bold: bool = False,
        halign: str = "left",
        valign: str = "middle",
        wrap: bool = False,
        line_height: float = 1.2,
        widget_size=None,
        **kwargs,
    ):
        kwargs.setdefault("font_name", FONT_NAME)
        kwargs.setdefault("font_size", fs(size))
        kwargs.setdefault("bold", bold)
        kwargs.setdefault("halign", halign)
        kwargs.setdefault("valign", valign)
        kwargs.setdefault("color", _as_color(color))
        kwargs.setdefault("line_height", line_height)
        kwargs.setdefault("markup", False)
        if widget_size is not None:
            kwargs.setdefault("size", widget_size)
        super().__init__(text=text, **kwargs)
        self._wrap = wrap
        # 只有给 Label 一个明确的 text_size，halign / valign 才会生效，
        # 否则 Kivy 会把文字纹理居中放在控件里，看起来像排版错位。
        self.bind(size=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *_):
        self.text_size = (max(1.0, self.width), max(1.0, self.height))


class Card(BoxLayout):
    """带圆角和细边框的容器。"""

    bg_color = ListProperty([1, 1, 1, 1])
    border_color = ListProperty([0, 0, 0, 0])
    radius = NumericProperty(CARD_RADIUS)

    def __init__(self, *, bg_color=(1, 1, 1, 1), border_color=(0, 0, 0, 0), radius=None, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = _as_color(bg_color)
        self.border_color = _as_color(border_color)
        if radius is not None:
            self.radius = radius
        self.bind(pos=self._redraw, size=self._redraw, bg_color=self._redraw, border_color=self._redraw, radius=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.radius)])
            if self.border_color[3] > 0:
                Color(*self.border_color)
                Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, dp(self.radius)),
                    width=1,
                )

    def set_colors(self, bg=None, border=None):
        if bg is not None:
            self.bg_color = _as_color(bg)
        if border is not None:
            self.border_color = _as_color(border)
        self._redraw()


class TapCard(ButtonBehavior, Card):
    """可以整块点击的卡片。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(state=self._state_changed)

    def _state_changed(self, *_):
        self.opacity = 0.82 if self.state == "down" else 1.0


class Pill(Card):
    """小胶囊标签。"""

    def __init__(self, text="", *, palette: Palette, fg=None, bg=None, font_size=11, **kwargs):
        super().__init__(
            size_hint=(None, None),
            height=dp(28),
            padding=(dp(11), 0),
            bg_color=bg or palette.accent_soft,
            border_color=(0, 0, 0, 0),
            radius=14,
            **kwargs,
        )
        label = Txt(text, size=font_size, bold=True, color=fg or palette.accent, halign="center")
        self.add_widget(label)
        text_width, _ = measure_text(text, font_size, True)
        self.width = max(dp(74), text_width + dp(26))


class Icon(Widget):
    """用线稿画的小图标。"""

    kind = StringProperty("grid")
    color = ListProperty([0, 0, 0, 1])
    line_width = NumericProperty(dp(1.8))

    def __init__(self, kind="grid", color="#19231C", **kwargs):
        super().__init__(**kwargs)
        self.kind = kind
        self.color = _as_color(color)
        self.bind(pos=self._redraw, size=self._redraw, kind=self._redraw, color=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 2 or h < 2:
            return
        c = self.color
        lw = self.line_width
        x, y = self.pos
        cx, cy = x + w / 2, y + h / 2
        pad = min(w, h) * 0.18
        # 所有坐标都在控件内部留一点边距。
        left, right = x + pad, x + w - pad
        bottom, top = y + pad, y + h - pad
        with self.canvas:
            Color(*c)
            if self.kind == "plus":
                Line(points=[left, cy, right, cy], width=lw, cap="round")
                Line(points=[cx, bottom, cx, top], width=lw, cap="round")
            elif self.kind == "minus":
                Line(points=[left, cy, right, cy], width=lw, cap="round")
            elif self.kind == "back":
                Line(points=[right, cy, left, cy], width=lw, cap="round")
                Line(points=[left, cy, x + w * 0.43, y + h * 0.72], width=lw, cap="round")
                Line(points=[left, cy, x + w * 0.43, y + h * 0.28], width=lw, cap="round")
            elif self.kind == "right":
                Line(points=[left, cy, right, cy], width=lw, cap="round")
                Line(points=[right, cy, x + w * 0.57, y + h * 0.72], width=lw, cap="round")
                Line(points=[right, cy, x + w * 0.57, y + h * 0.28], width=lw, cap="round")
            elif self.kind == "left":
                Line(points=[right, cy, left, cy], width=lw, cap="round")
                Line(points=[left, cy, x + w * 0.43, y + h * 0.72], width=lw, cap="round")
                Line(points=[left, cy, x + w * 0.43, y + h * 0.28], width=lw, cap="round")
            elif self.kind == "grid":
                Line(rounded_rectangle=(left, bottom, right - left, top - bottom, dp(3)), width=lw)
                Line(points=[left, cy, right, cy], width=lw)
                Line(points=[cx, bottom, cx, top], width=lw)
            elif self.kind == "sun":
                Color(*c)
                r = min(w, h) * 0.18
                Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)):
                    Line(
                        points=[
                            cx + dx * min(w, h) * 0.32,
                            cy + dy * min(w, h) * 0.32,
                            cx + dx * min(w, h) * 0.43,
                            cy + dy * min(w, h) * 0.43,
                        ],
                        width=lw * 0.8,
                        cap="round",
                    )
            elif self.kind == "sliders":
                for fy, knob_x in ((0.7, 0.35), (0.5, 0.62), (0.3, 0.42)):
                    yy = y + h * fy
                    Line(points=[left, yy, right, yy], width=lw, cap="round")
                    Ellipse(pos=(x + w * knob_x - dp(2), yy - dp(2)), size=(dp(4), dp(4)))
            elif self.kind == "check":
                Line(points=[left, cy, cx - w * 0.03, bottom, right, top], width=lw + dp(0.4), cap="round", joint="round")
            elif self.kind == "close":
                Line(points=[left, bottom, right, top], width=lw, cap="round")
                Line(points=[left, top, right, bottom], width=lw, cap="round")
            elif self.kind == "clock":
                Line(circle=(cx, cy, min(w, h) * 0.34), width=lw)
                Line(points=[cx, cy, cx, cy + min(w, h) * 0.19], width=lw, cap="round")
                Line(points=[cx, cy, cx + min(w, h) * 0.17, cy], width=lw, cap="round")
            elif self.kind == "pin":
                Line(circle=(cx, cy + min(w, h) * 0.09, min(w, h) * 0.2), width=lw)
                Line(points=[cx - min(w, h) * 0.18, cy, cx, bottom, cx + min(w, h) * 0.18, cy], width=lw)
            elif self.kind == "user":
                Line(circle=(cx, cy + h * 0.12, min(w, h) * 0.16), width=lw)
                Line(points=[cx - w * 0.23, bottom, cx - w * 0.15, cy - h * 0.02, cx + w * 0.15, cy - h * 0.02, cx + w * 0.23, bottom], width=lw, joint="round")
            elif self.kind == "note":
                Line(rounded_rectangle=(left, bottom, right - left, top - bottom, dp(2)), width=lw)
                Line(points=[left + w * 0.12, y + h * 0.62, right - w * 0.12, y + h * 0.62], width=lw)
                Line(points=[left + w * 0.12, y + h * 0.42, right - w * 0.24, y + h * 0.42], width=lw)
            elif self.kind == "more":
                for dx in (-0.24, 0, 0.24):
                    Ellipse(pos=(cx + w * dx - dp(1.6), cy - dp(1.6)), size=(dp(3.2), dp(3.2)))
            elif self.kind == "chevron_down":
                Line(points=[left, cy + h * 0.1, cx, cy - h * 0.12, right, cy + h * 0.1], width=lw, cap="round", joint="round")
            elif self.kind == "chevron_up":
                Line(points=[left, cy - h * 0.1, cx, cy + h * 0.12, right, cy - h * 0.1], width=lw, cap="round", joint="round")
            elif self.kind == "calendar":
                Line(rounded_rectangle=(left, bottom, right - left, top - bottom, dp(2)), width=lw)
                Line(points=[left, y + h * 0.63, right, y + h * 0.63], width=lw)
                Line(points=[x + w * 0.3, top, x + w * 0.3, y + h * 0.78], width=lw, cap="round")
                Line(points=[x + w * 0.7, top, x + w * 0.7, y + h * 0.78], width=lw, cap="round")
            elif self.kind == "leaf":
                Line(points=[left, bottom + h * 0.2, cx, top, right, cy], width=lw, joint="round")
                Line(points=[cx, top, cx, cy], width=lw)


class IconButton(ButtonBehavior, Widget):
    def __init__(self, kind="plus", color="#19231C", size=dp(40), icon_size=dp(21), **kwargs):
        super().__init__(size_hint=(None, None), size=(size, size), **kwargs)
        self.icon = Icon(kind=kind, color=color, size_hint=(None, None), size=(icon_size, icon_size))
        self.add_widget(self.icon)
        self.bind(pos=self._layout_icon, size=self._layout_icon)
        self.bind(state=self._state_changed)
        self._layout_icon()

    def _layout_icon(self, *_):
        self.icon.center = self.center

    def _state_changed(self, *_):
        self.opacity = 0.55 if self.state == "down" else 1.0


class LinkButton(ButtonBehavior, Label):
    """没有底色的文字按钮。"""

    def __init__(self, text="", *, color="#2B5C45", size=13, bold=True, **kwargs):
        kwargs.setdefault("font_name", FONT_NAME)
        kwargs.setdefault("font_size", fs(size))
        kwargs.setdefault("bold", bold)
        kwargs.setdefault("color", _as_color(color))
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(text=text, **kwargs)
        self.text_size = (None, None)
        self.bind(texture_size=self._resize, state=self._state_changed)
        self._resize()

    def _resize(self, *_):
        self.width = max(dp(36), self.texture_size[0] + dp(20))
        self.height = max(dp(36), self.texture_size[1] + dp(8))

    def _state_changed(self, *_):
        self.opacity = 0.55 if self.state == "down" else 1.0


class JkButton(ButtonBehavior, BoxLayout):
    """主按钮 / 次按钮 / 危险按钮。"""

    def __init__(
        self,
        text="",
        *,
        palette: Palette,
        kind="primary",
        height=dp(50),
        font_size=15,
        icon=None,
        on_release: Callable | None = None,
        **kwargs,
    ):
        super().__init__(size_hint_y=None, height=height, orientation="horizontal", spacing=dp(8), **kwargs)
        self.palette = palette
        self.kind = kind
        self._label = Txt(text, size=font_size, bold=True, halign="center", color=self._text_color())
        self.add_widget(self._label)
        if icon:
            self._icon = Icon(kind=icon, color=self._text_color(), size_hint=(None, None), size=(dp(17), dp(17)))
            self.add_widget(self._icon)
            self.bind(pos=self._layout_icon, size=self._layout_icon)
        else:
            self._icon = None
        if on_release:
            self.bind(on_release=lambda *_: on_release())
        self.bind(state=self._state_changed, pos=self._redraw, size=self._redraw)
        self._redraw()

    def _text_color(self):
        p = self.palette
        if self.kind == "primary":
            return p.accent_ink
        if self.kind == "danger":
            return p.danger
        if self.kind == "soft":
            return p.accent
        return p.ink

    def _fill(self):
        p = self.palette
        if self.kind == "primary":
            return p.accent
        if self.kind == "soft":
            return p.accent_soft
        if self.kind == "danger":
            return p.danger_soft
        return p.surface

    def _border(self):
        p = self.palette
        if self.kind in ("ghost", "danger"):
            return p.line
        return self._fill()

    def _layout_icon(self, *_):
        if self._icon:
            self._icon.center = (self.x + dp(22), self.center_y)

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*_as_color(self._fill()))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            if self.kind in ("ghost", "danger"):
                Color(*_as_color(self._border()))
                Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(14)), width=1)

    def _state_changed(self, *_):
        self.opacity = 0.72 if self.state == "down" else 1.0


class Chip(ButtonBehavior, Label):
    """可点选的胶囊标签。"""

    selected = BooleanProperty(False)

    def __init__(
        self,
        text="",
        *,
        palette: Palette,
        selected=False,
        font_size=13,
        height=dp(38),
        on_release: Callable | None = None,
        **kwargs,
    ):
        kwargs.setdefault("font_name", FONT_NAME)
        kwargs.setdefault("font_size", fs(font_size))
        kwargs.setdefault("bold", False)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", height)
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(text=text, **kwargs)
        self.palette = palette
        self.selected = selected
        self.text_size = (None, None)
        self.bind(pos=self._redraw, size=self._redraw, selected=self._redraw, state=self._state_changed)
        if on_release:
            self.bind(on_release=lambda *_: on_release())
        self._redraw()

    def _redraw(self, *_):
        p = self.palette
        bg = p.accent if self.selected else p.chip
        fg = p.accent_ink if self.selected else p.muted
        self.color = _as_color(fg)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*_as_color(bg))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.height / 2])
            if not self.selected:
                Color(*_as_color(p.line))
                Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.height / 2), width=1)

    def _state_changed(self, *_):
        self.opacity = 0.7 if self.state == "down" else 1.0


class InputField(BoxLayout):
    """带标题和圆角外框的输入框。"""

    def __init__(
        self,
        label: str,
        *,
        palette: Palette,
        hint: str = "",
        text: str = "",
        multiline: bool = False,
        field_height=None,
        helper: str = "",
        input_filter=None,
        **kwargs,
    ):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(6), **kwargs)
        self.palette = palette
        self._label_height = dp(18)
        self._helper_height = dp(17) if helper else 0
        field_height = field_height or (dp(96) if multiline else dp(48))
        self.height = self._label_height + dp(6) + field_height + (dp(4) + self._helper_height if helper else 0)
        self.title = Txt(label, size=11.5, color=palette.muted, bold=True, size_hint_y=None, height=self._label_height)
        self.add_widget(self.title)
        self.shell = BoxLayout(size_hint_y=None, height=field_height, padding=(dp(12), dp(8) if not multiline else dp(8)), spacing=0)
        self.add_widget(self.shell)
        self.input = TextInput(
            text=text,
            hint_text=hint,
            multiline=multiline,
            font_name=FONT_NAME,
            font_size=fs(15),
            foreground_color=_as_color(palette.ink),
            hint_text_color=_as_color(palette.faint),
            cursor_color=_as_color(palette.accent),
            cursor_width=dp(1.5),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            border=(0, 0, 0, 0),
            padding=(dp(0), dp(2), dp(0), dp(2)),
            write_tab=False,
            input_filter=input_filter,
        )
        self.shell.add_widget(self.input)
        self.helper = None
        if helper:
            self.helper = Txt(helper, size=10.5, color=palette.faint, size_hint_y=None, height=self._helper_height)
            self.add_widget(self.helper)
        self._error = False
        self.input.bind(focus=self._focus_changed)
        self.shell.bind(pos=self._redraw, size=self._redraw)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    @property
    def text(self) -> str:
        return self.input.text

    @text.setter
    def text(self, value: str) -> None:
        self.input.text = value or ""

    def _focus_changed(self, *_):
        self._redraw()

    def set_error(self, error: bool):
        self._error = bool(error)
        self._redraw()

    def _redraw(self, *_):
        p = self.palette
        self.shell.canvas.before.clear()
        focused = self.input.focus
        bg = p.surface if focused else p.chip
        border = p.danger if self._error else (p.accent if focused else p.line)
        with self.shell.canvas.before:
            Color(*_as_color(bg))
            RoundedRectangle(pos=self.shell.pos, size=self.shell.size, radius=[dp(13)])
            Color(*_as_color(border))
            Line(rounded_rectangle=(self.shell.x, self.shell.y, self.shell.width, self.shell.height, dp(13)), width=1)

    def on_touch_down(self, touch):
        # 点标题区域也把焦点给输入框，点按面积更大。
        if self.collide_point(*touch.pos) and not self.input.collide_point(*touch.pos):
            self.input.focus = True
            return True
        return super().on_touch_down(touch)


class NumberStepper(BoxLayout):
    def __init__(
        self,
        label: str,
        *,
        palette: Palette,
        value: int,
        minimum: int,
        maximum: int,
        formatter: Callable[[int], str] | None = None,
        on_change: Callable[[int], None] | None = None,
        **kwargs,
    ):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(78), spacing=dp(5), **kwargs)
        self.palette = palette
        self._value = value
        self.minimum, self.maximum = minimum, maximum
        self.formatter = formatter or (lambda v: str(v))
        self.on_change = on_change
        self.title = Txt(label, size=11.5, color=palette.muted, bold=True, size_hint_y=None, height=dp(17))
        self.add_widget(self.title)
        self.shell = Card(
            orientation="horizontal",
            bg_color=palette.chip,
            border_color=palette.line,
            radius=13,
            padding=(dp(4), dp(4)),
            size_hint_y=None,
            height=dp(52),
        )
        self.add_widget(self.shell)
        self.minus = IconButton("minus", color=palette.ink, size=dp(38), icon_size=dp(16))
        self.value_label = Txt("", size=15, bold=True, color=palette.ink, halign="center")
        self.plus = IconButton("plus", color=palette.ink, size=dp(38), icon_size=dp(16))
        self.shell.add_widget(self.minus)
        self.shell.add_widget(self.value_label)
        self.shell.add_widget(self.plus)
        self.minus.bind(on_release=lambda *_: self._step(-1))
        self.plus.bind(on_release=lambda *_: self._step(1))
        self._refresh()

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value: int):
        self._value = max(self.minimum, min(self.maximum, int(new_value)))
        self._refresh()

    def _step(self, delta):
        old = self._value
        self.value = self._value + delta
        if self._value != old and self.on_change:
            self.on_change(self._value)

    def _refresh(self):
        self.value_label.text = self.formatter(self._value)
        self.minus.opacity = 0.35 if self._value <= self.minimum else 1
        self.plus.opacity = 0.35 if self._value >= self.maximum else 1


class MiniSwitch(ButtonBehavior, Widget):
    value = BooleanProperty(False)

    def __init__(self, *, palette: Palette, value=False, on_change: Callable[[bool], None] | None = None, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(46), dp(28)), **kwargs)
        self.palette = palette
        self.value = value
        self.on_change = on_change
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)
        self._redraw()

    def on_release(self):
        self.value = not self.value
        if self.on_change:
            self.on_change(self.value)

    def _redraw(self, *_):
        p = self.palette
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*_as_color(p.accent if self.value else p.line))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.height / 2])
            knob = self.height - dp(6)
            kx = self.right - knob - dp(3) if self.value else self.x + dp(3)
            Color(*_as_color(p.accent_ink if self.value else p.surface))
            Ellipse(pos=(kx, self.y + dp(3)), size=(knob, knob))


class Divider(Widget):
    def __init__(self, color="#E5E2D8", height=dp(1), **kwargs):
        super().__init__(size_hint_y=None, height=height, **kwargs)
        with self.canvas:
            self._color = Color(*_as_color(color))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class EmptyArt(Widget):
    """空课表的小插画：一轮太阳、地平线和一片叶子。"""

    def __init__(self, palette: Palette, **kwargs):
        super().__init__(**kwargs)
        self.palette = palette
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        p = self.palette
        w, h = self.size
        if w < 10 or h < 10:
            return
        cx = self.x + w * 0.5
        sun_y = self.y + h * 0.64
        r = min(w, h) * 0.15
        with self.canvas:
            Color(*_as_color(p.accent_soft))
            Ellipse(pos=(cx - r * 2.2, sun_y - r * 2.2), size=(r * 4.4, r * 4.4))
            Color(*_as_color(p.accent))
            Line(circle=(cx, sun_y, r), width=dp(1.8))
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                Line(
                    points=[cx + dx * r * 1.45, sun_y + dy * r * 1.45, cx + dx * r * 1.8, sun_y + dy * r * 1.8],
                    width=dp(1.6),
                    cap="round",
                )
            Color(*_as_color(p.line))
            Line(points=[self.x + w * 0.16, self.y + h * 0.24, self.x + w * 0.84, self.y + h * 0.24], width=dp(1.2))


class ConfirmDialog(ModalView):
    def __init__(
        self,
        *,
        palette: Palette,
        title: str,
        message: str,
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        danger: bool = False,
        on_confirm: Callable | None = None,
        **kwargs,
    ):
        super().__init__(
            size_hint=(0.88, None),
            height=dp(246),
            auto_dismiss=False,
            background_color=(0, 0, 0, 0),
            background="",
            overlay_color=_as_color(palette.overlay),
            **kwargs,
        )
        self.palette = palette
        self._on_confirm = on_confirm
        card = Card(
            orientation="vertical",
            bg_color=palette.surface,
            border_color=palette.line,
            radius=22,
            padding=(dp(22), dp(20), dp(22), dp(16)),
            spacing=dp(8),
        )
        self.add_widget(card)
        card.add_widget(Txt(title, size=19, bold=True, color=palette.ink, size_hint_y=None, height=dp(30)))
        card.add_widget(
            Txt(
                message,
                size=13,
                color=palette.muted,
                wrap=True,
                size_hint_y=None,
                height=dp(82),
                valign="top",
            )
        )
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        cancel = JkButton(cancel_text, palette=palette, kind="ghost", height=dp(46), on_release=self.dismiss)
        ok = JkButton(confirm_text, palette=palette, kind="danger" if danger else "primary", height=dp(46), on_release=self._confirm)
        buttons.add_widget(cancel)
        buttons.add_widget(ok)
        card.add_widget(buttons)

    def _confirm(self):
        callback = self._on_confirm
        self.dismiss()
        if callback:
            callback()


class Toast(BoxLayout):
    def __init__(self, message: str, *, palette: Palette, **kwargs):
        super().__init__(size_hint=(None, None), orientation="horizontal", padding=(dp(16), dp(8)), **kwargs)
        self.palette = palette
        label = Txt(message, size=12.5, color=palette.surface, bold=True, halign="center")
        self.add_widget(label)
        text_width, text_height = measure_text(message, 12.5, True)
        self.width = min(dp(330), max(dp(150), text_width + dp(42)))
        self.height = max(dp(42), text_height + dp(18))
        with self.canvas.before:
            Color(*_as_color(palette.ink, 0.94))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.height / 2])
        self.bind(pos=self._redraw)
        self.opacity = 0

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*_as_color(self.palette.ink, 0.94))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.height / 2])


class SectionTitle(BoxLayout):
    def __init__(self, title: str, *, palette: Palette, trailing: str = "", **kwargs):
        super().__init__(size_hint_y=None, height=dp(34), **kwargs)
        self.add_widget(Txt(title, size=15, bold=True, color=palette.ink))
        if trailing:
            t = Txt(trailing, size=11.5, color=palette.faint, halign="right")
            self.add_widget(t)


class InfoRow(BoxLayout):
    def __init__(self, icon: str, label: str, value: str, *, palette: Palette, **kwargs):
        super().__init__(size_hint_y=None, height=dp(44), spacing=dp(10), **kwargs)
        ic = Icon(icon, color=palette.muted, size_hint=(None, None), size=(dp(18), dp(18)))
        self.add_widget(ic)
        self.add_widget(Txt(label, size=12, color=palette.muted, size_hint_x=None, width=dp(38)))
        self.add_widget(Txt(value, size=13, color=palette.ink, wrap=True))
