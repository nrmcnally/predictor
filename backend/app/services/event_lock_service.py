from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from app.repositories import (
    event_controls_repository,
    future_cards_repository,
    future_fight_odds_repository,
)
from app.utils.bool_parsing import parse_bool

LOCK_MODES = {"auto", "force_open", "force_locked"}
DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return " ".join(str(value).split())


def normalize_url(value: Any) -> str:
    normalized = clean_text(value)
    normalized = normalized.replace("https://www.", "https://")
    normalized = normalized.replace("http://www.", "http://")
    return normalized.rstrip("/")


def iso_utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_datetime_utc(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_datetime_utc(value: Any) -> str | None:
    parsed = parse_datetime_utc(value)
    return iso_utc(parsed) if parsed is not None else None


def parse_event_date(event_date: str | None) -> date | None:
    if not event_date:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(event_date.strip(), fmt).date()
        except ValueError:
            continue
    return None


def date_fallback_locked(event_date: str | None, today: date | None = None) -> bool:
    parsed = parse_event_date(event_date)
    if parsed is None:
        return False
    return (today or date.today()) >= parsed


def _event_from_db(event_id: Any) -> dict[str, Any] | None:
    events_df = future_cards_repository.read_upcoming_events_df()
    if events_df.empty:
        return None
    matches = events_df[events_df["event_id"].astype(str) == str(event_id)]
    if matches.empty:
        return None
    return dict(matches.iloc[0])


def _fight_urls_for_event(event_id: Any) -> list[str]:
    fights_df = future_cards_repository.read_upcoming_fights_df()
    if fights_df.empty:
        return []
    matches = fights_df[fights_df["event_id"].astype(str) == str(event_id)]
    return [normalize_url(value) for value in matches.get("fight_url", []) if normalize_url(value)]


def _odds_suggestion(event_id: Any, fight_urls: list[str] | None = None) -> dict[str, Any]:
    urls = set(fight_urls or _fight_urls_for_event(event_id))
    if not urls:
        return {
            "suggested_start_at_utc": None,
            "suggested_source": "",
            "suggested_confidence": "missing",
            "suggested_match_count": 0,
            "suggested_low_confidence_count": 0,
        }

    odds_df = future_fight_odds_repository.read_all_df()
    if odds_df.empty:
        return {
            "suggested_start_at_utc": None,
            "suggested_source": "",
            "suggested_confidence": "missing",
            "suggested_match_count": 0,
            "suggested_low_confidence_count": 0,
        }

    candidates: list[tuple[datetime, bool]] = []
    for _, row in odds_df.iterrows():
        if normalize_url(row.get("fight_url")) not in urls:
            continue
        parsed = parse_datetime_utc(row.get("odds_commence_time"))
        if parsed is None:
            continue
        candidates.append((parsed, bool(parse_bool(row.get("odds_match_low_confidence")))))

    if not candidates:
        return {
            "suggested_start_at_utc": None,
            "suggested_source": "",
            "suggested_confidence": "missing",
            "suggested_match_count": 0,
            "suggested_low_confidence_count": 0,
        }

    candidates.sort(key=lambda item: item[0])
    low_confidence_count = sum(1 for _, low in candidates if low)
    match_count = len(candidates)

    if match_count >= 3 and low_confidence_count == 0:
        confidence = "high"
    elif match_count >= 2 and low_confidence_count <= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "suggested_start_at_utc": iso_utc(candidates[0][0]),
        "suggested_source": "odds_commence_time",
        "suggested_confidence": confidence,
        "suggested_match_count": match_count,
        "suggested_low_confidence_count": low_confidence_count,
    }


def build_event_lock_state(
    event: dict[str, Any],
    *,
    fight_urls: list[str] | None = None,
    now: datetime | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    event_id = clean_text(event.get("event_id"))
    control = event_controls_repository.get(event_id) if event_id else None
    suggestion = _odds_suggestion(event_id, fight_urls)
    lock_mode = clean_text(control.get("lock_mode") if control else "auto") or "auto"
    if lock_mode not in LOCK_MODES:
        lock_mode = "auto"

    manual_start = normalize_datetime_utc(control.get("event_start_at_utc")) if control else None
    suggested_start = suggestion["suggested_start_at_utc"]
    effective_start = manual_start or suggested_start
    effective_source = "manual" if manual_start else ("odds" if suggested_start else "date_fallback")

    current_time = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    parsed_start = parse_datetime_utc(effective_start)
    fallback_locked = date_fallback_locked(clean_text(event.get("event_date")), today=today)

    if lock_mode == "force_open":
        locked = False
        reason = "force_open"
    elif lock_mode == "force_locked":
        locked = True
        reason = "force_locked"
    elif parsed_start is not None:
        locked = current_time >= parsed_start
        reason = "event_start_at_utc"
    else:
        locked = fallback_locked
        reason = "date_fallback"

    return {
        "event_id": event_id,
        "locked": bool(locked),
        "lock_mode": lock_mode,
        "lock_reason": reason,
        "effective_start_at_utc": effective_start,
        "effective_source": effective_source,
        "event_start_at_utc": manual_start,
        "suggested_start_at_utc": suggested_start,
        "suggested_source": suggestion["suggested_source"],
        "suggested_confidence": suggestion["suggested_confidence"],
        "suggested_match_count": suggestion["suggested_match_count"],
        "suggested_low_confidence_count": suggestion["suggested_low_confidence_count"],
        "date_fallback_locked": fallback_locked,
        "updated_at": clean_text(control.get("updated_at")) if control else "",
    }


def get_event_control_payload(event_id: Any) -> dict[str, Any]:
    event = _event_from_db(event_id)
    if event is None:
        raise ValueError(f"Future card not found: {event_id}")
    fight_urls = _fight_urls_for_event(event_id)
    return {
        "event_control": event_controls_repository.get(event_id),
        "lock_state": build_event_lock_state(event, fight_urls=fight_urls),
    }


def set_event_control(
    event_id: Any,
    *,
    lock_mode: str,
    event_start_at_utc: str | None,
    updated_by: Any | None,
) -> dict[str, Any]:
    event = _event_from_db(event_id)
    if event is None:
        raise ValueError(f"Future card not found: {event_id}")

    mode = clean_text(lock_mode).lower() or "auto"
    if mode not in LOCK_MODES:
        raise ValueError("Lock mode must be auto, force_open, or force_locked.")

    normalized_start = None
    if clean_text(event_start_at_utc):
        normalized_start = normalize_datetime_utc(event_start_at_utc)
        if normalized_start is None:
            raise ValueError("Event start time must be a valid ISO datetime.")

    control = event_controls_repository.upsert(
        event,
        event_start_at_utc=normalized_start,
        lock_mode=mode,
        updated_by=updated_by,
    )
    fight_urls = _fight_urls_for_event(event_id)
    return {
        "event_control": control,
        "lock_state": build_event_lock_state(event, fight_urls=fight_urls),
    }
