"""
tests/test_db.py — QA checks DB2 and DB3 for the db.py connection layer.

DB2: import-safety — db._client is None at import; no side effects.
DB3: env-driven branch selection — set MONGO_URI → pymongo.MongoClient;
     unset → mongomock.MongoClient; get_database() name default + override;
     singleton (two calls return the same object).
"""

import importlib
import pytest
import pymongo
import mongomock
import db


# ---------------------------------------------------------------------------
# Fixture: reset the module singleton before/after each test so tests are
# independent. Uses monkeypatch to restore any env edits automatically.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db_client():
    """Reset db._client to None before each test (and after, via yield)."""
    db._client = None
    yield
    db._client = None


# ---------------------------------------------------------------------------
# DB2 — Import-safety
# ---------------------------------------------------------------------------

class TestDB2ImportSafety:
    """DB2: db._client must be None at import time; get_mongo_client() builds it lazily."""

    def test_client_is_none_at_import(self):
        """After importing db, _client stays None — no side effect at import."""
        # reset_db_client fixture already cleared it; re-import the module
        # via importlib to prove the module attribute starts None.
        importlib.reload(db)
        assert db._client is None, (
            "db._client must be None immediately after import — "
            "no client may be constructed at module load time (ENV4)."
        )

    def test_client_built_after_first_call(self):
        """_client is populated after the first get_mongo_client() call."""
        assert db._client is None          # pre-condition
        db.get_mongo_client()
        assert db._client is not None      # now built


# ---------------------------------------------------------------------------
# DB3 — Branch selection and singleton
# ---------------------------------------------------------------------------

class TestDB3BranchSelection:
    """DB3: correct client type based on MONGO_URI env; singleton; DB_NAME default + override."""

    def test_fallback_branch_unset(self, monkeypatch):
        """With MONGO_URI unset, get_mongo_client() returns mongomock.MongoClient."""
        monkeypatch.delenv("MONGO_URI", raising=False)
        client = db.get_mongo_client()
        assert isinstance(client, mongomock.MongoClient), (
            f"Expected mongomock.MongoClient when MONGO_URI is unset, got {type(client)}"
        )

    def test_fallback_branch_empty_string(self, monkeypatch):
        """With MONGO_URI set to an empty string, fallback to mongomock."""
        monkeypatch.setenv("MONGO_URI", "")
        client = db.get_mongo_client()
        assert isinstance(client, mongomock.MongoClient)

    def test_real_branch_set(self, monkeypatch):
        """With MONGO_URI set, get_mongo_client() returns pymongo.MongoClient.

        We assert only the type — we do NOT call any method that triggers a
        network connection (no list_database_names(), no server_info()).
        """
        monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
        client = db.get_mongo_client()
        assert isinstance(client, pymongo.MongoClient), (
            f"Expected pymongo.MongoClient when MONGO_URI is set, got {type(client)}"
        )

    def test_singleton_same_object(self, monkeypatch):
        """Two successive calls return the exact same object (identity, not equality)."""
        monkeypatch.delenv("MONGO_URI", raising=False)
        client1 = db.get_mongo_client()
        client2 = db.get_mongo_client()
        assert client1 is client2, (
            "get_mongo_client() must return the cached singleton on the second call."
        )

    def test_singleton_same_object_real_branch(self, monkeypatch):
        """Singleton also holds on the pymongo branch (type-only, no network call)."""
        monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
        client1 = db.get_mongo_client()
        client2 = db.get_mongo_client()
        assert client1 is client2

    def test_get_database_default_name(self, monkeypatch):
        """get_database() returns a db whose .name is 'gtm_db' by default."""
        monkeypatch.delenv("MONGO_URI", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        database = db.get_database()
        assert database.name == "gtm_db", (
            f"Default DB_NAME must be 'gtm_db', got {database.name!r}"
        )

    def test_get_database_name_override(self, monkeypatch):
        """get_database() honors a DB_NAME env override."""
        monkeypatch.delenv("MONGO_URI", raising=False)
        monkeypatch.setenv("DB_NAME", "custom_db")
        database = db.get_database()
        assert database.name == "custom_db", (
            f"Expected 'custom_db' from DB_NAME override, got {database.name!r}"
        )

    def test_get_database_returns_correct_collection_access(self, monkeypatch):
        """Sanity: get_database()['contacts'] is accessible (basic doc-store access)."""
        monkeypatch.delenv("MONGO_URI", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        database = db.get_database()
        collection = database["contacts"]
        assert collection is not None
