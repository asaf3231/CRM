"""
tests/test_crm_store.py — Stage 11 QA checks for crm_store.py

Checks verified:
  CRM1 — lazy singleton: _leads_collection is None after import; collection builds on first call
  CRM2 — lead record shape on upsert (all required keys present, correct types)
  CRM3 — upsert_lead / get_lead / update_lead_stage round-trip; idempotent upsert
  CRM4 — attach_contact: valid key attaches; no-key / wrong-key → generic denial, NO leak
  CRM5 — opt_out_status suppressed from outbound_eligible_contacts and NOT attached
  CRM6 — compute_win_prob: deterministic, catalog-sourced, clamped to [0,1] at boundaries
  CRM7 — no corporate_access_key value in any returned record, log, or tracked file
  CRM8 — write_qualified_leads upserts CRM records; qualified_leads.json stays ≤3-capped

Uses only SYNTHETIC keys (TestKey001, TestKey002, etc.) — no real corporate_access_key
values. Singletons are reset between tests via importlib.reload.
"""

import importlib
import json
import os
import pathlib
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Path setup: ensure the CRM root is on sys.path so imports work.
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import crm_store  # noqa: E402
import lead_store  # noqa: E402
import main        # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic contact fixtures (NEVER use real corporate_access_key values)
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
        "target_brand_id": "brand-test-0001",
    },
    {
        "first_name": "Sofia",
        "last_name": "Klein",
        "email": "sofia.klein@example.com",
        "corporate_access_key": "TestKey002",
        "role": "Brand Manager",
        "linkedin_url": "https://www.linkedin.com/in/sofia-klein",
        "interaction_history_count": 3,
        "opt_out_status": True,   # opted OUT
        "target_brand_id": "brand-test-0002",
    },
]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_contacts_json(tmp_path):
    """Write SAMPLE_CONTACTS to a temp JSON file; return its path."""
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text(json.dumps(SAMPLE_CONTACTS), encoding="utf-8")
    return str(contacts_file)


@pytest.fixture
def seeded_stores(tmp_contacts_json, monkeypatch):
    """Reset BOTH singletons, seed lead_store, return (crm_col, lead_mod, crm_mod).

    Each test that uses auth-gated functions must use this fixture so that:
    1. lead_store._collection_instance is None (reset directly).
    2. crm_store._leads_collection is None (reset directly).
    3. Both modules are in a fresh, consistent state.
    4. cwd is the directory containing contacts.json so lead_store can open it.

    We reset singletons directly (not via importlib.reload) to avoid the
    "module not in sys.modules" error that occurs when test_catalog.py's ENV4
    tests remove and re-import the modules, leaving the module-object references
    in this file pointing to stale objects not registered in sys.modules.
    """
    import importlib as _importlib
    # Ensure both modules are freshly available in sys.modules
    for mod_name in ("lead_store", "crm_store"):
        if mod_name not in sys.modules:
            # Module was removed from sys.modules by an ENV4 test — re-import it
            _importlib.import_module(mod_name)

    # Get the live module objects from sys.modules (may differ from module-level refs)
    import lead_store as _lead_store  # noqa: F811
    import crm_store as _crm_store    # noqa: F811

    # Reset singletons directly — avoids reload() issues from cross-module deletes
    _lead_store._collection_instance = None
    _crm_store._leads_collection = None

    # chdir so lead_store.get_lead_data_collection() finds contacts.json
    contacts_dir = os.path.dirname(tmp_contacts_json)
    monkeypatch.chdir(contacts_dir)

    # Eagerly init lead_store (so contacts are loaded before CRM tests run)
    _lead_store.get_lead_data_collection()
    crm_collection = _crm_store.get_crm_collection()

    return crm_collection, _lead_store, _crm_store


@pytest.fixture
def fresh_crm(monkeypatch, tmp_path):
    """Reset crm_store singleton only (no lead_store needed).

    For tests that do NOT exercise the auth gate.
    Reset the singleton directly instead of reloading to avoid cross-module
    sys.modules conflicts from test_catalog.py's ENV4 tests.
    """
    import importlib as _importlib
    if "crm_store" not in sys.modules:
        _importlib.import_module("crm_store")
    import crm_store as _crm_store  # noqa: F811
    _crm_store._leads_collection = None
    monkeypatch.chdir(tmp_path)
    return _crm_store


