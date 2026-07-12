from __future__ import annotations

import math
import unicodedata
from datetime import date
from typing import Any

from app.repositories import (
    event_fights_repository,
    future_cards_repository,
    user_predictions_repository,
)

# Grades account picks against completed results (event_fights). Designed around the
# card-volatility rules: a pick is VOIDED (never penalized) when the bout changed
# (fighter swap), the result has no clean winner (draw / no-contest / overturned), or
# the picked fighter isn't in the result. Otherwise it's graded correct/incorrect,
# with an optional method-of-victory bonus.

# Upcoming fights use "ufcstats.com/..."; results use "www.ufcstats.com/..." — so the
# trailing fight-details id is the only reliable cross-table join key.
_NO_RESULT_METHODS = {"CNC", "OVERTURNED", "NC", "NO CONTEST", "DRAW", "OVERTURN"}

# A pick whose fight simply never happened (bout scrapped, card cancelled) gets no
# result row, so nothing above ever resolves it. Once the event date is this far past
# AND the fight is off every upcoming card, void it — otherwise it sits "open"
# forever, locked against deletion. The grace period covers late result scrapes and
# postponements that keep the fight scheduled.
ORPHAN_GRACE_DAYS = 3


def _fight_key(url: str | None) -> str:
    return (url or "").rstrip("/").split("/")[-1]


def _clean_str(value: Any) -> str:
    """Stripped string, treating None AND pandas NaN as missing. Result rows come
    through a DataFrame, where a NULL cell is a float NaN — which is truthy, so a
    plain `(value or "")` lets it straight through to .strip()."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _norm(name: Any) -> str:
    """Accent- and case-insensitive name key (UFCStats spells names a few ways)."""
    text = unicodedata.normalize("NFKD", _clean_str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split()).casefold()


def method_bucket(method: str | None) -> str | None:
    """Map a result's method string onto the coarse pick buckets, or None if it isn't
    one of them (DQ, no-contest, etc.)."""
    value = _clean_str(method).upper()
    if not value:
        return None
    if value.startswith("KO/TKO"):
        return "ko_tko"
    if value.startswith("SUB"):
        return "submission"
    if value.endswith("-DEC") or value in {"DEC", "DECISION"}:
        return "decision"
    return None


def grade_pick(
    pick: dict[str, Any], result: dict[str, Any]
) -> tuple[bool, bool | None] | None:
    """Return (result_correct, method_correct) for a graded pick, or None to VOID it.
    method_correct is None when the user didn't pick a method."""
    result_fighters = {_norm(result.get("fighter_1")), _norm(result.get("fighter_2"))}
    picked = _norm(pick.get("picked_fighter"))
    snapshot = {_norm(pick.get("fighter_1")), _norm(pick.get("fighter_2"))}

    # Card changed (fighter swap) or the picked fighter isn't in the actual bout.
    if picked not in result_fighters or snapshot != result_fighters:
        return None

    method = _clean_str(result.get("method")).upper()
    winner = _norm(result.get("winner"))
    if method in _NO_RESULT_METHODS or not winner:
        return None  # draw / no-contest / overturned — no gradable winner

    result_correct = winner == picked

    method_correct: bool | None = None
    if pick.get("picked_method"):
        if not method:
            # Winner is posted but the method cell is still empty (mid-scrape
            # partial results): grade the winner, leave the method ungraded
            # rather than calling it a miss on missing data.
            method_correct = None
        else:
            bucket = method_bucket(result.get("method"))
            method_correct = bucket is not None and bucket == pick["picked_method"]

    return result_correct, method_correct


def _result_lookup() -> dict[str, dict[str, Any]]:
    df = event_fights_repository.read_all_df()
    lookup: dict[str, dict[str, Any]] = {}
    for row in df.itertuples(index=False):
        key = _fight_key(getattr(row, "fight_url", None))
        if key:
            lookup[key] = {
                "fighter_1": getattr(row, "fighter_1", None),
                "fighter_2": getattr(row, "fighter_2", None),
                "winner": getattr(row, "winner", None),
                "method": getattr(row, "method", None),
            }
    return lookup


def _orphan_overdue(pick: dict[str, Any], today: date | None = None) -> bool:
    """True when the pick's event date is more than ORPHAN_GRACE_DAYS past."""
    from app.services.event_lock_service import parse_event_date

    parsed = parse_event_date(str(pick.get("event_date") or ""))
    if parsed is None:
        return False
    return ((today or date.today()) - parsed).days > ORPHAN_GRACE_DAYS


def _upcoming_fight_keys() -> set[str]:
    df = future_cards_repository.read_upcoming_fights_df()
    if df.empty:
        return set()
    return {_fight_key(url) for url in df.get("fight_url", []) if url}


def _score(pending: list[dict[str, Any]], today: date | None = None) -> dict[str, int]:
    results = _result_lookup()
    upcoming_keys: set[str] | None = None  # built lazily, only if needed
    scored = 0
    voided = 0
    for pick in pending:
        key = _fight_key(pick.get("fight_url"))
        result = results.get(key)
        if result is None:
            if _orphan_overdue(pick, today):
                if upcoming_keys is None:
                    upcoming_keys = _upcoming_fight_keys()
                # Still on an upcoming card (postponed/rescheduled) — leave it.
                if key not in upcoming_keys:
                    user_predictions_repository.mark_void(pick["id"])
                    voided += 1
            continue  # event not completed yet — leave pending

        outcome = grade_pick(pick, result)
        if outcome is None:
            user_predictions_repository.mark_void(pick["id"])
            voided += 1
        else:
            result_correct, method_correct = outcome
            user_predictions_repository.mark_scored(
                pick["id"], result_correct, method_correct
            )
            scored += 1

    return {
        "scored": scored,
        "voided": voided,
        "still_pending": len(pending) - scored - voided,
    }


def score_all_pending() -> dict[str, int]:
    """Grade every pending pick that now has a completed result. Idempotent: already
    scored/voided picks are skipped (only status 'open' is considered)."""
    return _score(user_predictions_repository.list_pending())


def score_user_pending(user_id: Any) -> dict[str, int]:
    """Grade one user's newly-completed picks (lazy resolution before reading stats)."""
    return _score(user_predictions_repository.list_pending(user_id))
