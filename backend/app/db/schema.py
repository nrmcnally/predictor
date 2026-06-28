from __future__ import annotations

import sqlite3

# Canonical typed column specs. Each transactional dataset migrated to SQLite lists
# its columns here (single source of truth), and the DDL + repository inserts are
# generated from them so the table definition and the code never drift.

# (column_name, sqlite_type) — order mirrors the legacy CSV header for faithful import.
SAVED_CARD_COLUMNS: list[tuple[str, str]] = [
    ("saved_at", "TEXT"),
    ("event_id", "TEXT"),
    ("event_name", "TEXT"),
    ("event_date", "TEXT"),
    ("event_location", "TEXT"),
    ("event_url", "TEXT"),
    ("fight_id", "TEXT"),
    ("fight_url", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("weight_class", "TEXT"),
    ("prediction_available", "INTEGER"),
    ("error_json", "TEXT"),
    ("predicted_winner", "TEXT"),
    ("fighter_1_probability", "REAL"),
    ("fighter_2_probability", "REAL"),
    ("fighter_1_percentage", "TEXT"),
    ("fighter_2_percentage", "TEXT"),
    ("confidence", "REAL"),
    ("confidence_percentage", "TEXT"),
    ("confidence_label", "TEXT"),
    ("model_name", "TEXT"),
    ("model_metrics_json", "TEXT"),
    ("basic_matchup_edges_json", "TEXT"),
    ("odds_available", "INTEGER"),
    ("odds_bookmaker", "TEXT"),
    ("odds_last_update", "TEXT"),
    ("bookmakers_matched", "INTEGER"),
    ("fighter_1_odds_american", "REAL"),
    ("fighter_2_odds_american", "REAL"),
    ("fighter_1_market_probability", "REAL"),
    ("fighter_2_market_probability", "REAL"),
    ("fighter_1_market_percentage", "TEXT"),
    ("fighter_2_market_percentage", "TEXT"),
    ("market_favorite", "TEXT"),
    ("market_favorite_probability", "REAL"),
    ("market_favorite_percentage", "TEXT"),
    ("scheduled_rounds", "INTEGER"),
    ("is_main_event", "INTEGER"),
    ("round_override_saved", "INTEGER"),
    ("round_override_source", "TEXT"),
    ("round_override_updated_at", "TEXT"),
    ("model_version", "TEXT"),
    ("model_recipe_hash", "TEXT"),
    ("model_trained_at", "TEXT"),
    ("model_git_commit", "TEXT"),
]

# saved_model_predictions — one prospective snapshot row per model per fight.
SAVED_MODEL_COLUMNS: list[tuple[str, str]] = [
    ("saved_at", "TEXT"),
    ("snapshot_id", "TEXT"),
    ("event_id", "TEXT"),
    ("event_name", "TEXT"),
    ("event_date", "TEXT"),
    ("event_location", "TEXT"),
    ("event_url", "TEXT"),
    ("fight_id", "TEXT"),
    ("fight_url", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("weight_class", "TEXT"),
    ("model_name", "TEXT"),
    ("is_best_model", "INTEGER"),
    ("model_metrics_json", "TEXT"),
    ("prediction_available", "INTEGER"),
    ("error_json", "TEXT"),
    ("predicted_winner", "TEXT"),
    ("fighter_1_probability", "REAL"),
    ("fighter_2_probability", "REAL"),
    ("fighter_1_percentage", "TEXT"),
    ("fighter_2_percentage", "TEXT"),
    ("confidence", "REAL"),
    ("confidence_percentage", "TEXT"),
    ("confidence_label", "TEXT"),
    ("odds_available", "INTEGER"),
    ("odds_bookmaker", "TEXT"),
    ("odds_last_update", "TEXT"),
    ("bookmakers_matched", "INTEGER"),
    ("fighter_1_odds_american", "REAL"),
    ("fighter_2_odds_american", "REAL"),
    ("fighter_1_market_probability", "REAL"),
    ("fighter_2_market_probability", "REAL"),
    ("fighter_1_market_percentage", "TEXT"),
    ("fighter_2_market_percentage", "TEXT"),
    ("market_favorite", "TEXT"),
    ("market_favorite_probability", "REAL"),
    ("market_favorite_percentage", "TEXT"),
    ("scheduled_rounds", "INTEGER"),
    ("is_main_event", "INTEGER"),
    ("round_override_saved", "INTEGER"),
    ("round_override_source", "TEXT"),
    ("round_override_updated_at", "TEXT"),
]


# Future cards — full-replace on every scrape, so a surrogate id is fine.
UPCOMING_EVENTS_COLUMNS: list[tuple[str, str]] = [
    ("event_id", "TEXT"),
    ("event_name", "TEXT"),
    ("event_date", "TEXT"),
    ("event_location", "TEXT"),
    ("event_url", "TEXT"),
]

UPCOMING_FIGHTS_COLUMNS: list[tuple[str, str]] = [
    ("event_id", "TEXT"),
    ("event_name", "TEXT"),
    ("event_date", "TEXT"),
    ("event_location", "TEXT"),
    ("event_url", "TEXT"),
    ("fight_url", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("weight_class", "TEXT"),
]

# model_runs — append-only audit log of training runs (#17: real reproducibility).
# Each row fingerprints the exact training data + the recipe/lineage it produced.
MODEL_RUNS_COLUMNS: list[tuple[str, str]] = [
    ("trained_at", "TEXT"),
    ("model_version", "TEXT"),
    ("recipe_hash", "TEXT"),
    ("git_commit", "TEXT"),
    ("git_dirty", "INTEGER"),
    ("model_type", "TEXT"),
    ("calibration_method", "TEXT"),
    ("best_model_name", "TEXT"),
    ("training_data_hash", "TEXT"),
    ("training_rows", "INTEGER"),
    ("training_fights", "INTEGER"),
    ("feature_count", "INTEGER"),
]


# event_fights (completed results). fight_url is the natural key (one row per fight),
# so it's the PRIMARY KEY — no surrogate id — which makes incremental upserts clean.
EVENT_FIGHTS_COLUMNS: list[tuple[str, str]] = [
    ("event_name", "TEXT"),
    ("event_date", "TEXT"),
    ("event_location", "TEXT"),
    ("event_url", "TEXT"),
    ("fight_url", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("result_1", "TEXT"),
    ("result_2", "TEXT"),
    ("winner", "TEXT"),
    ("loser", "TEXT"),
    ("weight_class", "TEXT"),
    ("method", "TEXT"),
    ("round", "INTEGER"),
    ("time", "TEXT"),
]


def create_table_sql(
    name: str,
    columns: list[tuple[str, str]],
    primary_key: str | None = None,
) -> str:
    col_defs = []
    for column, sql_type in columns:
        if column == primary_key:
            col_defs.append(f"{column} {sql_type} PRIMARY KEY")
        else:
            col_defs.append(f"{column} {sql_type}")
    body = ",\n        ".join(col_defs)

    if primary_key is None:
        # Surrogate autoincrement id (multiple rows per natural key).
        return (
            f"CREATE TABLE IF NOT EXISTS {name} (\n"
            f"        id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            f"        {body}\n"
            f"    )"
        )

    return f"CREATE TABLE IF NOT EXISTS {name} (\n        {body}\n    )"


# Idempotent DDL run on every connection. Add tables here as datasets migrate.
SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS fight_odds_track (
        fight_url TEXT PRIMARY KEY,
        fighter_1 TEXT,
        fighter_2 TEXT,
        opening_fighter_1_probability REAL,
        opening_fighter_2_probability REAL,
        opening_captured_at TEXT,
        closing_fighter_1_probability REAL,
        closing_fighter_2_probability REAL,
        closing_captured_at TEXT,
        capture_count INTEGER NOT NULL DEFAULT 1
    )
    """,
    create_table_sql("saved_card_predictions", SAVED_CARD_COLUMNS),
    "CREATE INDEX IF NOT EXISTS idx_saved_card_event ON saved_card_predictions(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_saved_card_fight_url ON saved_card_predictions(fight_url)",
    create_table_sql("saved_model_predictions", SAVED_MODEL_COLUMNS),
    "CREATE INDEX IF NOT EXISTS idx_saved_model_event ON saved_model_predictions(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_saved_model_fight_url ON saved_model_predictions(fight_url)",
    create_table_sql("event_fights", EVENT_FIGHTS_COLUMNS, primary_key="fight_url"),
    "CREATE INDEX IF NOT EXISTS idx_event_fights_event_url ON event_fights(event_url)",
    create_table_sql("upcoming_events", UPCOMING_EVENTS_COLUMNS),
    create_table_sql("upcoming_fights", UPCOMING_FIGHTS_COLUMNS),
    "CREATE INDEX IF NOT EXISTS idx_upcoming_fights_event ON upcoming_fights(event_id)",
    create_table_sql("model_runs", MODEL_RUNS_COLUMNS),
]


def init_db(conn: sqlite3.Connection) -> None:
    """Create any missing tables/indexes. Safe to call on every connection."""
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
