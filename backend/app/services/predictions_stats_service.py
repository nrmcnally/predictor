from __future__ import annotations

from datetime import date
from typing import Any

from app.repositories import (
    event_fights_repository,
    saved_predictions_repository,
    user_predictions_repository,
    users_repository,
)
from app.services.predictions_scoring_service import (
    _fight_key,
    _norm,
    score_all_pending,
    score_user_pending,
)
from app.services.predictions_service import _parse_event_date

# A predictor needs at least this many graded picks before their rating is "established"
# (it stays provisional until then, and provisional rows sort below established ones).
PROVISIONAL_THRESHOLD = 10

# Per-account prediction stats for the Profile "Your record" tiles + the leaderboard.
# Raw accuracy is the headline; record/streak/method come straight from scored picks; a
# best-effort "vs model" compares the user to the engine on shared fights; and a
# skill-vs-expectation **FIGHT IQ rating** (Elo-style, start 1000) ranks predictors.

START_RATING = 1000.0
PROVISIONAL_PICKS = 10  # higher K while the rating is still finding its level
K_PROVISIONAL = 40.0
K_STABLE = 24.0
# Clamp the expected-correct probability so a single chalk/upset can't swing wildly.
_E_MIN, _E_MAX = 0.05, 0.95


def _snapshot_lookup() -> dict[str, dict[str, Any]]:
    """fight_key -> the saved model/market snapshot (names, win probs, model pick)."""
    df = saved_predictions_repository.read_all_df()
    lookup: dict[str, dict[str, Any]] = {}
    for row in df.itertuples(index=False):
        key = _fight_key(getattr(row, "fight_url", None))
        if not key:
            continue
        lookup[key] = {
            "fighter_1": getattr(row, "fighter_1", None),
            "fighter_2": getattr(row, "fighter_2", None),
            "f1_prob": getattr(row, "fighter_1_probability", None),
            "f2_prob": getattr(row, "fighter_2_probability", None),
            "f1_market": getattr(row, "fighter_1_market_probability", None),
            "f2_market": getattr(row, "fighter_2_market_probability", None),
            "predicted_winner": getattr(row, "predicted_winner", None),
        }
    return lookup


def _actual_winner_lookup() -> dict[str, str]:
    df = event_fights_repository.read_all_df()
    lookup: dict[str, str] = {}
    for row in df.itertuples(index=False):
        key = _fight_key(getattr(row, "fight_url", None))
        winner = getattr(row, "winner", None)
        if key and winner:
            lookup[key] = winner
    return lookup


def _expected_correct(pick: dict[str, Any], snap: dict[str, Any] | None) -> float:
    """Probability the pick is correct a priori — market line preferred, then the model,
    then a coin flip when we have no snapshot for the fight."""
    if snap is None:
        return 0.5
    picked = _norm(pick.get("picked_fighter"))
    if picked == _norm(snap.get("fighter_1")):
        expected = snap.get("f1_market")
        if expected is None:
            expected = snap.get("f1_prob")
    elif picked == _norm(snap.get("fighter_2")):
        expected = snap.get("f2_market")
        if expected is None:
            expected = snap.get("f2_prob")
    else:
        expected = None
    if expected is None:
        return 0.5
    return min(_E_MAX, max(_E_MIN, float(expected)))


def _chrono_key(pick: dict[str, Any]):
    return (
        _parse_event_date(pick.get("event_date")) or date.min,
        pick.get("scored_at") or "",
        pick.get("id") or 0,
    )


def _rating(scored: list[dict[str, Any]], snapshots: dict[str, dict[str, Any]]) -> int:
    """Replay graded picks in fight order, nudging the rating by K*(actual - expected)."""
    rating = START_RATING
    for played, pick in enumerate(sorted(scored, key=_chrono_key)):
        snap = snapshots.get(_fight_key(pick.get("fight_url")))
        expected = _expected_correct(pick, snap)
        actual = 1.0 if pick.get("result_correct") == 1 else 0.0
        k = K_PROVISIONAL if played < PROVISIONAL_PICKS else K_STABLE
        rating += k * (actual - expected)
    return round(rating)


