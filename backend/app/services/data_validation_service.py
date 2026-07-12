"""Ingestion validation for scraped event results (data-contract layer 2).

Two severities, deliberately distinct:

- FAILURES are structural — they mean the scraper itself is broken
  (UFCStats changed their HTML, parser drift) and writing the rows would
  poison every downstream stage. The pipeline stage raises on these, so
  the morning run fails loudly at the boundary with a message that names
  the problem, instead of three stages later with a type error.

- WARNINGS are completeness — results still posting on UFCStats when the
  scrape ran. That is a legitimate transient state: the rows are written
  as-is (the incomplete-results re-scrape completes them on the next
  run), and the counts surface in the stage report and the morning log
  so a quiet site update has a visible, boring explanation.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.db.frame_contract import clean_text_cell


def _norm_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_text_cell(value) or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split()).casefold()


@dataclass
class ValidationReport:
    event_name: str
    total_rows: int = 0
    incomplete_rows: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def validate_scraped_event_fights(
    rows: list[dict[str, Any]], event_name: str
) -> ValidationReport:
    """Validate one completed event's freshly scraped fight rows before they
    are written. See the module docstring for the failure/warning split."""
    report = ValidationReport(event_name=event_name, total_rows=len(rows))

    if not rows:
        report.failures.append(
            f"{event_name}: scraped 0 fights — parser found nothing on the event page."
        )
        return report

    seen_urls: set[str] = set()

    for index, row in enumerate(rows):
        label = f"{event_name} fight #{index + 1}"

        fight_url = clean_text_cell(row.get("fight_url"))
        fighter_1 = clean_text_cell(row.get("fighter_1"))
        fighter_2 = clean_text_cell(row.get("fighter_2"))
        winner = clean_text_cell(row.get("winner"))
        method = clean_text_cell(row.get("method"))

        if not fight_url:
            report.failures.append(f"{label}: missing fight_url.")
        elif fight_url in seen_urls:
            report.failures.append(f"{label}: duplicate fight_url {fight_url}.")
        else:
            seen_urls.add(fight_url)

        if not fighter_1 or not fighter_2:
            report.failures.append(f"{label}: missing fighter name(s).")
            continue

        if winner and _norm_name(winner) not in {
            _norm_name(fighter_1),
            _norm_name(fighter_2),
        }:
            report.failures.append(
                f"{label}: winner '{winner}' matches neither "
                f"'{fighter_1}' nor '{fighter_2}'."
            )

        if not winner or not method:
            report.incomplete_rows += 1

    if report.incomplete_rows:
        report.warnings.append(
            f"{event_name}: {report.incomplete_rows} of {report.total_rows} "
            "results still posting (missing winner/method) — will re-scrape "
            "next run."
        )

    return report
