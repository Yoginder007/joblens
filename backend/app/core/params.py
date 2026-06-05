"""Small shared helpers for parsing request query parameters."""


def csv(value: str | None) -> list[str]:
    """Split a comma-separated query param into a clean list, dropping blanks.

    e.g. "Amazon, , Google," -> ["Amazon", "Google"]
    """
    return [s.strip() for s in value.split(",") if s.strip()] if value else []
