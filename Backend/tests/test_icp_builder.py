"""
tests/test_icp_builder.py — Stage 10: Layer 1 ICP Builder

Checks covered:
    ICPB1  structured shape {vertical, want_signals, avoid_signals, geo,
           size_band, icp_tags, anchor_companies} — correct types + JSON-serializable.
    ICPB2  anchors capped at ICP_ANCHOR_COUNT (=5) even when mock returns 8.
    ICPB3  ENV4 — import-safe; no side effects at import (cross-check).
    ICPB4  G2 anti-leakage — no catalog literals in shipped code (grep cross-check).
    ICPB5  Policy 2 unchanged — _ICP_TAGS and ICP_TAG_THRESHOLD untouched after call.
    ICPB6  Generalizes to 2 different seeds; deterministic shape under the mock.

Mocking pattern mirrors tests/test_tools.py:
    - Monkeypatch main._get_client → fake whose .messages.create() returns a scripted response.
    - Monkeypatch main._vector_a_search → canned result (no network).
"""

import ast
import json
import pathlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Ensure the CRM root is on sys.path so 'import main' works from tests/
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import main  # noqa: E402


# ===========================================================================
# Shared fixtures / helpers
# ===========================================================================

# Canned ICP document (well-formed, 4 anchors from LLM)
_CANNED_ICP_LLM_4_ANCHORS = {
    "vertical": "DTC sustainable footwear",
    "want_signals": [
        "DTC e-commerce brand",
        "paid social advertising budget",
        "brand marketing team present",
    ],
    "avoid_signals": [
        "pure marketplace seller",
        "no digital advertising presence",
    ],
    "geo": "North America",
    "size_band": "SMB",
    "icp_tags": [
        "ecommerce_dtc",
        "paid_social_advertising",
        "brand_marketing_team",
    ],
    "anchor_companies": [
        {"name": "Anchor A", "domain": "anchora.com", "why": "Leading DTC footwear brand."},
        {"name": "Anchor B", "domain": "anchorb.com", "why": "Sustainable footwear DTC."},
        {"name": "Anchor C", "domain": "anchorc.com", "why": "Paid social heavy spender."},
        {"name": "Anchor D", "domain": "anchord.com", "why": "Brand-safety risk history."},
    ],
}

# Canned ICP document with 8 anchors (to test ICP_ANCHOR_COUNT cap)
_CANNED_ICP_LLM_8_ANCHORS = {
    "vertical": "athleisure brands",
    "want_signals": ["DTC", "paid social"],
    "avoid_signals": ["no e-commerce"],
    "geo": "global",
    "size_band": "mid-market",
    "icp_tags": ["ecommerce_dtc", "paid_social_advertising"],
    "anchor_companies": [
        {"name": f"Brand{i}", "domain": f"brand{i}.com", "why": f"Reason {i}."}
        for i in range(1, 9)  # 8 anchors
    ],
}

# Canned for a second seed (generalizes — ICPB6)
_CANNED_ICP_SECOND_SEED = {
    "vertical": "pet food subscription",
    "want_signals": ["subscription DTC", "paid media"],
    "avoid_signals": ["brick-and-mortar only"],
    "geo": "US",
    "size_band": "SMB",
    "icp_tags": ["ecommerce_dtc", "ad_spend_signals"],
    "anchor_companies": [
        {"name": "PetBrand Alpha", "domain": "petbrandalpha.com", "why": "Subscription model."},
        {"name": "PetBrand Beta",  "domain": "petbrandbeta.com",  "why": "Heavy paid social."},
    ],
}


def _make_fake_client(canned_dict: dict):
    """Return a fake Anthropic client whose messages.create() returns canned JSON."""
    canned_json = json.dumps(canned_dict)
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(text=canned_json)],
        stop_reason="end_turn",
    )

    class _FakeMessages:
        def create(self, **kwargs):
            return fake_response

    fake_client = MagicMock()
    fake_client.messages = _FakeMessages()
    return fake_client


def _make_fake_vector_a(domains: list):
    """Return a fake _vector_a_search function that returns canned domains."""
    def _fake(query: str) -> dict:
        return {"domains": domains, "status": "ok", "error": None}
    return _fake


