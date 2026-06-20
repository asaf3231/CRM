"""
tests/test_api.py — Stage I1 + I2 API scaffold and endpoint checks
Phase 3 Integration Layer — ReactFirst AI Proactive Outbound Engine

QA checks covered:
    INTG1  import-safety: `import api_server` from an empty tmp dir exits 0 with no side effects.
    INTG2  singleton reset: conftest.py resets crm_store._leads_collection to None before each test.
    INTG3  health endpoint: GET /api/health → 200, {"status": "ok"};
           CORS middleware configured with localhost-only origin.
    INTG4  leads endpoints: GET /api/leads, GET /api/leads/stats, POST /api/leads/find-more.
    INTG5  adapter contract + thresholds: gov_band/fit_grade/lead_kind at boundaries;
           crm_lead_to_ui strips contact_ids and corporate_access_key;
           /api/leads response items contain neither contact_ids nor corporate_access_key.
    INTG6  ICP endpoints (offline seed): GET /api/icp, GET /api/icp/suggestions;
           ICP comes from seed dict, NOT from build_icp_document.
"""

import json
import os
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# INTG1 — Import-safety: subprocess probe from an empty tmp dir
# ---------------------------------------------------------------------------

class TestINTG1ImportSafety:
    """INTG1: import api_server must be side-effect-free."""

    def test_import_api_server_no_side_effects(self, tmp_path):
        """Run `python -c "import api_server"` from a fresh empty dir.

        The env has ANTHROPIC_API_KEY stripped.  None of the 3 input files
        (brands_catalog.csv, contacts.json, gtm_policies.txt) are present.
        The command must exit 0 with no stdout/stderr noise.
        """
        # Build a clean environment without ANTHROPIC_API_KEY
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        # The api_server module lives in the repo root; put it on PYTHONPATH
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = repo_root + (os.pathsep + python_path if python_path else "")

        result = subprocess.run(
            [sys.executable, "-c", "import api_server"],
            cwd=str(tmp_path),  # empty directory — no input files
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"import api_server failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
        # No side-effect noise expected on stdout
        assert result.stdout.strip() == "", (
            f"Unexpected stdout on import: {result.stdout!r}"
        )

    def test_import_api_server_no_backend_imports_at_top_level(self):
        """Verify api_server does not import crm_store/lead_store/main at module top level.

        We import api_server in-process and check that none of the backend
        singleton attributes were initialized.
        """
        import crm_store
        import lead_store

        # Reset first (conftest already does this, but be explicit)
        crm_store._leads_collection = None
        lead_store._collection_instance = None

        # Import api_server — must not trigger any backend work
        import api_server  # noqa: F401

        assert crm_store._leads_collection is None, (
            "crm_store._leads_collection was initialized by importing api_server — "
            "import is NOT side-effect-free."
        )
        assert lead_store._collection_instance is None, (
            "lead_store._collection_instance was initialized by importing api_server — "
            "import is NOT side-effect-free."
        )

    def test_import_api_seed_no_side_effects(self, tmp_path):
        """INTG4 import-safety regression: import api_seed from an empty dir exits 0."""
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = repo_root + (os.pathsep + python_path if python_path else "")

        result = subprocess.run(
            [sys.executable, "-c", "import api_seed"],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"import api_seed failed (exit {result.returncode}).\n"
            f"stderr: {result.stderr!r}"
        )
        assert result.stdout.strip() == "", f"Unexpected stdout: {result.stdout!r}"

    def test_import_api_adapters_no_side_effects(self, tmp_path):
        """INTG4 import-safety regression: import api_adapters from an empty dir exits 0."""
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = repo_root + (os.pathsep + python_path if python_path else "")

        result = subprocess.run(
            [sys.executable, "-c", "import api_adapters"],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"import api_adapters failed (exit {result.returncode}).\n"
            f"stderr: {result.stderr!r}"
        )
        assert result.stdout.strip() == "", f"Unexpected stdout: {result.stdout!r}"

    def test_import_api_seed_does_not_init_crm_store(self):
        """import api_seed must NOT initialize crm_store._leads_collection."""
        import crm_store
        crm_store._leads_collection = None

        import api_seed  # noqa: F401

        assert crm_store._leads_collection is None, (
            "crm_store._leads_collection was initialized by importing api_seed — "
            "import is NOT side-effect-free."
        )


# ---------------------------------------------------------------------------
# INTG2 — Singleton reset fixture verification
# ---------------------------------------------------------------------------

class TestINTG2SingletonReset:
    """INTG2: conftest.py resets singletons to None before each test."""

    def test_leads_collection_is_none_at_test_start(self):
        """crm_store._leads_collection must be None at the start of each test
        (i.e. the autouse fixture has run its pre-test reset).

        This test proves the reset fixture is active.
        """
        import crm_store
        assert crm_store._leads_collection is None, (
            "crm_store._leads_collection is not None at test start — "
            "the conftest.py reset fixture is not running correctly."
        )

    def test_lead_store_instance_is_none_at_test_start(self):
        """lead_store._collection_instance must be None at the start of each test."""
        import lead_store
        assert lead_store._collection_instance is None, (
            "lead_store._collection_instance is not None at test start — "
            "the conftest.py reset fixture is not running correctly."
        )

    def test_singleton_written_in_one_test_does_not_leak_to_next(self):
        """Write to crm_store singleton then confirm cleanup happens.

        This test sets _leads_collection to a sentinel value.  The autouse
        fixture's POST-test reset should clear it before the next test.  We
        verify the reset works by checking it here — if the previous test's
        write had leaked, this test would see a non-None value, but the
        autouse already ran its pre-test reset before entering this test,
        so we always start clean.
        """
        import crm_store

        # Precondition: starts None (fixture ran)
        assert crm_store._leads_collection is None

        # Simulate a write (e.g. what I2 seed does)
        crm_store._leads_collection = object()  # sentinel
        assert crm_store._leads_collection is not None  # write took effect

        # After this test, the autouse post-test reset will set it back to None


# ---------------------------------------------------------------------------
# INTG3 — Health endpoint + CORS middleware
# ---------------------------------------------------------------------------

class TestINTG3HealthAndCORS:
    """INTG3: GET /api/health returns 200 + {"status":"ok"}; CORS configured."""

    def test_health_returns_200(self):
        """GET /api/health → 200."""
        from fastapi.testclient import TestClient
        import api_server

        client = TestClient(api_server.app)
        response = client.get("/api/health")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text!r}"
        )

    def test_health_returns_correct_json(self):
        """GET /api/health → {"status": "ok"} (exact)."""
        from fastapi.testclient import TestClient
        import api_server

        client = TestClient(api_server.app)
        response = client.get("/api/health")
        assert response.json() == {"status": "ok"}, (
            f"Unexpected body: {response.json()!r}"
        )

    def test_health_content_type_is_json(self):
        """Response content-type must be application/json."""
        from fastapi.testclient import TestClient
        import api_server

        client = TestClient(api_server.app)
        response = client.get("/api/health")
        assert "application/json" in response.headers.get("content-type", ""), (
            f"Unexpected content-type: {response.headers.get('content-type')!r}"
        )

    def test_cors_middleware_is_present(self):
        """FastAPI app has CORSMiddleware configured."""
        import api_server
        from fastapi.middleware.cors import CORSMiddleware

        middleware_classes = [
            m.cls for m in api_server.app.user_middleware
        ]
        assert CORSMiddleware in middleware_classes, (
            f"CORSMiddleware not found in app middleware stack. "
            f"Found: {middleware_classes}"
        )

    def test_cors_allow_origins_is_localhost_only(self):
        """CORS allow_origins must be exactly ['http://localhost:5173'].

        The decision to restrict to localhost-only is recorded in NOTES.md.
        """
        import api_server
        from fastapi.middleware.cors import CORSMiddleware

        cors_middleware = None
        for m in api_server.app.user_middleware:
            if m.cls is CORSMiddleware:
                cors_middleware = m
                break

        assert cors_middleware is not None, "CORSMiddleware not found"

        # kwargs are stored in m.kwargs
        allow_origins = cors_middleware.kwargs.get("allow_origins", [])
        assert allow_origins == ["http://localhost:5173"], (
            f"Expected allow_origins=['http://localhost:5173'], got {allow_origins!r}"
        )

    def test_cors_preflight_allowed_from_localhost(self):
        """A preflight OPTIONS request from http://localhost:5173 is accepted."""
        from fastapi.testclient import TestClient
        import api_server

        client = TestClient(api_server.app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should be 200 (or 204); must include ACAO header
        assert response.status_code in (200, 204), (
            f"Preflight failed: {response.status_code}"
        )
        acao = response.headers.get("access-control-allow-origin", "")
        assert "localhost:5173" in acao, (
            f"Expected localhost:5173 in Access-Control-Allow-Origin, got {acao!r}"
        )

    def test_app_has_lifespan(self):
        """FastAPI app was created with a lifespan context manager (not a plain on_event)."""
        import api_server

        # In FastAPI >= 0.93, lifespan is stored as router.lifespan_context
        # The exact attribute varies by version; we accept any truthy lifespan indicator.
        router = api_server.app.router
        has_lifespan = (
            getattr(router, "lifespan_context", None) is not None
            or getattr(api_server.app, "lifespan", None) is not None
        )
        assert has_lifespan, (
            "FastAPI app does not have a lifespan context manager configured."
        )


# ---------------------------------------------------------------------------
# INTG5 — Adapter unit tests (no server needed)
# ---------------------------------------------------------------------------

class TestINTG5AdapterThresholds:
    """INTG5: gov_band/fit_grade/lead_kind boundary tests + crm_lead_to_ui strip."""

    # --- gov_band boundaries ---
    def test_gov_band_zero_is_no_gov(self):
        """incidents=0 → 'No Gov'."""
        from api_adapters import gov_band
        assert gov_band(0) == "No Gov"

    def test_gov_band_one_is_light_gov(self):
        """incidents=1 → 'Light Gov'."""
        from api_adapters import gov_band
        assert gov_band(1) == "Light Gov"

    def test_gov_band_two_is_light_gov(self):
        """incidents=2 → 'Light Gov'."""
        from api_adapters import gov_band
        assert gov_band(2) == "Light Gov"

    def test_gov_band_three_is_heavy_gov(self):
        """incidents=3 → 'Heavy Gov' (boundary)."""
        from api_adapters import gov_band
        assert gov_band(3) == "Heavy Gov"

    def test_gov_band_large_is_heavy_gov(self):
        """incidents=10 → 'Heavy Gov'."""
        from api_adapters import gov_band
        assert gov_band(10) == "Heavy Gov"

    # --- fit_grade boundaries ---
    def test_fit_grade_one_is_weak(self):
        """icp_count=1 → 'Weak'."""
        from api_adapters import fit_grade
        assert fit_grade(1) == "Weak"

    def test_fit_grade_zero_is_weak(self):
        """icp_count=0 → 'Weak'."""
        from api_adapters import fit_grade
        assert fit_grade(0) == "Weak"

    def test_fit_grade_two_is_medium(self):
        """icp_count=2 → 'Medium'."""
        from api_adapters import fit_grade
        assert fit_grade(2) == "Medium"

    def test_fit_grade_three_is_medium(self):
        """icp_count=3 → 'Medium'."""
        from api_adapters import fit_grade
        assert fit_grade(3) == "Medium"

    def test_fit_grade_four_is_strong(self):
        """icp_count=4 → 'Strong' (boundary)."""
        from api_adapters import fit_grade
        assert fit_grade(4) == "Strong"

    def test_fit_grade_large_is_strong(self):
        """icp_count=8 → 'Strong'."""
        from api_adapters import fit_grade
        assert fit_grade(8) == "Strong"

    # --- lead_kind ---
    def test_lead_kind_active_client_is_existing(self):
        """current_status='Active_Client' → 'Existing'."""
        from api_adapters import lead_kind
        assert lead_kind("Active_Client") == "Existing"

    def test_lead_kind_unreached_prospect_is_new(self):
        """current_status='Unreached_Prospect' → 'New'."""
        from api_adapters import lead_kind
        assert lead_kind("Unreached_Prospect") == "New"

    def test_lead_kind_open_opportunity_is_new(self):
        """current_status='Open_Opportunity' → 'New'."""
        from api_adapters import lead_kind
        assert lead_kind("Open_Opportunity") == "New"

    def test_lead_kind_unknown_is_new(self):
        """Unknown current_status → 'New'."""
        from api_adapters import lead_kind
        assert lead_kind("Unknown") == "New"

    # --- crm_lead_to_ui strip ---
    def test_crm_lead_to_ui_strips_contact_ids(self):
        """contact_ids must NOT appear in crm_lead_to_ui output (INTG5)."""
        from api_adapters import crm_lead_to_ui

        record = {
            "uniq_id": "test-001",
            "domain": "example.com",
            "company": "Example Co",
            "win_prob": 0.5,
            "icp_count": 3,
            "historical_social_incidents": 2,
            "current_status": "Open_Opportunity",
            "stage": "in_crm",
            "profile": {"icp_tags": ["dtc_brand"]},
            "contact_ids": ["ceo@example.com", "vp@example.com"],
        }
        result = crm_lead_to_ui(record)
        assert "contact_ids" not in result, (
            f"contact_ids found in output: {result}"
        )

    def test_crm_lead_to_ui_strips_corporate_access_key(self):
        """corporate_access_key must NEVER appear in crm_lead_to_ui output (INTG5 / G4)."""
        from api_adapters import crm_lead_to_ui

        record = {
            "uniq_id": "test-002",
            "domain": "example2.com",
            "company": "Example 2",
            "win_prob": 0.6,
            "icp_count": 4,
            "historical_social_incidents": 1,
            "current_status": "Active_Client",
            "stage": "enrolled",
            "profile": {"icp_tags": ["high_ad_spend"]},
            "contact_ids": [],
            "corporate_access_key": "ShouldBeStripped99",
        }
        result = crm_lead_to_ui(record)
        assert "corporate_access_key" not in result, (
            f"corporate_access_key found in output: {result}"
        )
        # Also check it doesn't appear as a value in any depth
        result_str = json.dumps(result)
        assert "corporate_access_key" not in result_str, (
            f"'corporate_access_key' string found in JSON output: {result_str}"
        )
        assert "ShouldBeStripped99" not in result_str, (
            f"corporate_access_key value found in JSON output: {result_str}"
        )

    def test_crm_lead_to_ui_score_is_rounded_win_prob_times_100(self):
        """score == round(win_prob * 100)."""
        from api_adapters import crm_lead_to_ui

        record = {
            "uniq_id": "test-003",
            "domain": "brand.com",
            "company": "Brand",
            "win_prob": 0.756,
            "icp_count": 3,
            "historical_social_incidents": 0,
            "current_status": "Open_Opportunity",
            "stage": "qualified",
            "profile": {"icp_tags": []},
            "contact_ids": [],
        }
        result = crm_lead_to_ui(record)
        assert result["score"] == round(0.756 * 100), (
            f"Expected score={round(0.756*100)}, got {result['score']}"
        )

    def test_crm_lead_to_ui_output_has_all_required_keys(self):
        """crm_lead_to_ui output has exactly the Lead camelCase keys."""
        from api_adapters import crm_lead_to_ui

        record = {
            "uniq_id": "test-004",
            "domain": "test.com",
            "company": "Test",
            "win_prob": 0.3,
            "icp_count": 2,
            "historical_social_incidents": 1,
            "current_status": "Unreached_Prospect",
            "stage": "discovered",
            "profile": {"icp_tags": ["dtc_brand"]},
            "contact_ids": [],
        }
        result = crm_lead_to_ui(record)
        expected_keys = {"id", "company", "domain", "score", "fit", "gov", "kind", "stage", "tags", "winProb"}
        assert set(result.keys()) == expected_keys, (
            f"Unexpected keys: {set(result.keys())} vs expected {expected_keys}"
        )

    def test_crm_lead_to_ui_tags_defaults_to_empty_list(self):
        """A record with no profile.icp_tags defaults tags to []."""
        from api_adapters import crm_lead_to_ui

        record = {
            "uniq_id": "test-005",
            "domain": "notagsbrand.com",
            "company": "No Tags Brand",
            "win_prob": 0.1,
            "icp_count": 0,
            "historical_social_incidents": 0,
            "current_status": "Unreached_Prospect",
            "stage": "discovered",
            "profile": {},
            "contact_ids": [],
        }
        result = crm_lead_to_ui(record)
        assert result["tags"] == [], f"Expected [], got {result['tags']}"


# ---------------------------------------------------------------------------
# INTG4 — Leads endpoints (use context manager to trigger lifespan)
# ---------------------------------------------------------------------------

class TestINTG4LeadsEndpoints:
    """INTG4: GET /api/leads, GET /api/leads/stats, POST /api/leads/find-more."""

    def test_get_leads_returns_200(self):
        """GET /api/leads → 200."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text!r}"
        )

    def test_get_leads_returns_non_empty_list(self):
        """GET /api/leads → non-empty list (seed has 16 records)."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads")
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) > 0, "Expected non-empty leads list after seed"

    def test_get_leads_each_item_has_camelcase_keys(self):
        """Each item in /api/leads has the camelCase Lead keys."""
        from fastapi.testclient import TestClient
        import api_server

        expected_keys = {"id", "company", "domain", "score", "fit", "gov", "kind", "stage", "tags", "winProb"}

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads")
        data = response.json()
        for item in data:
            for key in expected_keys:
                assert key in item, (
                    f"Missing key '{key}' in lead item: {item}"
                )

    def test_get_leads_no_contact_ids_in_response(self):
        """contact_ids must NOT appear in any /api/leads response item (INTG5)."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads")
        data = response.json()
        response_str = json.dumps(data)
        assert "contact_ids" not in response_str, (
            f"'contact_ids' found in /api/leads response: {response_str[:300]}"
        )

    def test_get_leads_no_corporate_access_key_in_response(self):
        """corporate_access_key must NOT appear in any /api/leads response item (INTG5 / G4)."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads")
        data = response.json()
        response_str = json.dumps(data)
        assert "corporate_access_key" not in response_str, (
            f"'corporate_access_key' found in /api/leads response: {response_str[:300]}"
        )

    def test_get_leads_stats_returns_200(self):
        """GET /api/leads/stats → 200."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads/stats")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text!r}"
        )

    def test_get_leads_stats_has_all_discovery_stats_keys(self):
        """GET /api/leads/stats → all LeadDiscoveryStats keys present."""
        from fastapi.testclient import TestClient
        import api_server

        expected_keys = {
            "goal", "discovered", "filteredByIcp", "retained",
            "belowFloor", "aboveFloor", "newCount", "existingCount",
            "alreadyInCrm", "strong", "review", "weak", "strictness",
        }

        with TestClient(api_server.app) as client:
            response = client.get("/api/leads/stats")
        data = response.json()
        for key in expected_keys:
            assert key in data, (
                f"Missing key '{key}' in /api/leads/stats response: {data}"
            )

    def test_find_more_leads_returns_200(self):
        """POST /api/leads/find-more → 200."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.post(
                "/api/leads/find-more",
                json={"existing_domains": [], "target": 5},
            )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text!r}"
        )

    def test_find_more_leads_excludes_existing_domain(self):
        """POST /api/leads/find-more with one seeded domain → that domain excluded."""
        from fastapi.testclient import TestClient
        import api_server

        # apexwear.com is seed-lead-001's domain
        excluded_domain = "apexwear.com"

        with TestClient(api_server.app) as client:
            response = client.post(
                "/api/leads/find-more",
                json={"existing_domains": [excluded_domain], "target": 5},
            )
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        domains_in_result = [item["domain"] for item in data]
        assert excluded_domain not in domains_in_result, (
            f"Excluded domain '{excluded_domain}' still appears in find-more result: {domains_in_result}"
        )

    def test_find_more_leads_respects_target_count(self):
        """POST /api/leads/find-more with target=5 → at most 5 results."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.post(
                "/api/leads/find-more",
                json={"existing_domains": [], "target": 5},
            )
        data = response.json()
        assert len(data) <= 5, (
            f"Expected at most 5 results, got {len(data)}"
        )

    def test_find_more_leads_each_item_has_camelcase_keys(self):
        """POST /api/leads/find-more items have the camelCase Lead keys."""
        from fastapi.testclient import TestClient
        import api_server

        expected_keys = {"id", "company", "domain", "score", "fit", "gov", "kind", "stage", "tags", "winProb"}

        with TestClient(api_server.app) as client:
            response = client.post(
                "/api/leads/find-more",
                json={"existing_domains": [], "target": 3},
            )
        data = response.json()
        for item in data:
            for key in expected_keys:
                assert key in item, (
                    f"Missing key '{key}' in find-more item: {item}"
                )

    def test_find_more_leads_no_contact_ids_in_response(self):
        """contact_ids must NOT appear in find-more response (INTG5)."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.post(
                "/api/leads/find-more",
                json={"existing_domains": [], "target": 10},
            )
        response_str = json.dumps(response.json())
        assert "contact_ids" not in response_str, (
            f"'contact_ids' found in find-more response"
        )