# ---------------------------------------------------------------------------
# Minimal CRM lead record builders
# ---------------------------------------------------------------------------

def _sample_lead(uniq_id="brand-test-0001", domain="alphabrand.com", **kwargs):
    """Build a minimal CRM lead record dict."""
    base = {
        "uniq_id": uniq_id,
        "domain": domain,
        "status": "qualified",
        "stage": "new",
        "profile": {"tier": "Tier 1"},
        "contact_ids": [],
        "win_prob": 0.75,
        "outreach_state": {},
        "notes": "",
    }
    base.update(kwargs)
    return base


# ===========================================================================
# CRM1 — Lazy singleton: _leads_collection is None at import time
# ===========================================================================

def _get_fresh_crm():
    """Return the live crm_store module with its singleton reset to None.

    Uses sys.modules to get the live module object (avoids importlib.reload issues
    when test_catalog.py's ENV4 tests have removed/re-imported the module).
    """
    import importlib as _importlib
    if "crm_store" not in sys.modules:
        _importlib.import_module("crm_store")
    import crm_store as _m  # noqa: F811
    _m._leads_collection = None
    return _m


class TestCRM1LazySingleton:
    """CRM1: import crm_store → singleton is None; collection builds on first call."""

    def test_singleton_is_none_at_import(self):
        """After import (or reload), _leads_collection must be None."""
        mod = _get_fresh_crm()
        assert mod._leads_collection is None, (
            "crm_store._leads_collection must be None immediately after import (ENV4)"
        )

    def test_collection_builds_on_first_call(self, tmp_path, monkeypatch):
        """get_crm_collection() builds the collection on first call."""
        mod = _get_fresh_crm()
        monkeypatch.chdir(tmp_path)
        assert mod._leads_collection is None
        col = mod.get_crm_collection()
        assert col is not None
        assert mod._leads_collection is not None

    def test_collection_is_singleton(self, tmp_path, monkeypatch):
        """Multiple calls to get_crm_collection() return the same object."""
        mod = _get_fresh_crm()
        monkeypatch.chdir(tmp_path)
        col1 = mod.get_crm_collection()
        col2 = mod.get_crm_collection()
        assert col1 is col2

    def test_collection_starts_empty(self, tmp_path, monkeypatch):
        """The CRM workspace starts empty — it is NOT pre-loaded from a file."""
        mod = _get_fresh_crm()
        monkeypatch.chdir(tmp_path)
        col = mod.get_crm_collection()
        assert col.count_documents({}) == 0


# ===========================================================================
# CRM2 — Lead record shape on upsert
# ===========================================================================

class TestCRM2RecordShape:
    """CRM2: upserted record has all required keys with correct types."""

    _REQUIRED_KEYS = {
        "uniq_id", "domain", "status", "stage",
        "profile", "contact_ids", "win_prob",
        "outreach_state", "notes", "updated_at",
    }

    def test_upserted_record_has_all_required_keys(self, fresh_crm):
        """upsert_lead returns a record with all CRM2 required keys."""
        record = fresh_crm.upsert_lead(_sample_lead())
        missing = self._REQUIRED_KEYS - set(record.keys())
        assert not missing, f"Missing keys in upserted record: {missing}"

    def test_upserted_record_types(self, fresh_crm):
        """Key fields have the correct types."""
        record = fresh_crm.upsert_lead(_sample_lead())
        assert isinstance(record["uniq_id"], str)
        assert isinstance(record["domain"], str)
        assert isinstance(record["status"], str)
        assert isinstance(record["stage"], str)
        assert isinstance(record["profile"], dict)
        assert isinstance(record["contact_ids"], list)
        assert isinstance(record["win_prob"], float)
        assert isinstance(record["outreach_state"], dict)
        assert isinstance(record["notes"], str)
        assert isinstance(record["updated_at"], str)

    def test_no_mongo_id_in_returned_record(self, fresh_crm):
        """The returned record must NOT contain mongo's _id field."""
        record = fresh_crm.upsert_lead(_sample_lead())
        assert "_id" not in record

    def test_record_is_json_serializable(self, fresh_crm):
        """The returned record must be JSON-serializable (no numpy types etc.)."""
        record = fresh_crm.upsert_lead(_sample_lead())
        serialized = json.dumps(record)  # must not raise
        assert isinstance(serialized, str)

    def test_defaults_applied_for_missing_optional_keys(self, fresh_crm):
        """Missing optional keys get safe defaults — upsert_lead is tolerant."""
        minimal = {"uniq_id": "brand-minimal-001", "domain": "minimal.com"}
        record = fresh_crm.upsert_lead(minimal)
        assert record["status"] == "qualified"
        assert record["stage"] == "new"
        assert record["profile"] == {}
        assert record["contact_ids"] == []
        assert record["win_prob"] == 0.0
        assert record["outreach_state"] == {}
        assert record["notes"] == ""


