"""周课表页：一周七天的网格、课程块和空白格添加。"""

from __future__ import annotations

from datetime import date, datetime

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .base import BaseScreen
from .core import WEEKDAY_NAMES, Course, overlap_layout
from .theme import PAGE_PAD
from .widgets import JkButton, Card, IconButton, Txt, _as_color, rgba


class EmptyCell(ButtonBehavior, Widget):
    def __init__(self, day, period, callback, **kwargs):
        super().__init__(**kwargs)
        self.day, self.period = day, period
        self.callback = callback
        self.bind(on_release=self._released)

    def _released(self, *_):
        if self.callback:
            self.callback(self.day, self.period)


class CourseBlock(ButtonBehavior, BoxLayout):
    def __init__(self, course: Course, *, palette, on_release, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.course = course
        self.palette = palette
        bg, fg = palette.course(course.color)
        self._bg = _as_color(bg)
        self._fg = _as_color(fg)
        self.padding = (dp(5), dp(5), dp(5), dp(4))
        self.spacing = 0
        self.bind(pos=self._redraw, size=self._redraw, state=self._state)
        if on_release:
            self.bind(on_release=lambda *_: on_release(course))
        self.name_label = Txt(
            course.name,
            size=10.5 if self.width >= dp(48) else 9.8,
            bold=True,
            color=fg,
            wrap=True,
            valign="top",
        )
        self.add_widget(self.name_label)
        self.room_label = None
        if course.room and course.period_count >= 2:
            self.room_label = Txt(
                course.room,
                size=7.4,
                color=rgba(fg, 0.72),
                wrap=True,
                size_hint_y=None,
                height=dp(22),
                valign="bottom",
            )
            self.add_widget(self.room_label)
        self._redraw()
        self._state()

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])
            Color(*_as_color(self._fg, 0.13))
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(9)), width=1)
        if self.room_label:
            self.room_label.opacity = 1 if self.height >= dp(67) else 0

    def _state(self, *_):
        self.opacity = 0.7 if self.state == "down" else 1.0


class NowLine(Widget):
    def __init__(self, palette, **kwargs):
        super().__init__(**kwargs)
        self.palette = palette
        self.bind(pos=self._redraw, size=self._redraw)
        self.y_pos = -1

    def set_y(self, y_pos, dot_x=None):
        self.y_pos = y_pos
        self.dot_x = dot_x
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        if self.y_pos < 0:
            return
        dot_x = getattr(self, "dot_x", None) or self.x
        with self.canvas:
            Color(*_as_color(self.palette.now_line))
            Line(points=[self.x, self.y_pos, self.right, self.y_pos], width=dp(1.4))
            Ellipse(pos=(dot_x - dp(3), self.y_pos - dp(3)), size=(dp(6), dp(6)))


