from __future__ import annotations

import json
import shutil
import unittest
import uuid
from contextlib import AbstractContextManager
from datetime import date, datetime, time, timedelta
from pathlib import Path

from jianke_app.core import (
    AppData,
    Course,
    DataError,
    Period,
    Semester,
    WeekPlan,
    conflict_weeks,
    courses_on,
    decode_backup,
    default_periods,
    demo_data,
    encode_backup,
    moment_for,
    overlap_layout,
    parse_weeks,
    validate_periods,
)
from jianke_app.storage import Storage


class LocalTempDir(AbstractContextManager):
    """测试用的临时目录，放在项目内，避开受限环境里的系统临时目录。"""

    def __init__(self):
        base = Path(__file__).resolve().parent / "_tmp"
        base.mkdir(exist_ok=True)
        self.path = base / f"test-{uuid.uuid4().hex[:8]}"

    def __enter__(self):
        self.path.mkdir()
        return str(self.path)

    def __exit__(self, *args):
        shutil.rmtree(self.path, ignore_errors=True)
        return False


def make_semester():
    return Semester(name="测试学期", start_date=date(2026, 8, 31), total_weeks=18)


def make_data():
    data = AppData(semester=make_semester())
    data.courses = [
        Course(name="高等数学", day=1, start=3, end=4, room="A201", color=0),
        Course(name="数据结构", day=1, start=5, end=6, room="B402", weeks=WeekPlan("odd"), color=1),
        Course(name="大学英语", day=2, start=1, end=2, room="C305", color=3),
    ]
    return data


class WeekTests(unittest.TestCase):
    def test_week_number(self):
        semester = make_semester()
        self.assertEqual(semester.week_on(date(2026, 8, 31)), 1)
        self.assertEqual(semester.week_on(date(2026, 9, 6)), 1)
        self.assertEqual(semester.week_on(date(2026, 9, 7)), 2)
        self.assertEqual(semester.week_on(date(2026, 10, 27)), 9)
        self.assertLess(semester.week_on(date(2026, 8, 30)), 1)
        self.assertGreater(semester.week_on(date(2027, 1, 10)), 18)

    def test_week_plan(self):
        self.assertTrue(WeekPlan("all").includes(9))
        self.assertTrue(WeekPlan("odd").includes(9))
        self.assertFalse(WeekPlan("odd").includes(10))
        self.assertTrue(WeekPlan("even").includes(10))
        custom = WeekPlan("custom", (1, 3, 5))
        self.assertTrue(custom.includes(3))
        self.assertFalse(custom.includes(2))
        with self.assertRaises(ValueError):
            WeekPlan("custom", ())

    def test_parse_weeks(self):
        self.assertEqual(parse_weeks("1-8, 10, 12~16", 18), tuple(range(1, 9)) + (10,) + tuple(range(12, 17)))
        self.assertEqual(parse_weeks("1，2、3", 18), (1, 2, 3))
        self.assertEqual(parse_weeks("第 1 周-第 3 周", 18), (1, 2, 3))
        with self.assertRaises(ValueError):
            parse_weeks("", 18)
        with self.assertRaises(ValueError):
            parse_weeks("1-20", 18)
        with self.assertRaises(ValueError):
            parse_weeks("5-2", 18)
        with self.assertRaises(ValueError):
            parse_weeks("0-3", 18)

    def test_periods(self):
        periods = default_periods()
        validate_periods(periods)
        self.assertEqual(len(periods), 12)
        bad = list(periods)
        bad[1] = Period(time(8, 30), time(9, 40))
        with self.assertRaises(ValueError):
            validate_periods(bad)
        with self.assertRaises(ValueError):
            validate_periods(periods[:11])


