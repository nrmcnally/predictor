"""Repository layer: the single data-access point for each transactional dataset.

Repositories return pandas DataFrames (matching the legacy CSV shape) so existing
consumers change minimally, while writes go through atomic SQLite transactions.
"""
