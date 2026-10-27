"""简课的核心数据模型与时间逻辑。

这个模块刻意不依赖 Kivy，方便在电脑上直接跑单元测试。
UI 只负责展示，所有“第几周 / 今天有什么课 / 下一节课”的判断都在这里。
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import unicodedata
import zlib
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Sequence

APP_SCHEMA_VERSION = 1
BACKUP_PREFIX = "JIANK1"
MAX_BACKUP_BYTES = 2 * 1024 * 1024

WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
WEEKDAY_SHORT = ("一", "二", "三", "四", "五", "六", "日")
WEEKDAY_FULL = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
DEFAULT_TOTAL_WEEKS = 18
PERIOD_COUNT = 12
MAX_COURSES = 500
MAX_TEXT = 120

DEFAULT_PERIOD_TIMES: tuple[tuple[str, str], ...] = (
    ("08:00", "08:45"),
    ("08:55", "09:40"),
    ("10:00", "10:45"),
    ("10:55", "11:40"),
    ("14:00", "14:45"),
    ("14:55", "15:40"),
    ("16:00", "16:45"),
    ("16:55", "17:40"),
    ("19:00", "19:45"),
    ("19:55", "20:40"),
    ("20:50", "21:35"),
    ("21:45", "22:30"),
)

COURSE_COLOR_COUNT = 8


class DataError(ValueError):
    """数据文件或备份码格式不正确。"""


def new_id() -> str:
    return secrets.token_hex(8)


# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------


def parse_clock(text: str) -> time:
    """解析 HH:MM / H:MM，返回 time。"""
    if not isinstance(text, str):
        raise ValueError("时间格式应为 HH:MM")
    value = unicodedata.normalize("NFKC", text).strip().replace("：", ":")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if not match:
        raise ValueError("时间格式应为 HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("时间超出了 00:00–23:59")
    return time(hour, minute)


def clock_text(value: time) -> str:
    return value.strftime("%H:%M")


def clock_range(start: time, end: time, sep: str = " – ") -> str:
    return f"{clock_text(start)}{sep}{clock_text(end)}"


def parse_date(text: str) -> date:
    """解析 YYYY-MM-DD，也接受 / 或 . 分隔。"""
    value = unicodedata.normalize("NFKC", str(text)).strip()
    value = value.replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if not match:
        raise ValueError("日期格式应为 YYYY-MM-DD")
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError as exc:
        raise ValueError("这个日期不存在") from exc


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def academic_term_name(day: date) -> str:
    if day.month >= 8:
        return f"{day.year} 年秋季学期"
    if day.month == 1:
        return f"{day.year - 1}–{day.year} 学年秋季学期"
    if day.month <= 7:
        return f"{day.year} 年春季学期"
    return f"{day.year} 年学期"


def greeting(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上好"
    if 11 <= hour < 14:
        return "中午好"
    if 14 <= hour < 18:
        return "下午好"
    if 18 <= hour < 23:
        return "晚上好"
    return "夜深了"


def format_minutes(minutes: int) -> str:
    minutes = max(0, int(minutes))
    if minutes < 1:
        return "不到 1 分钟"
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, mins = divmod(minutes, 60)
    if mins == 0:
        return f"{hours} 小时"
    return f"{hours} 小时 {mins} 分钟"


def relative_day(day: date, today: date) -> str:
    delta = (day - today).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    if delta == 2:
        return "后天"
    if 0 < delta < 7:
        return WEEKDAY_NAMES[day.weekday()]
    return f"{day.month} 月 {day.day} 日"


# ---------------------------------------------------------------------------
# 周期与课程
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    start: time
    end: time

    def to_dict(self) -> dict[str, str]:
        return {"start": clock_text(self.start), "end": clock_text(self.end)}

    @classmethod
    def from_dict(cls, raw: Any) -> "Period":
        if isinstance(raw, dict):
            start, end = raw.get("start"), raw.get("end")
        elif isinstance(raw, (list, tuple)) and len(raw) == 2:
            start, end = raw
        else:
            raise DataError("作息时间格式不正确")
        start_t, end_t = parse_clock(str(start)), parse_clock(str(end))
        if end_t <= start_t:
            raise DataError("每节课的结束时间必须晚于开始时间")
        return cls(start_t, end_t)


def default_periods() -> tuple[Period, ...]:
    return tuple(Period(parse_clock(a), parse_clock(b)) for a, b in DEFAULT_PERIOD_TIMES)


def validate_periods(periods: Sequence[Period]) -> None:
    if len(periods) != PERIOD_COUNT:
        raise ValueError(f"需要 {PERIOD_COUNT} 节课的作息时间")
    previous: Period | None = None
    for index, period in enumerate(periods, 1):
        if period.end <= period.start:
            raise ValueError(f"第 {index} 节：下课时间必须晚于上课时间")
        if previous is not None and period.start < previous.end:
            raise ValueError(f"第 {index} 节：上课时间不能早于第 {index - 1} 节的下课时间")
        previous = period


def parse_weeks(text: str, max_week: int = DEFAULT_TOTAL_WEEKS) -> tuple[int, ...]:
    """把 “1-8, 10, 12-16” 解析为周次元组。"""
    if max_week < 1:
        raise ValueError("总周数必须大于 0")
    raw = unicodedata.normalize("NFKC", str(text or "")).strip()
    raw = raw.replace("，", ",").replace("、", ",").replace("；", ",").replace(";", ",")
    raw = raw.replace("—", "-").replace("–", "-").replace("－", "-").replace("~", "-").replace("～", "-")
    raw = raw.replace("第", "").replace("周", "").replace(" ", "")
    if not raw:
        raise ValueError("请输入周次，例如 1-8, 10, 12-16")
    values: set[int] = set()
    for part in raw.split(","):
        if not part:
            continue
        if "-" in part:
            pieces = part.split("-")
            if len(pieces) != 2 or not pieces[0] or not pieces[1]:
                raise ValueError(f"看不懂“{part}”，范围应写成 1-8")
            try:
                start, end = int(pieces[0]), int(pieces[1])
            except ValueError as exc:
                raise ValueError(f"“{part}”不是有效的周次范围") from exc
            if start > end:
                raise ValueError(f"范围“{part}”的起点不能大于终点")
            values.update(range(start, end + 1))
        else:
            try:
                values.add(int(part))
            except ValueError as exc:
                raise ValueError(f"“{part}”不是有效的周次") from exc
    if not values:
        raise ValueError("请输入至少一个周次")
    if min(values) < 1:
        raise ValueError("周次从第 1 周开始")
    if max(values) > max_week:
        raise ValueError(f"这个学期只有 {max_week} 周")
    return tuple(sorted(values))


def compress_weeks(values: Iterable[int]) -> str:
    ordered = sorted(set(int(v) for v in values))
    if not ordered:
        return ""
    pieces: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        pieces.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    pieces.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(pieces)


@dataclass(frozen=True)
class WeekPlan:
    """课程在哪些周上课。mode 为 all / odd / even / custom。"""

    mode: str = "all"
    values: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in {"all", "odd", "even", "custom"}:
            raise ValueError("未知的周次类型")
        if self.mode == "custom" and not self.values:
            raise ValueError("自定义周次不能为空")

    def includes(self, week: int) -> bool:
        if week < 1:
            return False
        if self.mode == "all":
            return True
        if self.mode == "odd":
            return week % 2 == 1
        if self.mode == "even":
            return week % 2 == 0
        return week in self.values

    def label(self) -> str:
        if self.mode == "all":
            return "每周"
        if self.mode == "odd":
            return "单周"
        if self.mode == "even":
            return "双周"
        return f"第 {compress_weeks(self.values)} 周"

    def detail_label(self, total_weeks: int) -> str:
        if self.mode == "all":
            return f"每周 · 第 1–{total_weeks} 周"
        if self.mode == "odd":
            return f"单周 · 第 1–{total_weeks} 周中的单数周"
        if self.mode == "even":
            return f"双周 · 第 1–{total_weeks} 周中的双数周"
        return f"第 {compress_weeks(self.values)} 周 · 共 {len(self.values)} 周"

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "values": list(self.values)}

    @classmethod
    def from_dict(cls, raw: Any) -> "WeekPlan":
        if raw is None:
            return cls()
        if isinstance(raw, str):
            raw = {"mode": raw}
        if not isinstance(raw, dict):
            raise DataError("周次格式不正确")
        mode = str(raw.get("mode", "all"))
        if mode not in {"all", "odd", "even", "custom"}:
            raise DataError("周次格式不正确")
        values_raw = raw.get("values", [])
        values: tuple[int, ...] = ()
        if mode == "custom":
            if not isinstance(values_raw, (list, tuple)):
                raise DataError("自定义周次格式不正确")
            values = tuple(sorted({int(v) for v in values_raw if 1 <= int(v) <= 60}))
            if not values:
                raise DataError("自定义周次不能为空")
        return cls(mode, values)


def week_plans_intersection(a: WeekPlan, b: WeekPlan, total_weeks: int) -> list[int]:
    return [week for week in range(1, total_weeks + 1) if a.includes(week) and b.includes(week)]


@dataclass
class Course:
    name: str
    day: int
    start: int
    end: int
    weeks: WeekPlan = field(default_factory=WeekPlan)
    room: str = ""
    teacher: str = ""
    note: str = ""
    color: int = 0
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        self.name = clean_text(self.name, 40)
        self.room = clean_text(self.room, 40)
        self.teacher = clean_text(self.teacher, 30)
        self.note = clean_text(self.note, 300)
        self.day = int(self.day)
        self.start = int(self.start)
        self.end = int(self.end)
        self.color = int(self.color) % COURSE_COLOR_COUNT
        if not self.name:
            raise ValueError("请填写课程名称")
        if not 0 <= self.day <= 6:
            raise ValueError("星期几不正确")
        if not (1 <= self.start <= PERIOD_COUNT and 1 <= self.end <= PERIOD_COUNT):
            raise ValueError("节次不正确")
        if self.end < self.start:
            raise ValueError("结束节次不能早于开始节次")
        if not self.id or not re.fullmatch(r"[A-Za-z0-9_-]{4,40}", str(self.id)):
            self.id = new_id()

    @property
    def period_count(self) -> int:
        return self.end - self.start + 1

    @property
    def day_name(self) -> str:
        return WEEKDAY_NAMES[self.day]

    def active(self, week: int) -> bool:
        return self.weeks.includes(week)

    def period_label(self) -> str:
        if self.start == self.end:
            return f"第 {self.start} 节"
        return f"第 {self.start}–{self.end} 节"

    def time_range(self, periods: Sequence[Period]) -> str:
        try:
            return clock_range(periods[self.start - 1].start, periods[self.end - 1].end)
        except IndexError:
            return ""

    def copy_as_new(self) -> "Course":
        return replace(self, id=new_id())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "day": self.day,
            "start": self.start,
            "end": self.end,
            "weeks": self.weeks.to_dict(),
            "room": self.room,
            "teacher": self.teacher,
            "note": self.note,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "Course":
        if not isinstance(raw, dict):
            raise DataError("课程数据格式不正确")
        try:
            return cls(
                id=str(raw.get("id", "")),
                name=str(raw.get("name", "")),
                day=int(raw.get("day", 0)),
                start=int(raw.get("start", 1)),
                end=int(raw.get("end", 1)),
                weeks=WeekPlan.from_dict(raw.get("weeks")),
                room=str(raw.get("room", "") or ""),
                teacher=str(raw.get("teacher", "") or ""),
                note=str(raw.get("note", "") or ""),
                color=int(raw.get("color", 0)),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, DataError):
                raise
            raise DataError(f"课程数据有误：{exc}") from exc


def clean_text(value: Any, limit: int = MAX_TEXT) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


@dataclass
class Semester:
    name: str
    start_date: date
    total_weeks: int = DEFAULT_TOTAL_WEEKS
    periods: tuple[Period, ...] = field(default_factory=default_periods)

    def __post_init__(self) -> None:
        self.name = clean_text(self.name, 40) or "我的学期"
        if not isinstance(self.start_date, date):
            raise ValueError("开学日期不正确")
        self.total_weeks = max(1, min(30, int(self.total_weeks)))
        if len(self.periods) != PERIOD_COUNT:
            self.periods = default_periods()
        validate_periods(self.periods)

    def week_on(self, day: date) -> int:
        """返回 day 属于第几周；开学前 <=0，学期结束后 > total_weeks。"""
        return (day - self.start_date).days // 7 + 1

    def date_of(self, week: int, weekday: int) -> date:
        return self.start_date + timedelta(days=(week - 1) * 7 + weekday)

    def period_on(self, day: date, period: int) -> tuple[datetime, datetime] | None:
        if not 1 <= period <= len(self.periods):
            return None
        p = self.periods[period - 1]
        return (
            datetime.combine(day, p.start),
            datetime.combine(day, p.end),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "total_weeks": self.total_weeks,
            "periods": [p.to_dict() for p in self.periods],
        }

    @classmethod
    def from_dict(cls, raw: Any, today: date | None = None) -> "Semester":
        if not isinstance(raw, dict):
            return default_semester(today)
        try:
            start = parse_date(str(raw.get("start_date", "")))
        except ValueError:
            start = monday_of(today or date.today())
        try:
            total = int(raw.get("total_weeks", DEFAULT_TOTAL_WEEKS))
        except (TypeError, ValueError):
            total = DEFAULT_TOTAL_WEEKS
        raw_periods = raw.get("periods")
        periods = default_periods()
        if isinstance(raw_periods, list) and len(raw_periods) == PERIOD_COUNT:
            try:
                periods = tuple(Period.from_dict(item) for item in raw_periods)
                validate_periods(periods)
            except (DataError, ValueError):
                periods = default_periods()
        return cls(
            name=str(raw.get("name", "") or academic_term_name(start)),
            start_date=start,
            total_weeks=total,
            periods=periods,
        )


def default_semester(today: date | None = None) -> Semester:
    today = today or date.today()
    start = monday_of(today)
    return Semester(name=academic_term_name(today), start_date=start)


@dataclass
class AppData:
    semester: Semester = field(default_factory=default_semester)
    courses: list[Course] = field(default_factory=list)
    theme: str = "light"
    show_weekend: bool = True
    demo: bool = False

    def __post_init__(self) -> None:
        if self.theme not in {"light", "dark"}:
            self.theme = "light"
        seen: set[str] = set()
        cleaned: list[Course] = []
        for course in self.courses:
            if course.id in seen:
                course.id = new_id()
            seen.add(course.id)
            cleaned.append(course)
        self.courses = cleaned[:MAX_COURSES]

    @classmethod
    def default(cls, today: date | None = None) -> "AppData":
        return cls(semester=default_semester(today), courses=[])

    def sorted_courses(self) -> list[Course]:
        return sorted(self.courses, key=lambda c: (c.day, c.start, c.end, c.name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": APP_SCHEMA_VERSION,
            "semester": self.semester.to_dict(),
            "courses": [course.to_dict() for course in self.sorted_courses()],
            "settings": {"theme": self.theme, "show_weekend": self.show_weekend},
            "demo": bool(self.demo),
        }

    @classmethod
    def from_dict(cls, raw: Any, today: date | None = None) -> "AppData":
        if not isinstance(raw, dict):
            raise DataError("数据格式不正确")
        semester = Semester.from_dict(raw.get("semester"), today)
        courses_raw = raw.get("courses", [])
        if not isinstance(courses_raw, list):
            raise DataError("课程列表格式不正确")
        courses: list[Course] = []
        for item in courses_raw[:MAX_COURSES]:
            try:
                courses.append(Course.from_dict(item))
            except (DataError, ValueError):
                # 单条课程坏掉不应让整张课表打不开。
                continue
        settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
        theme = str(settings.get("theme", raw.get("theme", "light")))
        if theme not in {"light", "dark"}:
            theme = "light"
        show_weekend = settings.get("show_weekend", True)
        if not isinstance(show_weekend, bool):
            show_weekend = True
        return cls(
            semester=semester,
            courses=courses,
            theme=theme,
            show_weekend=show_weekend,
            demo=bool(raw.get("demo", False)),
        )


# ---------------------------------------------------------------------------
# 课表查询
# ---------------------------------------------------------------------------


def courses_on(data: AppData, day: date) -> list[Course]:
    week = data.semester.week_on(day)
    if not 1 <= week <= data.semester.total_weeks:
        return []
    return sorted(
        [c for c in data.courses if c.day == day.weekday() and c.active(week)],
        key=lambda c: (c.start, c.end, c.name),
    )


def courses_for_week(data: AppData, week: int) -> list[Course]:
    if not 1 <= week <= data.semester.total_weeks:
        return []
    return sorted(
        [c for c in data.courses if c.active(week)],
        key=lambda c: (c.day, c.start, c.end, c.name),
    )


@dataclass(frozen=True)
class Moment:
    kind: str  # ongoing / upcoming / none / before / after
    course: Course | None = None
    start: datetime | None = None
    end: datetime | None = None
    day: date | None = None
    message: str = ""

    @property
    def is_today(self) -> bool:
        return self.day == date.today()


def moment_for(data: AppData, now: datetime | None = None) -> Moment:
    now = now or datetime.now()
    today = now.date()
    semester = data.semester
    current_week = semester.week_on(today)
    if current_week < 1:
        return Moment(
            "before",
            message=f"学期还没开始，第 1 周从 {semester.start_date.month} 月 {semester.start_date.day} 日开始",
        )
    if current_week > semester.total_weeks:
        return Moment("after", message="这学期已经结束啦")
    if not data.courses:
        return Moment("none", message="还没有课程，添加第一节课吧")

    # 今天从早到晚找：正在上的课优先，其次是下一节。
    for course in courses_on(data, today):
        start, end = semester.period_on(today, course.start), semester.period_on(today, course.end)
        if not start or not end:
            continue
        if end[1] < now:
            continue
        if start[0] <= now <= end[1]:
            return Moment("ongoing", course, start[0], end[1], today)
        if start[0] > now:
            return Moment("upcoming", course, start[0], end[1], today)

    # 今天没有更多课，往后找，最远找到学期结束。
    last_day = semester.start_date + timedelta(days=semester.total_weeks * 7 - 1)
    cursor = today + timedelta(days=1)
    while cursor <= last_day:
        for course in courses_on(data, cursor):
            start = semester.period_on(cursor, course.start)
            end = semester.period_on(cursor, course.end)
            if start and end:
                return Moment("upcoming", course, start[0], end[1], cursor)
        cursor += timedelta(days=1)

    return Moment("none", message="这学期没有更多课了")


def conflict_weeks(data: AppData, candidate: Course, exclude_id: str | None = None) -> list[tuple[Course, list[int]]]:
    result: list[tuple[Course, list[int]]] = []
    for existing in data.courses:
        if existing.id == exclude_id or existing.id == candidate.id:
            continue
        if existing.day != candidate.day:
            continue
        if existing.end < candidate.start or existing.start > candidate.end:
            continue
        overlap = week_plans_intersection(existing.weeks, candidate.weeks, data.semester.total_weeks)
        if overlap:
            result.append((existing, overlap))
    return result


def week_label(data: AppData, day: date | None = None) -> str:
    day = day or date.today()
    week = data.semester.week_on(day)
    if week < 1:
        return "未开学"
    if week > data.semester.total_weeks:
        return "已结课"
    return f"第 {week} 周"


def week_range_text(data: AppData, week: int) -> str:
    monday = data.semester.date_of(week, 0)
    sunday = data.semester.date_of(week, 6)
    if monday.month == sunday.month:
        return f"{monday.month}/{monday.day} – {sunday.day}"
    return f"{monday.month}/{monday.day} – {sunday.month}/{sunday.day}"


# ---------------------------------------------------------------------------
# 重叠布局
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockLayout:
    course: Course
    column: int
    columns: int


def overlap_layout(courses: Sequence[Course]) -> list[BlockLayout]:
    """把同一天重叠的课程并排放置。返回每门课所在的列和总列数。"""
    if not courses:
        return []
    ordered = sorted(courses, key=lambda c: (c.start, -c.end, c.name))
    # 先按时间接触关系分成互不重叠的组。
    groups: list[list[Course]] = []
    current: list[Course] = []
    group_end = 0
    for course in ordered:
        if not current or course.start <= group_end:
            current.append(course)
            group_end = max(group_end, course.end)
        else:
            groups.append(current)
            current = [course]
            group_end = course.end
    if current:
        groups.append(current)

    result: list[BlockLayout] = []
    for group in groups:
        lanes: list[int] = []
        assignments: list[tuple[Course, int]] = []
        for course in sorted(group, key=lambda c: (c.start, -c.end, c.name)):
            lane = next((i for i, end in enumerate(lanes) if course.start > end), None)
            if lane is None:
                lane = len(lanes)
                lanes.append(course.end)
            else:
                lanes[lane] = course.end
            assignments.append((course, lane))
        columns = max(1, len(lanes))
        result.extend(BlockLayout(c, lane, columns) for c, lane in assignments)
    return result


# ---------------------------------------------------------------------------
# 备份码
# ---------------------------------------------------------------------------


def encode_backup(data: AppData) -> str:
    payload = json.dumps(data.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:12]
    compressed = zlib.compress(payload, 9)
    body = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    return f"{BACKUP_PREFIX}.{digest}.{body}"


def decode_backup(token: str, today: date | None = None) -> AppData:
    if not isinstance(token, str):
        raise DataError("备份码格式不正确")
    cleaned = "".join(token.split())
    if not cleaned.startswith(BACKUP_PREFIX + "."):
        raise DataError("这不是简课的备份码")
    try:
        _, digest, body = cleaned.split(".", 2)
    except ValueError as exc:
        raise DataError("备份码不完整") from exc
    try:
        padding = "=" * (-len(body) % 4)
        compressed = base64.urlsafe_b64decode(body + padding)
        decompressor = zlib.decompressobj()
        payload = decompressor.decompress(compressed, MAX_BACKUP_BYTES + 1)
        if len(payload) > MAX_BACKUP_BYTES or decompressor.unconsumed_tail:
            raise DataError("备份数据太大了")
    except (ValueError, zlib.error, base64.binascii.Error) as exc:
        if isinstance(exc, DataError):
            raise
        raise DataError("备份码已损坏，请重新复制") from exc
    if hashlib.sha256(payload).hexdigest()[:12] != digest:
        raise DataError("备份码校验失败，可能复制时缺了一段")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("备份内容不是有效的课表数据") from exc
    return AppData.from_dict(raw, today)


# ---------------------------------------------------------------------------
# 示例课表
# ---------------------------------------------------------------------------


def demo_data(today: date | None = None) -> AppData:
    """生成一份覆盖一周的示例课表，让第一次打开的人马上看懂界面。"""
    today = today or date.today()
    data = AppData.default(today)
    data.semester.name = f"{today.year} 年 · 演示学期"
    data.demo = True
    plan_all = WeekPlan()
    specs = [
        ("高等数学", 0, 1, 2, "教三 201", "周老师", 0, "极限与连续，记得带习题册。"),
        ("大学英语", 1, 3, 4, "外语楼 305", "Lily", 3, ""),
        ("数据结构", 1, 5, 6, "计算机楼 402", "陈老师", 1, "本周讲二叉树遍历。"),
        ("计算机组成原理", 0, 5, 6, "计算机楼 401", "刘老师", 5, ""),
        ("体育 · 羽毛球", 2, 7, 8, "体育馆", "王教练", 2, "带球拍。"),
        ("马克思主义基本原理", 4, 1, 2, "人文楼 108", "赵老师", 6, ""),
        ("操作系统实验", 4, 5, 6, "实验楼 503", "陈老师", 4, "两人一组。"),
        ("设计思维选修", 3, 9, 10, "创新工坊", "孙老师", 7, ""),
        ("算法竞赛训练", 5, 3, 4, "计算机楼 402", "陈老师", 1, "每周六，自愿参加。"),
    ]
    for name, day, start, end, room, teacher, color, note in specs:
        data.courses.append(
            Course(
                name=name,
                day=day,
                start=start,
                end=end,
                weeks=plan_all,
                room=room,
                teacher=teacher,
                note=note,
                color=color,
            )
        )
    # 一门双周课，用来说明周次功能。
    data.courses.append(
        Course(
            name="大学物理（双周）",
            day=2,
            start=3,
            end=4,
            weeks=WeekPlan("even"),
            room="理科楼 210",
            teacher="钱老师",
            color=2,
        )
    )
    return data
