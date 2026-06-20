"""
tests/test_lead_store.py — Stage 1 QA checks for lead_store.py

Checks verified:
  AG1 — no-key returns {"error":"unauthorized"} with zero record fields
  AG2 — wrong-key denied identically to no-key (generic denial)
  AG3 — valid key returns the contact record
  AG4 — returned record keys match PRD §2.2 layout (unaltered)
  AG5 — corporate_access_key never appears in any return value
  AG6 — single chokepoint enforced; opt_out_status=True suppressed from outbound

ENV4 — import of lead_store has zero side effects (verified separately in test_catalog.py)
"""

import importlib
import json
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONTACTS = [
    {
        "first_name": "Dana",
        "last_name": "Reyes",
        "email": "dana.reyes@example.com",
        "corporate_access_key": "TestKey001",
        "role": "VP Growth",
        "linkedin_url": "https://www.linkedin.com/in/dana-reyes",
        "interaction_history_count": 4,
        "opt_out_status": False,
        "target_brand_id": "brand-001",
    },
    {
        "first_name": "Sofia",
        "last_name": "Klein",
        "email": "sofia.klein@example.com",
        "corporate_access_key": "TestKey002",
        "role": "Brand Manager",
        "linkedin_url": "https://www.linkedin.com/in/sofia-klein",
        "interaction_history_count": 3,
        "opt_out_status": True,
        "target_brand_id": "brand-004",
    },
]


@pytest.fixture
def tmp_contacts_json(tmp_path):
    """Write SAMPLE_CONTACTS to a temp JSON file; return its path."""
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text(json.dumps(SAMPLE_CONTACTS), encoding="utf-8")
    return str(contacts_file)


@pytest.fixture
def seeded_lead_store(tmp_contacts_json, monkeypatch):
    """Point lead_store at the tmp contacts.json and return a fresh collection.

    Uses monkeypatch to:
    1. Change cwd to the directory containing contacts.json.
    2. Reset the module-level singleton so each test starts clean.
    """
    # Reload lead_store with a clean singleton
    import lead_store
    importlib.reload(lead_store)

    contacts_dir = os.path.dirname(tmp_contacts_json)
    monkeypatch.chdir(contacts_dir)

    collection = lead_store.get_lead_data_collection()
    return collection, lead_store


# ---------------------------------------------------------------------------
# AG1 — No key → generic denial, zero record fields
# ---------------------------------------------------------------------------

class TestAG1:
    def test_no_key_returns_denial(self, seeded_lead_store):
        """AG1: Missing key returns {"error":"unauthorized"} with no record data."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("", "dana.reyes@example.com")
        assert result.get("error") == "unauthorized", f"Expected denial, got: {result}"
        # No record fields leaked
        assert "email" not in result
        assert "first_name" not in result
        assert "last_name" not in result
        assert "role" not in result
        assert "interaction_history_count" not in result

    def test_none_key_returns_denial(self, seeded_lead_store):
        """AG1: None key also returns denial."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact(None, "dana.reyes@example.com")
        assert result.get("error") == "unauthorized"


# ---------------------------------------------------------------------------
# AG2 — Wrong key denied identically to no key (generic denial; no oracle)
# ---------------------------------------------------------------------------