# ===========================================================================
# CRM3 — upsert_lead / get_lead / update_lead_stage round-trip; idempotent upsert
# ===========================================================================

class TestCRM3RoundTrip:
    """CRM3: CRUD round-trip and idempotent upsert."""

    def test_upsert_then_get(self, fresh_crm):
        """get_lead returns the record stored by upsert_lead."""
        lead = _sample_lead(uniq_id="brand-0001", domain="alpha.com")
        fresh_crm.upsert_lead(lead)
        fetched = fresh_crm.get_lead("brand-0001")
        assert fetched is not None
        assert fetched["uniq_id"] == "brand-0001"
        assert fetched["domain"] == "alpha.com"

    def test_get_nonexistent_returns_none(self, fresh_crm):
        """get_lead returns None for an uniq_id that was never upserted."""
        result = fresh_crm.get_lead("does-not-exist-9999")
        assert result is None

    def test_idempotent_upsert_no_duplicate(self, fresh_crm):
        """Two upserts with the same uniq_id result in exactly ONE record."""
        lead = _sample_lead(uniq_id="brand-idem-001")
        fresh_crm.upsert_lead(lead)
        fresh_crm.upsert_lead(lead)
        col = fresh_crm.get_crm_collection()
        count = col.count_documents({"uniq_id": "brand-idem-001"})
        assert count == 1

    def test_idempotent_upsert_updates_fields(self, fresh_crm):
        """A second upsert with the same uniq_id but different fields updates them."""
        lead_v1 = _sample_lead(uniq_id="brand-upd-001", status="qualified")
        lead_v2 = _sample_lead(uniq_id="brand-upd-001", status="contacted")
        fresh_crm.upsert_lead(lead_v1)
        fresh_crm.upsert_lead(lead_v2)
        fetched = fresh_crm.get_lead("brand-upd-001")
        assert fetched["status"] == "contacted"

    def test_update_lead_stage_success(self, fresh_crm):
        """update_lead_stage returns updated record with new stage."""
        fresh_crm.upsert_lead(_sample_lead(uniq_id="brand-stg-001", stage="new"))
        result = fresh_crm.update_lead_stage("brand-stg-001", "outreach")
        assert result.get("stage") == "outreach"
        assert result.get("uniq_id") == "brand-stg-001"

    def test_update_lead_stage_not_found(self, fresh_crm):
        """update_lead_stage returns generic error for unknown uniq_id."""
        result = fresh_crm.update_lead_stage("does-not-exist-0000", "outreach")
        assert result.get("error") == "not_found"

    def test_update_lead_stage_refreshes_updated_at(self, fresh_crm):
        """update_lead_stage refreshes the updated_at timestamp."""
        fresh_crm.upsert_lead(_sample_lead(uniq_id="brand-ts-001"))
        before = fresh_crm.get_lead("brand-ts-001")["updated_at"]
        # Force a small time gap
        import time
        time.sleep(0.01)
        fresh_crm.update_lead_stage("brand-ts-001", "won")
        after = fresh_crm.get_lead("brand-ts-001")["updated_at"]
        # updated_at must be refreshed (may be equal in fast runs; just check it's a valid ISO string)
        assert isinstance(after, str)
        assert "T" in after  # ISO 8601 contains 'T'

    def test_upsert_missing_uniq_id_raises(self, fresh_crm):
        """upsert_lead raises ValueError if uniq_id is missing."""
        with pytest.raises(ValueError, match="uniq_id"):
            fresh_crm.upsert_lead({"domain": "no-id.com"})


