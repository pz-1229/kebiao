"""修改 12 节课的上课 / 下课时间。"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from .base import AppBar, BaseScreen
from .core import Period, PERIOD_COUNT, clock_text, parse_clock, validate_periods
from .theme import FONT_NAME, PAGE_PAD, fs
from .widgets import JkButton, Card, Txt, _as_color


class TimeBox(Card):
    def __init__(self, *, palette, text, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(76), dp(40)),
            bg_color=palette.chip,
            border_color=palette.line,
            radius=10,
            padding=(dp(8), 0),
            **kwargs,
        )
        self.palette = palette
        self.input = TextInput(
            text=text,
            multiline=False,
            font_name=FONT_NAME,
            font_size=fs(13),
            foreground_color=_as_color(palette.ink),
            cursor_color=_as_color(palette.accent),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            border=(0, 0, 0, 0),
            padding=(0, dp(8)),
            halign="center",
            write_tab=False,
        )
        self.add_widget(self.input)
        self.input.bind(focus=self._focused)
        self.bind(pos=self._redraw, size=self._redraw)

    def _focused(self, *_):
        self.border_color = _as_color(self.palette.accent if self.input.focus else self.palette.line)
        self._redraw()

    def _redraw(self, *_):
        # Card 的 _redraw 负责背景，这里只同步边框颜色。
        super()._redraw()


class PeriodEditorScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="periods", **kwargs)
        self._boxes = []
        self._error = None

    def refresh(self):
        self._build()

    def _build(self):
        self.clear_widgets()
        self._boxes = []
        p = self.palette
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)
        root.add_widget(AppBar("作息时间", palette=p, on_back=self.app.close_subpage, trailing="保存", on_trailing=self._save))
        scroll = ScrollView(do_scroll_x=False, bar_width=0, scroll_type=["bars", "content"])
        root.add_widget(scroll)
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(PAGE_PAD, dp(4), PAGE_PAD, dp(28)),
            spacing=dp(12),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        content.add_widget(
            Txt(
                "按学校作息填写每节课的上下课时间。下一节的开始时间不能早于上一节的结束时间。",
                size=11,
                color=p.muted,
                wrap=True,
                size_hint_y=None,
                height=dp(40),
                valign="top",
            )
        )
        card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(PERIOD_COUNT * 52 + 24),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(14), dp(12)),
            spacing=0,
        )
        content.add_widget(card)
        for index, period in enumerate(self.app.data.semester.periods, 1):
            row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
            row.add_widget(Txt(f"第 {index} 节", size=11.5, bold=True, color=p.ink, size_hint_x=None, width=dp(52)))
            start = TimeBox(palette=p, text=clock_text(period.start))
            end = TimeBox(palette=p, text=clock_text(period.end))
            row.add_widget(start)
            row.add_widget(Txt("–", size=13, color=p.faint, size_hint_x=None, width=dp(12), halign="center"))
            row.add_widget(end)
            row.add_widget(Widget())
            card.add_widget(row)
            self._boxes.append((start, end))
        self._error = Txt("", size=11, color=p.danger, wrap=True, size_hint_y=None, height=0)
        content.add_widget(self._error)
        content.add_widget(
            JkButton("保存作息", palette=p, height=dp(50), on_release=self._save)
        )
        content.add_widget(
            Txt(
                "修改后会立即影响今日课程、下一节课和倒计时。",
                size=9.5,
                color=p.faint,
                halign="center",
                size_hint_y=None,
                height=dp(24),
            )
        )

    def _save(self):
        periods = []
        for index, (start_box, end_box) in enumerate(self._boxes, 1):
            try:
                start = parse_clock(start_box.input.text)
                end = parse_clock(end_box.input.text)
            except ValueError:
                self._show_error(f"第 {index} 节的时间格式不对，请用 HH:MM，例如 08:00。")
                return
            periods.append(Period(start, end))
        try:
            validate_periods(periods)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self.app.data.semester.periods = tuple(periods)
        try:
            self.app.commit_data()
        except OSError:
            self._show_error("保存失败，请检查手机存储空间。")
            return
        self.app.toast("作息时间已保存")
        self.app.close_subpage()

    def _show_error(self, message):
        self._error.text = message
        self._error.height = dp(38)
        self.app.toast(message)

    def on_back(self):
        self.app.close_subpage()
        return True
