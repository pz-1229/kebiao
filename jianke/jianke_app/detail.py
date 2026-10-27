"""课程详情页。"""

from __future__ import annotations

from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .base import AppBar, BaseScreen
from .core import Course
from .theme import PAGE_PAD
from .widgets import JkButton, Card, ConfirmDialog, Divider, Txt, _as_color, rgba


class DetailHero(Card):
    def __init__(self, course: Course, *, palette, periods, **kwargs):
        bg, fg = palette.course(course.color)
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            height=dp(188),
            bg_color=bg,
            border_color=(0, 0, 0, 0),
            radius=24,
            padding=(dp(20), dp(18)),
            spacing=0,
            **kwargs,
        )
        self.palette = palette
        self.course = course
        self._bg = _as_color(bg)
        self._fg = _as_color(fg)
        inner = BoxLayout(orientation="vertical", padding=0, spacing=0)
        self.add_widget(inner)

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(25), spacing=dp(8))
        top.add_widget(Txt(f"{course.day_name} · {course.period_label()}", size=11, bold=True, color=rgba(fg, 0.72)))
        top.add_widget(Txt(course.weeks.label(), size=10.5, color=rgba(fg, 0.58), halign="right"))
        inner.add_widget(top)
        inner.add_widget(
            Txt(
                course.name,
                size=25,
                bold=True,
                color=fg,
                wrap=True,
                size_hint_y=None,
                height=dp(56),
                valign="top",
            )
        )
        inner.add_widget(Widget())
        place = " · ".join(x for x in (course.room, course.teacher) if x) or "还没有填写地点"
        inner.add_widget(Txt(place, size=12, color=rgba(fg, 0.78), shorten=True, size_hint_y=None, height=dp(20)))
        start = periods[course.start - 1].start.strftime("%H:%M")
        end = periods[course.end - 1].end.strftime("%H:%M")
        inner.add_widget(Txt(f"{start} – {end}", size=10.5, color=rgba(fg, 0.58), size_hint_y=None, height=dp(18)))


class DetailScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="detail", **kwargs)
        self.course_id: str | None = None

    def setup(self, course_id: str):
        self.course_id = course_id
        self._render()

    def _course(self) -> Course | None:
        return next((c for c in self.app.data.courses if c.id == self.course_id), None)

    def refresh(self):
        if self.course_id:
            self._render()

    def _render(self):
        course = self._course()
        if not course:
            # 课程被删除后回到主页面。
            self.app.close_detail()
            return
        self.clear_widgets()
        p = self.palette
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)
        root.add_widget(
            AppBar(
                "课程详情",
                palette=p,
                on_back=self.app.close_detail,
                trailing="编辑",
                on_trailing=lambda: self.app.open_editor(course, origin="detail"),
            )
        )
        scroll = ScrollView(do_scroll_x=False, bar_width=0, scroll_type=["bars", "content"])
        root.add_widget(scroll)
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(PAGE_PAD, dp(2), PAGE_PAD, dp(28)),
            spacing=dp(16),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        content.add_widget(DetailHero(course, palette=p, periods=self.app.data.semester.periods))

        content.add_widget(Txt("课程信息", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(20)))
        info = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(202),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(16), dp(8)),
            spacing=0,
        )
        content.add_widget(info)
        periods = self.app.data.semester.periods
        start = periods[course.start - 1].start.strftime("%H:%M")
        end = periods[course.end - 1].end.strftime("%H:%M")
        rows = [
            ("上课时间", f"{course.day_name}  {start} – {end}  ·  {course.period_label()}"),
            ("上课周次", course.weeks.detail_label(self.app.data.semester.total_weeks)),
            ("上课地点", course.room or "未填写"),
            ("授课老师", course.teacher or "未填写"),
        ]
        for index, (label, value) in enumerate(rows):
            row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
            row.add_widget(Txt(label, size=11.5, color=p.muted, size_hint_x=None, width=dp(58)))
            row.add_widget(Txt(value, size=12.5, color=p.ink, wrap=True, valign="middle"))
            info.add_widget(row)
            if index < len(rows) - 1:
                info.add_widget(Divider(p.line))

        if course.note.strip():
            content.add_widget(Txt("备注", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(20)))
            note = Card(
                orientation="vertical",
                size_hint_y=None,
                height=dp(96),
                bg_color=p.surface_alt,
                border_color=(0, 0, 0, 0),
                radius=16,
                padding=(dp(16), dp(12)),
            )
            note.add_widget(Txt(course.note, size=12.5, color=p.muted, wrap=True, valign="top"))
            content.add_widget(note)

        content.add_widget(Widget(size_hint_y=None, height=dp(6)))
        content.add_widget(
            JkButton(
                "再排一节同样的课",
                palette=p,
                kind="soft",
                height=dp(48),
                font_size=14,
                on_release=lambda: self._duplicate(course),
            )
        )
        content.add_widget(
            JkButton(
                "删除课程",
                palette=p,
                kind="danger",
                height=dp(44),
                font_size=12.5,
                on_release=lambda: self._confirm_delete(course),
            )
        )
        content.add_widget(
            Txt("所有内容只保存在本机", size=9.5, color=p.faint, halign="center", size_hint_y=None, height=dp(18))
        )

    def _duplicate(self, course):
        clone = course.copy_as_new()
        self.app.open_editor(None, origin="detail", template=clone)

    def _confirm_delete(self, course):
        ConfirmDialog(
            palette=self.palette,
            title="删除课程",
            message=f"确定删除「{course.name}」吗？这条安排会从所有周次中移除。",
            confirm_text="删除",
            danger=True,
            on_confirm=lambda: self._delete(course),
        ).open()

    def _delete(self, course):
        self.app.data.courses = [c for c in self.app.data.courses if c.id != course.id]
        try:
            self.app.commit_data()
        except OSError:
            self.app.toast("删除失败，请稍后再试")
            return
        self.app.toast("课程已删除")
        self.app.close_detail()

    def on_back(self):
        self.app.close_detail()
        return True