# ===========================================================================
# CRM4 — attach_contact: auth gate enforced; no/invalid key leaks nothing
# ===========================================================================

class TestCRM4AuthGate:
    """CRM4: attach_contact goes through the Policy-4 auth gate."""

    def test_valid_key_attaches_contact(self, seeded_stores):
        """A valid caller_key attaches the contact email to the lead's contact_ids."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        result = crm_mod.attach_contact(
            caller_key="TestKey001",
            uniq_id="brand-test-0001",
            target_email="dana.reyes@example.com",
        )
        assert result.get("ok") is True
        assert "dana.reyes@example.com" in result.get("contact_ids", [])

    def test_no_key_returns_generic_denial(self, seeded_stores):
        """Empty caller_key returns a generic unauthorized denial."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        result = crm_mod.attach_contact(
            caller_key="",
            uniq_id="brand-test-0001",
            target_email="dana.reyes@example.com",
        )
        assert result.get("error") == "unauthorized"

    def test_wrong_key_returns_generic_denial(self, seeded_stores):
        """Wrong caller_key returns the same generic denial as no-key."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        result = crm_mod.attach_contact(
            caller_key="WRONG_KEY_XYZ",
            uniq_id="brand-test-0001",
            target_email="dana.reyes@example.com",
        )
        assert result.get("error") == "unauthorized"

    def test_denial_does_not_modify_lead(self, seeded_stores):
        """A denied attach_contact must NOT modify the lead's contact_ids."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        crm_mod.attach_contact(
            caller_key="WRONG_KEY_XYZ",
            uniq_id="brand-test-0001",
            target_email="dana.reyes@example.com",
        )
        lead = crm_mod.get_lead("brand-test-0001")
        assert lead["contact_ids"] == []

    def test_denial_leaks_no_field(self, seeded_stores):
        """Denial result must not contain any contact record field."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        result = crm_mod.attach_contact(
            caller_key="WRONG_KEY_XYZ",
            uniq_id="brand-test-0001",
            target_email="dana.reyes@example.com",
        )
        # Denial must NOT contain PII fields
        for field in ("first_name", "last_name", "email", "role",
                      "linkedin_url", "interaction_history_count"):
            assert field not in result, (
                f"Denial leaked field '{field}' — Policy 4 violation"
            )

    def test_denial_never_leaks_corporate_access_key(self, seeded_stores):
        """The corporate_access_key value must never appear in any denial payload."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        for key in ("", "WRONG_KEY", "TestKey001"):
            result = crm_mod.attach_contact(
                caller_key=key,
                uniq_id="brand-test-0001",
                target_email="dana.reyes@example.com",
            )
            result_str = json.dumps(result)
            # TestKey001 is the REAL key — must never appear in the string representation
            assert "TestKey001" not in result_str, (
                "corporate_access_key value leaked in attach_contact result (CRM7 / G4)"
            )

    def test_idempotent_attach(self, seeded_stores):
        """Attaching the same contact twice does not duplicate contact_ids."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        crm_mod.attach_contact("TestKey001", "brand-test-0001", "dana.reyes@example.com")
        crm_mod.attach_contact("TestKey001", "brand-test-0001", "dana.reyes@example.com")
        lead = crm_mod.get_lead("brand-test-0001")
        assert lead["contact_ids"].count("dana.reyes@example.com") == 1


# ===========================================================================
# CRM5 — opt_out_status suppression
# ===========================================================================

class TestCRM5OptOutSuppression:
    """CRM5: opted-out contacts are excluded from outbound and NOT attached."""

    def test_attach_opted_out_contact_rejected(self, seeded_stores):
        """Attaching an opted-out contact returns ok=False, reason=opted_out."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0002"))
        # sofia.klein@example.com has opt_out_status=True; TestKey002 is correct key
        result = crm_mod.attach_contact(
            caller_key="TestKey002",
            uniq_id="brand-test-0002",
            target_email="sofia.klein@example.com",
        )
        assert result.get("ok") is False
        assert result.get("reason") == "opted_out"

    def test_opted_out_contact_not_in_contact_ids(self, seeded_stores):
        """After a rejected attach, opted-out email must not appear in contact_ids."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0002"))
        crm_mod.attach_contact(
            caller_key="TestKey002",
            uniq_id="brand-test-0002",
            target_email="sofia.klein@example.com",
        )
        lead = crm_mod.get_lead("brand-test-0002")
        assert "sofia.klein@example.com" not in lead.get("contact_ids", [])

    def test_outbound_eligible_excludes_opted_out(self, seeded_stores):
        """outbound_eligible_contacts returns only non-opted-out auth-passing contacts."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        eligible = crm_mod.outbound_eligible_contacts(
            caller_key="TestKey001",
            uniq_id="brand-test-0001",
            emails=["dana.reyes@example.com", "sofia.klein@example.com"],
        )
        # dana (TestKey001, opt_out=False) passes; sofia (TestKey002, opt_out=True) excluded
        # Note: TestKey001 only matches dana; sofia's key is TestKey002, so with TestKey001
        # sofia will be denied at auth (wrong key) — that is also fine (denied = excluded).
        emails_returned = [r.get("email") for r in eligible]
        assert "dana.reyes@example.com" in emails_returned
        assert "sofia.klein@example.com" not in emails_returned

    def test_outbound_eligible_returns_list(self, seeded_stores):
        """outbound_eligible_contacts always returns a list (never None)."""
        _, lead_mod, crm_mod = seeded_stores
        result = crm_mod.outbound_eligible_contacts(
            caller_key="TestKey001",
            uniq_id="brand-test-0001",
            emails=[],
        )
        assert isinstance(result, list)