# ===========================================================================
# ICPB1 — Structured shape + JSON-serializable
# ===========================================================================

class TestICPB1Shape(unittest.TestCase):
    """ICPB1: build_icp_document returns the exact 7-key shape with correct types."""

    EXPECTED_KEYS = {
        "vertical", "want_signals", "avoid_signals",
        "geo", "size_band", "icp_tags", "anchor_companies",
    }

    def _call_with_mock(self, seed: str, canned: dict, domains: list = None) -> dict:
        fake_client = _make_fake_client(canned)
        fake_va = _make_fake_vector_a(domains or [])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            return main.build_icp_document(seed)

    def test_icpb1_exact_key_set(self):
        result = self._call_with_mock(
            "DTC sustainable footwear", _CANNED_ICP_LLM_4_ANCHORS
        )
        self.assertEqual(set(result.keys()), self.EXPECTED_KEYS,
                         f"Unexpected keys: {set(result.keys()) ^ self.EXPECTED_KEYS}")

    def test_icpb1_vertical_is_str(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["vertical"], str)
        self.assertTrue(len(result["vertical"]) > 0)

    def test_icpb1_want_signals_is_list_of_str(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["want_signals"], list)
        for s in result["want_signals"]:
            self.assertIsInstance(s, str)

    def test_icpb1_avoid_signals_is_list_of_str(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["avoid_signals"], list)
        for s in result["avoid_signals"]:
            self.assertIsInstance(s, str)

    def test_icpb1_geo_is_str(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["geo"], str)

    def test_icpb1_size_band_is_str(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["size_band"], str)

    def test_icpb1_icp_tags_is_list_of_str(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["icp_tags"], list)
        for t in result["icp_tags"]:
            self.assertIsInstance(t, str)

    def test_icpb1_anchor_companies_is_list_of_dicts(self):
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertIsInstance(result["anchor_companies"], list)
        for a in result["anchor_companies"]:
            self.assertIsInstance(a, dict)

    def test_icpb1_json_serializable(self):
        """The entire result must be serializable via json.dumps (ICPB1)."""
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        try:
            serialized = json.dumps(result)
        except (TypeError, ValueError) as exc:
            self.fail(f"build_icp_document result is not JSON-serializable: {exc}")
        # Round-trip check
        parsed = json.loads(serialized)
        self.assertEqual(set(parsed.keys()), self.EXPECTED_KEYS)

    def test_icpb1_no_error_key_on_happy_path(self):
        """On a successful call, 'error' must NOT be in the result."""
        result = self._call_with_mock("footwear brands", _CANNED_ICP_LLM_4_ANCHORS)
        self.assertNotIn("error", result,
                         f"Unexpected 'error' key in result: {result.get('error')}")

    def test_icpb1_no_exception_on_normal_call(self):
        """A normal call must not raise any exception (ICPB3/ICPB4 quick check)."""
        try:
            result = self._call_with_mock("DTC sustainable footwear", _CANNED_ICP_LLM_4_ANCHORS)
        except Exception as exc:
            self.fail(f"build_icp_document raised an unexpected exception: {exc}")
        self.assertNotIn("error", result)


# ===========================================================================
# ICPB2 — Anchor count capped at ICP_ANCHOR_COUNT (=5)
# ===========================================================================

