"""Application-wide constants."""

# Single-user assistant identifier.  All memory and preference stores that
# need a user scope key off this value.  It is defined once here to avoid
# the string "default_user" being scattered across the codebase.
DEFAULT_USER_ID: str = "default_user"