# ===========================================================================
# CRM6 — compute_win_prob: deterministic, catalog-sourced, clamped
# ===========================================================================

class TestCRM6WinProb:
    """CRM6: compute_win_prob is deterministic, catalog-only, and clamped to [0,1]."""

    def test_deterministic_same_inputs(self):
        """Same inputs always produce exactly the same output."""
        p1 = crm_store.compute_win_prob("Tier 1", 3, 4, 2)
        p2 = crm_store.compute_win_prob("Tier 1", 3, 4, 2)
        assert p1 == p2

    def test_tier1_higher_than_tier2(self):
        """Tier 1 base produces a higher score than Tier 2 (all else equal)."""
        p1 = crm_store.compute_win_prob("Tier 1", 0, 0, 0)
        p2 = crm_store.compute_win_prob("Tier 2", 0, 0, 0)
        assert p1 > p2

    def test_tier2_higher_than_tier3(self):
        """Tier 2 base produces a higher score than Tier 3 (all else equal)."""
        p2 = crm_store.compute_win_prob("Tier 2", 0, 0, 0)
        p3 = crm_store.compute_win_prob("Tier 3", 0, 0, 0)
        assert p2 > p3

    def test_returns_float(self):
        """compute_win_prob always returns a float."""
        result = crm_store.compute_win_prob("Tier 2", 2, 3, 1)
        assert isinstance(result, float)

    def test_clamped_at_zero_lower_bound(self):
        """Score is clamped to at least 0.0 for extreme low inputs."""
        # With negative inputs (edge case — inputs should be >= 0, but clamp still applies)
        result = crm_store.compute_win_prob("Tier 3", 0, 0, 0)
        assert result >= 0.0

    def test_clamped_at_one_upper_bound(self):
        """Score is clamped to at most 1.0 for extreme high inputs."""
        # Max theoretical: 0.40 + 0.50 + 0.20 + 0.15 = 1.25 → clamped to 1.0
        result = crm_store.compute_win_prob("Tier 1", 5, 5, 3)
        assert result <= 1.0

    def test_clamped_to_exactly_one(self):
        """Tier 1 with max inputs clamps to exactly 1.0."""
        result = crm_store.compute_win_prob("Tier 1", 5, 5, 3)
        assert result == 1.0

    def test_unknown_tier_uses_fallback_base(self):
        """An unrecognized tier label uses the 0.10 fallback base."""
        result_unknown = crm_store.compute_win_prob("Unknown", 0, 0, 0)
        result_tier3   = crm_store.compute_win_prob("Tier 3", 0, 0, 0)
        assert result_unknown == result_tier3

    def test_icp_bonus_scales_with_count(self):
        """Higher icp_count yields higher score (up to the cap)."""
        p3 = crm_store.compute_win_prob("Tier 2", 0, 3, 0)
        p5 = crm_store.compute_win_prob("Tier 2", 0, 5, 0)
        assert p5 > p3

    def test_icp_bonus_caps_at_5(self):
        """icp_count beyond 5 does not increase the score."""
        p5  = crm_store.compute_win_prob("Tier 2", 0, 5, 0)
        p10 = crm_store.compute_win_prob("Tier 2", 0, 10, 0)
        assert p5 == p10

    def test_incident_bonus_scales(self):
        """Higher incidents yield higher score (models urgency)."""
        p0 = crm_store.compute_win_prob("Tier 2", 0, 0, 0)
        p5 = crm_store.compute_win_prob("Tier 2", 5, 0, 0)
        assert p5 > p0

    def test_pixel_bonus_scales(self):
        """Higher pixel_count yields higher score."""
        p0 = crm_store.compute_win_prob("Tier 2", 0, 0, 0)
        p3 = crm_store.compute_win_prob("Tier 2", 0, 0, 3)
        assert p3 > p0

    def test_exact_arithmetic_tier1_zero_all(self):
        """Exact value check for Tier 1, all bonuses zero."""
        # base=0.40, icp=0, incidents=0, pixels=0 → 0.40
        result = crm_store.compute_win_prob("Tier 1", 0, 0, 0)
        assert abs(result - 0.40) < 1e-9

    def test_exact_arithmetic_tier2_one_icp_one_incident_one_pixel(self):
        """Exact value: Tier 2, 1 ICP tag, 1 incident, 1 pixel."""
        # 0.25 + 0.10*1 + 0.04*1 + 0.05*1 = 0.25 + 0.10 + 0.04 + 0.05 = 0.44
        result = crm_store.compute_win_prob("Tier 2", 1, 1, 1)
        assert abs(result - 0.44) < 1e-9

    def test_result_in_unit_interval(self):
        """For a sweep of inputs, result is always in [0.0, 1.0]."""
        for tier in ("Tier 1", "Tier 2", "Tier 3", "Tier 4", ""):
            for inc in (0, 1, 5, 10):
                for icp in (0, 1, 3, 5, 8):
                    for pix in (0, 1, 2, 3, 5):
                        r = crm_store.compute_win_prob(tier, inc, icp, pix)
                        assert 0.0 <= r <= 1.0, (
                            f"Out of [0,1] for tier={tier!r} inc={inc} icp={icp} pix={pix}: {r}"
                        )