class TestICPB2AnchorCap(unittest.TestCase):
    """ICPB2: anchor_companies is always <= ICP_ANCHOR_COUNT (=5)."""

    def _call_with_mock(self, canned: dict, domains: list = None) -> dict:
        fake_client = _make_fake_client(canned)
        fake_va = _make_fake_vector_a(domains or [])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            return main.build_icp_document("athleisure brands")

    def test_icpb2_llm_returns_8_anchors_capped_to_5(self):
        """When LLM returns 8 anchors, only 5 must appear in the result."""
        result = self._call_with_mock(_CANNED_ICP_LLM_8_ANCHORS)
        anchors = result.get("anchor_companies", [])
        self.assertLessEqual(
            len(anchors), main.ICP_ANCHOR_COUNT,
            f"Expected <= {main.ICP_ANCHOR_COUNT} anchors, got {len(anchors)}"
        )
        self.assertEqual(len(anchors), 5,
                         "Expected exactly 5 anchors (capped from 8)")

    def test_icpb2_cap_constant_is_5(self):
        self.assertEqual(main.ICP_ANCHOR_COUNT, 5)

    def test_icpb2_4_llm_plus_2_domains_capped_to_5(self):
        """LLM provides 4 anchors; grounded research adds 2 domains → capped at 5."""
        extra_domains = ["extra1.com", "extra2.com", "extra3.com"]
        result = self._call_with_mock(
            _CANNED_ICP_LLM_4_ANCHORS,
            domains=extra_domains,
        )
        anchors = result.get("anchor_companies", [])
        self.assertLessEqual(len(anchors), main.ICP_ANCHOR_COUNT)

    def test_icpb2_0_llm_anchors_domains_capped_to_5(self):
        """If LLM provides 0 anchors but research returns 10 domains → capped at 5."""
        canned_no_anchors = dict(_CANNED_ICP_LLM_4_ANCHORS)
        canned_no_anchors["anchor_companies"] = []
        domains_10 = [f"brand{i}.com" for i in range(10)]
        result = self._call_with_mock(canned_no_anchors, domains=domains_10)
        anchors = result.get("anchor_companies", [])
        self.assertLessEqual(len(anchors), main.ICP_ANCHOR_COUNT)


# ===========================================================================
# ICPB3 — Import-safety (ENV4 cross-check)
# ===========================================================================

class TestICPB3ImportSafety(unittest.TestCase):
    """ICPB3: import main does not trigger any side effects (ENV4)."""

    def test_icpb3_anthropic_client_none_at_import(self):
        """_anthropic_client must be None — not built at import time."""
        # We can test this indirectly: if main was imported cleanly above (no network
        # calls fired), the singleton should still be None (nothing called _get_client).
        # Re-check after a fresh-module-state perspective: the client starts None.
        # NOTE: other tests in the suite MAY have patched _get_client, but the module
        # attribute stays None because the real _get_client was never called.
        # The canonical ENV4 proof is the full import-from-empty-dir test elsewhere;
        # this test confirms the lazy singleton pattern is in place.
        self.assertIsNone(main._anthropic_client,
                          "_anthropic_client should be None until _get_client() is called")

    def test_icpb3_icp_anchor_count_defined_in_config(self):
        """ICP_ANCHOR_COUNT is a module-level constant, not built lazily."""
        self.assertEqual(main.ICP_ANCHOR_COUNT, 5)


# ===========================================================================
# ICPB5 — Policy 2 unchanged: _ICP_TAGS + ICP_TAG_THRESHOLD untouched
# ===========================================================================

