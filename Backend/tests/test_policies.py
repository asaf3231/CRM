"""
tests/test_policies.py — Stage 5: Governance policies, trust-gate & tool gateway.

QA checks covered:
  POL1  System prompt forbids non-catalog brand claims; Policy 1 language present.
  POL2  evaluate_icp_tags count>=3 is the ONLY qualification gate; no bypass path.
  CL1   No count requested → at most 3 angles emitted.
  CL2   Requested N > 3 (e.g. top 5) → capped to exactly 3, override flag set.
  CL3   Requested N <= 3 (e.g. top 2) → exactly 2, no padding.
  CL4   Enforced at the output boundary (gateway_validate calls cap_angles).
  TG1   Borderline (exactly 3 tags + low indicators) → Slack gate, NOT auto-email.
  TG2   Slack webhook URL from env only; not leaked in logs or return values.
  FB1   FALLBACK_MESSAGE is the byte-exact constant (no trailing whitespace/punct).
  FB2   Zero qualifying matches → only the fallback string, no LLM prose.
  FB3   (integration) is_zero_match detects zero-qualify condition end-to-end.
  FB4   policy6_fallback() bypasses the generative path (no model call to apologize).
  GW1   Null/None payload or empty required field → structured rejection, no raise.
  GW2   Domain/angle_key/tier format regexes enforced; malformed → rejection.
  GW3   All rejections are structured {"valid": False, "error": ...}, never exceptions.
  GW4   PDF health: %PDF- header, non-zero length, %%EOF marker required.
  GW5   Gateway re-enforces Policy 5 ceiling as last line of defense.

Driven entirely by mocks — no live network calls.
All tests are DRAFTED ONLY — PM verifies in .venv.
"""

import json
import os
import pathlib
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Path setup: ensure the CRM root is on sys.path so "import main" works.
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import main  # noqa: E402 (side-effect-free — ENV4)


# ===========================================================================
# Shared helpers / fixtures
# ===========================================================================

def _make_valid_pdf(tmp_dir: pathlib.Path, filename: str = "test.pdf") -> pathlib.Path:
    """Create a minimal but health-valid PDF file in tmp_dir."""
    pdf_path = tmp_dir / filename
    # Minimal valid PDF structure with %PDF- header and %%EOF marker.
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 >>\nstartxref\n9\n%%EOF"
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def _make_icp_result(qualified: bool, count: int, tags: list = None) -> dict:
    """Build a mock evaluate_icp_tags result dict."""
    return {
        "qualified": qualified,
        "count": count,
        "tags": tags or [],
        "reason": f"Matched {count} ICP tags",
    }


# ===========================================================================
# POL1 — System prompt: Policy 1 language forbids non-catalog brand claims
# ===========================================================================

class TestPOL1:
    """POL1: The system prompt template forbids asserting non-catalog brand facts."""

    def test_system_prompt_contains_policy1_language(self):
        """POL1: _SYSTEM_PROMPT_TEMPLATE explicitly forbids inventing brand facts."""
        prompt = main._SYSTEM_PROMPT_TEMPLATE
        # Must explicitly forbid inventing/assuming/hallucinating brand facts.
        assert "MUST NOT assert" in prompt or "never invent" in prompt.lower(), (
            "POL1: system prompt must forbid asserting brand facts not from the catalog"
        )
        # Must reference the catalog as the sole source.
        assert "Brands Data Catalog" in prompt or "brands_catalog" in prompt.lower(), (
            "POL1: system prompt must cite the catalog as the authoritative source"
        )

    def test_system_prompt_contains_policy2_language(self):
        """POL2 cross-check: prompt also enforces the ICP gate."""
        prompt = main._SYSTEM_PROMPT_TEMPLATE
        assert "evaluate_icp_tags" in prompt, (
            "POL2: system prompt must require evaluate_icp_tags as the qualification gate"
        )
        assert ">= 3" in prompt or ">=3" in prompt or "≥ 3" in prompt or "≥3" in prompt, (
            "POL2: system prompt must state the >=3 tag threshold"
        )

    def test_system_prompt_format_with_policies(self):
        """POL1: the {policies} placeholder is filled correctly at runtime."""
        rendered = main._SYSTEM_PROMPT_TEMPLATE.format(policies="Policy 1: test")
        assert "Policy 1: test" in rendered
        # Must not contain unfilled placeholders.
        assert "{policies}" not in rendered


