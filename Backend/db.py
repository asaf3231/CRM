"""
db.py — ReactFirst AI Proactive Outbound Engine
Shared lazy Mongo connection layer.

Import-safe: import of this module has ZERO side effects — no client construction,
no env-driven logic, no I/O of any kind at import time. Only imports + the
module-level singleton sentinel are set.

Env contract:
  MONGO_URI  — if set (non-empty), returns a real pymongo.MongoClient(MONGO_URI).
                if unset / empty, falls back to mongomock.MongoClient() for
                offline use, testing, and local-dev without a running server.
  DB_NAME    — name of the MongoDB database (default: "gtm_db"). Read inside
                get_database() so monkeypatching env in tests takes effect.

NEVER log or print the MONGO_URI value — a connection string can carry credentials.
"""

import os
import pymongo
import mongomock

# ---------------------------------------------------------------------------
# Module-level singleton (None until first use — ENV4 requirement)
# ---------------------------------------------------------------------------
_client = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_mongo_client():
    """Return the shared Mongo client (pymongo or mongomock), building it lazily.

    Branch selection:
      - MONGO_URI is set and non-empty → pymongo.MongoClient(MONGO_URI,
          serverSelectionTimeoutMS=5000). pymongo is lazy: it does NOT open a
          network connection until the first operation, so this is import-safe.
      - MONGO_URI is unset / empty → mongomock.MongoClient() (in-memory,
          no network, zero side effects).

    The client is cached in the module global _client; a second call returns
    the same object (singleton).
    """
    global _client
    if _client is None:
        mongo_uri = os.environ.get("MONGO_URI")
        if mongo_uri:
            _client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        else:
            _client = mongomock.MongoClient()
    return _client


def get_database():
    """Return the database object from the shared client.

    DB_NAME env var selects the database name; defaults to "gtm_db".
    The env var is read inside this function so monkeypatching works in tests.
    """
    db_name = os.environ.get("DB_NAME", "gtm_db")
    return get_mongo_client()[db_name]


def using_real_mongo() -> bool:
    """Return True iff a real MongoDB is configured (MONGO_URI is set and non-empty).

    Reads the env inside the function (consistent with get_mongo_client) so that
    monkeypatching in tests takes effect.  This is the gate used by the stores to
    decide whether to create indexes — indexes are a safety net for real Mongo only;
    mongomock does not need them and silently ignores them in some versions.
    """
    return bool(os.environ.get("MONGO_URI"))
