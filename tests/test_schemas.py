"""tests/test_schemas.py — Stage 3: Tool JSON schema & dispatch checks (S0–S10).

Drafted only — PM runs in .venv.

S0  : exactly 8 schemas; names == function names == dispatch keys (three-way identity).
S1  : generate_search_queries schema well-formed (Anthropic shape, typed properties, required).
S2  : execute_3way_fanout schema well-formed.
S3  : extract_and_score_pool schema well-formed (only raw_pool exposed, not catalog_df).
S4  : analyze_company_chunk schema well-formed.
S5  : evaluate_icp_tags schema well-formed.
S6  : match_solicitation_angle schema well-formed.
S7  : request_reactfirst_pdf schema well-formed.
S8  : secured_calculator schema well-formed.
S9  : descriptions steer choice and state key constraints per tool.
S10 : live API smoke (gated — SKIPPED when ANTHROPIC_API_KEY is not set).
"""

import os
import re
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Import the module under test.  ENV4 guarantees this is side-effect-free.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES = [
    "generate_search_queries",
    "execute_3way_fanout",
    "extract_and_score_pool",
    "analyze_company_chunk",
    "evaluate_icp_tags",
    "match_solicitation_angle",
    "request_reactfirst_pdf",
    "secured_calculator",
]

ANTHROPIC_REQUIRED_KEYS = {"name", "description", "input_schema"}


def _is_anthropic_shape(schema: dict) -> bool:
    """Return True iff schema has exactly the Anthropic tool shape keys."""
    return ANTHROPIC_REQUIRED_KEYS.issubset(schema.keys())


def _is_not_openai_wrapper(schema: dict) -> bool:
    """Return True iff schema does NOT use the OpenAI {type:function} wrapper."""
    return schema.get("type") != "function" and "function" not in schema


def _input_schema(schema: dict) -> dict:
    """Return the input_schema sub-dict."""
    return schema["input_schema"]


def _properties(schema: dict) -> dict:
    return _input_schema(schema).get("properties", {})


def _required(schema: dict) -> list:
    return _input_schema(schema).get("required", [])


# ---------------------------------------------------------------------------
# S0 — Exactly 8 schemas; three-way name identity; import-time assert passes.
# ---------------------------------------------------------------------------

