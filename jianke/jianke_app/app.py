"""应用入口、导航与主题切换。"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import FadeTransition, ScreenManager, SlideTransition
from kivy.utils import platform

from .base import BaseScreen
from .backup import BackupScreen
from .core import AppData, Course, demo_data
from .detail import DetailScreen
from .editor import CourseEditScreen
from .home import HomeScreen
from .periods import PeriodEditorScreen
from .settings import SettingsScreen
from .storage import Storage
from .theme import LIGHT, NAV_HEIGHT, Palette, palette_for, register_font, rgba
from .week import WeekScreen
from .widgets import Icon, Txt, Toast


class NavItem(ButtonBehavior, BoxLayout):
    selected = BooleanProperty(False)

    def __init__(self, icon, label, *, palette, on_release=None, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(1), padding=(0, dp(7)), **kwargs)
        self.palette = palette
        self._icon = Icon(
            icon,
            color=palette.faint,
            size_hint=(None, None),
            size=(dp(21), dp(21)),
            pos_hint={"center_x": 0.5},
        )
        self.add_widget(self._icon)
        self._label = Txt(label, size=9.5, bold=False, color=palette.faint, halign="center", size_hint_y=None, height=dp(14))
        self.add_widget(self._label)
        self.bind(pos=self._refresh, size=self._refresh, selected=self._refresh, state=self._state)
        if on_release:
            self.bind(on_release=lambda *_: on_release())
        self._refresh()

    def _refresh(self, *_):
        p = self.palette
        self._icon.color = p.c("accent") if self.selected else p.c("faint")
        self._label.color = p.c("accent") if self.selected else p.c("faint")
        self._label.bold = self.selected
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*rgba(p.accent_soft if self.selected else p.nav, 0 if not self.selected else 0.9))
            RoundedRectangle(pos=(self.x + dp(7), self.y + dp(3)), size=(self.width - dp(14), self.height - dp(6)), radius=[dp(13)])

    def _state(self, *_):
        self.opacity = 0.65 if self.state == "down" else 1.0


class NavBar(BoxLayout):
    def __init__(self, *, palette, on_select, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=NAV_HEIGHT,
            padding=(dp(12), dp(5), dp(12), dp(4)),
            spacing=dp(4),
            **kwargs,
        )
        self.palette = palette
        self.on_select = on_select
        self.items = []
        for index, (icon, label) in enumerate((("sun", "今天"), ("grid", "课表"), ("sliders", "设置"))):
            item = NavItem(icon, label, palette=palette, on_release=lambda i=index: self.select(i))
            self.add_widget(item)
            self.items.append(item)
        self.bind(pos=self._border, size=self._border)
        self.select(0)

    def select(self, index):
        for i, item in enumerate(self.items):
            item.selected = i == index

    def _border(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*rgba(self.palette.nav))
            Rectangle(pos=self.pos, size=self.size)
            Color(*rgba(self.palette.line, 0.9))
            Rectangle(pos=(self.x, self.top - 1), size=(self.width, 1))


class RootLayout(FloatLayout):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self._toast = None
        with self.canvas.before:
            self._bg_color = Color(*rgba(app.palette.bg))
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._paint_bg, size=self._paint_bg)
        self.main = BoxLayout(orientation="vertical")
        self.add_widget(self.main)
        self.sm = ScreenManager(transition=FadeTransition(duration=0.14))
        self.nav = NavBar(palette=app.palette, on_select=app.open_tab)
        # 先加课表区，再加底部导航，Kivy 的 BoxLayout 会按添加顺序从上到下排列。
        self.main.add_widget(self.sm)
        self.main.add_widget(self.nav)
        self.sm.bind(pos=self._queue_sync, size=self._queue_sync)

    def _paint_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _queue_sync(self, *_):
        # ScreenManager 在转场中会跳过屏幕定位；转场结束后补一次，
        # 否则整个页面会整体偏移一个底部导航的高度。
        Clock.unschedule(self._sync_screens)
        Clock.schedule_once(self._sync_screens, 0.24)

    def _sync_screens(self, *_):
        sm = self.sm
        for screen in sm.screens:
            screen.pos = sm.pos
            screen.size = sm.size

    def set_nav_visible(self, visible: bool):
        if visible:
            self.nav.opacity = 1
            self.nav.height = NAV_HEIGHT
            self.nav.disabled = False
        else:
            self.nav.opacity = 0
            self.nav.height = 0
            self.nav.disabled = True
        self._queue_sync()

    def show_toast(self, message: str):
        if self._toast is not None and self._toast.parent:
            self._toast.parent.remove_widget(self._toast)
        toast = Toast(message, palette=self.app.palette)
        toast.pos_hint = {"center_x": 0.5}
        toast.y = dp(18) + (self.nav.height if self.nav.opacity else 0)
        self.add_widget(toast)
        self._toast = toast
        Animation(opacity=1, d=0.16).start(toast)
        Clock.schedule_once(lambda *_: self._hide_toast(toast), 2.2)

    def _hide_toast(self, toast):
        if toast.parent is None:
            return
        Animation(opacity=0, d=0.2).start(toast)
        Clock.schedule_once(lambda *_: self.remove_widget(toast) if toast.parent else None, 0.25)


class JianKeApp(App):
    title = "简课"

    def build(self):
        register_font()
        if platform not in ("android", "ios"):
            icon_path = Path(__file__).resolve().parent.parent / "assets" / "images" / "icon.png"
            if icon_path.exists():
                self.icon = str(icon_path)
            Window.size = (390, 844)
        Window.softinput_mode = "below_target"
        self.palette: Palette = LIGHT
        self.data_version = 1
        self._main_tab = 0
        self._detail_return_tab = 0
        self._load_warning = ""
        self._mount_data()
        Window.clearcolor = rgba(self.palette.bg)
        self.root_layout = RootLayout(self)
        self._register_screens()
        self.show_tab(0, animate=False)
        Window.bind(on_keyboard=self._on_keyboard)
        if self._load_warning:
            Clock.schedule_once(lambda *_: self.toast(self._load_warning), 0.7)
        return self.root_layout

    # ------------------------------------------------------------------
    def _mount_data(self):
        data_dir = os.environ.get("JIANKE_DATA_DIR")
        if data_dir:
            path = Path(data_dir) / "jianke-data.json"
        else:
            path = Path(self.user_data_dir) / "jianke-data.json"
        self.storage = Storage(path)
        result = self.storage.load()
        self.data = result.data
        self.palette = palette_for(self.data.theme)
        if result.warning:
            self._load_warning = result.warning

    @property
    def current_week(self) -> int:
        week = self.data.semester.week_on(date.today())
        return max(1, min(self.data.semester.total_weeks, week))

    def _register_screens(self):
        sm: ScreenManager = self.root_layout.sm
        self.home = HomeScreen()
        self.week = WeekScreen()
        self.settings = SettingsScreen()
        self.detail = DetailScreen()
        self.editor = CourseEditScreen()
        self.backup = BackupScreen()
        self.periods = PeriodEditorScreen()
        for screen in (self.home, self.week, self.settings, self.detail, self.editor, self.backup, self.periods):
            sm.add_widget(screen)

    def show_tab(self, index, animate=True):
        names = ("today", "week", "settings")
        index = max(0, min(2, int(index)))
        self._main_tab = index
        sm = self.root_layout.sm
        self.root_layout.set_nav_visible(True)
        self.root_layout.nav.select(index)
        sm.transition = FadeTransition(duration=0.14) if animate else FadeTransition(duration=0)
        if sm.current != names[index]:
            sm.current = names[index]
        elif hasattr(sm.current_screen, "refresh"):
            sm.current_screen.refresh()

    open_tab = show_tab

    def _subpage(self, screen, direction="left"):
        sm = self.root_layout.sm
        sm.transition = SlideTransition(duration=0.18, direction=direction)
        self.root_layout.set_nav_visible(False)
        sm.current = screen.name

    # ------------------------------------------------------------------
    def open_detail(self, course: Course):
        if self.root_layout.sm.current not in ("detail", "editor"):
            self._detail_return_tab = self._main_tab
        self.detail.course_id = course.id
        self.detail.setup(course.id)
        self._subpage(self.detail)

    def close_detail(self):
        if self.root_layout.sm.current not in ("detail", "editor"):
            return
        self.show_tab(self._detail_return_tab)

    def open_editor(self, course=None, defaults=None, origin=None, template=None):
        current = self.root_layout.sm.current
        if origin is None:
            if current == "detail":
                origin = "detail"
            else:
                origin = "today" if self._main_tab == 0 else "week"
        self.editor.setup(course=course, defaults=defaults, origin=origin, template=template)
        self._subpage(self.editor)

    def start_add_course(self):
        origin = "today" if self._main_tab == 0 else "week"
        self.open_editor(defaults=None, origin=origin)

    def leave_editor(self, origin):
        if origin == "detail" and self.detail.course_id:
            course = next((c for c in self.data.courses if c.id == self.detail.course_id), None)
            if course:
                self.detail.setup(course.id)
                self._subpage(self.detail)
                return
        self.show_tab(self._detail_return_tab if origin == "detail" else (0 if origin == "today" else 1))

    def after_edit(self, course, origin, editing=False):
        if origin == "detail":
            self.detail.course_id = course.id
            self.detail.setup(course.id)
            self._subpage(self.detail)
        else:
            self.show_tab(0 if origin == "today" else 1)

    def after_delete(self, origin):
        if origin == "detail":
            self.detail.course_id = None
            self.show_tab(self._detail_return_tab)
        else:
            self.show_tab(0 if origin == "today" else 1)

    def open_backup(self):
        self._subpage(self.backup)

    def open_periods(self):
        self._subpage(self.periods)

    def close_subpage(self):
        self.show_tab(2)

    # ------------------------------------------------------------------
    def toast(self, message):
        if getattr(self, "root_layout", None) is not None:
            self.root_layout.show_toast(str(message))

    def commit_data(self):
        self.storage.save(self.data)
        self.data_version += 1
        self.refresh_main()

    def refresh_main(self):
        for screen in (getattr(self, "home", None), getattr(self, "week", None)):
            if screen is not None and screen.manager is not None:
                screen.refresh()

    def apply_theme(self):
        old_theme = self.palette.name
        self.palette = palette_for(self.data.theme)
        Window.clearcolor = self.palette.c("bg")
        # 直接重建界面，确保所有 Canvas 颜色都换成新主题。
        old_root = self.root_layout
        new_root = RootLayout(self)
        self.root_layout = new_root
        self._register_screens()
        if old_root.parent:
            old_root.parent.remove_widget(old_root)
        Window.add_widget(new_root)
        self.root = new_root
        self._main_tab = 2
        self.show_tab(2, animate=False)
        if old_theme != self.palette.name:
            Clock.schedule_once(lambda *_: self.toast("已切换为深色模式" if self.palette.is_dark else "已切换为浅色模式"), 0.1)

    def replace_data(self, restored: AppData):
        theme_changed = restored.theme != self.data.theme
        self.data = restored
        self.storage.save(self.data)
        self.data_version += 1
        if theme_changed:
            self.palette = palette_for(self.data.theme)
            self.apply_theme()
        else:
            self.refresh_main()
            if self.week is not None:
                self.week.selected_week = self.current_week
        self._load_warning = ""

    def load_demo_with_confirm(self):
        if not self.data.courses:
            self._load_demo()
            return
        from .widgets import ConfirmDialog

        ConfirmDialog(
            palette=self.palette,
            title="载入示例课表",
            message="这会把当前课表替换成一份演示数据。需要保留的话，请先备份。",
            confirm_text="载入",
            danger=True,
            on_confirm=self._load_demo,
        ).open()

    def _load_demo(self):
        theme, weekend = self.data.theme, self.data.show_weekend
        demo = demo_data(date.today())
        demo.theme, demo.show_weekend = theme, weekend
        self.data = demo
        try:
            self.commit_data()
        except OSError:
            self.toast("载入失败，请检查存储空间")
            return
        self.show_tab(0)
        self.toast("已载入示例课表")

    # ------------------------------------------------------------------
    def week_label(self):
        week = self.data.semester.week_on(date.today())
        if week < 1:
            return "未开学"
        if week > self.data.semester.total_weeks:
            return "已结课"
        return f"第 {week} 周"

    def week_range(self, week):
        monday = self.data.semester.date_of(week, 0)
        sunday = self.data.semester.date_of(week, 6)
        if monday.month == sunday.month:
            return f"{monday.month}/{monday.day} – {sunday.day}"
        return f"{monday.month}/{monday.day} – {sunday.month}/{sunday.day}"

    def courses_for_week(self, week):
        from .core import courses_for_week

        return courses_for_week(self.data, week)

    # ------------------------------------------------------------------
    def go_back(self):
        if self.root_layout.sm.current != "today":
            self.show_tab(0)
            return True
        return False

    def _on_keyboard(self, window, key, scancode=None, codepoint=None, modifier=None, **kwargs):
        for child in Window.children:
            if isinstance(child, ModalView):
                child.dismiss()
                return True
        if key not in (27, 1001):
            return False
        sm = self.root_layout.sm
        current = sm.current_screen
        if isinstance(current, BaseScreen):
            handled = current.on_back()
            if handled:
                return True
        if sm.current in ("today", "week", "settings"):
            if sm.current != "today":
                self.show_tab(0)
                return True
            return False
        self.show_tab(0)
        return True

    def on_pause(self):
        try:
            self.storage.save(self.data)
        except OSError:
            pass
        return True

    def on_stop(self):
        try:
            self.storage.save(self.data)
        except OSError:
            pass
