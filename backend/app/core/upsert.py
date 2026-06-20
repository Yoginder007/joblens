"""
Dialect-aware single-row upsert, shared by ingestion and matching so the
PostgreSQL / SQLite branch lives in exactly one place.

  - PostgreSQL: ``INSERT ... ON CONFLICT DO UPDATE`` on a named unique constraint
    (race-safe). The ``(xmax = 0)`` trick reports whether the row was inserted.
  - SQLite (local dev, single writer): check-then-write — no concurrent writer
    to race with.

Returns ``(pk, inserted)`` so callers can both reference the row and count
inserts vs updates.
"""
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


def upsert(
    db: Session,
    model: Any,
    values: dict,
    *,
    conflict_constraint: str,
    update_cols: Sequence[str],
    match_by: Sequence[str],
    touch_updated_at: bool = False,
) -> tuple[Any, bool]:
    """Insert ``values`` or, on a conflict over ``match_by``, update ``update_cols``.

    ``conflict_constraint`` is the Postgres unique-constraint name; ``match_by``
    are the identity columns used for the SQLite lookup. ``touch_updated_at`` sets
    ``updated_at = now()`` on the Postgres UPDATE path (ON CONFLICT bypasses the
    ORM ``onupdate``; SQLite's check-then-write goes through the ORM, which fires
    ``onupdate`` on its own).
    """
    if db.bind.dialect.name == "postgresql":
        set_ = {c: values[c] for c in update_cols}
        if touch_updated_at:
            set_["updated_at"] = func.now()
        stmt = (
            pg_insert(model).values(**values)
            .on_conflict_do_update(constraint=conflict_constraint, set_=set_)
            .returning(model.id, literal_column("(xmax = 0)").label("inserted"))
        )
        row = db.execute(stmt).one()
        return row.id, bool(row.inserted)

    existing = db.scalar(
        select(model).where(*[getattr(model, c) == values[c] for c in match_by])
    )
    if existing is not None:
        for c in update_cols:
            setattr(existing, c, values[c])
        return existing.id, False
    obj = model(**values)
    db.add(obj)
    db.flush()
    return obj.id, True
