from __future__ import annotations

from datetime import date
from typing import Any

from app.repositories import (
    event_fights_repository,
    future_cards_repository,
    saved_predictions_repository,
    user_predictions_repository,
)
from app.services import event_lock_service

# Optional method-of-victory pick. Kept as coarse buckets that map onto the
# method-model targets; scoring maps a result's method string onto the same set.
VALID_METHODS = {"ko_tko", "submission", "decision"}

def is_locked(event_date: str | None, today: date | None = None) -> bool:
    """Legacy date-only fallback kept for tests and old callers."""
    return event_lock_service.date_fallback_locked(event_date, today=today)


def _parse_event_date(event_date: str | None) -> date | None:
    """Compatibility wrapper for existing social comparison sorting."""
    return event_lock_service.parse_event_date(event_date)


def _lock_state(row: dict[str, Any]) -> dict[str, Any]:
    return event_lock_service.build_event_lock_state(row)


def _fight_key(url: str | None) -> str:
    return (url or "").rstrip("/").split("/")[-1]


def _normalize_method(picked_method: str | None) -> str | None:
    if picked_method is None:
        return None
    value = picked_method.strip().lower()
    if value == "":
        return None
    if value not in VALID_METHODS:
        raise ValueError("Pick a valid method: KO/TKO, submission, or decision.")
    return value


def _result_lookup() -> dict[str, dict[str, Any]]:
    df = event_fights_repository.read_all_df()
    lookup: dict[str, dict[str, Any]] = {}
    for row in df.itertuples(index=False):
        key = _fight_key(getattr(row, "fight_url", None))
        if not key:
            continue
        lookup[key] = {
            "actual_winner": getattr(row, "winner", None),
            "actual_method": getattr(row, "method", None),
            "actual_round": getattr(row, "round", None),
            "actual_time": getattr(row, "time", None),
        }
    return lookup


def _snapshot_lookup() -> dict[str, dict[str, Any]]:
    df = saved_predictions_repository.read_all_df()
    lookup: dict[str, dict[str, Any]] = {}
    for row in df.itertuples(index=False):
        key = _fight_key(getattr(row, "fight_url", None))
        if not key:
            continue
        lookup[key] = {
            "model_predicted_winner": getattr(row, "predicted_winner", None),
            "model_confidence": getattr(row, "confidence", None),
            "model_confidence_percentage": getattr(row, "confidence_percentage", None),
            "model_name": getattr(row, "model_name", None),
            "market_favorite": getattr(row, "market_favorite", None),
            "market_favorite_probability": getattr(row, "market_favorite_probability", None),
            "market_favorite_percentage": getattr(row, "market_favorite_percentage", None),
        }
    return lookup


def _public(
    prediction: dict[str, Any],
    *,
    results: dict[str, dict[str, Any]] | None = None,
    snapshots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Client-facing shape: the stored pick plus a computed ``locked`` flag."""
    lock_state = _lock_state(prediction)
    payload = {
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
        "scored_at": prediction.get("scored_at"),
        "locked": lock_state["locked"],
        "lock_state": lock_state,
        "created_at": prediction.get("created_at"),
        "updated_at": prediction.get("updated_at"),
    }
    key = _fight_key(prediction.get("fight_url"))
    if results is not None and key in results:
        payload.update(results[key])
    if snapshots is not None and key in snapshots:
        payload.update(snapshots[key])
    return payload


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

    if _lock_state(fight)["locked"]:
        raise ValueError("Picks for this event are locked.")

    saved = user_predictions_repository.upsert(user_id, fight, picked_fighter, method)
    return _public(saved)


def list_predictions(user_id: Any, event_id: str | None = None) -> list[dict[str, Any]]:
    # Resolve newly-completed picks before returning them, so My Picks/Profile do not
    # depend on a manual admin scoring action after fresh results arrive.
    from app.services.predictions_scoring_service import score_user_pending

    score_user_pending(user_id)
    rows = user_predictions_repository.list_for_user(user_id, event_id)
    results = _result_lookup()
    snapshots = _snapshot_lookup()
    return [_public(row, results=results, snapshots=snapshots) for row in rows]


def remove_prediction(user_id: Any, fight_url: str) -> bool:
    """Delete a user's pick. Raises ValueError if the event is already locked."""
    existing = user_predictions_repository.get(user_id, fight_url)
    if existing is None:
        return False
    if _lock_state(existing)["locked"]:
        raise ValueError("Picks for this event are locked.")
    return user_predictions_repository.delete(user_id, fight_url)
