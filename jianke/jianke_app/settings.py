"""设置页：学期、显示、作息与数据管理。"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .base import BaseScreen
from .core import academic_term_name, monday_of, parse_date
from .theme import PAGE_PAD
from .widgets import (
    JkButton,
    Card,
    Chip,
    ConfirmDialog,
    Divider,
    Icon,
    InputField,
    MiniSwitch,
    NumberStepper,
    Txt,
)


class SettingsRow(ButtonBehavior, BoxLayout):
    def __init__(
        self,
        title,
        *,
        palette,
        subtitle="",
        danger=False,
        on_release=None,
        trailing=None,
        chevron=False,
        **kwargs,
    ):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            spacing=dp(10),
            padding=(dp(16), 0),
            **kwargs,
        )
        self.palette = palette
        body = BoxLayout(orientation="vertical", spacing=0)
        body.add_widget(Txt(title, size=13, bold=True, color=palette.danger if danger else palette.ink, size_hint_y=None, height=dp(22)))
        if subtitle:
            body.add_widget(Txt(subtitle, size=10, color=palette.muted, shorten=True, size_hint_y=None, height=dp(16)))
        self.add_widget(body)
        if trailing:
            self.add_widget(trailing)
        if chevron:
            self.add_widget(Icon("right", color=palette.faint, size_hint=(None, None), size=(dp(16), dp(16))))
        if on_release:
            self.bind(on_release=lambda *_: on_release())
            self.bind(state=self._state)
        else:
            self.disabled = True

    def _state(self, *_):
        self.opacity = 0.7 if self.state == "down" else 1.0


class SettingsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="settings", **kwargs)
        self._built_for_version = -1
        self._semester_error = None
        self._semester_saved = False
        self._week_count = 18
        self._week_count_label = None
        self._theme_chips = []

    def refresh(self):
        if self._built_for_version == self.app.data_version and not self._semester_saved:
            return
        self._semester_saved = False
        self._built_for_version = self.app.data_version
        self._build()

    def _build(self):
        self.clear_widgets()
        p = self.palette
        data = self.app.data
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)
        scroll = ScrollView(do_scroll_x=False, bar_width=0, scroll_type=["bars", "content"])
        root.add_widget(scroll)
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(PAGE_PAD, dp(10), PAGE_PAD, dp(30)),
            spacing=dp(0),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)

        content.add_widget(Txt("设置", size=27, bold=True, color=p.ink, size_hint_y=None, height=dp(42)))
        content.add_widget(
            Txt("没有广告，也没有账号。课表只属于你。", size=11.5, color=p.muted, size_hint_y=None, height=dp(24))
        )
        content.add_widget(Widget(size_hint_y=None, height=dp(16)))

        # ---- 学期 -----------------------------------------------------
        content.add_widget(self._section("学期"))
        semester_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(348),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(16), dp(14)),
            spacing=dp(10),
        )
        content.add_widget(semester_card)
        self.name_field = InputField("学期名称", palette=p, hint="例如：2026 年秋季学期", text=data.semester.name)
        self.date_field = InputField(
            "开学日期",
            palette=p,
            hint="YYYY-MM-DD",
            text=data.semester.start_date.isoformat(),
            helper="请填写第 1 周的周一",
        )
        semester_card.add_widget(self.name_field)
        semester_card.add_widget(self.date_field)
        self.week_stepper = NumberStepper(
            "总周数",
            palette=p,
            value=data.semester.total_weeks,
            minimum=1,
            maximum=30,
            formatter=lambda value: f"{value} 周",
        )
        semester_card.add_widget(self.week_stepper)
        semester_card.add_widget(
            JkButton(
                "保存学期设置",
                palette=p,
                kind="soft",
                height=dp(40),
                font_size=13,
                on_release=self._save_semester,
            )
        )
        self._semester_error = Txt("", size=10.5, color=p.danger, wrap=True, size_hint_y=None, height=0)
        content.add_widget(self._semester_error)
        content.add_widget(Widget(size_hint_y=None, height=dp(16)))

        # ---- 显示 -----------------------------------------------------
        content.add_widget(self._section("显示"))
        display_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(122),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(0), dp(4)),
            spacing=0,
        )
        content.add_widget(display_card)
        weekend_row = BoxLayout(size_hint_y=None, height=dp(52), padding=(dp(16), 0), spacing=dp(10))
        weekend_row.add_widget(Txt("显示周末", size=13, bold=True, color=p.ink))
        weekend_row.add_widget(Widget())
        self.weekend_switch = MiniSwitch(palette=p, value=data.show_weekend, on_change=self._toggle_weekend)
        weekend_row.add_widget(self.weekend_switch)
        display_card.add_widget(weekend_row)
        display_card.add_widget(Divider(p.line))
        theme_row = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(16), 0), spacing=dp(8))
        theme_row.add_widget(Txt("外观", size=13, bold=True, color=p.ink))
        theme_row.add_widget(Widget())
        for theme, label in (("light", "浅色"), ("dark", "深色")):
            chip = Chip(
                label,
                palette=p,
                selected=data.theme == theme,
                height=dp(34),
                font_size=11.5,
                size_hint=(None, None),
                width=dp(58),
                on_release=lambda t=theme: self._set_theme(t),
            )
            self._theme_chips.append(chip)
            theme_row.add_widget(chip)
        display_card.add_widget(theme_row)
        content.add_widget(Widget(size_hint_y=None, height=dp(16)))

        # ---- 作息 -----------------------------------------------------
        content.add_widget(self._section("作息"))
        periods_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(84),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(0), dp(0)),
            spacing=0,
        )
        content.add_widget(periods_card)
        first = data.semester.periods[0]
        periods_card.add_widget(
            SettingsRow(
                "作息时间",
                palette=p,
                subtitle=f"第 1 节 {first.start:%H:%M} 开始 · 共 {len(data.semester.periods)} 节",
                on_release=self.app.open_periods,
                chevron=True,
            )
        )
        content.add_widget(Widget(size_hint_y=None, height=dp(16)))

        # ---- 数据 -----------------------------------------------------
        content.add_widget(self._section("数据"))
        data_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(168),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(0), dp(0)),
            spacing=0,
        )
        content.add_widget(data_card)
        data_card.add_widget(
            SettingsRow(
                "备份与恢复",
                palette=p,
                subtitle="生成一串离线备份码，换手机也不丢课表",
                on_release=self.app.open_backup,
                chevron=True,
            )
        )
        data_card.add_widget(Divider(p.line))
        data_card.add_widget(
            SettingsRow(
                "载入示例课表",
                palette=p,
                subtitle="用一份演示数据快速熟悉界面",
                on_release=self.app.load_demo_with_confirm,
                chevron=True,
            )
        )
        data_card.add_widget(Divider(p.line))
        data_card.add_widget(
            SettingsRow(
                "清空全部课程",
                palette=p,
                danger=True,
                subtitle="不会删除学期和作息设置",
                on_release=self._confirm_clear,
                chevron=True,
            )
        )
        content.add_widget(Widget(size_hint_y=None, height=dp(16)))

        # ---- 关于 -----------------------------------------------------
        content.add_widget(self._section("关于"))
        about = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(164),
            bg_color=p.surface,
            border_color=p.line,
            radius=18,
            padding=(dp(18), dp(16)),
            spacing=dp(4),
        )
        content.add_widget(about)
        brand = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        brand.add_widget(Txt("简课", size=20, bold=True, color=p.ink))
        brand.add_widget(Txt("v1.0.0", size=10, color=p.faint, valign="bottom"))
        about.add_widget(brand)
        about.add_widget(
            Txt(
                "一个用 Python + Kivy 写的本地课程表。没有开屏广告，没有信息流，也不会把你的课表上传到任何服务器。",
                size=11,
                color=p.muted,
                wrap=True,
                size_hint_y=None,
                height=dp(54),
                valign="top",
            )
        )
        about.add_widget(
            Txt(
                "课程数据保存在应用私有目录。换机前请使用“备份与恢复”。",
                size=9.5,
                color=p.faint,
                wrap=True,
                size_hint_y=None,
                height=dp(30),
                valign="top",
            )
        )
        content.add_widget(Widget(size_hint_y=None, height=dp(12)))
        content.add_widget(
            Txt(
                "把课表还给自己。",
                size=10.5,
                color=p.faint,
                halign="center",
                size_hint_y=None,
                height=dp(24),
            )
        )

    def _section(self, text):
        p = self.palette
        return Txt(text, size=12, bold=True, color=p.muted, size_hint_y=None, height=dp(26))

    # ------------------------------------------------------------------
    def _save_semester(self):
        p = self.palette
        self._semester_error.text = ""
        self._semester_error.height = 0
        self.date_field.set_error(False)
        self.name_field.set_error(False)
        try:
            start = parse_date(self.date_field.text)
        except ValueError as exc:
            self.date_field.set_error(True)
            self._show_semester_error(f"开学日期不正确：{exc}")
            return
        if start.weekday() != 0:
            suggested = monday_of(start)
            self.date_field.set_error(True)
            self._show_semester_error(
                f"开学日期要填周一。{start.month} 月 {start.day} 日所在周的周一是 {suggested.isoformat()}。"
            )
            return
        name = self.name_field.text.strip() or academic_term_name(start)
        total = int(self.week_stepper.value)
        too_late = []
        for course in self.app.data.courses:
            if course.weeks.mode == "custom":
                late = [w for w in course.weeks.values if w > total]
                if late:
                    too_late.append((course.name, max(late)))
        if too_late:
            self._show_semester_error(
                f"「{too_late[0][0]}」安排到了第 {too_late[0][1]} 周，请先改课程或把总周数调大。"
            )
            return
        self.app.data.semester.name = name
        self.app.data.semester.start_date = start
        self.app.data.semester.total_weeks = total
        try:
            self.app.commit_data()
        except OSError:
            self._show_semester_error("保存失败，请检查手机存储空间。")
            return
        self._semester_saved = True
        self._built_for_version = self.app.data_version
        self.app.toast("学期设置已保存")
        self.app.refresh_main()

    def _show_semester_error(self, message):
        self._semester_error.text = message
        self._semester_error.height = dp(40)
        self.app.toast(message)

    def _toggle_weekend(self, value):
        self.app.data.show_weekend = bool(value)
        try:
            self.app.commit_data()
        except OSError:
            self.app.toast("保存失败")
            return
        self.app.refresh_main()
        self.app.toast("已显示周末" if value else "已隐藏周末")

    def _set_theme(self, theme):
        if self.app.data.theme == theme:
            return
        self.app.data.theme = theme
        try:
            self.app.commit_data()
        except OSError:
            self.app.toast("保存失败")
            return
        self.app.apply_theme()

    def _confirm_clear(self):
        if not self.app.data.courses:
            self.app.toast("现在还没有课程")
            return
        ConfirmDialog(
            palette=self.palette,
            title="清空全部课程",
            message="这会删除所有课程，但保留学期和作息设置。建议先备份。",
            confirm_text="清空",
            danger=True,
            on_confirm=self._clear,
        ).open()

    def _clear(self):
        count = len(self.app.data.courses)
        self.app.data.courses = []
        self.app.data.demo = False
        try:
            self.app.commit_data()
        except OSError:
            self.app.toast("清空失败，请稍后再试")
            return
        self.app.refresh_main()
        self.app.toast(f"已清空 {count} 门课程")
