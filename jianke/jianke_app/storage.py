"""本地 JSON 存储。

课表只保存在应用私有目录里，不联网、不需要账号。
写入采用临时文件 + 原子替换，避免写到一半被系统杀掉导致课表损坏。
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .core import AppData, DataError


@dataclass
class LoadResult:
    data: AppData
    warning: str = ""
    recovered_path: Path | None = None


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self, today: date | None = None) -> LoadResult:
        today = today or date.today()
        if not self.path.exists():
            return LoadResult(AppData.default(today))
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = AppData.from_dict(json.loads(raw), today)
            return LoadResult(data)
        except (OSError, ValueError, DataError):
            # 坏文件先留档，再用空课表启动，至少不会一打开就闪退。
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            recovered = self.path.with_name(f"{self.path.stem}.broken-{stamp}.json")
            try:
                shutil.copy2(self.path, recovered)
            except OSError:
                recovered = None
            return LoadResult(
                AppData.default(today),
                warning="本地课表文件读取失败，已为你保留原文件并新建了空课表。",
                recovered_path=recovered,
            )

    def save(self, data: AppData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        payload = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def export_json(self, data: AppData, folder: str | Path | None = None) -> Path:
        """在桌面端/调试时导出一份可读 JSON（手机端主要用备份码）。"""
        target_dir = Path(folder) if folder else self.path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = target_dir / f"jianke-backup-{stamp}.json"
        target.write_text(
            json.dumps(data.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target