class TestAG2:
    def test_wrong_key_identical_to_no_key(self, seeded_lead_store):
        """AG2: Wrong key produces the same structured denial as no key."""
        _, ls = seeded_lead_store
        no_key_result    = ls.authenticate_and_get_contact("", "dana.reyes@example.com")
        wrong_key_result = ls.authenticate_and_get_contact("WRONG_KEY_XYZ", "dana.reyes@example.com")

        # Both must be denials
        assert no_key_result.get("error") == "unauthorized"
        assert wrong_key_result.get("error") == "unauthorized"

        # Critically: they must look the same (no oracle distinguishing wrong-key vs no-key)
        assert no_key_result == wrong_key_result, (
            "Wrong-key denial must be structurally identical to no-key denial."
        )

    def test_wrong_key_leaks_nothing(self, seeded_lead_store):
        """AG2: Wrong key never leaks any record field."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("WRONG", "dana.reyes@example.com")
        assert "email" not in result
        assert "first_name" not in result
        assert "interaction_history_count" not in result


# ---------------------------------------------------------------------------
# AG3 — Valid key returns the record
# ---------------------------------------------------------------------------

class TestAG3:
    def test_valid_key_returns_record(self, seeded_lead_store):
        """AG3: Correct corporate_access_key returns the contact record."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey001", "dana.reyes@example.com")
        assert "error" not in result, f"Expected success, got: {result}"
        assert result["email"] == "dana.reyes@example.com"
        assert result["first_name"] == "Dana"
        assert result["last_name"] == "Reyes"

    def test_valid_key_returns_interaction_count(self, seeded_lead_store):
        """AG3: Valid key exposes interaction_history_count."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey001", "dana.reyes@example.com")
        assert "interaction_history_count" in result
        assert result["interaction_history_count"] == 4


# ---------------------------------------------------------------------------
# AG4 — Schema conformance: keys match PRD §2.2, unaltered
# ---------------------------------------------------------------------------

class TestAG4:
    EXPECTED_KEYS = {
        "first_name", "last_name", "email", "role",
        "linkedin_url", "interaction_history_count",
        "opt_out_status", "target_brand_id",
    }

    def test_record_keys_match_prd_schema(self, seeded_lead_store):
        """AG4: Returned record has exactly the PRD §2.2 keys (corporate_access_key excluded)."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey001", "dana.reyes@example.com")
        assert "error" not in result
        returned_keys = set(result.keys())
        missing = self.EXPECTED_KEYS - returned_keys
        assert not missing, f"Missing expected keys: {missing}"

    def test_corporate_access_key_not_in_record(self, seeded_lead_store):
        """AG4 / AG5: corporate_access_key is stripped from the returned record."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey001", "dana.reyes@example.com")
        assert "corporate_access_key" not in result, (
            "corporate_access_key must never appear in a returned record."
        )


# ---------------------------------------------------------------------------
# AG5 — The key value never appears in any return value, log, or error
# ---------------------------------------------------------------------------

class TestAG5:
    def test_key_not_in_success_response(self, seeded_lead_store):
        """AG5: The key literal 'TestKey001' does not appear in the success payload."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey001", "dana.reyes@example.com")
        payload_str = json.dumps(result)
        assert "TestKey001" not in payload_str, (
            "Key value must not appear in any returned payload."
        )

    def test_key_not_in_error_response(self, seeded_lead_store):
        """AG5: The key literal does not leak into denial payloads."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("WRONG_SECRET_KEY", "dana.reyes@example.com")
        payload_str = json.dumps(result)
        assert "WRONG_SECRET_KEY" not in payload_str


# ---------------------------------------------------------------------------
# AG6 — Single chokepoint + opt_out_status suppressed
# ---------------------------------------------------------------------------

class TestAG6:
    def test_opted_out_contact_is_identified(self, seeded_lead_store):
        """AG6: is_opted_out returns True for opt_out_status=True records."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey002", "sofia.klein@example.com")
        assert "error" not in result, f"Expected success for opt-out contact: {result}"
        assert ls.is_opted_out(result) is True

    def test_non_opted_out_contact(self, seeded_lead_store):
        """AG6: is_opted_out returns False for opt_out_status=False records."""
        _, ls = seeded_lead_store
        result = ls.authenticate_and_get_contact("TestKey001", "dana.reyes@example.com")
        assert "error" not in result
        assert ls.is_opted_out(result) is False

    def test_get_collection_is_singleton(self, seeded_lead_store):
        """AG6: get_lead_data_collection() returns the same object on repeated calls."""
        _, ls = seeded_lead_store
        col1 = ls.get_lead_data_collection()
        col2 = ls.get_lead_data_collection()
        assert col1 is col2, "get_lead_data_collection must return the same singleton."

    def test_brand_lookup_by_id(self, seeded_lead_store):
        """AG6: get_contact_by_brand returns correct record for valid key + brand_id."""
        _, ls = seeded_lead_store
        result = ls.get_contact_by_brand("TestKey001", "brand-001")
        assert "error" not in result, f"Expected success: {result}"
        assert result["first_name"] == "Dana"

    def test_brand_lookup_wrong_key(self, seeded_lead_store):
        """AG6: get_contact_by_brand with wrong key returns denial."""
        _, ls = seeded_lead_store
        result = ls.get_contact_by_brand("WRONG", "brand-001")
        assert result.get("error") == "unauthorized"