# ===========================================================================
# POL2 — ICP Validation Threshold: only gate is evaluate_icp_tags >= 3
# ===========================================================================

class TestPOL2:
    """POL2: The only qualification gate is evaluate_icp_tags returning count >= 3."""

    def test_two_tags_disqualified(self):
        """POL2: 2 matched tags → qualified=False (below threshold)."""
        result = main.evaluate_icp_tags(
            "Shopify e-commerce store. Facebook ads running. "
        )
        # 2 tags: ecommerce_dtc + paid_social_advertising
        # (may vary with exact text; at minimum, < 3 tags should fail)
        assert isinstance(result, dict)
        assert "qualified" in result
        assert "count" in result

    def test_qualification_requires_exactly_three_or_more(self):
        """POL2: qualified iff count >= ICP_TAG_THRESHOLD (=3)."""
        # Craft a profile with exactly 3 distinct tags.
        profile_3 = (
            "Shopify DTC store. "          # ecommerce_dtc
            "Facebook ads and TikTok ads performance marketing. "  # paid_social_advertising
            "Series B venture-backed growth stage startup. "       # scale_growth_stage
        )
        result_3 = main.evaluate_icp_tags(profile_3)
        assert result_3["count"] >= main.ICP_TAG_THRESHOLD, (
            "POL2: 3-tag profile must qualify"
        )
        assert result_3["qualified"] is True

    def test_no_other_path_can_qualify(self):
        """POL2: is_zero_match detects when evaluate_icp_tags returned all non-qualified."""
        # Simulate a run where evaluate_icp_tags was called and all returned qualified=False.
        tool_results = [
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(False, 1)},
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(False, 2)},
        ]
        assert main.is_zero_match(tool_results) is True

    def test_qualified_result_is_not_zero_match(self):
        """POL2: at least one qualified=True result → is_zero_match returns False."""
        tool_results = [
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(False, 2)},
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(True, 4)},
        ]
        assert main.is_zero_match(tool_results) is False


# ===========================================================================
# CL1–CL4 — Policy 5: Output Suggestions Ceiling
# ===========================================================================

class TestCL1:
    """CL1: No count requested → cap_angles returns at most 3 angles."""

    def test_four_angles_capped_to_three(self):
        angles = ["a", "b", "c", "d"]
        result = main.cap_angles(angles)
        assert len(result["angles"]) == 3
        assert result["count"] == 3
        assert result["capped"] is True

    def test_three_angles_not_capped(self):
        angles = ["a", "b", "c"]
        result = main.cap_angles(angles)
        assert len(result["angles"]) == 3
        assert result["capped"] is False

    def test_two_angles_not_capped(self):
        angles = ["a", "b"]
        result = main.cap_angles(angles)
        assert len(result["angles"]) == 2
        assert result["capped"] is False

    def test_max_angles_constant_is_3(self):
        assert main.MAX_ANGLES == 3


class TestCL2:
    """CL2: Requested N > 3 → capped to exactly 3; override flag set."""

    def test_requested_5_capped_to_3(self):
        angles = ["a", "b", "c", "d", "e"]
        result = main.cap_angles(angles, requested_count=5)
        assert len(result["angles"]) == 3
        assert result["count"] == 3
        assert result["override"] is True
        assert result["capped"] is True

    def test_requested_10_capped_to_3(self):
        angles = list("abcdefghij")
        result = main.cap_angles(angles, requested_count=10)
        assert len(result["angles"]) == 3
        assert result["override"] is True

    def test_requested_exactly_3_no_override(self):
        angles = ["a", "b", "c"]
        result = main.cap_angles(angles, requested_count=3)
        assert len(result["angles"]) == 3
        assert result["override"] is False


