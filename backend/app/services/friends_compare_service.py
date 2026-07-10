from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from app.repositories import (
    event_fights_repository,
    friends_repository,
    future_cards_repository,
    user_predictions_repository,
    users_repository,
)
from app.services import event_lock_service
from app.services.friends_service import _display_name
from app.services.predictions_scoring_service import _fight_key, score_user_pending
from app.services.predictions_service import _parse_event_date
from app.services.predictions_stats_service import (
    _actual_winner_lookup,
    _rating,
    _snapshot_lookup,
)

# Head-to-head compare between two friends: an overall rivalry record (accuracy + card
# wins + rating) and a per-card breakdown of who called each fight. Only picks BOTH
# users graded on the same fight count toward the comparison.


def _scored_by_key(user_id: Any) -> dict[str, dict[str, Any]]:
    picks = user_predictions_repository.list_for_user(user_id)
    return {_fight_key(p["fight_url"]): p for p in picks if p.get("status") == "scored"}


def _open_by_key(user_id: Any) -> dict[str, dict[str, Any]]:
    picks = user_predictions_repository.list_for_user(user_id)
    return {_fight_key(p["fight_url"]): p for p in picks if p.get("status") == "open"}


def _bout_order_lookup() -> dict[str, int]:
    """fight_key -> position in the scraped card order (main event first, as
    UFCStats lists them — the same order My Picks shows). A card's fights are
    contiguous rows in both tables, so a global row index sorts correctly within
    any one card. Without this, compare fights came back in set-iteration order."""
    order: dict[str, int] = {}
    index = 0
    for df in (
        future_cards_repository.read_upcoming_fights_df(),
        event_fights_repository.read_all_df(),
    ):
        if df.empty or "fight_url" not in df.columns:
            continue
        for url in df["fight_url"]:
            key = _fight_key(url)
            if key and key not in order:
                order[key] = index
            index += 1
    return order


def _build_upcoming(me_id: Any, other_id: Any) -> list[dict[str, Any]]:
    """Head-to-head on UPCOMING picks. Anti-copying rule: a friend's pick on a fight
    is revealed only once YOU have picked that fight yourself (or the event has
    locked) — you commit first, then you see theirs."""
    mine = _open_by_key(me_id)
    theirs = _open_by_key(other_id)

    lock_cache: dict[tuple[str, str], bool] = {}

    def _locked(row: dict[str, Any]) -> bool:
        key = (str(row.get("event_id") or ""), str(row.get("event_date") or ""))
        if key not in lock_cache:
            lock_cache[key] = bool(event_lock_service.build_event_lock_state(row)["locked"])
        return lock_cache[key]

    cards: dict[str, dict[str, Any]] = {}
    for key in set(mine) | set(theirs):
        my_pick = mine.get(key)
        their_pick = theirs.get(key)
        reference = my_pick or their_pick
        reveal = my_pick is not None or _locked(reference)

        card_key = str(reference.get("event_id") or reference.get("event_date") or "")
        card = cards.setdefault(
            card_key,
            {
                "event_id": reference.get("event_id"),
                "event_name": reference.get("event_name"),
                "event_date": reference.get("event_date"),
                "fights": [],
            },
        )
        card["fights"].append(
            {
                "fight_key": key,
                "fighter_1": reference.get("fighter_1"),
                "fighter_2": reference.get("fighter_2"),
                "weight_class": reference.get("weight_class"),
                "your_pick": my_pick.get("picked_fighter") if my_pick else None,
                "your_method": my_pick.get("picked_method") if my_pick else None,
                "their_pick": their_pick.get("picked_fighter") if their_pick and reveal else None,
                "their_method": their_pick.get("picked_method") if their_pick and reveal else None,
                # They have a pick you can't see yet — pick this fight to reveal it.
                "their_pick_hidden": their_pick is not None and not reveal,
                "agree": (
                    my_pick.get("picked_fighter") == their_pick.get("picked_fighter")
                    if my_pick and their_pick and reveal
                    else None
                ),
            }
        )

    ordered = sorted(
        cards.values(), key=lambda c: _parse_event_date(c.get("event_date")) or date.max
    )
    bout_order = _bout_order_lookup()
    for card in ordered:
        # Card order (main event first), matching My Picks — not alphabetical.
        card["fights"].sort(key=lambda f: bout_order.get(f["fight_key"], 10**9))
        card["your_picked"] = sum(1 for f in card["fights"] if f["your_pick"])
        card["their_hidden"] = sum(1 for f in card["fights"] if f["their_pick_hidden"])
    return ordered


