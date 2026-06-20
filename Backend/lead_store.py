"""
lead_store.py — ReactFirst AI Proactive Outbound Engine
MongoDB-backed CRM store + Policy 4 corporate_access_key authentication gate.

Import-safe: import of this module has ZERO side effects.
All heavy work (client construction, contacts.json load) happens lazily inside
get_lead_data_collection() on first call.
"""

import json
import os

import db

# ---------------------------------------------------------------------------
# Module-level singleton (None until first use)
# ---------------------------------------------------------------------------
_collection_instance = None


# ---------------------------------------------------------------------------
# Lazy singleton — PRD §2.2 exact pattern
# ---------------------------------------------------------------------------

def get_lead_data_collection():
    """Return the 'contacts' collection, loading contacts.json on first call (seed-if-empty).

    Pattern: lazy singleton — import-safe, no side effects at module level.
    The collection is obtained from db.get_database() so the same client is shared
    with crm_store; the offline suite uses mongomock (MONGO_URI unset) and a real
    MongoDB is used when MONGO_URI is set (DB4 / ENV4).

    Idempotent seed: contacts.json is only inserted when the collection is empty.
    A second call (e.g. after a process restart that reuses the same underlying
    client) does NOT re-insert and does NOT duplicate contact records (DB5).

    Database:   gtm_db  (or DB_NAME env var)
    Collection: contacts
    Source:     contacts.json (must exist in cwd at call time)
    """
    global _collection_instance
    if _collection_instance is None:
        collection = db.get_database()["contacts"]
        # Real-Mongo-only: create indexes as a uniqueness safety net.
        # Gated so that the mongomock path (MONGO_URI unset) is byte-identical
        # to the pre-D3 behaviour — no import-time or offline side effects (ENV4).
        if db.using_real_mongo():
            try:
                collection.create_index("email", unique=True)
                collection.create_index("target_brand_id")   # non-unique lookup
            except Exception:
                pass  # index creation is a real-Mongo safety net; never crash the getter
        # Idempotent seed: only load contacts.json when the collection is empty.
        # (An unconditional insert_many would DUPLICATE against a persistent Mongo
        # on every restart.)
        if collection.count_documents({}) == 0:
            contacts_path = os.path.join(os.getcwd(), "contacts.json")
            with open(contacts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                collection.insert_many(data)
        _collection_instance = collection
    return _collection_instance


# ---------------------------------------------------------------------------
# Policy 4 — Data Protection & Authentication Gate
# This is the SINGLE chokepoint to the contacts collection.
# No code path may reach the collection without passing through here.
# ---------------------------------------------------------------------------

def authenticate_and_get_contact(caller_key: str, target_email: str) -> dict:
    """Verify caller_key against the record's corporate_access_key field.

    Returns the sanitised contact record on success (key field stripped).
    Returns {"error": "unauthorized", "detail": "access denied"} on any
    failure — no-key, wrong-key, or missing record all produce the SAME
    response (generic denial; no existence oracle).

    The corporate_access_key value is NEVER included in any return payload,
    log message, or error string.

    Args:
        caller_key:   The key supplied by the caller (e.g. from the query text).
        target_email: Email address identifying the target contact record.

    Returns:
        dict — sanitised record on success; {"error": "unauthorized", ...} on failure.
    """
    _DENIAL = {"error": "unauthorized", "detail": "access denied"}

    # Reject immediately if no key provided (avoids any collection query)
    if not caller_key:
        return _DENIAL

    collection = get_lead_data_collection()
    # Query only by email — deliberately does NOT filter on caller_key in the
    # query itself; we fetch the record then compare in-memory to avoid leaking
    # which field caused the denial.
    record = collection.find_one({"email": target_email})

    if record is None:
        # Return the generic denial — do NOT reveal that the record doesn't exist.
        return _DENIAL

    stored_key = record.get("corporate_access_key", "")
    if stored_key != caller_key:
        return _DENIAL

    # Auth passed — build a sanitised view that omits the key.
    sanitised = {k: v for k, v in record.items() if k not in ("corporate_access_key", "_id")}
    return sanitised


def get_contact_by_brand(caller_key: str, target_brand_id: str) -> dict:
    """Auth-gated lookup by target_brand_id.

    Verifies caller_key against the record before returning any fields.
    Same denial semantics as authenticate_and_get_contact.

    Args:
        caller_key:      The key supplied by the caller.
        target_brand_id: The brand UUID (matches Uniq_Id in brands_catalog.csv).

    Returns:
        dict — sanitised record on success; {"error": "unauthorized", ...} on failure.
    """
    _DENIAL = {"error": "unauthorized", "detail": "access denied"}

    if not caller_key:
        return _DENIAL

    collection = get_lead_data_collection()
    record = collection.find_one({"target_brand_id": target_brand_id})

    if record is None:
        return _DENIAL

    stored_key = record.get("corporate_access_key", "")
    if stored_key != caller_key:
        return _DENIAL

    sanitised = {k: v for k, v in record.items() if k not in ("corporate_access_key", "_id")}
    return sanitised


def is_opted_out(contact_record: dict) -> bool:
    """Return True if the contact has opt_out_status=True.

    Suppresses the contact from outbound regardless of ICP fit.
    Accepts an already-authenticated (sanitised) record dict.
    """
    return bool(contact_record.get("opt_out_status", False))