class TestS0:
    def test_exactly_8_schemas(self):
        """S0: len(TOOL_SCHEMAS) == 8."""
        assert len(main.TOOL_SCHEMAS) == 8, (
            f"Expected 8 schemas, got {len(main.TOOL_SCHEMAS)}"
        )

    def test_schema_names_equal_expected(self):
        """S0: Schema names are byte-identical to the 8 expected function names."""
        actual_names = [s["name"] for s in main.TOOL_SCHEMAS]
        assert actual_names == EXPECTED_TOOL_NAMES, (
            f"Schema name list mismatch.\nExpected: {EXPECTED_TOOL_NAMES}\nGot: {actual_names}"
        )

    def test_dispatch_keys_match_schema_names(self):
        """S0: TOOL_DISPATCH keys == schema names (two-way set equality)."""
        schema_names   = {s["name"] for s in main.TOOL_SCHEMAS}
        dispatch_names = set(main.TOOL_DISPATCH.keys())
        assert schema_names == dispatch_names, (
            f"TOOL_DISPATCH keys do not match TOOL_SCHEMAS names.\n"
            f"  Schema only:   {schema_names - dispatch_names}\n"
            f"  Dispatch only: {dispatch_names - schema_names}"
        )

    def test_dispatch_values_are_callables(self):
        """S0: Every TOOL_DISPATCH value is callable."""
        for name, fn in main.TOOL_DISPATCH.items():
            assert callable(fn), f"TOOL_DISPATCH['{name}'] is not callable"

    def test_dispatch_function_name_matches_key(self):
        """S0: Every TOOL_DISPATCH[name] is the module-level function of that name."""
        for name, fn in main.TOOL_DISPATCH.items():
            module_fn = getattr(main, name, None)
            assert module_fn is not None, f"Function '{name}' not found in main module"
            assert fn is module_fn, (
                f"TOOL_DISPATCH['{name}'] does not point to main.{name}"
            )

    def test_import_time_assert_passed(self):
        """S0: If we reach this point, the import-time assert in §7 has already passed.

        The import-time assert in main.py §7 fires when the module is first imported.
        If it had raised, the import above would have failed and we never get here.
        So reaching this test means the three-way assert passed.
        """
        # Verify by re-checking the conditions the assert guards.
        assert len(main.TOOL_SCHEMAS) == 8
        assert len(main.TOOL_DISPATCH) == 8
        schema_names   = {s["name"] for s in main.TOOL_SCHEMAS}
        dispatch_names = set(main.TOOL_DISPATCH.keys())
        assert schema_names == dispatch_names

    def test_no_openai_wrapper_in_any_schema(self):
        """S0 / S1–S8: No schema uses the OpenAI {type:'function'} wrapper."""
        for s in main.TOOL_SCHEMAS:
            assert _is_not_openai_wrapper(s), (
                f"Schema '{s['name']}' uses OpenAI wrapper format"
            )

    def test_all_schemas_have_anthropic_keys(self):
        """S0 / S1–S8: Every schema has name, description, input_schema."""
        for s in main.TOOL_SCHEMAS:
            assert _is_anthropic_shape(s), (
                f"Schema '{s.get('name','?')}' missing required keys: "
                f"{ANTHROPIC_REQUIRED_KEYS - set(s.keys())}"
            )

    def test_input_schema_type_is_object(self):
        """S0 / S1–S8: Every input_schema has type='object'."""
        for s in main.TOOL_SCHEMAS:
            isch = _input_schema(s)
            assert isch.get("type") == "object", (
                f"Schema '{s['name']}' input_schema.type != 'object' "
                f"(got {isch.get('type')!r})"
            )

    def test_all_schemas_have_properties(self):
        """S0 / S1–S8: Every input_schema has a non-empty 'properties' dict."""
        for s in main.TOOL_SCHEMAS:
            props = _properties(s)
            assert isinstance(props, dict) and props, (
                f"Schema '{s['name']}' has empty or missing properties"
            )

    def test_all_schemas_have_required_array(self):
        """S0 / S1–S8: Every input_schema has a 'required' list (may be empty but present)."""
        for s in main.TOOL_SCHEMAS:
            req = _required(s)
            assert isinstance(req, list), (
                f"Schema '{s['name']}' required is not a list"
            )

    def test_required_fields_exist_in_properties(self):
        """S0 / S1–S8: Every field listed in required also appears in properties."""
        for s in main.TOOL_SCHEMAS:
            props = set(_properties(s).keys())
            for field_name in _required(s):
                assert field_name in props, (
                    f"Schema '{s['name']}': required field '{field_name}' "
                    f"not in properties {props}"
                )


# ---------------------------------------------------------------------------
# S1 — generate_search_queries
# ---------------------------------------------------------------------------

class TestS1:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "generate_search_queries")

    def test_name(self):
        assert self.SCHEMA["name"] == "generate_search_queries"

    def test_required_contains_vertical_seed(self):
        assert "vertical_seed" in _required(self.SCHEMA)

    def test_target_count_not_in_required(self):
        """target_count is optional (has a default of 15) — must NOT be in required."""
        assert "target_count" not in _required(self.SCHEMA)

    def test_vertical_seed_type_is_string(self):
        assert _properties(self.SCHEMA)["vertical_seed"]["type"] == "string"

    def test_target_count_type_is_integer(self):
        assert _properties(self.SCHEMA)["target_count"]["type"] == "integer"

    def test_description_mentions_discovery(self):
        desc = self.SCHEMA["description"].lower()
        assert "discovery" in desc or "variation" in desc or "search" in desc, (
            "Description should state when to use the tool (discovery/variation context)"
        )

    def test_description_mentions_target_count(self):
        desc = self.SCHEMA["description"]
        assert "target_count" in desc or "10" in desc or "20" in desc, (
            "Description should mention the target_count range constraint"
        )


# ---------------------------------------------------------------------------
# S2 — execute_3way_fanout
# ---------------------------------------------------------------------------

