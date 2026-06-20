"""
tests/test_contact_discovery.py — Stage 12: Layer 5b Profile Expander

Checks covered:
    DISC1  Contact-candidate return shape:
           {brand_id, contacts: [{first_name,last_name,role,email,linkedin_url}], count}
           JSON-serializable; count == len(contacts).
    DISC2  Injectable mocked client; deterministic under the mock; no live egress;
           de-duplication by email.
    DISC3  After a call the CRM lead for brand_id has the discovered emails in
           contact_ids (workspace metadata). The function NEVER touches lead_store
           private records — no stored corporate_access_key/private email appears in
           the output.  discover_contacts returns only the mocked candidate data.
    DISC4  Anti-leakage: no catalog/secret literals; len(TOOL_SCHEMAS) == 10;
           three-way name-identity holds; discover_contacts in dispatch.
    DISC5  Import-safety (ENV4): import main, lead_store, rag_engine, crm_store
           has zero side effects.

Mocking pattern mirrors tests/test_icp_builder.py (Stage 10):
    - monkeypatch main._get_client  → fake whose .messages.create() returns scripted resp.
    - monkeypatch main._vector_a_search → canned result (no network).
    - crm_store._leads_collection = None reset between tests (mirrors test_crm_store.py).

All synthetic data only — no real catalog literals, no contacts.json values.
"""

import json
import pathlib
import sys
import importlib
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure the CRM root is on sys.path so 'import main' works from tests/
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import main       # noqa: E402
import crm_store  # noqa: E402


# ===========================================================================
# Shared fixtures / helpers
# ===========================================================================

# Synthetic brand data — no real catalog literals
_SYNTH_BRAND_ID = "synth-brand-disc-001"
_SYNTH_DOMAIN   = "discovertest.example.com"

# Canned candidate list returned by the mocked LLM
_CANNED_CONTACTS = [
    {
        "first_name":   "Alice",
        "last_name":    "Brand",
        "role":         "VP Marketing",
        "email":        "alice@discovertest.example.com",
        "linkedin_url": "https://linkedin.com/in/alicebrand",
    },
    {
        "first_name":   "Bob",
        "last_name":    "Growth",
        "role":         "Head of Growth",
        "email":        "bob@discovertest.example.com",
        "linkedin_url": "",
    },
]

# Canned grounded discovery result
_CANNED_GROUNDED = {
    "domains": ["discovertest.example.com"],
    "status": "ok",
    "error": None,
}


def _make_fake_client(canned_list: list):
    """Return a fake Anthropic client whose messages.create() returns a canned JSON array."""
    canned_json = json.dumps(canned_list)
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(text=canned_json)],
        stop_reason="end_turn",
    )
    fake_messages = SimpleNamespace(
        create=MagicMock(return_value=fake_response)
    )
    return SimpleNamespace(messages=fake_messages)


@pytest.fixture(autouse=True)
def reset_crm_store():
    """Reset the crm_store singleton before each test (mirrors test_crm_store.py)."""
    crm_store._leads_collection = None
    yield
    crm_store._leads_collection = None


# ===========================================================================
# DISC1 — Return shape, types, JSON-serializable, count == len(contacts)
# ===========================================================================

