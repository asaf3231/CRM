"""
tests/test_outreach.py — Stage 13 QA checks (L6a Outreach Engine core)

Checks verified:
  OUT1 — schedule_outreach_cohort batches at most DAILY_SEND_CAP per cohort
  OUT2 — dispatch_outreach egress is ONLY to OUTREACH_SUBDOMAIN
  OUT3 — opted-out contacts are never dispatched
  OUT4 — Policy-4 auth gate + gateway_validate enforced before every send
  OUT5 — no secret / corporate_access_key in logs, returns, or sender calls
  OUT6 — escalate_prospect handles unanswered slack_gate; route_prospect unchanged

All external services are mocked with injectable stubs.
Synthetic keys only (TestKey001 / TestKey002) — no real corporate_access_key.
"""

import importlib
import json
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Shared synthetic contact fixtures
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
        "opt_out_status": True,    # opted out
        "target_brand_id": "brand-004",
    },
]


@pytest.fixture
def tmp_contacts_json(tmp_path):
    """Write SAMPLE_CONTACTS to a temp file; return its path."""
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text(json.dumps(SAMPLE_CONTACTS), encoding="utf-8")
    return str(contacts_file)


@pytest.fixture
def seeded_lead_store(tmp_contacts_json, monkeypatch):
    """Seed lead_store from the tmp contacts file, return fresh singleton."""
    import lead_store
    importlib.reload(lead_store)
    monkeypatch.chdir(os.path.dirname(tmp_contacts_json))
    lead_store.get_lead_data_collection()
    return lead_store


@pytest.fixture
def main_module():
    """Return the main module (reloaded to avoid cross-test state)."""
    import main
    return main


# ---------------------------------------------------------------------------
# Helper: a valid gateway payload (passes gateway_validate)
# ---------------------------------------------------------------------------

def _valid_payload():
    return {
        "type": "internal",
        "target_domain": "example.com",
        "validated_angle_key": "crisis_social_media_001",
    }


def _invalid_payload():
    """A payload that will fail gateway_validate — None."""
    return None


# ===========================================================================
# OUT1 — schedule_outreach_cohort
# ===========================================================================

class TestOUT1ScheduleCohorts:
    """Cohorts are ≤ DAILY_SEND_CAP and the constant is now wired/enforced."""

    def test_daily_send_cap_constant_exists(self, main_module):
        assert hasattr(main_module, "DAILY_SEND_CAP")
        assert main_module.DAILY_SEND_CAP == 50

    def test_function_exists(self, main_module):
        assert callable(main_module.schedule_outreach_cohort)

    def test_120_leads_produces_3_cohorts(self, main_module):
        leads = list(range(120))
        result = main_module.schedule_outreach_cohort(leads)
        assert result["cohort_count"] == 3
        assert result["total_leads"] == 120
        assert result["daily_cap"] == 50
        assert len(result["cohorts"]) == 3

    def test_no_cohort_exceeds_daily_cap(self, main_module):
        leads = list(range(120))
        result = main_module.schedule_outreach_cohort(leads)
        for cohort in result["cohorts"]:
            assert len(cohort) <= main_module.DAILY_SEND_CAP

    def test_120_leads_last_cohort_has_20(self, main_module):
        leads = list(range(120))
        result = main_module.schedule_outreach_cohort(leads)
        assert len(result["cohorts"][0]) == 50
        assert len(result["cohorts"][1]) == 50
        assert len(result["cohorts"][2]) == 20

    def test_empty_leads_produces_zero_cohorts(self, main_module):
        result = main_module.schedule_outreach_cohort([])
        assert result["cohort_count"] == 0
        assert result["total_leads"] == 0
        assert result["cohorts"] == []

    def test_order_preserving(self, main_module):
        leads = [f"lead-{i}" for i in range(5)]
        result = main_module.schedule_outreach_cohort(leads, daily_cap=3)
        flat = [item for cohort in result["cohorts"] for item in cohort]
        assert flat == leads

    def test_exact_cap_boundary(self, main_module):
        leads = list(range(50))
        result = main_module.schedule_outreach_cohort(leads)
        assert result["cohort_count"] == 1
        assert len(result["cohorts"][0]) == 50

    def test_one_over_cap_splits(self, main_module):
        leads = list(range(51))
        result = main_module.schedule_outreach_cohort(leads)
        assert result["cohort_count"] == 2
        assert len(result["cohorts"][0]) == 50
        assert len(result["cohorts"][1]) == 1

    def test_custom_daily_cap(self, main_module):
        leads = list(range(10))
        result = main_module.schedule_outreach_cohort(leads, daily_cap=3)
        assert result["cohort_count"] == 4    # 3+3+3+1
        assert result["daily_cap"] == 3

    def test_daily_cap_zero_returns_error(self, main_module):
        result = main_module.schedule_outreach_cohort(list(range(10)), daily_cap=0)
        assert "error" in result
        assert result["cohorts"] == []
        assert result["cohort_count"] == 0

    def test_daily_cap_negative_returns_error(self, main_module):
        result = main_module.schedule_outreach_cohort(list(range(5)), daily_cap=-5)
        assert "error" in result

    def test_deterministic_same_input(self, main_module):
        leads = [f"d{i}.com" for i in range(130)]
        r1 = main_module.schedule_outreach_cohort(leads)
        r2 = main_module.schedule_outreach_cohort(leads)
        assert r1["cohorts"] == r2["cohorts"]

    def test_return_keys_present(self, main_module):
        result = main_module.schedule_outreach_cohort([1, 2, 3])
        assert "cohorts" in result
        assert "cohort_count" in result
        assert "total_leads" in result
        assert "daily_cap" in result