class WeekGrid(Widget):
    ROW_HEIGHT = dp(58)
    GUTTER = dp(33)

    def __init__(self, *, app, on_empty, on_course, **kwargs):
        super().__init__(size_hint_y=None, **kwargs)
        self.app = app
        self.palette = app.palette
        self.on_empty = on_empty
        self.on_course = on_course
        self.week = 1
        self.visible_days = [0, 1, 2, 3, 4, 5, 6]
        self.courses: list[Course] = []
        self._blocks: list[CourseBlock] = []
        self._now_line = None
        self._last_size = (0, 0)
        self.height = self.ROW_HEIGHT * len(self.app.data.semester.periods)
        self.bind(pos=self._redraw_bg, size=self._on_size)
        self._now_event = Clock.schedule_interval(self._update_now, 30)

    def _on_size(self, *_):
        if (self.width, self.height) != self._last_size and self.width > 10:
            self._last_size = (self.width, self.height)
            self._rebuild()

    # ------------------------------------------------------------------
    def set_week(self, week: int, courses: list[Course], visible_days: list[int]):
        self.week = week
        self.courses = courses
        self.visible_days = visible_days
        self._rebuild()

    def _rebuild(self):
        if self.width <= 10:
            return
        self.clear_widgets()
        self._blocks.clear()
        self._now_line = None
        self._redraw_bg()
        n = len(self.visible_days)
        col_w = (self.width - self.GUTTER) / n
        periods = self.app.data.semester.periods

        # 空白格放在最底层，之后添加的课程块会盖在上面。
        for day in self.visible_days:
            day_index = self.visible_days.index(day)
            for period in range(1, len(periods) + 1):
                cell = EmptyCell(
                    day,
                    period,
                    self.on_empty,
                    size_hint=(None, None),
                    size=(col_w, self.ROW_HEIGHT),
                    pos=(self.x + self.GUTTER + day_index * col_w, self.top - period * self.ROW_HEIGHT),
                )
                self.add_widget(cell)

        # 左侧节次/时间表。
        for index, period in enumerate(periods, 1):
            top = self.top - (index - 1) * self.ROW_HEIGHT
            num = Txt(
                str(index),
                size=10.5,
                bold=True,
                color=self.palette.muted,
                halign="center",
                size_hint=(None, None),
                widget_size=(self.GUTTER - dp(4), dp(17)),
                pos=(self.x, top - dp(23)),
            )
            self.add_widget(num)
            tm = Txt(
                period.start.strftime("%H:%M"),
                size=7.9,
                color=self.palette.faint,
                halign="center",
                size_hint=(None, None),
                widget_size=(self.GUTTER - dp(4), dp(13)),
                pos=(self.x, top - dp(38)),
            )
            self.add_widget(tm)

        # 重叠布局必须一天一天算，否则周一第 1 节和周二第 1 节会被误认为重叠。
        for day in self.visible_days:
            day_index = self.visible_days.index(day)
            day_courses = [c for c in self.courses if c.day == day]
            for block in overlap_layout(day_courses):
                course = block.course
                lane_w = col_w / block.columns
                x = self.x + self.GUTTER + day_index * col_w + block.column * lane_w + dp(2)
                y = self.top - course.end * self.ROW_HEIGHT + dp(2)
                w = max(dp(18), lane_w - dp(4))
                h = max(dp(26), course.period_count * self.ROW_HEIGHT - dp(4))
                cb = CourseBlock(
                    course,
                    palette=self.palette,
                    on_release=self.on_course,
                    size_hint=(None, None),
                    size=(w, h),
                    pos=(x, y),
                )
                self.add_widget(cb)
                self._blocks.append(cb)

        self._now_line = NowLine(self.palette, size_hint=(None, None), size=(self.width, self.height), pos=self.pos)
        self.add_widget(self._now_line)
        self._update_now()

    # ------------------------------------------------------------------
    def _redraw_bg(self, *_):
        self.canvas.before.clear()
        self.canvas.clear()
        if self.width <= 10:
            return
        p = self.palette
        n = len(self.visible_days)
        col_w = (self.width - self.GUTTER) / max(1, n)
        rows = len(self.app.data.semester.periods)
        with self.canvas.before:
            Color(*_as_color(p.surface))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
            # 今天所在列淡淡的底色。
            if self.week == self.app.current_week:
                today_index = date.today().weekday()
                if today_index in self.visible_days:
                    di = self.visible_days.index(today_index)
                    Color(*rgba(p.accent, 0.045))
                    RoundedRectangle(
                        pos=(self.x + self.GUTTER + di * col_w, self.y),
                        size=(col_w, self.height),
                        radius=[0],
                    )
            # 周末底色
            for day in self.visible_days:
                if day >= 5:
                    di = self.visible_days.index(day)
                    Color(*rgba(p.surface_alt, 0.72))
                    RoundedRectangle(
                        pos=(self.x + self.GUTTER + di * col_w, self.y),
                        size=(col_w, self.height),
                        radius=[0],
                    )
        with self.canvas:
            # 横向时间线
            for index in range(rows + 1):
                y = self.top - index * self.ROW_HEIGHT
                wide = index in (0, 4, len(self.app.data.semester.periods))
                Color(*rgba(p.line, 1 if wide else 0.8))
                Line(points=[self.x + (0 if index == 0 else self.GUTTER), y, self.right, y], width=1.2 if wide else 1)
            # 纵向日分隔线
            for index in range(n + 1):
                x = self.x + self.GUTTER + index * col_w
                Color(*(_as_color(p.line)[:3] + (0.9,)))
                Line(points=[x, self.y, x, self.top], width=1)
            # 左侧栏分隔
            Color(*_as_color(p.line))
            Line(points=[self.x + self.GUTTER, self.y, self.x + self.GUTTER, self.top], width=1)

    def _update_now(self, *_):
        if getattr(self.app, "week", None) is not None and getattr(self.app.week, "grid", None) is not self:
            self._now_event.cancel()
            return
        if self._now_line is None:
            return
        if self.week != self.app.current_week or date.today().weekday() not in self.visible_days:
            self._now_line.set_y(-1)
            return
        now = datetime.now()
        periods = self.app.data.semester.periods
        y_pos = None
        for i, period in enumerate(periods):
            if now < datetime.combine(now.date(), period.start):
                y_pos = self.top - i * self.ROW_HEIGHT
                break
            if period.start <= now.time() <= period.end:
                total = (datetime.combine(now.date(), period.end) - datetime.combine(now.date(), period.start)).total_seconds()
                frac = (now - datetime.combine(now.date(), period.start)).total_seconds() / max(1, total)
                y_pos = self.top - (i + frac) * self.ROW_HEIGHT
                break
        if y_pos is None:
            y_pos = self.y
        today_index = self.visible_days.index(date.today().weekday())
        col_w = (self.width - self.GUTTER) / max(1, len(self.visible_days))
        dot_x = self.x + self.GUTTER + (today_index + 0.5) * col_w
        self._now_line.set_y(y_pos, dot_x)