class TestDisc1Shape:
    def test_return_has_required_keys(self, monkeypatch):
        """DISC1: Result dict has exactly brand_id, contacts, count."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        assert "brand_id" in result, "Missing key: brand_id"
        assert "contacts" in result, "Missing key: contacts"
        assert "count"    in result, "Missing key: count"
        # No unexpected top-level keys (allow only the three required)
        extra = set(result.keys()) - {"brand_id", "contacts", "count"}
        assert not extra, f"Unexpected extra keys in result: {extra}"

    def test_brand_id_is_string(self, monkeypatch):
        """DISC1: brand_id is a string."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert isinstance(result["brand_id"], str)

    def test_contacts_is_list(self, monkeypatch):
        """DISC1: contacts is a list."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert isinstance(result["contacts"], list)

    def test_count_equals_len_contacts(self, monkeypatch):
        """DISC1: count == len(contacts)."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert result["count"] == len(result["contacts"]), (
            f"count={result['count']} != len(contacts)={len(result['contacts'])}"
        )

    def test_each_contact_has_five_keys(self, monkeypatch):
        """DISC1: Each contact dict has exactly first_name, last_name, role, email, linkedin_url."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        required_keys = {"first_name", "last_name", "role", "email", "linkedin_url"}
        for i, contact in enumerate(result["contacts"]):
            assert set(contact.keys()) == required_keys, (
                f"Contact[{i}] has wrong keys: {set(contact.keys())}"
            )

    def test_each_contact_value_is_string(self, monkeypatch):
        """DISC1: All contact field values are strings."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        for i, contact in enumerate(result["contacts"]):
            for k, v in contact.items():
                assert isinstance(v, str), (
                    f"Contact[{i}]['{k}'] is {type(v).__name__}, expected str"
                )

    def test_result_is_json_serializable(self, monkeypatch):
        """DISC1: Result is fully JSON-serializable."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        try:
            serialised = json.dumps(result)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"discover_contacts result is not JSON-serializable: {exc}")
        reparsed = json.loads(serialised)
        assert reparsed["brand_id"] == result["brand_id"]
        assert reparsed["count"] == result["count"]

    def test_brand_id_echoed_back(self, monkeypatch):
        """DISC1: brand_id in the result matches the input."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert result["brand_id"] == _SYNTH_BRAND_ID


# ===========================================================================
# DISC2 — Deterministic under the mock; de-dup by email; no live egress
# ===========================================================================

class TestDisc2Determinism:
    def test_deterministic_under_mock_two_calls(self, monkeypatch):
        """DISC2: Two calls with the same mock → identical results."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        r1 = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        # reset crm singleton so the upsert starts fresh for the second call
        crm_store._leads_collection = None
        r2 = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        assert r1["count"] == r2["count"], "count differs between two identical calls"
        assert r1["contacts"] == r2["contacts"], "contacts differ between two identical calls"

    def test_dedup_by_email(self, monkeypatch):
        """DISC2: Duplicate emails in the LLM response produce only one contact."""
        duplicate_list = [
            {
                "first_name": "Alice",
                "last_name":  "Brand",
                "role":       "VP Marketing",
                "email":      "alice@discovertest.example.com",
                "linkedin_url": "",
            },
            {
                "first_name": "Alice",
                "last_name":  "Duplicate",
                "role":       "CMO",
                "email":      "alice@discovertest.example.com",  # same email → dedup
                "linkedin_url": "",
            },
        ]
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(duplicate_list))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert result["count"] == 1, f"Expected 1 after de-dup, got {result['count']}"
        assert len(result["contacts"]) == 1

    def test_dedup_is_case_insensitive(self, monkeypatch):
        """DISC2: Email de-dup is case-insensitive."""
        mixed_case_list = [
            {
                "first_name": "Alice", "last_name": "A", "role": "VP Marketing",
                "email": "Alice@DiscoverTest.Example.COM", "linkedin_url": "",
            },
            {
                "first_name": "Alice", "last_name": "B", "role": "CMO",
                "email": "alice@discovertest.example.com", "linkedin_url": "",
            },
        ]
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(mixed_case_list))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert result["count"] == 1, (
            f"Case-insensitive de-dup failed: got {result['count']} contacts"
        )

    def test_no_live_egress_without_api_key(self, monkeypatch):
        """DISC2: With mocked _get_client and _vector_a_search no real network call is made."""
        # If a live network call were attempted without a key it would raise KeyError/ValueError.
        # The mock intercepts it; if we reach the assertion without exception, egress is blocked.
        client_called = []

        def fake_client():
            client_called.append(True)
            return _make_fake_client(_CANNED_CONTACTS)

        monkeypatch.setattr(main, "_get_client", fake_client)
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert client_called, "_get_client was never called — implementation may have changed"

    def test_correct_contacts_returned(self, monkeypatch):
        """DISC2: Returned contacts match the canned mock data."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert result["count"] == len(_CANNED_CONTACTS)
        returned_emails = {c["email"] for c in result["contacts"]}
        expected_emails = {c["email"] for c in _CANNED_CONTACTS}
        assert returned_emails == expected_emails


# ===========================================================================
# DISC3 — CRM attachment; NO lead_store private-record bypass
# ===========================================================================

