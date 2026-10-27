"""无界面的交互流程测试：添加、编辑、复制、删除、设置、作息、备份恢复。"""

from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = ROOT / ".ui-test-data"
if TEST_DATA.exists():
    shutil.rmtree(TEST_DATA)
TEST_DATA.mkdir(parents=True)
os.environ["JIANKE_PREVIEW_DIR"] = str(TEST_DATA)

sys.path.insert(0, str(ROOT / "tools"))
from preview import PREVIEW_DATA, ROOT  # noqa: E402

from kivy.clock import Clock  # noqa: E402

from jianke_app.app import JianKeApp  # noqa: E402
from jianke_app.core import AppData, WeekPlan, demo_data, encode_backup, decode_backup  # noqa: E402
from jianke_app.storage import Storage  # noqa: E402

Storage(PREVIEW_DATA / "jianke-data.json").save(demo_data(date.today()))
app = JianKeApp()
LOG = []
FAILED = []
STEP = 0


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def step(name, fn):
    global STEP
    STEP += 1
    delay = 0.55 * STEP

    def wrapped(_dt):
        try:
            fn()
            LOG.append(f"PASS {name}")
        except Exception as exc:
            FAILED.append((name, exc, traceback.format_exc()))
            LOG.append(f"FAIL {name}: {exc}")
            finish()

    Clock.schedule_once(wrapped, delay)


def finish(*_):
    Path(ROOT / "previews" / "ui_test.txt").write_text(
        "\n\n".join(LOG + ["\n".join(str(x) for x in item) for item in FAILED]),
        encoding="utf-8",
    )
    print("DONE", "failed" if FAILED else "ok")
    app.stop()


def add_course():
    app.show_tab(1)
    app.open_editor(defaults={"day": 0, "start": 3, "end": 4}, origin="week")
    editor = app.editor
    editor.name_field.text = "测试课程"
    editor.room_field.text = "测试楼 101"
    editor.teacher_field.text = "测试老师"
    editor.note_field.text = "自动化测试"
    editor.save()
    check(app.data.semester.week_on(date.today()) >= 1, "week")
    matches = [c for c in app.data.courses if c.name == "测试课程"]
    check(len(matches) == 1, "course not added")
    check(matches[0].weeks == WeekPlan(), "default weeks")
    check(app.root_layout.sm.current == "week", "not back on week")
    check(app.root_layout.nav.height > 0, "nav not visible")


def edit_course():
    course = next(c for c in app.data.courses if c.name == "测试课程")
    app.open_detail(course)
    check(app.root_layout.sm.current == "detail", "detail not open")
    app.open_editor(course, origin="detail")
    app.editor.name_field.text = "测试课程（改）"
    app.editor._select_week_mode("custom")
    app.editor._custom_field.text = "1-4, 6"
    app.editor.save()
    updated = next((c for c in app.data.courses if c.id == course.id), None)
    check(updated is not None, "edited course vanished")
    check(updated.name == "测试课程（改）", "name not edited")
    check(updated.weeks.mode == "custom" and updated.weeks.values == (1, 2, 3, 4, 6), "weeks not parsed")
    check(app.root_layout.sm.current == "detail", "not back on detail")


def duplicate_course():
    course = next(c for c in app.data.courses if c.name == "测试课程（改）")
    app.open_detail(course)
    app.detail._duplicate(course)
    check(app.root_layout.sm.current == "editor", "duplicate editor")
    check(app.editor.editing_id is None, "duplicate should be new")
    check(app.editor.name_field.text == course.name, "template not prefilled")
    app.editor.name_field.text = "测试课程（副本）"
    app.editor.start_stepper.value = 7
    app.editor._start_changed(7)
    app.editor.end_stepper.value = 8
    app.editor._end_changed(8)
    app.editor.save()
    count = len([c for c in app.data.courses if c.name.startswith("测试课程")])
    check(count == 2, f"duplicate count {count}")


def list_weeks():
    course = next(c for c in app.data.courses if c.name == "测试课程（副本）")
    check(course.weeks.mode == "custom", "duplicate weeks")
    check(course.start == 7 and course.end == 8, "duplicate periods")
    app.open_detail(course)
    before = len(app.data.courses)
    app.detail._delete(course)
    check(len(app.data.courses) == before - 1, "delete failed")
    check(app.root_layout.sm.current in ("today", "week"), "delete navigation")


def semester_settings():
    app.show_tab(2)
    settings = app.settings
    new_start = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=7)
    settings.name_field.text = "自动化测试学期"
    settings.date_field.text = new_start.isoformat()
    settings.week_stepper.value = 20
    settings._save_semester()
    check(app.data.semester.name == "自动化测试学期", "semester name")
    check(app.data.semester.start_date == new_start, "semester date")
    check(app.data.semester.total_weeks == 20, "semester weeks")


def period_settings():
    app.open_periods()
    check(app.root_layout.sm.current == "periods", "periods not open")
    screen = app.periods
    check(len(screen._boxes) == 12, "period rows")
    screen._boxes[0][0].input.text = "08:05"
    screen._save()
    check(app.data.semester.periods[0].start.strftime("%H:%M") == "08:05", "period save")
    check(app.root_layout.sm.current == "settings", "period back")


def backup_restore():
    token = encode_backup(app.data)
    restored = decode_backup(token)
    check(len(restored.courses) == len(app.data.courses), "backup course count")
    # 改动一份数据，再恢复
    app.data.courses = []
    app.replace_data(restored)
    check(len(app.data.courses) == len(restored.courses), "restore count")
    check(app.data.semester.name == "自动化测试学期", "restore semester")


def android_back():
    app.show_tab(1)
    # 从周课表退到今日
    Clock.schedule_once(lambda *_: app._on_keyboard(None, 27), 0.05)


def final_check():
    # 数据已经写入磁盘
    disk = Storage(PREVIEW_DATA / "jianke-data.json").load()
    check(len(disk.data.courses) == len(app.data.courses), "data not persisted")
    # 没有课程被意外丢失
    check(len(app.data.courses) >= 8, "too few courses")


step("add_course", add_course)
step("edit_course", edit_course)
step("duplicate_course", duplicate_course)
step("delete_course", list_weeks)
step("semester_settings", semester_settings)
step("period_settings", period_settings)
step("backup_restore", backup_restore)
step("android_back", android_back)
step("final_check", final_check)
Clock.schedule_once(finish, 0.55 * (STEP + 2))
app.run()