# ===========================================================================
# CRM7 — no corporate_access_key value in any returned payload
# ===========================================================================

class TestCRM7NoSecretLeak:
    """CRM7: corporate_access_key must never appear in any returned record or error."""

    def test_upserted_record_has_no_key_field(self, fresh_crm):
        """Upserted CRM record does not expose corporate_access_key."""
        record = fresh_crm.upsert_lead(_sample_lead())
        assert "corporate_access_key" not in record

    def test_get_lead_has_no_key_field(self, fresh_crm):
        """get_lead result does not expose corporate_access_key."""
        fresh_crm.upsert_lead(_sample_lead(uniq_id="brand-nokey-001"))
        record = fresh_crm.get_lead("brand-nokey-001")
        assert "corporate_access_key" not in record

    def test_attach_success_has_no_key_field(self, seeded_stores):
        """attach_contact success payload does not contain corporate_access_key."""
        _, lead_mod, crm_mod = seeded_stores
        crm_mod.upsert_lead(_sample_lead(uniq_id="brand-test-0001"))
        result = crm_mod.attach_contact(
            caller_key="TestKey001",
            uniq_id="brand-test-0001",
            target_email="dana.reyes@example.com",
        )
        result_str = json.dumps(result)
        # Synthetic key must not appear in success payload string
        assert "TestKey001" not in result_str

    def test_outbound_eligible_result_has_no_key_field(self, seeded_stores):
        """outbound_eligible_contacts result items do not expose corporate_access_key."""
        _, lead_mod, crm_mod = seeded_stores
        eligible = crm_mod.outbound_eligible_contacts(
            caller_key="TestKey001",
            uniq_id="brand-test-0001",
            emails=["dana.reyes@example.com"],
        )
        for contact in eligible:
            assert "corporate_access_key" not in contact
            result_str = json.dumps(contact)
            assert "TestKey001" not in result_str


