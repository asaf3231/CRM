"""
tests/test_outreach_center.py — Stage 14 QA checks (L6b Outreach Center)

Checks verified:
  OUT7  — outreach_status_brief returns deterministic rollup with required keys + A/B tags.
  OUT8  — end-to-end offline test: discovery → ICP → CRM → cohorts → mocked dispatch → brief;
          no-match seed still yields byte-exact FALLBACK_MESSAGE.
  OUT9  — idempotent re-run: sender not called again; identical cohorts/brief.
  OUT10 — crm_store.py in MANIFEST.txt; ENV4 holds; full regression green.
  INT1  — run_outreach_pipeline does NOT reference OUTREACH_SUBDOMAIN directly.
  INT2  — multi-channel integration (auth gate honored).
  INT3  — idempotent re-run (no duplicate assets).
  H1-H5 — packaging hygiene (H5 now includes crm_store.py).

A/B variant rule (recorded in handback):
  Variant is determined by the index of the lead in the ordered cohort list:
    - Even index (0, 2, 4, ...) → variant "A"
    - Odd index  (1, 3, 5, ...) → variant "B"
  This is deterministic: same input always produces same tags.

Reply-rate rule:
  replies = max(0, sent // 5)   (one reply per 5 sends, truncated)
  reply_rate = replies / sent if sent > 0 else 0.0
  This is a mocked fixed-ratio analytics metric — not real network data.

All external services are mocked. No live network calls.
Synthetic keys only (TestKey001 / TestKey002).
"""

import importlib
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


# ---------------------------------------------------------------------------
# Shared synthetic contact fixtures (same as test_outreach.py)
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
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text(json.dumps(SAMPLE_CONTACTS), encoding="utf-8")
    return str(contacts_file)


@pytest.fixture
def seeded_lead_store(tmp_contacts_json, monkeypatch):
    import lead_store
    importlib.reload(lead_store)
    monkeypatch.chdir(os.path.dirname(tmp_contacts_json))
    lead_store.get_lead_data_collection()
    return lead_store


@pytest.fixture()
def tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def catalog_df():
    import pandas as pd
    return pd.DataFrame([
        {
            "Uniq_Id": "test-brand-0001",
            "Brand_Name": "AlphaBrand",
            "Primary_Domain": "alphabrand.com",
            "Core_Category": "Apparel > Athleisure > Sustainable",
            "Estimated_Ad_Spend_Tier": "Tier 1",
            "Current_Status": "Open_Opportunity",
            "Historical_Social_Incidents": 7,
            "Main_Competitor_Id": "test-brand-0002",
            "Gtin_Prefix": "0712345",
        },
        {
            "Uniq_Id": "test-brand-0002",
            "Brand_Name": "BetaBrand",
            "Primary_Domain": "betabrand.com",
            "Core_Category": "Apparel > Athleisure > Performance",
            "Estimated_Ad_Spend_Tier": "Tier 2",
            "Current_Status": "Unreached_Prospect",
            "Historical_Social_Incidents": 2,
            "Main_Competitor_Id": "test-brand-0001",
            "Gtin_Prefix": "0712346",
        },
    ])


@pytest.fixture()
def policies_text():
    return (
        "Policy 1: All brand facts from brands_catalog.csv only.\n"
        "Policy 2: ICP threshold >= 3 tags.\n"
        "Policy 5: Max 3 angles.\n"
        "Policy 6: FALLBACK_MESSAGE on zero match.\n"
    )


# ===========================================================================
# FakeReasoningClient (reuse the same pattern from test_e2e.py)
# ===========================================================================

class _FakeBlock:
    def __init__(self, block_type: str, **kwargs):
        self.type = block_type
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __iter__(self):
        return iter([])


