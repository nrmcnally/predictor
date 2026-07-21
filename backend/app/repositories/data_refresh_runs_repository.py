from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from app.db import connection, schema
from app.db.frame_contract import normalize_frame


COLUMNS_SPEC = schema.DATA_REFRESH_RUN_COLUMNS
COLUMN_NAMES = [name for name, _ in COLUMNS_SPEC]


def _stage(report: dict[str, Any], name: str) -> dict[str, Any]:
    return next(
        (stage for stage in report.get("stages", []) if stage.get("name") == name),
        {},
    )


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row_from_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    odds_stage = _stage(report, "Refresh future fight odds")
    odds = odds_stage.get("details") or {}
    settlement = (_stage(report, "Settle duration predictions").get("details") or {})
    finished_at = str(report.get("finished_at") or "")
    started_at = str(report.get("started_at") or "")

    return {
        "run_id": f"{finished_at}|{started_at}",
        "update_type": str(report.get("update_type") or "incremental"),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": report.get("duration_seconds"),
        "success": bool(summary.get("success")),
        "failed_stages_json": json.dumps(summary.get("failed_stages") or []),
        "degraded_stages_json": json.dumps(summary.get("degraded_stages") or []),
        "completed_events_rows": summary.get("completed_events_rows"),
        "event_fights_rows": summary.get("event_fights_rows"),
        "upcoming_events_rows": summary.get("upcoming_events_rows"),
        "upcoming_fights_rows": summary.get("upcoming_fights_rows"),
        "saved_card_predictions_rows": summary.get("saved_card_predictions_rows"),
        "saved_duration_predictions_rows": summary.get(
            "saved_duration_predictions_rows"
        ),
        "settled_duration_predictions": settlement.get("scored_predictions"),
        "pending_duration_predictions": settlement.get("pending_predictions"),
        "odds_stage_status": str(odds_stage.get("status") or "not_run"),
        "odds_available": bool(odds.get("available")),
        "odds_error_code": str(odds.get("error_code") or ""),
        "odds_message": str(odds.get("message") or ""),
        "provider_requests_remaining": _optional_int(
            odds.get("provider_requests_remaining")
        ),
        "odds_matched_fights": odds.get("matched_fights"),
        "odds_unmatched_fights": odds.get("unmatched_fights"),
        "totals_quotes_received": odds.get("totals_quotes_received"),
        "totals_snapshots_added": odds.get("totals_snapshots_added"),
        "totals_snapshots_total": odds.get("totals_snapshots_total"),
        "totals_fights_matched": odds.get("totals_fights_matched"),
        "totals_lines_json": json.dumps(odds.get("totals_lines_received") or []),
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }


def record_report(report: dict[str, Any]) -> None:
    """Persist one secret-free refresh heartbeat; duplicate runs are idempotent."""
    row = _row_from_report(report)
    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))
    values = [row.get(name) for name in COLUMN_NAMES]

    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute(
            f"INSERT OR REPLACE INTO data_refresh_runs ({columns}) "
            f"VALUES ({placeholders})",
            values,
        )


def read_all_df() -> pd.DataFrame:
    columns = ", ".join(COLUMN_NAMES)
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            f"SELECT {columns} FROM data_refresh_runs "
            "ORDER BY finished_at DESC, run_id DESC"
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=COLUMN_NAMES)
    frame = pd.DataFrame([dict(row) for row in rows], columns=COLUMN_NAMES)
    return normalize_frame(frame, COLUMNS_SPEC)


def latest() -> dict[str, Any] | None:
    frame = read_all_df()
    if frame.empty:
        return None
    row = frame.iloc[0].to_dict()
    for name in ("failed_stages_json", "degraded_stages_json", "totals_lines_json"):
        try:
            row[name.removesuffix("_json")] = json.loads(str(row.get(name) or "[]"))
        except json.JSONDecodeError:
            row[name.removesuffix("_json")] = []
    return row


def count() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(conn.execute("SELECT COUNT(*) FROM data_refresh_runs").fetchone()[0])