class TestS2:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "execute_3way_fanout")

    def test_name(self):
        assert self.SCHEMA["name"] == "execute_3way_fanout"

    def test_required_contains_queries(self):
        assert "queries" in _required(self.SCHEMA)

    def test_queries_type_is_array(self):
        assert _properties(self.SCHEMA)["queries"]["type"] == "array"

    def test_queries_items_type_is_string(self):
        items = _properties(self.SCHEMA)["queries"].get("items", {})
        assert items.get("type") == "string", (
            "queries items must be typed as string"
        )

    def test_description_mentions_vector_c_rule(self):
        """S9: Description must state the Vector C recovery rule."""
        desc = self.SCHEMA["description"]
        # Must mention the < 2 threshold for Vector C
        assert "2" in desc and ("vector c" in desc.lower() or "tavily" in desc.lower() or "recovery" in desc.lower()), (
            "Description must state that Vector C fires only when A+B < 2 domains"
        )

    def test_description_mentions_parallel(self):
        desc = self.SCHEMA["description"].lower()
        assert "concurrent" in desc or "parallel" in desc, (
            "Description should mention that A and B run concurrently/in parallel"
        )


# ---------------------------------------------------------------------------
# S3 — extract_and_score_pool
# ---------------------------------------------------------------------------

class TestS3:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "extract_and_score_pool")

    def test_name(self):
        assert self.SCHEMA["name"] == "extract_and_score_pool"

    def test_required_contains_only_raw_pool(self):
        """S3: catalog_df is runtime-injected — must NOT appear in schema."""
        req = _required(self.SCHEMA)
        assert "raw_pool" in req, "raw_pool must be required"
        assert "catalog_df" not in req, (
            "catalog_df is runtime-injected and must NOT appear in required"
        )

    def test_catalog_df_not_in_properties(self):
        """S3: catalog_df must NOT be in properties either."""
        props = _properties(self.SCHEMA)
        assert "catalog_df" not in props, (
            "catalog_df must not be in schema properties (it is runtime-injected)"
        )

    def test_raw_pool_type_is_array(self):
        assert _properties(self.SCHEMA)["raw_pool"]["type"] == "array"

    def test_description_mentions_catalog_internal(self):
        """S9: Description must say catalog mapping happens internally."""
        desc = self.SCHEMA["description"].lower()
        assert "catalog" in desc and ("internal" in desc or "internally" in desc), (
            "Description must state that catalog mapping happens internally"
        )

    def test_description_mentions_dedup(self):
        desc = self.SCHEMA["description"].lower()
        assert "de-dup" in desc or "dedup" in desc or "de-duplicate" in desc, (
            "Description should mention de-duplication"
        )


# ---------------------------------------------------------------------------
# S4 — analyze_company_chunk
# ---------------------------------------------------------------------------

class TestS4:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "analyze_company_chunk")

    def test_name(self):
        assert self.SCHEMA["name"] == "analyze_company_chunk"

    def test_required_contains_domains(self):
        assert "domains" in _required(self.SCHEMA)

    def test_domains_type_is_array(self):
        assert _properties(self.SCHEMA)["domains"]["type"] == "array"

    def test_domains_items_type_is_string(self):
        items = _properties(self.SCHEMA)["domains"].get("items", {})
        assert items.get("type") == "string"

    def test_description_mentions_100_ceiling(self):
        """S9: Description must state the ≤100 domains ceiling."""
        desc = self.SCHEMA["description"]
        assert "100" in desc, (
            "Description must mention the CHUNK_MAX_DOMAINS=100 ceiling"
        )

    def test_description_mentions_800s_budget(self):
        """S9: Description must state the 800s budget."""
        desc = self.SCHEMA["description"]
        assert "800" in desc, (
            "Description must mention the CHUNK_TIME_BUDGET_S=800 budget"
        )

    def test_description_mentions_three_pixels(self):
        """S9: Description must mention all three pixel types."""
        desc = self.SCHEMA["description"].lower()
        assert "tiktok" in desc or "tiktok_pixel" in desc, "Missing TikTok pixel mention"
        assert "meta" in desc or "meta_pixel" in desc, "Missing Meta pixel mention"
        assert "gtm" in desc or "google tag manager" in desc, "Missing GTM mention"

    def test_description_mentions_timeout_partial(self):
        """S9: Description should mention partial results on timeout."""
        desc = self.SCHEMA["description"].lower()
        assert "timeout" in desc or "timed_out" in desc or "partial" in desc, (
            "Description should mention partial results / timeout behavior"
        )


