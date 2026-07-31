"""
定时调度 — 2.0功能表 ③ 模块。

双模式：
1. 主模式（常驻后台）：APScheduler 在程序运行时按周期触发清理。
2. 兜底模式（启动补偿）：程序启动时检查是否有"到期未执行"的条目，
   返回列表由 GUI 弹提示框，用户确认后清理。

TODO(Claude Code): 实现。注意：
- APScheduler 的 job 需要按条目 schedule 动态注册/更新
- next_due_time 持久化在数据库，供启动补偿比对
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .database import Database
from .models import VirtualEntry

# 条目 schedule.kind → job 的 id 前缀
_JOB_ID_PREFIX = "entry_"


@dataclass
class DueEntry:
    """到期未执行的条目（启动补偿用）。"""

    entry: VirtualEntry
    overdue_seconds: int = 0      # 已过期时长（秒）


class CleanScheduler:
    """调度器：后台常驻触发 + 启动补偿检查。"""

    def __init__(self, db: Database, on_clean: Callable[[VirtualEntry], None] | None = None):
        self.db = db
        self.on_clean = on_clean          # 到点回调（由 GUI/入口注入）
        self._scheduler: BackgroundScheduler | None = None

    # ---------- 生命周期 ----------

    def start(self) -> None:
        """启动后台调度器。"""
        if self._scheduler and self._scheduler.running:
            return
        self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.refresh_jobs()
        self._scheduler.start()

    def stop(self) -> None:
        """停止后台调度器。"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    # ---------- Job 管理 ----------

    def refresh_jobs(self) -> None:
        """条目增删改后重新注册所有 job。"""
        if not self._scheduler:
            return
        # 清掉旧的条目 job
        for job in self._scheduler.get_jobs():
            if job.id.startswith(_JOB_ID_PREFIX):
                job.remove()
        for entry in self.db.list_entries():
            if entry.enabled:
                self._register_entry_job(entry)

    def _register_entry_job(self, entry: VirtualEntry) -> None:
        """为单个条目注册定时任务（按 Schedule 类型）。"""
        if not self._scheduler:
            return

        sched = entry.schedule
        job_id = _JOB_ID_PREFIX + entry.entry_id

        # 回调：先更新 next_due_time 再执行清理
        def _job():
            self._update_next_due(entry)
            if self.on_clean:
                self.on_clean(entry)

        try:
            if sched.kind == "daily":
                hh, mm = _parse_hhmm(sched.time)
                trigger = CronTrigger(hour=hh, minute=mm)
            elif sched.kind == "interval":
                days = max(1, sched.interval_days)
                trigger = IntervalTrigger(days=days)
            elif sched.kind == "weekly":
                hh, mm = _parse_hhmm(sched.time)
                trigger = CronTrigger(day_of_week=sched.weekday, hour=hh, minute=mm)
            elif sched.kind == "once" and sched.once_date:
                hh, mm = _parse_hhmm(sched.time)
                dt = datetime.fromisoformat(sched.once_date).replace(hour=hh, minute=mm)
                trigger = DateTrigger(run_date=dt)
            else:
                return

            self._scheduler.add_job(_job, trigger, id=job_id, replace_existing=True)
        except Exception:
            return

    def _update_next_due(self, entry: VirtualEntry) -> None:
        """job 触发时刷新 next_due_time 并持久化。"""
        entry.next_due_time = self.compute_next_due(entry, datetime.now())
        self.db.update_entry(entry)

    # ---------- 启动补偿 ----------

    def check_due_entries(self, now: datetime | None = None) -> List[DueEntry]:
        """启动时检查到期未执行的条目（兜底模式）。"""
        now = now or datetime.now()
        due: List[DueEntry] = []
        for entry in self.db.list_entries():
            if not entry.enabled or not entry.next_due_time:
                continue
            if entry.next_due_time < now:
                overdue = int((now - entry.next_due_time).total_seconds())
                due.append(DueEntry(entry=entry, overdue_seconds=overdue))
        return due

    def compute_next_due(self, entry: VirtualEntry, now: datetime | None = None) -> Optional[datetime]:
        """根据条目的 Schedule 计算下次到期时间（once 已过期返回 None）。"""
        now = now or datetime.now()
        sched = entry.schedule

        if sched.kind == "daily":
            hh, mm = _parse_hhmm(sched.time)
            next_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time

        if sched.kind == "interval":
            return now + timedelta(days=max(1, sched.interval_days))

        if sched.kind == "weekly":
            hh, mm = _parse_hhmm(sched.time)
            days_ahead = (sched.weekday - now.weekday()) % 7
            candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            candidate += timedelta(days=days_ahead)
            if candidate <= now:
                candidate += timedelta(days=7)
            return candidate

        if sched.kind == "once" and sched.once_date:
            try:
                hh, mm = _parse_hhmm(sched.time)
                dt = datetime.fromisoformat(sched.once_date).replace(
                    hour=hh, minute=mm, second=0, microsecond=0
                )
                # 已过触发点 → 不再有"下次到期"，避免启动补偿反复提示
                return dt if dt > now else None
            except ValueError:
                return now + timedelta(days=30)

        return now + timedelta(days=1)


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """解析 "HH:MM" → (hour, minute)，非法时默认 20:00。"""
    try:
        hh, mm = time_str.split(":")
        return max(0, min(23, int(hh))), max(0, min(59, int(mm)))
    except Exception:
        return 20, 0
