from __future__ import annotations

from datetime import date
from typing import Any

from app.repositories import (
    event_fights_repository,
    friends_repository,
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

# A user needs at least this many graded picks before their rating is "established"
# (it stays provisional until then, and provisional rows sort below established ones).
PROVISIONAL_THRESHOLD = 10
VALID_LEADERBOARD_SCOPES = {"overall", "friends", "me"}
VALID_LEADERBOARD_WINDOWS = {"all_time", "last5", "current_month"}

# Per-account prediction stats for the Profile "Your record" tiles + the leaderboard.
# Raw accuracy is the headline; record/streak/method come straight from scored picks; a
# best-effort "vs model" compares the user to the engine on shared fights; and a
# skill-vs-expectation **FIGHT IQ rating** (Elo-style, start 1000) ranks users.

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


def _event_key(pick: dict[str, Any]) -> str:
    event_id = str(pick.get("event_id") or "").strip()
    if event_id:
        return event_id
    event_date = str(pick.get("event_date") or "").strip()
    event_name = str(pick.get("event_name") or "").strip()
    if event_date or event_name:
        return f"{event_date}|{event_name}"
    return str(pick.get("fight_url") or "")


def _latest_event_keys(scored: list[dict[str, Any]], count: int = 5) -> set[str]:
    events: dict[str, tuple[date, str]] = {}
    for pick in scored:
        key = _event_key(pick)
        if not key:
            continue
        event_date = _parse_event_date(pick.get("event_date")) or date.min
        sort_value = (event_date, pick.get("scored_at") or "")
        if key not in events or sort_value > events[key]:
            events[key] = sort_value

    ordered = sorted(events.items(), key=lambda item: item[1], reverse=True)
    return {key for key, _ in ordered[:count]}


def _filter_scored_for_window(
    scored: list[dict[str, Any]],
    window: str,
    *,
    latest_event_keys: set[str] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    if window == "all_time":
        return scored

    if window == "last5":
        allowed = latest_event_keys or set()
        return [pick for pick in scored if _event_key(pick) in allowed]

    if window == "current_month":
        reference = today or date.today()
        return [
            pick
            for pick in scored
            if (parsed := _parse_event_date(pick.get("event_date"))) is not None
            and parsed.year == reference.year
            and parsed.month == reference.month
        ]

    raise ValueError("Leaderboard window must be all_time, last5, or current_month.")


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


def _public_name(user: dict[str, Any]) -> str:
    """Return the only public identity allowed on shared user leaderboards."""
    display_name = (user.get("display_name") or "").strip()
    if not display_name or "@" in display_name:
        return "Unnamed User"
    return display_name


def _users_for_scope(scope: str, current_user_id: Any) -> list[dict[str, Any]]:
    if scope == "overall":
        return users_repository.list_public_users()

    if current_user_id is None:
        return []

    if scope == "me":
        user = users_repository.get_by_id(current_user_id)
        return [user] if user else []

    if scope == "friends":
        ids = [int(current_user_id), *friends_repository.list_friend_ids(current_user_id)]
        users = [users_repository.get_by_id(user_id) for user_id in ids]
        return [user for user in users if user is not None]

    raise ValueError("Leaderboard scope must be overall, friends, or me.")


def build_leaderboard(
    current_user_id: Any = None,
    limit: int = 100,
    *,
    scope: str = "overall",
    window: str = "all_time",
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Public users ranked by FIGHT IQ rating. Established (>= PROVISIONAL_THRESHOLD
    graded picks) outrank provisional ones; ties break on accuracy then volume. Only
    display names are exposed."""
    scope = (scope or "overall").strip().lower()
    window = (window or "all_time").strip().lower()
    if scope not in VALID_LEADERBOARD_SCOPES:
        raise ValueError("Leaderboard scope must be overall, friends, or me.")
    if window not in VALID_LEADERBOARD_WINDOWS:
        raise ValueError("Leaderboard window must be all_time, last5, or current_month.")

    score_all_pending()  # grade everyone's now-completed picks before ranking
    snapshots = _snapshot_lookup()
    candidate_users = _users_for_scope(scope, current_user_id)
    picks_by_user: dict[int, list[dict[str, Any]]] = {}
    all_scored: list[dict[str, Any]] = []

    for user in candidate_users:
        picks = user_predictions_repository.list_for_user(user["id"])
        scored = [p for p in picks if p.get("status") == "scored"]
        picks_by_user[int(user["id"])] = scored
        all_scored.extend(scored)

    latest_keys = _latest_event_keys(all_scored) if window == "last5" else None

    rows: list[dict[str, Any]] = []
    for user in candidate_users:
        scored = _filter_scored_for_window(
            picks_by_user.get(int(user["id"]), []),
            window,
            latest_event_keys=latest_keys,
            today=today,
        )
        wins = sum(1 for p in scored if p.get("result_correct") == 1)
        losses = sum(1 for p in scored if p.get("result_correct") == 0)
        graded = wins + losses
        display_name = _public_name(user)
        picks_until_established = max(0, PROVISIONAL_THRESHOLD - graded)
        rows.append(
            {
                # Numeric id only — it keys the avatar image; emails stay private.
                "user_id": int(user["id"]),
                "display_name": display_name,
                "name": display_name,
                "rating": _rating(scored, snapshots),
                "wins": wins,
                "losses": losses,
                "graded": graded,
                "accuracy": (wins / graded) if graded else None,
                "provisional": graded < PROVISIONAL_THRESHOLD,
                "provisional_threshold": PROVISIONAL_THRESHOLD,
                "picks_until_established": picks_until_established,
                "is_me": current_user_id is not None and user["id"] == current_user_id,
                "scope": scope,
                "window": window,
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


def build_event_leaderboard(
    event_id: str,
    current_user_id: Any = None,
    limit: int = 100,
    *,
    scope: str = "friends",
) -> list[dict[str, Any]]:
    """Rank users for one completed card.

    Overall scope stays public opt-in only. Friends/me scopes can include private
    accounts, but still expose display names only.
    """
    event_id = (event_id or "").strip()
    if not event_id:
        raise ValueError("Event id is required.")

    scope = (scope or "friends").strip().lower()
    if scope not in VALID_LEADERBOARD_SCOPES:
        raise ValueError("Leaderboard scope must be overall, friends, or me.")

    score_all_pending()
    snapshots = _snapshot_lookup()
    candidate_users = _users_for_scope(scope, current_user_id)

    rows: list[dict[str, Any]] = []
    for user in candidate_users:
        scored = [
            pick
            for pick in user_predictions_repository.list_for_user(user["id"], event_id)
            if pick.get("status") == "scored"
        ]
        if not scored:
            continue

        wins = sum(1 for pick in scored if pick.get("result_correct") == 1)
        losses = sum(1 for pick in scored if pick.get("result_correct") == 0)
        graded = wins + losses
        method_picks = [pick for pick in scored if pick.get("picked_method")]
        method_hits = sum(1 for pick in method_picks if pick.get("method_correct") == 1)
        display_name = _public_name(user)
        event_name = next((pick.get("event_name") for pick in scored if pick.get("event_name")), "")
        event_date = next((pick.get("event_date") for pick in scored if pick.get("event_date")), "")

        rows.append(
            {
                "user_id": int(user["id"]),
                "display_name": display_name,
                "name": display_name,
                "event_id": event_id,
                "event_name": event_name,
                "event_date": event_date,
                "rating": _rating(scored, snapshots),
                "wins": wins,
                "losses": losses,
                "graded": graded,
                "accuracy": (wins / graded) if graded else None,
                "method_picks": len(method_picks),
                "method_hits": method_hits,
                "method_accuracy": (method_hits / len(method_picks)) if method_picks else None,
                "is_me": current_user_id is not None and user["id"] == current_user_id,
                "scope": scope,
            }
        )

    rows.sort(
        key=lambda row: (
            -row["wins"],
            -row["method_hits"],
            -row["rating"],
            -(row["accuracy"] or 0),
            -row["graded"],
            row["display_name"].casefold(),
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