# ---------------------------------------------------------------------------
# S5 — evaluate_icp_tags
# ---------------------------------------------------------------------------

class TestS5:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "evaluate_icp_tags")

    def test_name(self):
        assert self.SCHEMA["name"] == "evaluate_icp_tags"

    def test_required_contains_company_profile_data(self):
        assert "company_profile_data" in _required(self.SCHEMA)

    def test_company_profile_data_type_is_string(self):
        assert _properties(self.SCHEMA)["company_profile_data"]["type"] == "string"

    def test_description_mentions_icp_threshold_3(self):
        """S9: Description must state the ≥3 ICP tag qualification rule."""
        desc = self.SCHEMA["description"]
        # Must mention the threshold numerically and the qualification condition
        assert "3" in desc and (">= 3" in desc or "≥3" in desc or ">=3" in desc or "≥ 3" in desc or "iff" in desc or "if and only if" in desc.lower()), (
            "Description must state the ≥3 ICP qualification rule"
        )

    def test_description_mentions_pure_no_network(self):
        """S9: Description should state it's a pure/structural function."""
        desc = self.SCHEMA["description"].lower()
        assert "pure" in desc or "no network" in desc or "deterministic" in desc, (
            "Description should note this is a pure/deterministic function"
        )

    def test_description_mentions_trust_gate(self):
        """S9: Description should mention the Trust-Gated path for borderline (exactly 3)."""
        desc = self.SCHEMA["description"].lower()
        # The trust-gate for exactly 3 tags should be mentioned
        assert "trust" in desc or "human" in desc or "borderline" in desc or "exactly 3" in desc, (
            "Description should mention the trust-gated human-in-loop path"
        )


# ---------------------------------------------------------------------------
# S6 — match_solicitation_angle
# ---------------------------------------------------------------------------

class TestS6:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "match_solicitation_angle")

    def test_name(self):
        assert self.SCHEMA["name"] == "match_solicitation_angle"

    def test_required_fields(self):
        req = _required(self.SCHEMA)
        assert "scraped_narrative_context" in req
        assert "category_path" in req

    def test_scraped_narrative_context_type_is_string(self):
        assert _properties(self.SCHEMA)["scraped_narrative_context"]["type"] == "string"

    def test_category_path_type_is_string(self):
        assert _properties(self.SCHEMA)["category_path"]["type"] == "string"

    def test_description_mentions_tier_1_to_4(self):
        """S9: Description must mention the Tier 1–4 output and what Tier 4 means."""
        desc = self.SCHEMA["description"]
        assert "Tier 4" in desc and ("No Match" in desc or "fallback" in desc.lower()), (
            "Description must mention Tier 4 = No Match and the Policy 6 fallback"
        )
        assert "Tier 1" in desc, "Description must mention Tier 1 (Critical Fit or highest priority)"

    def test_description_mentions_max_angles_ceiling(self):
        """S9: Description must mention the ≤3 output angles ceiling."""
        desc = self.SCHEMA["description"]
        assert "3" in desc and ("MAX_ANGLES" in desc or "angle" in desc.lower() or "ceiling" in desc.lower()), (
            "Description must mention the MAX_ANGLES=3 ceiling"
        )

    def test_description_mentions_catalog_for_category_path(self):
        """S9: Description should say category_path comes from the catalog."""
        desc = self.SCHEMA["description"].lower()
        assert "catalog" in desc and "category" in desc, (
            "Description should say category_path must come from brands_catalog.csv"
        )


# ---------------------------------------------------------------------------
# S7 — request_reactfirst_pdf
# ---------------------------------------------------------------------------