class TestICPB5Policy2Unchanged(unittest.TestCase):
    """ICPB5: calling build_icp_document must NOT mutate _ICP_TAGS or ICP_TAG_THRESHOLD."""

    def test_icpb5_icp_tags_vocabulary_unchanged_after_call(self):
        """_ICP_TAGS must have the same keys after build_icp_document returns."""
        original_keys = set(main._ICP_TAGS.keys())
        expected_keys = {
            "ecommerce_dtc", "paid_social_advertising", "scale_growth_stage",
            "pixel_tracking_present", "brand_marketing_team", "product_catalogue_depth",
            "ad_spend_signals", "crisis_reputation_risk",
        }
        # Verify the expected vocabulary is intact before the call
        self.assertEqual(original_keys, expected_keys,
                         f"_ICP_TAGS vocabulary mismatch: {original_keys ^ expected_keys}")

        fake_client = _make_fake_client(_CANNED_ICP_LLM_4_ANCHORS)
        fake_va = _make_fake_vector_a([])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            main.build_icp_document("footwear brands")

        after_keys = set(main._ICP_TAGS.keys())
        self.assertEqual(original_keys, after_keys,
                         "_ICP_TAGS was mutated by build_icp_document!")

    def test_icpb5_icp_tag_threshold_unchanged(self):
        """ICP_TAG_THRESHOLD must remain 3 — the sole qualification gate."""
        self.assertEqual(main.ICP_TAG_THRESHOLD, 3)

        fake_client = _make_fake_client(_CANNED_ICP_LLM_4_ANCHORS)
        fake_va = _make_fake_vector_a([])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            main.build_icp_document("footwear brands")

        self.assertEqual(main.ICP_TAG_THRESHOLD, 3,
                         "ICP_TAG_THRESHOLD was mutated by build_icp_document!")

    def test_icpb5_evaluate_icp_tags_still_qualifies_correctly(self):
        """evaluate_icp_tags must still apply its >=3 gate after a build_icp_document call."""
        # Profile that hits exactly 3 ICP tags (should pass the gate)
        profile_3_tags = (
            "direct-to-consumer shopify store "
            "facebook ads paid social campaigns "
            "brand manager head of marketing"
        )
        fake_client = _make_fake_client(_CANNED_ICP_LLM_4_ANCHORS)
        fake_va = _make_fake_vector_a([])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            main.build_icp_document("footwear brands")

        result = main.evaluate_icp_tags(profile_3_tags)
        self.assertTrue(result["qualified"],
                        f"evaluate_icp_tags broken after build_icp_document. Tags: {result}")
        self.assertGreaterEqual(result["count"], 3)

    def test_icpb5_icp_doc_tags_do_not_replace_gate(self):
        """The icp_tags in the ICP document are advisory; they don't skip evaluate_icp_tags."""
        # Build an ICP doc with rich icp_tags
        fake_client = _make_fake_client(_CANNED_ICP_LLM_4_ANCHORS)
        fake_va = _make_fake_vector_a([])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            icp_doc = main.build_icp_document("footwear brands")

        # A profile that matches 0 real ICP tags should still fail evaluate_icp_tags
        empty_profile = "quarterly investor update slides"
        gate_result = main.evaluate_icp_tags(empty_profile)
        self.assertFalse(gate_result["qualified"],
                         "evaluate_icp_tags gate must be independent of ICP doc content")


# ===========================================================================
# ICPB6 — Generalizes to 2 different seeds; deterministic under mock
# ===========================================================================

class TestICPB6Generalization(unittest.TestCase):
    """ICPB6: 2 different seeds both produce correctly-shaped results; deterministic under mock."""

    EXPECTED_KEYS = {
        "vertical", "want_signals", "avoid_signals",
        "geo", "size_band", "icp_tags", "anchor_companies",
    }

    def _call_with_mock(self, seed: str, canned: dict, domains: list = None) -> dict:
        fake_client = _make_fake_client(canned)
        fake_va = _make_fake_vector_a(domains or [])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            return main.build_icp_document(seed)

    def test_icpb6_seed_1_footwear_shape(self):
        """Seed 1: DTC sustainable footwear → correct shape."""
        result = self._call_with_mock(
            "DTC sustainable footwear brands with paid social advertising",
            _CANNED_ICP_LLM_4_ANCHORS,
        )
        self.assertEqual(set(result.keys()), self.EXPECTED_KEYS)
        self.assertNotIn("error", result)
        self.assertLessEqual(len(result["anchor_companies"]), main.ICP_ANCHOR_COUNT)

    def test_icpb6_seed_2_pet_food_shape(self):
        """Seed 2: pet food subscription → correct shape (different canned response)."""
        result = self._call_with_mock(
            "pet food subscription DTC brands",
            _CANNED_ICP_SECOND_SEED,
        )
        self.assertEqual(set(result.keys()), self.EXPECTED_KEYS)
        self.assertNotIn("error", result)
        self.assertLessEqual(len(result["anchor_companies"]), main.ICP_ANCHOR_COUNT)

    def test_icpb6_deterministic_under_same_mock(self):
        """Calling build_icp_document twice with the same mock returns the same shape."""
        results = []
        for _ in range(2):
            results.append(
                self._call_with_mock(
                    "DTC sustainable footwear",
                    _CANNED_ICP_LLM_4_ANCHORS,
                )
            )
        # Both have the exact same key set
        self.assertEqual(set(results[0].keys()), set(results[1].keys()))
        # Both have the same vertical
        self.assertEqual(results[0]["vertical"], results[1]["vertical"])
        # Both have the same number of anchors
        self.assertEqual(
            len(results[0]["anchor_companies"]),
            len(results[1]["anchor_companies"]),
        )

    def test_icpb6_seed_1_icp_tags_from_vocabulary(self):
        """icp_tags in the ICP document must come from the _ICP_TAGS vocabulary."""
        result = self._call_with_mock(
            "DTC sustainable footwear",
            _CANNED_ICP_LLM_4_ANCHORS,
        )
        valid_tags = set(main._ICP_TAGS.keys())
        for tag in result.get("icp_tags", []):
            self.assertIn(tag, valid_tags,
                          f"ICP doc tag '{tag}' is not in the _ICP_TAGS vocabulary")

    def test_icpb6_seed_2_json_serializable(self):
        """Both seeds produce JSON-serializable results."""
        result = self._call_with_mock("pet food subscription DTC brands", _CANNED_ICP_SECOND_SEED)
        try:
            json.dumps(result)
        except (TypeError, ValueError) as exc:
            self.fail(f"Seed 2 result not JSON-serializable: {exc}")


