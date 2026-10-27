"""今日页。"""

from __future__ import annotations

from datetime import datetime

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .base import BaseScreen
from .core import (
    Moment,
    WEEKDAY_FULL,
    courses_on,
    format_minutes,
    greeting,
    moment_for,
    relative_day,
)
from .theme import PAGE_PAD
from .widgets import (
    JkButton,
    Card,
    EmptyArt,
    Icon,
    Pill,
    Txt,
    _as_color,
    rgba,
)


class ProgressLine(Widget):
    fraction = NumericProperty(0.0)

    def __init__(self, palette, **kwargs):
        super().__init__(size_hint_y=None, height=dp(3), **kwargs)
        self.palette = palette
        self.bind(pos=self._redraw, size=self._redraw, fraction=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        p = self.palette
        radius = self.height / 2
        with self.canvas:
            Color(*rgba(p.hero_muted, 0.28))
            Ellipse(pos=self.pos, size=(self.width, self.height))
            if self.fraction > 0:
                fw = max(self.height, self.width * max(0.0, min(1.0, self.fraction)))
                Color(*rgba(p.hero_ink, 0.9))
                Ellipse(pos=self.pos, size=(fw, self.height))


class CourseRow(ButtonBehavior, Card):
    def __init__(self, course, *, palette, periods, ongoing=False, on_release=None, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(86),
            bg_color=palette.surface,
            border_color=palette.accent if ongoing else palette.line,
            radius=16,
            padding=(dp(12), dp(10)),
            spacing=dp(10),
            **kwargs,
        )
        self.palette = palette
        if on_release:
            self.bind(on_release=lambda *_: on_release())
        self.bind(state=self._state)

        times = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(51), spacing=0)
        period = periods[course.start - 1]
        end_period = periods[course.end - 1]
        times.add_widget(Txt(period.start.strftime("%H:%M"), size=13, bold=True, color=palette.ink, size_hint_y=None, height=dp(20)))
        times.add_widget(Txt(end_period.end.strftime("%H:%M"), size=10, color=palette.faint, size_hint_y=None, height=dp(15)))
        times.add_widget(Txt(course.period_label().replace("第 ", "").replace(" 节", "节"), size=9.5, color=palette.muted, size_hint_y=None, height=dp(15), valign="bottom"))
        self.add_widget(times)

        bar = ColorBar(course.color, palette=palette, size_hint=(None, 1), width=dp(3))
        self.add_widget(bar)

        body = BoxLayout(orientation="vertical", spacing=dp(3))
        title_row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(25))
        title_row.add_widget(Txt(course.name, size=15.5, bold=True, color=palette.ink, shorten=True))
        if ongoing:
            badge = Card(
                size_hint=(None, None),
                height=dp(21),
                width=dp(48),
                bg_color=palette.accent,
                radius=10,
                padding=(dp(6), 0),
            )
            badge.add_widget(Txt("进行中", size=9, bold=True, color=palette.accent_ink, halign="center"))
            title_row.add_widget(badge)
        body.add_widget(title_row)
        details = " · ".join(x for x in (course.room, course.teacher) if x) or "未填写地点"
        body.add_widget(Txt(details, size=11, color=palette.muted, shorten=True))
        self.add_widget(body)
        self.add_widget(Icon("right", color=palette.faint, size_hint=(None, None), size=(dp(16), dp(16))))

    def _state(self, *_):
        self.opacity = 0.78 if self.state == "down" else 1.0


class ColorBar(Widget):
    def __init__(self, color_index, *, palette, **kwargs):
        super().__init__(**kwargs)
        self.palette = palette
        bg, fg = palette.course(color_index)
        self._color = _as_color(fg, 0.8)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self._color)
            from kivy.graphics import RoundedRectangle

            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.width / 2])


