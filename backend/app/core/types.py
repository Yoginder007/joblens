"""
Dialect-aware column types so the *same* models run on PostgreSQL (production)
and SQLite (local dev) without per-model branching.

  - GUID    → native UUID on Postgres, CHAR(36) on SQLite (always returns uuid.UUID)
  - JSONType→ JSONB on Postgres, JSON on SQLite
  - Vector  → pgvector ``vector(n)`` on Postgres, JSON list on SQLite
              (exposes ``cosine_distance`` via the ``<=>`` operator on Postgres)

pgvector is imported lazily, only when the bound dialect is PostgreSQL, so local
dev needs neither pgvector nor a Postgres driver installed.
"""
import uuid

from sqlalchemy import CHAR, JSON, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Vector(TypeDecorator):
    impl = JSON
    cache_ok = True

    class Comparator(TypeDecorator.Comparator):
        def cosine_distance(self, other):
            return self.op("<=>", return_type=Float)(other)

        def l2_distance(self, other):
            return self.op("<->", return_type=Float)(other)

    comparator_factory = Comparator

    def __init__(self, dim: int = 384, **kw):
        self.dim = dim
        super().__init__(**kw)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector as PGVector

            return dialect.type_descriptor(PGVector(self.dim))
        return dialect.type_descriptor(JSON())
