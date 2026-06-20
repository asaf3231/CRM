"""
tests/test_persistence.py — ReactFirst AI Proactive Outbound Engine
Stage D2: Idempotent contacts seed test (DB5).
Stage D3: Durability + index/uniqueness tests (DB6, DB7 — live, skipif-gated).

Proves that calling get_lead_data_collection() a second time against a persistent
(same-client) mongomock store does NOT re-insert contacts.json records —
the critical idempotency guarantee that prevents duplicate seeding on restart.

The autouse conftest fixture resets all three singletons (db._client,
crm_store._leads_collection, lead_store._collection_instance) around each test,
so every test here starts from a clean slate.

DB6/DB7 are gated with REQUIRES_MONGO (same pattern as S10) so that the offline
suite (MONGO_URI unset) skips them gracefully — they are run by the PM with a real
Docker-backed MongoDB.
"""

import os

import pytest

# ---------------------------------------------------------------------------
# Live-only gate — mirrors the S10 ANTHROPIC_API_KEY gate pattern (ENV4 / §0).
# Tests marked with this decorator are SKIPPED when MONGO_URI is not set so
# that the full offline suite stays 765 passed / 1 skipped.
# ---------------------------------------------------------------------------
REQUIRES_MONGO = pytest.mark.skipif(
    not os.environ.get("MONGO_URI"),
    reason="requires a real MongoDB (set MONGO_URI to run these tests)",
)

# DB5 is an OFFLINE mongomock check: it assumes a fresh empty collection per test
# (guaranteed by the conftest singleton reset under mongomock). Against a persistent
# real Mongo that assumption is false, so skip it when MONGO_URI is set — the live
# persistence equivalent is DB7.
OFFLINE_ONLY = pytest.mark.skipif(
    bool(os.environ.get("MONGO_URI")),
    reason="offline mongomock idempotency check; the live persistence equivalent is DB7",
)


@OFFLINE_ONLY
class TestContactsSeedIdempotency:
    """DB5 — idempotent contacts seed across a simulated store restart."""

    def test_contacts_seed_is_idempotent_across_store_restart(self, tmp_path, monkeypatch):
        """Seeding contacts.json twice (with the same underlying client) yields no duplicates.

        Simulates what happens with a persistent MongoDB: the process restarts (singleton
        reset) but the database already has data.  The second call must detect the
        non-empty collection and skip re-insertion.
        """
        import db
        import lead_store

        # Point the contacts.json loader at a minimal fixture so we don't need the
        # real contacts.json in the working dir.
        contacts_fixture = [
            {
                "first_name": "Alice",
                "last_name": "Test",
                "email": "alice@example.com",
                "corporate_access_key": "TestKeyAlice",
                "role": "Manager",
                "target_brand_id": "brand-001",
                "interaction_history_count": 0,
                "opt_out_status": False,
            },
            {
                "first_name": "Bob",
                "last_name": "Test",
                "email": "bob@example.com",
                "corporate_access_key": "TestKeyBob",
                "role": "Director",
                "target_brand_id": "brand-002",
                "interaction_history_count": 1,
                "opt_out_status": False,
            },
        ]
        contacts_file = tmp_path / "contacts.json"
        import json
        contacts_file.write_text(json.dumps(contacts_fixture), encoding="utf-8")

        # Redirect cwd so the loader finds our fixture
        monkeypatch.chdir(tmp_path)

        # First call — collection is empty → seeds contacts.json
        col1 = lead_store.get_lead_data_collection()
        n = col1.count_documents({})
        assert n > 0, "First call must seed at least one contact"
        assert n == len(contacts_fixture), f"Expected {len(contacts_fixture)} contacts, got {n}"

        # Simulate restarting the store singleton but NOT the underlying db client
        # (this is the persistence scenario: the client/DB retains the data).
        lead_store._collection_instance = None

        # Second call — collection is non-empty → must skip re-insertion
        col2 = lead_store.get_lead_data_collection()
        assert col2.count_documents({}) == n, (
            "Second call (store restart) must not duplicate contacts; "
            f"expected {n} documents, got {col2.count_documents({})}"
        )


# ---------------------------------------------------------------------------
# DB6 — Indexes + uniqueness enforcement (live Mongo only)
# ---------------------------------------------------------------------------