# ===========================================================================
# Tool registration checks (S0 parity for tool 9)
# ===========================================================================

class TestICPBRegistration(unittest.TestCase):
    """Verify the three-way identity: schema name == function == dispatch key."""

    def test_tool9_in_tool_schemas(self):
        schema_names = {s["name"] for s in main.TOOL_SCHEMAS}
        self.assertIn("build_icp_document", schema_names)

    def test_tool9_in_tool_dispatch(self):
        self.assertIn("build_icp_document", main.TOOL_DISPATCH)

    def test_tool9_dispatch_is_the_function(self):
        self.assertIs(main.TOOL_DISPATCH["build_icp_document"], main.build_icp_document)

    def test_tool_count_is_9(self):
        # Stage 12 bumped the count 9 → 10 (discover_contacts added).
        # This test now checks for 10 (the current total).
        self.assertEqual(len(main.TOOL_SCHEMAS), 10)
        self.assertEqual(len(main.TOOL_DISPATCH), 10)

    def test_schema_names_dispatch_keys_match(self):
        schema_names = {s["name"] for s in main.TOOL_SCHEMAS}
        dispatch_keys = set(main.TOOL_DISPATCH.keys())
        self.assertEqual(schema_names, dispatch_keys)

    def test_schema_9_anthropic_shape(self):
        """Schema 9 must be Anthropic-shaped (not OpenAI wrapper)."""
        schema = next(
            s for s in main.TOOL_SCHEMAS if s["name"] == "build_icp_document"
        )
        self.assertIn("name", schema)
        self.assertIn("description", schema)
        self.assertIn("input_schema", schema)
        self.assertNotIn("type", schema)  # No OpenAI {"type": "function"} wrapper
        self.assertEqual(schema["input_schema"]["type"], "object")
        self.assertIn("seed", schema["input_schema"]["properties"])
        self.assertIn("seed", schema["input_schema"]["required"])

    def test_schema_9_description_length(self):
        """Schema 9 description must be >= 50 chars."""
        schema = next(
            s for s in main.TOOL_SCHEMAS if s["name"] == "build_icp_document"
        )
        self.assertGreaterEqual(len(schema["description"]), 50)

    def test_schema_9_description_mentions_when_to_use(self):
        """Schema 9 description must mention WHEN to use the tool."""
        schema = next(
            s for s in main.TOOL_SCHEMAS if s["name"] == "build_icp_document"
        )
        desc = schema["description"].lower()
        self.assertIn("use this tool", desc)

    def test_schema_9_description_mentions_anchor_cap(self):
        """Schema 9 description must mention the 5-anchor constraint."""
        schema = next(
            s for s in main.TOOL_SCHEMAS if s["name"] == "build_icp_document"
        )
        desc = schema["description"]
        self.assertIn("5", desc, "Schema description must mention the 5-anchor cap")


