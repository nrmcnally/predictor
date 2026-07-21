from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.repositories import (
    data_refresh_runs_repository,
    future_cards_repository,
    future_fight_odds_repository,
    saved_predictions_repository,
    totals_odds_snapshots_repository,
)
from app.services.duration_evaluation_service import build_duration_evaluation


REFRESH_STALE_AFTER_HOURS = 36.0
TOTALS_STALE_AFTER_HOURS = 36.0


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_int(value: Any) -> int | None:
    number = _optional_float(value)
    return None if number is None else int(number)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    number = _optional_float(value)
    return bool(number) if number is not None else bool(value)


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _age_hours(value: Any, now: datetime) -> float | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    reference = now
    if parsed.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    elif parsed.tzinfo is not None and reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return max(0.0, (reference - parsed).total_seconds() / 3600.0)


def _utc_sort_value(value: datetime) -> datetime:
    """Normalize mixed legacy-naive and offset-aware timestamps for ordering."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _coverage(covered: int, total: int) -> dict[str, Any]:
    ratio = covered / total if total > 0 else 0.0
    return {
        "covered": int(covered),
        "total": int(total),
        "ratio": float(ratio),
        "percentage": f"{ratio * 100:.1f}%",
    }


def build_data_operations_health(
    *,
    now: datetime | None = None,
    latest_refresh: dict[str, Any] | None = None,
    upcoming_fights_df: pd.DataFrame | None = None,
    current_odds_df: pd.DataFrame | None = None,
    totals_snapshots_df: pd.DataFrame | None = None,
    saved_predictions_df: pd.DataFrame | None = None,
    duration_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the secret-free operational health contract used by Data Ops."""
    current_time = now or datetime.now()
    refresh = latest_refresh if latest_refresh is not None else data_refresh_runs_repository.latest()
    upcoming = (
        future_cards_repository.read_upcoming_fights_df()
        if upcoming_fights_df is None
        else upcoming_fights_df
    )
    current_odds = (
        future_fight_odds_repository.read_all_df()
        if current_odds_df is None
        else current_odds_df
    )
    totals = (
        totals_odds_snapshots_repository.read_all_df()
        if totals_snapshots_df is None
        else totals_snapshots_df
    )
    saved = (
        saved_predictions_repository.read_all_df()
        if saved_predictions_df is None
        else saved_predictions_df
    )
    duration = duration_evaluation or build_duration_evaluation(
        saved_predictions_df=saved
    )

    upcoming_count = int(len(upcoming))
    h2h_count = 0
    totals_current_count = 0
    low_confidence_count = 0
    if not current_odds.empty:
        if "odds_available" in current_odds.columns:
            h2h_count = int(current_odds["odds_available"].map(_truthy).sum())
        if "rounds_line" in current_odds.columns:
            totals_current_count = int(
                pd.to_numeric(current_odds["rounds_line"], errors="coerce").notna().sum()
            )
        if "odds_match_low_confidence" in current_odds.columns:
            low_confidence_count = int(
                current_odds["odds_match_low_confidence"].map(_truthy).sum()
            )

    latest_capture = None
    snapshot_age = None
    snapshot_fights = snapshot_books = 0
    snapshot_lines: list[float] = []
    if not totals.empty:
        if "captured_at" in totals.columns:
            timestamps = [
                _parse_timestamp(value)
                for value in totals["captured_at"].tolist()
            ]
            timestamps = [value for value in timestamps if value is not None]
            if timestamps:
                latest_timestamp = max(timestamps, key=_utc_sort_value)
                latest_capture = latest_timestamp.isoformat()
                snapshot_age = _age_hours(latest_timestamp.isoformat(), current_time)
        if "fight_url" in totals.columns:
            snapshot_fights = int(totals["fight_url"].replace("", pd.NA).dropna().nunique())
        if "bookmaker_key" in totals.columns:
            snapshot_books = int(
                totals["bookmaker_key"].replace("", pd.NA).dropna().nunique()
            )
        if "rounds_line" in totals.columns:
            values = pd.to_numeric(totals["rounds_line"], errors="coerce").dropna()
            snapshot_lines = sorted(float(value) for value in values.unique())

    prospective = duration.get("prospective") or {}
    refresh_age = _age_hours(refresh.get("finished_at"), current_time) if refresh else None
    degraded_stages = list((refresh or {}).get("degraded_stages") or [])
    failed_stages = list((refresh or {}).get("failed_stages") or [])
    requests_remaining = _optional_int((refresh or {}).get("provider_requests_remaining"))

    alerts: list[dict[str, str]] = []
    if not refresh:
        alerts.append(
            {
                "severity": "critical",
                "code": "no_refresh_heartbeat",
                "message": "No persisted incremental-refresh heartbeat is available yet.",
            }
        )
    elif not _truthy(refresh.get("success")):
        alerts.append(
            {
                "severity": "critical",
                "code": "latest_refresh_failed",
                "message": "The latest incremental refresh failed.",
            }
        )
    elif refresh_age is not None and refresh_age > REFRESH_STALE_AFTER_HOURS:
        alerts.append(
            {
                "severity": "critical",
                "code": "refresh_stale",
                "message": (
                    f"The latest successful refresh is {refresh_age:.1f} hours old "
                    f"(limit {REFRESH_STALE_AFTER_HOURS:.0f}h)."
                ),
            }
        )

    if degraded_stages:
        alerts.append(
            {
                "severity": "warning",
                "code": "degraded_stages",
                "message": "Completed with warnings: " + ", ".join(degraded_stages) + ".",
            }
        )
    if failed_stages:
        alerts.append(
            {
                "severity": "critical",
                "code": "failed_stages",
                "message": "Failed stages: " + ", ".join(failed_stages) + ".",
            }
        )
    odds_error_code = str((refresh or {}).get("odds_error_code") or "")
    if odds_error_code:
        alerts.append(
            {
                "severity": "warning",
                "code": odds_error_code,
                "message": str((refresh or {}).get("odds_message") or "Odds refresh needs attention."),
            }
        )
    elif refresh and not _truthy(refresh.get("odds_available")):
        alerts.append(
            {
                "severity": "warning",
                "code": "odds_refresh_unavailable",
                "message": str(
                    refresh.get("odds_message")
                    or "The latest run did not produce a verified odds refresh."
                ),
            }
        )
    if low_confidence_count:
        alerts.append(
            {
                "severity": "warning",
                "code": "low_confidence_odds_matches",
                "message": f"{low_confidence_count} current odds matches need identity review.",
            }
        )
    if requests_remaining is not None and requests_remaining <= 25:
        alerts.append(
            {
                "severity": "warning",
                "code": "provider_quota_low",
                "message": f"Odds provider quota is low ({requests_remaining} requests remaining).",
            }
        )
    if (
        snapshot_age is not None
        and upcoming_count > 0
        and snapshot_age > TOTALS_STALE_AFTER_HOURS
    ):
        alerts.append(
            {
                "severity": "warning",
                "code": "totals_snapshots_stale",
                "message": f"The newest totals quote is {snapshot_age:.1f} hours old.",
            }
        )

    severities = {alert["severity"] for alert in alerts}
    if "critical" in severities:
        status = "failed" if refresh and not _truthy(refresh.get("success")) else "stale"
    elif "warning" in severities:
        status = "attention"
    else:
        status = "healthy"

    return {
        "status": status,
        "generated_at": current_time.isoformat(timespec="seconds"),
        "thresholds": {
            "refresh_stale_after_hours": REFRESH_STALE_AFTER_HOURS,
            "totals_stale_after_hours": TOTALS_STALE_AFTER_HOURS,
        },
        "refresh": {
            "available": bool(refresh),
            "started_at": (refresh or {}).get("started_at"),
            "finished_at": (refresh or {}).get("finished_at"),
            "age_hours": refresh_age,
            "success": _truthy((refresh or {}).get("success")) if refresh else None,
            "duration_seconds": _optional_float((refresh or {}).get("duration_seconds")),
            "failed_stages": failed_stages,
            "degraded_stages": degraded_stages,
        },
        "odds": {
            "refresh_available": _truthy((refresh or {}).get("odds_available")),
            "error_code": odds_error_code,
            "message": str((refresh or {}).get("odds_message") or ""),
            "provider_requests_remaining": requests_remaining,
            "h2h_coverage": _coverage(h2h_count, upcoming_count),
            "totals_coverage": _coverage(totals_current_count, upcoming_count),
            "low_confidence_matches": low_confidence_count,
        },
        "totals_history": {
            "snapshot_rows": int(len(totals)),
            "unique_fights": snapshot_fights,
            "bookmakers": snapshot_books,
            "lines": snapshot_lines,
            "latest_captured_at": latest_capture,
            "age_hours": snapshot_age,
        },
        "duration_evaluation": {
            "status": prospective.get("status", "not_collecting"),
            "saved_predictions": int(prospective.get("saved_predictions", 0)),
            "scored_predictions": int(prospective.get("scored_predictions", 0)),
            "pending_predictions": int(prospective.get("pending_predictions", 0)),
            "invalid_predictions": int(prospective.get("invalid_predictions", 0)),
        },
        "alerts": alerts,
    }