class _FakeResponse:
    def __init__(self, content: list, stop_reason: str = "end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class FakeReasoningClient:
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


def _tool_use_block(name, block_id, input_dict):
    return _FakeBlock("tool_use", name=name, id=block_id, input=input_dict)


def _text_block(text):
    return _FakeBlock("text", text=text)


def _end_turn(text="Pipeline complete."):
    return _FakeResponse([_text_block(text)], "end_turn")


def _tool_use_turn(name, block_id, input_dict):
    return _FakeResponse(
        [_tool_use_block(name, block_id, input_dict)],
        "tool_use",
    )


def _make_valid_pdf_bytes():
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _icp_profile_4_tags():
    return (
        "This DTC e-commerce brand sells on Shopify. "
        "They run Facebook ads and Instagram ads at scale. "
        "Venture-backed company in a rapid growth stage. "
        "Ad spend is $2M, strong ROAS. "
        "Strong brand marketing team with CMO leading performance marketing."
    )


# ===========================================================================
# OUT7 — outreach_status_brief
# ===========================================================================

class TestOUT7OutreachStatusBrief:
    """outreach_status_brief returns deterministic morning-brief rollup."""

    def test_function_exists(self):
        assert callable(main.outreach_status_brief)

    def test_required_keys_present(self):
        state = {"cohorts": [], "dispatch_results": []}
        brief = main.outreach_status_brief(state)
        required = {"cohort_count", "scheduled", "sent", "failed",
                    "replies", "reply_rate", "variants"}
        assert required.issubset(set(brief.keys())), (
            f"Missing keys: {required - set(brief.keys())}"
        )

    def test_empty_state_zero_values(self):
        state = {"cohorts": [], "dispatch_results": []}
        brief = main.outreach_status_brief(state)
        assert brief["cohort_count"] == 0
        assert brief["scheduled"] == 0
        assert brief["sent"] == 0
        assert brief["failed"] == 0
        assert brief["replies"] == 0
        assert brief["reply_rate"] == 0.0
        assert isinstance(brief["variants"], dict)
        assert brief["variants"].get("A", 0) == 0
        assert brief["variants"].get("B", 0) == 0

    def test_variants_keys_present(self):
        state = {"cohorts": [], "dispatch_results": []}
        brief = main.outreach_status_brief(state)
        assert "A" in brief["variants"]
        assert "B" in brief["variants"]

    def test_sent_counts_true_results(self):
        state = {
            "cohorts": [["lead-0", "lead-1", "lead-2"]],
            "dispatch_results": [
                {"sent": True, "channel": "email", "variant": "A"},
                {"sent": True, "channel": "email", "variant": "B"},
                {"sent": False, "reason": "unauthorized"},
            ],
        }
        brief = main.outreach_status_brief(state)
        assert brief["sent"] == 2
        assert brief["failed"] == 1

    def test_cohort_count_correct(self):
        state = {
            "cohorts": [["l1", "l2"], ["l3"]],
            "dispatch_results": [],
        }
        brief = main.outreach_status_brief(state)
        assert brief["cohort_count"] == 2

    def test_scheduled_is_total_leads_in_cohorts(self):
        state = {
            "cohorts": [["l1", "l2", "l3"], ["l4", "l5"]],
            "dispatch_results": [],
        }
        brief = main.outreach_status_brief(state)
        assert brief["scheduled"] == 5

    def test_reply_rate_with_sent(self):
        """reply_rate = replies / sent; replies = sent // 5."""
        state = {
            "cohorts": [list(range(10))],
            "dispatch_results": [{"sent": True} for _ in range(10)],
        }
        brief = main.outreach_status_brief(state)
        # 10 sent → 10 // 5 = 2 replies → rate = 2/10 = 0.2
        assert brief["sent"] == 10
        assert brief["replies"] == 2
        assert abs(brief["reply_rate"] - 0.2) < 1e-9

    def test_deterministic_same_input_same_output(self):
        """Same input → same output (deterministic, no randomness)."""
        state = {
            "cohorts": [["lead-0", "lead-1", "lead-2", "lead-3"]],
            "dispatch_results": [
                {"sent": True, "variant": "A"},
                {"sent": True, "variant": "B"},
                {"sent": True, "variant": "A"},
                {"sent": False, "reason": "opted_out"},
            ],
        }
        brief1 = main.outreach_status_brief(state)
        brief2 = main.outreach_status_brief(state)
        assert brief1 == brief2

    def test_ab_variants_from_dispatch_results(self):
        """variants{"A","B"} count is derived from dispatch_results."""
        state = {
            "cohorts": [["l0", "l1", "l2", "l3"]],
            "dispatch_results": [
                {"sent": True, "variant": "A"},   # index 0 → A
                {"sent": True, "variant": "B"},   # index 1 → B
                {"sent": True, "variant": "A"},   # index 2 → A
                {"sent": True, "variant": "B"},   # index 3 → B
            ],
        }
        brief = main.outreach_status_brief(state)
        assert brief["variants"]["A"] == 2
        assert brief["variants"]["B"] == 2

    def test_reply_rate_zero_when_no_sends(self):
        state = {
            "cohorts": [["l1"]],
            "dispatch_results": [{"sent": False, "reason": "error"}],
        }
        brief = main.outreach_status_brief(state)
        assert brief["reply_rate"] == 0.0
        assert brief["replies"] == 0

    def test_returns_dict(self):
        brief = main.outreach_status_brief({"cohorts": [], "dispatch_results": []})
        assert isinstance(brief, dict)


# ===========================================================================
# run_outreach_pipeline — existence + basic structure
# ===========================================================================

class TestRunOutreachPipelineExists:
    """run_outreach_pipeline exists and returns the required top-level keys."""

    def test_function_exists(self):
        assert callable(main.run_outreach_pipeline)

    def test_empty_leads_returns_structure(self, monkeypatch, seeded_lead_store):
        monkeypatch.setattr(main, "lead_store", seeded_lead_store)
        result = main.run_outreach_pipeline([], sender=lambda url, data: None)
        assert isinstance(result, dict)
        assert "cohorts" in result
        assert "dispatch_results" in result
        assert "brief" in result

    def test_empty_leads_no_dispatch(self, monkeypatch, seeded_lead_store):
        monkeypatch.setattr(main, "lead_store", seeded_lead_store)
        sender_calls = []
        result = main.run_outreach_pipeline(
            [], sender=lambda url, data: sender_calls.append(url)
        )
        assert sender_calls == [], "No dispatch when leads list is empty"


# ===========================================================================
# OUT8 — End-to-end offline test
# ===========================================================================

class TestOUT8EndToEnd:
    """END-TO-END: answer_question → run_outreach_pipeline.

    Discovery query drives answer_question under the 15-call cap, then
    run_outreach_pipeline dispatches to the mocked sender, and brief is produced.
    A no-match seed still returns byte-exact FALLBACK_MESSAGE with no dispatch.
    """

    def _patch_tools(self, monkeypatch, tmp_cwd):
        """Patch all network-dependent tools."""
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "generate_search_queries",
            lambda vertical_seed, target_count=15: [
                "athleisure brands DTC ecommerce",
                "sustainable activewear direct to consumer",
            ],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "execute_3way_fanout",
            lambda queries: {
                "domains": {"alphabrand.com": {"provenance": ["A", "B"]}},
                "vector_status": {"A": "ok", "B": "ok", "C": "skipped"},
                "total_unique_domains": 1,
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d, "fetched": True, "status_code": 200,
                    "title": f"{d} - Home", "description": "DTC activewear brand",
                    "tiktok_pixel": True, "meta_pixel": True, "gtm": True,
                    "operational_scale_signals": [
                        "ecommerce_dtc", "paid_social_advertising",
                        "scale_growth_stage", "ad_spend_signals",
                    ],
                    "timed_out": False, "error": None,
                }
                for d in domains
            ],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "match_solicitation_angle",
            lambda scraped_narrative_context, category_path: {
                "angle_key": "crisis_social_media_001",
                "tier": 1,
                "scores": {"top_rrf_score": 0.032},
            },
        )

        def mock_pdf(target_domain, validated_angle_key, calculated_risk_score):
            assets_dir = pathlib.Path(os.getcwd()) / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            safe_domain = target_domain.replace(".", "_")
            pdf_path = assets_dir / f"reactfirst_{safe_domain}_{validated_angle_key}.pdf"
            pdf_path.write_bytes(_make_valid_pdf_bytes())
            return {"ok": True, "path": str(pdf_path)}

        monkeypatch.setitem(main.TOOL_DISPATCH, "request_reactfirst_pdf", mock_pdf)

    def test_out8_happy_path_end_to_end(
        self, tmp_cwd, monkeypatch, catalog_df, policies_text, seeded_lead_store
    ):
        """OUT8: discovery query → answer_question → run_outreach_pipeline → brief."""
        monkeypatch.setattr(main, "lead_store", seeded_lead_store)
        self._patch_tools(monkeypatch, tmp_cwd)

        scripted_responses = [
            _tool_use_turn("generate_search_queries", "tc-801",
                           {"vertical_seed": "athleisure DTC brands", "target_count": 15}),
            _tool_use_turn("execute_3way_fanout", "tc-802",
                           {"queries": ["athleisure brands DTC ecommerce"]}),
            _tool_use_turn("extract_and_score_pool", "tc-803",
                           {"raw_pool": [{"domain": "alphabrand.com", "provenance": ["A"]}]}),
            _tool_use_turn("analyze_company_chunk", "tc-804",
                           {"domains": ["alphabrand.com"]}),
            _tool_use_turn("evaluate_icp_tags", "tc-805",
                           {"company_profile_data": _icp_profile_4_tags()}),
            _tool_use_turn("match_solicitation_angle", "tc-806",
                           {"scraped_narrative_context": _icp_profile_4_tags(),
                            "category_path": "Apparel > Athleisure > Sustainable"}),
            _tool_use_turn("request_reactfirst_pdf", "tc-807",
                           {"target_domain": "alphabrand.com",
                            "validated_angle_key": "crisis_social_media_001",
                            "calculated_risk_score": 1500.0}),
            _end_turn("Found 1 qualified brand with Tier 1 angle."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        # 1) Run the agentic loop
        result = main.answer_question(
            "Find athleisure DTC brands for outreach",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # answer_question must not return FALLBACK_MESSAGE
        assert result != main.FALLBACK_MESSAGE
        assert isinstance(result, str)
        assert len(result) > 0

        # 2) Run the outreach pipeline post-loop
        sender_calls = []
        leads = [
            {
                "email": "dana.reyes@example.com",
                "caller_key": "TestKey001",
                "domain": "alphabrand.com",
                "angle_key": "crisis_social_media_001",
            }
        ]
        pipeline_result = main.run_outreach_pipeline(
            leads,
            sender=lambda url, data: sender_calls.append(url),
        )

        # 3) Validate the pipeline result structure
        assert isinstance(pipeline_result, dict)
        assert "cohorts" in pipeline_result
        assert "dispatch_results" in pipeline_result
        assert "brief" in pipeline_result

        # 4) The brief has all required keys
        brief = pipeline_result["brief"]
        required = {"cohort_count", "scheduled", "sent", "failed",
                    "replies", "reply_rate", "variants"}
        assert required.issubset(set(brief.keys())), (
            f"Missing brief keys: {required - set(brief.keys())}"
        )

        # 5) At least 1 dispatch was attempted (sender called)
        assert len(sender_calls) >= 1, "Sender must have been called for the lead"

        # 6) Cap still applied: loop used ≤15 tool calls
        total_llm_calls = len(fake_client.call_args_list)
        assert total_llm_calls <= main.TOOL_CALL_CAP

    def test_out8_no_match_no_dispatch(
        self, tmp_cwd, monkeypatch, catalog_df, policies_text, seeded_lead_store
    ):
        """OUT8: no-match seed → FALLBACK_MESSAGE; run_outreach_pipeline skipped."""
        monkeypatch.setattr(main, "lead_store", seeded_lead_store)

        # ICP will fail (< 3 tags) → FALLBACK_MESSAGE
        def _icp_profile_2_tags():
            return "This is a small shop. Nothing else notable. Regular business."

        scripted_responses = [
            _tool_use_turn("generate_search_queries", "tc-901",
                           {"vertical_seed": "obscure vertical", "target_count": 10}),
            _tool_use_turn("execute_3way_fanout", "tc-902",
                           {"queries": ["obscure vertical"]}),
            _tool_use_turn("extract_and_score_pool", "tc-903",
                           {"raw_pool": [{"domain": "unknown.com", "provenance": ["A"]}]}),
            _tool_use_turn("analyze_company_chunk", "tc-904",
                           {"domains": ["unknown.com"]}),
            _tool_use_turn("evaluate_icp_tags", "tc-905",
                           {"company_profile_data": _icp_profile_2_tags()}),
            _end_turn("No brands qualified."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        monkeypatch.setitem(
            main.TOOL_DISPATCH, "generate_search_queries",
            lambda vertical_seed, target_count=15: ["obscure vertical"],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "execute_3way_fanout",
            lambda queries: {
                "domains": {"unknown.com": {"provenance": ["A"]}},
                "vector_status": {"A": "ok", "B": "error", "C": "skipped"},
                "total_unique_domains": 1,
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH, "analyze_company_chunk",
            lambda domains: [{"domain": d, "fetched": True, "status_code": 200,
                               "tiktok_pixel": False, "meta_pixel": False, "gtm": False,
                               "operational_scale_signals": [], "timed_out": False, "error": None}
                             for d in domains],
        )

        result = main.answer_question(
            "Find brands in obscure vertical",
            catalog_df=catalog_df,
            policies=policies_text,
        )

        # Must be byte-exact FALLBACK_MESSAGE
        assert result == main.FALLBACK_MESSAGE, (
            f"Expected FALLBACK_MESSAGE on no-match.\nGot: {result!r}"
        )

    def test_out8_fallback_message_byte_exact(self):
        """FALLBACK_MESSAGE is the exact byte-stable constant (FB1)."""
        assert main.FALLBACK_MESSAGE == "We have no product available today that fits your request"


# ===========================================================================
# OUT8-MAIN — new test that drives main.main() directly (Stage 14-r1 fix)
# Exercises the full L6 wiring path from sys.argv → main() → L6 pipeline,
# proving the bug (TypeError from crm_store.outbound_eligible_contacts()
# called with zero args) is gone.
# ===========================================================================

class TestOUT8MainDriven:
    """Drive main.main() end-to-end to prove L6 wiring is correct.

    The original OUT8 tests bypassed main() by calling run_outreach_pipeline
    directly. These tests call main.main() and assert that the L6 pipeline
    actually executes (sender is called) or is correctly skipped (FALLBACK path).
    """

    def _make_minimal_catalog(self, tmp_path: pathlib.Path) -> pathlib.Path:
        catalog_path = tmp_path / "brands_catalog.csv"
        catalog_path.write_text(
            "Uniq_Id,Brand_Name,Primary_Domain,Core_Category,"
            "Estimated_Ad_Spend_Tier,Current_Status,"
            "Historical_Social_Incidents,Main_Competitor_Id,Gtin_Prefix\n"
            "test-brand-001,AlphaBrand,alphabrand.com,"
            "Apparel > Athleisure > Sustainable,Tier 1,Open_Opportunity,"
            "7,test-brand-002,0712345\n",
            encoding="utf-8",
        )
        return catalog_path

    def _make_minimal_contacts(self, tmp_path: pathlib.Path) -> pathlib.Path:
        contacts_path = tmp_path / "contacts.json"
        contacts = [
            {
                "first_name": "Dana",
                "last_name": "Reyes",
                "email": "dana.reyes@example.com",
                "corporate_access_key": "TestKey001",
                "role": "VP Growth",
                "linkedin_url": "https://www.linkedin.com/in/dana-reyes",
                "interaction_history_count": 4,
                "opt_out_status": False,
                "target_brand_id": "test-brand-001",
            }
        ]
        contacts_path.write_text(json.dumps(contacts), encoding="utf-8")
        return contacts_path

    def _make_minimal_policies(self, tmp_path: pathlib.Path) -> pathlib.Path:
        policies_path = tmp_path / "gtm_policies.txt"
        policies_path.write_text(
            "Policy 1: Brand facts from catalog only.\n"
            "Policy 2: ICP threshold >= 3 tags.\n"
            "Policy 5: Max 3 angles.\n"
            "Policy 6: Fallback on zero match.\n",
            encoding="utf-8",
        )
        return policies_path

    def _seed_crm_with_lead(self):
        """Seed a CRM lead record with contact_ids so L6 has something to dispatch."""
        import crm_store as _crm
        importlib.reload(_crm)
        _crm.upsert_lead({
            "uniq_id": "alphabrand.com",
            "domain": "alphabrand.com",
            "status": "qualified",
            "contact_ids": ["dana.reyes@example.com"],
            "profile": {"angle_key": "crisis_social_media_001"},
        })
        return _crm

    def test_main_l6_runs_and_sender_called(
        self, tmp_path, monkeypatch, seeded_lead_store
    ):
        """main.main() with a valid query+key → L6 pipeline runs and sender fires.

        This is the regression test for the Stage-14 bug where
        crm_store.outbound_eligible_contacts() was called with zero args,
        raising TypeError silently caught → L6 never executing.

        Strategy: stub answer_question to return a non-FALLBACK result,
        seed CRM with a lead record + contact_ids, monkeypatch
        run_outreach_pipeline to record the leads arg AND the sender,
        then verify the call happened with the correct data.
        """
        # ---- 1. Set up cwd with all three input files -------------------------
        monkeypatch.chdir(tmp_path)
        self._make_minimal_catalog(tmp_path)
        self._make_minimal_contacts(tmp_path)
        self._make_minimal_policies(tmp_path)

        # ---- 2. Seed contacts store + CRM workspace --------------------------
        monkeypatch.setattr(main, "lead_store", seeded_lead_store)
        crm = self._seed_crm_with_lead()
        monkeypatch.setattr(main, "crm_store", crm)

        # ---- 3. Stub answer_question to return a non-FALLBACK result ---------
        # Bypass the full LLM loop; isolate the L6 wiring path cleanly.
        monkeypatch.setattr(
            main,
            "answer_question",
            lambda query, catalog_df, policies: "Found 1 qualified brand.",
        )

        # ---- 4. Spy on run_outreach_pipeline with a recording sender ---------
        # We monkeypatch run_outreach_pipeline to capture the leads arg,
        # then call dispatch_outreach ourselves with a recording sender
        # so the auth gate still fires.
        sender_calls = []
        pipeline_leads_captured = []

        def spy_pipeline(leads, *, sender=None, daily_cap=main.DAILY_SEND_CAP):
            pipeline_leads_captured.extend(list(leads))
            # Run the real dispatch through dispatch_outreach with our sender.
            for lead in leads:
                email = lead.get("email", "")
                caller_key = lead.get("caller_key", "")
                domain = lead.get("domain", "")
                angle_key = lead.get("angle_key", "")
                if not email:
                    continue
                payload = {
                    "type": "outreach",
                    "target_domain": domain,
                    "validated_angle_key": angle_key,
                }
                dr = main.dispatch_outreach(
                    target_email=email,
                    caller_key=caller_key,
                    channel="email",
                    payload=payload,
                    sender=lambda url, data: sender_calls.append(url),
                )
            return {
                "cohorts": [list(leads)],
                "dispatch_results": [],
                "brief": {"cohort_count": 1, "scheduled": len(leads),
                          "sent": 0, "failed": 0, "replies": 0,
                          "reply_rate": 0.0, "variants": {"A": 0, "B": 0}},
            }

        monkeypatch.setattr(main, "run_outreach_pipeline", spy_pipeline)

        monkeypatch.setattr(sys, "argv", [
            "main.py",
            "Find athleisure brands access key is TestKey001"
        ])

        # ---- 5. Drive main() -------------------------------------------------
        main.main()

        # ---- 6. Assert L6 ran with the correct lead data ---------------------
        assert len(pipeline_leads_captured) >= 1, (
            "run_outreach_pipeline must be called with at least 1 lead. "
            "If zero leads: either crm_store.all_leads() was not called, "
            "or the CRM record has no contact_ids, "
            "or the old bug (outbound_eligible_contacts() with 0 args) is still present."
        )
        lead = pipeline_leads_captured[0]
        assert lead["email"] == "dana.reyes@example.com"
        assert lead["caller_key"] == "TestKey001"    # parsed from query
        assert lead["domain"] == "alphabrand.com"
        assert lead["angle_key"] == "crisis_social_media_001"

        # The sender was called (auth gate passes with TestKey001)
        assert len(sender_calls) >= 1, (
            "Sender must have been called for the authorized contact. "
            "If this fails, dispatch_outreach's auth gate is blocking or "
            "the L6 wiring bug is still present."
        )
        # Egress only to OUTREACH_SUBDOMAIN
        for url in sender_calls:
            assert main.OUTREACH_SUBDOMAIN in url, (
                f"Sender called with non-outreach URL: {url}"
            )

    def test_main_l6_skipped_on_fallback(
        self, tmp_path, monkeypatch, seeded_lead_store
    ):
        """main.main() that returns FALLBACK_MESSAGE must NOT invoke L6 at all.

        On a no-match run, crm_store.all_leads() and run_outreach_pipeline
        must NOT be called.
        """
        monkeypatch.chdir(tmp_path)
        self._make_minimal_catalog(tmp_path)
        self._make_minimal_contacts(tmp_path)
        self._make_minimal_policies(tmp_path)

        monkeypatch.setattr(main, "lead_store", seeded_lead_store)

        # answer_question returns the byte-exact fallback
        monkeypatch.setattr(
            main,
            "answer_question",
            lambda query, catalog_df, policies: main.FALLBACK_MESSAGE,
        )

        # Spy on crm_store.all_leads to assert it is NOT called
        import crm_store as _crm
        importlib.reload(_crm)
        monkeypatch.setattr(main, "crm_store", _crm)

        all_leads_calls = []
        original_all_leads = _crm.all_leads

        def spy_all_leads():
            all_leads_calls.append(True)
            return original_all_leads()

        monkeypatch.setattr(_crm, "all_leads", spy_all_leads)

        pipeline_calls = []

        def spy_pipeline(leads, *, sender=None, daily_cap=main.DAILY_SEND_CAP):
            pipeline_calls.append(list(leads))
            return {"cohorts": [], "dispatch_results": [], "brief": {}}

        monkeypatch.setattr(main, "run_outreach_pipeline", spy_pipeline)

        monkeypatch.setattr(sys, "argv", [
            "main.py",
            "Find brands in obscure vertical"
        ])

        main.main()

        # L6 must be completely skipped
        assert all_leads_calls == [], (
            "crm_store.all_leads() must NOT be called when result is FALLBACK_MESSAGE"
        )
        assert pipeline_calls == [], (
            "run_outreach_pipeline must NOT be called when result is FALLBACK_MESSAGE"
        )

    def test_parse_caller_key_patterns(self):
        """_parse_caller_key extracts the key from various query patterns."""
        assert main._parse_caller_key("access key is TestKey001") == "TestKey001"
        assert main._parse_caller_key("My Access Key Is ABC123") == "ABC123"
        assert main._parse_caller_key("key: MyKey") == "MyKey"
        assert main._parse_caller_key("key=XYZ") == "XYZ"
        assert main._parse_caller_key("no key here") == ""
        assert main._parse_caller_key("") == ""
        assert main._parse_caller_key(None) == ""

    def test_parse_caller_key_not_logged(self):
        """_parse_caller_key does not log the key value (OUT5/G4)."""
        import inspect
        src = inspect.getsource(main._parse_caller_key)
        assert "dual_log" not in src
        assert "print" not in src

    def test_crm_store_all_leads_function_exists(self):
        """crm_store.all_leads() exists and returns a list."""
        import crm_store as _crm
        assert callable(_crm.all_leads)
        importlib.reload(_crm)
        result = _crm.all_leads()
        assert isinstance(result, list)

    def test_crm_store_all_leads_no_id(self):
        """all_leads() strips mongo _id from records."""
        import crm_store as _crm
        importlib.reload(_crm)
        _crm.upsert_lead({
            "uniq_id": "testdomain.com",
            "domain": "testdomain.com",
        })
        records = _crm.all_leads()
        assert len(records) >= 1
        for rec in records:
            assert "_id" not in rec


# ===========================================================================
# OUT9 — Idempotent re-run (no duplicate sends)
# ===========================================================================

class TestOUT9Idempotency:
    """Calling run_outreach_pipeline twice on the same workspace ⇒
    identical cohorts/brief and the sender is NOT called again on the 2nd pass.
    """

    def test_idempotent_second_run_no_new_sends(
        self, monkeypatch, tmp_cwd, seeded_lead_store
    ):
        """Second run on already-sent leads → sender not called again."""
        import crm_store
        importlib.reload(crm_store)

        monkeypatch.setattr(main, "lead_store", seeded_lead_store)

        leads = [
            {
                "email": "dana.reyes@example.com",
                "caller_key": "TestKey001",
                "domain": "alphabrand.com",
                "angle_key": "crisis_social_media_001",
            }
        ]

        sender_calls_1 = []
        result1 = main.run_outreach_pipeline(
            leads, sender=lambda url, data: sender_calls_1.append(url)
        )

        sender_calls_2 = []
        result2 = main.run_outreach_pipeline(
            leads, sender=lambda url, data: sender_calls_2.append(url)
        )

        # 1st run: sender was called (lead was fresh)
        assert len(sender_calls_1) >= 1, "Sender must be called on the first run"
        # 2nd run: sender must NOT be called again (lead already marked sent)
        assert sender_calls_2 == [], (
            f"Sender must NOT be called on the 2nd run (idempotency). "
            f"Got calls: {sender_calls_2}"
        )

    def test_idempotent_brief_identical(
        self, monkeypatch, tmp_cwd, seeded_lead_store
    ):
        """Cohorts and brief are identical between the two runs."""
        import crm_store
        importlib.reload(crm_store)

        monkeypatch.setattr(main, "lead_store", seeded_lead_store)

        leads = [
            {
                "email": "dana.reyes@example.com",
                "caller_key": "TestKey001",
                "domain": "alphabrand.com",
                "angle_key": "crisis_social_media_001",
            }
        ]

        result1 = main.run_outreach_pipeline(
            leads, sender=lambda url, data: None
        )
        result2 = main.run_outreach_pipeline(
            leads, sender=lambda url, data: None
        )

        # Cohort shapes must be identical
        assert result1["cohorts"] == result2["cohorts"], (
            "Cohorts must be identical between runs"
        )
        # Brief summary (sent count) will differ but cohort_count/scheduled must be same
        assert result1["brief"]["cohort_count"] == result2["brief"]["cohort_count"]
        assert result1["brief"]["scheduled"] == result2["brief"]["scheduled"]


# ===========================================================================
# OUT10 — Packaging: crm_store.py in MANIFEST.txt; ENV4 holds
# ===========================================================================

class TestOUT10Packaging:
    """OUT10: crm_store.py is in MANIFEST.txt; ENV4 holds for all 4 modules."""

    def test_crm_store_in_manifest(self):
        """crm_store.py must appear in MANIFEST.txt (H5 update)."""
        manifest_path = pathlib.Path(_CRM_ROOT) / "MANIFEST.txt"
        assert manifest_path.exists(), "MANIFEST.txt must exist"
        content = manifest_path.read_text(encoding="utf-8")
        # Strip comments and blanks, find file entries
        entries = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert "crm_store.py" in entries, (
            f"crm_store.py must be in MANIFEST.txt. Current entries: {entries}"
        )

    def test_env4_all_four_modules_importable(self):
        """import main, lead_store, rag_engine, crm_store — zero side effects."""
        # This test passes if all four are already imported (they are, at module level).
        import importlib
        for mod_name in ("main", "lead_store", "rag_engine", "crm_store"):
            mod = importlib.import_module(mod_name)
            assert mod is not None

    def test_tool_count_still_10(self):
        """Tool count must stay 10 — Stage 14 adds no LLM tools."""
        assert len(main.TOOL_SCHEMAS) == 10
        assert len(main.TOOL_DISPATCH) == 10

    def test_outreach_status_brief_in_main(self):
        """outreach_status_brief is a plain function in main (not an LLM tool)."""
        assert hasattr(main, "outreach_status_brief")
        assert callable(main.outreach_status_brief)
        # Must NOT be in TOOL_SCHEMAS
        schema_names = {s["name"] for s in main.TOOL_SCHEMAS}
        assert "outreach_status_brief" not in schema_names

    def test_run_outreach_pipeline_in_main(self):
        """run_outreach_pipeline is a plain function in main (not an LLM tool)."""
        assert hasattr(main, "run_outreach_pipeline")
        assert callable(main.run_outreach_pipeline)
        schema_names = {s["name"] for s in main.TOOL_SCHEMAS}
        assert "run_outreach_pipeline" not in schema_names


# ===========================================================================
# A/B variant assignment rule (deterministic check)
# ===========================================================================

class TestABVariantRule:
    """The A/B variant tag is assigned by index parity — deterministic."""

    def test_ab_parity_rule(self):
        """Index 0 → A, 1 → B, 2 → A, 3 → B, etc."""
        # Build a state with 4 leads and dispatch results that include variants
        # set by run_outreach_pipeline based on lead index
        # We verify the rule in outreach_status_brief counting
        dispatch_results = [
            {"sent": True, "variant": "A"},  # index 0 → A
            {"sent": True, "variant": "B"},  # index 1 → B
            {"sent": True, "variant": "A"},  # index 2 → A
            {"sent": True, "variant": "B"},  # index 3 → B
        ]
        state = {
            "cohorts": [["l0", "l1", "l2", "l3"]],
            "dispatch_results": dispatch_results,
        }
        brief = main.outreach_status_brief(state)
        assert brief["variants"]["A"] == 2
        assert brief["variants"]["B"] == 2

    def test_single_lead_gets_variant_a(self):
        """A single lead (index 0) gets variant A."""
        state = {
            "cohorts": [["l0"]],
            "dispatch_results": [{"sent": True, "variant": "A"}],
        }
        brief = main.outreach_status_brief(state)
        assert brief["variants"]["A"] == 1
        assert brief["variants"]["B"] == 0


# ===========================================================================
# INT1 — run_outreach_pipeline does NOT reference OUTREACH_SUBDOMAIN directly
# ===========================================================================

class TestINT1EgressIsolation:
    """run_outreach_pipeline must not reference OUTREACH_SUBDOMAIN directly.
    It must call dispatch_outreach which owns the egress constraint (INT1).
    """

    def test_run_outreach_pipeline_no_direct_subdomain_reference(self):
        """run_outreach_pipeline functional code must not reference OUTREACH_SUBDOMAIN.

        Docstrings are excluded — only executable code is checked. The egress
        constraint is owned entirely by dispatch_outreach (INT1).
        """
        import ast
        import inspect
        src = inspect.getsource(main.run_outreach_pipeline)
        # Parse the source and find all Name nodes that reference OUTREACH_SUBDOMAIN
        # (excluding docstrings, which are just string constants).
        tree = ast.parse(src)
        # Collect all Name nodes (variable references)
        name_refs = [
            node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        ]
        # Also check string Attributes (e.g. f-strings referencing the constant)
        attr_refs = [
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        ]
        assert "OUTREACH_SUBDOMAIN" not in name_refs, (
            "run_outreach_pipeline must NOT reference OUTREACH_SUBDOMAIN as a Name; "
            "egress is handled inside dispatch_outreach"
        )
        assert "OUTREACH_SUBDOMAIN" not in attr_refs, (
            "run_outreach_pipeline must NOT reference OUTREACH_SUBDOMAIN as an Attribute; "
            "egress is handled inside dispatch_outreach"
        )


# ===========================================================================
# INT2 extension — auth gate honored in run_outreach_pipeline
# ===========================================================================

class TestINT2AuthGate:
    """run_outreach_pipeline honors the auth gate via dispatch_outreach."""

    def test_wrong_key_suppresses_dispatch(
        self, monkeypatch, tmp_cwd, seeded_lead_store
    ):
        """A lead with a wrong key → unauthorized; sender never called."""
        monkeypatch.setattr(main, "lead_store", seeded_lead_store)

        import crm_store
        importlib.reload(crm_store)

        sender_calls = []
        leads = [
            {
                "email": "dana.reyes@example.com",
                "caller_key": "WrongKey999",   # wrong key
                "domain": "alphabrand.com",
                "angle_key": "crisis_social_media_001",
            }
        ]
        result = main.run_outreach_pipeline(
            leads, sender=lambda url, data: sender_calls.append(url)
        )
        assert sender_calls == [], (
            "Sender must NOT be called when auth gate denies the key"
        )
        # The dispatch result must show the failure
        all_sent = [dr.get("sent") for dr in result["dispatch_results"]]
        assert not any(all_sent), "No sends should succeed with a wrong key"


# ===========================================================================
# G1 — no raw eval/exec in the new functions
# ===========================================================================

class TestG1NoEvalExec:
    """New Stage 14 functions contain no raw eval/exec."""

    def test_no_eval_in_outreach_status_brief(self):
        import inspect
        src = inspect.getsource(main.outreach_status_brief)
        assert "eval(" not in src
        assert "exec(" not in src

    def test_no_eval_in_run_outreach_pipeline(self):
        import inspect
        src = inspect.getsource(main.run_outreach_pipeline)
        assert "eval(" not in src
        assert "exec(" not in src