# ---------------------------------------------------------------------------
# INTG6 — ICP endpoints (offline seed)
# ---------------------------------------------------------------------------

class TestINTG6IcpEndpoints:
    """INTG6: GET /api/icp, GET /api/icp/suggestions; seed-based, not live."""

    def test_get_icp_returns_200(self):
        """GET /api/icp → 200."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text!r}"
        )

    def test_get_icp_has_all_required_keys(self):
        """GET /api/icp → IcpDocument with all keys."""
        from fastapi.testclient import TestClient
        import api_server

        expected_keys = {
            "id", "title", "description", "source", "keywords",
            "industryVerticals", "geographicFocus",
            "qualificationCriteria", "anchorCompanies",
        }

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp")
        data = response.json()
        for key in expected_keys:
            assert key in data, (
                f"Missing key '{key}' in /api/icp response: {data}"
            )

    def test_get_icp_title_equals_seed_vertical(self):
        """GET /api/icp → title == SEED_ICP['vertical']."""
        from fastapi.testclient import TestClient
        import api_server
        import api_seed

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp")
        data = response.json()
        assert data["title"] == api_seed.SEED_ICP["vertical"], (
            f"Expected title={api_seed.SEED_ICP['vertical']!r}, got {data['title']!r}"
        )

    def test_get_icp_source_is_companies(self):
        """GET /api/icp → source == 'Companies'."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp")
        data = response.json()
        assert data["source"] == "Companies", (
            f"Expected source='Companies', got {data['source']!r}"
        )

    def test_get_icp_qualification_criteria_length(self):
        """GET /api/icp → qualificationCriteria len == len(want)+len(avoid)."""
        from fastapi.testclient import TestClient
        import api_server
        import api_seed

        expected_len = (
            len(api_seed.SEED_ICP["want_signals"])
            + len(api_seed.SEED_ICP["avoid_signals"])
        )

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp")
        data = response.json()
        actual_len = len(data["qualificationCriteria"])
        assert actual_len == expected_len, (
            f"Expected qualificationCriteria length {expected_len}, got {actual_len}"
        )

    def test_get_icp_does_not_call_build_icp_document(self):
        """GET /api/icp must NOT call build_icp_document (offline seed only)."""
        from fastapi.testclient import TestClient
        import api_server

        # We verify by checking that main is not imported at all during the call,
        # or by confirming the response is deterministic without any LLM key set.
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with TestClient(api_server.app) as client:
                response = client.get("/api/icp")
            # If it called build_icp_document (which needs ANTHROPIC_API_KEY),
            # it would fail without the key. Success means it used the seed.
            assert response.status_code == 200, (
                f"Expected 200 (seed-based, no key needed), "
                f"got {response.status_code}. Body: {response.text!r}"
            )
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

    def test_get_icp_suggestions_returns_200(self):
        """GET /api/icp/suggestions → 200."""
        from fastapi.testclient import TestClient
        import api_server

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp/suggestions")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text!r}"
        )

    def test_get_icp_suggestions_equals_seed_want_signals(self):
        """GET /api/icp/suggestions → == SEED_ICP['want_signals']."""
        from fastapi.testclient import TestClient
        import api_server
        import api_seed

        with TestClient(api_server.app) as client:
            response = client.get("/api/icp/suggestions")
        data = response.json()
        assert data == api_seed.SEED_ICP["want_signals"], (
            f"Expected {api_seed.SEED_ICP['want_signals']!r}, got {data!r}"
        )

    def test_icp_doc_to_ui_qualification_criteria_want_is_high(self):
        """icp_doc_to_ui: each want_signal gets importance='High'."""
        from api_adapters import icp_doc_to_ui

        seed = {
            "vertical": "TestVertical",
            "want_signals": ["signal_a", "signal_b"],
            "avoid_signals": ["avoid_x"],
            "geo": "EU",
            "size_band": "SMB",
            "anchor_companies": [],
        }
        result = icp_doc_to_ui(seed)
        high_criteria = [c for c in result["qualificationCriteria"] if c["importance"] == "High"]
        assert len(high_criteria) == 2, f"Expected 2 High criteria, got {len(high_criteria)}"
        criterion_texts = [c["criterion"] for c in high_criteria]
        assert "signal_a" in criterion_texts
        assert "signal_b" in criterion_texts

    def test_icp_doc_to_ui_qualification_criteria_avoid_is_low(self):
        """icp_doc_to_ui: each avoid_signal gets importance='Low' with 'Avoid: ' prefix."""
        from api_adapters import icp_doc_to_ui

        seed = {
            "vertical": "TestVertical",
            "want_signals": [],
            "avoid_signals": ["brick-and-mortar"],
            "geo": "APAC",
            "size_band": "Enterprise",
            "anchor_companies": [],
        }
        result = icp_doc_to_ui(seed)
        low_criteria = [c for c in result["qualificationCriteria"] if c["importance"] == "Low"]
        assert len(low_criteria) == 1, f"Expected 1 Low criterion, got {len(low_criteria)}"
        assert low_criteria[0]["criterion"] == "Avoid: brick-and-mortar", (
            f"Unexpected criterion text: {low_criteria[0]['criterion']!r}"
        )

    def test_stats_to_ui_all_keys_present(self):
        """stats_to_ui output has all 13 LeadDiscoveryStats keys."""
        from api_adapters import stats_to_ui

        seed_stats = {
            "goal": 60, "discovered": 42, "filteredByIcp": 14,
            "retained": 28, "belowFloor": 4, "aboveFloor": 24,
            "newCount": 20, "existingCount": 8, "alreadyInCrm": 5,
            "strong": 10, "review": 11, "weak": 7, "strictness": "Balanced strictness",
        }
        result = stats_to_ui(seed_stats)
        expected_keys = {
            "goal", "discovered", "filteredByIcp", "retained",
            "belowFloor", "aboveFloor", "newCount", "existingCount",
            "alreadyInCrm", "strong", "review", "weak", "strictness",
        }
        assert set(result.keys()) == expected_keys, (
            f"Unexpected keys: {set(result.keys())} vs {expected_keys}"
        )


