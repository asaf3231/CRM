"""
tests/test_pipeline.py — connection-plan C4: live, ICP-driven discovery engine.

Covers (QA §13):
    CONN7   discovery job lifecycle: deterministic chain over MOCKED network tools
            (generate_search_queries / execute_3way_fanout / analyze_company_chunk);
            catalog matches that clear the ICP gate persist; net-new brands are reported
            but NOT saved (Policy 1); below-threshold brands don't qualify.
    CONN11  ICP wiring: seed composed from get_icp_document() vertical+want_signals;
            avoid_signals drop; icp_fit overlay from icp_tags intersection.
    CONN12  endpoint gating: 403 without ENABLE_LIVE, 401 on bad token, 409 single-job lock;
            no corporate_access_key in any job body.

All offline (MONGO_URI unset → mongomock); no live network. extract_and_score_pool +
load_catalog run for real against the real brands_catalog.csv so catalog mapping is genuine.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def _profile(domain, n_signals, title="", **px):
    """A fake analyze_company_chunk profile with n_signals ICP signals."""
    sigs = [f"sig_{i}" for i in range(n_signals)]
    p = {
        "domain": domain,
        "fetched": True,
        "operational_scale_signals": sigs,
        "title": title,
        "description": "",
        "tiktok_pixel": False,
        "meta_pixel": False,
        "gtm": True,
    }
    p.update(px)
    return p


def _patch_chain(monkeypatch, fanout_domains, profiles_by_domain):
    """Patch the 3 network tools; leave extract_and_score_pool + load_catalog REAL."""
    import main

    monkeypatch.setattr(main, "generate_search_queries", lambda seed, *a, **k: ["q1", "q2"])
    monkeypatch.setattr(
        main, "execute_3way_fanout",
        lambda queries: {"domains": {d: {"provenance": ["A"]} for d in fanout_domains}},
    )
    monkeypatch.setattr(
        main, "analyze_company_chunk",
        lambda domains: [profiles_by_domain.get(d, _profile(d, 0)) for d in domains],
    )


# ---------------------------------------------------------------------------
# CONN7 — discovery job lifecycle + persistence policy
# ---------------------------------------------------------------------------

class TestCONN7Lifecycle:

    def test_catalog_qualified_persists_netnew_does_not(self, monkeypatch):
        """aloyoga.com (catalog) qualifies → saved; a net-new domain qualifies → NOT saved."""
        import pipeline_runner
        import crm_store

        netnew = "totally-netnew-brand-xyz.com"
        _patch_chain(
            monkeypatch,
            fanout_domains=["aloyoga.com", netnew],
            profiles_by_domain={
                "aloyoga.com": _profile("aloyoga.com", 4),
                netnew: _profile(netnew, 3),
            },
        )

        job_id = pipeline_runner.create_job()
        job = pipeline_runner.run_discovery(job_id)

        assert job["status"] == "done" and job["stage"] == "done"
        saved_domains = {s["domain"] for s in job["saved"]}
        qualified_domains = {q["domain"] for q in job["qualified"]}
        assert "aloyoga.com" in saved_domains
        assert netnew not in saved_domains          # net-new not saved (Policy 1)
        assert {"aloyoga.com", netnew} <= qualified_domains  # both reported as qualified

        # Persisted: aloyoga present in crm_store, net-new absent.
        leads = {r["domain"] for r in crm_store.all_leads()}
        assert "aloyoga.com" in leads and netnew not in leads

    def test_below_threshold_not_qualified(self, monkeypatch):
        """A catalog brand with < ICP_TAG_THRESHOLD signals does not qualify or persist."""
        import pipeline_runner
        import crm_store
        import main

        _patch_chain(
            monkeypatch,
            fanout_domains=["vuori.com"],
            profiles_by_domain={"vuori.com": _profile("vuori.com", main.ICP_TAG_THRESHOLD - 1)},
        )
        job = pipeline_runner.run_discovery(pipeline_runner.create_job())
        assert job["qualified"] == [] and job["saved"] == []
        assert "vuori.com" not in {r["domain"] for r in crm_store.all_leads()}

    def test_runner_never_raises_records_error(self, monkeypatch):
        """A tool blowing up is recorded on the job (status='error'), not raised."""
        import pipeline_runner
        import main

        def _boom(*a, **k):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(main, "generate_search_queries", _boom)
        job = pipeline_runner.run_discovery(pipeline_runner.create_job())
        assert job["status"] == "error" and "kaboom" in (job["error"] or "")


# ---------------------------------------------------------------------------
# CONN11 — ICP wiring (seed composition, avoid_signals, icp_fit overlay)
# ---------------------------------------------------------------------------

class TestCONN11IcpWiring:

    def test_seed_composed_from_icp(self, monkeypatch):
        """The search seed is built from get_icp_document() vertical + want_signals."""
        import pipeline_runner
        import main
        import api_seed

        monkeypatch.setattr(
            api_seed, "get_icp_document",
            lambda: {"vertical": "Athleisure", "want_signals": ["high ad spend", "DTC brand"],
                     "avoid_signals": [], "icp_tags": []},
        )
        captured = {}

        def _capture_seed(seed, *a, **k):
            captured["seed"] = seed
            return ["q"]

        monkeypatch.setattr(main, "generate_search_queries", _capture_seed)
        monkeypatch.setattr(main, "execute_3way_fanout", lambda q: {"domains": {}})
        monkeypatch.setattr(main, "analyze_company_chunk", lambda d: [])

        pipeline_runner.run_discovery(pipeline_runner.create_job())
        assert "Athleisure" in captured["seed"]
        assert "high ad spend" in captured["seed"]

    def test_seed_override_wins(self, monkeypatch):
        """An explicit seed override is used instead of the ICP-composed seed."""
        import pipeline_runner
        import main

        captured = {}
        monkeypatch.setattr(main, "generate_search_queries",
                            lambda seed, *a, **k: captured.setdefault("seed", seed) or ["q"])
        monkeypatch.setattr(main, "execute_3way_fanout", lambda q: {"domains": {}})
        monkeypatch.setattr(main, "analyze_company_chunk", lambda d: [])

        pipeline_runner.run_discovery(pipeline_runner.create_job(), seed_override="custom vertical seed")
        assert captured["seed"] == "custom vertical seed"

    def test_avoid_signal_drops_candidate(self, monkeypatch):
        """A profile whose text matches an ICP avoid_signal is dropped even if it has >=3 signals."""
        import pipeline_runner
        import api_seed

        monkeypatch.setattr(
            api_seed, "get_icp_document",
            lambda: {"vertical": "X", "want_signals": [], "avoid_signals": ["wholesale marketplace"],
                     "icp_tags": []},
        )
        _patch_chain(
            monkeypatch,
            fanout_domains=["aloyoga.com"],
            profiles_by_domain={"aloyoga.com": _profile("aloyoga.com", 4, title="A wholesale marketplace for brands")},
        )
        job = pipeline_runner.run_discovery(pipeline_runner.create_job())
        assert job["qualified"] == [] and job["saved"] == []

    def test_icp_fit_overlay(self, monkeypatch):
        """icp_fit = |crawl signals ∩ ICP icp_tags|."""
        import pipeline_runner
        import api_seed

        monkeypatch.setattr(
            api_seed, "get_icp_document",
            lambda: {"vertical": "X", "want_signals": [], "avoid_signals": [],
                     "icp_tags": ["sig_0", "sig_1"]},  # overlaps the fake crawl signals
        )
        _patch_chain(
            monkeypatch,
            fanout_domains=["aloyoga.com"],
            profiles_by_domain={"aloyoga.com": _profile("aloyoga.com", 3)},  # sig_0,sig_1,sig_2
        )
        job = pipeline_runner.run_discovery(pipeline_runner.create_job())
        q = next(q for q in job["qualified"] if q["domain"] == "aloyoga.com")
        assert q["icpFit"] == 2


# ---------------------------------------------------------------------------
# CONN12 — endpoint gating + no secret leak
# ---------------------------------------------------------------------------

class TestCONN12Gating:

    def test_403_when_live_disabled(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api_server

        monkeypatch.delenv("ENABLE_LIVE", raising=False)
        resp = TestClient(api_server.app).post("/api/pipeline/discover", json={})
        assert resp.status_code == 403

    def test_401_on_bad_token(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api_server

        monkeypatch.setenv("ENABLE_LIVE", "1")
        monkeypatch.setenv("DISCOVERY_TOKEN", "secret-token")
        resp = TestClient(api_server.app).post(
            "/api/pipeline/discover", json={}, headers={"X-Discovery-Token": "wrong"},
        )
        assert resp.status_code == 401

    def test_409_when_a_job_is_running(self, monkeypatch):
        """A held single-job lock yields 409 (one run at a time)."""
        from fastapi.testclient import TestClient
        import api_server

        monkeypatch.setenv("ENABLE_LIVE", "1")
        monkeypatch.setenv("DISCOVERY_TOKEN", "tok")
        acquired = api_server._DISCOVERY_LOCK.acquire(blocking=False)
        assert acquired
        try:
            resp = TestClient(api_server.app).post(
                "/api/pipeline/discover", json={}, headers={"X-Discovery-Token": "tok"},
            )
            assert resp.status_code == 409
        finally:
            api_server._DISCOVERY_LOCK.release()

    def test_start_and_poll_job(self, monkeypatch):
        """Valid request → 200 {jobId, running}; the run is stubbed so no network fires."""
        from fastapi.testclient import TestClient
        import api_server
        import pipeline_runner

        monkeypatch.setenv("ENABLE_LIVE", "1")
        monkeypatch.setenv("DISCOVERY_TOKEN", "tok")
        # Stub the actual run so the background thread does no real work.
        monkeypatch.setattr(pipeline_runner, "run_discovery",
                            lambda job_id, seed=None: pipeline_runner.get_job(job_id))

        client = TestClient(api_server.app)
        start = client.post("/api/pipeline/discover", json={"seed": "test"},
                            headers={"X-Discovery-Token": "tok"})
        assert start.status_code == 200
        body = start.json()
        assert body["status"] == "running" and body["jobId"]

        poll = client.get(f"/api/pipeline/discover/{body['jobId']}")
        assert poll.status_code == 200
        assert poll.json()["jobId"] == body["jobId"]

    def test_unknown_job_404(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api_server

        resp = TestClient(api_server.app).get("/api/pipeline/discover/does-not-exist")
        assert resp.status_code == 404

    def test_no_corporate_access_key_in_job_body(self, monkeypatch):
        """No discovery job body ever carries corporate_access_key (no Policy-4 access here)."""
        import pipeline_runner

        _patch_chain(
            monkeypatch,
            fanout_domains=["aloyoga.com"],
            profiles_by_domain={"aloyoga.com": _profile("aloyoga.com", 4)},
        )
        job = pipeline_runner.run_discovery(pipeline_runner.create_job())
        assert "corporate_access_key" not in json.dumps(job)


# ---------------------------------------------------------------------------
# CONN15 — the full ICP shapes the search queries (deterministic, no keys)
# ---------------------------------------------------------------------------

class TestCONN15IcpDrivesQueries:
    """CONN15: every ICP field (vertical/want/tags/geo/size) shapes compose_icp_query_terms."""

    def test_full_icp_fields_appear_in_seed(self):
        import pipeline_runner

        seed = pipeline_runner.compose_icp_query_terms({
            "vertical": "Athleisure", "want_signals": ["high ad spend"],
            "icp_tags": ["ecommerce_dtc"], "geo": "North America", "size_band": "Mid-Market",
        })
        assert "Athleisure" in seed
        assert "high ad spend" in seed
        assert "ecommerce dtc" in seed          # humanized canonical tag
        assert "North America" in seed
        assert "Mid-Market" in seed

    def test_changing_an_icp_field_changes_the_seed(self):
        import pipeline_runner

        base = {"vertical": "X", "want_signals": [], "icp_tags": [], "geo": "Europe", "size_band": ""}
        assert (
            pipeline_runner.compose_icp_query_terms(base)
            != pipeline_runner.compose_icp_query_terms({**base, "geo": "APAC"})
        )
        assert (
            pipeline_runner.compose_icp_query_terms(base)
            != pipeline_runner.compose_icp_query_terms({**base, "icp_tags": ["pixel_tracking_present"]})
        )

    def test_empty_icp_falls_back(self):
        import pipeline_runner
        assert pipeline_runner.compose_icp_query_terms({}) == "ecommerce DTC brands"


# ---------------------------------------------------------------------------
# CONN16 — the ICP actually affects scoring (icp_fit > 0; icp_score ranking)
# ---------------------------------------------------------------------------

class TestCONN16IcpScoringIsReal:
    """CONN16: canonicalized icp_tags overlap the crawl signals (was always 0 pre-C8)."""

    def test_seed_icp_tags_now_overlap_crawl_signals(self):
        """The default SEED_ICP icp_tags are canonical → overlap a crawl that surfaced them."""
        import pipeline_runner
        import api_seed

        icp_tags = set(pipeline_runner.canonicalize_icp_tags(api_seed.SEED_ICP["icp_tags"]))
        crawl_signals = {"ecommerce_dtc", "ad_spend_signals", "scale_growth_stage"}
        assert len(crawl_signals & icp_tags) >= 2, "SEED_ICP tags must overlap canonical crawl signals (C8)"

    def test_canonicalize_maps_legacy_aliases(self):
        import pipeline_runner

        out = pipeline_runner.canonicalize_icp_tags(["dtc_brand", "high ad spend", "ecommerce"])
        assert "ecommerce_dtc" in out
        assert "ad_spend_signals" in out

    def test_canonicalize_passes_through_unknowns(self):
        """Explicit/unknown signal names survive (so nothing is silently dropped)."""
        import pipeline_runner
        assert pipeline_runner.canonicalize_icp_tags(["sig_0", "sig_1"]) == ["sig_0", "sig_1"]

    def test_icp_score_rewards_overlap_penalizes_avoid_and_is_bounded(self):
        import pipeline_runner

        icp = {"icp_tags": ["ecommerce_dtc", "ad_spend_signals"], "avoid_signals": ["wholesale marketplace"]}
        sig = ["ecommerce_dtc", "ad_spend_signals", "pixel_tracking_present"]
        good = {"operational_scale_signals": sig, "title": "A DTC brand", "description": ""}
        bad = {"operational_scale_signals": sig, "title": "A wholesale marketplace", "description": ""}
        assert pipeline_runner.icp_score(good, icp) > pipeline_runner.icp_score(bad, icp)
        assert 0.0 <= pipeline_runner.icp_score(good, icp) <= 1.0

    def test_run_discovery_ranks_qualified_by_icp_score(self, monkeypatch):
        import pipeline_runner
        import api_seed

        monkeypatch.setattr(
            api_seed, "get_icp_document",
            lambda: {"vertical": "X", "want_signals": [], "avoid_signals": [],
                     "icp_tags": ["sig_0", "sig_1", "sig_2"]},
        )
        _patch_chain(
            monkeypatch,
            fanout_domains=["a.com", "b.com"],
            profiles_by_domain={
                "a.com": _profile("a.com", 3),  # signals sig_0,1,2 → overlap 3
                "b.com": _profile("b.com", 3, operational_scale_signals=["sig_0", "z1", "z2"]),  # overlap 1
            },
        )
        job = pipeline_runner.run_discovery(pipeline_runner.create_job())
        scores = [q["icpScore"] for q in job["qualified"]]
        assert scores == sorted(scores, reverse=True), f"qualified not ranked by icpScore: {scores}"
        assert all("icpScore" in q for q in job["qualified"])


# ---------------------------------------------------------------------------
# CONN17 — graded contract byte-stable (C8 touches only ICP-side data/logic)
# ---------------------------------------------------------------------------

class TestCONN17GradedGateUntouched:
    """CONN17: C8 does NOT change the graded gate — main.py untouched (ICPB5 / Policy 2)."""

    def test_icp_tag_threshold_unchanged(self):
        import main
        assert main.ICP_TAG_THRESHOLD == 3

    def test_tool_count_still_10(self):
        import main
        assert len(main.TOOL_SCHEMAS) == 10
        assert len(main.TOOL_DISPATCH) == 10

    def test_alias_targets_are_subset_of_graded_vocab(self):
        """Every canonicalization target is a real _ICP_TAGS key (keeps them in sync)."""
        import main
        import pipeline_runner
        assert set(pipeline_runner._ICP_TAG_ALIASES.values()) <= set(main._ICP_TAGS.keys())

    def test_evaluate_icp_tags_gate_behaviour_intact(self):
        """The graded ≥3 gate still passes >=3 distinct tags and fails <3."""
        import main
        text_3 = "shopify direct-to-consumer ; facebook ads tiktok ads ; series a venture-backed"
        text_1 = "shopify direct-to-consumer only"
        assert main.evaluate_icp_tags(text_3)["qualified"] is True
        assert main.evaluate_icp_tags(text_1)["qualified"] is False