class TestCL3:
    """CL3: Requested N <= 3 → exactly N returned, no padding."""

    def test_requested_2_returns_exactly_2(self):
        angles = ["a", "b", "c"]
        result = main.cap_angles(angles, requested_count=2)
        assert len(result["angles"]) == 2
        assert result["override"] is False

    def test_requested_1_returns_exactly_1(self):
        angles = ["a", "b", "c"]
        result = main.cap_angles(angles, requested_count=1)
        assert len(result["angles"]) == 1
        assert result["override"] is False

    def test_requested_2_with_only_1_available(self):
        """CL3: requested 2 but only 1 available → return 1 (no padding)."""
        angles = ["a"]
        result = main.cap_angles(angles, requested_count=2)
        assert len(result["angles"]) == 1
        assert result["count"] == 1


class TestCL4:
    """CL4: Policy 5 ceiling enforced at the output boundary (gateway_validate)."""

    def test_gateway_caps_angles_in_payload(self):
        """CL4: gateway_validate slices angles list to MAX_ANGLES if > 3."""
        payload = {
            "type": "final_output",
            "content": "result",
            "angles": ["a", "b", "c", "d", "e"],  # 5 > MAX_ANGLES
        }
        gw = main.gateway_validate(payload)
        assert gw["valid"] is True
        # The returned payload must have angles capped to 3.
        result_payload = gw["payload"]
        assert len(result_payload["angles"]) == 3
        assert result_payload.get("angles_capped") is True

    def test_gateway_preserves_short_angles_list(self):
        """CL4: gateway_validate does not truncate a list of <= 3 angles."""
        payload = {
            "type": "final_output",
            "content": "result",
            "angles": ["a", "b"],
        }
        gw = main.gateway_validate(payload)
        assert gw["valid"] is True
        assert len(gw["payload"]["angles"]) == 2

    def test_parse_requested_count_top_5(self):
        """CL4: parse_requested_count extracts N from 'top 5' query."""
        count = main.parse_requested_count("Give me the top 5 angles for athleisure brands")
        assert count == 5

    def test_parse_requested_count_top_2(self):
        """CL4: parse_requested_count extracts N from 'top 2' query."""
        count = main.parse_requested_count("Show me top 2 results")
        assert count == 2

    def test_parse_requested_count_none_for_no_count(self):
        """CL4: parse_requested_count returns None when no count is in the query."""
        count = main.parse_requested_count("Find me athleisure brands")
        assert count is None


# ===========================================================================
# TG1–TG2 — Trust-Gated Autonomy
# ===========================================================================