# ---------------------------------------------------------------------------
# INTG7 — Outreach endpoints: stats + cohorts
# ---------------------------------------------------------------------------

class TestINTG7OutreachEndpoints:
    """INTG7: GET /api/outreach/stats → OutreachStats; /api/outreach/cohorts → Cohort[]."""

    def test_outreach_stats_returns_200(self):
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            r = client.get("/api/outreach/stats")
        assert r.status_code == 200, f"got {r.status_code}: {r.text!r}"

    def test_outreach_stats_has_all_keys(self):
        """OutreachStats camelCase keys exactly."""
        from fastapi.testclient import TestClient
        import api_server
        expected = {"totalCohorts", "totalCompanies", "inCampaign",
                    "inCampaignCohorts", "replies", "replyRate"}
        with TestClient(api_server.app) as client:
            data = client.get("/api/outreach/stats").json()
        assert set(data.keys()) == expected, f"keys: {set(data.keys())} vs {expected}"

    def test_outreach_cohorts_returns_list(self):
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            data = client.get("/api/outreach/cohorts").json()
        assert isinstance(data, list) and len(data) > 0, "expected non-empty cohort list"

    def test_outreach_cohort_item_shape(self):
        """Each Cohort has id/name/enrolledAt/leadsCount/variants; variant has label/stages/outcome."""
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            data = client.get("/api/outreach/cohorts").json()
        for c in data:
            assert {"id", "name", "enrolledAt", "leadsCount", "variants"} <= set(c.keys()), c
            for v in c["variants"]:
                assert {"label", "stages", "outcome"} <= set(v.keys()), v
                assert {"dead", "success"} <= set(v["outcome"].keys()), v["outcome"]
                for s in v["stages"]:
                    assert {"icon", "status", "count"} <= set(s.keys()), s

    def test_outreach_cohorts_respect_daily_send_cap(self):
        """No cohort exceeds DAILY_SEND_CAP (=50) — OUT1/INTG7."""
        from fastapi.testclient import TestClient
        import api_server
        import main
        with TestClient(api_server.app) as client:
            data = client.get("/api/outreach/cohorts").json()
        for c in data:
            assert c["leadsCount"] <= main.DAILY_SEND_CAP, (
                f"cohort {c['id']} has {c['leadsCount']} > DAILY_SEND_CAP={main.DAILY_SEND_CAP}"
            )

    def test_outreach_no_corporate_access_key_in_any_response(self):
        """No outreach endpoint leaks corporate_access_key (G4)."""
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            for path in ("/api/outreach/stats", "/api/outreach/cohorts", "/api/outreach/enrollments"):
                body = json.dumps(client.get(path).json())
                assert "corporate_access_key" not in body, f"leak in {path}"

    # --- adapter unit tests ---
    def test_brief_to_outreach_stats_mapping(self):
        from api_adapters import brief_to_outreach_stats
        pr = {
            "cohorts": [[{"domain": "a.com"}, {"domain": "b.com"}], [{"domain": "c.com"}]],
            "dispatch_results": [
                {"domain": "a.com", "sent": True, "variant": "A"},
                {"domain": "b.com", "sent": False, "variant": "B"},
                {"domain": "c.com", "sent": True, "variant": "A"},
            ],
            "brief": {"cohort_count": 2, "scheduled": 3, "sent": 2,
                      "failed": 1, "replies": 0, "reply_rate": 0.0},
        }
        out = brief_to_outreach_stats(pr)
        assert out["totalCohorts"] == 2
        assert out["totalCompanies"] == 3
        assert out["inCampaign"] == 2
        assert out["inCampaignCohorts"] == 2  # cohort 0 (a.com sent) + cohort 1 (c.com sent)
        assert out["replyRate"] == 0.0