class TestDisc3Governance:
    def test_crm_lead_has_contact_ids_after_call(self, monkeypatch):
        """DISC3: After discover_contacts, the CRM lead has discovered emails in contact_ids."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        lead = crm_store.get_lead(_SYNTH_BRAND_ID)
        assert lead is not None, "CRM lead was not created"
        contact_ids = lead.get("contact_ids", [])
        expected_emails = {c["email"].lower() for c in _CANNED_CONTACTS}
        for email in expected_emails:
            assert email in contact_ids, (
                f"Expected email {email!r} in contact_ids, got: {contact_ids}"
            )

    def test_result_contains_no_corporate_access_key(self, monkeypatch):
        """DISC3: The result dict must not contain a corporate_access_key field."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        # Check at the top level
        assert "corporate_access_key" not in result, (
            "discover_contacts returned corporate_access_key at the top level"
        )
        # Check inside each contact
        for i, contact in enumerate(result.get("contacts", [])):
            assert "corporate_access_key" not in contact, (
                f"Contact[{i}] contains corporate_access_key"
            )

    def test_result_contains_no_interaction_history_count(self, monkeypatch):
        """DISC3: The result must not expose interaction_history_count (private field)."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        assert "interaction_history_count" not in result
        for contact in result.get("contacts", []):
            assert "interaction_history_count" not in contact

    def test_result_contacts_only_have_five_allowed_keys(self, monkeypatch):
        """DISC3: Each contact has ONLY the 5 allowed keys — no private fields leaked."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        allowed_keys = {"first_name", "last_name", "role", "email", "linkedin_url"}
        for i, contact in enumerate(result.get("contacts", [])):
            extra = set(contact.keys()) - allowed_keys
            assert not extra, (
                f"Contact[{i}] exposes private or unexpected keys: {extra}"
            )

    def test_lead_store_contacts_collection_not_read(self, monkeypatch):
        """DISC3: discover_contacts does not call lead_store.get_lead_data_collection."""
        import lead_store as ls

        get_collection_calls = []
        original = ls.get_lead_data_collection

        def spy_get_lead_data_collection():
            get_collection_calls.append(True)
            return original()

        monkeypatch.setattr(ls, "get_lead_data_collection", spy_get_lead_data_collection)
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        assert not get_collection_calls, (
            "discover_contacts called lead_store.get_lead_data_collection — "
            "this bypasses the Policy-4 auth gate"
        )

    def test_crm_lead_created_if_absent(self, monkeypatch):
        """DISC3: If no CRM lead exists, discover_contacts upserts a minimal record."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        # Confirm no lead exists before the call
        assert crm_store.get_lead(_SYNTH_BRAND_ID) is None

        main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        lead = crm_store.get_lead(_SYNTH_BRAND_ID)
        assert lead is not None, "CRM lead was not created for brand_id"
        assert lead["uniq_id"] == _SYNTH_BRAND_ID

    def test_empty_candidate_list_still_creates_lead(self, monkeypatch):
        """DISC3: Even with no discovered contacts, a CRM lead record is upserted."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client([]))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        assert result["count"] == 0
        assert result["contacts"] == []
        # Lead should still be upserted
        lead = crm_store.get_lead(_SYNTH_BRAND_ID)
        assert lead is not None, "CRM lead not created even when no contacts were found"

    def test_existing_contact_ids_preserved(self, monkeypatch):
        """DISC3: Calling discover_contacts adds to existing contact_ids (append, not replace)."""
        # Pre-populate a CRM lead with one existing contact_id
        crm_store.upsert_lead({
            "uniq_id": _SYNTH_BRAND_ID,
            "domain": _SYNTH_DOMAIN,
            "contact_ids": ["pre-existing@example.com"],
        })

        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)

        lead = crm_store.get_lead(_SYNTH_BRAND_ID)
        contact_ids = lead.get("contact_ids", [])
        assert "pre-existing@example.com" in contact_ids, (
            "Pre-existing contact_id was removed — should have been preserved"
        )
        # Also check the newly discovered ones were added
        for c in _CANNED_CONTACTS:
            assert c["email"].lower() in contact_ids, (
                f"Newly discovered email {c['email']!r} not in contact_ids"
            )


# ===========================================================================
# DISC4 — Anti-leakage; tool count == 10; name-identity
# ===========================================================================