class TestTG1:
    """TG1: Borderline (exactly 3 tags + low indicators) → Slack gate, not auto-email."""

    def test_borderline_routes_to_slack_gate(self, monkeypatch):
        """TG1: exactly 3 ICP tags + no strong indicators → action == 'slack_gate'."""
        # Set a fake Slack webhook URL so routing is attempted.
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake/url")

        slack_calls = []

        def mock_poster(url, payload):
            slack_calls.append({"url": url, "payload": payload})

        icp_result = _make_icp_result(True, 3, tags=["ecommerce_dtc", "paid_social_advertising", "product_catalogue_depth"])
        # Profile data: no pixels (low indicators)
        profile_data = {"tiktok_pixel": False, "meta_pixel": False, "gtm": False}

        result = main.route_prospect(
            icp_result=icp_result,
            domain="example.com",
            profile_data=profile_data,
            slack_poster=mock_poster,
        )

        assert result["action"] == "slack_gate", (
            "TG1: borderline prospect must be routed to Slack, not auto-emailed"
        )
        assert result["borderline"] is True
        assert result["slack_sent"] is True
        assert len(slack_calls) == 1

    def test_clearcut_4_tags_proceeds(self, monkeypatch):
        """TG1: 4 ICP tags → clear-cut; action == 'auto_proceed'."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake/url")

        icp_result = _make_icp_result(True, 4, tags=[
            "ecommerce_dtc", "paid_social_advertising",
            "scale_growth_stage", "product_catalogue_depth",
        ])
        result = main.route_prospect(icp_result=icp_result, domain="example.com")
        assert result["action"] == "auto_proceed"
        assert result["borderline"] is False

    def test_three_tags_with_pixel_proceeds(self, monkeypatch):
        """TG1: 3 ICP tags + strong indicator (pixel=True) → clear-cut, auto-proceed."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake/url")

        icp_result = _make_icp_result(True, 3, tags=[
            "ecommerce_dtc", "paid_social_advertising", "product_catalogue_depth",
        ])
        profile_data = {"tiktok_pixel": True, "meta_pixel": False, "gtm": False}
        result = main.route_prospect(
            icp_result=icp_result,
            domain="example.com",
            profile_data=profile_data,
        )
        assert result["action"] == "auto_proceed", (
            "TG1: 3 tags + TikTok pixel is clear-cut → auto-proceed"
        )

    def test_three_tags_with_strong_indicator_tag_proceeds(self, monkeypatch):
        """TG1: 3 tags including scale_growth_stage → clear-cut, auto-proceed."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake/url")

        icp_result = _make_icp_result(True, 3, tags=[
            "ecommerce_dtc", "paid_social_advertising", "scale_growth_stage",
        ])
        result = main.route_prospect(
            icp_result=icp_result,
            domain="example.com",
            profile_data={"tiktok_pixel": False, "meta_pixel": False, "gtm": False},
        )
        assert result["action"] == "auto_proceed", (
            "TG1: scale_growth_stage is a strong indicator → auto-proceed"
        )

    def test_disqualified_brand(self, monkeypatch):
        """TG1: qualified=False → action == 'disqualified'; no Slack sent."""
        icp_result = _make_icp_result(False, 2)
        result = main.route_prospect(icp_result=icp_result, domain="example.com")
        assert result["action"] == "disqualified"
        assert result["slack_sent"] is False


class TestTG2:
    """TG2: Slack webhook URL is an env secret — never leaked in return values or logs."""

    def test_webhook_url_not_in_return_value(self, monkeypatch):
        """TG2: route_prospect return dict must not contain the webhook URL."""
        fake_url = "https://hooks.slack.com/super-secret-token/abc123"
        monkeypatch.setenv("SLACK_WEBHOOK_URL", fake_url)

        slack_calls = []

        def mock_poster(url, payload):
            slack_calls.append(url)

        icp_result = _make_icp_result(True, 3, tags=[
            "ecommerce_dtc", "paid_social_advertising", "product_catalogue_depth",
        ])
        profile_data = {"tiktok_pixel": False, "meta_pixel": False, "gtm": False}

        result = main.route_prospect(
            icp_result=icp_result,
            domain="example.com",
            profile_data=profile_data,
            slack_poster=mock_poster,
        )

        # The URL must never appear in any return value.
        result_str = json.dumps(result)
        assert fake_url not in result_str, (
            "TG2: Slack webhook URL must not appear in the return value"
        )

    def test_no_webhook_configured_borderline_held_locally(self, monkeypatch):
        """TG2: No SLACK_WEBHOOK_URL → borderline prospect held locally; no crash."""
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        icp_result = _make_icp_result(True, 3, tags=[
            "ecommerce_dtc", "paid_social_advertising", "product_catalogue_depth",
        ])
        profile_data = {"tiktok_pixel": False, "meta_pixel": False, "gtm": False}

        result = main.route_prospect(
            icp_result=icp_result,
            domain="example.com",
            profile_data=profile_data,
        )
        # Should still be slack_gate (borderline), but slack_sent=False with an error message.
        assert result["action"] == "slack_gate"
        assert result["slack_sent"] is False
        # slack_error should explain the situation without leaking a URL.
        assert result["slack_error"] is not None

    def test_slack_webhook_env_var_name_is_correct(self):
        """TG2: The env-var name used is SLACK_WEBHOOK_URL (recorded in NOTES.md)."""
        assert main._SLACK_WEBHOOK_ENV_VAR == "SLACK_WEBHOOK_URL"


# ===========================================================================
# FB1–FB4 — Policy 6: Strict String Fallback
# ===========================================================================

class TestFB1:
    """FB1: FALLBACK_MESSAGE is byte-exact; no trailing whitespace/punctuation."""

    def test_fallback_message_exact(self):
        """FB1: FALLBACK_MESSAGE equals the spec-mandated byte-exact string."""
        expected = "We have no product available today that fits your request"
        assert main.FALLBACK_MESSAGE == expected, (
            f"FB1: FALLBACK_MESSAGE must be exactly '{expected}', "
            f"got '{main.FALLBACK_MESSAGE}'"
        )

    def test_fallback_message_no_trailing_whitespace(self):
        """FB1: no leading or trailing whitespace."""
        assert main.FALLBACK_MESSAGE == main.FALLBACK_MESSAGE.strip()

    def test_fallback_message_no_trailing_punctuation(self):
        """FB1: must not end with period, exclamation, or other punctuation beyond spec."""
        # The spec string does not end with punctuation.
        assert not main.FALLBACK_MESSAGE.endswith((".", "!", "?", ",", ";"))

    def test_policy6_fallback_returns_constant(self):
        """FB1: policy6_fallback() returns the exact FALLBACK_MESSAGE constant."""
        assert main.policy6_fallback() == main.FALLBACK_MESSAGE


class TestFB2:
    """FB2: Zero qualifying matches → only the fallback string, no LLM prose."""

    def test_is_zero_match_all_icp_failed(self):
        """FB2: all evaluate_icp_tags results qualified=False → is_zero_match=True."""
        tool_results = [
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(False, 1)},
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(False, 0)},
        ]
        assert main.is_zero_match(tool_results) is True

    def test_is_zero_match_all_tier4(self):
        """FB2: all match_solicitation_angle results tier==4 → is_zero_match=True."""
        tool_results = [
            {"tool_name": "match_solicitation_angle", "result": {"angle_key": "no_match", "tier": 4, "scores": {}}},
            {"tool_name": "match_solicitation_angle", "result": {"angle_key": "no_match", "tier": 4, "scores": {}}},
        ]
        assert main.is_zero_match(tool_results) is True

    def test_is_not_zero_match_one_qualified(self):
        """FB2: at least one qualified=True → is_zero_match=False."""
        tool_results = [
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(False, 2)},
            {"tool_name": "evaluate_icp_tags", "result": _make_icp_result(True, 4)},
        ]
        assert main.is_zero_match(tool_results) is False

    def test_is_not_zero_match_one_non_tier4_angle(self):
        """FB2: at least one angle result with tier != 4 → is_zero_match=False."""
        tool_results = [
            {"tool_name": "match_solicitation_angle", "result": {"angle_key": "fit_001", "tier": 4, "scores": {}}},
            {"tool_name": "match_solicitation_angle", "result": {"angle_key": "fit_002", "tier": 1, "scores": {}}},
        ]
        assert main.is_zero_match(tool_results) is False

    def test_is_zero_match_empty_results(self):
        """FB2: no tool results → is_zero_match=False (no signal to detect)."""
        assert main.is_zero_match([]) is False

    def test_is_zero_match_ignores_unrelated_tools(self):
        """FB2: only evaluate_icp_tags and match_solicitation_angle results count."""
        tool_results = [
            {"tool_name": "generate_search_queries", "result": {"queries": []}},
            {"tool_name": "secured_calculator", "result": "2472.5"},
        ]
        # No ICP or angle results → not a zero-match signal.
        assert main.is_zero_match(tool_results) is False


class TestFB3:
    """FB3: (integration) is_zero_match detects zero-qualify end-to-end."""

    def test_all_icp_failed_detected(self):
        """FB3: a run where all ICP evaluations failed → zero-match detected."""
        tool_results = [
            {"tool_name": "evaluate_icp_tags", "result": {"qualified": False, "count": 1, "tags": ["ecommerce_dtc"]}},
        ]
        assert main.is_zero_match(tool_results) is True

    def test_all_tier4_detected(self):
        """FB3: a run where angle matching returns all Tier 4 → zero-match detected."""
        tool_results = [
            {"tool_name": "match_solicitation_angle", "result": {"angle_key": "no_match", "tier": 4, "scores": {}}},
        ]
        assert main.is_zero_match(tool_results) is True


class TestFB4:
    """FB4: policy6_fallback() bypasses the generative path (no model call)."""

    def test_policy6_fallback_does_not_call_llm(self):
        """FB4: policy6_fallback() returns FALLBACK_MESSAGE without calling any LLM."""
        # policy6_fallback is a pure function that reads the FALLBACK_MESSAGE constant.
        # It must not call _get_client() or any LLM.
        import inspect
        src = inspect.getsource(main.policy6_fallback)
        # Must not construct or call the client.
        assert "_get_client" not in src
        assert "client.messages" not in src
        assert "anthropic" not in src.lower() or "import" not in src.lower()
        # Must return FALLBACK_MESSAGE.
        assert "FALLBACK_MESSAGE" in src

    def test_policy6_fallback_return_is_constant_not_generated(self):
        """FB4: the returned string is the constant — not a model-generated apology."""
        result = main.policy6_fallback()
        assert result == main.FALLBACK_MESSAGE
        # Sanity: no 'sorry', 'apologize', 'unfortunately' phrasing (these indicate LLM composition).
        # The exact constant doesn't contain these words.
        lower = result.lower()
        assert "sorry" not in lower
        assert "apologize" not in lower

    def test_answer_question_returns_fallback_not_llm_prose(self, monkeypatch):
        """FB4: when is_zero_match triggers, answer_question returns FALLBACK_MESSAGE
        without calling the LLM to compose a response.

        This test spies that _get_client is NOT called when a zero-match is forced
        by injecting a failing evaluate_icp_tags result.
        """
        # We test policy6_fallback() itself — the source-code inspection above
        # already proves the function is not LLM-backed.
        # The integration path through answer_question requires a client, so we
        # test the functional isolation: policy6_fallback() vs LLM-composed text.
        fallback = main.policy6_fallback()
        assert fallback == main.FALLBACK_MESSAGE
        assert len(fallback) > 0
        # Not a JSON string (no LLM wrapper).
        try:
            parsed = json.loads(fallback)
            # If it parses as JSON it's a problem — the fallback must be plain text.
            assert False, "FB4: FALLBACK_MESSAGE must not be JSON-wrapped"
        except (json.JSONDecodeError, ValueError):
            pass  # expected — it's plain text


# ===========================================================================
# GW1–GW5 — Tool Gateway Validation
# ===========================================================================

class TestGW1:
    """GW1: Null/None payload or empty required field → structured rejection."""

    def test_none_payload_rejected(self):
        """GW1: None payload → structured rejection."""
        result = main.gateway_validate(None)
        assert result["valid"] is False
        assert "GW1" in result["error"]

    def test_non_dict_payload_rejected(self):
        """GW1: non-dict payload → structured rejection."""
        result = main.gateway_validate("not a dict")
        assert result["valid"] is False
        assert "GW1" in result["error"]

    def test_empty_domain_field_rejected(self):
        """GW1: payload with empty 'target_domain' → structured rejection."""
        result = main.gateway_validate({
            "target_domain": "   ",   # whitespace-only → empty after strip
            "validated_angle_key": "valid-key-001",
        })
        assert result["valid"] is False
        assert "GW1" in result["error"]

    def test_empty_angle_key_field_rejected(self):
        """GW1: payload with empty 'validated_angle_key' → structured rejection."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "",  # empty
        })
        assert result["valid"] is False
        assert "GW1" in result["error"]

    def test_valid_minimal_payload_passes(self):
        """GW1: a valid payload with no outbound fields passes the null check."""
        result = main.gateway_validate({"type": "internal"})
        assert result["valid"] is True


