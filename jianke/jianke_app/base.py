"""页面基类与顶部栏。"""

from __future__ import annotations

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from .theme import Palette
from .widgets import IconButton, LinkButton, Txt, _as_color


class BaseScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.palette: Palette = self.app.palette
        with self.canvas.before:
            self._bg_color = Color(*_as_color(self.palette.bg))
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._layout_bg, size=self._layout_bg)

    def _layout_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._bg_color.rgba = _as_color(self.palette.bg)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        pass

    def on_back(self) -> bool:
        return bool(self.app.go_back())


class AppBar(BoxLayout):
    """固定顶部栏：返回箭头 + 标题 + 可选右侧按钮。"""

    def __init__(
        self,
        title: str,
        *,
        palette: Palette,
        on_back=None,
        trailing: str = "",
        on_trailing=None,
        subtitle: str = "",
        **kwargs,
    ):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(4),
            padding=(dp(8), 0, dp(14), 0),
            **kwargs,
        )
        self.palette = palette
        if on_back:
            back = IconButton("back", color=palette.ink, size=dp(42), icon_size=dp(20))
            back.bind(on_release=lambda *_: on_back())
            self.add_widget(back)
        else:
            self.add_widget(BoxLayout(size_hint=(None, 1), width=dp(8)))
        titles = BoxLayout(orientation="vertical", spacing=0)
        titles.add_widget(Txt(title, size=18, bold=True, color=palette.ink))
        if subtitle:
            titles.add_widget(Txt(subtitle, size=10.5, color=palette.muted, size_hint_y=None, height=dp(14)))
        self.add_widget(titles)
        if trailing:
            btn = LinkButton(trailing, color=palette.accent, size=13.5)
            btn.bind(on_release=lambda *_: on_trailing and on_trailing())
            self.add_widget(btn)