class TestDisc4AntiLeakage:
    def test_tool_count_is_10(self):
        """DISC4: len(TOOL_SCHEMAS) == 10 after Stage 12."""
        assert len(main.TOOL_SCHEMAS) == 10, (
            f"Expected 10 schemas (9 original + discover_contacts), got {len(main.TOOL_SCHEMAS)}"
        )

    def test_dispatch_count_is_10(self):
        """DISC4: len(TOOL_DISPATCH) == 10 after Stage 12."""
        assert len(main.TOOL_DISPATCH) == 10, (
            f"Expected 10 dispatch entries, got {len(main.TOOL_DISPATCH)}"
        )

    def test_discover_contacts_in_tool_schemas(self):
        """DISC4: discover_contacts schema is present in TOOL_SCHEMAS."""
        names = [s["name"] for s in main.TOOL_SCHEMAS]
        assert "discover_contacts" in names, (
            f"discover_contacts not found in TOOL_SCHEMAS; found: {names}"
        )

    def test_discover_contacts_in_tool_dispatch(self):
        """DISC4: discover_contacts is in TOOL_DISPATCH."""
        assert "discover_contacts" in main.TOOL_DISPATCH, (
            "discover_contacts not in TOOL_DISPATCH"
        )

    def test_discover_contacts_dispatch_points_to_function(self):
        """DISC4: TOOL_DISPATCH['discover_contacts'] is main.discover_contacts."""
        fn = main.TOOL_DISPATCH.get("discover_contacts")
        assert fn is main.discover_contacts, (
            "TOOL_DISPATCH['discover_contacts'] does not point to main.discover_contacts"
        )

    def test_three_way_name_identity(self):
        """DISC4: schema name == dispatch key == function name (three-way identity)."""
        for schema in main.TOOL_SCHEMAS:
            name = schema["name"]
            assert name in main.TOOL_DISPATCH, f"Schema name '{name}' not in TOOL_DISPATCH"
            fn = main.TOOL_DISPATCH[name]
            assert fn.__name__ == name, (
                f"TOOL_DISPATCH['{name}'].__name__ == '{fn.__name__}' (mismatch)"
            )

    def test_no_catalog_literals_in_function_source(self):
        """DISC4 (G2): discover_contacts source must not contain real catalog literals.

        We check that neither brand names, domains, nor Uniq_Id-style UUIDs from the
        synthetic fixture appear in the function's source code.
        """
        import inspect
        source = inspect.getsource(main.discover_contacts)
        forbidden_fragments = [
            # Real brand / domain patterns that could indicate hardcoding
            "northwind", "crater", "verdewave", "nimbus", "lumenwave",
            # contacts.json key patterns
            "TestKey001", "TestKey002", "IntKeyValid",
        ]
        for fragment in forbidden_fragments:
            assert fragment.lower() not in source.lower(), (
                f"discover_contacts source contains forbidden literal: {fragment!r}"
            )

    def test_no_corporate_access_key_in_function_source(self):
        """DISC4 (G4): discover_contacts source must not contain any key value."""
        import inspect
        source = inspect.getsource(main.discover_contacts)
        # These are the synthetic key values used in tests — none should appear in the function
        forbidden_keys = ["Access99", "Cobalt7Key", "LumenAdmin42", "Verde2024",
                          "AtlasGrowthX", "PulseKey2025", "TestKey001", "TestKey002",
                          "IntKeyValidAlpha001", "IntKeyValidBeta002"]
        for key_val in forbidden_keys:
            assert key_val not in source, (
                f"discover_contacts source contains key value: {key_val!r}"
            )


# ===========================================================================
# DISC5 — Import-safety (ENV4)
# ===========================================================================

