"""The in-memory missing-value contract for entity data.

Every repository read returns DataFrames honoring this contract:

- TEXT columns hold ``str`` or ``None`` — never float NaN, and never the
  literal strings "nan"/"none"/"null" that a stray ``str()`` once minted.
  Present values are whitespace-stripped.
- INTEGER/REAL columns are numeric dtype with NaN as the missing marker —
  pandas' native representation, which arithmetic consumers rely on.

The write paths already coerce toward SQL NULL (see the repositories'
``_coerce``); this module is the READ-side half of the same contract.
``pd.DataFrame()`` resurrects SQL NULLs as float NaN even in string
columns — which is how a float reached scoring's ``.strip()`` and crashed
the 2026-07-11 auto-update. Consumers of repository frames may assume the
contract instead of re-defending against NaN at every use site.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Placeholder spellings of "missing" that should never survive a read.
_TEXT_MISSING_LITERALS = {"", "nan", "none", "null"}


def clean_text_cell(value: Any) -> str | None:
    """``None`` for missing (None, NaN, empty or placeholder strings);
    a stripped ``str`` otherwise."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text.lower() in _TEXT_MISSING_LITERALS:
        return None
    return text


def normalize_frame(
    df: pd.DataFrame, columns: list[tuple[str, str]]
) -> pd.DataFrame:
    """Enforce the contract on a frame read from storage. Mutates and returns
    ``df``. ``columns`` is the schema spec: ``[(name, sql_type), ...]``."""
    for name, sql_type in columns:
        if name not in df.columns:
            continue
        if sql_type == "TEXT":
            # Explicit object construction: Series.map would re-infer the
            # returned Nones straight back into NaN.
            df[name] = pd.Series(
                [clean_text_cell(v) for v in df[name]],
                index=df.index,
                dtype=object,
            )
        else:  # INTEGER / REAL — numeric dtype, NaN for missing
            df[name] = pd.to_numeric(df[name], errors="coerce")
    return df