def build_compare(me_id: Any, other_id: Any) -> dict[str, Any]:
    if other_id not in friends_repository.list_friend_ids(me_id):
        raise ValueError("You can only compare with your friends.")

    # Grade any now-completed picks for both sides so the comparison is current.
    score_user_pending(me_id)
    score_user_pending(other_id)

    mine = _scored_by_key(me_id)
    theirs = _scored_by_key(other_id)
    shared = set(mine) & set(theirs)

    winners = _actual_winner_lookup()
    snapshots = _snapshot_lookup()

    cards: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"fights": [], "you_correct": 0, "them_correct": 0}
    )
    you_correct = them_correct = 0

    for key in shared:
        mp, tp = mine[key], theirs[key]
        my_ok = mp.get("result_correct") == 1
        their_ok = tp.get("result_correct") == 1
        you_correct += int(my_ok)
        them_correct += int(their_ok)

        card = cards[mp.get("event_id") or key]
        card["event_id"] = mp.get("event_id")
        card["event_name"] = mp.get("event_name")
        card["event_date"] = mp.get("event_date")
        card["you_correct"] += int(my_ok)
        card["them_correct"] += int(their_ok)
        card["fights"].append(
            {
                "fight_key": key,
                "fighter_1": mp.get("fighter_1"),
                "fighter_2": mp.get("fighter_2"),
                "actual_winner": winners.get(key),
                "your_pick": mp.get("picked_fighter"),
                "your_correct": my_ok,
                "their_pick": tp.get("picked_fighter"),
                "their_correct": their_ok,
            }
        )

    record = {"you": 0, "them": 0, "tied": 0}
    bout_order = _bout_order_lookup()
    card_list = []
    for card in cards.values():
        # Shared picks arrive in set order; show them in card order instead.
        card["fights"].sort(key=lambda f: bout_order.get(f["fight_key"], 10**9))
        card["total"] = len(card["fights"])
        if card["you_correct"] > card["them_correct"]:
            card["winner"] = "you"
            record["you"] += 1
        elif card["them_correct"] > card["you_correct"]:
            card["winner"] = "them"
            record["them"] += 1
        else:
            card["winner"] = "tie"
            record["tied"] += 1
        card_list.append(card)

    card_list.sort(key=lambda c: _parse_event_date(c.get("event_date")) or date.min, reverse=True)

    shared_n = len(shared)
    my_scored = [p for p in user_predictions_repository.list_for_user(me_id) if p.get("status") == "scored"]
    their_scored = [p for p in user_predictions_repository.list_for_user(other_id) if p.get("status") == "scored"]

    return {
        "friend": {
            "user_id": int(other_id),
            "display_name": _display_name(users_repository.get_by_id(other_id)),
        },
        "shared": shared_n,
        "you": {
            "correct": you_correct,
            "accuracy": (you_correct / shared_n) if shared_n else None,
            "rating": _rating(my_scored, snapshots),
        },
        "them": {
            "correct": them_correct,
            "accuracy": (them_correct / shared_n) if shared_n else None,
            "rating": _rating(their_scored, snapshots),
        },
        "card_record": record,
        "cards": card_list,
        "upcoming": _build_upcoming(me_id, other_id),
    }