class CourseQueryTests(unittest.TestCase):
    def test_courses_on_weekday_and_parity(self):
        data = make_data()
        # 2026-10-27 是第 9 周（单周）的周二。
        tuesday = date(2026, 10, 27)
        names = [c.name for c in courses_on(data, tuesday)]
        self.assertEqual(names, ["高等数学", "数据结构"])
        # 下一周变成双周，数据结构的单周课消失。
        next_tuesday = tuesday + timedelta(days=7)
        self.assertEqual([c.name for c in courses_on(data, next_tuesday)], ["高等数学"])
        # 学期外没有课。
        self.assertEqual(courses_on(data, date(2027, 2, 1)), [])

    def test_moment(self):
        data = make_data()
        # 2026-10-27 周二
        ongoing = moment_for(data, datetime(2026, 10, 27, 10, 20))
        self.assertEqual(ongoing.kind, "ongoing")
        self.assertEqual(ongoing.course.name, "高等数学")
        upcoming = moment_for(data, datetime(2026, 10, 27, 12, 0))
        self.assertEqual(upcoming.kind, "upcoming")
        self.assertEqual(upcoming.course.name, "数据结构")
        # 晚于最后一节课，下一节是周三的英语。
        later = moment_for(data, datetime(2026, 10, 27, 21, 0))
        self.assertEqual(later.kind, "upcoming")
        self.assertEqual(later.course.name, "大学英语")
        self.assertEqual(later.day, date(2026, 10, 28))
        before = moment_for(data, datetime(2026, 8, 1, 9, 0))
        self.assertEqual(before.kind, "before")

    def test_no_courses(self):
        data = AppData(semester=make_semester())
        moment = moment_for(data, datetime(2026, 10, 27, 10, 0))
        self.assertEqual(moment.kind, "none")

    def test_overlap_columns(self):
        a = Course(name="A", day=0, start=1, end=2)
        b = Course(name="B", day=0, start=2, end=3)
        c = Course(name="C", day=0, start=5, end=6)
        blocks = {block.course.name: block for block in overlap_layout([a, b, c])}
        self.assertEqual(blocks["A"].columns, 2)
        self.assertEqual(blocks["B"].columns, 2)
        self.assertNotEqual(blocks["A"].column, blocks["B"].column)
        self.assertEqual(blocks["C"].columns, 1)

    def test_conflicts(self):
        data = make_data()
        candidate = Course(name="冲突课", day=1, start=4, end=5, weeks=WeekPlan("even"))
        conflicts = conflict_weeks(data, candidate)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0][0].name, "高等数学")
        # 单周的数据结构只在单周，even 候选不会与它冲突；与高数每周都冲突。
        odd_candidate = Course(name="单周冲突", day=1, start=5, end=6, weeks=WeekPlan("odd"))
        conflicts = conflict_weeks(data, odd_candidate)
        self.assertEqual({c.name for c, _ in conflicts}, {"数据结构"})


class BackupAndStorageTests(unittest.TestCase):
    def test_backup_roundtrip(self):
        data = make_data()
        token = encode_backup(data)
        self.assertTrue(token.startswith("JIANK1."))
        restored = decode_backup(token)
        self.assertEqual(restored.to_dict(), data.to_dict())

    def test_corrupted_backup(self):
        data = make_data()
        token = encode_backup(data)
        broken = token[:-8] + "AAAAAAAA"
        with self.assertRaises(DataError):
            decode_backup(broken)
        with self.assertRaises(DataError):
            decode_backup("hello")

    def test_storage_roundtrip(self):
        with LocalTempDir() as tmp:
            path = Path(tmp) / "data.json"
            storage = Storage(path)
            data = make_data()
            storage.save(data)
            self.assertTrue(path.exists())
            loaded = storage.load()
            self.assertEqual(loaded.data.to_dict(), data.to_dict())
            self.assertEqual(loaded.warning, "")

    def test_storage_recovers_from_corruption(self):
        with LocalTempDir() as tmp:
            path = Path(tmp) / "data.json"
            path.write_text("{not json", encoding="utf-8")
            result = Storage(path).load()
            self.assertTrue(result.warning)
            self.assertEqual(result.data.courses, [])
            self.assertTrue(any(Path(tmp).glob("*.broken-*.json")))

    def test_bad_course_is_skipped(self):
        raw = {
            "semester": {"name": "x", "start_date": "2026-08-31", "total_weeks": 18},
            "courses": [
                {"name": "好课", "day": 0, "start": 1, "end": 2},
                {"name": "", "day": 0, "start": 1, "end": 2},
            ],
        }
        data = AppData.from_dict(raw)
        self.assertEqual(len(data.courses), 1)
        self.assertEqual(data.courses[0].name, "好课")

    def test_demo_has_weekend_class(self):
        data = demo_data(date(2026, 10, 27))
        self.assertTrue(any(c.day >= 5 for c in data.courses))
        self.assertGreater(len(data.courses), 5)


if __name__ == "__main__":
    unittest.main()