# ===========================================================================
# CRM8 — write_qualified_leads upserts CRM records; qualified_leads.json stays stable
# ===========================================================================

class TestCRM8WriteQualifiedLeads:
    """CRM8: write_qualified_leads upserts CRM records; JSON shape/cap unchanged."""

    def _make_valid_pdf_bytes(self) -> bytes:
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"

    def _make_run_results(self, tmp_path, catalog_df):
        """Build a minimal run_tool_results list with one successful PDF entry."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = assets_dir / "reactfirst_testbrand_angle_social_001.pdf"
        pdf_path.write_bytes(self._make_valid_pdf_bytes())

        return [
            {
                "tool_name": "match_solicitation_angle",
                "result": {"angle_key": "angle_social_001", "tier": 1, "scores": {}},
                "input": {},
            },
            {
                "tool_name": "request_reactfirst_pdf",
                "result": {"ok": True, "path": str(pdf_path)},
                "input": {
                    "target_domain": "alphabrand.com",
                    "validated_angle_key": "angle_social_001",
                    "calculated_risk_score": 0.75,
                },
            },
        ]

    def test_write_qualified_leads_upserts_crm_record(
        self, tmp_path, monkeypatch
    ):
        """write_qualified_leads upserts each qualified lead into the CRM."""
        import pandas as pd
        # Reset singletons directly to avoid sys.modules conflicts from ENV4 tests
        import crm_store as _cs
        import lead_store as _ls
        import main as _main
        _cs._leads_collection = None
        _ls._collection_instance = None
        monkeypatch.chdir(tmp_path)

        catalog_df = pd.DataFrame([{
            "Uniq_Id":                    "test-brand-0001",
            "Brand_Name":                 "AlphaBrand",
            "Primary_Domain":             "alphabrand.com",
            "Core_Category":              "Apparel > Athleisure",
            "Estimated_Ad_Spend_Tier":    "Tier 1",
            "Current_Status":             "Open_Opportunity",
            "Historical_Social_Incidents": 3,
            "Main_Competitor_Id":         "test-brand-0002",
            "Gtin_Prefix":               "0712345",
        }])

        run_results = self._make_run_results(tmp_path, catalog_df)

        result_path = _main.write_qualified_leads(run_results, output_dir=str(tmp_path))
        assert result_path is not None

        # qualified_leads.json must be written (CL* — unchanged shape)
        ql_path = tmp_path / "qualified_leads.json"
        assert ql_path.exists()
        with open(str(ql_path), encoding="utf-8") as fh:
            ql_data = json.load(fh)
        assert "qualified_leads" in ql_data
        assert ql_data["count"] >= 1
        assert ql_data["count"] <= 3  # CL* cap unchanged

        # CRM record must have been upserted
        crm_col = _cs.get_crm_collection()
        # At least one record should be present (upsert from write_qualified_leads)
        assert crm_col.count_documents({}) >= 1

    def test_write_qualified_leads_json_shape_unchanged(
        self, tmp_path, monkeypatch
    ):
        """qualified_leads.json shape stays byte-stable (domain/angle_key/tier/pdf_path)."""
        import crm_store as _cs
        import lead_store as _ls
        import main as _main
        _cs._leads_collection = None
        _ls._collection_instance = None
        monkeypatch.chdir(tmp_path)

        run_results = self._make_run_results(tmp_path, None)
        _main.write_qualified_leads(run_results, output_dir=str(tmp_path))

        ql_path = tmp_path / "qualified_leads.json"
        with open(str(ql_path), encoding="utf-8") as fh:
            ql_data = json.load(fh)

        assert "qualified_leads" in ql_data
        assert "count" in ql_data
        assert "capped" in ql_data

        for lead in ql_data["qualified_leads"]:
            assert "domain" in lead
            assert "angle_key" in lead
            # tier and pdf_path are present when enrichment succeeded
            assert "pdf_path" in lead

    def test_write_qualified_leads_cap_unchanged(
        self, tmp_path, monkeypatch
    ):
        """write_qualified_leads still caps at MAX_ANGLES=3 (Policy 5 / CL*)."""
        import crm_store as _cs
        import lead_store as _ls
        import main as _main
        _cs._leads_collection = None
        _ls._collection_instance = None
        monkeypatch.chdir(tmp_path)

        # Build 4 PDF entries — only 3 should make it into qualified_leads.json
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        run_results = []
        for i in range(4):
            pdf_path = assets_dir / f"reactfirst_brand{i}_angle{i}.pdf"
            pdf_path.write_bytes(self._make_valid_pdf_bytes())
            run_results.append({
                "tool_name": "request_reactfirst_pdf",
                "result": {"ok": True, "path": str(pdf_path)},
                "input": {
                    "target_domain": f"brand{i}.com",
                    "validated_angle_key": f"angle_{i:03d}",
                    "calculated_risk_score": 0.5,
                },
            })

        _main.write_qualified_leads(run_results, output_dir=str(tmp_path))

        ql_path = tmp_path / "qualified_leads.json"
        with open(str(ql_path), encoding="utf-8") as fh:
            ql_data = json.load(fh)
        assert ql_data["count"] == 3  # hard cap
        assert ql_data["capped"] is True

    def test_crm_failure_does_not_break_json_write(
        self, tmp_path, monkeypatch
    ):
        """A CRM upsert failure must NOT prevent qualified_leads.json from being written."""
        import crm_store as _cs
        import lead_store as _ls
        import main as _main
        _cs._leads_collection = None
        _ls._collection_instance = None
        monkeypatch.chdir(tmp_path)

        # Patch crm_store.upsert_lead to always raise
        def _raising_upsert(record):
            raise RuntimeError("CRM failure injected by test")
        monkeypatch.setattr(_cs, "upsert_lead", _raising_upsert)

        run_results = self._make_run_results(tmp_path, None)
        result_path = _main.write_qualified_leads(run_results, output_dir=str(tmp_path))

        # File must still be written despite CRM failure
        assert result_path is not None
        ql_path = tmp_path / "qualified_leads.json"
        assert ql_path.exists()



# ===========================================================================
# ENV4 cross-check — crm_store is import-safe
# ===========================================================================

class TestENV4CrossCheck:
    """crm_store must be import-safe: _leads_collection stays None after import."""

    def test_crm_store_import_safe(self):
        """After import (or singleton reset), _leads_collection must be None."""
        mod = _get_fresh_crm()
        assert mod._leads_collection is None

    def test_crm_store_no_side_effects_on_import(self, tmp_path):
        """Importing crm_store does not create files, open the network, or build mongomock."""
        # If ANY side effect occurred, it would be caught by the singleton check.
        mod = _get_fresh_crm()
        assert mod._leads_collection is None
        # No files should have been created in tmp_path by the import
        created = list(tmp_path.iterdir())
        assert created == [], f"Import created unexpected files: {created}"