class DayStrip(BoxLayout):
    def __init__(self, *, app, week, visible_days, **kwargs):
        super().__init__(size_hint_y=None, height=dp(52), spacing=0, **kwargs)
        self.app = app
        self.palette = app.palette
        self.week = week
        self.visible_days = visible_days
        self._build()

    def _build(self):
        self.clear_widgets()
        self.add_widget(Widget(size_hint_x=None, width=WeekGrid.GUTTER))
        for day in self.visible_days:
            d = self.app.data.semester.date_of(self.week, day)
            today = d == date.today() and self.week == self.app.current_week
            cell = Card(
                orientation="vertical",
                bg_color=self.palette.accent_soft if today else (0, 0, 0, 0),
                border_color=(0, 0, 0, 0),
                radius=12,
                padding=(0, dp(4)),
                spacing=0,
            )
            label_color = self.palette.accent if today else self.palette.faint
            cell.add_widget(Txt(WEEKDAY_NAMES[day], size=8.9, bold=today, color=label_color, halign="center", size_hint_y=None, height=dp(18)))
            cell.add_widget(Txt(str(d.day), size=12.5, bold=True, color=self.palette.ink if today else self.palette.muted, halign="center", size_hint_y=None, height=dp(22)))
            self.add_widget(cell)


class WeekScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="week", **kwargs)
        self.selected_week = self.app.current_week
        self._data_version = -1
        root = BoxLayout(orientation="vertical", padding=(PAGE_PAD, dp(8), PAGE_PAD, 0), spacing=0)
        self.add_widget(root)

        header = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        title = Txt("课表", size=27, bold=True, color=self.palette.ink)
        header.add_widget(title)
        header.add_widget(Widget())
        add = JkButton(
            "添加",
            palette=self.palette,
            kind="soft",
            height=dp(36),
            font_size=12,
            size_hint=(None, None),
            width=dp(66),
            on_release=self.app.start_add_course,
        )
        header.add_widget(add)
        root.add_widget(header)

        nav = BoxLayout(size_hint_y=None, height=dp(47), spacing=dp(2))
        prev = IconButton("left", color=self.palette.muted, size=dp(40), icon_size=dp(18))
        prev.bind(on_release=lambda *_: self.shift_week(-1))
        nxt = IconButton("right", color=self.palette.muted, size=dp(40), icon_size=dp(18))
        nxt.bind(on_release=lambda *_: self.shift_week(1))
        nav.add_widget(prev)
        mid = BoxLayout(orientation="vertical", spacing=0)
        self.week_title = Txt("", size=17, bold=True, color=self.palette.ink, halign="center", size_hint_y=None, height=dp(25))
        self.week_range = Txt("", size=10.5, color=self.palette.muted, halign="center", size_hint_y=None, height=dp(17))
        mid.add_widget(self.week_title)
        mid.add_widget(self.week_range)
        nav.add_widget(mid)
        nav.add_widget(nxt)
        root.add_widget(nav)

        self.day_strip_holder = BoxLayout(size_hint_y=None, height=dp(52))
        root.add_widget(self.day_strip_holder)

        self.scroll = ScrollView(do_scroll_x=False, bar_width=0, scroll_type=["bars", "content"])
        root.add_widget(self.scroll)
        self.grid = WeekGrid(
            app=self.app,
            on_empty=self._empty_cell,
            on_course=self.app.open_detail,
        )
        self.scroll.add_widget(self.grid)

        hint = Txt("点空白格添加课程 · 点课程块查看详情", size=9.5, color=self.palette.faint, halign="center", size_hint_y=None, height=dp(24))
        root.add_widget(hint)

    # ------------------------------------------------------------------
    def refresh(self):
        current = self.app.current_week
        if self._data_version != self.app.data_version or self.selected_week < 1:
            self.selected_week = self.selected_week if 1 <= self.selected_week <= self.app.data.semester.total_weeks else current
            self._data_version = self.app.data_version
        if self.selected_week < 1:
            self.selected_week = 1
        if self.selected_week > self.app.data.semester.total_weeks:
            self.selected_week = self.app.data.semester.total_weeks
        self._render()

    def _render(self):
        week = self.selected_week
        semester = self.app.data.semester
        self.week_title.text = f"第 {week} 周"
        suffix = " · 本周" if week == self.app.current_week else ""
        self.week_range.text = self.app.week_range(week) + suffix
        visible = [0, 1, 2, 3, 4] if not self.app.data.show_weekend else [0, 1, 2, 3, 4, 5, 6]
        self.day_strip_holder.clear_widgets()
        self.day_strip_holder.add_widget(DayStrip(app=self.app, week=week, visible_days=visible))
        self.grid.set_week(week, self.app.courses_for_week(week), visible)
        # 换周后回到顶部，符合“翻页”的直觉。
        self.scroll.scroll_y = 1

    def shift_week(self, delta):
        target = self.selected_week + delta
        if target < 1:
            self.app.toast("已经是第 1 周了")
            return
        if target > self.app.data.semester.total_weeks:
            self.app.toast("已经是最后一周了")
            return
        self.selected_week = target
        self._render()

    def _empty_cell(self, day, period):
        self.app.open_editor(
            defaults={"day": day, "start": period, "end": period},
            origin="week",
        )

    def on_back(self):
        if self.selected_week != self.app.current_week:
            self.selected_week = self.app.current_week
            self._render()
            return True
        return False