class TestS7:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "request_reactfirst_pdf")

    def test_name(self):
        assert self.SCHEMA["name"] == "request_reactfirst_pdf"

    def test_required_fields(self):
        req = _required(self.SCHEMA)
        assert "target_domain" in req
        assert "validated_angle_key" in req
        assert "calculated_risk_score" in req

    def test_target_domain_type_is_string(self):
        assert _properties(self.SCHEMA)["target_domain"]["type"] == "string"

    def test_validated_angle_key_type_is_string(self):
        assert _properties(self.SCHEMA)["validated_angle_key"]["type"] == "string"

    def test_calculated_risk_score_type_is_number(self):
        """calculated_risk_score must be 'number' (not 'integer' — it's a float)."""
        assert _properties(self.SCHEMA)["calculated_risk_score"]["type"] == "number"

    def test_description_mentions_only_tool_for_outbound(self):
        """S9: Description must state this is the ONLY tool targeting the outbound subdomain."""
        desc = self.SCHEMA["description"]
        assert "ONLY" in desc or "only" in desc, (
            "Description must state this is the only tool targeting outreach.reactfirst.ai"
        )
        assert "outreach.reactfirst.ai" in desc or "outbound" in desc.lower(), (
            "Description must mention the outbound subdomain constraint"
        )

    def test_description_mentions_no_tier_4(self):
        """S9: Description must say not to call this for Tier 4."""
        desc = self.SCHEMA["description"]
        assert "Tier 4" in desc and ("NEVER" in desc or "never" in desc or "No Match" in desc), (
            "Description must forbid calling request_reactfirst_pdf for Tier 4 results"
        )

    def test_description_mentions_max_angles_ceiling(self):
        """S9: Description must mention the ≤3 PDFs / MAX_ANGLES ceiling."""
        desc = self.SCHEMA["description"]
        assert "3" in desc and ("MAX_ANGLES" in desc or "ceiling" in desc.lower() or "angle" in desc.lower()), (
            "Description must mention the MAX_ANGLES=3 ceiling"
        )


# ---------------------------------------------------------------------------
# S8 — secured_calculator
# ---------------------------------------------------------------------------

class TestS8:
    SCHEMA = next(s for s in main.TOOL_SCHEMAS if s["name"] == "secured_calculator")

    def test_name(self):
        assert self.SCHEMA["name"] == "secured_calculator"

    def test_required_contains_expression(self):
        assert "expression" in _required(self.SCHEMA)

    def test_expression_type_is_string(self):
        assert _properties(self.SCHEMA)["expression"]["type"] == "string"

    def test_description_mentions_no_eval(self):
        """S9: Description must explicitly state no eval/exec is used."""
        desc = self.SCHEMA["description"].lower()
        assert "no eval" in desc or "not eval" in desc or "never" in desc, (
            "Description must state that NO eval/exec is used"
        )

    def test_description_mentions_operator_whitelist(self):
        """S9: Description must mention the allowed operators."""
        desc = self.SCHEMA["description"]
        # Should mention the allowed arithmetic ops
        assert "+" in desc or "* " in desc or "- " in desc or "/ " in desc, (
            "Description should list the allowed arithmetic operators"
        )

    def test_description_mentions_sop_smoke(self):
        """S9: Description should include the SOP smoke expression."""
        desc = self.SCHEMA["description"]
        assert "1700" in desc or "(1700" in desc, (
            "Description should include the SOP smoke '(1700 + 450) * 1.15'"
        )

    def test_description_forbids_power_and_function_calls(self):
        """S9: Description must mention that ** (power) and function calls are forbidden."""
        desc = self.SCHEMA["description"].lower()
        assert "**" in desc or "power" in desc or "function call" in desc, (
            "Description must mention that ** (power) and function calls are forbidden"
        )


# ---------------------------------------------------------------------------
# S9 — Cross-schema description quality checks
# ---------------------------------------------------------------------------

