from __future__ import annotations

import math
import re
from typing import Any, Mapping


ROUND_SECONDS = 5 * 60
_DECISION_PATTERN = re.compile(r"(?:^|[- /])DEC(?:$|[- /])|DECISION", re.IGNORECASE)
_EXCLUDED_METHOD_PATTERN = re.compile(
    r"NO CONTEST|OVERTURN|CANCEL|DRAW|DISQUAL|\bDQ\b",
    re.IGNORECASE,
)


def _finite_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_round_time(value: Any) -> int | None:
    """Convert an official round clock value such as ``4:37`` to seconds."""
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None

    minutes = int(match.group(1))
    seconds = int(match.group(2))
    if minutes > 5 or seconds >= 60 or (minutes == 5 and seconds != 0):
        return None
    return minutes * 60 + seconds


def resolve_fight_duration(
    result: Mapping[str, Any],
    *,
    scheduled_rounds: Any,
) -> dict[str, Any]:
    """Resolve official elapsed fight time without applying a betting line.

    Training a duration distribution needs the underlying elapsed time, including
    results that happen exactly on a possible market boundary. Line-specific push
    handling belongs in ``settle_duration_result`` and must not discard those fights
    from the survival dataset.
    """
    numeric_rounds = _finite_number(scheduled_rounds)
    if numeric_rounds is None or int(numeric_rounds) not in {3, 5}:
        return {"status": "excluded", "reason": "unsupported_scheduled_rounds"}

    result_1 = str(result.get("result_1") or "").strip().lower()
    result_2 = str(result.get("result_2") or "").strip().lower()
    winner = str(result.get("winner") or "").strip()
    method = str(result.get("method") or "").strip()
    if {result_1, result_2} != {"win", "loss"} or not winner:
        return {"status": "excluded", "reason": "unsettled_result"}
    if not method or _EXCLUDED_METHOD_PATTERN.search(method):
        return {"status": "excluded", "reason": "unsupported_result_method"}

    scheduled_seconds = int(numeric_rounds) * ROUND_SECONDS
    if _DECISION_PATTERN.search(method):
        elapsed_seconds = scheduled_seconds
        observed_finish = False
    else:
        numeric_finish_round = _finite_number(result.get("round"))
        clock_seconds = parse_round_time(result.get("time"))
        if numeric_finish_round is None or clock_seconds is None:
            return {"status": "excluded", "reason": "missing_finish_time"}
        finish_round = int(numeric_finish_round)
        if finish_round < 1 or finish_round > int(numeric_rounds):
            return {"status": "excluded", "reason": "invalid_finish_round"}
        elapsed_seconds = (finish_round - 1) * ROUND_SECONDS + clock_seconds
        if elapsed_seconds > scheduled_seconds:
            return {"status": "excluded", "reason": "finish_after_scheduled_time"}
        observed_finish = elapsed_seconds < scheduled_seconds

    return {
        "status": "resolved",
        "reason": "",
        "elapsed_seconds": float(elapsed_seconds),
        "scheduled_seconds": scheduled_seconds,
        "observed_finish": observed_finish,
    }


def settle_duration_result(
    result: Mapping[str, Any],
    *,
    line: Any,
    scheduled_rounds: Any,
) -> dict[str, Any]:
    """Settle an exact rounds-total line from an official result.

    This baseline contract handles standard five-minute UFC rounds. Ambiguous
    results and exact-boundary outcomes are excluded rather than guessed. That is
    deliberately conservative until provider-specific void rules are versioned.
    """
    numeric_line = _finite_number(line)
    if numeric_line is None or numeric_line <= 0:
        return {"status": "excluded", "reason": "invalid_line"}
    duration = resolve_fight_duration(result, scheduled_rounds=scheduled_rounds)
    if duration["status"] != "resolved":
        return duration

    elapsed_seconds = float(duration["elapsed_seconds"])

    threshold_seconds = numeric_line * ROUND_SECONDS
    if math.isclose(elapsed_seconds, threshold_seconds, abs_tol=1e-9):
        return {
            "status": "push",
            "reason": "exact_boundary",
            "elapsed_seconds": elapsed_seconds,
            "threshold_seconds": threshold_seconds,
        }

    actual_side = "over" if elapsed_seconds > threshold_seconds else "under"
    return {
        "status": "settled",
        "reason": "",
        "actual_side": actual_side,
        "target_over": 1 if actual_side == "over" else 0,
        "elapsed_seconds": elapsed_seconds,
        "threshold_seconds": threshold_seconds,
    }
