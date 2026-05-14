"""Pytest hooks: configure environment before app modules import."""
import os

# TestClient(app) runs lifespan during test collection; avoid real external services.
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
