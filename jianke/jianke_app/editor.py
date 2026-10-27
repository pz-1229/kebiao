"""添加 / 编辑课程。"""

from __future__ import annotations

from datetime import datetime

from kivy.graphics import Color, Ellipse, Line
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .base import AppBar, BaseScreen
from .core import (
    COURSE_COLOR_COUNT,
    WEEKDAY_NAMES,
    Course,
    WeekPlan,
    compress_weeks,
    conflict_weeks,
    parse_weeks,
)
from .theme import PAGE_PAD
from .widgets import (
    JkButton,
    Card,
    Chip,
    ConfirmDialog,
    InputField,
    LinkButton,
    NumberStepper,
    Txt,
    _as_color,
    rgba,
)


class ColorSwatch(ButtonBehavior, Widget):
    def __init__(self, index, *, palette, selected=False, on_select=None, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(36), dp(36)), **kwargs)
        self.index = index
        self.palette = palette
        self.selected = selected
        self.on_select = on_select
        bg, fg = palette.course(index)
        self._bg = _as_color(fg)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_selected(self, selected):
        self.selected = selected
        self._redraw()

    def on_release(self):
        if self.on_select:
            self.on_select(self.index)

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            if self.selected:
                Color(*_as_color(self.palette.ink))
                Line(circle=(self.center_x, self.center_y, dp(16.5)), width=dp(1.6))
            Color(*self._bg)
            Ellipse(pos=(self.x + dp(5), self.y + dp(5)), size=(dp(26), dp(26)))
            if self.selected:
                Color(*_as_color(self.palette.surface))
                Ellipse(pos=(self.center_x - dp(3), self.center_y - dp(3)), size=(dp(6), dp(6)))


class CourseEditScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="editor", **kwargs)
        self.origin = "week"
        self.editing_id: str | None = None
        self._snapshot_initial = None
        self._saved = False
        self._closing = False
        self._custom_field = None
        self._custom_added = False
        self._chips = []
        self._week_chips = []
        self._swatches = []
        self._loaded = False

    # ------------------------------------------------------------------
    def setup(
        self,
        *,
        course: Course | None = None,
        defaults: dict | None = None,
        origin: str = "week",
        template: Course | None = None,
    ):
        self.origin = origin
        self.editing_id = course.id if course else None
        self._saved = False
        self._closing = False
        self._loaded = True
        source = course or template
        if source:
            values = {
                "name": source.name,
                "room": source.room,
                "teacher": source.teacher,
                "note": source.note,
                "day": source.day,
                "start": source.start,
                "end": source.end,
                "mode": source.weeks.mode,
                "color": source.color,
                "custom": compress_weeks(source.weeks.values),
            }
        else:
            today = datetime.now().date()
            day = today.weekday()
            if day >= 5 and not self.app.data.show_weekend:
                day = 0
            values = {
                "name": "",
                "room": "",
                "teacher": "",
                "note": "",
                "day": day,
                "start": 1,
                "end": 2,
                "mode": "all",
                "color": len(self.app.data.courses) % COURSE_COLOR_COUNT,
                "custom": "",
            }
        if defaults:
            for key in ("day", "start", "end"):
                if key in defaults and defaults[key] is not None:
                    values[key] = int(defaults[key])
            if values["end"] < values["start"]:
                values["end"] = values["start"]
        self.values = values
        self._build()
        self._snapshot_initial = self._snapshot()

    # ------------------------------------------------------------------
    def _build(self):
        self.clear_widgets()
        self._chips = []
        self._week_chips = []
        self._swatches = []
        v = self.values
        p = self.palette
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)
        root.add_widget(
            AppBar(
                "编辑课程" if self.editing_id else "添加课程",
                palette=p,
                on_back=self.try_close,
                trailing="保存",
                on_trailing=self.save,
            )
        )

        scroll = ScrollView(do_scroll_x=False, bar_width=0, scroll_type=["bars", "content"])
        root.add_widget(scroll)
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(PAGE_PAD, dp(4), PAGE_PAD, dp(26)),
            spacing=dp(14),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)

        self.name_field = InputField("课程名称", palette=p, hint="例如：高等数学", text=v["name"])
        content.add_widget(self.name_field)
        row = BoxLayout(size_hint_y=None, height=dp(75), spacing=dp(10))
        self.room_field = InputField("上课地点", palette=p, hint="教三 201", text=v["room"])
        self.room_field.size_hint_x = 0.52
        self.teacher_field = InputField("老师", palette=p, hint="选填", text=v["teacher"])
        self.teacher_field.size_hint_x = 0.48
        row.add_widget(self.room_field)
        row.add_widget(self.teacher_field)
        content.add_widget(row)

        content.add_widget(Txt("时间安排", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(22)))
        time_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(202),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(14), dp(12)),
            spacing=dp(8),
        )
        content.add_widget(time_card)
        time_card.add_widget(Txt("上课日", size=10.5, bold=True, color=p.muted, size_hint_y=None, height=dp(15)))
        days = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        for day, name in enumerate(WEEKDAY_NAMES):
            chip = Chip(
                name[1],
                palette=p,
                selected=(day == v["day"]),
                height=dp(36),
                on_release=lambda d=day: self._select_day(d),
            )
            days.add_widget(chip)
            self._chips.append(chip)
        time_card.add_widget(days)

        steps = BoxLayout(size_hint_y=None, height=dp(78), spacing=dp(10))
        self.start_stepper = NumberStepper(
            "开始节",
            palette=p,
            value=v["start"],
            minimum=1,
            maximum=12,
            formatter=lambda x: f"第 {x} 节",
            on_change=self._start_changed,
        )
        self.end_stepper = NumberStepper(
            "结束节",
            palette=p,
            value=v["end"],
            minimum=1,
            maximum=12,
            formatter=lambda x: f"第 {x} 节",
            on_change=self._end_changed,
        )
        steps.add_widget(self.start_stepper)
        steps.add_widget(self.end_stepper)
        time_card.add_widget(steps)
        self.time_hint = Txt(self._time_hint(), size=10, color=p.faint, halign="center", size_hint_y=None, height=dp(15))
        time_card.add_widget(self.time_hint)

        content.add_widget(Txt("上课周次", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(22)))
        week_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(86),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(14), dp(12)),
            spacing=dp(8),
        )
        content.add_widget(week_card)
        weeks_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        for mode, label in (("all", "每周"), ("odd", "单周"), ("even", "双周"), ("custom", "自定义")):
            chip = Chip(
                label,
                palette=p,
                selected=(mode == v["mode"]),
                height=dp(36),
                font_size=12,
                on_release=lambda m=mode: self._select_week_mode(m),
            )
            weeks_row.add_widget(chip)
            self._week_chips.append(chip)
        week_card.add_widget(weeks_row)

        self._custom_field = InputField(
            "自定义周次",
            palette=p,
            hint="例如：1-8, 10, 12-16",
            text=v["custom"],
            helper="用逗号分隔，短横线表示连续周次",
            height=dp(80),
        )
        self._custom_field.height = dp(18 + 6 + 48 + 21)
        self._custom_holder = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=0,
        )
        content.add_widget(self._custom_holder)
        self._custom_added = False
        self._sync_custom_field(v["mode"])

        content.add_widget(Txt("颜色标签", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(22)))
        colors = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        for index in range(COURSE_COLOR_COUNT):
            swatch = ColorSwatch(index, palette=p, selected=(index == v["color"]), on_select=self._select_color)
            colors.add_widget(swatch)
            self._swatches.append(swatch)
        colors.add_widget(Widget())
        content.add_widget(colors)

        self.note_field = InputField(
            "备注",
            palette=p,
            hint="作业、考试范围，或者任何想记住的事（选填）",
            text=v["note"],
            multiline=True,
        )
        content.add_widget(self.note_field)

        self.error_label = Txt("", size=11.5, color=p.danger, wrap=True, size_hint_y=None, height=0)
        content.add_widget(self.error_label)

        content.add_widget(
            JkButton(
                "保存课程",
                palette=p,
                height=dp(50),
                on_release=self.save,
            )
        )
        if self.editing_id:
            content.add_widget(
                JkButton(
                    "删除这门课",
                    palette=p,
                    kind="danger",
                    height=dp(44),
                    font_size=13,
                    on_release=self._confirm_delete,
                )
            )
        content.add_widget(
            Txt(
                "课程只保存在本机 · 可在设置里备份",
                size=9.5,
                color=p.faint,
                halign="center",
                size_hint_y=None,
                height=dp(22),
            )
        )

    # ------------------------------------------------------------------
    def _time_hint(self):
        periods = self.app.data.semester.periods
        start = max(1, min(12, self.values["start"]))
        end = max(start, min(12, self.values["end"]))
        s = periods[start - 1].start.strftime("%H:%M")
        e = periods[end - 1].end.strftime("%H:%M")
        return f"{s} – {e} · 共 {end - start + 1} 节"

    def _refresh_time_hint(self):
        self.time_hint.text = self._time_hint()

    def _select_day(self, day):
        self.values["day"] = day
        for index, chip in enumerate(self._chips):
            chip.selected = index == day

    def _start_changed(self, value):
        self.values["start"] = value
        if self.values["end"] < value:
            self.values["end"] = value
            self.end_stepper.value = value
        self._refresh_time_hint()

    def _end_changed(self, value):
        self.values["end"] = value
        if self.values["start"] > value:
            self.values["start"] = value
            self.start_stepper.value = value
        self._refresh_time_hint()

    def _select_week_mode(self, mode):
        self.values["mode"] = mode
        for index, chip in enumerate(self._week_chips):
            chip.selected = ("all", "odd", "even", "custom")[index] == mode
        self._sync_custom_field(mode)

    def _sync_custom_field(self, mode):
        if mode == "custom" and not self._custom_added:
            self._custom_holder.add_widget(self._custom_field)
            self._custom_holder.height = self._custom_field.height
            self._custom_added = True
        elif mode != "custom" and self._custom_added:
            if self._custom_field.parent:
                self._custom_field.parent.remove_widget(self._custom_field)
            self._custom_holder.height = 0
            self._custom_added = False

    def _select_color(self, index):
        self.values["color"] = index
        for i, swatch in enumerate(self._swatches):
            swatch.set_selected(i == index)

    def _snapshot(self):
        def get(field):
            try:
                return field.text
            except Exception:
                return ""
        return (
            get(getattr(self, "name_field", None)),
            get(getattr(self, "room_field", None)),
            get(getattr(self, "teacher_field", None)),
            self.values.get("day"),
            self.values.get("start"),
            self.values.get("end"),
            self.values.get("mode"),
            get(self._custom_field) if self._custom_added else "",
            self.values.get("color"),
            get(getattr(self, "note_field", None)),
        )

    def _dirty(self):
        return self._snapshot() != self._snapshot_initial

    # ------------------------------------------------------------------
    def _error(self, message, field=None):
        self.error_label.text = message
        self.error_label.height = dp(38) if message else 0
        if field:
            field.set_error(True)
        self.app.toast(message)

    def _clear_error(self):
        self.error_label.text = ""
        self.error_label.height = 0
        for field in (self.name_field, self._custom_field):
            field.set_error(False)

    def save(self):
        self._clear_error()
        name = self.name_field.text.strip()
        if not name:
            self._error("先给课程起个名字吧", self.name_field)
            return
        mode = self.values["mode"]
        if mode == "custom":
            try:
                values = parse_weeks(self._custom_field.text, self.app.data.semester.total_weeks)
            except ValueError as exc:
                self._error(str(exc), self._custom_field)
                return
            weeks = WeekPlan("custom", values)
        else:
            weeks = WeekPlan(mode)
        try:
            candidate = Course(
                id=self.editing_id or "",
                name=name,
                day=int(self.values["day"]),
                start=int(self.values["start"]),
                end=int(self.values["end"]),
                weeks=weeks,
                room=self.room_field.text.strip(),
                teacher=self.teacher_field.text.strip(),
                note=self.note_field.text.strip(),
                color=int(self.values["color"]),
            )
        except ValueError as exc:
            self._error(str(exc))
            return
        conflicts = conflict_weeks(self.app.data, candidate, exclude_id=self.editing_id)
        if conflicts:
            descriptions = []
            for other, overlap in conflicts[:2]:
                descriptions.append(f"「{other.name}」第 {compress_weeks(overlap)} 周")
            message = "与 " + "、".join(descriptions) + " 的星期和节次重叠。仍然保存吗？"
            ConfirmDialog(
                palette=self.palette,
                title="时间冲突",
                message=message,
                confirm_text="仍然保存",
                danger=True,
                on_confirm=lambda c=candidate: self._do_save(c),
            ).open()
            return
        self._do_save(candidate)

    def _do_save(self, candidate):
        data = self.app.data
        if self.editing_id:
            for index, existing in enumerate(data.courses):
                if existing.id == self.editing_id:
                    data.courses[index] = candidate
                    break
            else:
                data.courses.append(candidate)
        else:
            data.courses.append(candidate)
        if data.demo:
            data.demo = False
        try:
            self.app.commit_data()
        except OSError:
            self._error("保存失败，手机存储空间可能已满")
            return
        self._saved = True
        self.app.toast("课程已保存")
        self.app.after_edit(candidate, self.origin, editing=bool(self.editing_id))

    def _confirm_delete(self):
        if not self.editing_id:
            return
        ConfirmDialog(
            palette=self.palette,
            title="删除课程",
            message="删除后，这门课的所有周次安排都会消失。可以先在设置里备份课表。",
            confirm_text="删除",
            danger=True,
            on_confirm=self._do_delete,
        ).open()

    def _do_delete(self):
        course_id = self.editing_id
        if not course_id:
            return
        self.app.data.courses = [c for c in self.app.data.courses if c.id != course_id]
        try:
            self.app.commit_data()
        except OSError:
            self.app.toast("删除失败，请稍后再试")
            return
        self._saved = True
        self.app.toast("课程已删除")
        self.app.after_delete(self.origin)

    # ------------------------------------------------------------------
    def try_close(self):
        if self._saved or not self._loaded:
            self.app.leave_editor(self.origin)
            return
        if not self._dirty():
            self.app.leave_editor(self.origin)
            return
        if self._closing:
            return
        self._closing = True
        ConfirmDialog(
            palette=self.palette,
            title="放弃修改？",
            message="刚刚填写的内容还没有保存。",
            confirm_text="放弃",
            cancel_text="继续编辑",
            danger=True,
            on_confirm=self._discard,
        ).open()
        # Modal 关掉后允许再次触发返回。
        from kivy.clock import Clock

        Clock.schedule_once(lambda *_: setattr(self, "_closing", False), 0.4)

    def _discard(self):
        self.app.leave_editor(self.origin)

    def on_back(self):
        self.try_close()
        return True