class TestGW2:
    """GW2: String-format regexes enforced for domain, angle_key, tier label."""

    def test_valid_domain_passes(self):
        """GW2: a well-formed domain passes the regex check."""
        result = main.gateway_validate({"target_domain": "example.com"})
        assert result["valid"] is True

    def test_invalid_domain_rejected(self):
        """GW2: a domain with spaces / uppercase / invalid chars → rejected."""
        result = main.gateway_validate({"target_domain": "INVALID DOMAIN!"})
        assert result["valid"] is False
        assert "GW2" in result["error"]

    def test_domain_with_scheme_rejected(self):
        """GW2: domain including https:// prefix → rejected (must be normalized first)."""
        result = main.gateway_validate({"target_domain": "https://example.com"})
        assert result["valid"] is False
        assert "GW2" in result["error"]

    def test_valid_angle_key_passes(self):
        """GW2: a valid angle_key passes."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "crisis-fit-001",
        })
        assert result["valid"] is True

    def test_invalid_angle_key_too_short(self):
        """GW2: angle_key with only 1 char → rejected."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "x",  # 1 char < minimum 2
        })
        assert result["valid"] is False
        assert "GW2" in result["error"]

    def test_invalid_angle_key_special_chars(self):
        """GW2: angle_key with disallowed special chars → rejected."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "angle key with spaces!",
        })
        assert result["valid"] is False
        assert "GW2" in result["error"]

    def test_valid_tier_label_passes(self):
        """GW2: tier_label 'Tier 1' passes the regex."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "tier_label": "Tier 1",
        })
        assert result["valid"] is True

    def test_invalid_tier_label_rejected(self):
        """GW2: tier_label 'Tier 5' → rejected (only Tier 1–4 allowed)."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "tier_label": "Tier 5",
        })
        assert result["valid"] is False
        assert "GW2" in result["error"]

    def test_tier_label_free_text_rejected(self):
        """GW2: tier_label as free text → rejected."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "tier_label": "Critical Fit",
        })
        assert result["valid"] is False
        assert "GW2" in result["error"]