# ===========================================================================
# ICPB4 — Anti-leakage: no catalog literals in the tool implementation
# ===========================================================================

class TestICPB4AntiLeakage(unittest.TestCase):
    """ICPB4 (G2 cross-check): no hardcoded catalog values in main.py."""

    def test_icpb4_no_catalog_domains_in_build_icp_source(self):
        """The build_icp_document function source must not contain real catalog domain literals.

        We check by reading the source lines of the function.
        This is a lightweight guard; the full G2 grep is run by the PM.
        """
        import inspect
        source = inspect.getsource(main.build_icp_document)
        # Real catalog domains from brands_catalog.csv — any one of these in source = leak
        # We test with a generic pattern check: the function prompt must not build in
        # any hardcoded brand/domain literal.
        # Specifically, the anchor_companies must come from runtime research, not literals.
        # We assert the source does NOT contain any hardcoded .com domain in a string literal
        # beyond what would come from parameterized input.
        # (A domain literal looks like "something.com" in a string context.)
        # The only domain-shaped string in the implementation should be the prompt template
        # placeholder or generic examples, not real catalog values.
        #
        # Test: no raw brand domains from the known catalog (from test fixture)
        catalog_test_domains = [
            "acmesports.com", "bloombeauty.com", "evilcorp.com", "pixelaudio.com",
        ]
        for domain in catalog_test_domains:
            self.assertNotIn(
                domain, source,
                f"Catalog domain literal '{domain}' found hardcoded in build_icp_document!"
            )

    def test_icpb4_icp_tags_read_at_runtime_not_hardcoded(self):
        """The build_icp_document implementation reads _ICP_TAGS at runtime (not hardcoded list)."""
        import inspect
        source = inspect.getsource(main.build_icp_document)
        # The implementation should reference '_ICP_TAGS' (the runtime constant)
        # rather than a hardcoded list of tag names inline.
        self.assertIn("_ICP_TAGS", source,
                      "build_icp_document should read _ICP_TAGS at runtime, not hardcode tags")


# ===========================================================================
# Error handling (tool errors are data, not crashes — CLAUDE.md §6.6)
# ===========================================================================

class TestICPBErrorHandling(unittest.TestCase):
    """Tool failures must return {"error": ...}, never raise."""

    def test_empty_seed_returns_error_dict(self):
        """An empty string seed must return an error dict, not raise."""
        fake_client = _make_fake_client({})
        fake_va = _make_fake_vector_a([])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            result = main.build_icp_document("")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_llm_raises_returns_error_dict(self):
        """If the LLM client raises, the tool must return {"error": ...}, not propagate."""
        class _RaisingMessages:
            def create(self, **kwargs):
                raise RuntimeError("simulated LLM outage")

        fake_client = MagicMock()
        fake_client.messages = _RaisingMessages()
        fake_va = _make_fake_vector_a(["somebrand.com"])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            result = main.build_icp_document("athleisure brands")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("build_icp_document failed", result["error"])

    def test_malformed_llm_json_still_returns_valid_shape(self):
        """If the LLM returns unparseable JSON, fall back to empty fields (not a crash)."""
        # Return a response that _parse_icp_json cannot parse
        bad_json_response = SimpleNamespace(
            content=[SimpleNamespace(text="Sorry, I cannot help with that.")],
            stop_reason="end_turn",
        )

        class _BadMessages:
            def create(self, **kwargs):
                return bad_json_response

        fake_client = MagicMock()
        fake_client.messages = _BadMessages()
        fake_va = _make_fake_vector_a([])
        with patch.object(main, "_get_client", return_value=fake_client), \
             patch.object(main, "_vector_a_search", side_effect=fake_va):
            result = main.build_icp_document("footwear brands")
        # Should return a valid dict — either a shaped ICP doc with empty fields or an error.
        self.assertIsInstance(result, dict)
        # Must not raise, must be serializable
        try:
            json.dumps(result)
        except (TypeError, ValueError) as exc:
            self.fail(f"Result not JSON-serializable after malformed LLM output: {exc}")


if __name__ == "__main__":
    unittest.main()
