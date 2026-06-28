"""Authentication: accounts, roles, password hashing, and signed tokens.

Dependency-free (stdlib): PBKDF2-SHA256 password hashing and HMAC-SHA256 signed
tokens (a compact JWT-equivalent). Swappable for bcrypt/PyJWT later without touching
callers — only app/auth/security.py changes.
"""
