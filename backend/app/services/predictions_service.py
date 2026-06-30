from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.repositories import future_cards_repository, user_predictions_repository

# Optional method-of-victory pick. Kept as coarse buckets that map onto the
# method-model targets; scoring maps a result's method string onto the same set.
VALID_METHODS = {"ko_tko", "submission", "decision"}

# Date formats seen on upcoming cards (e.g. "July 11, 2026").
_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d")


def _parse_event_date(event_date: str | None) -> date | None:
    if not event_date:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(event_date.strip(), fmt).date()
        except ValueError:
            continue
    return None


def is_locked(event_date: str | None, today: date | None = None) -> bool:
    """Picks lock once the event day arrives. Editable strictly before then.
    Unparseable dates are treated as NOT locked so a pick is never silently blocked."""
    parsed = _parse_event_date(event_date)
    if parsed is None:
        return False
    return (today or date.today()) >= parsed


def _normalize_method(picked_method: str | None) -> str | None:
    if picked_method is None:
        return None
    value = picked_method.strip().lower()
    if value == "":
        return None
    if value not in VALID_METHODS:
        raise ValueError("Pick a valid method: KO/TKO, submission, or decision.")
    return value


def _public(prediction: dict[str, Any]) -> dict[str, Any]:
    """Client-facing shape: the stored pick plus a computed ``locked`` flag."""
    return {
        "fight_url": prediction["fight_url"],
        "event_id": prediction.get("event_id"),
        "event_name": prediction.get("event_name"),
        "event_date": prediction.get("event_date"),
        "fighter_1": prediction.get("fighter_1"),
        "fighter_2": prediction.get("fighter_2"),
        "weight_class": prediction.get("weight_class"),
        "picked_fighter": prediction.get("picked_fighter"),
        "picked_method": prediction.get("picked_method"),
        "status": prediction.get("status"),
        "result_correct": prediction.get("result_correct"),
        "method_correct": prediction.get("method_correct"),
        "locked": is_locked(prediction.get("event_date")),
        "created_at": prediction.get("created_at"),
        "updated_at": prediction.get("updated_at"),
    }


def make_prediction(
    user_id: Any,
    fight_url: str,
    picked_fighter: str,
    picked_method: str | None = None,
) -> dict[str, Any]:
    """Create or update a user's winner pick for an upcoming fight. Raises ValueError
    if the bout isn't on an upcoming card, the picked fighter isn't in it, the method
    is invalid, or the event is already locked."""
    fight = future_cards_repository.get_upcoming_fight(fight_url)
    if fight is None:
        raise ValueError("That fight isn't on an upcoming card.")

    picked_fighter = (picked_fighter or "").strip()
    if picked_fighter not in (fight.get("fighter_1"), fight.get("fighter_2")):
        raise ValueError("Pick one of the two fighters in this bout.")

    method = _normalize_method(picked_method)

    if is_locked(fight.get("event_date")):
        raise ValueError("Picks for this event are locked.")

    saved = user_predictions_repository.upsert(user_id, fight, picked_fighter, method)
    return _public(saved)


def list_predictions(user_id: Any, event_id: str | None = None) -> list[dict[str, Any]]:
    rows = user_predictions_repository.list_for_user(user_id, event_id)
    return [_public(row) for row in rows]


def remove_prediction(user_id: Any, fight_url: str) -> bool:
    """Delete a user's pick. Raises ValueError if the event is already locked."""
    existing = user_predictions_repository.get(user_id, fight_url)
    if existing is None:
        return False
    if is_locked(existing.get("event_date")):
        raise ValueError("Picks for this event are locked.")
    return user_predictions_repository.delete(user_id, fight_url)