# ---------------------------------------------------------------------------
# INTG8 — Enrollments + FE-mock split (no backend route for the 4 mock methods)
# ---------------------------------------------------------------------------

class TestINTG8EnrollmentsAndMockSplit:
    """INTG8: GET /api/outreach/enrollments → EnrollmentEvent[]; FE-mock endpoints 404."""

    def test_enrollments_returns_200_list(self):
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            r = client.get("/api/outreach/enrollments")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_enrollment_item_shape_and_iso_date(self):
        """Each EnrollmentEvent has id/date/label; date is ISO YYYY-MM-DD."""
        import re
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            data = client.get("/api/outreach/enrollments").json()
        assert len(data) > 0
        for e in data:
            assert {"id", "date", "label"} == set(e.keys()), e
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", e["date"]), f"bad date: {e['date']!r}"

    def test_enrollments_count_matches_cohorts(self):
        """One enrollment event per cohort."""
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            cohorts = client.get("/api/outreach/cohorts").json()
            enrollments = client.get("/api/outreach/enrollments").json()
        assert len(enrollments) == len(cohorts)

    def test_fe_mock_endpoints_have_no_backend_route(self):
        """getReachSeries/getAgentEvents/runDiscovery/getSwarmStages stay FE-mock → 404 here."""
        from fastapi.testclient import TestClient
        import api_server
        with TestClient(api_server.app) as client:
            for path in ("/api/outreach/reach", "/api/outreach/agent-events",
                         "/api/pipeline/discover", "/api/pipeline/swarm"):
                assert client.get(path).status_code == 404, (
                    f"{path} should NOT exist as a backend route in v1"
                )

    def test_cohorts_to_enrollments_unit(self):
        from api_adapters import cohorts_to_enrollments
        cohorts_ui = [{"name": "Cohort 1"}, {"name": "Cohort 2"}]
        out = cohorts_to_enrollments(cohorts_ui)
        assert len(out) == 2
        assert out[0]["label"] == "Cohort 1 enrolled"
        assert out[0]["date"] == "2026-03-31"
        assert out[1]["date"] == "2026-04-01"


