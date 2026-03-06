from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class QueueStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS queue_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              url TEXT NOT NULL UNIQUE,
              domain TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              retry_count INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '',
              started_at TEXT,
              finished_at TEXT,
              updated_at TEXT NOT NULL,
              discovery_quality_score INTEGER NOT NULL DEFAULT 0,
              is_healthy INTEGER NOT NULL DEFAULT 0,
              quality_flags TEXT NOT NULL DEFAULT '',
              platform_detected TEXT NOT NULL DEFAULT 'unknown',
              result_json TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_items(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_domain ON queue_items(domain)")
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM queue_items")
        self.conn.commit()

    def upsert_targets(self, records: list[dict[str, Any]]) -> None:
        now = utc_now()
        current_urls = {str(r["url"]) for r in records}
        payload = [
            (
                r["url"],
                r["domain"],
                int(r.get("discovery_quality_score", 0)),
                1 if bool(r.get("is_healthy", False)) else 0,
                str(r.get("quality_flags", "")),
                str(r.get("platform_detected", "unknown")),
                now,
            )
            for r in records
        ]
        self.conn.executemany(
            """
            INSERT INTO queue_items (
              url, domain, discovery_quality_score, is_healthy, quality_flags, platform_detected, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              domain=excluded.domain,
              discovery_quality_score=excluded.discovery_quality_score,
              is_healthy=excluded.is_healthy,
              quality_flags=excluded.quality_flags,
              platform_detected=excluded.platform_detected,
              updated_at=excluded.updated_at
            """,
            payload,
        )
        if current_urls:
            placeholders = ",".join("?" for _ in current_urls)
            self.conn.execute(f"DELETE FROM queue_items WHERE url NOT IN ({placeholders})", tuple(current_urls))
        else:
            self.conn.execute("DELETE FROM queue_items")
        self.conn.commit()

    def reset_stale_processing(self) -> None:
        self.conn.execute(
            """
            UPDATE queue_items
            SET status='pending', updated_at=?
            WHERE status='processing'
            """,
            (utc_now(),),
        )
        self.conn.commit()

    def claim_batch(self, batch_size: int, retry_budget: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        rows = cur.execute(
            """
            SELECT id, url, domain, retry_count, discovery_quality_score, is_healthy, quality_flags, platform_detected
            FROM queue_items
            WHERE status='pending' AND retry_count < ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (max(1, retry_budget), max(1, batch_size)),
        ).fetchall()
        if not rows:
            return []

        ids = [r["id"] for r in rows]
        now = utc_now()
        cur.executemany(
            """
            UPDATE queue_items
            SET status='processing', started_at=COALESCE(started_at, ?), updated_at=?, last_error=''
            WHERE id=?
            """,
            [(now, now, i) for i in ids],
        )
        self.conn.commit()
        return [dict(r) for r in rows]

    def _domain_retry_total(self, domain: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(retry_count), 0) AS total_retry FROM queue_items WHERE domain=?",
            (domain,),
        ).fetchone()
        return int(row["total_retry"]) if row else 0

    def mark_completed(self, item_id: int, row: dict[str, Any]) -> None:
        now = utc_now()
        self.conn.execute(
            """
            UPDATE queue_items
            SET status='completed',
                finished_at=?,
                updated_at=?,
                result_json=?,
                last_error=''
            WHERE id=?
            """,
            (now, now, json.dumps(row, ensure_ascii=False), item_id),
        )
        self.conn.commit()

    def mark_failed(
        self,
        item_id: int,
        domain: str,
        error: str,
        retry_budget_by_domain: int,
        row: dict[str, Any] | None = None,
    ) -> bool:
        current_domain_retries = self._domain_retry_total(domain)
        next_domain_retry = current_domain_retries + 1
        now = utc_now()

        final_fail = next_domain_retry >= max(1, retry_budget_by_domain)
        if final_fail:
            self.conn.execute(
                """
                UPDATE queue_items
                SET status='failed',
                    retry_count=retry_count+1,
                    finished_at=?,
                    updated_at=?,
                    last_error=?,
                    result_json=COALESCE(?, result_json)
                WHERE id=?
                """,
                (now, now, (error or "")[:500], json.dumps(row, ensure_ascii=False) if row else None, item_id),
            )
        else:
            self.conn.execute(
                """
                UPDATE queue_items
                SET status='pending',
                    retry_count=retry_count+1,
                    updated_at=?,
                    last_error=?
                WHERE id=?
                """,
                (now, (error or "")[:500], item_id),
            )
        self.conn.commit()
        return final_fail

    def fetch_final_rows(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT result_json
            FROM queue_items
            WHERE status IN ('completed', 'failed') AND result_json IS NOT NULL AND result_json != ''
            ORDER BY id ASC
            """
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(row["result_json"])
                if isinstance(parsed, dict):
                    out.append(parsed)
            except Exception:
                continue
        return out

    def counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT status, COUNT(*) AS c
            FROM queue_items
            GROUP BY status
            """
        ).fetchall()
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        for row in rows:
            status = str(row["status"])
            if status in counts:
                counts[status] = int(row["c"])
        counts["total"] = counts["pending"] + counts["processing"] + counts["completed"] + counts["failed"]
        return counts

    def fail_reasons_distribution(self) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT last_error, COUNT(*) AS c
            FROM queue_items
            WHERE status='failed'
            GROUP BY last_error
            ORDER BY c DESC
            """
        ).fetchall()
        out: dict[str, int] = {}
        for row in rows:
            key = str(row["last_error"] or "unknown")
            out[key] = int(row["c"])
        return out

    def close(self) -> None:
        self.conn.close()