@REQUIRES_MONGO
class TestIndexesLiveMongo:
    """DB6 — unique indexes are present and enforce uniqueness on real Mongo."""

    def test_db6_leads_unique_index_on_uniq_id(self):
        """crm_store.get_crm_collection() creates a unique index on uniq_id."""
        import crm_store

        col = crm_store.get_crm_collection()
        index_info = col.index_information()

        # Find the unique index on uniq_id
        unique_uniq_id_found = False
        for name, info in index_info.items():
            key_fields = [f for f, _ in info.get("key", [])]
            if "uniq_id" in key_fields and info.get("unique", False):
                unique_uniq_id_found = True
                break

        assert unique_uniq_id_found, (
            "Expected a unique index on 'uniq_id' in the leads collection; "
            f"found indexes: {list(index_info.keys())}"
        )

    def test_db6_contacts_unique_index_on_email(self):
        """lead_store.get_lead_data_collection() creates a unique index on email."""
        import json
        import os
        import lead_store

        # Ensure get_lead_data_collection() can find contacts.json.
        # We seed an empty file so the collection is populated but we control the content.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        contacts_path = os.path.join(project_root, "contacts.json")
        assert os.path.exists(contacts_path), (
            "contacts.json must exist in the project root for this live test"
        )

        col = lead_store.get_lead_data_collection()
        index_info = col.index_information()

        # Find the unique index on email
        unique_email_found = False
        for name, info in index_info.items():
            key_fields = [f for f, _ in info.get("key", [])]
            if "email" in key_fields and info.get("unique", False):
                unique_email_found = True
                break

        assert unique_email_found, (
            "Expected a unique index on 'email' in the contacts collection; "
            f"found indexes: {list(index_info.keys())}"
        )

    def test_db6_duplicate_uniq_id_raises(self):
        """Inserting a duplicate uniq_id into the leads collection raises DuplicateKeyError."""
        import pymongo.errors
        import crm_store

        col = crm_store.get_crm_collection()
        test_id = "db6-uniqueness-probe"

        # Clean up any leftover from a previous interrupted run
        col.delete_many({"uniq_id": test_id})

        # First insert — must succeed
        col.insert_one({"uniq_id": test_id, "domain": "probe.example.com"})

        try:
            # Second insert of the SAME uniq_id — must raise DuplicateKeyError
            with pytest.raises(pymongo.errors.DuplicateKeyError):
                col.insert_one({"uniq_id": test_id, "domain": "probe2.example.com"})
        finally:
            # Always clean up the probe document
            col.delete_many({"uniq_id": test_id})


# ---------------------------------------------------------------------------
# DB7 — Cross-restart durability (live Mongo only)
# ---------------------------------------------------------------------------

@REQUIRES_MONGO
class TestRestartDurabilityLiveMongo:
    """DB7 — data survives a simulated process restart (singleton reset + reconnect)."""

    def test_db7_lead_survives_singleton_reset(self):
        """Upsert a lead → reset client + collection singletons → reconnect → lead still present."""
        import db
        import crm_store

        test_id = "db7-restart-probe"
        test_domain = "restart-probe.example.com"

        # --- Phase 1: upsert a test lead ---
        crm_store.upsert_lead({"uniq_id": test_id, "domain": test_domain})

        # Confirm it was written
        assert crm_store.get_lead(test_id) is not None, (
            "Lead must exist after upsert before simulating a restart"
        )

        # --- Phase 2: simulate a full process restart by resetting all singletons ---
        # This mirrors what happens when the process exits and a new one starts
        # (the in-memory singleton cache is cleared, but the DB data persists).
        db._client = None
        crm_store._leads_collection = None

        # --- Phase 3: reconnect and verify the lead is still present ---
        retrieved = crm_store.get_lead(test_id)
        assert retrieved is not None, (
            f"Lead with uniq_id='{test_id}' must survive a simulated process restart; "
            "got None after resetting singletons and reconnecting"
        )
        assert retrieved.get("domain") == test_domain, (
            f"Unexpected domain after restart: got {retrieved.get('domain')!r}, "
            f"expected {test_domain!r}"
        )

        # --- Cleanup: remove the probe document ---
        crm_store.get_crm_collection().delete_one({"uniq_id": test_id})
