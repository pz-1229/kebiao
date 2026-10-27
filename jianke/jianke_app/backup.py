"""离线备份码：复制一串文本，就能把课表带到新手机。"""

from __future__ import annotations

from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from .base import AppBar, BaseScreen
from .core import DataError, decode_backup, encode_backup
from .theme import FONT_NAME, PAGE_PAD, fs
from .widgets import JkButton, Card, ConfirmDialog, InputField, Txt, _as_color


class BackupScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(name="backup", **kwargs)
        self._error = None
        self._token = ""

    def refresh(self):
        self._build()

    def _build(self):
        self.clear_widgets()
        p = self.palette
        self._token = encode_backup(self.app.data)
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)
        root.add_widget(AppBar("备份与恢复", palette=p, on_back=self.app.close_subpage))
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
                "备份码是一串压缩后的纯文本，包含你的课程、学期和作息设置。它不会上传到服务器。",
                size=11,
                color=p.muted,
                wrap=True,
                size_hint_y=None,
                height=dp(54),
                valign="top",
            )
        )

        content.add_widget(Txt("当前课表的备份码", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(22)))
        code_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(122),
            bg_color=p.surface_alt,
            border_color=p.line,
            radius=16,
            padding=(dp(10), dp(8)),
        )
        content.add_widget(code_card)
        self.code_input = TextInput(
            text=self._token,
            multiline=True,
            readonly=True,
            font_name=FONT_NAME,
            font_size=fs(8.5),
            foreground_color=_as_color(p.muted),
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            border=(0, 0, 0, 0),
            padding=(dp(2), dp(2)),
            cursor_color=_as_color(p.accent),
        )
        code_card.add_widget(self.code_input)
        content.add_widget(
            Txt(
                f"共 {len(self._token):,} 个字符 · 建议复制到备忘录或发给自己",
                size=9.5,
                color=p.faint,
                size_hint_y=None,
                height=dp(18),
            )
        )
        content.add_widget(
            JkButton("复制备份码", palette=p, height=dp(48), on_release=self._copy)
        )
        content.add_widget(Widget(size_hint_y=None, height=dp(8)))

        content.add_widget(Txt("从备份码恢复", size=13, bold=True, color=p.ink, size_hint_y=None, height=dp(22)))
        content.add_widget(
            Txt(
                "恢复会覆盖当前课表。建议先复制上面的备份码，给自己留一条后路。",
                size=10,
                color=p.muted,
                wrap=True,
                size_hint_y=None,
                height=dp(32),
            )
        )
        self.restore_field = InputField(
            "备份码",
            palette=p,
            hint="在这里粘贴 JIANK1.……",
            multiline=True,
            field_height=dp(108),
        )
        content.add_widget(self.restore_field)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        row.add_widget(JkButton("粘贴", palette=p, kind="ghost", height=dp(48), font_size=13, on_release=self._paste))
        row.add_widget(JkButton("恢复课表", palette=p, kind="soft", height=dp(48), font_size=13, on_release=self._restore))
        content.add_widget(row)
        self._error = Txt("", size=10.5, color=p.danger, wrap=True, size_hint_y=None, height=0)
        content.add_widget(self._error)
        content.add_widget(Widget(size_hint_y=None, height=dp(10)))
        content.add_widget(
            Txt(
                "注意：备份码里可能包含老师姓名、教室等信息，分享前请确认。",
                size=9.5,
                color=p.faint,
                wrap=True,
                size_hint_y=None,
                height=dp(30),
                valign="top",
            )
        )

    def _copy(self):
        try:
            Clipboard.copy(self._token)
        except Exception:
            self.app.toast("复制失败，请长按备份码手动选择")
            return
        self.app.toast("备份码已复制")

    def _paste(self):
        try:
            value = Clipboard.paste() or ""
        except Exception:
            value = ""
        if not value:
            self.app.toast("剪贴板是空的，或系统不允许读取")
            return
        self.restore_field.text = value.strip()

    def _restore(self):
        self._error.text = ""
        self._error.height = 0
        token = self.restore_field.text.strip()
        if not token:
            self._show_error("请先粘贴备份码")
            return
        try:
            restored = decode_backup(token)
        except DataError as exc:
            self._show_error(str(exc))
            return
        count = len(restored.courses)
        ConfirmDialog(
            palette=self.palette,
            title="恢复这份备份？",
            message=f"当前课表会被覆盖，恢复后包含 {count} 门课程。此操作不能自动撤销。",
            confirm_text="恢复",
            danger=True,
            on_confirm=lambda: self._do_restore(restored),
        ).open()

    def _do_restore(self, restored):
        try:
            self.app.replace_data(restored)
        except OSError:
            self._show_error("恢复失败，手机存储空间可能已满。")
            return
        self.app.toast(f"已恢复 {len(restored.courses)} 门课程")
        self.app.open_tab(0)

    def _show_error(self, message):
        self._error.text = message
        self._error.height = dp(38)
        self.app.toast(message)

    def on_back(self):
        self.app.close_subpage()
        return True