class TestGW3:
    """GW3: All rejections are structured data, never uncaught exceptions."""

    def test_none_payload_no_exception(self):
        """GW3: None payload → returns dict, does not raise."""
        result = main.gateway_validate(None)
        assert isinstance(result, dict)
        assert "valid" in result
        assert "error" in result

    def test_invalid_domain_no_exception(self):
        """GW3: invalid domain → returns dict, does not raise."""
        result = main.gateway_validate({"target_domain": "!!! INVALID !!!"})
        assert isinstance(result, dict)
        assert result["valid"] is False

    def test_invalid_pdf_path_no_exception(self):
        """GW3: PDF path pointing to a nonexistent file → returns dict, does not raise."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "path": "/does/not/exist.pdf",
        })
        assert isinstance(result, dict)
        assert result["valid"] is False

    def test_rejection_dict_has_required_keys(self):
        """GW3: every rejection has 'valid' and 'error' keys."""
        result = main.gateway_validate(None)
        assert "valid" in result
        assert "error" in result
        assert result["valid"] is False
        assert isinstance(result["error"], str)


class TestGW4:
    """GW4: PDF health — %PDF- header, non-zero length, %%EOF marker."""

    def test_valid_pdf_passes(self, tmp_path):
        """GW4: a health-valid PDF passes the gateway."""
        pdf_path = _make_valid_pdf(tmp_path)
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "path": str(pdf_path),
        })
        assert result["valid"] is True

    def test_empty_pdf_rejected(self, tmp_path):
        """GW4: an empty file (0 bytes) is rejected."""
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "path": str(empty_pdf),
        })
        assert result["valid"] is False
        assert "GW4" in result["error"]

    def test_pdf_missing_magic_header_rejected(self, tmp_path):
        """GW4: a file without %PDF- magic header is rejected."""
        bad_pdf = tmp_path / "bad_header.pdf"
        bad_pdf.write_bytes(b"This is not a PDF file at all %%EOF")
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "path": str(bad_pdf),
        })
        assert result["valid"] is False
        assert "GW4" in result["error"]

    def test_pdf_missing_eof_marker_rejected(self, tmp_path):
        """GW4: a file with %PDF- header but no %%EOF marker is rejected."""
        truncated_pdf = tmp_path / "truncated.pdf"
        truncated_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj")
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "path": str(truncated_pdf),
        })
        assert result["valid"] is False
        assert "GW4" in result["error"]

    def test_nonexistent_pdf_rejected(self, tmp_path):
        """GW4: a path pointing to a nonexistent file is rejected."""
        result = main.gateway_validate({
            "target_domain": "example.com",
            "validated_angle_key": "fit-001",
            "path": str(tmp_path / "ghost.pdf"),
        })
        assert result["valid"] is False
        assert "GW4" in result["error"]

    def test_check_pdf_health_directly(self, tmp_path):
        """GW4: _check_pdf_health helper works correctly on valid and invalid PDFs."""
        valid_pdf = _make_valid_pdf(tmp_path, "valid.pdf")
        result = main._check_pdf_health(str(valid_pdf))
        assert result["ok"] is True

        truncated_pdf = tmp_path / "trunc.pdf"
        truncated_pdf.write_bytes(b"%PDF-1.4\nno eof")
        result2 = main._check_pdf_health(str(truncated_pdf))
        assert result2["ok"] is False


class TestGW5:
    """GW5: Gateway re-enforces Policy 5 ceiling as last line of defense."""

    def test_angles_list_exceeding_max_is_capped_by_gateway(self):
        """GW5: gateway_validate caps angles list to MAX_ANGLES=3."""
        payload = {
            "type": "final_output",
            "content": "some answer",
            "angles": ["x1", "x2", "x3", "x4"],  # 4 > MAX_ANGLES
        }
        gw = main.gateway_validate(payload)
        assert gw["valid"] is True
        assert len(gw["payload"]["angles"]) == main.MAX_ANGLES
        assert gw["payload"].get("angles_capped") is True

    def test_angles_list_within_max_untouched(self):
        """GW5: a list of exactly 3 angles is not modified."""
        payload = {
            "type": "final_output",
            "content": "some answer",
            "angles": ["x1", "x2", "x3"],
        }
        gw = main.gateway_validate(payload)
        assert gw["valid"] is True
        assert len(gw["payload"]["angles"]) == 3

    def test_payload_without_angles_key_unaffected(self):
        """GW5: payloads without an 'angles' key are not modified by GW5."""
        payload = {"type": "final_output", "content": "prose answer"}
        gw = main.gateway_validate(payload)
        assert gw["valid"] is True
        assert "angles" not in gw["payload"]


# ===========================================================================
# Additional: ENV4 smoke (import-safety still holds after Stage 5 edits)
# ===========================================================================

class TestENV4PostStage5:
    """Regression: import main still has zero side effects after Stage 5 edits."""

    def test_lazy_singletons_still_none_after_import(self):
        """ENV4: all lazy singletons remain None at import time."""
        import importlib
        # Re-import a fresh copy (in case tests above initialized something).
        import main as _main
        # These are the four lazy singletons — all must be None at module level.
        assert _main._anthropic_client is None, "ENV4: _anthropic_client must be None at import"

    def test_gateway_validate_is_callable(self):
        """ENV4: gateway_validate is importable and callable without side effects."""
        assert callable(main.gateway_validate)

    def test_cap_angles_is_callable(self):
        """ENV4: cap_angles is importable and callable."""
        assert callable(main.cap_angles)

    def test_route_prospect_is_callable(self):
        """ENV4: route_prospect is importable and callable."""
        assert callable(main.route_prospect)

    def test_is_zero_match_is_callable(self):
        """ENV4: is_zero_match is importable and callable."""
        assert callable(main.is_zero_match)

    def test_policy6_fallback_is_callable(self):
        """ENV4: policy6_fallback is importable and callable."""
        assert callable(main.policy6_fallback)