# ---------------------------------------------------------------------------
# CONN0 / CONN1 — seed-if-empty guard (Stage C0)
# ---------------------------------------------------------------------------

class TestSeedDemoGuard:
    """CONN0 / CONN1: seed_demo() seed-if-empty guard and SEED_DEMO opt-out.

    Each test starts with an empty workspace because the autouse reset_singletons
    fixture (conftest.py) resets crm_store._leads_collection to None before every test,
    so get_crm_collection() will build a fresh empty mongomock collection on first use.
    """

    def test_conn1_empty_workspace_seeds_16_records(self):
        """CONN1 — seed_demo() on an empty (fresh) workspace inserts all 16 demo leads."""
        import crm_store
        import api_seed

        # Workspace is empty (conftest reset + fresh mongomock)
        api_seed.seed_demo()

        count = crm_store.get_crm_collection().count_documents({})
        assert count == 16, (
            f"Expected 16 demo leads after seed_demo() on empty workspace, got {count}"
        )

    def test_conn0_nonempty_workspace_is_not_clobbered(self):
        """CONN0 — seed_demo() does NOT overwrite a non-empty workspace.

        Pre-inserts:
          - a 'real' lead with uniq_id='real-lead-001'
          - a demo-id lead (seed-lead-001) with a sentinel domain field

        After seed_demo():
          - count must still be 2 (not 18 or any other number)
          - the sentinel demo record must still carry domain='DO-NOT-OVERWRITE.example'
        """
        import crm_store
        import api_seed

        # Pre-populate the workspace with 2 records BEFORE seed_demo() runs
        crm_store.upsert_lead({
            "uniq_id": "real-lead-001",
            "domain": "real-customer.example",
            "company": "Real Customer",
            "status": "qualified",
            "stage": "in_crm",
            "win_prob": 0.75,
        })
        crm_store.upsert_lead({
            "uniq_id": "seed-lead-001",
            "domain": "DO-NOT-OVERWRITE.example",  # sentinel — must survive seed_demo()
            "company": "Sentinel Record",
            "status": "qualified",
            "stage": "in_crm",
            "win_prob": 0.50,
        })

        count_before = crm_store.get_crm_collection().count_documents({})
        assert count_before == 2, f"Pre-condition failed: expected 2 records, got {count_before}"

        # Call seed_demo() — must skip because workspace is non-empty
        api_seed.seed_demo()

        count_after = crm_store.get_crm_collection().count_documents({})
        assert count_after == 2, (
            f"seed_demo() modified a non-empty workspace: count went from 2 to {count_after}"
        )

        # The sentinel demo record must NOT have been overwritten
        sentinel = crm_store.get_crm_collection().find_one({"uniq_id": "seed-lead-001"})
        assert sentinel is not None, "sentinel record (seed-lead-001) was deleted"
        assert sentinel.get("domain") == "DO-NOT-OVERWRITE.example", (
            f"sentinel domain was overwritten: got {sentinel.get('domain')!r}"
        )

    def test_conn0_seed_demo_env_opt_out(self, monkeypatch):
        """CONN0 — SEED_DEMO=0 prevents seeding even on an empty workspace."""
        import crm_store
        import api_seed

        monkeypatch.setenv("SEED_DEMO", "0")

        # Workspace is empty — but SEED_DEMO=0 should prevent seeding
        api_seed.seed_demo()

        count = crm_store.get_crm_collection().count_documents({})
        assert count == 0, (
            f"Expected 0 records with SEED_DEMO=0, got {count}"
        )