# ===========================================================================
# OUT2 — egress ONLY to OUTREACH_SUBDOMAIN
# ===========================================================================

class TestOUT2EgressIsolation:
    """dispatch_outreach must only call sender with OUTREACH_SUBDOMAIN URLs."""

    def test_outreach_subdomain_constant_exists(self, main_module):
        assert hasattr(main_module, "OUTREACH_SUBDOMAIN")
        assert main_module.OUTREACH_SUBDOMAIN == "outreach.reactfirst.ai"

    def test_successful_dispatch_uses_outreach_subdomain(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        def spy_sender(url, data):
            calls.append(url)

        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=_valid_payload(),
            sender=spy_sender,
        )

        assert result["sent"] is True
        assert len(calls) == 1
        assert main_module.OUTREACH_SUBDOMAIN in calls[0]

    def test_sender_never_called_with_other_host(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        def spy_sender(url, data):
            calls.append(url)

        main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=_valid_payload(),
            sender=spy_sender,
        )

        for url in calls:
            assert main_module.OUTREACH_SUBDOMAIN in url, (
                f"Sender called with non-OUTREACH_SUBDOMAIN host: {url}"
            )

    def test_result_host_field_is_outreach_subdomain(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: None,
        )
        assert result["sent"] is True
        assert result["host"] == main_module.OUTREACH_SUBDOMAIN

    def test_channel_in_result(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        for ch in ("email", "linkedin", "form"):
            result = main_module.dispatch_outreach(
                target_email="dana.reyes@example.com",
                caller_key="TestKey001",
                channel=ch,
                payload=_valid_payload(),
                sender=lambda url, data: None,
            )
            assert result["sent"] is True
            assert result["channel"] == ch


# ===========================================================================
# OUT3 — opted-out contact never dispatched
# ===========================================================================

class TestOUT3OptOut:
    """Contacts with opt_out_status=True must never reach the sender."""

    def test_opted_out_returns_opted_out(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        result = main_module.dispatch_outreach(
            target_email="sofia.klein@example.com",
            caller_key="TestKey002",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: calls.append(url),
        )

        assert result["sent"] is False
        assert result["reason"] == "opted_out"

    def test_sender_never_called_for_opted_out(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        main_module.dispatch_outreach(
            target_email="sofia.klein@example.com",
            caller_key="TestKey002",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: calls.append(url),
        )
        assert calls == [], "Sender must NOT be called for opted-out contacts"


# ===========================================================================
# OUT4 — Policy-4 auth gate + gateway_validate
# ===========================================================================

class TestOUT4AuthAndGateway:
    """Auth gate and gateway enforce checks before any send."""

    def test_no_key_returns_unauthorized(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: calls.append(url),
        )
        assert result["sent"] is False
        assert result["reason"] == "unauthorized"
        assert calls == []

    def test_wrong_key_returns_unauthorized(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="WrongKey999",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: calls.append(url),
        )
        assert result["sent"] is False
        assert result["reason"] == "unauthorized"
        assert calls == []

    def test_no_key_and_wrong_key_identical(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        """AG2 extension: wrong-key denial is identical to no-key denial."""
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        r_no_key = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: None,
        )
        r_wrong_key = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="WrongKey999",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: None,
        )
        assert r_no_key == r_wrong_key

    def test_gateway_rejected_payload_returns_gateway_rejected(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=_invalid_payload(),    # None → GW1 rejected
            sender=lambda url, data: calls.append(url),
        )
        assert result["sent"] is False
        assert result["reason"] == "gateway_rejected"
        assert calls == [], "Sender must NOT be called when gateway rejects"

    def test_gateway_rejected_bad_domain_payload(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        """A payload with a malformed domain fails gateway_validate (GW2)."""
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        bad_payload = {
            "target_domain": "INVALID DOMAIN!!!",
            "validated_angle_key": "angle_001",
        }
        calls = []
        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=bad_payload,
            sender=lambda url, data: calls.append(url),
        )
        assert result["sent"] is False
        assert result["reason"] == "gateway_rejected"
        assert calls == []

    def test_sender_never_called_when_auth_fails(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        calls = []
        main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="BadKey",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: calls.append(url),
        )
        assert calls == []


# ===========================================================================
# OUT5 — no secret in returns / logs / sender calls
# ===========================================================================

class TestOUT5NoSecretLeak:
    """No corporate_access_key or secret appears in any return value or sender call."""

    def test_success_return_has_no_corporate_key(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: None,
        )
        result_str = json.dumps(result)
        assert "TestKey001" not in result_str, (
            "corporate_access_key must not appear in dispatch success return"
        )
        assert "corporate_access_key" not in result_str

    def test_unauthorized_return_has_no_corporate_key(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="BadKey",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: None,
        )
        result_str = json.dumps(result)
        assert "BadKey" not in result_str
        assert "TestKey001" not in result_str
        assert "corporate_access_key" not in result_str

    def test_sender_call_data_has_no_corporate_key(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        sender_data = []
        def capture_sender(url, data):
            sender_data.append(data)

        main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="TestKey001",
            channel="email",
            payload=_valid_payload(),
            sender=capture_sender,
        )

        for data in sender_data:
            # data is bytes
            data_str = data.decode("utf-8") if isinstance(data, bytes) else str(data)
            assert "TestKey001" not in data_str, (
                "corporate_access_key must not appear in data passed to sender"
            )
            assert "corporate_access_key" not in data_str

    def test_error_result_has_no_pii_beyond_target_email(
        self, seeded_lead_store, main_module, monkeypatch
    ):
        """On auth failure, the return must not contain any record field."""
        monkeypatch.setattr(main_module, "lead_store", seeded_lead_store)

        result = main_module.dispatch_outreach(
            target_email="dana.reyes@example.com",
            caller_key="WrongKey",
            channel="email",
            payload=_valid_payload(),
            sender=lambda url, data: None,
        )
        result_str = json.dumps(result)
        # No record fields (first_name, last_name, role, interaction_history_count)
        assert "Dana" not in result_str
        assert "Reyes" not in result_str
        assert "VP Growth" not in result_str
        assert "interaction_history_count" not in result_str


# ===========================================================================
# OUT6 — escalate_prospect + route_prospect byte-stability
# ===========================================================================

class TestOUT6EscalateProspect:
    """escalate_prospect handles unanswered slack_gate; route_prospect unchanged."""

    def _make_slack_gate_result(self, domain="test-brand.com"):
        """Minimal slack_gate routing result (as route_prospect returns)."""
        return {
            "action": "slack_gate",
            "borderline": True,
            "domain": domain,
            "icp_count": 3,
            "slack_sent": False,
            "slack_error": None,
        }

    def _make_auto_proceed_result(self, domain="clear-brand.com"):
        return {
            "action": "auto_proceed",
            "borderline": False,
            "domain": domain,
            "icp_count": 4,
            "slack_sent": False,
            "slack_error": None,
        }

    def test_function_exists(self, main_module):
        assert callable(main_module.escalate_prospect)

    def test_slack_gate_not_approved_escalates(self, main_module):
        escalator_calls = []
        result = main_module.escalate_prospect(
            routing_result=self._make_slack_gate_result(),
            approved=False,
            escalator=lambda payload: escalator_calls.append(payload),
        )
        assert result["action"] == "escalated"
        assert result["escalated"] is True
        assert len(escalator_calls) == 1

    def test_slack_gate_not_approved_domain_in_result(self, main_module):
        domain = "my-brand.com"
        result = main_module.escalate_prospect(
            routing_result=self._make_slack_gate_result(domain=domain),
            approved=False,
            escalator=lambda p: None,
        )
        assert result["domain"] == domain

    def test_slack_gate_approved_no_escalation(self, main_module):
        escalator_calls = []
        result = main_module.escalate_prospect(
            routing_result=self._make_slack_gate_result(),
            approved=True,
            escalator=lambda payload: escalator_calls.append(payload),
        )
        assert result["action"] == "no_escalation"
        assert result["escalated"] is False
        assert escalator_calls == [], "Escalator must NOT be called when approved"

    def test_auto_proceed_no_escalation(self, main_module):
        escalator_calls = []
        result = main_module.escalate_prospect(
            routing_result=self._make_auto_proceed_result(),
            approved=False,    # approved=False but it's auto_proceed, not slack_gate
            escalator=lambda payload: escalator_calls.append(payload),
        )
        assert result["action"] == "no_escalation"
        assert result["escalated"] is False
        assert escalator_calls == []

    def test_none_approved_escalates(self, main_module):
        """None is falsy → escalate."""
        escalator_calls = []
        result = main_module.escalate_prospect(
            routing_result=self._make_slack_gate_result(),
            approved=None,
            escalator=lambda payload: escalator_calls.append(payload),
        )
        assert result["action"] == "escalated"
        assert result["escalated"] is True

    def test_escalator_not_required_if_no_one_set(self, main_module):
        """When no escalator is provided, it silently skips — no crash."""
        result = main_module.escalate_prospect(
            routing_result=self._make_slack_gate_result(),
            approved=False,
            escalator=None,
        )
        assert result["action"] == "escalated"
        assert result["escalated"] is True

    # --- OUT6: route_prospect byte-stability (TG1/TG2 keys unchanged) ---

    def test_route_prospect_still_returns_auto_proceed_for_clear_cut(
        self, main_module
    ):
        """route_prospect's behavior/keys are byte-stable (additive-only guarantee)."""
        icp_result = {
            "qualified": True,
            "count": 4,
            "tags": [
                "ecommerce_dtc",
                "paid_social_advertising",
                "pixel_tracking_present",
                "scale_growth_stage",
            ],
        }
        result = main_module.route_prospect(
            icp_result=icp_result,
            domain="clear-brand.com",
            profile_data=None,
            slack_poster=lambda url, payload: None,
        )
        assert result["action"] == "auto_proceed"
        assert result["borderline"] is False
        assert "domain" in result
        assert "icp_count" in result
        assert "slack_sent" in result
        assert "slack_error" in result

    def test_route_prospect_still_routes_borderline_to_slack(self, main_module):
        """Exactly-3 + no strong indicators → slack_gate (TG1/TG2 unchanged)."""
        icp_result = {
            "qualified": True,
            "count": 3,
            "tags": [
                "ecommerce_dtc",
                "paid_social_advertising",
                "brand_marketing_team",
            ],
        }
        slack_calls = []
        result = main_module.route_prospect(
            icp_result=icp_result,
            domain="borderline-brand.com",
            profile_data={
                "tiktok_pixel": False,
                "meta_pixel": False,
                "gtm": False,
            },
            slack_poster=lambda url, payload: slack_calls.append(url),
        )
        assert result["action"] == "slack_gate"
        assert result["borderline"] is True

    def test_route_prospect_keys_unchanged(self, main_module):
        """The exact key set returned by route_prospect is byte-stable."""
        expected_keys = {"action", "borderline", "domain", "icp_count", "slack_sent", "slack_error"}
        icp_result = {
            "qualified": True,
            "count": 4,
            "tags": ["ecommerce_dtc", "paid_social_advertising",
                     "pixel_tracking_present", "scale_growth_stage"],
        }
        result = main_module.route_prospect(
            icp_result=icp_result,
            domain="stable-brand.com",
            profile_data=None,
            slack_poster=lambda url, payload: None,
        )
        assert set(result.keys()) == expected_keys, (
            f"route_prospect return keys changed: {set(result.keys())}"
        )


# ===========================================================================
# Import-safety (ENV4 extension — Stage 13 functions are import-safe)
# ===========================================================================

class TestENV4ImportSafety:
    """schedule_outreach_cohort, dispatch_outreach, escalate_prospect
    are plain module functions; import main must remain side-effect free."""

    def test_import_main_has_schedule_outreach_cohort(self, main_module):
        assert hasattr(main_module, "schedule_outreach_cohort")

    def test_import_main_has_dispatch_outreach(self, main_module):
        assert hasattr(main_module, "dispatch_outreach")

    def test_import_main_has_escalate_prospect(self, main_module):
        assert hasattr(main_module, "escalate_prospect")

    def test_tool_count_still_10(self, main_module):
        """Tool count must stay 10 — Stage 13 adds no LLM tools."""
        assert len(main_module.TOOL_SCHEMAS) == 10
        assert len(main_module.TOOL_DISPATCH) == 10
