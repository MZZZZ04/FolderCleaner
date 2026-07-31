"""
SQLite 数据层 — 配置 / 虚拟条目 / 回收站记录 / 清理日志。

数据库位置：应用数据目录下 clean_app.db（详见 config.py 的 DATA_DIR）。

TODO(Claude Code): 实现以下 CRUD 方法。表结构建议：
    - entries(id, name, physical_path, rule_json, schedule_json, enabled, last_clean_time, next_due_time)
    - recycle_items(id, file_name, original_path, recycle_path, size_bytes, moved_at)
    - clean_logs(id, time, entry_name, trigger, file_count, total_bytes, result)
    - settings(key, value)  -- 全局设置（回收站保留时间等）
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from .models import CleanLog, CleanRule, RecycleItem, Schedule, VirtualEntry


def _serialize_dt(dt: Optional[datetime]) -> Optional[str]:
    """datetime → ISO 字符串（None 保持 None）。"""
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """ISO 字符串 → datetime（空/None 返回 None）。"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class Database:
    """SQLite 封装。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_schema()

    # ---------- 连接管理 ----------

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """获取连接（自动提交/回滚 + 关闭）。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """创建表结构（若不存在）。"""
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    physical_path TEXT NOT NULL,
                    rule_json TEXT NOT NULL DEFAULT '{}',
                    schedule_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_clean_time TEXT,
                    next_due_time TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recycle_items (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    recycle_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    moved_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clean_logs (
                    id TEXT PRIMARY KEY,
                    time TEXT NOT NULL,
                    entry_name TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    total_bytes INTEGER NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recycle_moved_at ON recycle_items(moved_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON clean_logs(time)")

    # ---------- 虚拟条目 ----------

    @staticmethod
    def _entry_from_row(row: sqlite3.Row) -> VirtualEntry:
        return VirtualEntry(
            entry_id=row["id"],
            name=row["name"],
            physical_path=row["physical_path"],
            rule=CleanRule(**json.loads(row["rule_json"] or "{}")),
            schedule=Schedule(**json.loads(row["schedule_json"] or "{}")),
            enabled=bool(row["enabled"]),
            last_clean_time=_parse_dt(row["last_clean_time"]),
            next_due_time=_parse_dt(row["next_due_time"]),
        )

    @staticmethod
    def _entry_to_params(entry: VirtualEntry) -> tuple:
        return (
            entry.entry_id or uuid.uuid4().hex,
            entry.name,
            entry.physical_path,
            json.dumps(entry.rule.__dict__, ensure_ascii=False, default=str),
            json.dumps(entry.schedule.__dict__, ensure_ascii=False, default=str),
            int(entry.enabled),
            _serialize_dt(entry.last_clean_time),
            _serialize_dt(entry.next_due_time),
        )

    def list_entries(self) -> List[VirtualEntry]:
        """获取全部虚拟条目。"""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM entries ORDER BY name").fetchall()
        return [self._entry_from_row(r) for r in rows]

    def get_entry(self, entry_id: str) -> Optional[VirtualEntry]:
        """按 ID 获取条目。"""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        return self._entry_from_row(row) if row else None

    def add_entry(self, entry: VirtualEntry) -> str:
        """新增条目，返回 entry_id。"""
        params = self._entry_to_params(entry)
        if not entry.entry_id:
            entry.entry_id = params[0]
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO entries (id, name, physical_path, rule_json, schedule_json,
                                     enabled, last_clean_time, next_due_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        return entry.entry_id

    def update_entry(self, entry: VirtualEntry) -> None:
        """更新条目。"""
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE entries SET name=?, physical_path=?, rule_json=?, schedule_json=?,
                                   enabled=?, last_clean_time=?, next_due_time=?
                WHERE id=?
                """,
                (
                    entry.name,
                    entry.physical_path,
                    json.dumps(entry.rule.__dict__, ensure_ascii=False, default=str),
                    json.dumps(entry.schedule.__dict__, ensure_ascii=False, default=str),
                    int(entry.enabled),
                    _serialize_dt(entry.last_clean_time),
                    _serialize_dt(entry.next_due_time),
                    entry.entry_id,
                ),
            )

    def delete_entry(self, entry_id: str) -> None:
        """删除条目（仅移除配置，不动物理路径文件）。"""
        with self._conn() as conn:
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    # ---------- 程序回收站 ----------

    @staticmethod
    def _recycle_from_row(row: sqlite3.Row) -> RecycleItem:
        return RecycleItem(
            item_id=row["id"],
            file_name=row["file_name"],
            original_path=row["original_path"],
            recycle_path=row["recycle_path"],
            size_bytes=row["size_bytes"],
            moved_at=_parse_dt(row["moved_at"]) or datetime.now(),
        )

    def list_recycle_items(self) -> List[RecycleItem]:
        """获取回收站全部条目。"""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM recycle_items ORDER BY moved_at DESC").fetchall()
        return [self._recycle_from_row(r) for r in rows]

    def add_recycle_item(self, item: RecycleItem) -> str:
        """新增回收站条目。"""
        item_id = item.item_id or uuid.uuid4().hex
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO recycle_items (id, file_name, original_path, recycle_path,
                                           size_bytes, moved_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    item.file_name,
                    item.original_path,
                    item.recycle_path,
                    item.size_bytes,
                    _serialize_dt(item.moved_at) or datetime.now().isoformat(),
                ),
            )
        return item_id

    def remove_recycle_item(self, item_id: str) -> None:
        """移除回收站条目（恢复或删除后调用）。"""
        with self._conn() as conn:
            conn.execute("DELETE FROM recycle_items WHERE id = ?", (item_id,))

    def clear_recycle(self) -> int:
        """清空回收站记录，返回清除条数。"""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM recycle_items")
        return cursor.rowcount

    # ---------- 清理日志 ----------

    def add_log(self, log: CleanLog) -> str:
        """新增日志。"""
        log_id = log.log_id or uuid.uuid4().hex
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO clean_logs (id, time, entry_name, trigger, file_count,
                                        total_bytes, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    log.time.isoformat() if log.time else datetime.now().isoformat(),
                    log.entry_name,
                    log.trigger,
                    log.file_count,
                    log.total_bytes,
                    log.result,
                ),
            )
        return log_id

    def list_logs(self, limit: int = 100) -> List[CleanLog]:
        """获取最近日志。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM clean_logs ORDER BY time DESC LIMIT ?", (limit,)
            ).fetchall()
        logs = []
        for r in rows:
            logs.append(
                CleanLog(
                    log_id=r["id"],
                    time=_parse_dt(r["time"]) or datetime.now(),
                    entry_name=r["entry_name"],
                    trigger=r["trigger"],
                    file_count=r["file_count"],
                    total_bytes=r["total_bytes"],
                    result=r["result"],
                )
            )
        return logs

    # ---------- 全局设置 ----------

    def get_setting(self, key: str, default: str = "") -> str:
        """读取全局设置。"""
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """写入全局设置。"""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
