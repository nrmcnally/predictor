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
    # Provenance: which model generation produced this prospective snapshot, so the
    # Evaluation tab doesn't blend rows across recipe changes.
    ("model_version", "TEXT"),
    ("model_recipe_hash", "TEXT"),
    ("model_trained_at", "TEXT"),
    ("model_git_commit", "TEXT"),
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

# future_fight_odds — current market odds per upcoming fight; full-replaced on each
# odds refresh. (The 2 trailing flag columns postdate some older CSVs -> NULL on import.)
FUTURE_FIGHT_ODDS_COLUMNS: list[tuple[str, str]] = [
    ("event_name", "TEXT"),
    ("event_date", "TEXT"),
    ("event_url", "TEXT"),
    ("fight_url", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("weight_class", "TEXT"),
    ("odds_available", "INTEGER"),
    ("odds_event_id", "TEXT"),
    ("odds_commence_time", "TEXT"),
    ("odds_match_score", "REAL"),
    ("odds_match_min_score", "REAL"),
    ("odds_match_low_confidence", "INTEGER"),
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


# user_predictions — per-account winner picks on upcoming fights (Phase 6).
# Surrogate id PK + a UNIQUE(user_id, fight_url) index = one pick per user per fight.
# fighter_1/fighter_2 are SNAPSHOTTED at pick time so a later card change (fighter
# swap / cancellation) is detectable at scoring, and such picks are voided not graded.
USER_PREDICTIONS_COLUMNS: list[tuple[str, str]] = [
    ("user_id", "INTEGER"),
    ("fight_url", "TEXT"),
    ("event_id", "TEXT"),
    ("event_name", "TEXT"),
    ("event_url", "TEXT"),
    ("event_date", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("weight_class", "TEXT"),
    ("picked_fighter", "TEXT"),
    ("picked_method", "TEXT"),  # optional: ko_tko | submission | decision
    ("status", "TEXT"),         # open | locked | scored | void
    ("result_correct", "INTEGER"),
    ("method_correct", "INTEGER"),
    ("scored_at", "TEXT"),
    ("created_at", "TEXT"),
    ("updated_at", "TEXT"),
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
    create_table_sql("future_fight_odds", FUTURE_FIGHT_ODDS_COLUMNS),
    "CREATE INDEX IF NOT EXISTS idx_future_fight_odds_fight_url ON future_fight_odds(fight_url)",
    # users: accounts + roles. email is the unique login identifier (Phase 6).
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        display_name TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        is_public INTEGER NOT NULL DEFAULT 0,
        created_at TEXT
    )
    """,
    create_table_sql("user_predictions", USER_PREDICTIONS_COLUMNS),
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_predictions_user_fight "
    "ON user_predictions(user_id, fight_url)",
    "CREATE INDEX IF NOT EXISTS idx_user_predictions_user ON user_predictions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_predictions_event ON user_predictions(event_id)",
    # friendships: mutual-accept connections. One directed row (requester -> addressee)
    # per pair; status pending -> accepted. Friendship exists if an accepted row joins
    # the two in either direction.
    """
    CREATE TABLE IF NOT EXISTS friendships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_id INTEGER NOT NULL,
        addressee_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_friendships_pair "
    "ON friendships(requester_id, addressee_id)",
    "CREATE INDEX IF NOT EXISTS idx_friendships_addressee ON friendships(addressee_id)",
    "CREATE INDEX IF NOT EXISTS idx_friendships_requester ON friendships(requester_id)",
]


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    """Add missing columns to an existing table (lightweight forward migration)."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, declaration in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def _migrate_users_to_email(conn: sqlite3.Connection) -> None:
    """One-time conversion of the legacy username-keyed users table to the
    email-keyed one: email := '<username>@fightiq.local', display_name := username."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "username" not in cols or "email" in cols:
        return

    conn.execute(
        """
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_public INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO users_new (id, email, display_name, password_hash, role, is_public, created_at)
        SELECT id, username || '@fightiq.local', username, password_hash, role,
               COALESCE(is_public, 0), created_at
        FROM users
        """
    )
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")


def _ensure_unique_display_names(conn: sqlite3.Connection) -> None:
    """Back-fill existing accounts to unique display names (usernames) before the
    unique index is created. Derives from the current name (or email local-part) and
    de-dupes with a numeric suffix. Skipped once the unique index exists."""
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(users)").fetchall()}
    if "idx_users_display_name_nocase" in indexes:
        return

    seen: dict[str, int] = {}
    for row in conn.execute("SELECT id, display_name, email FROM users ORDER BY id").fetchall():
        uid, name, email = row[0], (row[1] or "").strip(), row[2] or ""
        base = name or email.split("@")[0] or f"user{uid}"
        candidate = base
        suffix = 1
        while candidate.lower() in seen:
            suffix += 1
            candidate = f"{base}{suffix}"
        if candidate != (row[1] or ""):
            conn.execute(
                "UPDATE users SET display_name = ? WHERE id = ?", (candidate, uid)
            )
        seen[candidate.lower()] = uid


# Spec-driven tables that get automatic column forward-migration: adding a column to
# any of these specs above backfills existing DBs on the next open (no manual migration).
_SPEC_TABLES: list[tuple[str, list[tuple[str, str]]]] = [
    ("saved_card_predictions", SAVED_CARD_COLUMNS),
    ("saved_model_predictions", SAVED_MODEL_COLUMNS),
    ("event_fights", EVENT_FIGHTS_COLUMNS),
    ("upcoming_events", UPCOMING_EVENTS_COLUMNS),
    ("upcoming_fights", UPCOMING_FIGHTS_COLUMNS),
    ("model_runs", MODEL_RUNS_COLUMNS),
    ("future_fight_odds", FUTURE_FIGHT_ODDS_COLUMNS),
    ("user_predictions", USER_PREDICTIONS_COLUMNS),
]


def init_db(conn: sqlite3.Connection) -> None:
    """Create any missing tables/indexes. Safe to call on every connection."""
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)

    # Forward-migrate older DBs.
    _migrate_users_to_email(conn)
    _ensure_columns(conn, "users", {"is_public": "INTEGER NOT NULL DEFAULT 0"})
    for table, columns in _SPEC_TABLES:
        _ensure_columns(conn, table, {name: sql_type for name, sql_type in columns})

    # Display name is the unique username (case-insensitive): de-dupe then enforce.
    _ensure_unique_display_names(conn)
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_display_name_nocase "
            "ON users(display_name COLLATE NOCASE)"
        )
    except sqlite3.OperationalError:
        pass  # residual dupes; service-level checks still enforce uniqueness