class HeroCard(ButtonBehavior, Card):
    def __init__(self, *, palette, moment: Moment, periods, on_release=None, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            height=dp(194),
            bg_color=palette.hero,
            border_color=(0, 0, 0, 0),
            radius=24,
            padding=0,
            **kwargs,
        )
        self.palette = palette
        self.moment = moment
        self.countdown = None
        self.progress = None
        if on_release:
            self.bind(on_release=lambda *_: on_release())

        inner = BoxLayout(
            orientation="vertical",
            padding=(dp(20), dp(17), dp(20), dp(15)),
            spacing=0,
        )
        self.add_widget(inner)

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(24), spacing=dp(8))
        label = "正在上课" if moment.kind == "ongoing" else "下一节课"
        prefix = ""
        if moment.kind != "ongoing" and moment.day and moment.start:
            prefix = relative_day(moment.day, datetime.now().date()) + " · "
        top.add_widget(Txt(prefix + label, size=11.5, bold=True, color=palette.hero_muted))
        time_label = moment.start.strftime("%H:%M") if moment.start else ""
        if moment.course:
            time_label = f"{time_label}  ·  {moment.course.period_label()}"
        top.add_widget(Txt(time_label, size=10.5, color=palette.hero_muted, halign="right"))
        inner.add_widget(top)

        name = moment.course.name if moment.course else ""
        inner.add_widget(
            Txt(
                name,
                size=24,
                bold=True,
                color=palette.hero_ink,
                wrap=True,
                size_hint_y=None,
                height=dp(46),
                valign="top",
            )
        )
        inner.add_widget(Widget(size_hint_y=1))
        bottom = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        place_parts = []
        if moment.course:
            place_parts = [x for x in (moment.course.room, moment.course.teacher) if x]
        place = " · ".join(place_parts) if place_parts else ""
        place_box = BoxLayout(orientation="vertical", spacing=0)
        place_box.add_widget(Txt(place or " ", size=11, color=palette.hero_muted, shorten=True))
        start_end = ""
        if moment.start and moment.end:
            start_end = f"{moment.start:%H:%M} – {moment.end:%H:%M}"
        place_box.add_widget(Txt(start_end, size=10, color=rgba(palette.hero_muted, 0.75), shorten=True))
        bottom.add_widget(place_box)
        self.countdown = Txt(self._countdown_text(), size=11.5, bold=True, color=palette.hero_ink, halign="right")
        bottom.add_widget(self.countdown)
        inner.add_widget(bottom)

        self.progress = ProgressLine(palette)
        inner.add_widget(self.progress)
        if moment.kind != "ongoing":
            self.progress.opacity = 0
        self.update_countdown()

    def _countdown_text(self):
        moment = self.moment
        now = datetime.now()
        if not moment.start:
            return ""
        if moment.kind == "ongoing":
            minutes = (moment.end - now).total_seconds() / 60
            return "还剩 " + format_minutes(round(minutes))
        if moment.day == now.date():
            minutes = (moment.start - now).total_seconds() / 60
            return "还有 " + format_minutes(max(0, round(minutes)))
        if moment.day and moment.start:
            return f"{relative_day(moment.day, now.date())} {moment.start:%H:%M}"
        return ""

    def update_countdown(self):
        if self.countdown:
            self.countdown.text = self._countdown_text()
        if self.progress and self.moment.start and self.moment.end:
            total = (self.moment.end - self.moment.start).total_seconds()
            now = datetime.now()
            self.progress.fraction = max(0.0, min(1.0, (now - self.moment.start).total_seconds() / max(1, total)))

    def _state(self, *_):
        self.opacity = 0.9 if self.state == "down" else 1.0


class HomeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="today", **kwargs)
        self._moment_key = None
        self._hero = None
        self.scroll = ScrollView(do_scroll_x=False, bar_width=0, scroll_type=["bars", "content"])
        self.add_widget(self.scroll)
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(0),
            padding=(PAGE_PAD, dp(10), PAGE_PAD, dp(30)),
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self._tick_event = Clock.schedule_interval(self._tick, 20)

    # ------------------------------------------------------------------
    def refresh(self):
        now = datetime.now()
        data = self.app.data
        today_courses = courses_on(data, now.date())
        moment = moment_for(data, now)
        key = (
            self.app.data_version,
            moment.kind,
            moment.course.id if moment.course else None,
            moment.day,
            now.date(),
        )
        if key == self._moment_key:
            if self._hero:
                self._hero.update_countdown()
            return
        self._moment_key = key
        self.content.clear_widgets()
        self._build_header(now, today_courses, moment)
        self._build_hero(moment, today_courses)
        self._build_timeline(today_courses, moment, now)
        self._build_footer()

    # ------------------------------------------------------------------
    def _build_header(self, now, today_courses, moment):
        top = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(10))
        mark = Card(
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            bg_color=self.palette.accent,
            border_color=(0, 0, 0, 0),
            radius=11,
            padding=0,
        )
        mark.add_widget(Txt("简", size=16, bold=True, color=self.palette.accent_ink, halign="center"))
        top.add_widget(mark)
        brand = BoxLayout(orientation="vertical", spacing=0)
        brand.add_widget(Txt("简课", size=16.5, bold=True, color=self.palette.ink, size_hint_y=None, height=dp(20)))
        brand.add_widget(Txt("无广告 · 纯本地", size=9, color=self.palette.faint, size_hint_y=None, height=dp(13)))
        top.add_widget(brand)
        top.add_widget(Widget())
        week = self.app.week_label()
        pill = Pill(week, palette=self.palette, font_size=10.5)
        top.add_widget(pill)
        self.content.add_widget(top)

        self.content.add_widget(Widget(size_hint_y=None, height=dp(25)))
        date_line = f"{now.month} 月 {now.day} 日 · {WEEKDAY_FULL[now.weekday()]}"
        self.content.add_widget(Txt(date_line, size=11.5, color=self.palette.muted, size_hint_y=None, height=dp(18)))
        self.content.add_widget(
            Txt(greeting(now), size=30, bold=True, color=self.palette.ink, size_hint_y=None, height=dp(44))
        )
        if today_courses:
            count = len(today_courses)
            if moment.kind == "ongoing" and moment.course:
                sub = f"今天 {count} 节课 · 正在上《{moment.course.name}》"
            elif moment.kind == "upcoming" and moment.course and moment.day == now.date():
                sub = f"今天 {count} 节课 · 下一节 {moment.start:%H:%M}"
            else:
                sub = f"今天 {count} 节课"
        elif moment.kind in {"before", "after"}:
            sub = moment.message
        elif self.app.data.courses:
            sub = "今天没有课，给自己留一点空白。"
        else:
            sub = "还没有课程，先添加第一节课吧。"
        self.content.add_widget(Txt(sub, size=12.5, color=self.palette.muted, size_hint_y=None, height=dp(21)))
        self.content.add_widget(Widget(size_hint_y=None, height=dp(18)))

    def _build_hero(self, moment, today_courses):
        if moment.course:
            hero = HeroCard(
                palette=self.palette,
                moment=moment,
                periods=self.app.data.semester.periods,
                on_release=lambda: self.app.open_detail(moment.course),
            )
            self._hero = hero
            self.content.add_widget(hero)
            return
        self._hero = None
        card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(192),
            bg_color=self.palette.hero,
            border_color=(0, 0, 0, 0),
            radius=24,
            padding=(dp(20), dp(18)),
            spacing=dp(6),
        )
        no_courses = not self.app.data.courses
        title = "把课表，还给自己。" if no_courses else "今天，留白。"
        if moment.kind in {"before", "after"}:
            title = "学期之外。"
        self.content.add_widget(card)
        body_text = moment.message or "没有广告，没有弹窗，只有你的课程。"
        if no_courses and moment.kind not in {"before", "after"}:
            body_text = "没有广告，没有弹窗，只有你的课程。"
        card.add_widget(Txt(title, size=24, bold=True, color=self.palette.hero_ink, size_hint_y=None, height=dp(40)))
        card.add_widget(
            Txt(
                body_text,
                size=11.5,
                color=self.palette.hero_muted,
                wrap=True,
                size_hint_y=None,
                height=dp(38),
                valign="top",
            )
        )
        card.add_widget(Widget())
        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        if moment.kind in {"before", "after"}:
            actions.add_widget(
                JkButton(
                    "去设置学期",
                    palette=self.palette,
                    kind="soft",
                    height=dp(42),
                    font_size=13,
                    on_release=lambda: self.app.open_tab(2),
                )
            )
        elif no_courses:
            actions.add_widget(
                JkButton(
                    "添加第一节课",
                    palette=self.palette,
                    kind="soft",
                    height=dp(42),
                    font_size=13,
                    on_release=self.app.start_add_course,
                )
            )
            actions.add_widget(Widget(size_hint_x=None, width=dp(4)))
            actions.add_widget(
                JkButton(
                    "看看示例",
                    palette=self.palette,
                    kind="ghost",
                    height=dp(42),
                    font_size=13,
                    on_release=self.app.load_demo_with_confirm,
                )
            )
        else:
            actions.add_widget(
                JkButton(
                    "打开周课表",
                    palette=self.palette,
                    kind="soft",
                    height=dp(42),
                    font_size=13,
                    on_release=lambda: self.app.open_tab(1),
                )
            )
        card.add_widget(actions)

    def _build_timeline(self, today_courses, moment, now):
        self.content.add_widget(Widget(size_hint_y=None, height=dp(22)))
        header = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        header.add_widget(Txt("今日课程", size=16, bold=True, color=self.palette.ink))
        header.add_widget(
            Txt(f"{len(today_courses)} 节", size=11.5, color=self.palette.faint, halign="right")
        )
        self.content.add_widget(header)
        self.content.add_widget(Widget(size_hint_y=None, height=dp(4)))
        if not today_courses:
            empty = Card(
                orientation="vertical",
                size_hint_y=None,
                height=dp(174),
                bg_color=self.palette.surface,
                border_color=self.palette.line,
                radius=18,
                padding=(dp(20), dp(12)),
                spacing=0,
            )
            art = EmptyArt(self.palette, size_hint_y=None, height=dp(78))
            empty.add_widget(art)
            empty.add_widget(Txt("今天没有安排", size=15, bold=True, color=self.palette.ink, halign="center", size_hint_y=None, height=dp(26)))
            empty.add_widget(
                Txt(
                    "去周课表点一个空格，就能添加课程。" if self.app.data.courses else "添加课程后，它会出现在这里。",
                    size=11,
                    color=self.palette.muted,
                    halign="center",
                    wrap=True,
                    size_hint_y=None,
                    height=dp(33),
                )
            )
            self.content.add_widget(empty)
            return
        for course in today_courses:
            ongoing = bool(
                moment.kind == "ongoing"
                and moment.course
                and moment.course.id == course.id
            )
            row = CourseRow(
                course,
                palette=self.palette,
                periods=self.app.data.semester.periods,
                ongoing=ongoing,
                on_release=lambda c=course: self.app.open_detail(c),
            )
            self.content.add_widget(row)
            self.content.add_widget(Widget(size_hint_y=None, height=dp(9)))

    def _build_footer(self):
        self.content.add_widget(Widget(size_hint_y=None, height=dp(18)))
        self.content.add_widget(
            Txt("课程数据只保存在这台设备里", size=9.5, color=self.palette.faint, halign="center", size_hint_y=None, height=dp(18))
        )

    # ------------------------------------------------------------------
    def _tick(self, *_):
        if getattr(self.app, "home", None) is not self:
            self._tick_event.cancel()
            return
        if self.manager is None or self.manager.current != "today":
            return
        moment = moment_for(self.app.data, datetime.now())
        key = (
            self.app.data_version,
            moment.kind,
            moment.course.id if moment.course else None,
            moment.day,
            datetime.now().date(),
        )
        if key != self._moment_key:
            self.refresh()
        elif self._hero:
            self._hero.update_countdown()
