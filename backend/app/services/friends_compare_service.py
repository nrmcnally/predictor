from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from app.repositories import (
    friends_repository,
    user_predictions_repository,
    users_repository,
)
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
    card_list = []
    for card in cards.values():
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
    }
