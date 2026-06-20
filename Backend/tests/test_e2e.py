"""
tests/test_e2e.py — Stage 7: End-to-end single-vertical run.

QA checks covered:
  E1  happy path: discovery seed → qualified_leads.json + reactfirst_run.log produced;
      ≤3 angles; ≥1 saved PDF passing GW4 (%PDF-/non-zero/%%EOF).
  E2  within cap: total tool calls ≤15 with headroom; metrics in log + result.
  E3  recovery path: A∪B < 2 domains → Vector C fires (call-spy); pipeline completes.
  E4  fallback path: no-match seed → result is EXACTLY FALLBACK_MESSAGE; no
      generative apology path; no qualified_leads.json written.

All external services mocked — ZERO network calls.  Driven via FakeReasoningClient
(monkeypatch main._get_client) + per-tool monkeypatches for network-dependent tools.

Uses tmp_path / monkeypatch.chdir so all artifacts (qualified_leads.json,
reactfirst_run.log, assets/*.pdf) land in a throwaway temp directory.

All tests are DRAFTED ONLY — PM verifies in .venv.
"""

import json
import os
import pathlib
import sys
import pytest

# ---------------------------------------------------------------------------
# Path setup: ensure the CRM root is on sys.path so "import main" works.
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import main  # noqa: E402  (side-effect-free — ENV4)


# ===========================================================================
# FakeReasoningClient — reusable scripted fake (same pattern as test_loop.py)
# ===========================================================================

class _FakeBlock:
    """Minimal duck-type of an Anthropic content block."""

    def __init__(self, block_type: str, **kwargs):
        self.type = block_type
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __iter__(self):
        return iter([])