class TestDisc5ImportSafety:
    def test_import_side_effect_free(self, tmp_path, monkeypatch):
        """DISC5/ENV4: import main, lead_store, rag_engine, crm_store is side-effect-free.

        Removes the three input files from view and imports from a tmp dir.
        All lazy singletons must remain None after import.
        """
        import subprocess, sys as _sys, os

        # Build a minimal env that blocks real file discovery
        check_code = (
            "import sys\n"
            "sys.path.insert(0, repr(_CRM_ROOT)[1:-1])\n".replace("repr(_CRM_ROOT)[1:-1]", repr(str(_CRM_ROOT))) +
            "import main, lead_store, rag_engine, crm_store\n"
            "assert main._anthropic_client is None, 'anthropic client built at import'\n"
            "assert lead_store._collection_instance is None, 'lead_store collection built at import'\n"
            "assert crm_store._leads_collection is None, 'crm_store collection built at import'\n"
            "print('ENV4 DISC5 OK')\n"
        )

        # Write the check to a temp file and run it from a tmp cwd (no input files present)
        check_file = tmp_path / "check_import.py"
        check_file.write_text(check_code)

        result = subprocess.run(
            [_sys.executable, str(check_file)],
            cwd=str(tmp_path),   # no brands_catalog.csv / contacts.json / gtm_policies.txt here
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import side-effect check failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        assert "ENV4 DISC5 OK" in result.stdout

    def test_discover_contacts_callable_at_import(self):
        """DISC5: main.discover_contacts is callable (module-level function exists)."""
        assert callable(main.discover_contacts), "main.discover_contacts is not callable"

    def test_crm_store_singleton_none_at_import(self):
        """DISC5: crm_store._leads_collection is None after module import (lazy)."""
        # The autouse fixture already reset it; verify it's still None before any call
        assert crm_store._leads_collection is None, (
            "crm_store._leads_collection is not None at test start — "
            "the singleton was built at import time (violates ENV4)"
        )


# ===========================================================================
# Error-handling / robustness (CLAUDE.md §6.6 — tool errors are data)
# ===========================================================================

class TestErrorHandling:
    def test_missing_brand_id_returns_error(self, monkeypatch):
        """Tool error for empty brand_id is data, not crash."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client([]))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts("", _SYNTH_DOMAIN)
        assert "error" in result, "Expected error dict for empty brand_id"
        assert "discover_contacts failed" in result["error"]

    def test_missing_domain_returns_error(self, monkeypatch):
        """Tool error for empty domain is data, not crash."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client([]))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, "")
        assert "error" in result, "Expected error dict for empty domain"
        assert "discover_contacts failed" in result["error"]

    def test_llm_client_exception_returns_error(self, monkeypatch):
        """Tool error when LLM raises is data, not crash."""
        def bad_client():
            raise RuntimeError("Simulated LLM failure")

        monkeypatch.setattr(main, "_get_client", bad_client)
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        assert "error" in result, "Expected error dict when LLM raises"
        assert "discover_contacts failed" in result["error"]

    def test_malformed_llm_response_returns_empty_contacts(self, monkeypatch):
        """Malformed LLM JSON → empty contacts list (not a crash)."""
        malformed_response = SimpleNamespace(
            content=[SimpleNamespace(text="not-json-at-all {{{")],
            stop_reason="end_turn",
        )
        fake_messages = SimpleNamespace(create=MagicMock(return_value=malformed_response))
        fake_client = SimpleNamespace(messages=fake_messages)

        monkeypatch.setattr(main, "_get_client", lambda: fake_client)
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        # Should not crash; contacts may be empty
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert isinstance(result["contacts"], list)
        assert result["count"] == len(result["contacts"])

    def test_grounded_search_error_still_proceeds(self, monkeypatch):
        """DISC2: A grounded search failure is isolated — tool still attempts LLM step."""
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(_CANNED_CONTACTS))
        monkeypatch.setattr(
            main, "_vector_a_search",
            lambda q: {"domains": [], "status": "error", "error": "network timeout"},
        )

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        # Should not crash; LLM step still produces contacts
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["count"] == len(_CANNED_CONTACTS)

    def test_contacts_with_empty_email_skipped(self, monkeypatch):
        """DISC2: Contacts with an empty or blank email are skipped (not de-duped to one)."""
        list_with_blank_emails = [
            {"first_name": "Alice", "last_name": "A", "role": "VP", "email": "alice@example.com", "linkedin_url": ""},
            {"first_name": "Bob",   "last_name": "B", "role": "CMO", "email": "",   "linkedin_url": ""},
            {"first_name": "Carol", "last_name": "C", "role": "Dir", "email": "  ", "linkedin_url": ""},
        ]
        monkeypatch.setattr(main, "_get_client", lambda: _make_fake_client(list_with_blank_emails))
        monkeypatch.setattr(main, "_vector_a_search", lambda q: _CANNED_GROUNDED)

        result = main.discover_contacts(_SYNTH_BRAND_ID, _SYNTH_DOMAIN)
        # Only "alice@example.com" has a valid email
        assert result["count"] == 1, (
            f"Expected 1 valid contact (blank emails skipped), got {result['count']}"
        )