class TestS9:
    """Verifies that every description states *when to use* and its key constraint."""

    def test_all_descriptions_non_empty_and_substantive(self):
        """Every description must be at least 50 characters and not vague filler."""
        for s in main.TOOL_SCHEMAS:
            desc = s["description"]
            assert len(desc) >= 50, (
                f"Schema '{s['name']}' description is too short ({len(desc)} chars)"
            )

    def test_descriptions_state_when_to_use(self):
        """Each description should say 'Use this tool' or equivalent."""
        for s in main.TOOL_SCHEMAS:
            desc = s["description"].lower()
            assert "use this tool" in desc or "call this" in desc or "use this" in desc, (
                f"Schema '{s['name']}' description does not state when to use the tool"
            )

    def test_tool2_vectors_c_rule_exact(self):
        """S9: Tool 2 description must state the exact Vector C rule (< 2 domains)."""
        schema = next(s for s in main.TOOL_SCHEMAS if s["name"] == "execute_3way_fanout")
        desc = schema["description"]
        # Must have < 2 or fewer than 2
        assert "< 2" in desc or "fewer than 2" in desc or "<2" in desc, (
            "execute_3way_fanout description must state Vector C fires when A+B < 2 domains"
        )

    def test_tool5_icp_threshold_exact(self):
        """S9: Tool 5 description must state >= 3 ICP tags qualification rule."""
        schema = next(s for s in main.TOOL_SCHEMAS if s["name"] == "evaluate_icp_tags")
        desc = schema["description"]
        assert ">= 3" in desc or "≥3" in desc or "≥ 3" in desc or ">=3" in desc, (
            "evaluate_icp_tags description must state the >= 3 tag threshold"
        )

    def test_tool8_no_eval_statement(self):
        """S9: Tool 8 description must explicitly say 'no eval'."""
        schema = next(s for s in main.TOOL_SCHEMAS if s["name"] == "secured_calculator")
        desc = schema["description"].lower()
        assert "no eval" in desc, (
            "secured_calculator description must explicitly say 'no eval'"
        )

    def test_tool3_catalog_df_wrinkle_documented(self):
        """S9: Tool 3 description must say catalog mapping is internal (catalog_df wrinkle)."""
        schema = next(s for s in main.TOOL_SCHEMAS if s["name"] == "extract_and_score_pool")
        desc = schema["description"].lower()
        assert "internal" in desc or "internally" in desc, (
            "extract_and_score_pool description must say catalog mapping happens internally"
        )

    def test_tool6_tier4_routes_to_fallback(self):
        """S9: Tool 6 description must say Tier 4 routes to the Policy 6 fallback."""
        schema = next(s for s in main.TOOL_SCHEMAS if s["name"] == "match_solicitation_angle")
        desc = schema["description"]
        assert "Tier 4" in desc and ("fallback" in desc.lower() or "Policy 6" in desc), (
            "match_solicitation_angle description must say Tier 4 → Policy 6 fallback"
        )

    def test_tool7_only_outbound_subdomain(self):
        """S9: Tool 7 description must say it is the ONLY tool for outreach.reactfirst.ai."""
        schema = next(s for s in main.TOOL_SCHEMAS if s["name"] == "request_reactfirst_pdf")
        desc = schema["description"]
        assert "outreach.reactfirst.ai" in desc or ("ONLY" in desc and "outbound" in desc.lower()), (
            "request_reactfirst_pdf description must state it is the only outbound tool"
        )


# ---------------------------------------------------------------------------
# S10 — Live API smoke (GATED — SKIPPED if ANTHROPIC_API_KEY is not set)
# ---------------------------------------------------------------------------

class TestS10:
    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="S10 is a gated live call — ANTHROPIC_API_KEY not set; SKIPPED (not failed)",
    )
    def test_schemas_accepted_by_anthropic_api(self):
        """S10 (gated): client.messages.create(..., tools=TOOL_SCHEMAS) does not 400.

        Only runs when ANTHROPIC_API_KEY is set in the environment.
        This is a smoke test — we send a minimal message and verify the API
        accepts TOOL_SCHEMAS without returning an HTTP 400 error.
        """
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        # Minimal call — just check the schemas are accepted (tool_choice="auto").
        response = client.messages.create(
            model=main.LIGHT_MODEL,
            max_tokens=50,
            tools=main.TOOL_SCHEMAS,
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": "ping"}],
        )
        # If we get here without an exception, the schemas were accepted.
        assert response is not None, "API returned None response"
        # Acceptable stop reasons: end_turn, tool_use (model chose to call a tool on 'ping')
        assert response.stop_reason in {"end_turn", "tool_use"}, (
            f"Unexpected stop_reason: {response.stop_reason}"
        )
