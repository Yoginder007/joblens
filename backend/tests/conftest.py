import os

# Pure-logic tests don't touch the DB or download a model.
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("ENVIRONMENT", "local")
