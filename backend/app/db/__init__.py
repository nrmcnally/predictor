"""SQLite data-access layer.

Houses the connection factory (WAL, atomic transactions) and the schema for the
app's *transactional* data (results, saved predictions, odds track, future cards).
Large ML artifacts (snapshots, matchups, trained models) stay as files.
"""