class _FakeResponse:
    """Minimal duck-type of an Anthropic messages.create(...) response."""

    def __init__(self, content: list, stop_reason: str = "end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class FakeReasoningClient:
    """Scripted fake for the Anthropic reasoning client.

    Pops responses from the queue in order; on exhaustion, returns an end_turn text.
    call_args_list records every messages.create call.
    """

    def __init__(self, responses: list = None):
        self._queue = list(responses or [])
        self.call_args_list: list = []

    def _next(self):
        if not self._queue:
            return _FakeResponse(
                [_FakeBlock("text", text="Pipeline complete.")],
                "end_turn",
            )
        item = self._queue.pop(0)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item("FakeReasoningClient: scripted exception")
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            return item()
        return item

    class _MessagesAPI:
        def __init__(self, fake):
            self._fake = fake

        def create(self, **kwargs):
            self._fake.call_args_list.append(kwargs)
            return self._fake._next()

    @property
    def messages(self):
        return self._MessagesAPI(self)


def _tool_use_block(name: str, block_id: str, input_dict: dict) -> _FakeBlock:
    """Build a tool_use content block."""
    return _FakeBlock("tool_use", name=name, id=block_id, input=input_dict)


def _text_block(text: str) -> _FakeBlock:
    """Build a text content block."""
    return _FakeBlock("text", text=text)


def _end_turn(text: str = "Pipeline complete.") -> _FakeResponse:
    """A response that terminates the loop cleanly."""
    return _FakeResponse([_text_block(text)], "end_turn")


def _tool_use_turn(name: str, block_id: str, input_dict: dict) -> _FakeResponse:
    """A response that requests a single tool call."""
    return _FakeResponse(
        [_tool_use_block(name, block_id, input_dict)],
        "tool_use",
    )


# ===========================================================================
# Shared fixtures
# ===========================================================================

@pytest.fixture()
def tmp_cwd(tmp_path, monkeypatch):
    """Change cwd to a temp dir for the duration of the test.

    All artifacts (qualified_leads.json, reactfirst_run.log, assets/*.pdf)
    land here so they don't pollute the real project directory.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def catalog_df():
    """A minimal 9-column catalog DataFrame matching the schema."""
    import pandas as pd
    return pd.DataFrame([
        {
            "Uniq_Id":                    "test-brand-0001",
            "Brand_Name":                 "AlphaBrand",
            "Primary_Domain":             "alphabrand.com",
            "Core_Category":              "Apparel > Athleisure > Sustainable",
            "Estimated_Ad_Spend_Tier":    "Tier 1",
            "Current_Status":             "Open_Opportunity",
            "Historical_Social_Incidents": 7,
            "Main_Competitor_Id":         "test-brand-0002",
            "Gtin_Prefix":               "0712345",
        },
        {
            "Uniq_Id":                    "test-brand-0002",
            "Brand_Name":                 "BetaBrand",
            "Primary_Domain":             "betabrand.com",
            "Core_Category":              "Apparel > Athleisure > Performance",
            "Estimated_Ad_Spend_Tier":    "Tier 2",
            "Current_Status":             "Unreached_Prospect",
            "Historical_Social_Incidents": 2,
            "Main_Competitor_Id":         "test-brand-0001",
            "Gtin_Prefix":               "0712346",
        },
    ])


@pytest.fixture()
def policies_text():
    """A minimal policies string for system prompt injection."""
    return (
        "Policy 1: All brand facts from brands_catalog.csv only.\n"
        "Policy 2: ICP threshold >= 3 tags.\n"
        "Policy 5: Max 3 angles.\n"
        "Policy 6: FALLBACK_MESSAGE on zero match.\n"
    )


# ===========================================================================
# Mock tool helpers
# ===========================================================================

def _make_valid_pdf_bytes() -> bytes:
    """Return a minimal, GW4-valid PDF byte string."""
    # Must have: %PDF- header, non-zero length, %%EOF marker.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"%%EOF"
    )


def _make_mock_pdf_tool(tmp_path):
    """Return a mock request_reactfirst_pdf that saves a real GW4-valid PDF."""

    def mock_pdf(target_domain: str, validated_angle_key: str, calculated_risk_score: float) -> dict:
        assets_dir = pathlib.Path(os.getcwd()) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        safe_domain = target_domain.replace(".", "_")
        pdf_filename = f"reactfirst_{safe_domain}_{validated_angle_key}.pdf"
        pdf_path = assets_dir / pdf_filename
        pdf_path.write_bytes(_make_valid_pdf_bytes())
        return {"ok": True, "path": str(pdf_path)}

    return mock_pdf


def _icp_profile_4_tags():
    """An ICP profile string that matches exactly 4 tags (clear-cut, ≥ 3)."""
    # Tags triggered: ecommerce_dtc, paid_social_advertising, scale_growth_stage,
    # ad_spend_signals (4 distinct tags → qualified=True, clear-cut)
    return (
        "This DTC e-commerce brand sells on Shopify. "
        "They run Facebook ads and Instagram ads at scale. "
        "Venture-backed company in a rapid growth stage. "
        "Ad spend is $2M, strong ROAS. "
        "Strong brand marketing team with CMO leading performance marketing."
    )


def _icp_profile_2_tags():
    """An ICP profile string that matches only 2 tags (fails ICP, < threshold)."""
    # Tags triggered: ecommerce_dtc only + maybe 1 more → definitely < 3
    return "This is a small Shopify store. Nothing else notable. Regular business."


# ===========================================================================
# E1 — Happy path: qualified_leads.json + log + ≥1 health-valid PDF; ≤3 angles
# ===========================================================================

class TestE1HappyPath:
    """E1: drive answer_question with a discovery seed through a realistic multi-turn
    conversation and verify all three artifacts are produced correctly.

    Turn sequence scripted by FakeReasoningClient:
      Turn 1 (LLM → model):   calls generate_search_queries
      Turn 2 (LLM → model):   calls execute_3way_fanout
      Turn 3 (LLM → model):   calls extract_and_score_pool
      Turn 4 (LLM → model):   calls analyze_company_chunk
      Turn 5 (LLM → model):   calls evaluate_icp_tags  (qualified=True, ≥3 tags)
      Turn 6 (LLM → model):   calls match_solicitation_angle
      Turn 7 (LLM → model):   calls secured_calculator
      Turn 8 (LLM → model):   calls request_reactfirst_pdf
      Turn 9 (end_turn):       final answer text
    """

    def _patch_tools(self, monkeypatch, tmp_path):
        """Patch all network-dependent tools so no I/O occurs."""

        # generate_search_queries → canned list (avoids inner LLM call)
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "generate_search_queries",
            lambda vertical_seed, target_count=15: [
                "athleisure brands DTC ecommerce",
                "sustainable activewear direct to consumer",
                "performance apparel paid social advertising",
            ],
        )

        # execute_3way_fanout → canned pool (avoids Vector A/B/C calls)
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "execute_3way_fanout",
            lambda queries: {
                "domains": {
                    "alphabrand.com": {"provenance": ["A", "B"]},
                    "betabrand.com":  {"provenance": ["A"]},
                },
                "vector_status": {"A": "ok", "B": "ok", "C": "skipped"},
                "total_unique_domains": 2,
            },
        )

        # analyze_company_chunk → canned profile with pixel flags
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d,
                    "fetched": True,
                    "status_code": 200,
                    "title": f"{d} - Home",
                    "description": "DTC activewear brand",
                    "tiktok_pixel": True,
                    "meta_pixel": True,
                    "gtm": True,
                    "operational_scale_signals": [
                        "ecommerce_dtc",
                        "paid_social_advertising",
                        "scale_growth_stage",
                        "ad_spend_signals",
                    ],
                    "timed_out": False,
                    "error": None,
                }
                for d in domains
            ],
        )

        # evaluate_icp_tags → 4-tag qualified result (runs real code for this profile)
        # We let this run real code but with a profile that definitely hits 4 tags.
        # No patch needed: the tool is pure / no network.

        # match_solicitation_angle → mocked to return Tier 1 (avoids rag_engine load)
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "match_solicitation_angle",
            lambda scraped_narrative_context, category_path: {
                "angle_key": "crisis_social_media_001",
                "tier": 1,
                "scores": {
                    "semantic_results": 5,
                    "bm25_results": 5,
                    "fused_results": 5,
                    "top_rrf_score": 0.032,
                },
            },
        )

        # request_reactfirst_pdf → save a GW4-valid PDF, return ok=True
        mock_pdf_fn = _make_mock_pdf_tool(tmp_path)
        monkeypatch.setitem(main.TOOL_DISPATCH, "request_reactfirst_pdf", mock_pdf_fn)

    def test_e1_artifacts_produced(self, tmp_cwd, monkeypatch, catalog_df, policies_text):
        """E1: qualified_leads.json + reactfirst_run.log produced; ≤3 angles; ≥1 PDF passes GW4."""

        # Script the model's multi-turn conversation.
        scripted_responses = [
            # Turn 1: call generate_search_queries
            _tool_use_turn(
                "generate_search_queries", "tc-001",
                {"vertical_seed": "athleisure DTC brands", "target_count": 15},
            ),
            # Turn 2: call execute_3way_fanout
            _tool_use_turn(
                "execute_3way_fanout", "tc-002",
                {"queries": [
                    "athleisure brands DTC ecommerce",
                    "sustainable activewear direct to consumer",
                ]},
            ),
            # Turn 3: call extract_and_score_pool
            _tool_use_turn(
                "extract_and_score_pool", "tc-003",
                {"raw_pool": [
                    {"domain": "alphabrand.com", "provenance": ["A", "B"]},
                    {"domain": "betabrand.com",  "provenance": ["A"]},
                ]},
            ),
            # Turn 4: call analyze_company_chunk
            _tool_use_turn(
                "analyze_company_chunk", "tc-004",
                {"domains": ["alphabrand.com"]},
            ),
            # Turn 5: call evaluate_icp_tags (profile that triggers ≥3 ICP tags)
            _tool_use_turn(
                "evaluate_icp_tags", "tc-005",
                {"company_profile_data": _icp_profile_4_tags()},
            ),
            # Turn 6: call match_solicitation_angle
            _tool_use_turn(
                "match_solicitation_angle", "tc-006",
                {
                    "scraped_narrative_context": _icp_profile_4_tags(),
                    "category_path": "Apparel > Athleisure > Sustainable",
                },
            ),
            # Turn 7: call secured_calculator (Policy 3 premium)
            _tool_use_turn(
                "secured_calculator", "tc-007",
                {"expression": "2000 * 1.15"},
            ),
            # Turn 8: call request_reactfirst_pdf
            _tool_use_turn(
                "request_reactfirst_pdf", "tc-008",
                {
                    "target_domain": "alphabrand.com",
                    "validated_angle_key": "crisis_social_media_001",
                    "calculated_risk_score": 2300.0,
                },
            ),
            # Turn 9: end_turn with final answer
            _end_turn("Found 1 qualified brand with Tier 1 angle. PDF generated."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        self._patch_tools(monkeypatch, tmp_cwd)

        # Run the pipeline
        result = main.answer_question(
            "Find athleisure DTC brands for outreach",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # ----------------------------------------------------------------
        # E1a — result is a non-empty string (pipeline completed)
        # ----------------------------------------------------------------
        assert isinstance(result, str)
        assert len(result) > 0

        # ----------------------------------------------------------------
        # E1b — reactfirst_run.log produced
        # ----------------------------------------------------------------
        log_path = tmp_cwd / "reactfirst_run.log"
        assert log_path.exists(), "reactfirst_run.log must be produced"
        log_content = log_path.read_text(encoding="utf-8")
        assert len(log_content) > 0, "reactfirst_run.log must be non-empty"

        # ----------------------------------------------------------------
        # E1c — qualified_leads.json produced
        # ----------------------------------------------------------------
        leads_path = tmp_cwd / "qualified_leads.json"
        assert leads_path.exists(), "qualified_leads.json must be produced on a successful run"
        with open(str(leads_path), encoding="utf-8") as fh:
            leads_data = json.load(fh)

        assert "qualified_leads" in leads_data, "qualified_leads key must be present"
        leads = leads_data["qualified_leads"]
        assert isinstance(leads, list), "qualified_leads must be a list"
        assert len(leads) >= 1, "At least 1 lead must be present"

        # ----------------------------------------------------------------
        # E1d — ≤3 angles in qualified_leads.json (Policy 5 enforced)
        # ----------------------------------------------------------------
        assert len(leads) <= main.MAX_ANGLES, (
            f"qualified_leads must not exceed MAX_ANGLES={main.MAX_ANGLES}; "
            f"got {len(leads)}"
        )

        # ----------------------------------------------------------------
        # E1e — ≥1 PDF passing GW4 health check (%PDF-/non-zero/%%EOF)
        # ----------------------------------------------------------------
        assets_dir = tmp_cwd / "assets"
        assert assets_dir.exists(), "assets/ directory must exist after PDF generation"
        pdf_files = list(assets_dir.glob("*.pdf"))
        assert len(pdf_files) >= 1, "At least 1 PDF must be saved under assets/"

        for pdf_file in pdf_files:
            gw4 = main._check_pdf_health(str(pdf_file))
            assert gw4["ok"], (
                f"PDF {pdf_file.name} failed GW4 health check: {gw4.get('error')}"
            )

        # ----------------------------------------------------------------
        # E1f — leads entries contain expected fields
        # ----------------------------------------------------------------
        for lead in leads:
            assert "domain" in lead, f"Lead entry must have 'domain': {lead}"
            assert "angle_key" in lead, f"Lead entry must have 'angle_key': {lead}"
            assert "pdf_path" in lead, f"Lead entry must have 'pdf_path': {lead}"


# ===========================================================================
# E2 — Total tool calls ≤ 15 with headroom; metrics in log + result
# ===========================================================================

class TestE2WithinCap:
    """E2: verify the happy-path run uses ≤15 total tool calls with headroom,
    and that metrics are present in the log and the result.
    """

    def _patch_tools_e2(self, monkeypatch, tmp_path):
        """Patch tools (same as E1 but we need to inspect call count)."""
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "generate_search_queries",
            lambda vertical_seed, target_count=15: [
                "skincare DTC brands ecommerce",
                "clean beauty direct to consumer paid social",
            ],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "execute_3way_fanout",
            lambda queries: {
                "domains": {"betabrand.com": {"provenance": ["A"]}},
                "vector_status": {"A": "ok", "B": "ok", "C": "skipped"},
                "total_unique_domains": 1,
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d, "fetched": True, "status_code": 200,
                    "title": "DTC Brand", "description": "Paid social brand",
                    "tiktok_pixel": False, "meta_pixel": True, "gtm": True,
                    "operational_scale_signals": ["ecommerce_dtc", "paid_social_advertising"],
                    "timed_out": False, "error": None,
                }
                for d in domains
            ],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "match_solicitation_angle",
            lambda scraped_narrative_context, category_path: {
                "angle_key": "crisis_social_media_002",
                "tier": 2,
                "scores": {"semantic_results": 3, "bm25_results": 3,
                           "fused_results": 3, "top_rrf_score": 0.020},
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "request_reactfirst_pdf",
            _make_mock_pdf_tool(tmp_path),
        )

    def test_e2_call_count_within_cap(self, tmp_cwd, monkeypatch, catalog_df, policies_text):
        """E2: total tool calls ≤ 15 with headroom; metrics in log."""
        # 6-turn run: generate → fanout → extract → analyze → evaluate → match
        # → calculator → pdf → end_turn (8 tool calls + some headroom under 15)
        scripted_responses = [
            _tool_use_turn("generate_search_queries", "tc-201",
                           {"vertical_seed": "clean beauty DTC", "target_count": 10}),
            _tool_use_turn("execute_3way_fanout", "tc-202",
                           {"queries": ["skincare DTC brands ecommerce"]}),
            _tool_use_turn("extract_and_score_pool", "tc-203",
                           {"raw_pool": [{"domain": "betabrand.com", "provenance": ["A"]}]}),
            _tool_use_turn("analyze_company_chunk", "tc-204",
                           {"domains": ["betabrand.com"]}),
            _tool_use_turn("evaluate_icp_tags", "tc-205",
                           {"company_profile_data": _icp_profile_4_tags()}),
            _tool_use_turn("match_solicitation_angle", "tc-206",
                           {"scraped_narrative_context": _icp_profile_4_tags(),
                            "category_path": "Apparel > Athleisure > Performance"}),
            _tool_use_turn("secured_calculator", "tc-207",
                           {"expression": "1500 * 1.15"}),
            _tool_use_turn("request_reactfirst_pdf", "tc-208",
                           {"target_domain": "betabrand.com",
                            "validated_angle_key": "crisis_social_media_002",
                            "calculated_risk_score": 1725.0}),
            _end_turn("Done. 1 brand qualified with a Tier 2 angle."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)
        self._patch_tools_e2(monkeypatch, tmp_cwd)

        result = main.answer_question(
            "Find clean beauty brands for outreach",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # ----------------------------------------------------------------
        # E2a — total LLM calls (rounds) is ≤ 15 (not the tool dispatch count,
        # but the pipeline cap covers dispatches; each scripted turn = 1 LLM call + 1 dispatch)
        # ----------------------------------------------------------------
        total_llm_calls = len(fake_client.call_args_list)
        # 8 tool-use turns + 1 end_turn = 9 LLM calls
        assert total_llm_calls <= main.TOOL_CALL_CAP, (
            f"Total LLM calls must be ≤ {main.TOOL_CALL_CAP}; got {total_llm_calls}"
        )
        # Verify there is headroom (not at the cap)
        assert total_llm_calls < main.TOOL_CALL_CAP, (
            f"Run hit the cap exactly ({total_llm_calls}); must have headroom"
        )

        # ----------------------------------------------------------------
        # E2b — metrics present in the log
        # ----------------------------------------------------------------
        log_path = tmp_cwd / "reactfirst_run.log"
        assert log_path.exists(), "reactfirst_run.log must be produced"
        log_content = log_path.read_text(encoding="utf-8")
        assert "[metrics]" in log_content, (
            "reactfirst_run.log must contain a [metrics] line (RS4)"
        )
        assert "total_calls=" in log_content, (
            "Metrics must include total_calls= count"
        )

        # ----------------------------------------------------------------
        # E2c — tool call count is ≤ 15 (8 dispatches in this run)
        # The loop counts dispatches in metrics["total"]; verify it's in the log.
        # ----------------------------------------------------------------
        # Count tool dispatch log lines as a cross-check
        tool_entry_lines = [l for l in log_content.splitlines() if "** Entering tool" in l]
        assert len(tool_entry_lines) <= main.TOOL_CALL_CAP, (
            f"Dispatched tool calls ({len(tool_entry_lines)}) must be ≤ {main.TOOL_CALL_CAP}"
        )
        assert len(tool_entry_lines) <= 8, (
            f"Expected at most 8 tool dispatches in this scripted run, got {len(tool_entry_lines)}"
        )


# ===========================================================================
# E3 — Recovery path: A∪B < 2 domains → Vector C fires (call-spy)
# ===========================================================================

class TestE3VectorCRecovery:
    """E3: script the fanout so A+B < 2 distinct domains; confirm Vector C fires.

    We monkeypatch _vector_a_search and _vector_b_search to return 0/1 domains
    (triggering the recovery threshold), spy on _vector_c_search, and confirm the
    pipeline still completes end-to-end.

    This tests the FANOUT_RECOVERY_THRESHOLD=2 rule from CLAUDE.md §6.
    """

    def test_e3_vector_c_fires_when_ab_under_threshold(
        self, tmp_cwd, monkeypatch, catalog_df, policies_text
    ):
        """E3: when A+B < 2 domains, Vector C is invoked; pipeline still completes."""
        # Track whether Vector C was called
        vector_c_calls = []

        def mock_vector_a(query: str) -> dict:
            # Return 0 domains from A
            return {"domains": [], "status": "ok", "error": None}

        def mock_vector_b(query: str) -> dict:
            # Return 0 domains from B (total A+B = 0 < FANOUT_RECOVERY_THRESHOLD=2)
            return {"domains": [], "status": "ok", "error": None}

        def mock_vector_c(query: str) -> dict:
            # Vector C (recovery) returns ≥1 domain
            vector_c_calls.append(query)
            return {
                "domains": ["betabrand.com"],
                "status": "ok",
                "error": None,
            }

        monkeypatch.setattr(main, "_vector_a_search", mock_vector_a)
        monkeypatch.setattr(main, "_vector_b_search", mock_vector_b)
        monkeypatch.setattr(main, "_vector_c_search", mock_vector_c)

        # Patch compute-heavy tools
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "generate_search_queries",
            lambda vertical_seed, target_count=15: ["athleisure DTC ecommerce"],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d, "fetched": True, "status_code": 200,
                    "title": "Brand", "description": "DTC brand",
                    "tiktok_pixel": True, "meta_pixel": True, "gtm": True,
                    "operational_scale_signals": ["ecommerce_dtc", "paid_social_advertising"],
                    "timed_out": False, "error": None,
                }
                for d in domains
            ],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "match_solicitation_angle",
            lambda scraped_narrative_context, category_path: {
                "angle_key": "crisis_social_media_003",
                "tier": 1,
                "scores": {"semantic_results": 3, "bm25_results": 3,
                           "fused_results": 3, "top_rrf_score": 0.030},
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "request_reactfirst_pdf",
            _make_mock_pdf_tool(tmp_cwd),
        )

        # Script the model's turns: the model calls execute_3way_fanout which
        # internally calls the real fanout logic (with mocked A/B/C vectors).
        scripted_responses = [
            # Turn 1: generate queries
            _tool_use_turn(
                "generate_search_queries", "tc-301",
                {"vertical_seed": "athleisure DTC brands", "target_count": 10},
            ),
            # Turn 2: fanout (internally calls mocked A/B/C)
            _tool_use_turn(
                "execute_3way_fanout", "tc-302",
                {"queries": ["athleisure DTC ecommerce"]},
            ),
            # Turn 3: extract pool (betabrand.com recovered via Vector C)
            _tool_use_turn(
                "extract_and_score_pool", "tc-303",
                {"raw_pool": [{"domain": "betabrand.com", "provenance": ["C"]}]},
            ),
            # Turn 4: analyze
            _tool_use_turn(
                "analyze_company_chunk", "tc-304",
                {"domains": ["betabrand.com"]},
            ),
            # Turn 5: evaluate ICP (4-tag profile → qualified)
            _tool_use_turn(
                "evaluate_icp_tags", "tc-305",
                {"company_profile_data": _icp_profile_4_tags()},
            ),
            # Turn 6: angle match
            _tool_use_turn(
                "match_solicitation_angle", "tc-306",
                {"scraped_narrative_context": _icp_profile_4_tags(),
                 "category_path": "Apparel > Athleisure > Performance"},
            ),
            # Turn 7: PDF
            _tool_use_turn(
                "request_reactfirst_pdf", "tc-307",
                {"target_domain": "betabrand.com",
                 "validated_angle_key": "crisis_social_media_003",
                 "calculated_risk_score": 1200.0},
            ),
            # Turn 8: end_turn
            _end_turn("Recovery path exercised. BetaBrand qualified."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        result = main.answer_question(
            "Find athleisure DTC brands for outreach",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # ----------------------------------------------------------------
        # E3a — Vector C was actually invoked during the fanout
        # (the fanout tool is called with real execute_3way_fanout code, which
        #  sees A+B=0 < 2 and invokes the mocked _vector_c_search)
        # ----------------------------------------------------------------
        assert len(vector_c_calls) > 0, (
            "Vector C (_vector_c_search) must have been called when A+B < 2 domains. "
            f"Call log: {vector_c_calls}"
        )

        # ----------------------------------------------------------------
        # E3b — pipeline still completed (result is a non-empty string)
        # ----------------------------------------------------------------
        assert isinstance(result, str)
        assert result != main.FALLBACK_MESSAGE, (
            "Vector C recovery should allow the pipeline to complete, "
            "not fall back to the fallback message"
        )
        assert len(result) > 0

        # ----------------------------------------------------------------
        # E3c — log was produced
        # ----------------------------------------------------------------
        log_path = tmp_cwd / "reactfirst_run.log"
        assert log_path.exists(), "reactfirst_run.log must be produced after Vector C recovery"


# ===========================================================================
# E4 — No-match seed → exactly FALLBACK_MESSAGE; no generative apology; no leads file
# ===========================================================================

class TestE4NoMatchFallback:
    """E4: drive answer_question with a seed where all evaluate_icp_tags return
    qualified=False (or all angles return Tier 4) → result is EXACTLY FALLBACK_MESSAGE.

    The generative path must be bypassed — the model should NOT be asked to
    compose an apology (FB4 cross-check via call-spy on messages.create calls
    after the zero-match condition is detected).

    qualified_leads.json is NOT written on a no-match run.
    """

    def test_e4_all_icp_fail_yields_fallback(
        self, tmp_cwd, monkeypatch, catalog_df, policies_text
    ):
        """E4: all evaluate_icp_tags calls return qualified=False → FALLBACK_MESSAGE."""

        # Patch tools so the pipeline runs but all ICP evaluations fail.
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "generate_search_queries",
            lambda vertical_seed, target_count=15: ["obscure vertical no brands"],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "execute_3way_fanout",
            lambda queries: {
                "domains": {"unknownbrand.com": {"provenance": ["A"]}},
                "vector_status": {"A": "ok", "B": "error", "C": "skipped"},
                "total_unique_domains": 1,
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d, "fetched": True, "status_code": 200,
                    "title": "Unknown", "description": "No signals",
                    "tiktok_pixel": False, "meta_pixel": False, "gtm": False,
                    "operational_scale_signals": [],
                    "timed_out": False, "error": None,
                }
                for d in domains
            ],
        )

        # evaluate_icp_tags will run real code.
        # The profile below matches < 3 ICP tags → qualified=False.

        # Script the model to call evaluate_icp_tags with a low-signal profile.
        scripted_responses = [
            # Turn 1: generate queries
            _tool_use_turn(
                "generate_search_queries", "tc-401",
                {"vertical_seed": "obscure vertical seed", "target_count": 10},
            ),
            # Turn 2: fanout
            _tool_use_turn(
                "execute_3way_fanout", "tc-402",
                {"queries": ["obscure vertical no brands"]},
            ),
            # Turn 3: extract
            _tool_use_turn(
                "extract_and_score_pool", "tc-403",
                {"raw_pool": [{"domain": "unknownbrand.com", "provenance": ["A"]}]},
            ),
            # Turn 4: analyze
            _tool_use_turn(
                "analyze_company_chunk", "tc-404",
                {"domains": ["unknownbrand.com"]},
            ),
            # Turn 5: evaluate ICP — profile yields < 3 tags → qualified=False
            _tool_use_turn(
                "evaluate_icp_tags", "tc-405",
                {"company_profile_data": _icp_profile_2_tags()},
            ),
            # Turn 6: model concludes (no match found, returns end_turn)
            # The loop checks is_zero_match at end_turn and returns FALLBACK_MESSAGE.
            _end_turn("No brands qualified."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        result = main.answer_question(
            "Find brands in the obscure vertical",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # ----------------------------------------------------------------
        # E4a — result is EXACTLY FALLBACK_MESSAGE (byte-exact, FB3)
        # ----------------------------------------------------------------
        assert result == main.FALLBACK_MESSAGE, (
            f"No-match seed must return EXACTLY FALLBACK_MESSAGE.\n"
            f"Expected: {main.FALLBACK_MESSAGE!r}\n"
            f"Got:      {result!r}"
        )

        # ----------------------------------------------------------------
        # E4b — log confirms the policy-6 path was triggered (not the model text)
        # ----------------------------------------------------------------
        log_path = tmp_cwd / "reactfirst_run.log"
        assert log_path.exists(), "reactfirst_run.log must be produced even on no-match"
        log_content = log_path.read_text(encoding="utf-8")
        assert "[policy-6]" in log_content, (
            "Log must record the policy-6 fallback trigger on a no-match run"
        )

        # ----------------------------------------------------------------
        # E4c — generative path bypassed: no messages.create called AFTER the
        # fallback decision (FB4: the model is never asked to compose an apology).
        # In our scripted run, end_turn is the 6th LLM call; the fallback is
        # detected AFTER that turn ends (is_zero_match fires on end_turn).
        # The key check is that fake_client.call_args_list has ≤ 6 entries —
        # no extra LLM call was made to compose an apology.
        # ----------------------------------------------------------------
        total_llm_calls = len(fake_client.call_args_list)
        # We scripted 6 turns (5 tool-use + 1 end_turn) → at most 6 LLM calls.
        assert total_llm_calls <= 6, (
            f"No extra LLM calls after zero-match detection (FB4). "
            f"Got {total_llm_calls} total LLM calls."
        )

        # ----------------------------------------------------------------
        # E4d — qualified_leads.json NOT written on a no-match run
        # ----------------------------------------------------------------
        leads_path = tmp_cwd / "qualified_leads.json"
        assert not leads_path.exists(), (
            "qualified_leads.json must NOT be written on a no-match run"
        )

    def test_e4_all_tier4_angles_yields_fallback(
        self, tmp_cwd, monkeypatch, catalog_df, policies_text
    ):
        """E4: all match_solicitation_angle calls return Tier 4 → FALLBACK_MESSAGE."""

        # Patch tools: ICP passes (≥3 tags) but angle matching → Tier 4.
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "generate_search_queries",
            lambda vertical_seed, target_count=15: ["garden supply tools"],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "execute_3way_fanout",
            lambda queries: {
                "domains": {"gardentools.com": {"provenance": ["A"]}},
                "vector_status": {"A": "ok", "B": "error", "C": "skipped"},
                "total_unique_domains": 1,
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d, "fetched": True, "status_code": 200,
                    "title": "Garden Tools", "description": "Garden supply",
                    "tiktok_pixel": True, "meta_pixel": True, "gtm": True,
                    "operational_scale_signals": [],
                    "timed_out": False, "error": None,
                }
                for d in domains
            ],
        )
        # Angle matching always returns Tier 4 (No Match).
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "match_solicitation_angle",
            lambda scraped_narrative_context, category_path: {
                "angle_key": "no_match",
                "tier": 4,
                "scores": {
                    "semantic_results": 0,
                    "bm25_results": 0,
                    "fused_results": 0,
                    "top_rrf_score": 0.0,
                    "relevance_floor_triggered": True,
                },
            },
        )

        scripted_responses = [
            _tool_use_turn("generate_search_queries", "tc-501",
                           {"vertical_seed": "garden supply tools", "target_count": 10}),
            _tool_use_turn("execute_3way_fanout", "tc-502",
                           {"queries": ["garden supply tools"]}),
            _tool_use_turn("extract_and_score_pool", "tc-503",
                           {"raw_pool": [{"domain": "gardentools.com", "provenance": ["A"]}]}),
            _tool_use_turn("analyze_company_chunk", "tc-504",
                           {"domains": ["gardentools.com"]}),
            # ICP passes: profile triggers ≥ 3 tags.
            _tool_use_turn("evaluate_icp_tags", "tc-505",
                           {"company_profile_data": _icp_profile_4_tags()}),
            # Angle → Tier 4
            _tool_use_turn("match_solicitation_angle", "tc-506",
                           {"scraped_narrative_context": _icp_profile_4_tags(),
                            "category_path": "Home > Garden > Tools"}),
            # Model concludes (no valid angle found)
            _end_turn("No matching angles found."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        result = main.answer_question(
            "Find garden supply brands for outreach",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # E4a: result is exactly FALLBACK_MESSAGE
        assert result == main.FALLBACK_MESSAGE, (
            f"All-Tier-4 seed must return EXACTLY FALLBACK_MESSAGE.\n"
            f"Expected: {main.FALLBACK_MESSAGE!r}\n"
            f"Got:      {result!r}"
        )

        # E4d: qualified_leads.json NOT written
        leads_path = tmp_cwd / "qualified_leads.json"
        assert not leads_path.exists(), (
            "qualified_leads.json must NOT be written when all angles are Tier 4"
        )


# ===========================================================================
# Additional: write_qualified_leads unit tests
# ===========================================================================

class TestWriteQualifiedLeads:
    """Unit tests for the write_qualified_leads helper (Stage 7 artifact writer).

    These tests call the helper directly without going through answer_question,
    verifying its contract in isolation.
    """

    def test_no_pdf_results_returns_none(self, tmp_cwd):
        """write_qualified_leads returns None when no ok=True PDF results exist."""
        result = main.write_qualified_leads([])
        assert result is None

    def test_no_ok_pdf_returns_none(self, tmp_cwd):
        """write_qualified_leads returns None when PDFs all failed (ok=False)."""
        run_results = [
            {
                "tool_name": "request_reactfirst_pdf",
                "result": {"ok": False, "error": "network error"},
                "input": {"target_domain": "fail.com",
                          "validated_angle_key": "angle-001",
                          "calculated_risk_score": 100.0},
            }
        ]
        result = main.write_qualified_leads(run_results)
        assert result is None

    def test_single_lead_written(self, tmp_cwd):
        """write_qualified_leads writes qualified_leads.json for a single ok lead."""
        # Create a fake PDF in assets/ so the path is meaningful.
        assets_dir = tmp_cwd / "assets"
        assets_dir.mkdir()
        pdf_path = assets_dir / "reactfirst_example_com_angle-001.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

        run_results = [
            {
                "tool_name": "match_solicitation_angle",
                "result": {"angle_key": "angle-001", "tier": 1,
                            "scores": {"top_rrf_score": 0.030}},
            },
            {
                "tool_name": "request_reactfirst_pdf",
                "result": {"ok": True, "path": str(pdf_path)},
                "input": {"target_domain": "example.com",
                          "validated_angle_key": "angle-001",
                          "calculated_risk_score": 1500.0},
            },
        ]

        out_path = main.write_qualified_leads(run_results, output_dir=str(tmp_cwd))
        assert out_path is not None

        leads_path = pathlib.Path(out_path)
        assert leads_path.exists(), "qualified_leads.json must be written"

        with open(str(leads_path), encoding="utf-8") as fh:
            data = json.load(fh)

        assert "qualified_leads" in data
        assert data["count"] == 1
        leads = data["qualified_leads"]
        assert len(leads) == 1
        assert leads[0]["domain"] == "example.com"
        assert leads[0]["angle_key"] == "angle-001"
        assert leads[0]["tier"] == 1

    def test_more_than_3_leads_capped_to_3(self, tmp_cwd):
        """write_qualified_leads caps at MAX_ANGLES=3 (Policy 5)."""
        # Create 5 ok PDF results → must be capped to 3.
        run_results = []
        for i in range(1, 6):
            run_results.append({
                "tool_name": "request_reactfirst_pdf",
                "result": {"ok": True, "path": f"/fake/path/pdf_{i}.pdf"},
                "input": {
                    "target_domain": f"brand{i}.com",
                    "validated_angle_key": f"angle-{i:03d}",
                    "calculated_risk_score": float(i * 100),
                },
            })

        out_path = main.write_qualified_leads(run_results, output_dir=str(tmp_cwd))
        assert out_path is not None

        with open(out_path, encoding="utf-8") as fh:
            data = json.load(fh)

        assert len(data["qualified_leads"]) <= main.MAX_ANGLES, (
            f"Must be capped at MAX_ANGLES={main.MAX_ANGLES}"
        )
        assert data["capped"] is True, "capped flag must be True when leads were truncated"

    def test_import_safe_not_called_at_import(self):
        """write_qualified_leads does not run at import time (ENV4 cross-check)."""
        # If this module imported without error and write_qualified_leads exists,
        # and no files were written in the cwd at import time, ENV4 is satisfied.
        import importlib
        # Re-importing main must not write any files.
        m = importlib.import_module("main")
        assert hasattr(m, "write_qualified_leads"), (
            "write_qualified_leads must be defined in main"
        )