def _vs_model(
    scored: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    winners: dict[str, str],
) -> dict[str, Any] | None:
    """Compare the user against the model on the user's own scored fights where the model
    has a saved pick. None until there's overlap (early-state)."""
    overlap = user_right = model_right = user_beats = model_beats = 0
    for pick in scored:
        key = _fight_key(pick.get("fight_url"))
        snap = snapshots.get(key)
        actual = winners.get(key)
        if not snap or not snap.get("predicted_winner") or not actual:
            continue
        overlap += 1
        user_correct = pick.get("result_correct") == 1
        model_correct = _norm(snap["predicted_winner"]) == _norm(actual)
        user_right += int(user_correct)
        model_right += int(model_correct)
        user_beats += int(user_correct and not model_correct)
        model_beats += int(model_correct and not user_correct)

    if overlap == 0:
        return None

    return {
        "overlap": overlap,
        "user_accuracy": user_right / overlap,
        "model_accuracy": model_right / overlap,
        "delta": (user_right - model_right) / overlap,  # +ve = beating the engine
        "user_beats": user_beats,
        "model_beats": model_beats,
    }


def build_user_stats(user_id: Any) -> dict[str, Any]:
    # Lazily grade this user's now-completed picks so the stats are current on read.
    score_user_pending(user_id)

    picks = user_predictions_repository.list_for_user(user_id)
    scored = [p for p in picks if p.get("status") == "scored"]

    wins = sum(1 for p in scored if p.get("result_correct") == 1)
    losses = sum(1 for p in scored if p.get("result_correct") == 0)
    graded = wins + losses

    method_picks = [p for p in scored if p.get("picked_method")]
    method_hits = sum(1 for p in method_picks if p.get("method_correct") == 1)

    snapshots = _snapshot_lookup()
    winners = _actual_winner_lookup()

    return {
        "rating": _rating(scored, snapshots),
        "record": {"wins": wins, "losses": losses},
        "graded": graded,
        "accuracy": (wins / graded) if graded else None,
        "streak": _current_streak(scored),
        "method": {
            "picks": len(method_picks),
            "hits": method_hits,
            "accuracy": (method_hits / len(method_picks)) if method_picks else None,
        },
        "vs_model": _vs_model(scored, snapshots, winners),
        "pending": sum(1 for p in picks if p.get("status") == "open"),
        "voided": sum(1 for p in picks if p.get("status") == "void"),
    }


def _mask_email(email: str | None) -> str:
    """Privacy: never expose another user's full email on a shared board. nate@x.com
    -> na***@x***. (Used only as a fallback when a user has no display name.)"""
    local, sep, domain = (email or "").partition("@")
    masked_local = (local[:2] + "***") if local else "***"
    if not sep:
        return masked_local
    return f"{masked_local}@{domain[0]}***"


def _public_name(user: dict[str, Any]) -> str:
    return (user.get("display_name") or "").strip() or _mask_email(user.get("email"))


def build_leaderboard(current_user_id: Any = None, limit: int = 100) -> list[dict[str, Any]]:
    """Public predictors ranked by FIGHT IQ rating. Established (>= PROVISIONAL_THRESHOLD
    graded picks) outrank provisional ones; ties break on accuracy then volume. Only
    display names (or masked emails) are exposed."""
    score_all_pending()  # grade everyone's now-completed picks before ranking
    snapshots = _snapshot_lookup()

    rows: list[dict[str, Any]] = []
    for user in users_repository.list_public_users():
        picks = user_predictions_repository.list_for_user(user["id"])
        scored = [p for p in picks if p.get("status") == "scored"]
        wins = sum(1 for p in scored if p.get("result_correct") == 1)
        losses = sum(1 for p in scored if p.get("result_correct") == 0)
        graded = wins + losses
        rows.append(
            {
                "name": _public_name(user),
                "rating": _rating(scored, snapshots),
                "wins": wins,
                "losses": losses,
                "graded": graded,
                "accuracy": (wins / graded) if graded else None,
                "provisional": graded < PROVISIONAL_THRESHOLD,
                "is_me": current_user_id is not None and user["id"] == current_user_id,
            }
        )

    # Established first, then rating, then accuracy, then more picks.
    rows.sort(
        key=lambda r: (
            r["provisional"],
            -r["rating"],
            -(r["accuracy"] or 0),
            -r["graded"],
        )
    )
    for index, row in enumerate(rows[:limit]):
        row["rank"] = index + 1
    return rows[:limit]


def _current_streak(scored: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The run of consecutive same outcomes ending at the most recent scored pick."""
    ordered = sorted(scored, key=_chrono_key)
    streak_type: str | None = None
    count = 0
    for pick in reversed(ordered):
        is_win = pick.get("result_correct") == 1
        if streak_type is None:
            streak_type = "W" if is_win else "L"
            count = 1
        elif (streak_type == "W") == is_win:
            count += 1
        else:
            break
    return {"type": streak_type, "count": count} if streak_type else None
