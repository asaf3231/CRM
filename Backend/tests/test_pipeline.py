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
